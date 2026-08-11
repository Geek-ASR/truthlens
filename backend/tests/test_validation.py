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
