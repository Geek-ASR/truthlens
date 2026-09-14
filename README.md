# TruthLens

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22758785.svg)](https://doi.org/10.5281/zenodo.22758785)

An evidence-first pipeline for fact-checking short-form political video and
image posts. TruthLens decomposes a post into atomic claims, researches each
against the open web, and subjects every generated verdict to a deterministic,
non-LLM validator before anything is published.

**Author:** Aditya Rekhe (Independent Researcher)
**Preprint + dataset:** <https://doi.org/10.5281/zenodo.22758785>

> **Status: research preprint and prototype.** Not peer reviewed, not a
> production fact-checking service, and not published in any journal or
> conference proceedings.

## What it does

A post goes through ten stages: ingestion (download, transcribe, OCR, optional
vision) → claim extraction → research planning → evidence retrieval → per-source
stance analysis → verdict proposal → **deterministic validation** → reel-level
aggregation → carousel rendering → human-approval-gated publishing.

The load-bearing design choice is the validator: a non-LLM check that verifies a
proposed verdict's citations exist, its sources were actually fetched, its
numbers are grounded in retrieved evidence, and its label does not contradict
its own reasoning. A verdict that fails is downgraded, not published.

By default every LLM stage runs on **local models** via Ollama — no API key, no
per-token cost, no rate limit.

## Results, briefly

On the 193-item `validation` split of TruthLens-202, in the local-only
configuration: 34.7% of posts produce a verdict at all, and bucketed accuracy on
those is 29.9% (Wilson 95% CI [20.2, 41.7]); balanced accuracy is 22.2%, below
an always-FALSE predictor. This is reported as an honest **floor** for a
deliberately minimal zero-cost configuration, not as a headline capability. The
diagnostic finding is that claim extraction — not retrieval — gates whether a
post gets checked at all.

Full numbers, methodology and limitations are in the preprint.

## Layout

```
backend/      FastAPI service, the 10-stage pipeline, and research harnesses
frontend/     Next.js review dashboard
infra/        docker-compose (Postgres/pgvector, Redis, MinIO)
docs/         architecture, data model, API requirements, security notes
research/     evaluation protocols, metric definitions, results, dataset
research_paper/  LaTeX source, figures, and the compiled preprint
```

## Running it

Requires Python 3.12, Node 20+, Docker, and [Ollama](https://ollama.com).

```bash
cp infra/.env.example backend/.env       # fill in what you need; no key required for local-only
docker compose -f infra/docker-compose.yml up -d
ollama pull llama3.2 && ollama pull llava-phi3
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload
```

Exact pinned versions used for the reported results: `research/environment.lock`.
Reproduction notes: `research/REPRODUCIBILITY.md`.

## Licensing

- **Code** — MIT (see `LICENSE`).
- **Paper and dataset** — CC BY 4.0.
- **Third-party content** — the social-media posts referenced by URL and the
  fact-checking organisations' articles remain the property of their rights
  holders and are **not** redistributed. The dataset ships URLs, labels and
  annotations only.

## Citing

```bibtex
@misc{rekhe2026truthlens,
  author       = {Rekhe, Aditya},
  title        = {{TruthLens: A Verification-Gated Pipeline for
                   Evidence-Grounded Fact-Checking of Short-Form
                   Political Video}},
  year         = {2026},
  publisher    = {Zenodo},
  version      = {1.0.0},
  doi          = {10.5281/zenodo.22758785},
  url          = {https://doi.org/10.5281/zenodo.22758785}
}
```

The concept DOI `10.5281/zenodo.22758784` always resolves to the latest
version. See also `CITATION.cff`.
