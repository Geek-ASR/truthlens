"""research/MASS_SOURCING_V2.md's spot_check_eligible_candidates.py --
the deterministic filter applied to every ELIGIBLE candidate before
promotion. Three of these behaviors were real bugs found live (see the
module's own docstring/comments) that let bad candidates through
undetected until manual review caught them -- covered here so they
can't silently regress."""
from research.benchmark_v2.spot_check_eligible_candidates import (
    _extract_reasoning_text,
    _find_flag_reason,
)


def _candidate(**overrides) -> dict:
    base = {
        "candidate_id": "cand-test-0001",
        "ground_truth_claim": "A real, specific claim sentence.",
        "ground_truth_label": "FALSE",
        "history": [
            {"status": "ELIGIBLE", "note": "llama3.2 judge (confidence=0.90): The caption directly asserts the claim. NOT yet human/manual-reviewed."},
        ],
    }
    base.update(overrides)
    return base


def test_well_formed_candidate_is_not_flagged():
    assert _find_flag_reason(_candidate()) is None


def test_extracts_reasoning_from_boilerplate_wrapped_note():
    note = "llama3.2 judge (confidence=0.90): The real reasoning here. NOT yet human/manual-reviewed."
    # The trailing period before "NOT yet..." is boilerplate punctuation,
    # not part of the reasoning -- stripped along with the wrapper.
    assert _extract_reasoning_text(note) == "The real reasoning here"


def test_extracts_reasoning_from_bare_note_with_no_boilerplate():
    # Alt News's GROUND_TRUTH_VERIFIED note IS the bare reasoning -- no
    # wrapping boilerplate to strip.
    assert _extract_reasoning_text("The real reasoning here, no wrapper.") == "The real reasoning here, no wrapper."


def test_genuinely_empty_reasoning_is_flagged_even_inside_boilerplate():
    # Found live (cand-thequint-0351): judgment.reasoning=="" still
    # produced a NON-empty note string once wrapped in boilerplate,
    # so a raw `not note.strip()` check never fired. Must check the
    # EXTRACTED reasoning, not the raw note.
    note = "llama3.2 judge (confidence=1.00): . NOT yet human/manual-reviewed."
    c = _candidate(history=[{"status": "ELIGIBLE", "note": note}])
    reason = _find_flag_reason(c)
    assert reason is not None
    assert "empty reasoning" in reason


def test_prefers_ground_truth_verified_note_over_eligible_filler():
    # Found live: Alt News writes real reasoning to a GROUND_TRUTH_VERIFIED
    # note, then a separate generic ELIGIBLE filler note after it. Taking
    # the LAST match silently discarded the real, self-contradicting
    # reasoning -- must prefer GROUND_TRUTH_VERIFIED when present.
    c = _candidate(history=[
        {"status": "GROUND_TRUTH_VERIFIED", "note": "The caption is unrelated to the claim being debunked."},
        {"status": "ELIGIBLE", "note": "Auto-accepted, not yet reviewed."},
    ])
    reason = _find_flag_reason(c)
    assert reason is not None
    assert "self-contradicting" in reason


def test_self_contradiction_literal_phrase_is_flagged():
    c = _candidate(history=[{"status": "ELIGIBLE", "note": "llama3.2 judge (confidence=0.90): This post is unrelated to the claim. NOT yet human/manual-reviewed."}])
    reason = _find_flag_reason(c)
    assert reason is not None and "self-contradicting" in reason


def test_self_contradiction_regex_catches_unlisted_phrasing():
    # Found live across cand-mass-0321/0344/cand-thequint-0351-adjacent
    # cases: a fixed phrase list kept missing new "does not X the claim"
    # variants one at a time -- the regex generalizes the family.
    c = _candidate(history=[{"status": "ELIGIBLE", "note": "llama3.2 judge (confidence=0.90): The post does not contain the false claim being debunked. NOT yet human/manual-reviewed."}])
    reason = _find_flag_reason(c)
    assert reason is not None and "self-contradicting" in reason


def test_hedging_language_is_flagged():
    c = _candidate(history=[{"status": "ELIGIBLE", "note": "llama3.2 judge (confidence=0.90): It is unclear whether this is the real source. NOT yet human/manual-reviewed."}])
    reason = _find_flag_reason(c)
    assert reason is not None and "hedging" in reason


def test_empty_claim_is_flagged():
    c = _candidate(ground_truth_claim="")
    reason = _find_flag_reason(c)
    assert reason is not None and "malformed ground_truth_claim" in reason


def test_markdown_link_claim_is_flagged():
    c = _candidate(ground_truth_claim="[Read more](https://example.com/article)")
    reason = _find_flag_reason(c)
    assert reason is not None and "malformed ground_truth_claim" in reason


def test_stringified_list_claim_is_flagged():
    # Found live (cand-vishvas-0533): llama3.2 dumped its own internal
    # list-of-fragments straight into ground_truth_claim instead of a
    # sentence.
    c = _candidate(ground_truth_claim='["Akhilesh Yadav ", "boots thrown"]')
    reason = _find_flag_reason(c)
    assert reason is not None and "stringified list" in reason


def test_empty_label_is_flagged():
    c = _candidate(ground_truth_label="")
    reason = _find_flag_reason(c)
    assert reason is not None and "empty ground_truth_label" in reason


def test_invalid_label_is_flagged():
    # Found live: "Fact Check: झूठ" (cand-vishvas-0510, leaked
    # article-title text) and bare "Claim" (cand-thequint-0351, not a
    # verdict at all) both slipped through with no label validation.
    for bad_label in ("Fact Check: झूठ", "Claim", "Probably False", ""):
        reason = _find_flag_reason(_candidate(ground_truth_label=bad_label))
        assert reason is not None, f"expected {bad_label!r} to be flagged"


def test_valid_labels_are_not_flagged_regardless_of_case():
    for label in ("FALSE", "false", "Misleading", "MOSTLY_TRUE", "outdated"):
        assert _find_flag_reason(_candidate(ground_truth_label=label)) is None
