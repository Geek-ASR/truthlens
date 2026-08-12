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
_URL_PATTERN = re.compile(r"https?://\S+")
# Internal citation markup, e.g. "[[evidence_id=b7e30502-... | source_id=...]]".
# Found live: UUID fragments inside this markup (e.g. "609", "8371") were
# being extracted by _NUMBER_PATTERN and flagged as unsupported statistics,
# downgrading verdicts for the wrong reason — a UUID is not a factual claim
# needing evidence support, and this markup is already validated
# separately (Check 1, cited-evidence-id existence).
_INTERNAL_MARKUP_PATTERN = re.compile(r"\[\[.*?\]\]", re.DOTALL)

_CAPPED_CONFIDENCE = 0.4


class ValidationOutcome:
    def __init__(
        self,
        status: ValidationStatus,
        verdict: VerdictLabel,
        confidence: float,
        notes: list[str],
        *,
        corrected_fact: str | None = None,
        context_note: str | None = None,
    ):
        self.status = status
        self.verdict = verdict
        self.confidence = confidence
        self.notes = notes
        self.corrected_fact = corrected_fact
        self.context_note = context_note


def _numbers_needing_support(text: str) -> list[str]:
    # Strip internal citation markup first (see _INTERNAL_MARKUP_PATTERN),
    # then URLs — observed live: a model that cites a source inline as
    # "(https://example.com/article-3065258.html)" was getting flagged
    # for an "unsupported number" on the URL's own numeric ID, which is
    # never a factual claim needing evidence support. Citation is already
    # handled structurally via cited_evidence_ids; a URL appearing in the
    # prose is incidental, not a statistic.
    text_without_markup = _INTERNAL_MARKUP_PATTERN.sub("", text)
    text_without_urls = _URL_PATTERN.sub("", text_without_markup)
    found = _NUMBER_PATTERN.findall(text_without_urls)
    return [n for n in found if len(re.sub(r"[,.%]", "", n)) >= _MIN_DIGITS_TO_CHECK]


def _all_numbers(text: str) -> list[str]:
    # Unlike _numbers_needing_support, no _MIN_DIGITS_TO_CHECK filter:
    # corrected_fact/context_note are short, specific, single-sentence
    # fields (not prose that might incidentally mention a meta-number
    # like "3 sources"), so there's no legitimate reason for one to
    # contain a single-digit number that isn't in the source it's
    # supposedly drawn from. Same reasoning as reel_content.py's headline
    # -grounding check, which exists because "$1 Billion" (single-digit
    # "1") would otherwise slip past a >=2-digit filter entirely.
    text_without_markup = _INTERNAL_MARKUP_PATTERN.sub("", text)
    text_without_urls = _URL_PATTERN.sub("", text_without_markup)
    return _NUMBER_PATTERN.findall(text_without_urls)


def _grounded_or_none(text: str | None, all_passages: str) -> str | None:
    # Independent of the main citation/number checks below -- a
    # corrected_fact or context_note can be grounded in ANY source in
    # this claim's evidence matrix, not only the ones cited for
    # reasoning_summary, since the "actual fact" or context might come
    # from a different source than the one that drove the verdict label
    # itself. Dropped silently (not downgraded) if its numbers aren't
    # grounded -- these are supplementary, so an ungrounded one shouldn't
    # invalidate an otherwise-good verdict, but its own text is never
    # trusted for display or reuse.
    if not text:
        return None
    numbers = _all_numbers(text)
    if numbers and any(n not in all_passages for n in numbers):
        return None
    return text


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

    all_passages = " ".join(
        s.relevant_passage for s in source_by_evidence_id.values() if s.relevant_passage
    )
    # A "correction" for a TRUE verdict is a contradiction in terms --
    # dropped regardless of what the model provided, even if it happened
    # to be well-grounded, rather than displaying something confusing.
    corrected_fact = None if proposal.verdict == VerdictLabel.TRUE else _grounded_or_none(
        proposal.corrected_fact, all_passages
    )
    context_note = _grounded_or_none(proposal.context_note, all_passages)

    return ValidationOutcome(
        ValidationStatus.passed,
        proposal.verdict,
        proposal.confidence,
        [],
        corrected_fact=corrected_fact,
        context_note=context_note,
    )
