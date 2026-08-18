# Resuming this project

**Status: paused, 2026-08-18.** This is the single entry point for
picking this back up — what's actually built and working, what's left,
and where to find the detail behind each item. Everything below was
true as of the last commit on `main` (126 commits total); nothing here
should be trusted blindly if a lot of time has passed before you read
it — grep/read the real code before acting on anything specific.

## TL;DR

TruthLens (an automated Instagram political-fact-checking system) is
built, evaluated, and documented in a real research paper. The
benchmark it's evaluated against is small (22 items) and a whole
session went into trying to grow it faster, concluding that it's
structurally capped, not a tooling problem. Separately, the system's
Instagram-publishing pipeline — already built, previously untested —
was verified to work and given real test coverage, but has never
posted to a live account. The single most concrete, actionable next
step is finishing that account connection.

## What's built and working

- **The 9-stage fact-checking pipeline** (ingestion → claim extraction
  → research → evidence → verdict → deterministic validation →
  aggregation → carousel rendering), described in full in
  `research_paper/main.tex` (`sec:architecture`) and implemented under
  `backend/app/pipeline/`.
- **A 10th stage**: human-approval-gated publishing to Instagram via
  the official Meta Graph API (`backend/app/pipeline/publishing.py`,
  `backend/app/services/instagram/graph_client.py`). Real, correct
  implementation — not a stub. Verified this session by generating and
  visually inspecting real carousel slide images from the dev DB, and
  given 18 new tests (`backend/tests/test_instagram_graph_client.py`,
  `backend/tests/test_publish_fact_check.py`) after finding it had
  zero coverage. **Never exercised against a real, live Instagram
  account** — see "What's left" below.
- **A review dashboard** (`frontend/`) with an Approve/Reject/Publish
  workflow already wired to the backend.
- **The benchmark**: 22 items total — `research/dataset/items.jsonl`
  (9, `dev` split) + `research/dataset/items_v2.jsonl` (13,
  `validation` split).
- **The research paper** (`research_paper/main.tex`, ~3,090 lines):
  real experimental results against the frozen 9-item comparison, a
  foundation-phase extension program, and this session's mass-sourcing
  and publishing-pipeline work. `research_paper/main.pdf` is **stale**
  — see item 2 below.
- **304 backend tests**, all passing as of the last commit
  (`cd backend && ./.venv/bin/python -m pytest -q`).

## What's left, in priority order

### 1. Connect a real Instagram account (the concrete next step)

Nothing is connected yet — `instagram_accounts` is empty in the dev
DB, confirmed directly, regardless of what `backend/.env` currently
has set for `META_APP_ID`/`META_APP_SECRET`/`INSTAGRAM_ACCESS_TOKEN`
(those values were not re-verified this pass; check they're real and
current, or replace them, before relying on them — `INSTAGRAM_ACCESS_TOKEN`
specifically is dead/unused code regardless, per `docs/API_REQUIREMENTS.md`).
What's actually needed, free, one-time (~15–20 min):

1. A Facebook Page (any name/category — doesn't need real activity).
2. An Instagram account switched to **Business** and linked to that
   Page.
3. A Meta Developer App (Business type) at developers.facebook.com,
   with the Instagram account added as a **Tester** — this is what
   lets posting work for your own account without needing Meta's full
   App Review process.
4. A short-lived access token via Graph API Explorer, submitted through
   the dashboard's Instagram Settings page (or directly to
   `POST /api/instagram-accounts`) — the backend exchanges it for a
   long-lived token and stores it encrypted automatically.

Full detail and the exact Graph API constraints (rate limits, carousel
size, App Review scope): `docs/API_REQUIREMENTS.md` §1.

Once connected: run one real fact-check through
`ready_for_review → approved → published` end to end, on a real post,
and confirm the permalink comes back correctly before treating this
pipeline as production-ready.

### 2. Recompile the research paper

`research_paper/main.tex` was extended this session (two new
subsections, an updated Abstract/Conclusion/Future Work item) but
**no LaTeX toolchain was available** in the environment that did it —
the edit was checked for brace balance, duplicate labels, and
unresolved cross-references only, not an actual compile. Run
`pdflatex`/`xelatex` (whatever `research_paper/main.log` shows was used
last), fix anything that doesn't compile clean, and visually check the
new pages (`pdftoppm` or just opening the PDF) before treating
`main.pdf` as current. Full detail on exactly what changed and this
gap: `research_paper/STATUS.md` (top entry).

### 3. A decision on benchmark scaling

22 items is still short of the ~40–60 needed for real statistical
power (McNemar test, named throughout the paper). This session
measured, precisely, why: automated crawling across six independent
Indian fact-checker sources (Alt News, Vishvas News, WebQoof, Factly,
India Today, Fact Crescendo — full detail in
`research/MASS_SOURCING_V2.md`) judged ~3,600 real candidates and
promoted 4 — a blended yield of **roughly 1 promotable item per 900
candidates checked**. This isn't a tooling gap (two real filter bugs
were found and fixed mid-session, each confirmed to add real volume,
neither meaningfully moved the yield rate) — it looks structural:
most of this specific misinformation pattern is posted to X/Twitter,
not Instagram, a finding this session confirmed quantitatively after
first finding it qualitatively (8/8 sampled cases, mentioned in
`research/RESEARCH_ROADMAP_V2.md`'s Phase 1 log). The real open
decision, explicitly deferred rather than made unilaterally: keep
growing slowly Instagram-only, relax the platform scope, or accept 22
items and adjust the paper's statistical claims accordingly. Whoever
resumes this should make that call before spending more sourcing
effort.

### 4. Diagnosed-but-unresolved research findings

Not blockers, just real, named, still-open items — the authoritative,
maintained list is `research_paper/main.tex`'s Future Work section
(`sec:futurework`) and its Conclusion (`sec:conclusion`). Highlights:
claim-extraction coverage failures on degraded audio; the cross-post
attribution problem (most false claims in this dataset live outside
the specific post being fact-checked, not fixable by better
single-post extraction); a verdict-stage failure where the model
doesn't reliably weight source reliability under direct contradiction,
which a prompt fix did not resolve; RQ5 (bias) and RQ6 (calibration),
both deferred because the dataset is too small to support them, not
attempted and abandoned.

## Where things actually live

| What | Where |
|---|---|
| The paper (source of truth for research claims) | `research_paper/main.tex`, changelog in `research_paper/STATUS.md` |
| Sourcing pipeline architecture, bugs found/fixed, final numbers | `research/MASS_SOURCING_V2.md` |
| Phase-by-phase project roadmap | `research/RESEARCH_ROADMAP_V2.md` |
| Every controlled experiment run, with real numbers | `experiments/registry.jsonl` |
| Instagram/Meta API setup requirements | `docs/API_REQUIREMENTS.md` |
| Known failure modes (24+ entries, most with a fix + regression test) | Paper Appendix, `sec:appendixtaxonomy` |
| Fact-checking pipeline code | `backend/app/pipeline/` |
| Instagram publishing code | `backend/app/services/instagram/`, `backend/app/pipeline/publishing.py` |
| Mass-sourcing pipeline code | `backend/research/benchmark_v2/mass_source_*.py` |
| Review dashboard | `frontend/src/app/` |

## Picking this back up, practically

```
cd backend && ./.venv/bin/python -m pytest -q   # confirm 304 pass before touching anything
cd infra && docker compose up -d                # Postgres + MinIO, if not already running
cd backend && ./.venv/bin/alembic upgrade head   # confirm migrations are current (403a421884b7 as of pause)
```

Then re-read this file's "What's left" section and pick one item —
item 1 (Instagram account connection) is the one with no dependencies
on anything else and the clearest definition of done.
