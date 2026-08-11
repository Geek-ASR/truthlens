"""Stage 1: ingestion. Two paths:

1. Manual, human-supplied media (docs/ARCHITECTURE.md §2) — the default,
   fully compliant path: the operator uploads the video or pastes a
   transcript themselves.
2. Opt-in auto-fetch (`ReelCreate.auto_fetch=True`, docs/ARCHITECTURE.md
   §2a) — the backend downloads the video/caption itself via yt-dlp. For
   Instagram this operates outside Instagram's ToS; it is off by default
   and only runs when explicitly requested per-reel."""
import hashlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProviderError
from app.db.models import ActorType, DiscoverySource, IngestionStatus, Reel
from app.pipeline.audit import record_audit
from app.schemas.reel import ReelCreate
from app.services.media import extract_audio, extract_thumbnail, sample_frames
from app.services.storage.s3 import get_storage_client
from app.services.url_downloader import fetch_from_url


async def ingest_reel(db: AsyncSession, payload: ReelCreate, video_bytes: bytes | None, submitted_by_user_id) -> Reel:
    fetched_meta = None
    tmp_fetch_dir: tempfile.TemporaryDirectory | None = None

    if not video_bytes and not payload.pasted_transcript:
        if not payload.auto_fetch:
            raise ValueError(
                "Either an uploaded video file, a pasted transcript, or auto_fetch=true is required."
            )
        tmp_fetch_dir = tempfile.TemporaryDirectory()
        try:
            fetched_meta = fetch_from_url(str(payload.source_url), tmp_fetch_dir.name)
        except ProviderError:
            tmp_fetch_dir.cleanup()
            raise
        if fetched_meta.video_path:
            video_bytes = Path(fetched_meta.video_path).read_bytes()
        elif not fetched_meta.caption_text:
            tmp_fetch_dir.cleanup()
            raise ProviderError(
                f"auto_fetch could not find a video or caption at {payload.source_url}."
            )

    fetched_posted_at = None
    if fetched_meta and fetched_meta.posted_at:
        fetched_posted_at = datetime.strptime(fetched_meta.posted_at, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    reel = Reel(
        source_url=str(payload.source_url),
        platform=payload.platform,
        creator_handle=payload.creator_handle or (fetched_meta.creator_handle if fetched_meta else None),
        caption_text=payload.caption_text or (fetched_meta.caption_text if fetched_meta else None),
        posted_at=payload.posted_at or fetched_posted_at,
        view_count=payload.view_count or (fetched_meta.view_count if fetched_meta else None),
        like_count=payload.like_count or (fetched_meta.like_count if fetched_meta else None),
        comment_count=payload.comment_count or (fetched_meta.comment_count if fetched_meta else None),
        share_count=payload.share_count,
        hashtags=payload.hashtags or (fetched_meta.hashtags if fetched_meta else []),
        transcript=payload.pasted_transcript,
        discovery_source=DiscoverySource.manual,
        ingestion_status=IngestionStatus.uploaded,
        auto_fetched=fetched_meta is not None,
        submitted_by_user_id=submitted_by_user_id,
    )

    storage = get_storage_client()

    if video_bytes:
        content_hash = hashlib.sha256(video_bytes).hexdigest()
        reel.media_content_hash = content_hash

        video_key = storage.generate_key("reels/video", "mp4")
        storage.put_bytes(video_key, video_bytes, content_type="video/mp4")
        reel.media_storage_key = video_key

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = str(Path(tmpdir) / "input.mp4")
            Path(video_path).write_bytes(video_bytes)

            # Prefer the platform-provided thumbnail from auto-fetch when
            # available; otherwise extract a keyframe with ffmpeg.
            if fetched_meta and fetched_meta.thumbnail_path:
                thumb_bytes = Path(fetched_meta.thumbnail_path).read_bytes()
                thumb_ext = Path(fetched_meta.thumbnail_path).suffix.lstrip(".") or "jpg"
            else:
                thumb_local_path = extract_thumbnail(video_path, tmpdir)
                thumb_bytes = Path(thumb_local_path).read_bytes()
                thumb_ext = "jpg"

            thumb_key = storage.generate_key("reels/thumbnail", thumb_ext)
            storage.put_bytes(thumb_key, thumb_bytes, content_type=f"image/{thumb_ext}")
            reel.thumbnail_storage_key = thumb_key

    if tmp_fetch_dir:
        tmp_fetch_dir.cleanup()

    db.add(reel)
    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.human if not payload.auto_fetch else ActorType.system,
        actor=str(submitted_by_user_id) if submitted_by_user_id else "unauthenticated-ingest",
        action="ingest_reel",
        input_summary={"source_url": str(payload.source_url), "auto_fetch": payload.auto_fetch},
        output_summary={"reel_id": str(reel.id), "has_video": bool(video_bytes)},
    )
    return reel


def extract_media_artifacts(video_bytes: bytes) -> tuple[str, list[str]]:
    """Returns (audio_path, frame_paths) in a temp dir the caller is
    responsible for cleaning up alongside the returned tempdir context."""
    tmpdir = tempfile.mkdtemp()
    video_path = str(Path(tmpdir) / "input.mp4")
    Path(video_path).write_bytes(video_bytes)
    audio_path = extract_audio(video_path, tmpdir)
    frame_paths = sample_frames(video_path, tmpdir)
    return audio_path, frame_paths
