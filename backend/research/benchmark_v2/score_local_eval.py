"""Scores research/results/local_eval_v2.jsonl (produced by
run_local_eval.py) against the v2 `validation` ground truth, using the
metric definitions in research/METRICS.md verbatim:

  * Accuracy denominator  = items with outcome_type == "resolved".
  * Label bucketing       = TRUE/MOSTLY_TRUE -> TRUE; FALSE/MOSTLY_FALSE
                            -> FALSE; MISLEADING/MISSING_CONTEXT/OUTDATED
                            -> MISLEADING.  UNVERIFIED never matches any
                            ground-truth label.
  * Macro-F1 over the full VerdictLabel set (not micro -- small,
    non-stratified sample).  Per-class F1 reported alongside.
  * Balanced accuracy = mean per-bucket recall (the metric the 83% FALSE
    skew requires; an always-FALSE predictor scores ~0.33 on it).
  * Abstention rate, false-abstention rate, research-failed rate, all
    reported separately, never folded into accuracy.

Also breaks results down by platform / ground-truth label / language /
vision-context-availability / annotation_status, and puts a Wilson 95%
CI on the headline accuracy (same CI convention as the paper).

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.score_local_eval
"""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
_RESULTS = _ROOT / "research" / "results" / "local_eval_v2.jsonl"
_ITEMS_V2 = _ROOT / "research" / "dataset" / "items_v2.jsonl"
_REPORT = _ROOT / "research" / "results" / "LOCAL_EVAL_V2_REPORT.md"
_SCORES = _ROOT / "research" / "results" / "local_eval_v2_scores.json"

_BUCKET = {
    "TRUE": "TRUE", "MOSTLY_TRUE": "TRUE",
    "FALSE": "FALSE", "MOSTLY_FALSE": "FALSE",
    "MISLEADING": "MISLEADING", "MISSING_CONTEXT": "MISLEADING", "OUTDATED": "MISLEADING",
    "UNVERIFIED": "UNVERIFIED",
}
_GT_BUCKETS = ["FALSE", "MISLEADING", "TRUE"]
_ALL_LABELS = ["TRUE", "MOSTLY_TRUE", "MISLEADING", "MOSTLY_FALSE", "FALSE", "UNVERIFIED", "OUTDATED", "MISSING_CONTEXT"]


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _load_rows() -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in _RESULTS.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            rows[r["item_id"]] = r  # last write wins (resume-friendly)
    return rows


def _load_items() -> dict[str, dict]:
    return {
        json.loads(l)["item_id"]: json.loads(l)
        for l in _ITEMS_V2.read_text().splitlines()
        if l.strip()
    }


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def main() -> None:
    rows = _load_rows()
    items = _load_items()
    L: list[str] = []
    scores: dict = {}

    n_items = len(items)
    n_scored = len(rows)
    L.append("# TruthLens local-only configuration -- validation-split evaluation\n")
    L.append(f"- Corpus: v2 `validation` split, {n_items} items")
    L.append(f"- Rows in `local_eval_v2.jsonl`: {n_scored}"
             + ("" if n_scored == n_items else f"  **(INCOMPLETE: {n_items - n_scored} not yet run)**"))
    L.append("- Configuration: `full_truthlens_local` -- every stage on local llama3.2, "
             "DuckDuckGo keyless search, no Gemini escalation, no API keys, $0.\n")

    # --- outcome distribution ---
    oc = Counter(r["outcome_type"] for r in rows.values())
    L.append("## Outcome distribution\n")
    L.append("| outcome_type | n | share of scored |")
    L.append("|---|--:|--:|")
    for k in ("resolved", "no_verifiable_claims", "research_failed", "error"):
        L.append(f"| {k} | {oc.get(k, 0)} | {_pct(oc.get(k, 0) / n_scored) if n_scored else '-'} |")
    L.append("")
    scores["outcome_distribution"] = dict(oc)

    resolved = {iid: r for iid, r in rows.items() if r["outcome_type"] == "resolved"}
    n_res = len(resolved)

    # --- headline accuracy (bucketed), over resolved ---
    correct = 0
    conf = defaultdict(Counter)  # gt_bucket -> Counter(pred_bucket)
    for iid, r in resolved.items():
        gt_b = _BUCKET.get((r.get("ground_truth_label") or "").upper())
        pr_b = _BUCKET.get((r.get("predicted_label") or "").upper(), "UNVERIFIED")
        conf[gt_b][pr_b] += 1
        if gt_b is not None and pr_b == gt_b:
            correct += 1
    acc = correct / n_res if n_res else 0.0
    lo, hi = _wilson(correct, n_res)
    L.append("## Headline verdict accuracy (bucketed, resolved items only)\n")
    L.append(f"- **Accuracy = {correct}/{n_res} = {_pct(acc)}**  (Wilson 95% CI [{_pct(lo)}, {_pct(hi)}])")

    # balanced accuracy = mean recall over the 3 GT buckets present
    per_bucket_recall = {}
    for b in _GT_BUCKETS:
        tot = sum(conf[b].values())
        per_bucket_recall[b] = (conf[b][b] / tot) if tot else None
    present = [v for v in per_bucket_recall.values() if v is not None]
    bal_acc = sum(present) / len(present) if present else 0.0
    L.append(f"- **Balanced accuracy (mean per-bucket recall) = {_pct(bal_acc)}**")
    # always-FALSE / majority baseline over resolved
    gt_bucket_counts = Counter(_BUCKET.get((r.get("ground_truth_label") or "").upper()) for r in resolved.values())
    maj_bucket, maj_n = gt_bucket_counts.most_common(1)[0] if gt_bucket_counts else (None, 0)
    L.append(f"- Majority-class baseline (always predict {maj_bucket}) = {_pct(maj_n / n_res) if n_res else '-'}  "
             f"(balanced accuracy {_pct(1/3)})")
    L.append("")
    scores["accuracy"] = {"correct": correct, "n_resolved": n_res, "accuracy": acc,
                          "wilson95": [lo, hi], "balanced_accuracy": bal_acc,
                          "per_bucket_recall": per_bucket_recall,
                          "majority_class": maj_bucket, "majority_baseline_acc": (maj_n / n_res) if n_res else None}

    # --- confusion matrix ---
    L.append("## Confusion matrix (ground-truth bucket x predicted bucket, resolved items)\n")
    pred_cols = ["FALSE", "MISLEADING", "TRUE", "UNVERIFIED"]
    L.append("| GT \\ pred | " + " | ".join(pred_cols) + " | row total |")
    L.append("|---|" + "|".join(["--:"] * (len(pred_cols) + 1)) + "|")
    for b in _GT_BUCKETS:
        tot = sum(conf[b].values())
        L.append(f"| **{b}** | " + " | ".join(str(conf[b][c]) for c in pred_cols) + f" | {tot} |")
    L.append("")
    scores["confusion_matrix"] = {b: dict(conf[b]) for b in _GT_BUCKETS}

    # --- macro-F1 / per-class F1 over full label set (resolved) ---
    L.append("## Per-class F1 over the full label set (resolved items)\n")
    L.append("| label | precision | recall | F1 | support (GT) |")
    L.append("|---|--:|--:|--:|--:|")
    f1s = []
    per_class = {}
    for lab in _ALL_LABELS:
        tp = sum(1 for r in resolved.values()
                 if (r.get("predicted_label") or "").upper() == lab and (r.get("ground_truth_label") or "").upper() == lab)
        fp = sum(1 for r in resolved.values()
                 if (r.get("predicted_label") or "").upper() == lab and (r.get("ground_truth_label") or "").upper() != lab)
        fn = sum(1 for r in resolved.values()
                 if (r.get("predicted_label") or "").upper() != lab and (r.get("ground_truth_label") or "").upper() == lab)
        sup = sum(1 for r in resolved.values() if (r.get("ground_truth_label") or "").upper() == lab)
        p, rec, f = _prf(tp, fp, fn)
        per_class[lab] = {"precision": p, "recall": rec, "f1": f, "support": sup, "tp": tp, "fp": fp, "fn": fn}
        if sup > 0 or tp + fp > 0:
            L.append(f"| {lab} | {p:.3f} | {rec:.3f} | {f:.3f} | {sup} |")
        if sup > 0:  # macro-F1 averaged over classes actually present in GT
            f1s.append(f)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0
    L.append(f"\n- **Macro-F1 (over {len(f1s)} GT-present classes) = {macro_f1:.3f}**\n")
    scores["macro_f1"] = macro_f1
    scores["per_class"] = per_class

    # --- abstention / research-failed ---
    n_unv_resolved = sum(1 for r in resolved.values() if (r.get("predicted_label") or "").upper() == "UNVERIFIED")
    n_novc = oc.get("no_verifiable_claims", 0)
    n_rf = oc.get("research_failed", 0)
    n_err = oc.get("error", 0)
    abst = n_unv_resolved / n_res if n_res else 0.0
    # METRICS.md defines "false-abstention rate" strictly as UNVERIFIED *outputs*
    # (a produced verdict of UNVERIFIED) on a confidently-resolvable (Tier-1) item,
    # over Tier-1 items. All 193 v2 items are Tier-1 by construction, so:
    strict_false_abst = n_unv_resolved / n_scored if n_scored else 0.0
    # The broader quantity below -- every item on which the system produced no
    # committed verdict, for ANY reason -- is NOT the pre-registered false-abstention
    # rate; it is a "declined-to-answer / non-response rate". Reported under its own
    # name so the two are never conflated (prior versions mislabelled this "false
    # abstention"; see EXPERIMENT_PROTOCOL_V3 / METRICS_ADDENDUM_V3).
    non_response = (n_unv_resolved + n_novc + n_rf) / n_scored if n_scored else 0.0
    L.append("## Abstention and infrastructure outcomes\n")
    L.append(f"- Abstention rate (UNVERIFIED / resolved) = {n_unv_resolved}/{n_res} = {_pct(abst)}")
    L.append(f"- False-abstention rate, METRICS.md strict (UNVERIFIED outputs / Tier-1 items) "
             f"= {n_unv_resolved}/{n_scored} = {_pct(strict_false_abst)}")
    L.append(f"- Declined-to-answer / non-response rate ((UNVERIFIED-resolved + no_verifiable_claims "
             f"+ research_failed) / scored) = {n_unv_resolved + n_novc + n_rf}/{n_scored} = {_pct(non_response)}")
    L.append(f"- Research-failed rate = {n_rf}/{n_scored} = {_pct(n_rf / n_scored) if n_scored else '-'}")
    L.append(f"- Errored items = {n_err}\n")
    scores["abstention_rate"] = abst
    scores["false_abstention_rate_strict"] = strict_false_abst
    scores["non_response_rate"] = non_response
    scores["research_failed_rate"] = (n_rf / n_scored) if n_scored else None

    # --- breakdowns ---
    def breakdown(title: str, keyfn):
        L.append(f"## Accuracy by {title} (resolved items)\n")
        L.append(f"| {title} | n resolved | correct | accuracy |")
        L.append("|---|--:|--:|--:|")
        buckets = defaultdict(lambda: [0, 0])
        for iid, r in resolved.items():
            it = items.get(iid, {})
            key = keyfn(r, it)
            gt_b = _BUCKET.get((r.get("ground_truth_label") or "").upper())
            pr_b = _BUCKET.get((r.get("predicted_label") or "").upper(), "UNVERIFIED")
            buckets[key][0] += 1
            if gt_b is not None and pr_b == gt_b:
                buckets[key][1] += 1
        for key in sorted(buckets, key=lambda k: str(k)):
            nn, cc = buckets[key]
            L.append(f"| {key} | {nn} | {cc} | {_pct(cc / nn) if nn else '-'} |")
        L.append("")

    breakdown("platform", lambda r, it: it.get("platform") or r.get("platform") or "?")
    breakdown("ground-truth label", lambda r, it: (r.get("ground_truth_label") or "?"))
    breakdown("language", lambda r, it: it.get("language") or "?")
    breakdown("vision_context_available", lambda r, it: str(r.get("vision_context_available")))
    breakdown("annotation_status", lambda r, it: it.get("annotation_status") or "(pre-protocol)")

    _REPORT.write_text("\n".join(L) + "\n")
    _SCORES.write_text(json.dumps(scores, indent=2))
    print(f"wrote {_REPORT}")
    print(f"wrote {_SCORES}")
    print("\n".join(L[:40]))


if __name__ == "__main__":
    main()
