# AUDIT_REPORT_V2.md — Repository Audit for the V2 Research Program

Status: 2026-08-14. This audits the repository as it actually stands
right now — every claim below was verified live this pass (direct file
reads, `grep`, a live `psql` query against the running dev database, and
two independent read-only sub-agent explorations), not recalled from
memory or from prior documents. File:line citations are given wherever
possible so every claim here is checkable.

This is a **new**, separately-named file, not an overwrite of the
existing `research/AUDIT_REPORT.md` (which documents a specific, already
-fixed finding — the baseline claim-input confound — and remains the
correct historical record for that). Per this program's own Step 34
("do not destroy existing work"), nothing prior is deleted or modified
by this audit.

---

## 1. Current architecture

FastAPI backend (`backend/app/`), PostgreSQL 16 + pgvector, Redis,
MinIO (S3-compatible) for media/renders, Next.js admin dashboard
(`frontend/`, not audited in depth this pass). Orchestration entry
points: `app/pipeline/orchestrator.py:38` (`analyze_reel`) and `:83`
(`build_reel_fact_check`).

## 2. Current pipeline

Nine logical stages, each its own module under `app/pipeline/`:

| Stage | File | Entry point |
|---|---|---|
| Ingestion | `ingestion.py` | `ingest_reel()` |
| Transcription | `transcription.py` | `transcribe_reel()` |
| OCR | `ocr.py` | `ocr_reel()` |
| Vision context (advisory only, never cited as evidence) | `vision_context.py` | `analyze_vision_context()` |
| Claim extraction | `claim_extraction.py` | `extract_claims()` |
| Research planning | `research_planning.py` | `plan_research()` |
| Search & fetch | `search_fetch.py` (+ `source_scoring.py`) | `fetch_evidence_sources()` |
| Evidence analysis | `evidence_analysis.py` | `analyze_evidence()` |
| Verdict proposal | `verdict.py` | `propose_verdict()` |
| Deterministic validation | `validation.py` | `validate_verdict()` (called from `verdict.py:136`) |
| Overall-verdict aggregation | `overall_verdict.py` | `derive_overall_verdict()` — deterministic rule table, no LLM call |
| Content assembly / rendering | `reel_content.py` → `slide_generation.py` → `app/templates/slides.py` | `assemble_reel_content()` |

No stage begins before the previous one persists its output (enforced
by orchestrator sequencing, not just documentation).

**A second, legacy single-claim content path exists**:
`app/pipeline/content_generation.py`'s `generate_content()` is called
directly from `app/api/routers/fact_checks.py:320`, not from the
multi-claim `build_reel_fact_check` orchestrator path — two live content
-generation code paths coexist. Not necessarily a bug, but a real piece
of technical debt worth resolving before further multi-claim work (it's
easy to fix one path and silently leave the other stale).

## 3. Current models

Default: `LLM_PROVIDER="ollama"` (`app/core/config.py:36`), local models
`llama3.2` (text, all 5 text stages) and `llava-phi3` (vision), $0 cost,
no key required. Gemini (`gemini-flash-latest`) is wired in two
different ways, not one:

1. **`FallbackLLMProvider`** (`app/services/ai/factory.py:14-72`) — used
   only when the *primary provider call itself fails* (`ProviderError`:
   connection error, or Ollama's own exhausted-retries schema failure).
2. **Per-stage "quality retry" escalation** — five stages
   (`claim_extraction.py`, `vision_context.py`, `evidence_analysis.py`,
   `verdict.py`, `content_generation.py`) each run their own cheap
   deterministic heuristic on a *successful* Ollama response and, if it
   looks substantively bad (e.g. `_MIN_GROUNDED_SHARE=0.5`,
   `_PROMPT_ECHO_RATIO_THRESHOLD=0.20`, `_MIN_REASONING_WORDS=6`), call
   `GeminiProvider()` **directly**, bypassing the factory entirely, for
   one retry.

This second path has **no cooldown, no circuit breaker, and no shared
quota awareness with path 1** — if Gemini 429s during a quality-retry
call, the `ProviderError` propagates up uncaught. Anthropic
(`anthropic_provider.py`) exists as a third, fully-manual opt-in
(`LLM_PROVIDER="anthropic"`), not part of any cascade.

**Gemini quota/retry behavior, exactly as implemented today**
(`gemini_provider.py:132-137`): `tenacity` retries up to 3 attempts,
exponential backoff 2–20s, on `_RetryableAPIError` (which wraps any
status in `{429, 500, 502, 503, 504}` or a dropped connection) —
**this treats a daily-quota-exhausted 429 identically to a transient
5xx**, retrying 3 times over ~20 seconds before giving up. There is no
distinction between "wait a few seconds and retry" and "wait until
tomorrow," no persistent task queue, and no configuration surface
(`GEMINI_MAX_RETRIES`, `GEMINI_COOLDOWN_SECONDS`, etc. do not exist
anywhere in `config.py` or elsewhere) — this is a direct, confirmed gap
against this program's own "Gemini Quota Exhaustion Behavior" section,
built and engineered as Phase-1 work below, not assumed.

`GEMINI_API_KEY` is read in 9 places, all either a boolean presence
check or the single point it's passed into `genai.Client()`
(`gemini_provider.py:92-94`); it is never logged, printed, or written to
the DB — `app/core/logging.py:8-16` additionally redacts any structlog
field whose name ends in `key`/`secret`/`token`/`password` as a defense
-in-depth backstop, confirmed present and correctly patterned.

## 4. Current benchmark

`research/dataset/items.jsonl`: **9 items**, all Tier-1 (professional
-fact-checker-verified), **7 FALSE / 1 TRUE / 1 MISLEADING**, 5/9
`provenance`-type. **6 of 9 usable for the full paired comparison**
(item-0003 never ingestible in 3 attempts; items 0008/0009 blocked on
Gemini quota for the full-TruthLens condition). **No `split` field
exists anywhere on the dataset** — confirmed by exhaustive key
enumeration across all 9 rows; it is a single, undifferentiated
held-out set, not partitioned into dev/val/test. Sourcing hit rate is a
documented, measured $\sim$8% (2 of the first 26 fact-check articles
checked yielded a usable item) — `DATASET_CARD.md`/`DATASET_SPEC.md`
both name this as the real, load-bearing constraint on scaling.

Separately, the live Postgres dev database (currently running, queried
directly this pass) has **20 `reels` rows, 62 `claims`, 223 `sources`,
207 `evidence` rows, 38 `verdicts`** — substantially more raw material
than the 9-item frozen set, but with real duplicate re-ingestions (at
least 6 URLs ingested 2–3 times each during development) and **no
scoping flag separating dev material from benchmark material** — this
is the same Finding 2 the original `AUDIT_REPORT.md` already disclosed
and left unfixed; still true today, unchanged.

A **synthetic validator benchmark already exists**: `research/results/
validator_synthetic_benchmark_20260814.json`, n=28 (14 dev/14 test,
`"split"` field present in *this* file, unlike the real-content
dataset), 12 failure categories (A/C/D/E/F/G/H/I/J/K/L/M/N/O plus 10
valid cases). This is real, prior work — a starting point for Step 18's
100+-case adversarial suite, not a from-scratch task.

A **separate, smaller entity-consistency evaluation** exists
(`research/ENTITY_CONSISTENCY_EVALUATION.md`, 10 evidence rows / 9 real
claims, 1 genuine true positive found) — explicitly a prototype, **not
wired into production** (confirmed: zero imports of
`entity_consistency_eval` anywhere under `app/`).

## 5. Current experiments

`research/EXPERIMENT_PROTOCOL.md` documents the real pipeline (dataset
→ `backend/research/{baselines,validator,multimodal}/*.py` → `research/
results/*` → `day8_final_tables.py`/`day10_figures.py` →
`research_paper/main.tex`) and **explicitly rejected** a numbered
`EXP-NNN` ledger reorg as "complexity without justification" when it was
last touched. Confirmed: **zero files anywhere named `EXP-*` or
`*ledger*`** exist in the repo today. Three git tags mark freeze points:
`truthlens-pre-ieee`, `truthlens-day8-frozen`,
`truthlens-day9-general-fixes`.

## 6. Current metrics

Reported today, real and computed (not aspirational): reel-level
accuracy (bucket-matched), validator precision/recall/F1 (n=9, single
unadjudicated reviewer), four-way evidence-quality metric (tier
-classification/relevance/fetch-success/usable-evidence), claim-coverage
by modality (n=6), efficiency (LLM calls/claim, partial latency gap
disclosed). **Never yet separately measured, despite being logically
distinct**: claim-extraction recall against a recall-labeled ground
truth (only coverage-vs-fact-check-claim is measured, not recall against
*everything checkworthy in the post*), entity-consistency at production
scale, temporal-consistency (no check exists to measure), cross-post
detection precision/recall (no detector exists), Gemini escalation rate
as its own tracked number (present in per-stage audit logs, never
aggregated into a reported metric).

## 7. Current failure modes

21 documented, reproducible failure modes in `research_paper/main.tex`'s
Appendix (Section~XII summary + full appendix list), each with a fix and
in most cases a regression test. Categories map cleanly onto this
program's new taxonomy (Step 19): several `INGESTION`/`TRANSCRIPTION`
-class (yt-dlp error-message drift, MissingGreenlet crash),
`CLAIM_EXTRACTION`-class (schema-valid-but-empty output, four separate
occurrences across different stages), `VALIDATION`-class (UUID-leak
false-catch, reasoning/label mismatch), `RENDERING`-class (bracket
-matching truncation, missing Rupee glyph). No prior formal
`FAILURE_TAXONOMY.md` file exists under this exact name — the paper's
appendix is the closest existing equivalent and should be the seed for
it, not duplicated from scratch.

## 8. Current technical debt

- Two parallel content-generation code paths (§2, `content_generation.py`
  vs. `reel_content.py`) — one is dead-in-practice for the primary flow
  but still live and tested.
- No config surface for any LLM retry/escalation threshold — six
  different hardcoded magic numbers across five files (§3), each a
  silent single point of failure if someone changes one without
  realizing the others exist.
- `Claim.claim_type` (5-value enum: factual/opinion/prediction/satire/
  rhetorical) and the dataset's `claim_type` vocabulary (9-value:
  statistic/quote/law_policy/historical/event/visual/provenance/
  misleading_context/true_claim) are deliberately different vocabularies
  documented as such — a correct design choice, but a real source of
  confusion for anyone joining this program without reading
  `DATASET_SPEC.md`'s explanation first.
- `media_content_hash` is an exact-byte hash used only for literal re
  -upload detection — there is no perceptual/fuzzy media-matching
  capability anywhere (no `imagehash`/`opencv`/similar dependency in
  `requirements.txt`), meaning cross-post detection (Step 16) starts
  from zero, not from a partial implementation.

## 9. Current reproducibility risks

`research/REPRODUCIBILITY.md` exists and (after this session's separate
doc-consistency pass) has an accurate table/figure regeneration map.
Known, disclosed gaps: the $n{=}68$ evidence tier/stance distribution
behind one figure isn't re-derivable by a single script in every
environment (needs a live Postgres instance with the original data);
LLM sampling is unseeded, so exact-number reproduction isn't guaranteed,
only arithmetic-over-saved-numbers is. Both are named, not hidden.

## 10. Current research risks

- **$n=9$ (6 usable)** is the dominant risk to every quantitative claim
  in the paper — explicitly the top item in the paper's own Future Work
  and the unanimous #1 concern of all three simulated IEEE reviewers.
- **No dev/val/test split** on the real-content benchmark means any
  future system change validated against "the benchmark" has no
  methodologically clean way to avoid indirectly tuning against the same
  9 items repeatedly — this is a real, not yet actualized, contamination
  risk that Phase 1 below must resolve before Phase 2+ work touches the
  system.
- **No matched political-actor pairs** — RQ5 (bias) cannot be
  responsibly attempted at all until this is fixed at the sourcing
  level, not the analysis level.
- **The live dev DB's dev/benchmark data are unscoped** (§4) — a latent
  risk that any future "let's just query the live DB for more examples"
  shortcut could silently reintroduce exactly the kind of confound the
  original audit found and fixed once already.

## 11. Proposed priorities

In the free/local/deterministic-first order this program's own protocol
requires:

1. **Gemini quota/cooldown infrastructure** (config-driven, per this
   program's explicit spec) — pure engineering, zero API cost, closes a
   real gap, unblocks safe use of Gemini for everything downstream.
2. **Dataset split infrastructure + schema v2** (Step 3/4) — must exist
   *before* any new benchmark items are collected, so every new item is
   born already correctly split, never retrofitted.
3. **Claim provenance/modality fields on `Claim`** (Step 5/8) — a schema
   migration plus extraction-prompt update; free, local, high-leverage
   for the multimodal-coverage experiments already planned.
4. **Benchmark V2 collection infrastructure** (tooling, not yet the
   items themselves) — scaffolding for stratified sourcing, dedup
   against the live DB's already-known content hashes, and the new
   schema from #2.
5. Everything else in Steps 5–21 follows, gated behind these four.

---

**Repository state confirmed clean**: `git status` shows no uncommitted
changes as of this audit; latest commit `c2951cd`. This audit itself
introduces no code changes — inspection only, per Step 0's explicit
instruction not to rewrite anything yet.
