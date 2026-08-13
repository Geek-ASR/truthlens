"""Regression coverage for a real gap found live during the Day 5
validator audit (research/VALIDATOR_EVALUATION.md): 32 of 68 real
evidence rows in that run had an empty `explanation` -- including one
`stance=contradicts` row for a source that doesn't obviously contradict
the claim, with no explanation on record either way. Unlike every other
LLM-calling pipeline stage, evidence_analysis.py had no substantiveness
check of its own until this fix."""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.config import get_settings
from app.db.models import Claim, ClaimType, Platform, Reel, SourceTier
from app.db.session import AsyncSessionLocal
from app.pipeline.evidence_analysis import _explanation_looks_substantive, analyze_evidence
from app.schemas.evidence import EvidenceAnalysisItem
from app.services.ai.base import LLMCallResult
from app.services.storage.s3 import get_storage_client


def test_empty_explanation_is_not_substantive():
    assert _explanation_looks_substantive("") is False
    assert _explanation_looks_substantive("   ") is False


def test_real_explanation_is_substantive():
    assert _explanation_looks_substantive("This source directly confirms the claim's key figure.") is True


async def _make_claim_and_source(db):
    reel = Reel(source_url="https://instagram.com/reel/evidence-substantive-test", platform=Platform.instagram)
    db.add(reel)
    await db.flush()
    claim = Claim(reel_id=reel.id, text="A claim needing evidence.", claim_type=ClaimType.factual, verifiable=True)
    db.add(claim)
    await db.flush()

    storage = get_storage_client()
    text_key = storage.generate_key("sources/fulltext", "txt")
    storage.put_bytes(text_key, b"Full real article text about the claim's topic.", content_type="text/plain")

    from app.db.models import Source

    now = datetime.now(timezone.utc)
    source = Source(
        url="https://example.test/article",
        title="Real article",
        publication_date=None,
        retrieved_at=now,
        source_type=SourceTier.established_news,
        full_text_storage_key=text_key,
        relevant_passage="Full real article text about the claim's topic.",
        reliability_score=0.7,
        reliability_breakdown={},
        created_at=now,
    )
    db.add(source)
    await db.flush()
    return claim, source


@pytest.mark.asyncio
async def test_empty_explanation_triggers_gemini_retry(monkeypatch):
    settings = get_settings()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    import app.pipeline.evidence_analysis as evidence_analysis_module

    empty_result = LLMCallResult(
        parsed=EvidenceAnalysisItem(
            source_id=uuid.uuid4(), stance="irrelevant", explanation="", directness="indirect"
        ),
        raw_output={},
        model="ollama-test",
        prompt_version="evidence_analysis.v1-test",
    )

    class _EmptyExplanationProvider:
        async def structured_call(self, **kwargs):
            return empty_result

    class _FakeGeminiProvider:
        async def structured_call(self, **kwargs):
            parsed = EvidenceAnalysisItem(
                source_id=uuid.uuid4(),
                stance="supports",
                explanation="The source's third paragraph directly confirms the claim's central figure.",
                directness="direct",
            )
            return LLMCallResult(parsed=parsed, raw_output={}, model="gemini-test", prompt_version="evidence_analysis.v1-test")

    monkeypatch.setattr(evidence_analysis_module, "get_llm_provider", lambda: _EmptyExplanationProvider())
    monkeypatch.setattr("app.services.ai.gemini_provider.GeminiProvider", _FakeGeminiProvider)

    async with AsyncSessionLocal() as db:
        claim, source = await _make_claim_and_source(db)
        evidence_rows = await analyze_evidence(db, claim, [source])
        await db.rollback()

    assert len(evidence_rows) == 1
    assert evidence_rows[0].explanation.strip() != ""
    assert "confirms the claim" in evidence_rows[0].explanation
    assert evidence_rows[0].stance.value == "supports"  # the retried (Gemini) result, not the empty original


@pytest.mark.asyncio
async def test_real_explanation_is_not_retried(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    import app.pipeline.evidence_analysis as evidence_analysis_module

    call_count = {"n": 0}

    class _RealExplanationProvider:
        async def structured_call(self, **kwargs):
            call_count["n"] += 1
            parsed = EvidenceAnalysisItem(
                source_id=uuid.uuid4(),
                stance="irrelevant",
                explanation="The source discusses an unrelated topic and never mentions the claim's subject.",
                directness="indirect",
            )
            return LLMCallResult(parsed=parsed, raw_output={}, model="ollama-test", prompt_version="evidence_analysis.v1-test")

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Gemini must not be called when the original explanation was already substantive")

    monkeypatch.setattr(evidence_analysis_module, "get_llm_provider", lambda: _RealExplanationProvider())
    monkeypatch.setattr("app.services.ai.gemini_provider.GeminiProvider", _fail_if_called)

    async with AsyncSessionLocal() as db:
        claim, source = await _make_claim_and_source(db)
        evidence_rows = await analyze_evidence(db, claim, [source])
        await db.rollback()

    assert call_count["n"] == 1
    assert evidence_rows[0].explanation.startswith("The source discusses")
