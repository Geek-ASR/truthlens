# RECONSTRUCTED_RESULTS.md — Phase 1

Status: 2026-08-14. Every number below is recomputed directly from raw
artifacts in this pass — none is copied from `main.tex` or any prior
`.md` summary without independent recomputation. Where a prior published
number is confirmed unchanged, that is stated explicitly. Where it
changes, both the old and new numbers are shown, with the reason.

---

## 1. THE HEADLINE CORRECTION (supersedes the Day 9 paper's Table I/II)

### 1.1 What was wrong

`AUDIT_REPORT.md` Finding 1: `backend/research/baselines/common.py`
fed every baseline (1–3) `items.jsonl["claim_text"]` — a human-written
summary of the claim — instead of "the claim as already extracted by
TruthLens's own claim-extraction stage," as `BASELINE_SPEC.md` has
always specified. This has been true of every baseline run since Day 3.

### 1.2 The fix

`backend/research/baselines/baseline_corrected_per_claim.py`, run live
2026-08-14. For the 6 items with real, already-extracted TruthLens
claims available (the same 6 items the existing paired comparison
already uses — item-0003 has no extraction, ever; items 0008/0009 have
no *complete* real extraction, see §1.5), each baseline is now run once
per real extracted claim (sourced from
`research/results/validator_audit_20260813T073200Z.json`'s `claim_text`
+ the live `claims` table's `importance`, both real, both already
published elsewhere in this project — not freshly re-extracted, to avoid
new LLM non-determinism in a fix that doesn't need it), then the
per-claim baseline verdicts are aggregated with the exact same
`derive_overall_verdict()` function TruthLens itself uses. This holds
claim-extraction constant across every configuration for the first time
in this program.

Real claim counts used: item-0001 (4 claims), item-0002 (2), item-0004
(1), item-0005 (2), item-0006 (0 — genuine, real zero-verifiable-claims
outcome), item-0007 (0 — same). Raw output:
`research/results/baselines_corrected_per_claim_20260814.json`.

### 1.3 Item-by-item, both versions

| Item | GT | Full TruthLens | B1 old→corr | B2 old→corr | B3 old→corr |
|---|---|---|---|---|---|
| item-0001 | FALSE | MOSTLY_FALSE ✓ | UNVERIFIED✗ → MISLEADING✗ | MOSTLY_FALSE✓ → MOSTLY_FALSE✓ | MOSTLY_FALSE✓ → MISLEADING✗ |
| item-0002 | FALSE | MOSTLY_FALSE ✓ | MOSTLY_FALSE✓ → MOSTLY_TRUE✗ | MOSTLY_FALSE✓ → MOSTLY_FALSE✓ | MOSTLY_FALSE✓ → UNVERIFIED✗ |
| item-0004 | TRUE | FALSE ✗ | FALSE✗ → FALSE✗ | FALSE✗ → MOSTLY_TRUE✓ | FALSE✗ → MOSTLY_FALSE✗ |
| item-0005 | MISLEADING | UNVERIFIED ✗ | FALSE✗ → UNVERIFIED✗ | FALSE✗ → MOSTLY_FALSE✗ | FALSE✗ → MOSTLY_FALSE✗ |
| item-0006 | FALSE | UNVERIFIED ✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ |
| item-0007 | FALSE | UNVERIFIED ✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ | MOSTLY_FALSE✓ → UNVERIFIED✗ |

(✓/✗ = bucket match against ground truth, identical bucketing rule used
everywhere else in this project: TRUE/MOSTLY_TRUE→TRUE_ADJ,
FALSE/MOSTLY_FALSE→FALSE_ADJ, UNVERIFIED never a match, MISLEADING its
own bucket.)

Note the pattern in items 0006/0007: the *old* method let baselines
"win" both by being handed a clean claim summary to reason about even
though TruthLens's own real extraction found nothing checkworthy in
either post. The *corrected* method gives baselines the same
nothing-to-work-with input TruthLens actually had, and all three now
correctly abstain (UNVERIFIED) rather than guessing MOSTLY_FALSE — which
happened to match the ground-truth bucket before, for a reason that had
nothing to do with search or reasoning quality.

### 1.4 Paired accuracy, $n=6$, before and after

| Config | Old accuracy | Corrected accuracy |
|---|---|---|
| B1 (LLM-only) | 0/6 = 0.0% [0.0%, 39.0%] | 0/6 = 0.0% [0.0%, 39.0%] (unchanged) |
| B2 (Search+LLM) | 4/6 = 66.7% [30.0%, 90.3%] | **3/6 = 50.0% [18.8%, 81.2%]** |
| B3 (Search+RAG+LLM) | 3/6 = 50.0% [18.8%, 81.2%] | **0/6 = 0.0% [0.0%, 39.0%]** |
| Full TruthLens | 2/6 = 33.3% [9.7%, 70.0%] | 2/6 = 33.3% [9.7%, 70.0%] (not re-run; same real system, same real run) |

**Reversal: on the corrected, claim-input-controlled comparison, full
TruthLens (33.3%) now beats B1 (0.0%) and B3 (0.0%), and trails only B2
(50.0%) — by 16.7 points, not the 33.4-point gap the uncorrected
comparison showed against B2, and no longer trails B3 at all.**

McNemar (TruthLens vs. corrected B2, the only baseline still ahead):
both-correct=2 (item-0001, item-0002), both-wrong=3 (item-0005,
item-0006, item-0007), TruthLens-only-correct=0,
B2-only-correct=1 (item-0004). One discordant pair; exact McNemar
$p=1.0$. Still completely uninformative at this $n$ — reported for the
same reason the original underpowered test was: completeness, not
evidence.

### 1.5 What remains out of scope for this correction, and why

- **item-0003**: still excluded from everything (never ingested, no
  extraction possible under any method).
- **Items 0008/0009**: `AUDIT_REPORT.md`'s investigation into this
  found real `claims` rows exist for item-0008 (Bihar education
  -minister quote claim, 6 rows, `status IN ('extracted','researching')`)
  but **no row has `status='researched'`** — the real pipeline run for
  this item never completed a verdict either, consistent with the
  already-disclosed Gemini quota exhaustion. item-0009 has **zero**
  claim rows in the live database at all — extraction never ran for it.
  Neither item has a real, complete full-TruthLens verdict to compare
  against, so extending the corrected baseline method to either would
  produce a baseline-only number with nothing to pair it against. Both
  remain excluded from the paired comparison, exactly as before.
- **Table I** (each baseline's own "full $n=9$" run) is not corrected in
  this pass beyond the 6 items above — items 0003/0008/0009's rows in
  the original `baseline_*_20260813*.jsonl` files still use the old,
  flawed per-item claim-text method. Recommendation (applied in the
  paper update): retire Table I as a standalone headline table — it was
  already caveated as "not directly comparable" to TruthLens's own
  number before this fix, and that caveat is now compounded by the
  claim-input confound for 3 of its 9 rows. The corrected, paired,
  $n=6$ table is the only comparison this paper makes a claim from going
  forward.

---

## 2. Benchmark size and usable items

**[reconfirmed this pass]** 9 items total, `research/dataset/items.jsonl`
(direct file read). 7 FALSE / 1 TRUE / 1 MISLEADING. item-0003
permanently unusable (3 independent ingestion attempts across this
program, all failed identically). 6 items have a complete real
full-TruthLens run. 2 items (0008/0009) have incomplete or absent real
pipeline data (§1.5).

## 3. Validator confusion matrix, before and after (reconfirmed, unchanged from Day 8/10)

Source: `research/VALIDATOR_EVALUATION.md`, cross-checked this pass
against `research/results/validator_audit_20260813T073200Z.json`
directly (9 real verdict-generation events, item_ids 0001×4, 0002×2,
0004×1, 0005×2 — matches exactly).

| | Before (3 checks) | After (+ Check 4) |
|---|---|---|
| TP | 1 | 2 |
| FN | 5 | 3 |
| FP | 0 | 0 |
| TN | 3 | 4 (all no-op) |
| Precision | 1/1 = 100% | 2/2 = 100% |
| Recall | 1/6 = 16.7% | 2/5 = 40% |

No change from previously published — reconfirmed accurate, not
recomputed differently.

## 4. Claim-decomposition counterfactual (relabeled per Phase 8, §AUDIT_REPORT.md C)

Source: `research/results/claim_decomposition_ablation.json` (4 items,
no generator script — a hand-constructed reanalysis of real per-claim
verdict data, not a freshly-run paired experiment; each claim's own
verdict is real and independently computed regardless of decomposition
condition, so the *aggregation* comparison is valid, but this is not
evidence about whether *deciding to decompose* changes upstream
research behavior). Single-claim: 1/4 = 25.0%. Multi-claim: 2/4 = 50.0%.
Numbers unchanged from prior publication; only the methodological label
changes (Section VIII of the paper will be retitled "counterfactual
claim-selection analysis").

## 5. Evidence-quality four-way metric (reconfirmed as a historical snapshot; not live-requerying — see AUDIT_REPORT.md Finding 2)

$n=68$ sources / 9 claims, `research/EVIDENCE_EVALUATION.md`. Metric 1:
16/68=23.5%. Metric 2: 11/16=68.75%. Metric 3: 16/16 (by construction).
Metric 4: 3/16=18.75%. Confirmed these are unchanged from the published
figures; **not** re-derived from the live DB in this pass, because
(Finding 2) the live DB now holds 207 evidence rows spanning both
benchmark and non-benchmark reels with no committed scoping artifact to
correctly isolate the original 68-row sample. Building that scoping
artifact is a recommended, not-yet-completed, Phase 2 task.

## 6. Multimodal claim coverage (reconfirmed, unchanged)

$n=6$ (item-0003 excluded), `research/MULTIMODAL_EVALUATION.md`.
text_only 1/6=16.7%, text_ocr 0/6=0.0%, text_ocr_vision 2/6=33.3%.
Unchanged.

## 7. Source-tier domain-restriction fix (reconfirmed, unchanged, distinct sample from §5)

$n=20$ sources across 4 real queries that returned results (of 7
attempted). 19/20=95% primary-tier, against an $\sim$11% (8/72) baseline
measured before the fix. Unchanged.

## 8. Statistical treatment used throughout this document

Wilson 95% CI for every proportion (formula and constants identical to
`backend/research/day8_final_tables.py`'s `wilson_ci()`, re-implemented
independently in this pass and cross-checked to produce identical output
on the unchanged numbers in §3, §6, §7 — confirms no drift in the CI
computation itself). Exact McNemar test for the one paired comparison
that supports it (§1.4). No test is reported without its raw contingency
counts alongside it.
