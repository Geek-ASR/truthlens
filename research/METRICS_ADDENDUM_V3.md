# METRICS ADDENDUM V3

**Pre-registered before the claim-extraction v2 freeze (EXPERIMENT_PROTOCOL_V3).**
Each definition is generic and was chosen before any V3 result existed. This
addendum does not alter any formula already in `METRICS.md`; it adds definitions
the current draft and `score_local_eval.py` already use informally, fixes one
mislabel, and specifies the V3 baseline conditions.

Dated with this commit's git SHA. Tag: `experiment-protocol-v3-frozen`.

---

### A1. Balanced accuracy (was used, never defined)

`score_local_eval.py` computes it and the paper leads with it, but `METRICS.md`
§1 does not define it. **Definition:** unweighted mean of per-ground-truth-bucket
recall over the buckets with ≥ 1 item in the denominator. Buckets =
{FALSE, MISLEADING, TRUE} (bucketing per `METRICS.md` §1). Reported on **both**
denominators:

- **resolved balanced accuracy** — recall computed over resolved items only.
- **corpus balanced accuracy** — recall computed over all 193 attempted items
  (`no_verifiable_claims`, `research_failed`, and `UNVERIFIED` all count as
  incorrect for the bucket they belong to).

CI: item-level bootstrap, B = 10,000, deterministic index schedule (no RNG).
Majority-class reference = `1/k` (= 33.3% for k = 3). C0 values: resolved 22.2%,
corpus 12.3%.

### A2. Corpus-level bucketed accuracy (distinct from the resolved-denominator one)

`METRICS.md` §1 defines accuracy only over `outcome_type == "resolved"`. Add, as a
distinct §1 entry: **corpus bucketed accuracy** = `correct / attempted`, where
`no_verifiable_claims`, `research_failed`, and any `UNVERIFIED` output all count
as incorrect. This is the **denominator-stable cross-config adjudication metric**
— resolved-only accuracy is confounded by *which* items each config resolves.
C0 value: 20/193 = 10.4%. Both accuracies are always reported together.

### A3. False-abstention rate — mislabel fix + new non-response metric

`score_local_eval.py` computed `(UNVERIFIED-resolved + no_verifiable_claims) /
193 = 155/193 = 80.3%` and printed it under the name **"false-abstention rate"**.
`METRICS.md` §1 defines that term strictly as `# UNVERIFIED outputs where GT is
confidently resolvable (Tier-1) / # Tier-1 items`. All 193 v2 items are Tier-1
(§A12), so:

- **False-abstention rate (METRICS.md strict)** = `UNVERIFIED outputs / 193` =
  **29/193 = 15.0%** for C0.
- **Declined-to-answer / non-response rate** *(new)* =
  `(UNVERIFIED-resolved + no_verifiable_claims + research_failed) / attempted` =
  **155/193 = 80.3%** for C0 — "the system produced no committed verdict, for any
  reason".

Both are reported, under these names, in the scorer, the report, Table VI, and
every place the paper discussed "false abstention". The relabel is applied to the
shipped draft in this commit (Table VI).

### A4. Macro-F1 scope

`METRICS.md` §1 says "over the full VerdictLabel set"; `score_local_eval.py`
averages over classes with non-zero GT support (3 classes → 0.194). **Amended
wording:** macro-F1 is the unweighted mean of per-class F1 over classes with
**non-zero ground-truth support OR non-zero predictions**. For transparency the
full-8-class value (dividing by 8) is also printed once, flagged as
uninformative at this n.

### A5. Verdict resolution rate & no-checkable-claim rate

Named throughout the draft, never given a §1 formula. Add:
- **Verdict resolution rate (coverage)** = `resolved / attempted`. C0 = 34.7%.
- **No-checkable-claim rate** = `no_verifiable_claims / attempted`. C0 = 65.3%.

Both with Wilson 95% CI.

### A6. Baseline extraction-source condition (V3)

`BASELINE_SPEC.md` / `METRICS.md` say baselines run "on the claim as already
extracted by TruthLens's own claim-extraction stage" but do not pin the
procedure. **Pinned (per `RECONSTRUCTED_RESULTS.md` §1.2, now applied at n=193):**
one baseline LLM verdict call **per verifiable extracted claim**, per-claim labels
aggregated to one reel-level label by the real
`app.pipeline.overall_verdict.derive_overall_verdict`, inheriting the extraction
source's `no_verifiable_claims` / `research_failed` outcomes. **Extraction
source** is a named variable:
- `C1-3B-v5` — the frozen 3B + v5 + filter run.
- `C3-8B-v5` — the frozen 8B-extraction + v5 + filter run (the **SHARED**
  condition claim source; the headline).
- `oracle-GT` — the reviewer's `ground_truth_claim` (the **ORACLE** condition).

Verdict LLM call for all V3 baselines: 3B (matches C3 downstream). Search: the
shared V3 cache. Compared **within model only**.

### A7. ORACLE reference row = labeled non-comparable

The ORACLE condition (every config fed `ground_truth_claim`) is pre-registered as
a **labeled upper-bound reference**, ruled off below the primary table body,
reporting corpus + resolved bucketed accuracy only. It is "the value of perfect
claim extraction", never a system result, never the headline comparison.

### A8. Claim-extraction stage instrumentation (descriptive, §2)

Per config: mean & median total claims/item; mean & median verifiable
claims/item; % items with ≥ 1 extracted claim (Wilson CI); % items with ≥ 1
verifiable claim (Wilson CI); empty-claim-text rate = extracted claims with
blank/whitespace text / all extracted claims (Wilson CI); deterministic
post-filter removal counts per rule (F1 triviality / F2 recitation / F3a
debunk-framing / F5 incidental) and % items affected;
`n_verifiable_pre_filter` vs `n_verifiable_post_filter`.

### A9. `is_visual_claim` handling

`items_v2.jsonl` has no `is_visual_claim` tag, so `METRICS.md` §2 Visual Claim
Recall is uncomputable. **Pre-registered:** the second-pass annotation adds
`is_visual_claim` / `is_provenance_claim` per item (preferred); failing that,
Visual Claim Recall is formally marked "not computed for TruthLens-202, tag
absent" and **Provenance Claim Recall** (`claim_type == "provenance"`, already
present, 156 items) is the reported proxy.

### A10. Support-validity sampling protocol (extends §3)

When the verifiable-claim verdict census exceeds the human-adjudication budget,
Validator Precision / Recall are estimated on a **pre-registered stratified
sample** (strata = predicted-label-bucket × deterministic-validator-decision
{downgraded, passed}), IDs frozen before annotation, annotator **blind to
`validation_status`**. Target n = 60; if the run yields < 60 verifiable-claim
verdicts, take the full census and report that n. Deterministic
grounding-constraint-violation (downgrade) rates are still reported at **full
census**, per check, for C1 and C3, recomputed identically from the frozen C0
artifact for comparison. The prior dev-split point (recall 16.7% → 40%,
precision 100%, n = 9) is **cited, not recomputed or pooled**.

### A11. Constant-predictor references

Always-FALSE, always-MISLEADING, always-TRUE, always-UNVERIFIED reported on
**both** denominators (193-corpus and each resolved subset). Always-UNVERIFIED
scores 0 by the "UNVERIFIED never matches" rule — stated explicitly, not omitted.
Always-FALSE: corpus bucketed 82.9%, corpus balanced 33.3%.

### A12. `ground_truth_tier` backfill

Every V2 validation item traces to a professional fact-check with a recorded
verbatim anchor quote, which is the Tier-1 definition (`METRICS.md` /
`DATASET_SPEC.md`). `ground_truth_tier` was `null` on all 193; it is backfilled to
`1` on all 193 in this commit, with `_tier_backfill_note` on each row. This makes
explicit what `score_local_eval.py` already assumed. Any tier-denominated metric
(false-abstention rate) now has a real denominator.

---

## Statistical reporting (unchanged from METRICS.md §8, restated for V3)

Every proportion as `k/n (%, Wilson 95% CI)`. Balanced-accuracy figures with
bootstrap 95% CI (B = 10,000, deterministic schedule). Paired system-vs-baseline
comparisons: McNemar exact with the raw 2×2 contingency table shown, over the
shared resolved item set, plus the strict-domination check (count of discordant
pairs favoring each side). Second-pass agreement: PABAK / Gwet's AC1 as headline
(kappa paradox under 83% FALSE), Cohen's κ + raw % agreement + confusion matrix
alongside.
