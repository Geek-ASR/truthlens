"""Stage 7: anti-hallucination validation. Deterministic code, not an
LLM — a verdict cannot argue its way past this (docs/FACT_CHECK_METHODOLOGY.md
§7, product spec §17). Any failure downgrades the verdict to UNVERIFIED
and routes the fact_check to human review rather than publishing a
guess."""
import re

from app.db.models import Source, ValidationStatus, VerdictLabel
from app.schemas.verdict import VerdictProposal

_NUMBER_PATTERN = re.compile(r"\b\d+(?:,\d{3})*(?:\.\d+)?%?")
_MIN_DIGITS_TO_CHECK = 2  # ignore single-digit numbers (e.g. "3 sources") to avoid false-positive failures

_CAPPED_CONFIDENCE = 0.4


class ValidationOutcome:
    def __init__(self, status: ValidationStatus, verdict: VerdictLabel, confidence: float, notes: list[str]):
        self.status = status
        self.verdict = verdict
        self.confidence = confidence
        self.notes = notes


def _numbers_needing_support(text: str) -> list[str]:
    found = _NUMBER_PATTERN.findall(text)
    return [n for n in found if len(re.sub(r"[,.%]", "", n)) >= _MIN_DIGITS_TO_CHECK]


def validate_verdict(
    proposal: VerdictProposal,
    evidence_by_id: dict,
    source_by_evidence_id: dict[object, Source],
) -> ValidationOutcome:
    """`evidence_by_id` / `source_by_evidence_id` are passed explicitly
    (rather than traversed via Evidence.source) so this stays a pure,
    synchronous function with no ORM lazy-loading involved."""
    valid_evidence_ids = set(evidence_by_id.keys())

    # Check 1: every cited evidence id must belong to this claim's evidence.
    cited = set(proposal.cited_evidence_ids)
    if not cited or not cited.issubset(valid_evidence_ids):
        return ValidationOutcome(
            ValidationStatus.downgraded_missing_citation,
            VerdictLabel.UNVERIFIED,
            min(proposal.confidence, _CAPPED_CONFIDENCE),
            ["Verdict cited evidence not present in this claim's evidence matrix."],
        )

    cited_sources = [source_by_evidence_id[eid] for eid in cited]

    # Check 2: every cited evidence's source must have actually been fetched.
    for source in cited_sources:
        if not source.retrieved_at or not source.full_text_storage_key:
            return ValidationOutcome(
                ValidationStatus.downgraded_unfetched_source,
                VerdictLabel.UNVERIFIED,
                min(proposal.confidence, _CAPPED_CONFIDENCE),
                [f"Source {source.id} for cited evidence was never actually retrieved."],
            )

    # Check 3: numeric claims in the reasoning must appear in cited passages.
    numbers_in_reasoning = _numbers_needing_support(proposal.reasoning_summary)
    if numbers_in_reasoning:
        combined_passages = " ".join(s.relevant_passage for s in cited_sources)
        missing = [n for n in numbers_in_reasoning if n not in combined_passages]
        if missing:
            return ValidationOutcome(
                ValidationStatus.downgraded_unsupported_stat,
                VerdictLabel.UNVERIFIED,
                min(proposal.confidence, _CAPPED_CONFIDENCE),
                [f"Numbers {missing} in reasoning_summary do not appear in any cited source passage."],
            )

    return ValidationOutcome(ValidationStatus.passed, proposal.verdict, proposal.confidence, [])
