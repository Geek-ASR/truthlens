"""Real bug found live (research/RESEARCH_ROADMAP_V2.md Phase 2, EXP-009
experimentation): llama3.2 produced `importance=-2e-18` for a real claim
extracted from real reel content -- floating-point noise the model
clearly intended as 0.0, but which failed the `ge=0.0` schema constraint
and crashed the entire extraction after all 3 retries (zero claims
persisted, the worst possible recall outcome). Same constraint shape
applies to `extraction_confidence`.

Not previously caught by any existing test -- every prior test
constructs ExtractedClaim with hand-picked, exact values (0.5, 0.8, ...),
never a value with realistic floating-point noise near a boundary."""
import pytest
from pydantic import ValidationError

from app.schemas.claim import ExtractedClaim


def _claim(**overrides):
    defaults = dict(text="a claim", claim_type="factual", verifiable=True, importance=0.5, extraction_confidence=0.5)
    defaults.update(overrides)
    return ExtractedClaim(**defaults)


def test_tiny_negative_importance_is_clamped_to_zero():
    claim = _claim(importance=-2e-18)
    assert claim.importance == 0.0


def test_tiny_over_one_importance_is_clamped_to_one():
    claim = _claim(importance=1.0 + 5e-17)
    assert claim.importance == 1.0


def test_tiny_negative_extraction_confidence_is_clamped_to_zero():
    claim = _claim(extraction_confidence=-1e-15)
    assert claim.extraction_confidence == 0.0


def test_genuinely_out_of_range_importance_still_rejected():
    """The clamp must not silently swallow a real out-of-range value --
    only floating-point noise within the defined epsilon."""
    with pytest.raises(ValidationError):
        _claim(importance=-0.5)


def test_genuinely_out_of_range_high_importance_still_rejected():
    with pytest.raises(ValidationError):
        _claim(importance=1.5)


def test_exact_boundary_values_are_unaffected():
    claim = _claim(importance=0.0, extraction_confidence=1.0)
    assert claim.importance == 0.0
    assert claim.extraction_confidence == 1.0


def test_mid_range_value_is_unaffected():
    claim = _claim(importance=0.73)
    assert claim.importance == 0.73
