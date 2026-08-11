"""Integration tests against real Postgres (product spec §27: never
publish the same fact-check twice)."""
import uuid
from datetime import datetime, timezone

import pytest

from app.db.models import (
    Claim,
    ClaimType,
    ConfidenceBand,
    FactCheck,
    FactCheckStatus,
    Platform,
    Reel,
    Verdict,
    VerdictLabel,
)
from app.db.session import AsyncSessionLocal
from app.pipeline.duplicate_detection import find_duplicate


async def _make_published_fact_check(db, *, claim_text: str, media_hash: str | None = None) -> tuple[Reel, Claim]:
    reel = Reel(source_url="https://instagram.com/reel/original", platform=Platform.instagram, media_content_hash=media_hash)
    db.add(reel)
    await db.flush()

    claim = Claim(reel_id=reel.id, text=claim_text, claim_type=ClaimType.factual, verifiable=True)
    db.add(claim)
    await db.flush()

    now = datetime.now(timezone.utc)
    verdict = Verdict(
        claim_id=claim.id,
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        confidence_band=ConfidenceBand.very_high,
        reasoning_summary="...",
        cited_evidence_ids=[],
        verdict_model="test",
        created_at=now,
    )
    db.add(verdict)
    await db.flush()

    fact_check = FactCheck(
        reel_id=reel.id,
        primary_claim_id=claim.id,
        current_verdict_id=verdict.id,
        status=FactCheckStatus.published,
    )
    db.add(fact_check)
    await db.flush()
    return reel, claim


@pytest.mark.asyncio
async def test_exact_reel_reupload_is_flagged_as_duplicate():
    shared_hash = f"hash-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as db:
        await _make_published_fact_check(db, claim_text="Some claim about policy X.", media_hash=shared_hash)

        new_reel = Reel(source_url="https://instagram.com/reel/reupload", media_content_hash=shared_hash)
        db.add(new_reel)
        await db.flush()
        new_claim = Claim(reel_id=new_reel.id, text="A totally different claim.", claim_type=ClaimType.factual, verifiable=True)
        db.add(new_claim)
        await db.flush()

        match = await find_duplicate(db, new_reel, new_claim)
        await db.rollback()

    assert match is not None
    assert "content hash" in match.reason.lower()


@pytest.mark.asyncio
async def test_similar_claim_text_is_flagged_as_duplicate():
    async with AsyncSessionLocal() as db:
        await _make_published_fact_check(
            db, claim_text="The Ministry of Finance raised fuel taxes by 12 percent in March 2026."
        )

        new_reel = Reel(source_url="https://instagram.com/reel/different-video")
        db.add(new_reel)
        await db.flush()
        new_claim = Claim(
            reel_id=new_reel.id,
            text="The Ministry of Finance raised fuel taxes by 12 percent in March 2026",  # near-identical, no period
            claim_type=ClaimType.factual,
            verifiable=True,
        )
        db.add(new_claim)
        await db.flush()

        match = await find_duplicate(db, new_reel, new_claim)
        await db.rollback()

    assert match is not None
    assert "similar claim" in match.reason.lower()


@pytest.mark.asyncio
async def test_unrelated_claim_is_not_flagged_as_duplicate():
    async with AsyncSessionLocal() as db:
        await _make_published_fact_check(db, claim_text="The city council approved a new transit budget.")

        new_reel = Reel(source_url="https://instagram.com/reel/unrelated")
        db.add(new_reel)
        await db.flush()
        new_claim = Claim(
            reel_id=new_reel.id,
            text="A foreign minister resigned after a corruption investigation.",
            claim_type=ClaimType.factual,
            verifiable=True,
        )
        db.add(new_claim)
        await db.flush()

        match = await find_duplicate(db, new_reel, new_claim)
        await db.rollback()

    assert match is None


@pytest.mark.asyncio
async def test_rejected_fact_checks_do_not_count_as_existing_duplicates():
    async with AsyncSessionLocal() as db:
        _, claim = await _make_published_fact_check(db, claim_text="A claim that was later rejected on review.")
        # Flip the fact_check we just made to rejected.
        from sqlalchemy import select

        fc = (await db.execute(select(FactCheck).where(FactCheck.primary_claim_id == claim.id))).scalar_one()
        fc.status = FactCheckStatus.rejected
        await db.flush()

        new_reel = Reel(source_url="https://instagram.com/reel/resubmitted")
        db.add(new_reel)
        await db.flush()
        new_claim = Claim(
            reel_id=new_reel.id,
            text="A claim that was later rejected on review.",
            claim_type=ClaimType.factual,
            verifiable=True,
        )
        db.add(new_claim)
        await db.flush()

        match = await find_duplicate(db, new_reel, new_claim)
        await db.rollback()

    assert match is None
