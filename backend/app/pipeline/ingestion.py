"""Stage 1: ingestion. Manual, human-supplied media per
docs/ARCHITECTURE.md §2 — this never scrapes Instagram itself."""
import hashlib
import tempfile
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActorType, IngestionStatus, Reel
from app.pipeline.audit import record_audit
from app.schemas.reel import ReelCreate
from app.services.media import extract_audio, extract_thumbnail, sample_frames
from app.services.storage.s3 import get_storage_client


async def ingest_reel(db: AsyncSession, payload: ReelCreate, video_bytes: bytes | None, submitted_by_user_id) -> Reel:
    if not video_bytes and not payload.pasted_transcript:
        raise ValueError("Either an uploaded video file or a pasted transcript is required.")

    reel = Reel(
        source_url=str(payload.source_url),
        platform=payload.platform,
        creator_handle=payload.creator_handle,
        caption_text=payload.caption_text,
        posted_at=payload.posted_at,
        view_count=payload.view_count,
        like_count=payload.like_count,
        comment_count=payload.comment_count,
        share_count=payload.share_count,
        hashtags=payload.hashtags,
        transcript=payload.pasted_transcript,
        ingestion_status=IngestionStatus.uploaded,
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

            thumb_path = extract_thumbnail(video_path, tmpdir)
            thumb_key = storage.generate_key("reels/thumbnail", "jpg")
            storage.put_bytes(thumb_key, Path(thumb_path).read_bytes(), content_type="image/jpeg")
            reel.thumbnail_storage_key = thumb_key

    db.add(reel)
    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.human,
        actor=str(submitted_by_user_id) if submitted_by_user_id else "unauthenticated-ingest",
        action="ingest_reel",
        input_summary={"source_url": str(payload.source_url), "has_video": bool(video_bytes)},
        output_summary={"reel_id": str(reel.id)},
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
