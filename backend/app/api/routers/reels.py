from datetime import datetime

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DbSession, RequireReviewer
from app.api.routers.fact_checks import _load_fact_check_detail
from app.core.exceptions import DuplicateFactCheckError, ProviderError
from app.db.models import Reel
from app.pipeline.orchestrator import analyze_reel, build_reel_fact_check
from app.pipeline.ingestion import ingest_reel
from app.schemas.claim import ClaimOut
from app.schemas.common import Platform
from app.schemas.fact_check import FactCheckDetail
from app.schemas.reel import QuickFactCheckRequest, ReelCreate, ReelOut

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
    auto_fetch: bool = Form(False),
    video: UploadFile | None = File(None),
):
    """Two ways to supply media (docs/ARCHITECTURE.md §2/§2a):
    upload `video` / paste `pasted_transcript` yourself (default, fully
    compliant), or set `auto_fetch=true` to have the backend download the
    video/caption from `source_url` itself via yt-dlp — for Instagram
    URLs this runs outside Instagram's Terms of Service and is only
    attempted when explicitly requested."""
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
        auto_fetch=auto_fetch,
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
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"auto_fetch failed: {exc}") from exc
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


@router.post("/quick", response_model=FactCheckDetail, status_code=201)
async def quick_fact_check(payload: QuickFactCheckRequest, db: DbSession, current_user: RequireReviewer):
    """The one-box flow: paste a URL, get back a finished fact-check —
    ingest (auto_fetch) -> analyze -> build the reel-level fact-check, all
    in one call. Equivalent to running the 3-step manual flow yourself.
    Takes 1-3+ minutes on local models; this is a long synchronous call,
    not a background job, matching how /analyze already behaves.

    If a later stage fails, whatever the earlier stages already committed
    (the reel, its transcript, extracted claims, verdicts) is NOT lost —
    each stage commits before the next begins, so the normal multi-step
    dashboard flow (RequireReviewer > /reels/{id}) can pick up from
    wherever this left off."""
    create_payload = ReelCreate(source_url=payload.source_url, platform=payload.platform, auto_fetch=True)
    try:
        reel = await ingest_reel(db, create_payload, None, current_user.id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"Could not fetch this reel: {exc}") from exc
    await db.commit()
    await db.refresh(reel)
    # Captured now, while the session is fresh, rather than read from
    # `reel.id` after a later rollback: AsyncSession expires ORM
    # attributes on commit/rollback by default, and accessing an expired
    # attribute triggers a lazy-reload that needs an awaited DB round
    # trip — doing that implicitly inside an f-string (no await) crashes
    # with "MissingGreenlet: greenlet_spawn has not been called" instead
    # of raising the intended HTTPException. Found live: the first
    # request that ever hit this exact path (zero verifiable claims
    # extracted from a photo post) surfaced it as a bare 500 instead of
    # the intended 400 with a helpful message.
    reel_id = reel.id

    try:
        reel = await analyze_reel(db, reel)
    except ProviderError as exc:
        await db.rollback()
        raise HTTPException(502, f"Analysis failed: {exc}") from exc
    await db.commit()

    try:
        fact_check = await build_reel_fact_check(db, reel)
    except DuplicateFactCheckError as exc:
        await db.commit()
        raise HTTPException(409, f"DUPLICATE — DO NOT PUBLISH: {exc}") from exc
    except (ValueError, ProviderError) as exc:
        await db.rollback()
        raise HTTPException(
            400,
            f"{exc} The reel and its research were still saved (id={reel_id}) — "
            f"you can retry research or build a fact-check for it manually from the dashboard.",
        ) from exc

    await db.commit()
    return await _load_fact_check_detail(db, fact_check.id)


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
