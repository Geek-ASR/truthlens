# Reproducibility

## Environment, verified live on 2026-08-13

```
Python 3.12.10
fastapi==0.115.6
SQLAlchemy==2.0.36
pydantic==2.13.4
pydantic-settings==2.7.0
alembic==1.14.0
boto3==1.35.86
faster-whisper==1.1.0
google-genai==2.17.0
pgvector==0.3.6
tenacity==9.0.0
```
Full lock: `research/environment.lock` (`pip freeze` from `backend/.venv`,
130 pinned packages, captured 2026-08-13). Regenerate with:
```bash
cd backend && .venv/bin/pip freeze > ../research/environment.lock
```

Ollama models actually pulled on this machine, verified via `ollama
list` (2026-08-13): `llama3.2:latest` (2.0 GB, the default text/claim
-extraction/verdict model used throughout this program) and
`llava-phi3:latest` (2.9 GB, vision). `moondream`, `llama3`, `mistral`
are also present locally but not used by any experiment in this paper —
listed for completeness, not because they are load-bearing.

Postgres 16 (native, not Docker, on this dev machine) + pgvector
extension. MinIO (S3-compatible) for object storage. Ollama running
locally with models `llama3.2` (text) and `llava-phi3` (vision) already
pulled. `GEMINI_API_KEY` set for the optional escalation cascade — its
absence does not break the pipeline, only disables escalation (verified
by direct code inspection of every `if settings.GEMINI_API_KEY` guard).

## Freeze points

Two tags, not one, because the dataset and the system code were frozen
at different points (Section~V-D/`EXPERIMENT_PLAN.md` §7):
```bash
git tag -a truthlens-pre-ieee -m "..."     # Day 1: system code + audit frozen
git tag -a truthlens-day8-frozen -m "..."  # Day 8: dataset (9 items) + baselines/ablations frozen
git checkout truthlens-day8-frozen         # reproduces the exact Day 8 headline-result state
```
The two general validator/vision-context fixes described in
Section~IX/`sec:validation` were made *after* `truthlens-day8-frozen`, in
direct response to its headline finding, and are on `main` (not tagged
separately as of this writing) — their ground-truth-independence, not a
tag boundary, is what keeps them from being test-set tuning (Section
V-D/§"Held-out discipline").

## Commands verified to actually work on this date (2026-08-13)

```bash
cd backend
.venv/bin/python -m pytest -q
# → 161 passed, 8 warnings (unrelated deprecation warnings in dependencies)
```

```bash
cd research_paper
tectonic main.tex
# → main.pdf, 21 pages, no undefined references, 2 trivial (<9pt) overfull-hbox
#   warnings only
```

## Regenerating every table and figure in the paper

Nothing in `main.tex` is hand-typed from a raw calculation; each number
traces to one of the commands below. Run from the repository root unless
noted. **Figure numbers below are the actual LaTeX-compiled numbers**
(verified against `main.pdf`'s rendered captions, not the
`day10_figures.py` script's internal filenames, which number figures in
generation order rather than final document order -- Fig. 1 in the
compiled paper is the RQ-status chart because it appears in Section III,
before the architecture diagram in Section IV, even though the
generating script produced it last, as `fig8_rq_status.pdf`; this
mismatch is exactly the kind of thing this section exists to catch, and
was itself caught by rendering and reading the actual compiled pages
rather than trusting the filenames).

| Paper artifact | Regeneration command | Reads |
|---|---|---|
| Table I (RQ status) | hand-authored summary of Sections VII-XI's own status lines; not machine-generated (it *describes* the other tables, it doesn't compute a new number) | — |
| Fig. 1 (RQ status chart) | `./backend/.venv/bin/python backend/research/day10_figures.py` (`fig_rq_status`, writes `figures/fig8_rq_status.pdf`) -- a hand-set visual index of Table I's own status column, not an independent computation | — |
| Fig. 2 (architecture) | compiled directly from the `tikzpicture` in `main.tex`; no external script, no PDF asset | — |
| Tables III/IV, Table V (decomposition) | `./backend/.venv/bin/python backend/research/day8_final_tables.py` | `research/results/baseline_*_2026*.jsonl`, `full_truthlens_reel_level_day8_v2_with_new_checks.json`, `claim_decomposition_ablation.json` → writes `research/results/day8_summary.json` |
| Fig. 3 (Tables III/IV plotted) | `day10_figures.py`, `fig_main_results` (writes `figures/fig2_main_results.pdf`) | `research/results/day8_summary.json` (above) |
| Fig. 4 (Table V plotted) | `day10_figures.py`, `fig_decomposition_ablation` (writes `figures/fig3_decomposition_ablation.pdf`) | `research/results/day8_summary.json` |
| Tables VII/VIII (validator confusion matrices) | figures hardcode the published TP/FP/TN/FN counts from `research/VALIDATOR_EVALUATION.md` and its addendum, which are themselves computed by a human reviewer reading `research/results/validator_audit_20260813T073200Z.json` against `research/validator_results.csv`'s `draft_human_judgment` column -- not currently re-derivable by a script alone, since the ground truth is a human judgment call, not a formula |
| Fig. 5 (validator P/R before/after) | `day10_figures.py`, `fig_validator_before_after` (writes `figures/fig4_validator_before_after.pdf`) | the same hardcoded TP/FP/TN/FN counts as Tables VII/VIII, above |
| Tables IX/X (source tier / evidence stance), Fig. 6 (evidence quality) | `day10_figures.py`, `fig_evidence_quality` (writes `figures/fig5_evidence_quality.pdf`) -- **partial gap, disclosed**: the $n{=}68$ tier/stance distribution is hardcoded from `research/EVIDENCE_EVALUATION.md`'s published table, not re-queried live, because that table was originally produced by a direct Postgres query against a `truthlens-pre-ieee`-era database that is not running in every environment (including the one this figure was regenerated in). To re-derive it: stand up the stack (`infra/docker-compose.yml` + Ollama), re-run `backend/research/validator/run_validator_audit.py`, then query `sources`/`evidence` tables directly for tier/stance counts -- not yet scripted as a single command, a concrete open item (below) |
| Table XI (claim coverage), Fig. 7 (multimodal) | `day10_figures.py`, `fig_multimodal_coverage` (writes `figures/fig6_multimodal_coverage.pdf`) -- numbers hardcoded from `research/MULTIMODAL_EVALUATION.md`'s published table, itself produced by `backend/research/multimodal/run_claim_coverage.py` against `research/dataset/items.jsonl` and `research/annotations/atomic_claims_draft.json` (a human/LLM-assisted draft ground truth, not machine-derivable alone) |
| Table XII (efficiency), Fig. 8 | `day10_figures.py`, `fig_efficiency` (writes `figures/fig7_efficiency.pdf`), reading `research/system_efficiency.csv` directly (a real, versioned CSV, not regenerated by a script -- see that file's own `notes` column for each row's provenance) |

To regenerate every data figure in one pass:
```bash
./backend/.venv/bin/python backend/research/day10_figures.py
```
writes all 7 PDFs to `research_paper/figures/`; Fig. 2 (architecture) is
regenerated automatically on the next `tectonic main.tex` run since it
is native TikZ, not a raster/vector file on disk -- not part of this
script's 7.

## What is NOT yet reproducible end-to-end from a clean checkout

Documented honestly rather than assumed away:
- No single `docker-compose up` currently starts Postgres+MinIO+Ollama
  together with models pre-pulled — `infra/docker-compose.yml` exists
  for Postgres/Redis/MinIO, but Ollama and its models are a manual local
  install on this machine (an 8GB M1), not containerized. A different
  machine reproducing this work needs to independently install Ollama
  and pull `llama3.2`/`llava-phi3`.
- No seed script populates a demo `User` row with a known password —
  `backend/scripts/seed_admin.py` requires a password argument chosen at
  seed time, not a fixed reproducible credential.
- Dataset construction (`DATASET_SPEC.md`) is inherently not
  "reproducible" in the bit-for-bit sense — it depends on which
  Instagram posts are still live and which fact-check articles exist at
  construction time. What IS reproducible: the `items.jsonl` file itself
  (frozen, versioned in git) and every downstream experiment run against
  it.
- The $n{=}68$ evidence tier/stance distribution behind Fig. 6 (Section
  IX) is not re-derivable by a single script in every environment — see
  the table above. This is a real, disclosed gap, not an oversight: the
  original numbers came from a direct database query during Day 6's live
  run, and no environment used to prepare this specific paper revision
  had that same Postgres instance running. The exact query needed is one
  `GROUP BY source_tier` / `GROUP BY stance` pair against the `sources`/
  `evidence` tables scoped to the claims audited in
  `validator_audit_20260813T073200Z.json` — trivial once the stack is
  running, not scripted here only because it wasn't running when this
  section was written.
- item-0003 (Section VI) cannot be reproduced by re-running ingestion —
  it has failed on every attempt across this entire program (3
  independent tries) with a persistent Instagram-side error, which is
  itself the reproducible fact being reported, not a gap in our tooling.

## Random seeds

No component of the current pipeline uses a fixed random seed —
`source_scoring.py`'s formula is deterministic (no randomness at all);
LLM sampling temperature/seed behavior is whatever Ollama's/Gemini's
defaults are, not currently pinned. **This is a real limitation for
exact reproducibility of individual LLM calls** (re-running the same
claim through the same model may not produce byte-identical output) and
will be stated as such in the paper's threats-to-validity section,
consistent with how the existing paper already treats development
telemetry as "not independent draws" rather than claiming exact
repeatability.

## Day 10 reproducibility package: delivered vs. still open

Delivered:
- `research/environment.lock` — full `pip freeze` (130 packages);
  Ollama models verified via `ollama list` and recorded above verbatim.
- `backend/research/day8_final_tables.py` — drives Tables III/IV/V and
  Figs. 3-4 from `research/results/*.jsonl`/`*.json`; fixed this pass
  after a real variable-shadowing bug was found (Section XII/`sec:failuremodes`)
  that made its persisted JSON silently disagree with its own printed
  stdout tables.
- `backend/research/day10_figures.py` — drives Figs. 1, 3, 4, 5, 6
  (partial, see gap above), 7, 8 from real result files (everything
  except Fig. 2, the native-TikZ architecture diagram); single command,
  documented above.
- Prompt versions: every prompt used is already versioned in
  `backend/app/services/ai/prompts.py` (`CLAIM_EXTRACTION_PROMPT_VERSION`
  etc.) and recorded per-call in `audit_logs.prompt_version`.

Still open, named rather than hidden:
- No single `scripts/run_all_experiments.sh` exists that re-runs every
  baseline/ablation against the dataset from a clean checkout end-to-end
  (real LLM calls, real web fetches -- Section V's own "honest scope
  reductions" already note this is realistically hours of wall-clock
  runtime per full pass, not a one-line CI step).
- No unified `docker-compose up` starts Postgres+MinIO+Ollama together
  with models pre-pulled (above).
- Fig. 6's $n{=}68$ tier/stance distribution is not re-derivable by a
  single script in every environment (above) -- the query is trivial,
  the standing stack is not.
- No fixed LLM sampling seed (see "Random seeds" above) -- a real,
  disclosed limit on bit-for-bit reproducibility of any individual LLM
  call, independent of code or data versioning.
