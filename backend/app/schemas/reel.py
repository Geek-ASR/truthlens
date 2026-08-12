import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import DiscoverySource, IngestionStatus, Platform


class ReelCreate(BaseModel):
    """Two ingestion paths (docs/ARCHITECTURE.md §2, §2a):

    1. Manual (default): the operator uploads the video file and/or
       pastes a transcript themselves. Fully compliant, no platform ToS
       exposure.
    2. auto_fetch=True: the backend downloads the video/caption itself
       from source_url via yt-dlp. For Instagram URLs this is outside
       Instagram's Terms of Service — off by default, opt-in per reel.

    At least one of {uploaded video file, pasted transcript, auto_fetch}
    must be provided/true."""

    source_url: HttpUrl
    platform: Platform = Platform.instagram
    creator_handle: str | None = Field(default=None, max_length=255)
    caption_text: str | None = None
    posted_at: datetime | None = None
    view_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    hashtags: list[str] = Field(default_factory=list)
    pasted_transcript: str | None = None
    auto_fetch: bool = Field(
        default=False,
        description=(
            "Fetch the video/caption automatically from source_url via yt-dlp instead of "
            "requiring a manual upload. For Instagram URLs this operates outside Instagram's "
            "Terms of Service — see docs/ARCHITECTURE.md §2a. Off by default."
        ),
    )


class QuickFactCheckRequest(BaseModel):
    """The one-box "just paste a URL" flow: ingest (auto_fetch) -> analyze
    -> build the reel-level fact-check, all in one call. Equivalent to the
    3-step manual flow (POST /reels, POST /reels/{id}/analyze, POST
    /claims/{id}/build-fact-check) with auto_fetch always on, since
    there's no separate step to upload a video or paste a transcript."""

    source_url: HttpUrl
    platform: Platform = Platform.instagram


class ReelOut(BaseModel):
    id: uuid.UUID
    source_url: str
    platform: Platform
    creator_handle: str | None
    caption_text: str | None
    posted_at: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None
    hashtags: list[str] | None
    thumbnail_storage_key: str | None
    auto_fetched: bool
    transcript: str | None
    transcript_segments: list | None
    ocr_text: list | None
    discovery_source: DiscoverySource
    ingestion_status: IngestionStatus
    created_at: datetime

    model_config = {"from_attributes": True}
