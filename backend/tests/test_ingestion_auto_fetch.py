"""Tests for the opt-in auto_fetch ingestion path (docs/ARCHITECTURE.md
§2a). yt-dlp and S3 are mocked — these test our merge/precedence and
plumbing logic, not yt-dlp itself or a real network call."""
import uuid
from pathlib import Path

import pytest

from app.core.exceptions import ProviderError
from app.db.models import MediaType
from app.db.session import AsyncSessionLocal
from app.pipeline import ingestion
from app.schemas.reel import ReelCreate
from app.services.url_downloader import UrlFetchResult


class FakeStorageClient:
    def __init__(self):
        self.puts: list[tuple[str, bytes, str]] = []

    def generate_key(self, prefix: str, extension: str) -> str:
        return f"{prefix}/{uuid.uuid4()}.{extension.lstrip('.')}"

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self.puts.append((key, data, content_type))
        return key


@pytest.fixture
def fake_storage(monkeypatch):
    fake = FakeStorageClient()
    monkeypatch.setattr(ingestion, "get_storage_client", lambda: fake)
    return fake


@pytest.fixture
def tmp_media_files(tmp_path):
    video_path = tmp_path / "download.mp4"
    video_path.write_bytes(b"fake-video-bytes")
    thumb_path = tmp_path / "download.jpg"
    thumb_path.write_bytes(b"fake-thumb-bytes")
    return str(video_path), str(thumb_path)


@pytest.mark.asyncio
async def test_auto_fetch_populates_reel_from_fetched_metadata(monkeypatch, fake_storage, tmp_media_files):
    video_path, thumb_path = tmp_media_files
    fetched = UrlFetchResult(
        video_path=video_path,
        thumbnail_path=thumb_path,
        caption_text="Fetched caption text",
        creator_handle="fetched_handle",
        posted_at="2026-03-05",
        view_count=50000,
        like_count=1200,
        comment_count=80,
        hashtags=["politics", "news"],
    )
    monkeypatch.setattr(ingestion, "fetch_from_url", lambda url, out_dir: fetched)

    payload = ReelCreate(source_url="https://instagram.com/reel/autotest", auto_fetch=True)

    async with AsyncSessionLocal() as db:
        reel = await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()

    assert reel.auto_fetched is True
    assert reel.caption_text == "Fetched caption text"
    assert reel.creator_handle == "fetched_handle"
    assert reel.view_count == 50000
    assert reel.hashtags == ["politics", "news"]
    assert reel.media_storage_key is not None
    assert reel.thumbnail_storage_key is not None
    assert reel.posted_at is not None and reel.posted_at.year == 2026 and reel.posted_at.month == 3
    # thumbnail came from the fetch result, not an ffmpeg extraction
    assert any(data == b"fake-thumb-bytes" for _, data, _ in fake_storage.puts)


@pytest.mark.asyncio
async def test_manual_fields_take_precedence_over_fetched_metadata(monkeypatch, fake_storage, tmp_media_files):
    video_path, thumb_path = tmp_media_files
    fetched = UrlFetchResult(
        video_path=video_path,
        thumbnail_path=thumb_path,
        caption_text="Fetched caption",
        creator_handle="fetched_handle",
        posted_at=None,
        view_count=999,
        like_count=None,
        comment_count=None,
        hashtags=["fetched-tag"],
    )
    monkeypatch.setattr(ingestion, "fetch_from_url", lambda url, out_dir: fetched)

    payload = ReelCreate(
        source_url="https://instagram.com/reel/autotest2",
        auto_fetch=True,
        caption_text="Operator-provided caption",
        creator_handle="operator_handle",
    )

    async with AsyncSessionLocal() as db:
        reel = await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()

    assert reel.caption_text == "Operator-provided caption"
    assert reel.creator_handle == "operator_handle"
    assert reel.view_count == 999  # not overridden, so falls back to fetched value


@pytest.mark.asyncio
async def test_auto_fetch_failure_propagates_as_provider_error(monkeypatch, fake_storage):
    def _raise(url, out_dir):
        raise ProviderError("could not fetch")

    monkeypatch.setattr(ingestion, "fetch_from_url", _raise)
    payload = ReelCreate(source_url="https://instagram.com/reel/willfail", auto_fetch=True)

    async with AsyncSessionLocal() as db:
        with pytest.raises(ProviderError):
            await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()


@pytest.mark.asyncio
async def test_no_media_no_transcript_no_auto_fetch_raises_value_error(fake_storage):
    payload = ReelCreate(source_url="https://instagram.com/reel/nothing")

    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError):
            await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()


# ---------------------------------------------------------------------------
# Photo posts (no video stream at all — app/services/url_downloader.py's
# Open Graph fallback). Confirmed live against a real photo post
# (instagram.com/p/Dbrw0EPhFcU/) during development.
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_photo_file(tmp_path):
    photo_path = tmp_path / "download.jpg"
    photo_path.write_bytes(b"fake-photo-bytes")
    return str(photo_path)


@pytest.mark.asyncio
async def test_photo_post_sets_media_type_photo_and_reuses_image_as_thumbnail(
    monkeypatch, fake_storage, tmp_photo_file
):
    fetched = UrlFetchResult(
        video_path=None,
        thumbnail_path=None,
        caption_text="The second poorest state by income, but number one in publicity and propaganda",
        creator_handle="thenewindia2",
        posted_at="2026-08-05",
        view_count=None,
        like_count=13000,
        comment_count=222,
        hashtags=[],
        photo_path=tmp_photo_file,
    )
    monkeypatch.setattr(ingestion, "fetch_from_url", lambda url, out_dir: fetched)

    payload = ReelCreate(source_url="https://www.instagram.com/p/Dbrw0EPhFcU/", auto_fetch=True)

    async with AsyncSessionLocal() as db:
        reel = await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()

    assert reel.media_type == MediaType.photo
    assert reel.media_storage_key is not None
    # The photo doubles as its own thumbnail -- same key, not a second upload.
    assert reel.thumbnail_storage_key == reel.media_storage_key
    assert reel.media_content_hash is not None
    assert reel.caption_text.startswith("The second poorest state")
    assert reel.like_count == 13000
    assert reel.comment_count == 222
    # Exactly one upload (the photo) -- no ffmpeg-derived thumbnail upload
    # happened, unlike the video path's two uploads (video + thumbnail).
    assert len(fake_storage.puts) == 1
    assert fake_storage.puts[0][1] == b"fake-photo-bytes"


@pytest.mark.asyncio
async def test_photo_post_with_no_caption_still_ingests(monkeypatch, fake_storage, tmp_photo_file):
    # A photo with a caption-less og:description (e.g. an unparseable
    # format) shouldn't be treated as "nothing found" the way a
    # caption-less, video-less, transcript-less fetch is.
    fetched = UrlFetchResult(
        video_path=None,
        thumbnail_path=None,
        caption_text=None,
        creator_handle=None,
        posted_at=None,
        view_count=None,
        like_count=None,
        comment_count=None,
        hashtags=[],
        photo_path=tmp_photo_file,
    )
    monkeypatch.setattr(ingestion, "fetch_from_url", lambda url, out_dir: fetched)

    payload = ReelCreate(source_url="https://www.instagram.com/p/nocaption/", auto_fetch=True)

    async with AsyncSessionLocal() as db:
        reel = await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()

    assert reel.media_type == MediaType.photo
    assert reel.media_storage_key is not None


@pytest.mark.asyncio
async def test_video_post_still_gets_media_type_video(monkeypatch, fake_storage, tmp_media_files):
    # Regression guard: adding photo support must not change the default
    # for the existing, far more common video path.
    video_path, thumb_path = tmp_media_files
    fetched = UrlFetchResult(
        video_path=video_path,
        thumbnail_path=thumb_path,
        caption_text="A video caption",
        creator_handle="someone",
        posted_at=None,
        view_count=None,
        like_count=None,
        comment_count=None,
        hashtags=[],
    )
    monkeypatch.setattr(ingestion, "fetch_from_url", lambda url, out_dir: fetched)

    payload = ReelCreate(source_url="https://instagram.com/reel/stillvideo", auto_fetch=True)

    async with AsyncSessionLocal() as db:
        reel = await ingestion.ingest_reel(db, payload, None, None)
        await db.rollback()

    assert reel.media_type == MediaType.video
    assert reel.media_storage_key != reel.thumbnail_storage_key


def test_extract_photo_artifact_returns_one_element_frame_list():
    frame_paths = ingestion.extract_photo_artifact(b"fake-photo-bytes")
    assert len(frame_paths) == 1
    assert Path(frame_paths[0]).read_bytes() == b"fake-photo-bytes"
