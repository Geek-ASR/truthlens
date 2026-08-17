"""EXP-030 (research/RESEARCH_ROADMAP_V2.md Phase 11 follow-up):
real, disclosed evaluation of the candidate reliability-direction check
(reliability_direction_check.py) BEFORE any integration decision --
same discipline Checks 6/7 were held to (build, evaluate against real
and synthetic data, measure against a stopping condition, THEN decide).

Three parts:
1. 10 hand-designed synthetic cases spanning the intended-catch shape
   (EXP-029's exact scenario), the mirror-image direction, close-call
   gaps that should NOT fire, and missing-data cases -- a real
   precision/recall measurement against ground truth, not just "it ran."
2. A REPLAY of EXP-029's own actually-observed real verdict labels (14
   reliability_weighted_conflict trials, 5 majority_with_credible_outlier
   trials) through this check -- the most direct, real-world-grounded
   number: of the real trials that were wrong, how many would this
   check have caught? Of the ones that were reasonable, does it stay
   silent?
3. A false-positive sanity check against the EXISTING 34-case
   adversarial benchmark (build_and_run_v2.py) -- confirms (rather than
   assumes) that this check has zero effect on any existing case, since
   none of them wire real Evidence.stance + Source.reliability_score
   together for cited evidence.

Run: cd backend && ./.venv/bin/python research/verdict_reliability_v2/evaluate_reliability_check.py
"""
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.db.models import Evidence, EvidenceDirectness, EvidenceStance, Source, SourceTier, VerdictLabel  # noqa: E402
from research.validator_benchmark.build_and_run import build_cases  # noqa: E402
from research.validator_benchmark.build_and_run_v2 import build_new_cases  # noqa: E402
from research.verdict_reliability_v2.reliability_direction_check import reliability_direction_violation  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


def _ev(stance, reliability) -> tuple:
    eid = uuid.uuid4()
    evidence = Evidence(id=eid, claim_id=uuid.uuid4(), source_id=uuid.uuid4(), stance=stance,
                         explanation="synthetic", directness=EvidenceDirectness.direct,
                         analysis_model="synthetic")
    source = Source(id=uuid.uuid4(), url="https://example.test/x", source_type=SourceTier.other,
                     full_text_storage_key="x", relevant_passage="synthetic", reliability_score=reliability,
                     reliability_breakdown={})
    return eid, evidence, source


def _case(name, pairs, verdict_label, expected_flag):
    """pairs: list of (stance, reliability). Returns a dict result."""
    evidence_by_id, source_by_evidence_id, cited = {}, {}, []
    for stance, reliability in pairs:
        eid, evidence, source = _ev(stance, reliability)
        evidence_by_id[eid] = evidence
        source_by_evidence_id[eid] = source
        cited.append(eid)
    note = reliability_direction_violation(cited, evidence_by_id, source_by_evidence_id, verdict_label)
    flagged = note is not None
    correct = flagged == expected_flag
    return {"case": name, "verdict": verdict_label.value, "expected_flag": expected_flag,
            "flagged": flagged, "correct": correct, "note": note}


def part1_synthetic_precision_recall() -> list[dict]:
    S, C = EvidenceStance.supports, EvidenceStance.contradicts
    cases = [
        _case("R1_exact_exp029_shape_mostly_false", [(S, 0.95), (C, 0.20)], VerdictLabel.MOSTLY_FALSE, True),
        _case("R2_exact_exp029_shape_unverified", [(S, 0.95), (C, 0.20)], VerdictLabel.UNVERIFIED, True),
        _case("R3_exact_exp029_shape_correct_true", [(S, 0.95), (C, 0.20)], VerdictLabel.TRUE, False),
        _case("R4_reverse_direction_wrong_true", [(S, 0.20), (C, 0.95)], VerdictLabel.TRUE, True),
        _case("R5_reverse_direction_correct_false", [(S, 0.20), (C, 0.95)], VerdictLabel.FALSE, False),
        _case("R6_close_call_gap_should_not_fire", [(S, 0.75), (C, 0.65)], VerdictLabel.UNVERIFIED, False),
        _case("R7_majority_outlier_shape_should_not_fire", [(S, 0.75), (C, 0.85)], VerdictLabel.MOSTLY_TRUE, False),
        _case("R8_only_supporting_no_conflict", [(S, 0.95)], VerdictLabel.FALSE, False),
        _case("R9_only_contradicting_no_conflict", [(C, 0.95)], VerdictLabel.TRUE, False),
        _case("R10_multi_evidence_takes_max_each_side", [(S, 0.30), (S, 0.90), (C, 0.20), (C, 0.10)], VerdictLabel.UNVERIFIED, True),
    ]
    return cases


def part2_replay_exp029_real_trials() -> dict:
    S, C = EvidenceStance.supports, EvidenceStance.contradicts
    # Exact real observed labels from EXP-029 (research/CONTRADICTORY_SOURCES_V2.md,
    # experiments/registry.jsonl EXP-029): reliability_weighted_conflict is
    # always 0.95-support vs 0.20-contradict.
    reliability_weighted_trials = [
        VerdictLabel.MOSTLY_FALSE, VerdictLabel.UNVERIFIED, VerdictLabel.OUTDATED,  # pre-fix, verdict.v2
        VerdictLabel.UNVERIFIED, VerdictLabel.UNVERIFIED, VerdictLabel.MOSTLY_FALSE, VerdictLabel.MOSTLY_FALSE,
        VerdictLabel.MOSTLY_FALSE, VerdictLabel.UNVERIFIED, VerdictLabel.UNVERIFIED,  # post-fix, verdict.v3
        VerdictLabel.UNVERIFIED, VerdictLabel.UNVERIFIED, VerdictLabel.MOSTLY_FALSE, VerdictLabel.UNVERIFIED,
    ]
    # majority_with_credible_outlier: 3x 0.75-support vs 1x 0.85-contradict.
    majority_outlier_trials = [
        VerdictLabel.MOSTLY_TRUE,  # pre-fix single sample
        VerdictLabel.MOSTLY_TRUE, VerdictLabel.MOSTLY_TRUE, VerdictLabel.UNVERIFIED, VerdictLabel.UNVERIFIED,  # post-fix
    ]

    rw_results = []
    for label in reliability_weighted_trials:
        eid1, ev1, src1 = _ev(S, 0.95)
        eid2, ev2, src2 = _ev(C, 0.20)
        note = reliability_direction_violation(
            [eid1, eid2], {eid1: ev1, eid2: ev2}, {eid1: src1, eid2: src2}, label
        )
        rw_results.append({"verdict": label.value, "flagged": note is not None})

    mo_results = []
    for label in majority_outlier_trials:
        eid1, ev1, src1 = _ev(S, 0.75)
        eid2, ev2, src2 = _ev(C, 0.85)
        note = reliability_direction_violation(
            [eid1, eid2], {eid1: ev1, eid2: ev2}, {eid1: src1, eid2: src2}, label
        )
        mo_results.append({"verdict": label.value, "flagged": note is not None})

    return {"reliability_weighted_conflict": rw_results, "majority_with_credible_outlier": mo_results}


def part3_existing_benchmark_false_positive_check() -> dict:
    all_cases = build_cases() + build_new_cases()
    n_evaluable = 0
    n_flagged = 0
    flagged_case_ids = []
    for c in all_cases:
        note = reliability_direction_violation(
            c.proposal.cited_evidence_ids, c.evidence_by_id, c.source_by_evidence_id, c.proposal.verdict
        )
        # Evaluable = at least one cited evidence item actually has .stance
        # (i.e. is a real Evidence/Evidence-like object with the attribute,
        # not build_and_run.py's object() placeholder).
        has_stance_evidence = any(
            getattr(c.evidence_by_id.get(eid), "stance", None) is not None for eid in c.proposal.cited_evidence_ids
        )
        if has_stance_evidence:
            n_evaluable += 1
        if note is not None:
            n_flagged += 1
            flagged_case_ids.append(c.case_id)
    return {"total_cases": len(all_cases), "evaluable_cases": n_evaluable, "flagged_cases": n_flagged,
            "flagged_case_ids": flagged_case_ids}


def main() -> None:
    part1 = part1_synthetic_precision_recall()
    n_correct = sum(1 for c in part1 if c["correct"])
    print(f"Part 1 (synthetic precision/recall): {n_correct}/{len(part1)} correct", file=sys.stderr)
    for c in part1:
        status = "OK" if c["correct"] else "WRONG"
        print(f"  [{status}] {c['case']}: verdict={c['verdict']} expected_flag={c['expected_flag']} flagged={c['flagged']}", file=sys.stderr)

    part2 = part2_replay_exp029_real_trials()
    rw_flagged = sum(1 for r in part2["reliability_weighted_conflict"] if r["flagged"])
    mo_flagged = sum(1 for r in part2["majority_with_credible_outlier"] if r["flagged"])
    print(f"\nPart 2 (replay of EXP-029's real trials):", file=sys.stderr)
    print(f"  reliability_weighted_conflict: {rw_flagged}/{len(part2['reliability_weighted_conflict'])} real wrong trials would be flagged", file=sys.stderr)
    print(f"  majority_with_credible_outlier: {mo_flagged}/{len(part2['majority_with_credible_outlier'])} real trials flagged (expected 0 -- gap below threshold)", file=sys.stderr)

    part3 = part3_existing_benchmark_false_positive_check()
    print(f"\nPart 3 (existing 34-case benchmark, false-positive check):", file=sys.stderr)
    print(f"  {part3['evaluable_cases']}/{part3['total_cases']} cases have real stance-bearing cited evidence", file=sys.stderr)
    print(f"  {part3['flagged_cases']} cases flagged by this candidate check (expected 0)", file=sys.stderr)
    if part3["flagged_case_ids"]:
        print(f"  FLAGGED: {part3['flagged_case_ids']}", file=sys.stderr)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "verdict_reliability_check_evaluation_20260818.json"
    out_path.write_text(json.dumps({"part1_synthetic": part1, "part2_replay": part2, "part3_existing_benchmark": part3}, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
