"""Day 8: consolidate every real result file collected across Days 3-8
into the final comparison tables. Reads only real, already-collected
data (research/results/*.jsonl, *.json) -- computes nothing that wasn't
actually run. Writes plain-text tables to stdout and a JSON summary to
research/results/day8_summary.json.
"""
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = PROJECT_ROOT / "research" / "results"

_BUCKETS = {
    "TRUE": "TRUE_ADJ", "MOSTLY_TRUE": "TRUE_ADJ",
    "FALSE": "FALSE_ADJ", "MOSTLY_FALSE": "FALSE_ADJ",
    "UNVERIFIED": "UNVERIFIED",
}


def bucket(label):
    return _BUCKETS.get(label, label)  # MISLEADING/MISSING_CONTEXT/OUTDATED/None each their own bucket


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = (z * math.sqrt((p * (1 - p) + z**2 / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


def accuracy_and_ci(rows, label_key="predicted_label", gt_key="ground_truth_label"):
    resolved = [r for r in rows if r.get(label_key)]
    if not resolved:
        return 0, 0, (0.0, 0.0)
    matches = sum(1 for r in resolved if bucket(r[label_key]) == bucket(r[gt_key]))
    lo, hi = wilson_ci(matches, len(resolved))
    return matches, len(resolved), (lo, hi)


def main():
    b1 = load_jsonl(RESULTS_DIR / "baseline_llm_only_20260813T091300Z.jsonl")
    b2 = load_jsonl(RESULTS_DIR / "baseline_search_llm_20260813T090758Z.jsonl")
    b3 = load_jsonl(RESULTS_DIR / "baseline_search_rag_llm_20260813T091225Z.jsonl")
    full_tl = json.loads((RESULTS_DIR / "full_truthlens_reel_level_day8.json").read_text())
    decomp = json.loads((RESULTS_DIR / "claim_decomposition_ablation.json").read_text())

    print("=" * 70)
    print("TABLE 1: Main baseline comparison (bucket accuracy)")
    print("=" * 70)
    print(f"{'Config':<25} {'n':>4} {'correct':>8} {'accuracy':>10} {'95% CI':>18}")
    for name, rows in [("Baseline 1 (LLM-only)", b1), ("Baseline 2 (Search+LLM)", b2), ("Baseline 3 (Search+RAG+LLM)", b3)]:
        k, n, (lo, hi) = accuracy_and_ci(rows)
        print(f"{name:<25} {n:>4} {k:>8} {k/n:>9.1%} {f'[{lo:.1%}, {hi:.1%}]':>18}")

    full_resolved = [r for r in full_tl if r.get("full_truthlens_label")]
    full_tl_k = sum(1 for r in full_resolved if bucket(r["full_truthlens_label"]) == bucket(r["ground_truth"]))
    full_tl_n = len(full_resolved)
    lo, hi = wilson_ci(full_tl_k, full_tl_n)
    print(f"{'Full TruthLens (n=6)':<25} {full_tl_n:>4} {full_tl_k:>8} {full_tl_k/full_tl_n:>9.1%} {f'[{lo:.1%}, {hi:.1%}]':>18}")
    print()
    print("NOTE: Full TruthLens covers 6/9 items (item-0003 never")
    print("ingestable; items 0008/0009 blocked by real Gemini quota")
    print("exhaustion during this Day 8 pass -- not silently omitted,")
    print("see research/results/day8_summary.json 'known_gaps'.")
    print("Baselines 1-3 cover all 9 items -- NOT a like-for-like n until")
    print("re-run restricted to the same 6-item subset (Table 2).")
    print()

    print("=" * 70)
    print("TABLE 2: Paired comparison on the SAME 6 items full TruthLens covers")
    print("=" * 70)
    full_ids = {r["item_id"] for r in full_resolved}
    print(f"{'Config':<25} {'n':>4} {'correct':>8} {'accuracy':>10} {'95% CI':>18}")
    table2_paired = {}
    for name, rows in [("Baseline 1 (LLM-only)", b1), ("Baseline 2 (Search+LLM)", b2), ("Baseline 3 (Search+RAG+LLM)", b3)]:
        subset = [r for r in rows if r["item_id"] in full_ids]
        pk, pn, (lo, hi) = accuracy_and_ci(subset)
        table2_paired[name] = {"n": pn, "correct": pk}
        print(f"{name:<25} {pn:>4} {pk:>8} {pk/pn:>9.1%} {f'[{lo:.1%}, {hi:.1%}]':>18}")

    full_correct = sum(1 for r in full_resolved if bucket(r["full_truthlens_label"]) == bucket(r["ground_truth"]))
    full_n = len(full_resolved)
    full_lo, full_hi = wilson_ci(full_correct, full_n)
    print(f"{'Full TruthLens':<25} {full_n:>4} {full_correct:>8} {full_correct / full_n:>9.1%} "
          f"{f'[{full_lo:.1%}, {full_hi:.1%}]':>18}")

    print()
    print("=" * 70)
    print("TABLE 3: Claim-decomposition ablation (single-claim vs multi-claim)")
    print("=" * 70)
    single_k = sum(1 for r in decomp if r["single_claim_match"])
    multi_k = sum(1 for r in decomp if r["multi_claim_match"])
    decomp_n = len(decomp)
    print(f"{'Single-claim (primary only)':<30} {decomp_n:>4} {single_k:>8} {single_k/decomp_n:>9.1%}")
    print(f"{'Multi-claim (full decomposition)':<30} {decomp_n:>4} {multi_k:>8} {multi_k/decomp_n:>9.1%}")
    print()
    print("Per-item detail:")
    for r in decomp:
        print(f"  {r['item_id']}: n_claims={r['n_claims']} | single={r['single_claim_label']} ({r['single_claim_match']}) | "
              f"multi={r['multi_claim_label']} ({r['multi_claim_match']}) | gt={r['ground_truth']}")

    print()
    print("=" * 70)
    print("TABLE 2 CORRECTED: paired n=6, baselines re-run per real extracted")
    print("claim (fixes AUDIT_REPORT.md Finding 1 -- see baseline_corrected_per_claim.py)")
    print("=" * 70)
    corrected_path = RESULTS_DIR / "baselines_corrected_per_claim_20260814.json"
    table2_corrected = {}
    if corrected_path.exists():
        corrected = json.loads(corrected_path.read_text())
        name_map = {"llm_only": "Baseline 1 (LLM-only)", "search_llm": "Baseline 2 (Search+LLM)", "search_rag_llm": "Baseline 3 (Search+RAG+LLM)"}
        key_map = {"llm_only": "baseline_1_llm_only", "search_llm": "baseline_2_search_llm", "search_rag_llm": "baseline_3_search_rag_llm"}
        for config, rows in corrected.items():
            ck = sum(1 for r in rows if bucket(r["predicted_label"]) == bucket(r["ground_truth_label"]))
            cn = len(rows)
            lo, hi = wilson_ci(ck, cn)
            table2_corrected[key_map[config]] = {"n": cn, "correct": ck}
            print(f"{name_map[config]:<25} {cn:>4} {ck:>8} {ck/cn:>9.1%} {f'[{lo:.1%}, {hi:.1%}]':>18}")
        print(f"{'Full TruthLens':<25} {full_n:>4} {full_correct:>8} {full_correct / full_n:>9.1%} "
              f"{f'[{full_lo:.1%}, {full_hi:.1%}]':>18}  (unchanged -- real system, not re-run)")
    else:
        print("(baselines_corrected_per_claim_20260814.json not found -- run baseline_corrected_per_claim.py first)")

    summary = {
        "table1_all_9_items": {
            "baseline_1_llm_only": {"n": len(b1), "correct": accuracy_and_ci(b1)[0]},
            "baseline_2_search_llm": {"n": len(b2), "correct": accuracy_and_ci(b2)[0]},
            "baseline_3_search_rag_llm": {"n": len(b3), "correct": accuracy_and_ci(b3)[0]},
            "full_truthlens_n6": {"n": full_tl_n, "correct": full_tl_k},
        },
        "table2_paired_6_items": {
            "baseline_1_llm_only": table2_paired["Baseline 1 (LLM-only)"],
            "baseline_2_search_llm": table2_paired["Baseline 2 (Search+LLM)"],
            "baseline_3_search_rag_llm": table2_paired["Baseline 3 (Search+RAG+LLM)"],
            "full_truthlens": {"n": full_n, "correct": full_correct},
        },
        "table2_paired_6_items_CORRECTED": {
            **table2_corrected,
            "full_truthlens": {"n": full_n, "correct": full_correct},
            "note": "Baselines re-run per real TruthLens-extracted claim, fixing AUDIT_REPORT.md Finding 1. This table, not table2_paired_6_items above, is the one main.tex cites as the primary headline comparison.",
        },
        "table3_claim_decomposition": {
            "single_claim_accuracy": f"{single_k}/{decomp_n}",
            "multi_claim_accuracy": f"{multi_k}/{decomp_n}",
        },
        "known_gaps": [
            "item-0003 never successfully ingested (persistent Instagram empty-media-response)",
            "items 0008/0009 full-TruthLens run blocked by real Gemini free-tier quota exhaustion during this Day 8 pass -- baselines 1-3 completed for these items (Ollama-only, no Gemini dependency), full TruthLens did not",
            "Full TruthLens n=6, not n=9 -- Table 2 restricts baselines to the same 6 items for a fair paired comparison; Table 1's baseline numbers are on the full 9-item set and are NOT directly comparable to the n=6 full-TruthLens row without that restriction",
        ],
    }
    (RESULTS_DIR / "day8_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote summary to {RESULTS_DIR / 'day8_summary.json'}", file=sys.stderr)


if __name__ == "__main__":
    main()
