"""Stage 7: anti-hallucination validation. Deterministic code, not an
LLM — a verdict cannot argue its way past this (docs/FACT_CHECK_METHODOLOGY.md
§7, product spec §17). Any failure downgrades the verdict to UNVERIFIED
and routes the fact_check to human review rather than publishing a
guess."""
import re
from datetime import timedelta, timezone

from dateutil import parser as date_parser

from app.db.models import EvidenceStance, Source, ValidationStatus, VerdictLabel
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

# research/RESEARCH_ROADMAP_V2.md Phase 5 (temporal consistency). Real
# time_reference values observed live across this project's dev data
# (~30 values): almost all are vague ("present", "recent", "unspecified")
# and exactly one is an explicit, unambiguous date ("August 4, 2026").
# dateutil.parser.parse(fuzzy=False) was confirmed live to correctly
# reject every vague/relative value (including "today"/"yesterday",
# which it does NOT resolve on its own) and only accept the explicit
# one — exactly the conservative behavior this check needs. No relative
# -term resolution (e.g. "yesterday" anchored to the reel's posted_at)
# is attempted in this version: it would require threading Reel through
# validate_verdict()'s otherwise-pure signature for a case that never
# once appeared as an explicit, resolvable value in real data, and Phase
# 5's own stopping condition treats a false positive from mis-resolving
# a vague term as disqualifying regardless of any recall gained — a real,
# disclosed recall ceiling, not an oversight.
_TEMPORAL_MISMATCH_TOLERANCE_DAYS = 2


def _resolve_explicit_claim_date(time_reference: str | None):
    if not time_reference or not time_reference.strip():
        return None
    try:
        return date_parser.parse(time_reference, fuzzy=False)
    except (ValueError, OverflowError):
        return None


# research/RESEARCH_ROADMAP_V2.md Phase 4 (entity consistency). Promoted
# from a standalone prototype (research/entity_consistency_eval.py,
# ENTITY_CONSISTENCY_EVALUATION.md's original audit) to production after
# a second, corrected evaluation (research/entity_consistency_v2/evaluate.py,
# real DEV-split data) cleared the roadmap's own integration bar: v1's
# only 4 false positives were ALL one abstract-concept entity
# ({"name": "Democracy", "type": "concept"}) matched against unrelated
# legal text -- fixed by filtering to PERSON/ORGANIZATION/LOCATION before
# evaluating, which took the corrected sample to 2/2 real true positives
# (including the exact "Delhi Police vs Burdwan Police" case Step 9
# names) and 0 false positives, plus 1 real transliteration-variance case
# (Dipke/Deepke) recovered by the calibrated fuzzy-match fallback below
# without collapsing either of the two real must-not-match cases in this
# project's own data (Delhi/Burdwan Police, Karni Sena/Sri Ram Sena).
#
# Real Claim.entities `type` values observed live are messy free text
# ("person", "Organization", "EducationalInstitution", "Examination",
# "concept", ...) -- canonicalized into a fixed vocabulary here rather
# than guessed at. This is NOT the roadmap's full aspirational 7
# -category schema (PERSON/ORGANIZATION/LOCATION/EVENT/DATE/NUMBER/
# POLITICAL_ACTOR) -- EVENT/DATE/NUMBER/POLITICAL_ACTOR would require a
# claim_extraction prompt/schema change not made this pass, disclosed
# here rather than silently narrowed.
_ENTITY_ALIAS_GROUPS = [
    {"government of india", "union government", "centre", "central government", "govt of india"},
]

_ENTITY_TYPE_NORMALIZATION = {
    "person": "PERSON",
    "organization": "ORGANIZATION",
    "organisation": "ORGANIZATION",
    "educationalinstitution": "ORGANIZATION",
    "location": "LOCATION",
    "place": "LOCATION",
    "policy": "OTHER",
    "concept": "OTHER",
    "examination": "OTHER",
    "other": "OTHER",
}
_ENTITY_EVALUABLE_TYPES = {"PERSON", "ORGANIZATION", "LOCATION"}

# Check 8 (research/RESEARCH_ROADMAP_V2.md Phase 11 follow-up, EXP-029/
# EXP-030, research/CONTRADICTORY_SOURCES_V2.md). Calibrated against
# EXP-029's own two real evidence-reliability gaps: 0.75 (0.95 vs 0.20)
# never produced a correct verdict across 14 real trials; 0.10 (0.85 vs
# 0.75) behaved reasonably (or at least not clearly wrong) about half
# the time. 0.4 sits clear of the "genuinely close call" zone the
# second case demonstrated while still catching the first.
_RELIABILITY_GAP_THRESHOLD = 0.4
_RELIABILITY_MISMATCH_NEGATIVE_LABELS = {
    VerdictLabel.FALSE, VerdictLabel.MOSTLY_FALSE, VerdictLabel.UNVERIFIED,
    # OUTDATED effectively sides with "this used to be true but changed" --
    # functionally the same as siding with the contradicting evidence; the
    # real EXP-029 case this check targets included exactly this label,
    # paired with confidence 1.0, against a 0.95-reliability primary
    # -government source.
    VerdictLabel.OUTDATED,
}
_RELIABILITY_MISMATCH_POSITIVE_LABELS = {VerdictLabel.TRUE, VerdictLabel.MOSTLY_TRUE}

# Calibrated against this project's own real cases (research/
# entity_consistency_v2/evaluate.py's module docstring has the full
# numbers): "abhijit dipke" vs "abhijeet deepke" (the real case that
# SHOULD match) scores 0.786; "delhi police" vs "burdwan police" and
# "karni sena" vs "sri ram sena" (the real cases that must NOT collapse)
# score 0.615 and 0.545 -- 0.75 clears the former with margin and
# rejects both latter with much larger margin.
_ENTITY_FUZZY_MATCH_THRESHOLD = 0.75


def _normalize_entity_type(raw_type: str | None) -> str:
    return _ENTITY_TYPE_NORMALIZATION.get((raw_type or "").strip().lower(), "OTHER")


def _entity_exact_match(entity_name: str, text_lower: str) -> bool:
    name = entity_name.lower().strip()
    if not name:
        return False
    if name in text_lower:
        return True
    for group in _ENTITY_ALIAS_GROUPS:
        if name in group:
            return any(alias in text_lower for alias in group)
    return False


def _entity_fuzzy_match(entity_name: str, text_lower: str) -> bool:
    """A disclosed secondary signal for transliteration variance --
    checks the entity name against every word-run of matching length in
    the text, not one global ratio (a name is usually a small fragment
    of a much longer passage)."""
    from difflib import SequenceMatcher

    name = entity_name.lower().strip()
    if not name or len(name) < 4:  # too short for a meaningful fuzzy ratio
        return False
    words = text_lower.split()
    name_word_count = max(1, len(name.split()))
    for i in range(len(words) - name_word_count + 1):
        window = " ".join(words[i : i + name_word_count])
        if SequenceMatcher(None, name, window).ratio() >= _ENTITY_FUZZY_MATCH_THRESHOLD:
            return True
    return False


def _entity_consistency_violation(claim_entities: list[dict] | None, title: str | None, passage: str | None) -> bool:
    """True only when the claim has >=1 evaluable-type entity AND none of
    them (exact or fuzzy) appears in this evidence's own title+passage --
    a claim with zero evaluable entities cannot be evaluated by this
    check at all and is never flagged (matches the prototype's own
    discipline: not evaluable is not the same as passing)."""
    evaluable_names = [
        e["name"] for e in (claim_entities or [])
        if _normalize_entity_type(e.get("type")) in _ENTITY_EVALUABLE_TYPES and e.get("name")
    ]
    if not evaluable_names:
        return False
    text_lower = f"{title or ''} {passage or ''}".lower()
    return not any(
        _entity_exact_match(name, text_lower) or _entity_fuzzy_match(name, text_lower)
        for name in evaluable_names
    )


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
    claim_time_reference: str | None = None,
    claim_entities: list[dict] | None = None,
) -> ValidationOutcome:
    """`evidence_by_id` / `source_by_evidence_id` are passed explicitly
    (rather than traversed via Evidence.source) so this stays a pure,
    synchronous function with no ORM lazy-loading involved.
    `claim_time_reference` / `claim_entities` are likewise passed as
    plain values (Claim.time_reference / Claim.entities), not the Claim
    object itself, for the same reason."""
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

    # Check 6 (research/RESEARCH_ROADMAP_V2.md Phase 5 — the 5th being the
    # supplementary-field grounding below, _grounded_or_none, never
    # explicitly numbered in-code before now): the claim asserts
    # a specific, explicit date, but every cited source that reports a
    # publication_date was published well BEFORE that date — the "old
    # footage/story presented as current" pattern Phase 5 names. A source
    # published AFTER the claimed date is normal (fact-checks are usually
    # written after the fact) and never flagged — only sources that
    # predate the claimed event are suspicious. Deliberately narrow: only
    # fires when time_reference resolves to an unambiguous explicit date
    # AND at least one cited source has a real publication_date, both
    # real, disclosed preconditions this check does not force past
    # (Phase 5's own failure condition, RESEARCH_ROADMAP_V2.md).
    resolved_claim_date = _resolve_explicit_claim_date(claim_time_reference)
    if resolved_claim_date is not None:
        dated_sources = [s for s in cited_sources if s.publication_date is not None]
        if dated_sources:
            cutoff = resolved_claim_date - timedelta(days=_TEMPORAL_MISMATCH_TOLERANCE_DAYS)
            # dateutil parses a bare date string (e.g. "August 4, 2026")
            # as naive; Source.publication_date is stored timezone-aware
            # — normalize before comparing rather than letting the two
            # silently compare as an error.
            if cutoff.tzinfo is None:
                cutoff = cutoff.replace(tzinfo=timezone.utc)
            if all(s.publication_date < cutoff for s in dated_sources):
                return ValidationOutcome(
                    ValidationStatus.downgraded_temporal_mismatch,
                    VerdictLabel.UNVERIFIED,
                    min(proposal.confidence, _CAPPED_CONFIDENCE),
                    [
                        f"Claim asserts a specific date ({resolved_claim_date.date()}) but every cited "
                        f"source with a known publication date predates it by more than "
                        f"{_TEMPORAL_MISMATCH_TOLERANCE_DAYS} day(s) — possible old footage/story "
                        f"presented as current."
                    ],
                )

    # Check 7 (research/RESEARCH_ROADMAP_V2.md Phase 4): for every cited
    # evidence with a stance that actually influences the verdict
    # (supports/contradicts -- irrelevant-stance evidence isn't driving
    # the reasoning, so a mismatch there is not this check's concern),
    # at least one of the claim's own PERSON/ORGANIZATION/LOCATION
    # entities must appear (exact or calibrated-fuzzy) in that evidence's
    # title+passage. Catches the "wrong entity, wrong incident" pattern
    # -- e.g. citing a Burdwan, West Bengal police incident as if it
    # contradicts a claim specifically about Delhi Police.
    #
    # A claim with zero evaluable-type entities is not evaluable by this
    # check at all (same discipline as the original prototype) -- and,
    # deliberately, `evidence.stance` is never even read in that case:
    # callers that never pass claim_entities (most existing tests and
    # any research script that only exercises the other checks) keep
    # working against plain Evidence-shaped stand-ins that don't
    # implement `.stance`, since this check has nothing to look at either
    # way.
    has_evaluable_entity = any(
        _normalize_entity_type(e.get("type")) in _ENTITY_EVALUABLE_TYPES and e.get("name")
        for e in (claim_entities or [])
    )
    if has_evaluable_entity:
        for eid in cited:
            evidence = evidence_by_id[eid]
            if evidence.stance == EvidenceStance.irrelevant:
                continue
            source = source_by_evidence_id[eid]
            if _entity_consistency_violation(claim_entities, source.title, source.relevant_passage):
                return ValidationOutcome(
                    ValidationStatus.downgraded_entity_mismatch,
                    VerdictLabel.UNVERIFIED,
                    min(proposal.confidence, _CAPPED_CONFIDENCE),
                    [
                        f"None of the claim's named entities appear in cited evidence {eid} "
                        f"(source {source.id}) despite a {evidence.stance.value} stance -- possible "
                        f"wrong-entity/wrong-incident citation."
                    ],
                )

    # Check 8 (EXP-029/EXP-030): among CITED evidence, does one stance
    # (supports/contradicts) have a meaningfully higher-reliability source
    # than the other, while the verdict sides with the LOWER-reliability
    # stance? EXP-029 found this exact pattern in 0/14 real trials
    # producing a correct label -- a prompt-level fix did not resolve it,
    # so this deterministic cross-check exists to catch it after the fact.
    # Evidence objects without `.stance` (plain placeholders used by
    # callers that don't exercise this check) are skipped, same
    # discipline as Check 7's has_evaluable_entity guard.
    supporting_reliability: list[float] = []
    contradicting_reliability: list[float] = []
    for eid in cited:
        evidence = evidence_by_id[eid]
        source = source_by_evidence_id[eid]
        stance = getattr(evidence, "stance", None)
        reliability = getattr(source, "reliability_score", None)
        if stance is None or reliability is None:
            continue
        if stance == EvidenceStance.supports:
            supporting_reliability.append(reliability)
        elif stance == EvidenceStance.contradicts:
            contradicting_reliability.append(reliability)

    if supporting_reliability and contradicting_reliability:
        max_support = max(supporting_reliability)
        max_contradict = max(contradicting_reliability)
        gap = max_support - max_contradict
        reliability_violation_note = None
        if gap >= _RELIABILITY_GAP_THRESHOLD and proposal.verdict in _RELIABILITY_MISMATCH_NEGATIVE_LABELS:
            reliability_violation_note = (
                f"Cited evidence includes a supporting source with reliability {max_support:.2f} "
                f"vs. the highest contradicting source's {max_contradict:.2f} (gap {gap:.2f}), but the "
                f"verdict is {proposal.verdict.value} -- possible reliability-direction mismatch."
            )
        elif -gap >= _RELIABILITY_GAP_THRESHOLD and proposal.verdict in _RELIABILITY_MISMATCH_POSITIVE_LABELS:
            reliability_violation_note = (
                f"Cited evidence includes a contradicting source with reliability {max_contradict:.2f} "
                f"vs. the highest supporting source's {max_support:.2f} (gap {-gap:.2f}), but the "
                f"verdict is {proposal.verdict.value} -- possible reliability-direction mismatch."
            )
        if reliability_violation_note is not None:
            return ValidationOutcome(
                ValidationStatus.downgraded_reliability_mismatch,
                VerdictLabel.UNVERIFIED,
                min(proposal.confidence, _CAPPED_CONFIDENCE),
                [reliability_violation_note],
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
