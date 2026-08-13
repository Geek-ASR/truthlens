# EXPERIMENT_PROTOCOL.md — Phase 2

Status: 2026-08-14.

## A note on scope: why this is not a directory reorganization

Phase 2 of the governing review asked for a single-source-of-truth
pipeline under `experiments/{benchmark,baselines,validator,...}` writing
to `results/*.json`, with every table and figure regenerated from it.
**That property already holds** in this codebase — verified repeatedly
this session, including finding and fixing the one place it didn't
(`day8_final_tables.py`'s variable-shadowing bug, Section
`sec:failuremodes`) — via a different, already-established directory
layout (`backend/research/` for scripts, `research/results/` for
outputs). Moving working, tested scripts into a new directory tree at
this stage, purely to match a suggested naming convention, would be
exactly the kind of complexity-without-justification Rule 4 warns
against: no failure mode it solves, no evaluation it changes, real risk
of breaking a path some other script or doc references. This document
instead makes the existing structure's single-source-of-truth property
explicit and auditable, which is what Phase 2 actually needs.

## The protocol, as actually followed

```
research/dataset/items.jsonl          [frozen, git-tagged, held-out]
        |
        v
backend/research/baselines/*.py       [Baselines 1-3, + corrected per-claim variant]
backend/research/validator/*.py       [real production pipeline, SKIP_VALIDATION flag]
backend/research/multimodal/*.py      [3 real ingestion + extraction conditions]
        |
        v
research/results/*.jsonl, *.json      [raw, one row per (item, config)]
        |
        v
backend/research/day8_final_tables.py [reads raw results -> day8_summary.json]
backend/research/day10_figures.py     [reads day8_summary.json + CSVs -> figures/*.pdf]
        |
        v
research_paper/main.tex               [\includegraphics + \ref{} only -- no hand-typed
                                        experimental numbers, verified by
                                        CLAIM_EVIDENCE_MATRIX.md]
```

Every arrow above is a real, runnable command, listed exhaustively in
`REPRODUCIBILITY.md`'s regeneration table. The two disclosed exceptions
(the $n=68$ evidence-quality snapshot, and any figure sourced from a
human-judgment CSV rather than a formula) are named explicitly in that
same table, not hidden by omission.

## Held-out discipline (the actual protocol enforced, not just stated)

1. **Freeze points are git tags, not a promise.** `truthlens-pre-ieee`
   (system code), `truthlens-day8-frozen` (9-item dataset + baselines/
   ablations), `truthlens-day9-general-fixes` (the two post-freeze
   validator/vision fixes, tagged separately for audit clarity).
2. **A change made after a freeze is either ground-truth-independent, or
   it doesn't happen.** The two general validator fixes (Check 4,
   vision-context substantiveness) are pure functions of the model's own
   output, never of the held-out labels — this is stated as a design
   constraint, not just a description, and its one imperfect instance
   (Check 4's phrase list read the real failing cases while being
   written) is disclosed as a named threat to validity, not smoothed
   over.
3. **The baseline-input fix (Section VII.A of the paper) is likewise
   ground-truth-independent**: it changes what claim text a baseline
   receives (from a hand-written summary to TruthLens's own real
   extraction), not any threshold, prompt, or judgment informed by
   knowing the correct label. This is what allows the corrected
   comparison to be reported as a real result rather than test-set
   tuning.
4. **A number that cannot be regenerated from a committed script and a
   committed raw file is labeled as such**, not presented identically to
   one that can (`REPRODUCIBILITY.md`'s regeneration table draws this
   line explicitly for every table and figure in the paper).

## What "done" looks like for a new experiment added to this protocol

1. Write the raw-output script under `backend/research/` (or the
   relevant existing subdirectory), writing one JSON/JSONL row per
   (item, condition) to `research/results/`, matching
   `METRICS.md`'s "Raw result row schema" where the metric already has
   one, or extending that schema explicitly where it does not.
2. Extend `day8_final_tables.py` or `day10_figures.py` (or add a new,
   analogously-structured script) to consume the new raw file and
   produce the summary numbers / figure — never hand-type the result
   into `main.tex`.
3. Add the new artifact's regeneration command to
   `REPRODUCIBILITY.md`'s table.
4. Add its empirical claim(s) to `CLAIM_EVIDENCE_MATRIX.md`.
5. If it changes an existing published number, disclose the change with
   the same prominence as the number itself — the pattern this program
   followed for the Day 10 `day8_final_tables.py` bug fix and this
   pass's baseline-claim-input fix, not a new rule invented for this
   document.
