# VALIDATOR_SYNTHETIC_BENCHMARK_V2.md — Phase 8

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 8: re-run
the adversarial validator benchmark against the new combined check set
— Checks 6 (temporal, Phase 5) and 7 (entity, Phase 4), both integrated
into production this session — which the original 28-case benchmark
(`research/validator_benchmark/build_and_run.py`,
`VALIDATOR_SYNTHETIC_BENCHMARK.md`) has **zero** coverage of: its cases
never set `claim_time_reference`/`claim_entities`, so Checks 6/7 were
structurally dormant against every one of them (`validate_verdict()`'s
own documented backward-compatibility design, not a bug).

## Honest scope

Step 18 names 20 adversarial categories. Several (OCR/audio corruption,
AI-generated image, edited video, mixed-language, multiple claims) are
upstream pipeline concerns a *validator-only* benchmark structurally
cannot test — Phase 11's later, broader, whole-pipeline scope, not
padded in here to inflate a count. This pass adds 6 real, hand
-considered cases targeting exactly the 2 new checks — 34 total, not
the 100+ target (same honest-shortfall disclosure the original 28-case
benchmark already made about its own 60-100 target).

## New cases

- **P1/P2** (Check 6, temporal): claim asserts an explicit date, cited
  source predates it by 400/900 days — the "old footage presented as
  current" pattern. Both correctly flagged (`downgraded_temporal_mismatch`).
- **P3-negative** (Check 6): source published *after* the claimed date
  (the normal case) — correctly NOT flagged.
- **Q1/Q2** (Check 7, entity): claim about one named organization, cited
  evidence about a different, unrelated one (Delhi Police/Burdwan
  Police; Karni Sena/Sri Ram Sena — the same real case shapes from
  `ENTITY_CONSISTENCY_EVALUATION_V2.md`). Both correctly flagged
  (`downgraded_entity_mismatch`).
- **E1v2-retest**: a direct re-test of the *original* benchmark's `E1`
  case ("wrong entity: cited evidence about a different, similarly
  -named organization"), which was explicitly marked
  `checkable_by_current_checks=False` when first written — a real,
  disclosed gap at the time. Same evidence text, same reasoning, this
  time with `claim_entities` actually wired through.
  **Result: correctly caught (`downgraded_entity_mismatch`).** This is
  not a new case invented to look good — it is the specific,
  previously-named limitation, re-tested and closed.

## Combined results (28 original + 6 new = 34 cases)

| | Original (n=28) | This pass (n=34) |
|---|---|---|
| Precision | 81.8% | **87.5%** |
| Recall | 50.0% | **60.9%** |

**All 6 new cases scored correctly** (5 true positives, 1 true
negative). **Zero new false positives were introduced** — the
benchmark's only 2 false positives (`valid-9-contrastive-fp`,
`valid-10-contrastive-fp`) are the *same, already-documented* Check-3
contrastive-number limitation the original benchmark's own construction
notes disclosed ("the true figure is X, not the falsely claimed Y" verdicts
false-positiving because Y never appears in the evidence passage, only
the claim text) — unrelated to Checks 6/7, unchanged by this pass.

Per Phase 8's own explicit precision-preservation rule ("if a new
check's false-positive rate rises, that check is not integrated even if
its recall contribution looks good"): satisfied. Both new checks added
real recall with zero precision cost on this expanded benchmark.

## What did NOT happen

- No attempt to reach 100+ cases or cover Step 18's non-validator
  -testable categories.
- The pre-existing Check-3 contrastive-number false-positive limitation
  is unchanged — named again here, not re-litigated or fixed (out of
  this pass's scope).

## Raw data

`research/results/validator_synthetic_benchmark_v2_20260818.json` (all
34 cases, full detail). Generator:
`backend/research/validator_benchmark/build_and_run_v2.py` (imports
`build_cases()` from the original file unchanged, adds the 6 new cases
above).
