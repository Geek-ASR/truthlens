"""Stage: derive ONE overall reel-level verdict from already-validated
claim-level verdicts (product spec: "the overall verdict should be
generated only AFTER claim-level verdicts exist... Claim 1: TRUE, Claim 2:
TRUE, Claim 3: FALSE -> Overall: MISLEADING").

Deterministic, not an LLM call: every claim verdict fed in has already
been through propose_verdict()'s LLM-plus-anti-hallucination-validator
pipeline, so aggregating them is a fixed-rule decision, not a new
judgment call that needs its own evidence. This keeps the highest-stakes
number in the product (the headline verdict shown on slide 1) fully
auditable from a truth table, not a second opaque model call."""
from dataclasses import dataclass

from app.db.models import Claim, ClaimStatus, Verdict, VerdictLabel

_MAJOR_CLAIM_IMPORTANCE = 0.5  # a claim at/above this weight can singlehandedly steer the overall verdict


@dataclass
class OverallVerdict:
    label: VerdictLabel
    reasoning: str
    claim_verdicts: list[tuple[Claim, Verdict]]  # only the ones that actually factored in
    unresolved_claim_count: int  # research_failed / no-verdict claims, excluded from the label decision


def derive_overall_verdict(claim_verdict_pairs: list[tuple[Claim, Verdict | None]]) -> OverallVerdict:
    resolved = [(c, v) for c, v in claim_verdict_pairs if v is not None and c.status != ClaimStatus.research_failed]
    unresolved_count = len(claim_verdict_pairs) - len(resolved)

    if not resolved:
        return OverallVerdict(
            label=VerdictLabel.UNVERIFIED,
            reasoning="No claims from this reel could be fully researched and verified.",
            claim_verdicts=[],
            unresolved_claim_count=unresolved_count,
        )

    labels = {v.verdict for _, v in resolved}
    major_labels = {v.verdict for c, v in resolved if c.importance >= _MAJOR_CLAIM_IMPORTANCE}

    def _reasoning(label: VerdictLabel) -> str:
        parts = []
        for claim, verdict in resolved:
            parts.append(f"\"{claim.text}\" — {verdict.verdict.value.replace('_', ' ')}")
        joined = "; ".join(parts)
        return f"Overall verdict {label.value.replace('_', ' ')} derived from {len(resolved)} claim-level verdict(s): {joined}."

    # Rule table, in priority order. Each rule is a plain, checkable
    # condition over the SET of already-established claim verdicts —
    # nothing here re-derives a fact, it only combines conclusions.
    if labels == {VerdictLabel.TRUE}:
        label = VerdictLabel.TRUE
    elif labels == {VerdictLabel.FALSE}:
        label = VerdictLabel.FALSE
    elif VerdictLabel.FALSE in labels and (VerdictLabel.TRUE in labels or VerdictLabel.MOSTLY_TRUE in labels):
        # A real mix of accurate and false claims is the textbook
        # definition of a misleading reel, not a wholesale fabrication.
        label = VerdictLabel.MISLEADING
    elif VerdictLabel.FALSE in major_labels:
        label = VerdictLabel.FALSE
    elif VerdictLabel.FALSE in labels or VerdictLabel.MOSTLY_FALSE in labels:
        label = VerdictLabel.MOSTLY_FALSE
    elif VerdictLabel.MISLEADING in labels:
        label = VerdictLabel.MISLEADING
    elif VerdictLabel.MISSING_CONTEXT in labels:
        label = VerdictLabel.MISSING_CONTEXT
    elif VerdictLabel.OUTDATED in labels:
        label = VerdictLabel.OUTDATED
    elif labels == {VerdictLabel.UNVERIFIED}:
        label = VerdictLabel.UNVERIFIED
    elif VerdictLabel.TRUE in labels and VerdictLabel.UNVERIFIED in labels:
        # Some of the reel checks out, some couldn't be confirmed either
        # way — not false, but not fully verified either.
        label = VerdictLabel.MOSTLY_TRUE if VerdictLabel.TRUE in major_labels else VerdictLabel.UNVERIFIED
    else:
        label = VerdictLabel.MISLEADING if len(labels) > 1 else next(iter(labels))

    return OverallVerdict(
        label=label,
        reasoning=_reasoning(label),
        claim_verdicts=resolved,
        unresolved_claim_count=unresolved_count,
    )
