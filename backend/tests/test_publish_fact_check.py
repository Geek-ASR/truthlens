"""app/pipeline/publishing.py (Stage 10 -- the actual "post the
approved carousel to the real Instagram account" step) had zero test
coverage despite guarding the one action in this codebase with a real,
irreversible external side effect. Found while verifying the existing
(already-built) carousel-generation-and-publish pipeline end to end,
ahead of connecting a real Instagram Business account.

Builds a real row graph (User -> Reel -> Claim -> FactCheck -> 4 Slides
-> InstagramAccount -> GeneratedPost -> PublishingJob) against Postgres,
matching this project's established pattern (test_fact_check_detail_
endpoint.py), and mocks only the two genuine external boundaries: the
real Graph API call (InstagramGraphClient.publish_full_carousel) and
S3 URL construction (get_storage_client)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.exceptions import PublishError
from app.core.security import encrypt_secret, hash_password
from app.db.models import (
    Claim,
    ClaimType,
    FactCheck,
    FactCheckStatus,
    GeneratedPost,
    InstagramAccount,
    InstagramAccountStatus,
    Platform,
    PublishingJob,
    PublishingJobStatus,
    Reel,
    Slide,
    SlideType,
    User,
)
from app.db.session import AsyncSessionLocal
from app.pipeline.publishing import build_idempotency_key, publish_fact_check
from app.services.instagram.graph_client import InstagramGraphClient


@pytest.fixture
async def scenario():
    """One full, real row graph for a fact_check in `approved` status,
    ready to publish -- everything publish_fact_check actually reads."""
    async with AsyncSessionLocal() as db:
        user = User(
            email=f"test-{uuid.uuid4().hex[:8]}@truthlensapp.io",
            hashed_password=hash_password("test-password-123"),
        )
        db.add(user)
        await db.flush()

        reel = Reel(source_url="https://instagram.com/reel/publish-test", platform=Platform.instagram)
        db.add(reel)
        await db.flush()

        claim = Claim(reel_id=reel.id, text="A claim being fact-checked.", claim_type=ClaimType.factual, verifiable=True)
        db.add(claim)
        await db.flush()

        fact_check = FactCheck(
            reel_id=reel.id, primary_claim_id=claim.id, status=FactCheckStatus.approved,
            caption_text="Fact check caption for the carousel.",
        )
        db.add(fact_check)
        await db.flush()

        for i, slide_type in enumerate([SlideType.poster, SlideType.original_reel, SlideType.evidence, SlideType.conclusion]):
            db.add(Slide(
                fact_check_id=fact_check.id, position=i + 1, slide_type=slide_type,
                image_storage_key=f"slides/{fact_check.id}/{i + 1}.png",
                template_version="slides.v2", content_json={},
            ))
        await db.flush()

        account = InstagramAccount(
            ig_user_id="17841400000000000", ig_username="truthlens_test",
            access_token_encrypted=encrypt_secret("real-long-lived-token"),
            status=InstagramAccountStatus.active,
        )
        db.add(account)
        await db.flush()

        generated_post = GeneratedPost(
            fact_check_id=fact_check.id, instagram_account_id=account.id,
            idempotency_key=build_idempotency_key(fact_check.id, [1, 2, 3, 4]),
            approved_by_user_id=user.id, approved_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(generated_post)
        await db.flush()

        job = PublishingJob(generated_post_id=generated_post.id, status=PublishingJobStatus.pending)
        db.add(job)
        await db.commit()

        ids = (fact_check.id, generated_post.id, account.id, job.id, reel.id, claim.id, user.id)

    yield ids

    async with AsyncSessionLocal() as db:
        fact_check_id, generated_post_id, account_id, job_id, reel_id, claim_id, user_id = ids
        for model, id_ in [
            (PublishingJob, job_id), (GeneratedPost, generated_post_id), (Slide, None),
            (FactCheck, fact_check_id), (Claim, claim_id), (Reel, reel_id),
            (InstagramAccount, account_id), (User, user_id),
        ]:
            if model is Slide:
                rows = (await db.execute(select(Slide).where(Slide.fact_check_id == fact_check_id))).scalars().all()
                for row in rows:
                    await db.delete(row)
            else:
                row = (await db.execute(select(model).where(model.id == id_))).scalar_one_or_none()
                if row:
                    await db.delete(row)
            await db.flush()
        await db.commit()


async def _load(ids):
    fact_check_id, generated_post_id, account_id, job_id, *_ = ids
    async with AsyncSessionLocal() as db:
        fact_check = (await db.execute(select(FactCheck).where(FactCheck.id == fact_check_id))).scalar_one()
        generated_post = (await db.execute(select(GeneratedPost).where(GeneratedPost.id == generated_post_id))).scalar_one()
        account = (await db.execute(select(InstagramAccount).where(InstagramAccount.id == account_id))).scalar_one()
        job = (await db.execute(select(PublishingJob).where(PublishingJob.id == job_id))).scalar_one()
        slides = list((await db.execute(select(Slide).where(Slide.fact_check_id == fact_check_id))).scalars())
        return db, fact_check, generated_post, account, job, slides


class _StubStorage:
    def public_url(self, key: str) -> str:
        return f"https://cdn.test/{key}"


@pytest.mark.asyncio
async def test_happy_path_publishes_and_updates_everything(monkeypatch, scenario):
    monkeypatch.setattr("app.pipeline.publishing.get_storage_client", lambda: _StubStorage())
    monkeypatch.setattr(
        InstagramGraphClient, "publish_full_carousel",
        AsyncMock(return_value=(["c1", "c2", "c3", "c4"], "carousel-1", "ig-media-1", "https://www.instagram.com/p/xyz/")),
    )

    db, fact_check, generated_post, account, job, slides = await _load(scenario)
    result = await publish_fact_check(db, fact_check, generated_post, account, slides, job)
    await db.commit()

    assert result.status == PublishingJobStatus.published
    assert result.ig_media_id == "ig-media-1"
    assert result.permalink == "https://www.instagram.com/p/xyz/"
    assert result.carousel_container_id == "carousel-1"
    assert result.attempt_count == 1
    assert fact_check.status == FactCheckStatus.published
    await db.close()


@pytest.mark.asyncio
async def test_refuses_to_publish_an_already_published_fact_check(monkeypatch, scenario):
    """product spec §27: never publish the same fact-check twice."""
    call = AsyncMock()
    monkeypatch.setattr(InstagramGraphClient, "publish_full_carousel", call)

    db, fact_check, generated_post, account, job, slides = await _load(scenario)
    fact_check.status = FactCheckStatus.published

    with pytest.raises(PublishError, match="already published"):
        await publish_fact_check(db, fact_check, generated_post, account, slides, job)

    call.assert_not_called()
    await db.rollback()
    await db.close()


@pytest.mark.asyncio
async def test_refuses_to_publish_without_a_stored_access_token(scenario):
    db, fact_check, generated_post, account, job, slides = await _load(scenario)
    account.access_token_encrypted = None

    with pytest.raises(PublishError, match="no stored access token"):
        await publish_fact_check(db, fact_check, generated_post, account, slides, job)

    await db.rollback()
    await db.close()


@pytest.mark.asyncio
async def test_graph_api_failure_marks_the_job_failed_and_reraises(monkeypatch, scenario):
    """A failed Graph API call must leave a real, inspectable failure
    record (not silently swallow the error or leave the job stuck at
    'publishing' forever) -- and must NOT flip fact_check.status to
    published."""
    monkeypatch.setattr("app.pipeline.publishing.get_storage_client", lambda: _StubStorage())
    monkeypatch.setattr(
        InstagramGraphClient, "publish_full_carousel",
        AsyncMock(side_effect=PublishError("Graph API error 190/0: token expired")),
    )

    db, fact_check, generated_post, account, job, slides = await _load(scenario)
    with pytest.raises(PublishError, match="token expired"):
        await publish_fact_check(db, fact_check, generated_post, account, slides, job)

    assert job.status == PublishingJobStatus.failed
    assert "token expired" in job.last_error
    assert fact_check.status != FactCheckStatus.published
    await db.commit()
    await db.close()


def test_idempotency_key_is_deterministic_and_order_independent():
    fc_id = uuid.uuid4()
    key_a = build_idempotency_key(fc_id, [3, 1, 2])
    key_b = build_idempotency_key(fc_id, [1, 2, 3])
    assert key_a == key_b


def test_idempotency_key_differs_for_different_fact_checks():
    key_a = build_idempotency_key(uuid.uuid4(), [1, 2, 3])
    key_b = build_idempotency_key(uuid.uuid4(), [1, 2, 3])
    assert key_a != key_b
