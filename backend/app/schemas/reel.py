import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from app.schemas.common import DiscoverySource, IngestionStatus, Platform


class ReelCreate(BaseModel):
    """Phase 1 manual ingestion (docs/ARCHITECTURE.md §2): the operator
    supplies the URL for attribution/citation, and the actual media is
    uploaded as a separate multipart file on the same request. At least
    one of the video file or a pasted transcript must be provided."""

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
    transcript: str | None
    transcript_segments: list | None
    ocr_text: list | None
    discovery_source: DiscoverySource
    ingestion_status: IngestionStatus
    created_at: datetime

    model_config = {"from_attributes": True}
