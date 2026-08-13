# CLAIM_EVIDENCE_MATRIX.md — Phase 25

Status: 2026-08-14. Every empirical claim sentence in `main.tex` that
asserts a number, a direction, or a comparison is mapped below to its
exact experiment, raw artifact, sample size, statistical treatment, and
status. A claim with no row here, if found, should be treated as a gap to
close (weaken the wording, add evidence, or remove it), not an oversight
to ignore.

| # | Claim (as stated in the paper) | Experiment | Raw artifact | $n$ | Statistical treatment | Status |
|---|---|---|---|---|---|---|
| 1 | Full TruthLens (33.3%, 2/6) beats Baseline 1 (0.0%) and Baseline 3 (0.0%) outright, trails Baseline 2 (50.0%) by 16.7 points | Corrected paired comparison, Section VII | `baselines_corrected_per_claim_20260814.json`, `full_truthlens_reel_level_day8_v2_with_new_checks.json` | 6 | Wilson 95% CI per cell; exact McNemar (TruthLens vs.\ B2: 1 discordant pair, $p=1.0$) | **Supported** |
| 2 | The original (superseded) comparison showed Baseline 2 at 66.7%, Baseline 3 at 50.0%, both ahead of TruthLens | Original paired comparison, Section VII (retained for record) | `baseline_search_llm_20260813T090758Z.jsonl`, `baseline_search_rag_llm_20260813T091225Z.jsonl` | 6 | Wilson 95% CI | **Supported, explicitly superseded** |
| 3 | The baseline claim-input confound (Finding 1) existed in every baseline run since Day 3 | Source-code audit | `backend/research/baselines/common.py` (git history: `aa656bb`, never modified since), `AUDIT_REPORT.md` | n/a (code artifact, not a sample) | n/a | **Supported** (direct code inspection, not inferred) |
| 4 | Validator recall improved 16.7%→40%, 100% precision both times, $n=9$ | Validator audit, before/after two general fixes | `validator_audit_20260813T073200Z.json`, `validator_results.csv` (single-reviewer draft judgment) | 9 | Wilson 95% CI on precision/recall | **Directional** — single, unadjudicated annotator; new check's phrase list calibrated on the same 9 cases (disclosed circularity) |
| 5 | Reel-level accuracy unchanged (2/6) despite validator recall improvement, both before and after the baseline correction | Cross-reference of #1 and #4 | Same as #1, #4 | 6 / 9 | n/a (a comparison of two independently-computed numbers, not a joint test) | **Supported** |
| 6 | Claim-decomposition counterfactual: 50.0% (multi-claim) vs.\ 25.0% (single-claim), $n=4$ | Counterfactual reanalysis of real per-claim verdict data | `claim_decomposition_ablation.json` (no generator script — hand-constructed, disclosed) | 4 | None (too small for a CI to be informative; raw counts only) | **Directional**, explicitly relabeled from "ablation" to "counterfactual" (Phase 8) |
| 7 | Four-way evidence metric: tier-classification 23.5% (16/68), relevance 68.75% (11/16), fetch-success 16/16 (by construction), usable-evidence 18.75% (3/16) | Evidence-quality audit | `research/evidence_results.csv`, `EVIDENCE_EVALUATION.md` | 68 sources / 9 claims | Wilson 95% CI on metric 1 | **Directional** — single-reviewer draft relevance judgment (metric 2); this snapshot no longer matches the live DB (207 evidence rows now), disclosed as Finding 2, not re-derived this pass |
| 8 | Source-tier domain-restriction fix: $\sim$11% (8/72) baseline $\to$ 95% (19/20) after fix | Before/after domain-restricted-query experiment | Pre-existing `main.tex` §"Closing the primary-source gap" real query logs | 72 baseline / 20 corrected | Percentages only, both from real counts | **Supported**, distinct sample from #7 (disclosed as such) |
| 9 | Multimodal claim coverage: text\_only 16.7% (1/6), text\_ocr 0.0% (0/6), text\_ocr\_vision 33.3% (2/6) | Real ingestion + 3-condition claim extraction | `claim_coverage_results.csv`, `multimodal_claim_extraction_20260812T211658Z.json` | 6 | Wilson 95% CI | **Directional** — single, non-repeated call per condition; draft ground truth |
| 10 | 47.1% (32/68) of real evidence rows had an empty explanation field before the fix | Evidence-analysis substantiveness audit | Direct count against Day 5 evidence rows, `EVIDENCE_EVALUATION.md` | 68 | Percentage from exact count | **Supported** (the specific bug and fix are also unit-tested, `test_evidence_analysis_substantive.py`) |
| 11 | Cross-post attribution problem: 4 of 6 scoreable items have their false claim living outside the specific post's own content | Manual review of real ingested content vs.\ ground-truth claim | `MULTIMODAL_EVALUATION.md`, item-level notes | 6 | None (exact count, exhaustively reviewed at this $n$) | **Supported** |
| 12 | The 8-dimension source-tier rubric's weights are hand-set and were never tuned against evaluation data | Git history audit | `backend/app/pipeline/source_scoring.py` commit history (`fb8ae64`, `cf0539e`, `6671d75` — `_WEIGHTS` dict byte-identical across all three) | n/a | n/a | **Supported** (direct git diff inspection) |
| 13 | Error budget: transcription accounts for 2/4 item-level errors; evidence interpretation accounts for 2/5 claim-level false negatives | Earliest-causal-failure tracing | `ERROR_BUDGET.md`, built from #1's item list + #4's claim-level detail | 4 items / 5 claims | None (exact counts at this $n$) | **Directional**, explicitly small-$n$ |
| 14 | RQ5 (bias) is deferred — no matched political-actor pairs exist in the 9-item dataset | Direct inspection of `items.jsonl`'s `political_actor` field | `items.jsonl` (BJP $\times$3, six other actors $\times$1 each, no topic-matched pair) | 9 | n/a | **Supported** (a non-result, correctly reported as such) |
| 15 | RQ6 (calibration) is deferred — 9 confidence values cannot meet the pre-registered "no bin under 3 items" gate | Direct inspection of real confidence values | `validator_audit_20260813T073200Z.json` (values: 0.0, 0.0, 0.1, 0.1, 0.2, 0.2, 0.2, 0.7, 0.8) | 9 | n/a (gate not met, no ECE/Brier computed) | **Supported** (a non-result, correctly reported as such) |
| 16 | Efficiency: Baselines 2/3 make 1 LLM call per claim; full TruthLens makes $\sim$9.6 | Real call-count measurement | `system_efficiency.csv` | 7 (baselines) / 9 (TruthLens, derived from avg.\ 7.56 sources/claim) | None (means only, small $n$) | **Directional** — latency not captured for full TruthLens (disclosed gap) |
| 17 | Full test suite passes (161/161) | `pytest` run | `backend/tests/` | 161 tests | n/a | **Supported**, reverified 2026-08-13 |

## Claims with no dedicated row (by design, not omission)

Purely architectural/descriptive statements (e.g., "TruthLens builds one
fact-check per reel," "the pipeline runs in nine stages") are not
empirical claims requiring a sample size — they describe what the code
does, verifiable by reading the code itself, not by an experiment. These
are excluded from this matrix deliberately, consistent with its purpose:
tracking claims that could be wrong in the way an experiment can be
wrong, not claims that could only be wrong in the way a bug can be wrong.

## What this matrix would flag as a problem, and currently does not

No claim in `main.tex` as of this commit lacks a row above with a
"Directional" or "Supported" status; none is asserted at a "Significant"
or "generalizable" strength the underlying $n$ does not support. This
was verified by re-reading every empirical sentence in Sections
III–XIV against this table while building it, not assumed.
