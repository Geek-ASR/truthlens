# PHASE1_RESEARCH_NOTES.md

Status: 2026-08-14. Governing brief Step 13. Not a paper update — the
paper is untouched this phase, per that same step's explicit instruction
("You may create PHASE1_RESEARCH_NOTES.md... But do not claim scientific
improvement until a controlled experiment demonstrates it").

## What changed

Six commits (`d4a7d77` through `b2bbe37`, on top of the Phase 0 audit
commit `6cc1c90`), each a coherent, independently-tested unit:

1. Centralized Gemini quota management (`app/services/ai/gemini_quota.py`)
   — replaced two independent, uncoordinated Gemini call paths with one.
2. Claim provenance/modality/confidence populated at extraction time.
3. Dataset split schema v2 + retroactive DB benchmark/development scoping.
4. Benchmark collection tooling (candidate tracker + composition report).
5. Regression test infrastructure (`tests/regression/` + `FAILURE_TAXONOMY.md`).
6. Experiment ledger (`experiments/registry.jsonl`, backfilled).
7. Mock Gemini provider + 7 quota scenario tests.

## Why

The governing brief's own audit (Phase 0, this session) found that
Gemini's quota-exhaustion handling had a real, specific bug — a
daily-exhausted 429 was retried identically to a transient 5xx — and
that several structural gaps (no dataset split, no DB scoping, no claim
provenance) blocked the larger benchmark-expansion and improvement work
the brief's later phases depend on. This phase built the foundation
those later phases need, deliberately not the benchmark expansion itself
(Step 8's explicit instruction).

## Tests performed

201 tests total, all passing, all free/local (no Gemini quota consumed —
every Gemini-dependent test uses the mock provider in
`tests/mock_gemini.py`). Breakdown of what's new this phase: 11 (claim
provenance) + 4 (dataset scoping) + 8 (candidate tracker) + 1
(composition report) + 2 (regression: MissingGreenlet, baseline-factory)
+ 5 (experiment registry) + 7 (Gemini quota scenarios A-G) = 38 new
tests, plus 2 pre-existing test fixtures updated for a new required
field. Full suite: `cd backend && ./.venv/bin/python -m pytest -q`.

## Research implications

- **The baseline-confound-style bug pattern recurred, in a different
  form.** Two real bugs were found and fixed *during this phase's own
  test-writing*, not just in the system under test: the quota provider's
  Gemini delegate was memoized, silently ignoring a test's monkeypatch
  set after the singleton's first use; and the composition-report
  script's claim-count query collapsed "never ingested" and "ingested,
  zero claims" into the same result. Both are the same *shape* of error
  the original baseline-confound audit found — a query or cache that
  looks correct but silently conflates two different real-world
  conditions — now caught at write-time by this phase's own test
  discipline rather than needing a later audit to find it.
- **Split assignment for the existing 9 items is a real, load-bearing
  methodological decision, not a formality.** They cannot be
  retroactively called TEST — see `DATASET_SCHEMA_V2.md`'s "Split
  assignment" section for the full reasoning. This means the *existing*
  headline comparison in `research_paper/main.tex` still has no clean
  TEST-split backing under the new, stricter discipline; only new `v2`
  items collected under Phase 1's stricter protocol can supply one.
- **`extraction_confidence` is populated but not yet validated as
  useful.** The field exists, is asked of the LLM, and is persisted as
  `MODEL_CONFIDENCE` — but no experiment yet checks whether it
  correlates with anything (e.g., extraction accuracy, downstream verdict
  correctness). That's a real, concrete next experiment, not yet run.

## New possible experiments (not yet run)

- Does `extraction_confidence` correlate with claim-extraction recall or
  precision, measured against a real held-out sample?
- Does `source_modalities` multi-modality overlap (a claim matched in
  more than one input) predict higher downstream verdict accuracy than a
  single-modality match?
- A genuine Gemini-vs-Ollama cross-check experiment (governing brief Step
  22/`RESEARCH_ROADMAP_V2.md`'s explicit later phase) — not attempted
  this pass; the infrastructure (centralized quota service, caching, cost
  caps) that makes this safe to run now exists, but the experiment itself
  does not.

## Unresolved problems

- Failure taxonomy entry #21 (`day8_final_tables.py`'s variable
  -shadowing bug) still has no regression test — named as a real,
  not-yet-closed gap in `FAILURE_TAXONOMY.md`, not silently dropped.
- No automated secret-scanning tool (`gitleaks`/`trufflehog`) is
  installed in this environment; the Step 12 security check was done via
  manual, targeted `grep` across every file changed this phase instead.
  Real, but a narrower guarantee than a dedicated tool would give.
- `Claim.confidence_type` is currently always the literal string
  `"MODEL_CONFIDENCE"` — a real constant, not yet an enum — since no
  second confidence source (a `SYSTEM_CONFIDENCE`) exists yet to
  distinguish it from. Worth promoting to an enum once/if one does,
  rather than pre-building for a distinction that doesn't exist yet.
