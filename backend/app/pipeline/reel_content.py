"""Stage: assemble the rich, multi-claim carousel content (headline,
quote, per-claim evidence cards, claim table, source lists) for a whole
reel. Deliberately structured so almost everything comes DIRECTLY from
already-validated DB rows (claims, verdicts, evidence, sources) rather
than a single free-text LLM blob — only the headline phrasing and the
overall-verdict explanation go through the LLM, and both are narrow,
schema-constrained calls with a deterministic grounding check on their
output (same anti-fabrication pattern as claim_extraction's source_quote
check, docs/CURRENT_ARCHITECTURE.md)."""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.db.models import Claim, Evidence, Source, SourceTier, ValidationStatus, Verdict, VerdictLabel
from app.pipeline.overall_verdict import OverallVerdict
from app.schemas.content import HeadlineResult, OverallWhyResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import (
    HEADLINE_PROMPT_VERSION,
    HEADLINE_SYSTEM_PROMPT,
    OVERALL_WHY_PROMPT_VERSION,
    OVERALL_WHY_SYSTEM_PROMPT,
)

_PRIMARY_TIERS = {SourceTier.primary_government, SourceTier.primary_legal, SourceTier.primary_data}
_MAX_EVIDENCE_CARDS = 3
_MAX_SOURCES_PER_LIST = 4

# Real fabrication found live: HEADLINE_SYSTEM_PROMPT explicitly says
# "Never introduce a fact, number, date, or name that is not already in
# the claim text you were given" -- and the model violated it anyway,
# converting a claim's "4,000 crore rupees" into a headline reading "$1
# Billion" (an invented, and wrong -- 4,000 crore is roughly $480M, not
# $1B -- currency conversion nobody asked for). highlight_phrases already
# had a grounding check (must be a real substring of the headline this
# call wrote), but nothing checked the headline's own numbers against
# the source claim it was supposed to be restating. Same principle as
# validation.py's number-grounding check for verdict reasoning, applied
# to this separate exposure point.
_HEADLINE_NUMBER_PATTERN = re.compile(r"\d[\d,.]*")


def _numbers_in(text: str) -> set[str]:
    return {n.strip(",.") for n in _HEADLINE_NUMBER_PATTERN.findall(text)}


def _headline_numbers_are_grounded(headline: str, claim_text: str) -> bool:
    return all(n in claim_text for n in _numbers_in(headline))

_VERDICT_ICON = {
    VerdictLabel.TRUE: "✓",
    VerdictLabel.MOSTLY_TRUE: "✓",
    VerdictLabel.MISLEADING: "⚠",
    VerdictLabel.MISSING_CONTEXT: "⚠",
    VerdictLabel.OUTDATED: "⚠",
    VerdictLabel.MOSTLY_FALSE: "✗",
    VerdictLabel.FALSE: "✗",
    VerdictLabel.UNVERIFIED: "?",
}

# verdict.py appends "\n\n[VALIDATION NOTE: ...]" as a SUFFIX to
# reasoning_summary when a verdict gets downgraded (app/pipeline/verdict.py
# — always the last thing in the string, nothing is ever appended after
# it). Some models also occasionally echo internal-looking
# "[[evidence_id=... | source=...]]" citation markup into their own
# reasoning_summary text (observed live — docs/CURRENT_ARCHITECTURE.md).
# Neither is meant for an end reader; both are stripped before
# reasoning_summary is ever put on a slide or in the caption. This never
# touches the underlying Verdict row — only the copy shown to a viewer.
#
# Truncating at the marker (rather than a "[...]" bracket-matching regex)
# is deliberate: a naive regex here previously stopped at the FIRST "]" it
# found, which was the closing bracket of the Python list repr inside the
# note itself (e.g. "Numbers ['3065258', '69'] in reasoning_summary..."),
# leaving the note's own tail un-stripped and visible on the slide.
_VALIDATION_NOTE_MARKER = "[VALIDATION NOTE:"
_INTERNAL_MARKUP_PATTERN = re.compile(r"\[\[.*?\]\]", re.DOTALL)


def _display_text(raw: str) -> str:
    text = raw.split(_VALIDATION_NOTE_MARKER)[0]
    text = _INTERNAL_MARKUP_PATTERN.sub("", text)
    return " ".join(text.split()).strip()


# A downgraded verdict's reasoning_summary is prose the model wrote to
# justify its ORIGINAL (rejected) verdict — validate_verdict() strips
# neither the reasoning nor the specific sentence that caused the
# downgrade, because there's no reliable way to isolate just the bad
# sentence. Real failure found live (research_paper/benchmark/results.md
# bm-0002): a verdict downgraded for citing an unsupported number still
# had its full reasoning text — including an unrelated-entity hallucination
# ("this suggests [organization] has a violent ideology", sourced from a
# DIFFERENT, similarly-named organization's Wikipedia page) — reused
# verbatim as an evidence-card's answer_text AND as raw input material for
# the overall "why" paragraph's own LLM call, which then wove it into
# published output. Once a verdict fails validation, none of its free-text
# reasoning is safe to display or reuse — only the label and a generic,
# non-fabricated note are.
_UNVALIDATED_REASONING_NOTE = "Automated reasoning for this claim did not pass grounding checks; recorded as UNVERIFIED pending human review."


def _safe_reasoning_text(verdict: Verdict) -> str:
    if verdict.validation_status != ValidationStatus.passed:
        return _UNVALIDATED_REASONING_NOTE
    return _display_text(verdict.reasoning_summary)


@dataclass
class SourceCitation:
    label: str
    url: str
    date_str: str | None
    excerpt: str


@dataclass
class EvidenceCard:
    claim_text: str
    verdict_label: str
    icon: str
    answer_text: str
    primary_source: SourceCitation | None
    independent_source: SourceCitation | None


@dataclass
class ClaimTableRow:
    claim_text: str
    verdict_label: str
    icon: str


@dataclass
class ReelFactCheckContent:
    headline: str
    highlight_phrases: list[str]
    speaker_name: str | None
    quote: str | None
    key_points: list[str]
    evidence_cards: list[EvidenceCard] = field(default_factory=list)
    overall_verdict_label: str = ""
    why_paragraph: str = ""
    claim_table: list[ClaimTableRow] = field(default_factory=list)
    primary_sources: list[SourceCitation] = field(default_factory=list)
    independent_sources: list[SourceCitation] = field(default_factory=list)


def _citation_from_source(source: Source) -> SourceCitation:
    return SourceCitation(
        label=source.publisher or source.title or source.url,
        url=source.url,
        date_str=source.publication_date.strftime("%b %Y") if source.publication_date else None,
        excerpt=(source.relevant_passage or "")[:180],
    )


def _best_sources_for_claim(
    evidence_rows: list[Evidence], sources_by_id: dict
) -> tuple[SourceCitation | None, SourceCitation | None]:
    relevant = [e for e in evidence_rows if e.stance.value in ("supports", "contradicts")]
    ranked = sorted(relevant, key=lambda e: sources_by_id[e.source_id].reliability_score, reverse=True)
    primary = next((sources_by_id[e.source_id] for e in ranked if sources_by_id[e.source_id].source_type in _PRIMARY_TIERS), None)
    independent = next((sources_by_id[e.source_id] for e in ranked if sources_by_id[e.source_id].source_type not in _PRIMARY_TIERS), None)
    return (
        _citation_from_source(primary) if primary else None,
        _citation_from_source(independent) if independent else None,
    )


# Verbs that indicate a claim is ABOUT someone's statement/reaction, not
# a description of a fact, rule, or event. Used to pick which claim's
# source_quote actually belongs in the "quote box" — real bug found live
# (docs/CURRENT_ARCHITECTURE.md): defaulting to the highest-importance
# claim put a rule-description claim's quote in the box and attributed it
# to a Person entity ("Narendra Modi") that the extraction model had
# loosely associated with that claim from surrounding OCR context, not
# someone who actually said the quoted words.
_ATTRIBUTION_VERBS = (
    "criticized", "criticised", "alleged", "said", "claimed", "stated", "argued",
    "wrote", "posted", "tweeted", "warned", "accused", "called", "urged", "slammed",
)


def _find_quote_claim(claims: list[Claim]) -> Claim | None:
    candidates = [c for c in claims if c.source_quote and c.source_quote.strip()]
    attributed = [c for c in candidates if any(v in c.text.lower() for v in _ATTRIBUTION_VERBS)]
    pool = attributed or candidates
    return max(pool, key=lambda c: c.importance) if pool else None


def _speaker_name(quote_claim: Claim | None, reel_creator_handle: str | None) -> str | None:
    if quote_claim is not None and quote_claim.source_quote:
        quote_text_lower = quote_claim.source_quote.lower()
        for entity in quote_claim.entities or []:
            name = entity.get("name")
            # Grounding check: only trust a Person entity as the speaker
            # if its name actually appears in THIS claim's own text — not
            # just anywhere in the claim-extraction output for the reel.
            if "person" not in (entity.get("type") or "").lower() or not name or name not in quote_claim.text:
                continue
            # Second check, found live on a real reel
            # (docs/CURRENT_ARCHITECTURE.md): source_quote can be genuine
            # verbatim on-screen text that still isn't this person's own
            # words — e.g. a news-style caption like "Kejriwal Attacks
            # Centre Over New 3-Hour Takedown Rule", written by the
            # publisher ABOUT him, in the third person. A person's own
            # quote essentially never refers to themselves by name, so if
            # any part of their name shows up inside the quote text
            # itself, treat it as third-person description rather than
            # trusting it as first-person speech.
            name_parts = [p.lower() for p in name.split() if len(p) > 2]
            if any(part in quote_text_lower for part in name_parts):
                continue
            return name
    return reel_creator_handle


async def _generate_headline(primary_claim: Claim) -> HeadlineResult:
    provider = get_llm_provider()
    settings = get_settings()
    result = await provider.structured_call(
        model=settings.LLM_MODEL_CONTENT_GENERATION,
        system_prompt=HEADLINE_SYSTEM_PROMPT,
        user_content=f"CLAIM: {primary_claim.text}",
        output_schema=HeadlineResult,
        prompt_version=HEADLINE_PROMPT_VERSION,
    )
    parsed = result.parsed
    headline = parsed.headline

    if not _headline_numbers_are_grounded(headline, primary_claim.text):
        # The model invented/changed a number despite being told not to
        # (see _HEADLINE_NUMBER_PATTERN's comment for the real case this
        # was found from). No amount of highlight-phrase validation makes
        # a fabricated number safe to publish, so the whole generated
        # headline is discarded here, not just trimmed -- fall back to
        # the claim's own already-grounded text verbatim, which can never
        # introduce a number the claim didn't already have.
        headline = primary_claim.text[:180]
        return HeadlineResult(headline=headline, highlight_phrases=[])

    # Grounding check, same principle as claim_extraction's source_quote
    # check: a highlight phrase that isn't actually a substring of the
    # headline the model itself wrote is dropped, not trusted.
    validated_phrases = [p for p in parsed.highlight_phrases if p and p in headline]
    return HeadlineResult(headline=headline, highlight_phrases=validated_phrases)


async def _generate_why_paragraph(overall: OverallVerdict) -> str:
    if not overall.claim_verdicts:
        return overall.reasoning
    provider = get_llm_provider()
    settings = get_settings()
    claims_block = "\n".join(
        f"- Claim: {c.text}\n  Verdict: {v.verdict.value}\n  Reasoning: {_safe_reasoning_text(v)}"
        for c, v in overall.claim_verdicts
    )
    user_content = f"OVERALL VERDICT: {overall.label.value}\n\nCLAIMS:\n{claims_block}"
    try:
        result = await provider.structured_call(
            model=settings.LLM_MODEL_CONTENT_GENERATION,
            system_prompt=OVERALL_WHY_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=OverallWhyResult,
            prompt_version=OVERALL_WHY_PROMPT_VERSION,
        )
        text = _display_text(result.parsed.why_paragraph)
        return text if text else overall.reasoning
    except Exception:  # noqa: BLE001 — the deterministic reasoning is always a safe fallback
        return overall.reasoning


async def assemble_reel_content(
    *,
    reel_creator_handle: str | None,
    overall: OverallVerdict,
    evidence_by_claim: dict,  # claim.id -> list[Evidence]
    sources_by_id: dict,  # source.id -> Source
) -> ReelFactCheckContent:
    if not overall.claim_verdicts:
        return ReelFactCheckContent(
            headline="No verifiable factual claims could be checked in this reel.",
            highlight_phrases=[],
            speaker_name=reel_creator_handle,
            quote=None,
            key_points=[],
            overall_verdict_label=overall.label.value,
            why_paragraph=overall.reasoning,
        )

    primary_claim = max((c for c, _ in overall.claim_verdicts), key=lambda c: c.importance)
    headline_result = await _generate_headline(primary_claim)
    why_paragraph = await _generate_why_paragraph(overall)

    quote_claim = _find_quote_claim([c for c, _ in overall.claim_verdicts])
    quote = quote_claim.source_quote if quote_claim else None
    speaker_name = _speaker_name(quote_claim, reel_creator_handle)

    evidence_cards: list[EvidenceCard] = []
    claim_table: list[ClaimTableRow] = []
    all_primary: dict[str, SourceCitation] = {}
    all_independent: dict[str, SourceCitation] = {}

    ranked_claims = sorted(overall.claim_verdicts, key=lambda cv: cv[0].importance, reverse=True)
    for claim, verdict in ranked_claims:
        icon = _VERDICT_ICON.get(verdict.verdict, "?")
        claim_table.append(ClaimTableRow(claim_text=claim.text, verdict_label=verdict.verdict.value, icon=icon))

        if len(evidence_cards) < _MAX_EVIDENCE_CARDS:
            claim_evidence = evidence_by_claim.get(claim.id, [])
            primary_source, independent_source = _best_sources_for_claim(claim_evidence, sources_by_id)
            if primary_source:
                all_primary.setdefault(primary_source.url, primary_source)
            if independent_source:
                all_independent.setdefault(independent_source.url, independent_source)
            evidence_cards.append(
                EvidenceCard(
                    claim_text=claim.text,
                    verdict_label=verdict.verdict.value,
                    icon=icon,
                    answer_text=_safe_reasoning_text(verdict),
                    primary_source=primary_source,
                    independent_source=independent_source,
                )
            )

    return ReelFactCheckContent(
        headline=headline_result.headline,
        highlight_phrases=headline_result.highlight_phrases,
        speaker_name=speaker_name,
        quote=quote,
        key_points=[c.text for c, _ in ranked_claims],
        evidence_cards=evidence_cards,
        overall_verdict_label=overall.label.value,
        why_paragraph=why_paragraph,
        claim_table=claim_table,
        primary_sources=list(all_primary.values())[:_MAX_SOURCES_PER_LIST],
        independent_sources=list(all_independent.values())[:_MAX_SOURCES_PER_LIST],
    )
