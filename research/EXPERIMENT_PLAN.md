# TruthLens Experimental Plan — IEEE Submission Program

Status: **Day 1 draft.** Frozen baseline: git tag `truthlens-pre-ieee`
(HEAD `fdc31dc`). This document is the master plan every later day's work
must trace back to. It will be revised as experiments actually run — but
revisions must be logged (§8), never silently edited to match a
convenient result.

## 0. What "10 days" means here, honestly

This program is being executed by one AI agent (me) working with one
human (Aditya) across conversational sessions, not a research team
working independent 8-hour days. "Day N" below means a checkpointed
phase of work, not a calendar day with idle time in between. The actual
throughput bottleneck is **not effort, it's rate-limited infrastructure**:

- Gemini free tier: 20 requests/day, shared across every pipeline stage
  that escalates (`claim_extraction`, `content_generation`, `verdict`).
  Confirmed exhausted live on 2026-08-12 by ordinary development testing
  alone.
- Local transcription: ~60-100 seconds per reel on an 8GB M1 (faster-whisper).
- Instagram fetching: subject to the same ToS-sensitivity already flagged
  in `docs/SECURITY.md` for the existing opt-in auto-fetch feature —
  fetching at dataset-construction scale (15-30+ posts) must stay
  well within what a single manual researcher would plausibly do, not
  look like scraping infrastructure.
- Every claim in the eventual dataset that reaches `verifiable=true`
  triggers 2-5 search queries × full-page fetch × evidence-analysis LLM
  call × verdict LLM call, for **each** of 5 system configurations
  (4 baselines + full TruthLens) planned in Day 3/8. At even a
  conservative 20 verifiable claims, that is up to 500 LLM calls for a
  single metric table, run serially against local Ollama at ~10-30s/call
  plus real web-fetch latency. This is realistically hours of wall-clock
  runtime per full experimental pass, not minutes.

None of this is a reason to skip the work. It is a reason the dataset
size, baseline count, and schedule below are **deliberately smaller than
the original ask**, with the reduction stated and justified rather than
hidden, per Rule 12 of the governing instructions ("if a feature cannot
be rigorously evaluated within 10 days, move it to future work instead
of forcing weak experiments into the main contribution").

## 1. Central research question (unchanged from the brief)

> Can a verification-gated, evidence-grounded architecture reduce
> unsupported fact-checking outputs while preserving or improving
> factual correctness in short-form political media?

## 2. Research questions → experiments (this is the binding contract)

| RQ | Question | Experiment | Day | Feasible at full scope? |
|---|---|---|---|---|
| RQ1 | Does deterministic verification reduce unsupported/ungrounded outputs? | Validator audit: human-labeled TP/FP/TN/FN on a sample of verdict-generation events, WITH vs WITHOUT validation | 5 | **Yes**, at reduced sample size (§7) |
| RQ2 | Does multi-stage decomposition + retrieval beat single-shot search+LLM? | Baselines 1-4 vs full system on held-out dataset | 3, 8 | **Yes**, at reduced dataset size (§7) |
| RQ3 | Does multimodal extraction improve coverage of non-text misinformation? | Text-only vs +OCR vs +OCR+vision claim coverage, using the two existing Tier-1 visual-misinformation items plus new ones | 4 | **Partially** — see §7, this is the single hardest RQ to scale |
| RQ4 | Does source-tiering/primary-source retrieval improve evidence quality? | Before/after domain-restriction comparison (already has real Day-0 data, see `research_paper/main.tex` §V-F); extend with human evidence-quality labels | 6 | **Yes**, building on already-collected data |
| RQ5 | Can the system maintain comparable standards across political actors? | Matched claim-pair comparison | 7 | **Small-sample only** — reported as such, not as a bias-free claim |
| RQ6 | Does confidence correlate with correctness? | Reliability diagram / ECE against held-out labels, IF sample size supports it | 7 | **Conditional** — see §7; will be removed from the paper's claims if not, per the brief's own instruction |

No RQ7+ is introduced. If an experiment under one of these six cannot be
completed at a scientifically meaningful sample size, the result is
reported as "attempted at n=X, underpowered, directional only" — never
silently omitted and never dressed up as more than it is.

## 3. Independent and dependent variables

**Independent variables (what we manipulate):**
- System configuration: {LLM-only, Search+LLM, Search+RAG+LLM,
  TruthLens-minus-validation, Full TruthLens} — see `BASELINE_SPEC.md`.
- Input modality: {text-only, text+OCR, text+OCR+vision}.
- Source-retrieval mode: {unrestricted, domain-restricted (tier1_primary)}.
- Political actor / claim pairing (for RQ5).

**Dependent variables (what we measure):** defined precisely, with exact
formulas and DB provenance, in `METRICS.md`. Summary list: verdict
accuracy/macro-F1, claim coverage, visual/provenance claim recall,
validator precision/recall/F1, unsupported-output rate, evidence
precision/recall, citation correctness, primary-source retrieval rate
(4-way denominator, per the brief's explicit instruction), source
diversity, calibration (ECE, Brier — conditional), latency, LLM call
count, escalation rate, estimated cost.

## 4. Baselines (full spec in `BASELINE_SPEC.md`)

1. **LLM-only**: claim text → Ollama `llama3.2` (same model TruthLens
   uses by default) → verdict. No search, no pipeline. This baseline
   **already exists** as `research_paper/benchmark/run_naive_baseline.py`
   — it will be reused, not rebuilt, and extended to the new held-out set.
2. **Search+LLM**: claim → one DuckDuckGo search (same
   `DuckDuckGoSearchProvider` TruthLens itself uses — holding search
   access constant, per the brief's explicit instruction not to let a
   baseline's weaker infrastructure masquerade as an architectural
   finding) → raw top-N snippets → single LLM call → verdict. **New
   code, to be written Day 3.**
3. **Search+RAG+LLM**: claim → search → fetch full page text for each
   result (reusing `search_fetch.py`'s own fetch logic so page-retrieval
   quality is held constant) → concatenated passages → single LLM call
   → verdict. **New code, Day 3.**
4. **TruthLens-minus-validation**: the real pipeline, unmodified, except
   `validate_verdict()`'s result is recorded but never applied — the raw
   LLM verdict is what gets scored. Implemented as a config flag, not a
   code fork, so this baseline can never drift from the real system.
   **New code, Day 3, small.**
5. **Full TruthLens**: the system as it exists at the `truthlens-pre-ieee`
   tag, unmodified.

All five run against the same underlying model (`llama3.2` via Ollama)
and, where applicable, the same search provider — isolating
architecture from model/vendor quality, per the brief's explicit
warning against comparing "cheap model vs. expensive model" and
attributing the gap to architecture.

## 5. Ablations

Baseline 4 above (TruthLens-minus-validation) is itself the primary
ablation for RQ1. Two more, scoped to what's cheaply and honestly
answerable from data the system already produces or can produce without
new infrastructure:
- **Source-tier ablation**: domain-restricted vs. unrestricted retrieval
  — this already has real before/after data (`research_paper/main.tex`
  §V-F); Day 6 extends it with human evidence-quality labels rather than
  re-running it from scratch.
- **Claim-decomposition ablation**: single-claim-per-reel (only the
  primary/highest-importance claim researched) vs. full multi-claim
  decomposition, measuring whether decomposition changes claim coverage
  and overall-verdict correctness. **New, small, Day 3/8.**

The multimodal ablation (text-only / +OCR / +OCR+vision) is listed
separately under RQ3/Day 4 since it is a claim-coverage experiment, not
a verdict-accuracy ablation — conflating the two is exactly the mistake
Rule 5 warns against ("a system can have a correct verdict while
checking the wrong claim").

## 6. Datasets

Full spec in `DATASET_SPEC.md`. Summary: this program does **not** start
from zero — `research_paper/benchmark/` already contains a real,
disjoint-from-development, Tier-1 (professionally-fact-checked ground
truth) mini-corpus of 2 items, built under a documented protocol
(`benchmark/PROTOCOL.md`) that already anticipated most of this plan's
concerns (independent ground truth over self-graded labels, disjointness
from development data, target size of 15-20 reels justified by the
project's real fetch-rate constraints). `DATASET_SPEC.md` formalizes and
extends this existing protocol to the new `items.jsonl` schema and
broader claim-type diversity requirements, rather than replacing it.

## 7. Honest scope reductions, stated up front

Per Rule 12 and the brief's own "do NOT pretend 50 is equivalent to 100"
instruction, here is every place this plan deliberately targets less
than the brief's stated ideal, and why:

1. **Dataset size target: 20-30 items, not 50-100.** Justification:
   `benchmark/PROTOCOL.md` already found, empirically, that scaling past
   the original 2 Tier-1 items has an approximately 8% hit rate (2 of 26
   BOOM Live/Alt News articles checked had a usable live Instagram
   embed) — meaning even reaching 20-30 well-sourced items requires
   checking on the order of 250-375 professional fact-check articles, a
   real, bounded, but non-trivial manual research task. 50 is possible
   only by relaxing the Tier-1 sourcing standard (accepting
   independently-labeled-by-Aditya-alone items for the majority), which
   the brief itself treats as a lesser tier. This plan uses **both
   tiers explicitly and reports the split**, targeting Tier-1 wherever
   findable and Tier-2 (single-annotator, disclosed as such) to reach
   the 20-30 total.
2. **Single primary human annotator (Aditya), not 2-3 independent
   annotators.** No inter-annotator agreement statistic (Cohen's/Fleiss'
   kappa) will be computed and reported as if it were real unless a
   second independent annotator actually participates. If that doesn't
   happen, `GROUND_TRUTH.md` will say exactly this — "single-annotator
   ground truth, no IAA computed" — rather than fabricate or omit the
   limitation. Tier-1 items' ground truth (the professional
   fact-checking org's own published verdict) is not authored by any
   annotator in this project at all, which is its whole methodological
   value.
3. **RQ3 (multimodal claim coverage) is the hardest to scale honestly.**
   The two existing Tier-1 items include exactly one genuine
   visual-misinformation case (bm-0002, already documented as a
   *coincidental* correct-label/wrong-claim-coverage result — see
   `benchmark/results.md`). A statistically meaningful visual-claim-recall
   number needs more cases like it than this project can source in 10
   days at the established ~8% hit rate for this specific failure
   pattern. **This experiment will report exact counts on whatever n is
   actually reached, explicitly flagged as directional, not a
   generalizable recall percentage** — consistent with the brief's Rule
   1 ("if it fails, say it failed") applied to statistical power, not
   just to pass/fail results.
4. **RQ5 (bias) and RQ6 (calibration) are explicitly conditional.**
   Matched political-claim pairs and a calibration curve both need
   enough labeled items with known-correct verdicts to say anything.
   Given (1) and (2) above, this plan does not promise a specific number
   of matched pairs or a computed ECE — it promises an honest attempt,
   with the brief's own fallback rule applied literally: if calibration
   can't be meaningfully evaluated, numerical confidence claims are
   removed from the paper, not kept with a fabricated number attached.
5. **Statistical significance testing will use exact counts and
   confidence intervals, not p-values, at the dataset sizes above.**
   A 20-30 item dataset split across 5 system configurations and
   multiple claim subgroups does not support classical significance
   testing with any real power. Reporting a p-value here would be the
   exact "mechanical," misleading use of statistics the brief warns
   against. Wilson/Clopper-Pearson confidence intervals on proportions
   will be used instead, and reported as what they are: a description of
   uncertainty at this sample size, not a claim of significance.

## 8. Revision log

Any change to this document after Day 1 must be appended here with a
date and reason — never a silent edit.

- 2026-08-13: Initial version (Day 1).

## 9. Statistical tests to be used, and why

- **Wilson score interval** for all proportion metrics (accuracy,
  recall, precision, retrieval rates) — appropriate at small n, does not
  assume normality, does not produce nonsensical bounds outside [0,1]
  the way a naive normal-approximation interval can at small n.
- **McNemar's test** for paired accuracy comparisons between two system
  configurations evaluated on the *same* dataset items (appropriate
  because every configuration will be run on the identical item set —
  this is a paired design, not independent samples).
- **Exact binomial test** where a single proportion is compared against
  a fixed reference value (e.g., "is the validator's downgrade rate
  different from what would be expected by chance").
- Explicitly **not used**: independent-samples t-tests or chi-square
  tests that assume a sample size this program will not reach; any test
  presented without also reporting the raw counts it was computed from.

## 10. What "done" looks like for Day 1

- [x] Codebase, schema, prompts, validation, retrieval, tests inspected
      and verified against actual current files (not memory).
- [x] Current TruthLens output reproduced (142/142 tests).
- [x] Known failure cases from the manuscript cross-checked against
      current code (validated in `docs/SYSTEM_AUDIT.md` §5).
- [x] Fabrication/data-loss/silent-failure risk points identified,
      including two not previously documented anywhere (§5.2, §5.3 of
      `docs/SYSTEM_AUDIT.md`).
- [x] `git tag truthlens-pre-ieee` created.
- [x] This experiment plan, with explicit IVs/DVs/baselines/ablations/
      datasets/metrics/statistical tests/expected-output structure and
      honestly-justified scope reductions.
- [ ] Architecture diagram (figure) — deferred to Day 10's figure batch
      per the brief's own figure-production schedule, since it depends
      on the finalized architecture description, not Day 1's audit.
