from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireReviewer
from app.core.exceptions import ProviderError
from app.db.models import Reel
from app.pipeline.orchestrator import analyze_reel
from app.pipeline.ingestion import ingest_reel
from app.schemas.claim import ClaimOut
from app.schemas.common import Platform
from app.schemas.reel import ReelCreate, ReelOut

router = APIRouter()

_MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB


@router.post("", response_model=ReelOut, status_code=201)
async def create_reel(
    db: DbSession,
    current_user: RequireReviewer,
    source_url: str = Form(...),
    platform: Platform = Form(Platform.instagram),
    creator_handle: str | None = Form(None),
    caption_text: str | None = Form(None),
    posted_at: datetime | None = Form(None),
    view_count: int | None = Form(None),
    like_count: int | None = Form(None),
    comment_count: int | None = Form(None),
    share_count: int | None = Form(None),
    hashtags: str | None = Form(None, description="comma-separated"),
    pasted_transcript: str | None = Form(None),
    video: UploadFile | None = File(None),
):
    """Phase 1 manual ingestion (docs/ARCHITECTURE.md §2). `video` is the
    operator-supplied media file — this endpoint never scrapes Instagram."""
    payload = ReelCreate(
        source_url=source_url,
        platform=platform,
        creator_handle=creator_handle,
        caption_text=caption_text,
        posted_at=posted_at,
        view_count=view_count,
        like_count=like_count,
        comment_count=comment_count,
        share_count=share_count,
        hashtags=[h.strip() for h in hashtags.split(",")] if hashtags else [],
        pasted_transcript=pasted_transcript,
    )

    video_bytes = None
    if video is not None:
        video_bytes = await video.read()
        if len(video_bytes) > _MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Uploaded video exceeds the 200MB limit.")

    try:
        reel = await ingest_reel(db, payload, video_bytes, current_user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.commit()
    await db.refresh(reel)
    return reel


@router.post("/{reel_id}/analyze", response_model=ReelOut)
async def analyze(reel_id: str, db: DbSession, current_user: RequireReviewer):
    """Runs transcription -> OCR -> vision context -> claim extraction ->
    research -> evidence -> verdict for every verifiable claim
    (product spec §38 steps 2-8, the "Analyze" button)."""
    result = await db.execute(select(Reel).where(Reel.id == reel_id))
    reel = result.scalar_one_or_none()
    if reel is None:
        raise HTTPException(404, "Reel not found")

    try:
        reel = await analyze_reel(db, reel)
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"Analysis failed: {exc}") from exc
    await db.commit()
    await db.refresh(reel)
    return reel


@router.get("/{reel_id}", response_model=ReelOut)
async def get_reel(reel_id: str, db: DbSession, current_user: RequireReviewer):
    result = await db.execute(select(Reel).where(Reel.id == reel_id))
    reel = result.scalar_one_or_none()
    if reel is None:
        raise HTTPException(404, "Reel not found")
    return reel


@router.get("/{reel_id}/claims", response_model=list[ClaimOut])
async def get_reel_claims(reel_id: str, db: DbSession, current_user: RequireReviewer):
    result = await db.execute(select(Reel).options(selectinload(Reel.claims)).where(Reel.id == reel_id))
    reel = result.scalar_one_or_none()
    if reel is None:
        raise HTTPException(404, "Reel not found")
    return reel.claims


@router.get("", response_model=list[ReelOut])
async def list_reels(db: DbSession, current_user: RequireReviewer, limit: int = 50):
    result = await db.execute(select(Reel).order_by(Reel.created_at.desc()).limit(limit))
    return list(result.scalars().all())
