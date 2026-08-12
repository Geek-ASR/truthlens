"""Regression coverage for Baseline 4 (research/BASELINE_SPEC.md):
SKIP_VALIDATION must persist the LLM's raw, unfiltered proposal while
still computing and recording what validate_verdict() would have found
-- a runtime flag, not a forked codepath, so this ablation can never
silently drift from the real verdict.py logic."""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import get_settings
from app.db.models import (
    Claim,
    ClaimType,
    Evidence,
    EvidenceDirectness,
    EvidenceStance,
    Platform,
    Reel,
    Source,
    SourceTier,
    ValidationStatus,
    VerdictLabel,
)
from app.db.session import AsyncSessionLocal
from app.pipeline.verdict import propose_verdict
from app.services.ai.base import LLMCallResult
from app.schemas.verdict import VerdictProposal


async def _make_claim_with_evidence(db):
    reel = Reel(source_url="https://instagram.com/reel/skip-validation-test", platform=Platform.instagram)
    db.add(reel)
    await db.flush()
    claim = Claim(reel_id=reel.id, text="A claim needing research.", claim_type=ClaimType.factual, verifiable=True)
    db.add(claim)
    await db.flush()

    now = datetime.now(timezone.utc)
    source = Source(
        url="https://example.test/article",
        title="Real article",
        publication_date=None,
        retrieved_at=now,
        source_type=SourceTier.established_news,
        full_text_storage_key="sources/fulltext/fake-key.txt",
        relevant_passage="The event happened on a Tuesday. No specific number is mentioned here at all.",
        reliability_score=0.7,
        reliability_breakdown={},
        created_at=now,
    )
    db.add(source)
    await db.flush()

    evidence = Evidence(
        claim_id=claim.id,
        source_id=source.id,
        stance=EvidenceStance.supports,
        explanation="Confirms the event occurred.",
        directness=EvidenceDirectness.direct,
        analysis_model="test-model",
        created_at=now,
    )
    db.add(evidence)
    await db.flush()

    return claim, [evidence], [source]


def _fake_llm_result(*, cited_evidence_id) -> LLMCallResult:
    # Cites a number ("42,000") that does NOT appear in the source's
    # relevant_passage above -- this is exactly the condition
    # validate_verdict() downgrades as downgraded_unsupported_stat.
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary="This is confirmed true, with 42,000 people affected according to the source.",
        cited_evidence_ids=[cited_evidence_id],
    )
    return LLMCallResult(
        parsed=proposal, raw_output={}, model="test-model", prompt_version="verdict.v2-test"
    )


@pytest.mark.asyncio
async def test_validation_still_downgrades_by_default(monkeypatch):
    """Baseline: SKIP_VALIDATION is False by default -- confirms the
    ablation's control condition (real TruthLens) is what we think it is
    before trusting the flag's effect below."""
    import app.pipeline.verdict as verdict_module

    async with AsyncSessionLocal() as db:
        claim, evidence_rows, sources = await _make_claim_with_evidence(db)

        class _FakeProvider:
            async def structured_call(self, **kwargs):
                return _fake_llm_result(cited_evidence_id=evidence_rows[0].id)

        monkeypatch.setattr(verdict_module, "get_llm_provider", lambda: _FakeProvider())

        verdict = await propose_verdict(db, claim, evidence_rows, sources)
        await db.rollback()

    assert verdict.validation_status == ValidationStatus.downgraded_unsupported_stat
    assert verdict.verdict == VerdictLabel.UNVERIFIED  # downgraded, not the raw TRUE


@pytest.mark.asyncio
async def test_skip_validation_persists_raw_proposal_but_still_records_validation_status(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SKIP_VALIDATION", True)
    import app.pipeline.verdict as verdict_module

    async with AsyncSessionLocal() as db:
        claim, evidence_rows, sources = await _make_claim_with_evidence(db)

        class _FakeProvider:
            async def structured_call(self, **kwargs):
                return _fake_llm_result(cited_evidence_id=evidence_rows[0].id)

        monkeypatch.setattr(verdict_module, "get_llm_provider", lambda: _FakeProvider())

        verdict = await propose_verdict(db, claim, evidence_rows, sources)
        await db.rollback()

    # The raw, unfiltered proposal is what gets persisted...
    assert verdict.verdict == VerdictLabel.TRUE
    assert "42,000" in verdict.reasoning_summary
    assert "[VALIDATION NOTE" not in verdict.reasoning_summary
    assert verdict.cited_evidence_ids == [evidence_rows[0].id]
    # ...but validate_verdict() still ran, and its finding is still
    # recorded -- this is what makes the Baseline-4 vs Full-TruthLens
    # comparison possible at all.
    assert verdict.validation_status == ValidationStatus.downgraded_unsupported_stat
