# Reproducibility (Day 1 draft — will be expanded Day 10)

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
Full lock: `backend/.venv` via `pip` (no `requirements.txt` hash
recorded yet — Day 10 will add `pip freeze > research/environment.lock`).

Postgres 16 (native, not Docker, on this dev machine) + pgvector
extension. MinIO (S3-compatible) for object storage. Ollama running
locally with models `llama3.2` (text) and `llava-phi3` (vision) already
pulled. `GEMINI_API_KEY` set for the optional escalation cascade — its
absence does not break the pipeline, only disables escalation (verified
by direct code inspection of every `if settings.GEMINI_API_KEY` guard).

## Freeze point

```
git tag -a truthlens-pre-ieee -m "..."
git checkout truthlens-pre-ieee   # to reproduce exactly the audited state
```

## Commands verified to actually work on this date

```bash
cd backend
.venv/bin/python3 -m pytest tests/ -q
# → 142 passed, 4 warnings (unrelated deprecation warnings in dependencies)
```

```bash
cd research_paper
tectonic main.tex
# → main.pdf, 13 pages, no undefined references, no missing-character warnings
```

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

## Full Day 10 reproducibility package (not yet built, planned contents)

- `research/environment.lock` — full `pip freeze` + Ollama model digests
  (already visible via `ollama list`, to be captured verbatim).
- `scripts/run_all_experiments.sh` — drives every baseline/ablation over
  the frozen dataset, writing to `research/results/`.
- `scripts/generate_paper_tables.py` — reads `research/results/*.jsonl`,
  writes every LaTeX table in the paper; no table is ever hand-typed.
- `scripts/generate_paper_figures.py` — same discipline for figures.
- Prompt versions: every prompt used is already versioned in
  `backend/app/services/ai/prompts.py` (`CLAIM_EXTRACTION_PROMPT_VERSION`
  etc.) and recorded per-call in `audit_logs.prompt_version` — this
  mechanism already exists and needs no new work, only needs to be cited
  correctly in the paper's methodology section.
