# Bias, Calibration, and Efficiency Evaluation (Day 7)

## Political bias (RQ5): attempted, blocked by data availability, deferred honestly

`research/dataset/items.jsonl` currently has 7 items across 6 distinct
political actors/institutions (BJP ×2, Karni Sena, CJP, Delhi Police,
Congress, none) — **no genuine matched pairs exist** (same topic,
structure, evidence availability, and difficulty, varying only the
political actor named). BJP is the only actor with more than one item,
and those two items (item-0001's NEET-marks video, item-0003's
CJP-protest AI-fakes investigation, which could not even be ingested —
see `MULTIMODAL_EVALUATION.md`) are not remotely matched on topic or
claim type.

Per Rule 12 ("if a feature cannot be rigorously evaluated within 10 days,
move it to future work instead of forcing weak experiments into the main
contribution"), **this is not attempted as a quantitative result.**
Constructing real matched pairs requires deliberately sourcing
Tier-1 items in topic-matched sets (e.g., a government-scheme
misinformation claim about the ruling party AND a structurally similar
one about an opposition state government), which the Day 2 sourcing
process so far has optimized for actor *diversity*, not actor
*matching* — a real, disclosed methodological choice that trades away
this specific analysis for broader dataset coverage. Recommend: a
dedicated Day 2-style sourcing pass specifically for matched pairs
before this analysis can be run at all, named as the top open item for
whoever continues this program past Day 10.

**What can be said now, qualitatively, from the real data already
collected** (not a substitute for the real analysis): of the 9 real
verdicts in `validator_results.csv`, the two verdicts targeting a
government body's own claims (item-0004's Delhi Police baton case, and
implicitly the Ladakh government source used as evidence in item-0002)
were treated no differently in kind by the pipeline than verdicts about
party or activist claims — the system was willing to reach `FALSE`
against a claim ultimately traceable to Delhi Police/PIB's own public
denial (`item-0004`, see `VALIDATOR_EVALUATION.md` for why that specific
verdict is itself judged wrong, for reasons unrelated to which actor was
involved). This is not evidence of neutrality — it is one data point
showing the system does not categorically refuse to find against a
government actor, which is a necessary but nowhere near sufficient
condition for the bias question RQ5 actually asks.

## Calibration (RQ6): not computed — sample too small, per the brief's own explicit fallback rule

9 real confidence values exist (`research/results/validator_audit_*.json`):
0.0, 0.0, 0.1, 0.1, 0.2, 0.2, 0.2, 0.7, 0.8. Computing a reliability
diagram or Expected Calibration Error requires enough items per
confidence bin to mean anything — `METRICS.md` §6 already set a gate of
"no bin with fewer than 3 items," and this distribution cannot meet that
gate no matter how bins are drawn (most values cluster at 0.0–0.2, only
two values above 0.5, and n=9 total). **Per the brief's explicit
instruction ("If confidence cannot be meaningfully calibrated: remove
numerical confidence claims from the paper... do NOT use fake confidence
percentages"), no ECE or Brier score is reported.**

One qualitative, heavily-caveated observation, reported as an
observation and explicitly not as a statistic: the two highest
-confidence verdicts in this sample (0.7 "democracy/protest rights,"
0.8 "Durrani met Dipke") are both cases the draft human review in
`VALIDATOR_EVALUATION.md` judged unreliable or factually wrong, while
several of the lowest-confidence verdicts (0.0–0.1) were appropriately
cautious `UNVERIFIED` outputs. At n=9 this is not evidence of an inverse
relationship between confidence and correctness — it is exactly the
kind of pattern a real calibration analysis, at real scale, would need
to check for rather than assume away.

## Efficiency (`research/system_efficiency.csv`)

Real, measured data from Day 3's baseline smoke tests and Day 5's real
pipeline run:

- **Baseline 2 (search+LLM)**: 1 LLM call, ~716 input / ~71 output
  tokens, ~15.9s average latency, $0 (Ollama-only).
- **Baseline 3 (search+RAG+LLM)**: 1 LLM call, ~2,268 input tokens (full
  page text roughly 3× baseline 2's snippet-only input) / ~70 output
  tokens, ~17.8s average latency, $0.
- **Full TruthLens**: **not directly latency-comparable in this pass —
  a real, disclosed gap**: `run_validator_audit.py` (Day 5) did not
  capture per-claim wall-clock time. What IS measurable from that same
  real run: an average of **7.56 sources per claim**, each requiring its
  own `evidence_analysis` LLM call, plus one `research_planning` call
  and one `verdict` call — roughly **9.6 LLM calls per claim**, against
  baselines 2/3's fixed 1 call per claim. This alone (independent of
  per-call latency) means full TruthLens's real cost/time-per-claim is
  necessarily several times either baseline's, before even accounting
  for the actual page-fetch time each of those 7.56 sources took.
- **Baseline 4 (TruthLens minus validation)**: built and unit-tested
  (Day 3) but not run as its own timed pass — since the `SKIP_VALIDATION`
  flag changes only which content gets *persisted*, not which LLM calls
  get *made*, its call count/token/latency profile is identical to full
  TruthLens's by construction; no separate measurement would show
  anything different.
- **Baseline 1 (LLM-only)**: reused from
  `research_paper/benchmark/naive_baseline_results.jsonl` — timing was
  not captured in that original Day-0 script either, a pre-existing gap
  inherited rather than newly introduced here.

**What this pass could not measure and is not claiming to have
measured**: exact dollar cost per configuration (Gemini escalation
pricing was not itemized per call during Day 5's real run), and
apples-to-apples latency for full TruthLens against the two baselines.
Both are concrete, scoped gaps for the Day 8 full run rather than
estimated here.
