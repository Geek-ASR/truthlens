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
# The prompt never actually specifies a bracket format for inline
# citations -- the model sometimes uses double brackets (the pattern
# above), sometimes a single bracket, e.g. "[evidence_id=e9aad959-737f-
# 49b4-840f-f75c4b378594]". Found live (research/VALIDATOR_EVALUATION.md):
# the single-bracket form isn't stripped by _INTERNAL_MARKUP_PATTERN, so
# hex fragments that happen to start with digits ("737", "49", "840"
# from that UUID) leaked through as "unsupported numbers," wrongly
# downgrading an otherwise-reasonable verdict. Rather than chase every
# bracket style the model might invent, strip anything shaped like a
# UUID directly, wherever it appears in the text (bracketed or not) --
# a UUID is never a legitimate statistic needing grounding, regardless
# of what markup does or doesn't wrap it.
_UUID_PATTERN = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)

# Phrases indicating the model itself is asserting that no supporting
# evidence exists -- as opposed to asserting that evidence exists and
# CONTRADICTS the claim, which is a legitimate basis for a definitive
# label. Found live (research/VALIDATOR_EVALUATION.md's Day 5 audit): 2
# of 5 real validator false negatives were exactly this pattern --
# reasoning_summary stating "the evidence matrix does not provide any
# reliable [information/sources]..." while the verdict was a confident
# FALSE (once at confidence 0.8) or MOSTLY_FALSE rather than UNVERIFIED.
# A general, keyword-based check for internal self-consistency between
# what the model says it found and what it concluded -- not a check
# against any external ground truth, and not tuned to any specific
# claim's correct answer, only to whether the model's own stated
# reasoning logically supports its own chosen label. Necessarily a
# heuristic (natural language has unlimited ways to say "no evidence
# found"), same tradeoff already accepted for every other keyword/regex
# -based check in this file.
_NO_EVIDENCE_FOUND_PHRASES = (
    "does not provide any reliable",
    "does not provide any relevant",
    "no reliable information",
    "no reliable sources",
    "no relevant information",
    "no relevant sources",
    "cannot be verified",
    "could not be verified",
    "not been able to verify",
)


def _reasoning_claims_no_evidence_found(reasoning_summary: str) -> bool:
    lowered = reasoning_summary.lower()
    return any(phrase in lowered for phrase in _NO_EVIDENCE_FOUND_PHRASES)

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
    text_without_uuids = _UUID_PATTERN.sub("", text_without_markup)
    text_without_urls = _URL_PATTERN.sub("", text_without_uuids)
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
    text_without_uuids = _UUID_PATTERN.sub("", text_without_markup)
    text_without_urls = _URL_PATTERN.sub("", text_without_uuids)
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

    # Check 4: reasoning that itself says no evidence was found must not
    # be paired with a confident non-UNVERIFIED label -- "I found nothing
    # to confirm or deny this" is a description of UNVERIFIED, not a
    # basis for FALSE/MOSTLY_FALSE/TRUE/etc regardless of how the model
    # phrases its confidence.
    if proposal.verdict != VerdictLabel.UNVERIFIED and _reasoning_claims_no_evidence_found(
        proposal.reasoning_summary
    ):
        return ValidationOutcome(
            ValidationStatus.downgraded_reasoning_label_mismatch,
            VerdictLabel.UNVERIFIED,
            min(proposal.confidence, _CAPPED_CONFIDENCE),
            [
                f"reasoning_summary states no supporting evidence was found, but verdict was "
                f"{proposal.verdict.value} instead of UNVERIFIED."
            ],
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
