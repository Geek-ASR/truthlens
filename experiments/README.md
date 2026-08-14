# experiments/

Status: 2026-08-14. `research/RESEARCH_ROADMAP_V2.md` Phase 1, governing
brief Step 9 (Experiment Ledger).

## A note on why this exists now, having previously been rejected

`research/EXPERIMENT_PROTOCOL.md` (Phase 2 of the prior audit program)
explicitly considered and rejected a numbered-experiment-directory reorg
as "complexity without justification," keeping the existing
`backend/research/{baselines,validator,multimodal}/` + `research/results/`
layout instead. That decision was correct for what it evaluated at the
time — a lightweight, already-working pipeline for a ~10-experiment
program run by one person over ten days, where a full ledger's
bookkeeping overhead genuinely outweighed its benefit.

This governing brief explicitly asks for one now, for the V2 program,
which is a different situation: more phases, more contributors possible
over time, and — per this brief's own "MOST IMPORTANT PRINCIPLE" section
— an explicit goal of making it possible to trace *which experiment*
established *which finding* without re-deriving it from memory or prose.
`EXPERIMENT_PROTOCOL.md` is not superseded or wrong for its own scope;
this is a genuinely new decision for a genuinely larger program, made
explicit rather than silently reversing the earlier one.

## What lives here

`registry.jsonl` — one JSON object per experiment, append-only in spirit
(a later experiment revisiting an earlier question gets a new
`experiment_id`, never edits over an old one — "No experiment may
silently overwrite an old result," per the governing brief). Backfilled
with the major experiments from the prior program so the registry isn't
starting empty and disconnected from everything this project has already
learned.

Actual experiment code and raw output remain exactly where they already
were (`backend/research/`, `research/results/`) — this registry indexes
and summarizes, it does not relocate anything, consistent with
`EXPERIMENT_PROTOCOL.md`'s original reasoning about not moving working
code for its own sake.

## Schema

| Field | Meaning |
|---|---|
| `experiment_id` | `EXP-NNN`, assigned in registration order, never reused |
| `hypothesis` | What this experiment was designed to test, stated so it could have come out false |
| `dataset` | Which dataset file/artifact |
| `split` | `dev` / `validation` / `test` / `regression` / `n/a` (n/a for structural/code-level findings) |
| `n` | Sample size actually used |
| `baseline` | What this was compared against, if anything |
| `variant` | What changed relative to the baseline |
| `model` | Model(s) involved |
| `prompt_version` | Prompt version string(s), where applicable |
| `retrieval_version` | Retrieval configuration, where applicable |
| `validator_version` | Validator check set in effect, where applicable |
| `metrics` | What was measured |
| `result` | The actual numbers |
| `confidence_interval` | Where appropriate; `null` where the brief's own discipline says a CI wouldn't be informative at this $n$ |
| `failure_cases` | Specific items/cases that failed, where relevant |
| `interpretation` | What the result means |
| `hypothesis_supported` | `true` / `false` / `directional` / `n/a` |
| `artifact` | Path to the underlying raw output this entry summarizes |
| `date` | When the experiment was run |

## Adding a new entry

Append to `registry.jsonl`, assign the next `EXP-NNN`. Do not edit a
prior entry's `result` or `interpretation` after the fact — if later work
changes how a result should be read, add a new entry that references the
old `experiment_id` in its own `interpretation` field, the same
discipline `research/RECONSTRUCTED_RESULTS.md` already used for the
baseline-confound correction.
