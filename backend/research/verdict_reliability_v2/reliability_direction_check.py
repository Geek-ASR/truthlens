"""Candidate 8th deterministic validator check (research/RESEARCH_ROADMAP_V2.md
Phase 11 follow-up, named as the likely real fix in EXP-029/
research/CONTRADICTORY_SOURCES_V2.md, NOT yet integrated into
app/pipeline/validation.py -- this module exists to be evaluated first,
per this project's own Rule 4 discipline ("no complexity without
experimental justification") and the same build-then-evaluate pattern
Checks 6/7 followed before their own integration decision.

EXP-029 found verdict.propose_verdict() does not reliably let a large
source-reliability gap steer the verdict LABEL under direct
contradiction: a 0.95-reliability primary-government source supporting
a claim lost to a 0.20-reliability, uncited source contradicting it in
0/14 real trials, even when the model's own reasoning correctly
identified the low-reliability side as unreliable. A prompt-level fix
did not resolve this.

This check is a deterministic, purely mechanical cross-check: among the
CITED evidence for a verdict, if one stance (supports or contradicts)
has a meaningfully higher maximum reliability_score than the other, and
the verdict's LABEL sides with the LOWER-reliability stance, flag it.
Deliberately conservative (see _RELIABILITY_GAP_THRESHOLD) to avoid
punishing genuinely close calls -- this is meant to catch the specific,
measured EXP-029 failure shape (a wide, unambiguous reliability gap),
not to adjudicate every contested case.

**Outcome (EXP-030, research/CONTRADICTORY_SOURCES_V2.md)**: evaluated
against 10 synthetic ground-truth cases (10/10 correct), a replay of
EXP-029's own 19 real observed verdict labels (14/14 real wrong trials
caught, 0/5 false positives on the genuinely ambiguous sanity-check
case), and the existing 34-case adversarial benchmark (0 interactions,
confirming no regression risk). This cleared the same integration bar
Checks 6/7 were held to and was promoted into production as Check 8 in
`app/pipeline/validation.py` (`ValidationStatus.downgraded_reliability_mismatch`).
This module and its logic remain here as the historical
build-then-evaluate record; `app/pipeline/validation.py` is the
canonical, live copy -- keep them in sync if either changes.
"""
from app.db.models import EvidenceStance, VerdictLabel

# EXP-029's own diagnostic case had a 0.75 gap (0.95 vs 0.20) and never
# once produced a correct label across 14 trials; the majority_with
# _credible_outlier sanity check's gap was only 0.10 (0.85 vs 0.75) and
# behaved reasonably (or at least ambiguously, not clearly wrong) about
# half the time. 0.4 sits well clear of the "genuinely close call" zone
# observed in that second case while still catching the first.
_RELIABILITY_GAP_THRESHOLD = 0.4

_NEGATIVE_LABELS = {
    VerdictLabel.FALSE, VerdictLabel.MOSTLY_FALSE, VerdictLabel.UNVERIFIED,
    # OUTDATED effectively sides with "this used to be true but changed" --
    # functionally the same as siding with the contradicting evidence, and
    # the exact real EXP-029 case this check is meant to catch (a wrong
    # OUTDATED label paired with confidence 1.0 against a 0.95-reliability
    # primary-government source) would otherwise slip through uncaught.
    VerdictLabel.OUTDATED,
}
_POSITIVE_LABELS = {VerdictLabel.TRUE, VerdictLabel.MOSTLY_TRUE}


def reliability_direction_violation(
    cited_evidence_ids, evidence_by_id: dict, source_by_evidence_id: dict, verdict_label: VerdictLabel
) -> str | None:
    """Returns a human-readable violation note, or None if no violation
    (including when there isn't enough information to evaluate --
    matches Check 7's own precedent of doing nothing rather than
    guessing when its preconditions aren't met)."""
    supporting_reliability: list[float] = []
    contradicting_reliability: list[float] = []

    for eid in cited_evidence_ids:
        evidence = evidence_by_id.get(eid)
        source = source_by_evidence_id.get(eid)
        # Plain Evidence-shaped stand-ins (object()) used by cases that
        # don't exercise this check at all have no .stance -- skip them,
        # same discipline as Check 7's has_evaluable_entity guard.
        stance = getattr(evidence, "stance", None)
        reliability = getattr(source, "reliability_score", None)
        if stance is None or reliability is None:
            continue
        if stance == EvidenceStance.supports:
            supporting_reliability.append(reliability)
        elif stance == EvidenceStance.contradicts:
            contradicting_reliability.append(reliability)

    if not supporting_reliability or not contradicting_reliability:
        return None  # no real conflict between cited evidence to evaluate

    max_support = max(supporting_reliability)
    max_contradict = max(contradicting_reliability)
    gap = max_support - max_contradict

    if gap >= _RELIABILITY_GAP_THRESHOLD and verdict_label in _NEGATIVE_LABELS:
        return (
            f"Cited evidence includes a supporting source with reliability {max_support:.2f} "
            f"vs. the highest contradicting source's {max_contradict:.2f} (gap {gap:.2f}), but the "
            f"verdict is {verdict_label.value} -- possible reliability-direction mismatch."
        )
    if -gap >= _RELIABILITY_GAP_THRESHOLD and verdict_label in _POSITIVE_LABELS:
        return (
            f"Cited evidence includes a contradicting source with reliability {max_contradict:.2f} "
            f"vs. the highest supporting source's {max_support:.2f} (gap {-gap:.2f}), but the "
            f"verdict is {verdict_label.value} -- possible reliability-direction mismatch."
        )
    return None
