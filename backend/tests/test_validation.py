"""Anti-hallucination validation (docs/FACT_CHECK_METHODOLOGY.md §7).
These are the highest-stakes tests in the repo: a bug here means a
verdict could ship without real evidentiary backing."""
import uuid
from datetime import datetime, timezone

from app.db.models import Source, SourceTier, ValidationStatus, VerdictLabel
from app.pipeline.validation import validate_verdict
from app.schemas.verdict import VerdictProposal


def _make_source(**overrides) -> Source:
    defaults = dict(
        id=uuid.uuid4(),
        url="https://example-gov.test/report",
        title="Official report",
        source_type=SourceTier.primary_government,
        full_text_storage_key="sources/fulltext/abc.txt",
        relevant_passage="Unemployment rose to 12% in March 2026 according to the labor ministry.",
        reliability_score=0.9,
        reliability_breakdown={},
        retrieved_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return Source(**defaults)


def test_passes_when_cited_evidence_is_real_and_numbers_are_supported():
    source = _make_source()
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary="Unemployment rose to 12% in March 2026 per the labor ministry report.",
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed
    assert outcome.verdict == VerdictLabel.TRUE
    assert outcome.confidence == 0.9


def test_downgrades_when_cited_evidence_id_is_not_real():
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.95,
        reasoning_summary="Some claim.",
        cited_evidence_ids=[uuid.uuid4()],  # not in evidence_by_id
    )

    outcome = validate_verdict(proposal, {}, {})

    assert outcome.status == ValidationStatus.downgraded_missing_citation
    assert outcome.verdict == VerdictLabel.UNVERIFIED
    assert outcome.confidence <= 0.4


def test_downgrades_when_source_was_never_actually_fetched():
    unfetched_source = _make_source(retrieved_at=None, full_text_storage_key="")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.9,
        reasoning_summary="No numbers here.",
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: unfetched_source})

    assert outcome.status == ValidationStatus.downgraded_unfetched_source
    assert outcome.verdict == VerdictLabel.UNVERIFIED


def test_downgrades_when_reasoning_cites_a_number_not_in_any_passage():
    source = _make_source(relevant_passage="The report discusses trade policy in general terms.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary="The report shows a 47% increase in tariffs.",  # 47% not in passage -> hallucinated
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.downgraded_unsupported_stat
    assert outcome.verdict == VerdictLabel.UNVERIFIED


def test_ignores_numbers_that_are_only_part_of_a_cited_url():
    # Real failure observed live (docs/CURRENT_ARCHITECTURE.md §10): a
    # model cited a source inline as "(https://site.com/article-3065258.html)"
    # and the URL's own numeric ID got flagged as an unsupported statistic,
    # downgrading an otherwise well-evidenced TRUE verdict to UNVERIFIED.
    source = _make_source(relevant_passage="Kejriwal criticized the new takedown rule in a public statement.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary=(
            "Kejriwal criticized the rule (https://zeenews.india.com/india/"
            "kejriwal-slams-centre-3065258.html)."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed
    assert outcome.verdict == VerdictLabel.TRUE


def test_still_catches_a_real_hallucinated_number_next_to_a_url():
    source = _make_source(relevant_passage="Kejriwal criticized the new takedown rule.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary=(
            "47% of the public opposed the rule (https://zeenews.india.com/india/"
            "kejriwal-slams-centre-3065258.html)."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.downgraded_unsupported_stat


def test_ignores_numbers_inside_internal_citation_markup():
    # Real bug found live against a genuinely new reel (never seen
    # during earlier development, research_paper/benchmark/results.md
    # bm-0002): [[evidence_id=<uuid> | source_id=<uuid>]] markup contains
    # UUID fragments that look like numbers ("609", "8371", ...) to
    # _NUMBER_PATTERN. These got flagged as "unsupported statistics",
    # downgrading a verdict for the wrong reason — a UUID inside
    # citation markup is not a factual claim needing evidence support,
    # and citation validity is already checked separately (Check 1).
    source = _make_source(relevant_passage="Karni Sena accused the MP of insulting Rajput pride.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.UNVERIFIED,
        confidence=0.4,
        reasoning_summary=(
            "The claim is not supported by [[evidence_id=b7e30502-609c-40e9-8371-2515adffaf81 | "
            "source_id=70210daf-638c-48a8-9513-889725c9c100]](https://example.test/article)."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed


def test_ignores_numbers_inside_single_bracket_citation_markup():
    # Real bug found live during the Day 5 validator audit
    # (research/VALIDATOR_EVALUATION.md, item-0004): the verdict prompt
    # never specifies a bracket format for inline citations, and this
    # time the model used a SINGLE bracket ("[evidence_id=...]") rather
    # than the double-bracket form the existing test above covers.
    # _INTERNAL_MARKUP_PATTERN only strips "[[...]]", so the UUID's own
    # hex fragments that happen to start with digits ("737", "49", "840"
    # from "e9aad959-737f-49b4-840f-f75c4b378594") leaked through and
    # got flagged as unsupported statistics -- wrongly downgrading an
    # otherwise reasonable verdict that actually did cite real evidence.
    source = _make_source(
        relevant_passage="Delhi Police have been accused of using nail-studded batons against protesters."
    )
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.0,
        reasoning_summary=(
            "[evidence_id=e9aad959-737f-49b4-840f-f75c4b378594] According to factcheck.org, Delhi "
            "Police have been accused of using nail-studded batons against protesters in the past."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed


def test_ignores_small_meta_numbers_that_dont_need_source_support():
    source = _make_source(relevant_passage="General discussion with no specific figures.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.UNVERIFIED,
        confidence=0.5,
        reasoning_summary="We reviewed 3 sources and found no direct evidence either way.",
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed


# ---------------------------------------------------------------------------
# corrected_fact / context_note — "what's actually true" and broader
# context, both independently number-grounded against the FULL evidence
# matrix (not just cited_evidence_ids), since a correction can legitimately
# come from a different source than the one driving the verdict label.
# ---------------------------------------------------------------------------

def test_corrected_fact_passes_through_when_grounded():
    source = _make_source(
        relevant_passage="Government records show the actual figure was 7,000 crore, not 4,000 crore."
    )
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.8,
        reasoning_summary="The cited figure does not match official records.",
        cited_evidence_ids=[evidence_id],
        corrected_fact="The actual figure was 7,000 crore, not 4,000 crore.",
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed
    assert outcome.corrected_fact == "The actual figure was 7,000 crore, not 4,000 crore."


def test_corrected_fact_dropped_when_it_introduces_an_ungrounded_number():
    # Same principle as the headline-fabrication bug found live
    # (app/pipeline/reel_content.py's _headline_numbers_are_grounded):
    # a "correction" that itself invents a number not in any source
    # passage is exactly as dangerous as a hallucinated reasoning_summary
    # -- just quieter, since it reads as extra-helpful rather than wrong.
    source = _make_source(relevant_passage="Government records show the actual figure was 7,000 crore.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.8,
        reasoning_summary="The cited figure does not match official records.",
        cited_evidence_ids=[evidence_id],
        corrected_fact="The actual figure was $1 billion.",  # not in any passage
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    # The core verdict is unaffected -- only the ungrounded supplementary
    # field is dropped, not the whole verdict.
    assert outcome.status == ValidationStatus.passed
    assert outcome.corrected_fact is None


def test_corrected_fact_dropped_entirely_for_a_true_verdict():
    # A "correction" for a claim that's actually TRUE is a contradiction
    # in terms -- dropped regardless of grounding, not just displayed
    # confusingly next to a TRUE badge.
    source = _make_source(relevant_passage="Confirmed: the figure was 4,000 crore.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.9,
        reasoning_summary="Official records confirm the figure.",
        cited_evidence_ids=[evidence_id],
        corrected_fact="The figure was 4,000 crore.",  # grounded, but nonsensical for TRUE
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.corrected_fact is None


def test_context_note_can_be_grounded_in_a_source_not_cited_for_reasoning():
    # corrected_fact/context_note are checked against the FULL evidence
    # matrix, not just cited_evidence_ids -- a context note can
    # legitimately draw on a different source than the one that drove
    # the verdict label.
    cited_evidence_id = uuid.uuid4()
    other_evidence_id = uuid.uuid4()
    cited_source = _make_source(relevant_passage="The rule took effect in March 2026.")
    other_source = _make_source(
        relevant_passage="This follows a broader push for social media regulation across the region in 2025."
    )
    proposal = VerdictProposal(
        verdict=VerdictLabel.TRUE,
        confidence=0.8,
        reasoning_summary="Official records confirm the rule took effect in March 2026.",
        cited_evidence_ids=[cited_evidence_id],
        context_note="This follows a broader push for social media regulation across the region in 2025.",
    )

    outcome = validate_verdict(
        proposal,
        {cited_evidence_id: object(), other_evidence_id: object()},
        {cited_evidence_id: cited_source, other_evidence_id: other_source},
    )

    assert outcome.status == ValidationStatus.passed
    assert outcome.context_note == (
        "This follows a broader push for social media regulation across the region in 2025."
    )


def test_corrected_fact_and_context_note_are_none_when_verdict_is_downgraded():
    # A downgraded verdict (missing citation, in this case) shouldn't
    # carry a corrected_fact/context_note either, even though the early
    # -return path never computes them -- confirms they default safely.
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.9,
        reasoning_summary="Some claim.",
        cited_evidence_ids=[uuid.uuid4()],  # not in evidence_by_id
        corrected_fact="Some correction.",
    )

    outcome = validate_verdict(proposal, {}, {})

    assert outcome.status == ValidationStatus.downgraded_missing_citation
    assert outcome.corrected_fact is None
    assert outcome.context_note is None


# ---------------------------------------------------------------------------
# Check 4: reasoning stating "no evidence found" paired with a confident
# non-UNVERIFIED label (research/VALIDATOR_EVALUATION.md, Day 5 audit --
# 2 of 5 real false negatives were exactly this pattern).
# ---------------------------------------------------------------------------

def test_downgrades_when_reasoning_says_no_evidence_but_label_is_confident():
    # Real case (paraphrased structure, not the literal claim text) from
    # the Day 5 audit: reasoning says no reliable info was found, yet the
    # verdict is a confident non-UNVERIFIED label.
    source = _make_source(relevant_passage="Some unrelated passage text.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.MOSTLY_FALSE,
        confidence=0.2,
        reasoning_summary=(
            "The evidence matrix does not provide any reliable information about this person's "
            "role in the organization."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.downgraded_reasoning_label_mismatch
    assert outcome.verdict == VerdictLabel.UNVERIFIED


def test_downgrades_real_durrani_meeting_case_from_day5_audit():
    # The exact real reasoning text from the Day 5 audit's most
    # consequential false negative: FALSE at confidence 0.8, contradicted
    # by independent Tier-1 ground truth, undetected until this check.
    source = _make_source(relevant_passage="Some unrelated passage text.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.8,
        reasoning_summary=(
            "The evidence matrix does not provide any reliable sources that support or confirm a "
            "courtesy meeting between Babajani Durrani and Abhijit Dipke at his residence in "
            "Chhatrapati Sambhajinagar."
        ),
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.downgraded_reasoning_label_mismatch
    assert outcome.verdict == VerdictLabel.UNVERIFIED


def test_no_evidence_phrase_is_a_noop_when_verdict_is_already_unverified():
    # The check must never re-flag an already-appropriate UNVERIFIED --
    # only a *confident* label paired with "no evidence" reasoning.
    source = _make_source()
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.UNVERIFIED,
        confidence=0.1,
        reasoning_summary="The evidence matrix does not provide any reliable information here.",
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed


def test_confident_label_with_real_contradicting_evidence_still_passes():
    # Must not become an over-broad "any low-confidence FALSE gets
    # downgraded" check -- a verdict backed by real, cited, contradicting
    # evidence (no "no evidence found" language at all) must still pass.
    source = _make_source(relevant_passage="Official records show the event occurred on a Tuesday, not a Wednesday.")
    evidence_id = uuid.uuid4()
    proposal = VerdictProposal(
        verdict=VerdictLabel.FALSE,
        confidence=0.85,
        reasoning_summary="Official records directly contradict the claim, confirming the event was on a Tuesday.",
        cited_evidence_ids=[evidence_id],
    )

    outcome = validate_verdict(proposal, {evidence_id: object()}, {evidence_id: source})

    assert outcome.status == ValidationStatus.passed
