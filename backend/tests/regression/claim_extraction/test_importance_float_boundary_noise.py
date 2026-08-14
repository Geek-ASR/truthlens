"""Real bugs found live (research/RESEARCH_ROADMAP_V2.md Phase 2,
EXP-009/EXP-010 experimentation against real reel content) -- two
distinct shapes of the same underlying problem, both handled by
app.schemas.claim._clamp_float_boundary_noise:

(1) Tiny floating-point/generation noise around a boundary the model
    clearly meant to hit exactly (importance=-2e-18, then later
    -1.1111111111e-06 -- an order of magnitude a serialization artifact
    alone wouldn't explain). Clamped silently.

(2) The model genuinely writing a wrong-but-plausible number while
    still expressing some confidence/importance judgment on roughly the
    right scale -- real values observed live across these two
    experiments: -0.5 (x3, same run), -1, -2, -2.3, 1.2, 4. Clamped to
    the nearer boundary too, but loudly (a structlog warning naming the
    field and raw value) -- not silently absorbed like case (1), since
    this is real, disclosable evidence of local-model unreliability, not
    representation noise.

Before either fix existed, any of these crashed the entire extraction
after all 3 retries (zero claims persisted) -- the worst possible
recall outcome for a field that was never a calibrated system-level
number to begin with (see ExtractedClaim.extraction_confidence's own
docstring)."""
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


def test_second_real_observed_noise_value_is_also_clamped():
    """A second real value observed live in a later run of the same
    experiment (EXP-009), an order of magnitude larger than the original
    -2e-18 case -- the epsilon was widened (1e-6 -> 1e-4) specifically
    because this real value fell just outside the original window."""
    claim = _claim(importance=-1.1111111111e-06)
    assert claim.importance == 0.0


def test_tiny_over_one_importance_is_clamped_to_one():
    claim = _claim(importance=1.0 + 5e-17)
    assert claim.importance == 1.0


def test_tiny_negative_extraction_confidence_is_clamped_to_zero():
    claim = _claim(extraction_confidence=-1e-15)
    assert claim.extraction_confidence == 0.0


@pytest.mark.parametrize("raw_value", [-0.5, -1.0, -2.0, -2.3])
def test_real_observed_confused_negative_values_are_clamped_to_zero(raw_value):
    """Every one of these exact values was produced live by llama3.2 on
    real content across EXP-009/EXP-010 -- not synthetic edge cases."""
    claim = _claim(importance=raw_value)
    assert claim.importance == 0.0


def test_real_observed_confused_high_value_is_clamped_to_one():
    """extraction_confidence=4 was produced live on the genuinely
    garbled-transcript item (item-0006) in EXP-009."""
    claim = _claim(extraction_confidence=4.0)
    assert claim.extraction_confidence == 1.0


def test_confused_value_clamp_logs_a_warning_not_silently(capsys):
    """structlog in this project renders to stdout (PrintLoggerFactory,
    app/core/logging.py), not through stdlib logging -- capsys, not
    caplog, is what actually observes it. This must NOT be a silent
    clamp: unlike the pure floating-point-noise case, this is real,
    disclosable evidence of local-model unreliability."""
    _claim(importance=-2.3)
    captured = capsys.readouterr()
    # Exact rendering (key=value vs. JSON) depends on whether
    # app.core.logging.configure_logging() has run yet in this process --
    # check content, not one specific wire format.
    assert "claim_extraction_float_field_clamped" in captured.out
    assert "-2.3" in captured.out
    assert "importance" in captured.out


def test_noise_level_clamp_does_not_log_a_warning(capsys):
    """The silent case (1) must stay silent -- logging on every tiny
    serialization artifact would drown out the genuinely interesting
    signal from case (2)."""
    _claim(importance=-2e-18)
    captured = capsys.readouterr()
    assert "claim_extraction_float_field_clamped" not in captured.out


def test_extremely_out_of_range_value_is_still_rejected():
    """Something this far off the [0,1] scale suggests a structurally
    different kind of error (e.g. a stray token count or index leaking
    into the field) that a blind clamp should not paper over -- this
    must still fail validation and fall through to production's
    Gemini-escalation fallback (verified end-to-end in EXP-010), not be
    silently absorbed here."""
    with pytest.raises(ValidationError):
        _claim(importance=-50.0)
    with pytest.raises(ValidationError):
        _claim(importance=100.0)


def test_exact_boundary_values_are_unaffected():
    claim = _claim(importance=0.0, extraction_confidence=1.0)
    assert claim.importance == 0.0
    assert claim.extraction_confidence == 1.0


def test_mid_range_value_is_unaffected():
    claim = _claim(importance=0.73)
    assert claim.importance == 0.73
