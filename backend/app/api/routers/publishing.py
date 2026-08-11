from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession, RequireAdmin, RequireReviewer
from app.core.exceptions import PublishError
from app.core.security import encrypt_secret
from app.db.models import (
    FactCheck,
    FactCheckStatus,
    GeneratedPost,
    InstagramAccount,
    InstagramAccountStatus,
    PublishingJob,
    PublishingJobStatus,
    Slide,
)
from app.pipeline.publishing import publish_fact_check
from app.schemas.fact_check import PublishingJobOut
from app.services.instagram.graph_client import exchange_for_long_lived_token

router = APIRouter()


class ConnectInstagramAccountRequest(BaseModel):
    ig_user_id: str
    ig_username: str | None = None
    facebook_page_id: str | None = None
    short_lived_user_token: str


class InstagramAccountOut(BaseModel):
    id: str
    ig_user_id: str
    ig_username: str | None
    status: InstagramAccountStatus

    model_config = {"from_attributes": True}


@router.post("/instagram-accounts", response_model=InstagramAccountOut, status_code=201)
async def connect_instagram_account(
    payload: ConnectInstagramAccountRequest, db: DbSession, current_user: RequireAdmin
):
    """One-time OAuth connection step (docs/API_REQUIREMENTS.md §1).
    Requires the operator to already have completed the Meta OAuth
    dialog and obtained a short-lived user token for their Instagram
    Business account; this exchanges it for a long-lived token and
    stores it encrypted (docs/SECURITY.md §1)."""
    try:
        exchange_result = await exchange_for_long_lived_token(payload.short_lived_user_token)
    except PublishError as exc:
        raise HTTPException(502, f"Token exchange failed: {exc}") from exc

    long_lived_token = exchange_result["access_token"]
    expires_in_seconds = exchange_result.get("expires_in")  # typically ~5.2M seconds (60 days)
    token_expires_at = (
        datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds) if expires_in_seconds else None
    )

    account = InstagramAccount(
        ig_user_id=payload.ig_user_id,
        ig_username=payload.ig_username,
        facebook_page_id=payload.facebook_page_id,
        access_token_encrypted=encrypt_secret(long_lived_token),
        token_expires_at=token_expires_at,
        connected_by_user_id=current_user.id,
        status=InstagramAccountStatus.active,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/instagram-accounts", response_model=list[InstagramAccountOut])
async def list_instagram_accounts(db: DbSession, current_user: RequireReviewer):
    result = await db.execute(select(InstagramAccount).where(InstagramAccount.status == InstagramAccountStatus.active))
    return list(result.scalars().all())


@router.post("/{fact_check_id}/publish", response_model=PublishingJobOut)
async def publish(fact_check_id: str, db: DbSession, current_user: RequireAdmin):
    """Publishes an approved fact_check (product spec §21). Refuses to
    run twice for the same fact_check (product spec §27: never publish
    the same fact-check twice) — the unique `generated_posts.fact_check_id`
    plus the `fact_check.status` check are the two backstops."""
    fc_result = await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))
    fact_check = fc_result.scalar_one_or_none()
    if fact_check is None:
        raise HTTPException(404, "Fact check not found")
    if fact_check.status == FactCheckStatus.published:
        raise HTTPException(409, "This fact_check has already been published.")
    if fact_check.status != FactCheckStatus.approved:
        raise HTTPException(400, f"Fact check must be approved before publishing (current: {fact_check.status.value})")

    generated_post = (
        await db.execute(select(GeneratedPost).where(GeneratedPost.fact_check_id == fact_check.id))
    ).scalar_one_or_none()
    if generated_post is None:
        raise HTTPException(400, "No approved GeneratedPost found — call the approve endpoint first.")

    account = (
        await db.execute(select(InstagramAccount).where(InstagramAccount.id == generated_post.instagram_account_id))
    ).scalar_one_or_none()
    if account is None:
        raise HTTPException(404, "Instagram account for this post not found")

    slides = list(
        (await db.execute(select(Slide).where(Slide.fact_check_id == fact_check.id))).scalars()
    )
    if len(slides) != 4:
        raise HTTPException(400, f"Expected 4 slides, found {len(slides)}.")

    job = (
        await db.execute(select(PublishingJob).where(PublishingJob.generated_post_id == generated_post.id))
    ).scalar_one_or_none()
    if job is None:
        job = PublishingJob(generated_post_id=generated_post.id, status=PublishingJobStatus.pending)
        db.add(job)
        await db.flush()
    elif job.status == PublishingJobStatus.published:
        raise HTTPException(409, "This fact_check has already been published.")

    try:
        job = await publish_fact_check(db, fact_check, generated_post, account, slides, job)
    except PublishError as exc:
        await db.commit()  # keep the failed-job record for retry/inspection
        raise HTTPException(502, f"Publish failed: {exc}") from exc

    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{fact_check_id}/status", response_model=PublishingJobOut)
async def publish_status(fact_check_id: str, db: DbSession, current_user: RequireReviewer):
    generated_post = (
        await db.execute(select(GeneratedPost).where(GeneratedPost.fact_check_id == fact_check_id))
    ).scalar_one_or_none()
    if generated_post is None:
        raise HTTPException(404, "No publishing record for this fact_check")
    job = (
        await db.execute(select(PublishingJob).where(PublishingJob.generated_post_id == generated_post.id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(404, "No publishing job for this fact_check")
    return job
