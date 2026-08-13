# Metrics Definitions

Every metric used anywhere in the paper must resolve to an entry in this
document: exact formula, exact data source, exact denominator. "Where
did this number come from" (the Day 10 audit question) must always be
answerable by pointing here plus a raw-data file.

## Raw result row schema

Every experiment (baseline run, ablation run, full-system run) writes
one row per (dataset item, system configuration) to a `.jsonl` file
under `research/results/`:

```json
{
  "item_id": "item-0001",
  "config": "full_truthlens",
  "predicted_label": "MOSTLY_FALSE",
  "ground_truth_label": "FALSE",
  "ground_truth_tier": 1,
  "claim_ids_extracted": ["uuid1", "uuid2"],
  "claim_texts_extracted": ["...", "..."],
  "outcome_type": "resolved",
  "confidence": 0.72,
  "validation_status": "passed",
  "cited_source_urls": ["https://..."],
  "n_llm_calls": 6,
  "n_search_queries": 3,
  "n_escalations": 1,
  "input_tokens": 4200,
  "output_tokens": 890,
  "latency_seconds": 47.3,
  "estimated_cost_usd": 0.0,
  "run_timestamp": "2026-08-18T10:00:00Z",
  "code_version": "git-sha-or-tag"
}
```

`outcome_type` ∈ {resolved, research_failed, no_verifiable_claims,
error}. **`research_failed` is never collapsed into `resolved`** —
per Rule 7, an infrastructure failure is not a verdict and must not
enter accuracy/F1 denominators as if it were a wrong (or right) answer.
It is reported as its own rate.

## 1. Verdict-level metrics (RQ2)

- **Accuracy** = (# items where `predicted_label`'s bucket matches
  `ground_truth_label`'s bucket) / (# items with `outcome_type ==
  "resolved"`). Bucketing: TRUE/MOSTLY_TRUE → `TRUE`-adjacent;
  FALSE/MOSTLY_FALSE → `FALSE`-adjacent; MISLEADING/MISSING_CONTEXT/
  OUTDATED → their own bucket; UNVERIFIED is **never** counted as a
  match to any ground-truth label, including a ground-truth
  `UNVERIFIABLE` — see the naive-baseline result already on record where
  this exact question came up.
- **Macro-F1** over the full `VerdictLabel` set, unweighted by class
  frequency (appropriate given the small, non-stratified sample — a
  micro-averaged number would be dominated by whichever label happens to
  be most common in a 20-30 item set, which is not informative here).
- **Per-class F1**, reported alongside macro-F1, not instead of it.
- **Abstention rate** = (# `UNVERIFIED` outputs) / (# resolved items).
- **False abstention rate** = (# `UNVERIFIED` outputs where ground truth
  was confidently resolvable, i.e. Tier-1) / (# Tier-1 items). This is
  the metric that would catch a system that abstains its way to a
  flattering-looking low error rate.
- **Research-failed rate** = (# `outcome_type == "research_failed"`) /
  (# items attempted). Reported separately per RQ2 configuration — a
  baseline with weaker search infrastructure should show this
  distinctly, not have it silently folded into its accuracy denominator.

## 2. Claim coverage metrics (RQ3) — distinct from verdict accuracy

Defined precisely per Rule 5: a correct overall verdict reached by
checking the wrong claim is a **claim coverage failure**, scored as
such, never presented as a successful fact-check.

- **Claim Recall** = (# ground-truth checkworthy claims that have at
  least one extracted claim covering the same specific assertion, by
  human judgment during annotation) / (# ground-truth checkworthy claims).
- **Claim Precision** = (# extracted claims that correspond to a real
  ground-truth checkworthy claim) / (# extracted claims total).
- **Claim Coverage** (the brief's own named metric) = identical formula
  to Claim Recall, kept as a separate named entry because the brief
  names it explicitly and a reader should be able to find it by that
  name.
- **Visual Claim Recall** = Claim Recall restricted to ground-truth
  claims tagged `is_visual_claim: true` in `items.jsonl`.
- **Provenance Claim Recall** = Claim Recall restricted to
  `is_provenance_claim: true`.
- Measured separately for each of the four input-modality configurations
  in `EXPERIMENT_PLAN.md` §5/RQ3 (text-only / +OCR / +OCR+vision / full).

**Human judgment procedure for "covers the same specific assertion"**:
an extracted claim covers a ground-truth claim if a human annotator,
blind to which pipeline configuration produced it, agrees they assert
the same checkable fact — not merely overlapping topic. This is
necessarily a human call (matching two pieces of free text is not
reducible to string similarity without producing nonsense on
paraphrase), recorded per-pair in `research/claim_coverage_results.csv`
(the plan's originally-named path, `research/annotations/claim_coverage_labels.csv`,
was never created — this is the actual file, corrected here 2026-08-14
after `main.tex` cited the nonexistent path during a terminology pass).

## 3. Validator metrics (RQ1, Day 5)

Ground truth here is a **human** judgment of whether a given
verdict-generation event's output was actually unsupported/hallucinated,
independent of what the deterministic validator decided. Confusion
matrix:

| | Validator says downgrade | Validator says pass |
|---|---|---|
| Human says actually unsupported | TP | FN |
| Human says actually supported | FP | TN |

- **Validator Precision** = TP / (TP + FP)
- **Validator Recall** = TP / (TP + FN)
- **Validator F1** = harmonic mean of the two
- **Unsupported Output Rate WITHOUT validation** = (# human-judged
  unsupported outputs among Baseline-4 — i.e. TruthLens-minus-validation
  — outputs) / (# Baseline-4 outputs)
- **Unsupported Output Rate WITH validation** = same, computed over
  outputs that *passed* validation in the full system (i.e., what
  actually got published) — this is the number that matters for the
  paper's central claim, since it measures what a reader would actually
  see, not what the raw model produced before the gate.
- Per Rule 8: none of the above is called a "hallucination rate" unless
  the human annotation guideline (`ANNOTATION_GUIDELINES.md`) explicitly
  defines and applies that term. Default terminology: **"grounding
  -constraint violation rate"** for the deterministic validator's own
  downgrade rate (a description of what the code checked, always
  accurate by construction), and **"unsupported generation rate"** for
  the human-judged quantity above (a description of what a human
  concluded, only accurate insofar as the human judgment is trusted).

## 4. Evidence quality metrics (RQ4, Day 6)

Per the brief's explicit instruction, primary-source retrieval is
**four separate metrics**, never collapsed into one headline number:

1. **Source-tier classification rate**: % of retrieved sources
   classified `primary_government`/`primary_legal`/`primary_data` by
   `classify_source_tier()`. (This is what the existing paper's "95%"
   figure in §V-F actually measures — restated here with its correct,
   narrow name.)
2. **Relevant primary source rate**: % of tier-classified-primary
   sources that a human annotator judges topically relevant to the
   specific claim (catches the already-documented "Karni Sena" false
   -positive-relevance case — correct domain, wrong topic).
3. **Primary source fetch-success rate**: % of tier-classified-primary
   sources where `full_text_storage_key` corresponds to real, non-empty
   fetched content, not a 403/SSL-failure fallback to a short search
   snippet (already known to be a real gap for `.gov.in` domains
   specifically, per `main.tex` §V-F/§VII).
4. **Usable evidence extraction rate**: % of successfully-fetched
   primary sources where `evidence_analysis.py`'s stance classification
   is anything other than `irrelevant` — i.e., the source didn't just
   get fetched, it actually contributed to the evidence matrix.

Additional evidence metrics:
- **Evidence Precision** = (# `Evidence` rows human-judged as a correct
  stance classification) / (# `Evidence` rows total), sampled — see
  §5.3 of `docs/SYSTEM_AUDIT.md` for why this specific check is a real,
  previously-unmeasured gap.
- **Evidence Recall**: harder to define without a fixed universe of "all
  true evidence that exists" — operationalized as: for each ground-truth
  claim with a known Tier-1 correction/explanation, did the system
  retrieve *at least one* source that independently corroborates the
  same fact the professional fact-checker cited? Binary per item,
  reported as a rate with the small-n caveat attached.
- **Citation Correctness** = (# cited evidence IDs in a verdict's
  `cited_evidence_ids` that a human judges actually support the specific
  sentence citing them) / (# citations sampled).
- **Source Diversity** = distinct publisher domains / total sources, per
  claim, averaged.
- **Duplicate/republished-source rate** = % of sources sharing
  substantially identical text (simple normalized-text-overlap check)
  across different URLs for the same claim.

## 5. Bias metrics (RQ5, Day 7) — reported, not concluded

For matched claim pairs only (see `EXPERIMENT_PLAN.md` §7.4 on the
small-sample caveat): verdict-label distribution, error rate,
false-positive rate (system says FALSE when ground truth is TRUE-side),
false-negative rate (system says TRUE when ground truth is FALSE-side),
mean confidence, and mean evidence-quality score (§4 above), each
computed **per political-actor group** and reported side by side. No
single "bias score" is computed or reported — per Rule 9, this program
measures asymmetry, it does not certify its absence.

## 6. Calibration metrics (RQ6, Day 7) — conditional

- **Reliability diagram**: binned confidence vs. observed accuracy.
- **Expected Calibration Error (ECE)** = Σ (|bin|/N) × |accuracy(bin) −
  confidence(bin)|, standard equal-width binning, bin count chosen so no
  bin has fewer than 3 items at whatever n is actually reached — if that
  constraint can't be met (likely at n=20-30 split across bins), ECE is
  **not reported**, per the brief's own explicit fallback instruction,
  and the paper states plainly that confidence was not evaluated at a
  meaningful sample size rather than printing a number computed on 1-2
  items per bin.
- **Brier score**, computed only if the above sample-size gate is met.

## 7. Efficiency metrics (Day 7)

Average latency (wall-clock, seconds), LLM call count, escalation rate
(`n_escalations / n_llm_calls`), input+output tokens, web queries per
item, estimated cost in USD (Ollama calls = $0 by construction; Gemini
escalation calls priced at the actual per-token rate active on the day
of the run — recorded, not assumed). Compared across all 5
configurations from `BASELINE_SPEC.md`.

## 8. Statistical reporting convention

Every proportion metric above is reported as `k/n (percentage, 95%
Wilson CI [lower, upper])`, not a bare percentage. Paired comparisons
between two configurations on the same item set use McNemar's test and
report the exact contingency table alongside the p-value, per
`EXPERIMENT_PLAN.md` §9.
