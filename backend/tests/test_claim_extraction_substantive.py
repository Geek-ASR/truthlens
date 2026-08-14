"""Regression coverage for a real gap found live against
https://www.instagram.com/p/Db6Dd14Cte5/: Ollama returned two schema
-valid claims (claim_type=satire, verifiable=False, text="") for a reel
whose OCR text actually contained multiple checkable claims. Existing
_extraction_looks_grounded never caught this, because it only evaluates
verifiable claims' source_quote and is a no-op whenever every claim
comes back non-verifiable -- exactly what happened here."""
import pytest

from app.core.config import get_settings
from app.db.models import Claim, Platform, Reel
from app.db.session import AsyncSessionLocal
from app.pipeline.claim_extraction import _extraction_looks_substantive, extract_claims
from app.schemas.claim import ClaimExtractionResult, ExtractedClaim
from app.services.ai.base import LLMCallResult


def _claim(text: str, *, verifiable=False, claim_type="satire") -> ExtractedClaim:
    return ExtractedClaim(
        text=text, source_quote=None, claim_type=claim_type, verifiable=verifiable, importance=0.5,
        extraction_confidence=0.5,
    )


def test_all_claims_blank_text_is_not_substantive():
    claims = [_claim(""), _claim("  ")]
    assert _extraction_looks_substantive(claims) is False


def test_one_real_claim_among_blanks_is_substantive():
    claims = [_claim(""), _claim("A real, non-empty claim", verifiable=True, claim_type="factual")]
    assert _extraction_looks_substantive(claims) is True


def test_empty_extraction_is_not_treated_as_a_quality_failure():
    # A genuine "found nothing" result (e.g. pure entertainment content)
    # is a legitimate outcome, not the failure this check targets.
    assert _extraction_looks_substantive([]) is True


def test_non_verifiable_claim_with_real_text_is_substantive():
    # Must not regress test_no_verifiable_claims_is_not_treated_as_a_quality_failure
    # in test_claim_extraction_grounding.py -- opinion/satire claims with
    # actual text are a fine, legitimate extraction outcome.
    claims = [_claim("This is just an opinion", verifiable=False, claim_type="opinion")]
    assert _extraction_looks_substantive(claims) is True


@pytest.mark.asyncio
async def test_blank_text_claims_are_never_persisted(monkeypatch):
    """Defensive backstop, independent of whether the retry cascade
    fires: a Claim row with empty text must never reach the database,
    the same "never store what we can't actually use" discipline as
    search_fetch.py never storing a Source we couldn't fetch."""
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)  # force no retry, isolate the persist-filter

    class _GarbageProvider:
        async def structured_call(self, **kwargs):
            parsed = ClaimExtractionResult(
                claims=[
                    _claim(""),
                    _claim("   "),
                    _claim("A real claim with actual content", verifiable=True, claim_type="factual"),
                ]
            )
            return LLMCallResult(parsed=parsed, raw_output={}, model="test-model", prompt_version="test.v1")

    import app.pipeline.claim_extraction as claim_extraction_module

    monkeypatch.setattr(claim_extraction_module, "get_llm_provider", lambda: _GarbageProvider())

    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/blank-claim-test", platform=Platform.instagram, caption_text="A caption.")
        db.add(reel)
        await db.flush()

        claims = await extract_claims(db, reel)
        await db.rollback()

    assert len(claims) == 1
    assert claims[0].text == "A real claim with actual content"
