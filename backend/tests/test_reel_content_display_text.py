from app.db.models import ValidationStatus
from app.db.models import Verdict as VerdictModel
from app.db.models import VerdictLabel
from app.pipeline.reel_content import (
    _UNVALIDATED_REASONING_NOTE,
    _display_text,
    _safe_reasoning_text,
    _safe_supplementary_text,
)


def _verdict(
    reasoning_summary: str,
    validation_status: ValidationStatus,
    corrected_fact: str | None = None,
    context_note: str | None = None,
) -> VerdictModel:
    return VerdictModel(
        verdict=VerdictLabel.UNVERIFIED,
        confidence=0.4,
        reasoning_summary=reasoning_summary,
        cited_evidence_ids=[],
        validation_status=validation_status,
        corrected_fact=corrected_fact,
        context_note=context_note,
    )


def test_strips_trailing_validation_note():
    raw = "The rule exists and Kejriwal criticized it.\n\n[VALIDATION NOTE: Some issue.]"
    assert _display_text(raw) == "The rule exists and Kejriwal criticized it."


def test_strips_validation_note_containing_a_python_list_repr():
    # Real bug found live (docs/CURRENT_ARCHITECTURE.md): a naive
    # non-greedy "[VALIDATION NOTE:...]" regex stopped at the FIRST "]"
    # it found, which was the closing bracket of the list repr inside the
    # note itself — leaving the note's tail visible on the slide.
    raw = (
        "The rule requires takedown within three hours.\n\n"
        "[VALIDATION NOTE: Numbers ['3065258', '69'] in reasoning_summary "
        "do not appear in any cited source passage.]"
    )
    assert _display_text(raw) == "The rule requires takedown within three hours."


def test_strips_internal_double_bracket_markup():
    raw = "Kejriwal criticized the rule [[evidence_id=abc123 | source=publisher=https://example.test]]."
    assert _display_text(raw) == "Kejriwal criticized the rule ."


def test_leaves_normal_text_untouched():
    raw = "The regulation was notified on February 10, 2026."
    assert _display_text(raw) == raw


def test_collapses_whitespace():
    raw = "Line one.\n\n\nLine   two."
    assert _display_text(raw) == "Line one. Line two."


def test_safe_reasoning_text_shows_real_text_when_validation_passed():
    v = _verdict("Kejriwal criticized the rule in a public statement.", ValidationStatus.passed)
    assert _safe_reasoning_text(v) == "Kejriwal criticized the rule in a public statement."


def test_safe_reasoning_text_hides_reasoning_from_a_downgraded_verdict():
    # Real bug found live (research_paper/benchmark/results.md bm-0002):
    # a verdict downgraded for citing an unsupported number still had its
    # full free-text reasoning — including an unrelated-entity
    # hallucination sourced from a DIFFERENT organization's Wikipedia
    # page — reused verbatim on a published evidence-card slide and as
    # input to the overall "why" paragraph's own LLM call. Once a
    # verdict fails validation, none of its free-text reasoning is safe
    # to reuse, only a generic, non-fabricated note.
    v = _verdict(
        "This suggests an unrelated organization has a violent ideology.",
        ValidationStatus.downgraded_unsupported_stat,
    )
    result = _safe_reasoning_text(v)
    assert result == _UNVALIDATED_REASONING_NOTE
    assert "violent ideology" not in result


def test_safe_reasoning_text_hides_reasoning_for_every_downgrade_reason():
    for status in (
        ValidationStatus.downgraded_missing_citation,
        ValidationStatus.downgraded_unfetched_source,
        ValidationStatus.downgraded_unsupported_stat,
    ):
        v = _verdict("Some potentially unsafe reasoning text.", status)
        assert _safe_reasoning_text(v) == _UNVALIDATED_REASONING_NOTE


def test_safe_supplementary_text_shown_when_passed():
    v = _verdict("...", ValidationStatus.passed, corrected_fact="The real figure was 7,000 crore.")
    assert _safe_supplementary_text(v, v.corrected_fact) == "The real figure was 7,000 crore."


def test_safe_supplementary_text_hidden_when_verdict_downgraded():
    # Even though validate_verdict() already independently grounds
    # corrected_fact/context_note before persisting them, once the
    # verdict AS A WHOLE is downgraded nothing from that same LLM call
    # is trusted for display -- same rule as reasoning_summary.
    v = _verdict(
        "...", ValidationStatus.downgraded_unsupported_stat, corrected_fact="The real figure was 7,000 crore."
    )
    assert _safe_supplementary_text(v, v.corrected_fact) is None


def test_safe_supplementary_text_none_when_field_unset():
    v = _verdict("...", ValidationStatus.passed, corrected_fact=None)
    assert _safe_supplementary_text(v, v.corrected_fact) is None
