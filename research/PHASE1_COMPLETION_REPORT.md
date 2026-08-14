# PHASE1_COMPLETION_REPORT.md

Status: 2026-08-14. Governing brief's Final Report requirements. Six
commits on `main`: `d4a7d77`, `3912b32`, `cd1ded8`, `c974c97`, `2962cc4`,
`89e33cc`, `b2bbe37` — each independently tested and committed, on top of
the Phase 0 audit commit `6cc1c90`.

## 1. What was implemented

A centralized, quota-aware Gemini call path replacing two previously
-independent ones; claim-level provenance/modality/confidence fields,
populated deterministically (modality) or from the LLM (confidence) at
extraction time; a versioned dataset-split schema (v2) migrating the
existing 9-item benchmark without touching it in place; retroactive
database scoping distinguishing benchmark from development records;
benchmark-collection tooling (candidate tracker + composition reporting);
a regression-test taxonomy mapping all 21 known failure modes to real
tests (closing 2 genuine gaps found this pass); an experiment ledger
backfilled with 8 major past experiments; and a mock Gemini provider with
7 quota state-machine scenario tests.

## 2. Files changed

Verified via `git diff --name-status 6cc1c90..HEAD` (from immediately
after the Phase 0 audit commit to the end of this phase) — **31 added,
17 modified**, exactly:

**Added (31)**: `backend/alembic/versions/72b8bd05d670_*.py`;
`backend/app/services/ai/gemini_quota.py`;
`backend/research/benchmark_v2/{candidate_tracker,composition_report,
migrate_v1_to_v2_schema,tag_existing_benchmark_reels}.py`;
`backend/tests/mock_gemini.py`; `backend/tests/regression/` (9 category
`__init__.py` files + its own `__init__.py` + 2 new test files:
`database/test_missing_greenlet_after_rollback.py`,
`research_infrastructure/test_baselines_never_use_the_gemini_fallback_factory.py`);
`backend/tests/test_{benchmark_candidate_tracker,benchmark_composition_report,
claim_provenance,dataset_scoping,experiment_registry,gemini_quota_scenarios}.py`;
`experiments/{README.md,registry.jsonl}`; `research/{BENCHMARK_COLLECTION_GUIDE,
DATASET_SCHEMA_V2,FAILURE_TAXONOMY}.md`; `research/dataset/items_v1_as_v2_schema.jsonl`.

**Modified (17)**: `backend/app/core/config.py` (6 new Gemini settings);
`backend/app/db/models.py` (6 new enums, `Reel`/`Claim` new columns, new
`GeminiTask` table); `backend/app/services/ai/{base,factory,
gemini_provider,ollama_provider,anthropic_provider,prompts}.py`;
`backend/app/pipeline/{claim_extraction,vision_context,evidence_analysis,
verdict,content_generation}.py`; `backend/app/schemas/claim.py`;
`backend/tests/conftest.py`; `backend/tests/test_claim_extraction_{grounding,
substantive}.py`.

(`research/AUDIT_REPORT_V2.md` and `research/RESEARCH_ROADMAP_V2.md` were
Phase 0 deliverables, committed at `6cc1c90` itself — the baseline this
diff is measured from — and are correctly *not* counted again here.)

## 3. Database migrations

One: `72b8bd05d670` (applied to the live dev database). Adds
`gemini_tasks` table (new); `claims.source_modalities`/
`extraction_confidence`/`confidence_type`/`verifiability`/
`provenance_detail` (all nullable, unbackfilled by design — populated
going forward only); `reels.dataset_type`/`benchmark_version`/
`benchmark_split` (`dataset_type` NOT NULL with `server_default=
'development'`, correctly backfilling all 20 pre-existing rows). Fully
additive — no column dropped, renamed, or made more restrictive; no data
loss possible. Downgrade path defined and symmetric for every change.

A second, non-schema live-database write: `tag_existing_benchmark_reels.py`
retroactively set `dataset_type=benchmark`/`benchmark_version=v1`/
`benchmark_split=dev` on the 11 existing reel rows (across 9 distinct
URLs, some re-ingested during development) matching the frozen
benchmark's source URLs. Verified after running: 11 benchmark + 9
development = 20, matching the pre-existing total exactly (no rows
created or lost).

## 4. Tests created

38 new tests across 8 files (full list and rationale in
`PHASE1_RESEARCH_NOTES.md`'s "Tests performed" section) plus 2 files with
pre-existing tests, updated for a new required field.

## 5. Tests passed

**201 of 201** (full suite, `cd backend && ./.venv/bin/python -m pytest -q`),
confirmed as the very last step before writing this report.

## 6. Tests failed

None, currently. Two were found and fixed *during* this phase (not left
failing): a real test-isolation bug (the Gemini quota singleton's
memoized delegate ignoring a later test's monkeypatch) and a real
design bug in the composition-report script (conflating "never
ingested" with "zero claims extracted"). Both are described in detail in
their respective commit messages and in `PHASE1_RESEARCH_NOTES.md`.

## 7. Benchmark schema

`research/DATASET_SCHEMA_V2.md`, full field table there. Headline
change from v1: explicit `benchmark_version`/`split` fields, and
`audio_available`/`ocr_available`/`caption_available`/
`visual_information_available`/`cross_post_possible`/`cross_post_verified`
as real, DB-queried-not-guessed fields (previously implicit or absent).
`items.jsonl` (v1) is untouched; `items_v1_as_v2_schema.jsonl` presents
the same 9 items' same facts under the new schema, generated by
`migrate_v1_to_v2_schema.py` (re-runnable, not hand-edited).

## 8. Dataset isolation design

Two independent layers, both tested: (a) file-level — `benchmark_version`
strings (`"v1"`, future `"v2"`) never overwrite each other, enforced by
convention plus this report's own review, not yet by a script-level
guard; (b) database-level — `dataset_type` (development/benchmark/
regression/synthetic) on every `Reel` row, defaulting to `development`
so a query that forgets to filter never silently includes benchmark data
by accident, and vice versa. `tests/test_dataset_scoping.py` proves both
directions of this with real inserted rows, not just schema assertions.

## 9. Gemini architecture

Before this phase: two independent call paths (`FallbackLLMProvider`'s
connection-failure fallback; five separate per-stage quality-retry
escalations, each constructing `GeminiProvider()` directly), no shared
state, no cooldown, no persistence, no config surface. After: every
Gemini call goes through `get_gemini_provider()` — one process-lifetime
singleton wrapping the real `GeminiProvider`, gating every call on
`GEMINI_ENABLED`/`GEMINI_MAX_CALLS_PER_RUN`/`GEMINI_MAX_CALLS_PER_ITEM`/
current cooldown state, and persisting one `GeminiTask` row per attempt.

## 10. Gemini quota behavior

429/`RESOURCE_EXHAUSTED`/quota-exceeded messages are classified
`QUOTA_EXHAUSTED` (long cooldown, `GEMINI_COOLDOWN_SECONDS`, default
3600s) and kept distinct from a plain rate-limit 429 (`RATE_LIMITED`,
short cooldown, `GEMINI_RETRY_BASE_SECONDS * 30`, default 60s) and a
transient 5xx/timeout (`TRANSIENT`, retried within the existing
per-provider tenacity backoff, then `PERMANENT_FAILURE` once
`GEMINI_MAX_RETRIES` is reached). Callers catch the new
`GeminiUnavailableError` specifically and keep their existing local
-model result rather than crash — verified end-to-end through a real
pipeline stage (`vision_context.py`) in scenario F of
`test_gemini_quota_scenarios.py`, not just at the quota-manager level in
isolation.

## 11. Remaining Gemini limitations

No cross-process/cross-worker coordination — `_calls_this_run`/
`_calls_by_item` are per-process in-memory counters (the "current
execution" concept from Step 3), so a multi-worker deployment would have
one call budget per worker, not a shared one; cooldown state itself
*is* shared (it's read from the database), just not the raw counters.
Cache lookups (`input_hash`) are exact-match only — no near-duplicate or
semantic cache. Never tested against the real Gemini API this phase
(deliberately, per Step 11 — only the mock).

## 12. Claim provenance design

`source_modalities` and `provenance_detail` are derived deterministically
by substring-matching a claim's (required-verbatim) `source_quote`
against the reel's transcript/OCR/caption/vision-context text — never
asked of the LLM, and left `null` (not guessed) for claims with no quote.
`extraction_confidence` is the one field actually asked of the LLM,
persisted with `confidence_type="MODEL_CONFIDENCE"` fixed at write time,
documented explicitly as the model's own self-reported number, never a
calibrated probability. `verifiability` (VERIFIABLE/NOT_VERIFIABLE/
UNCERTAIN) sits alongside the pre-existing boolean `verifiable` column
(kept, unchanged) and surfaces a case that boolean silently collapses:
verifiable=true paired with a non-factual claim_type.

## 13. Benchmark collection workflow

`research/BENCHMARK_COLLECTION_GUIDE.md` + `candidate_tracker.py`: a
7-state eligibility machine (DISCOVERED through ELIGIBLE, plus REJECTED/
UNRESOLVED), JSONL-backed, full history retained per candidate. **Zero
candidates were added this phase** — this is infrastructure only, per
Step 8's explicit instruction not to collect benchmark items yet.
Promotion from ELIGIBLE to a real dataset row stays a manual decision
(dedup + split assignment need real judgment, not a script default).

## 14. Regression framework

`tests/regression/` with the 9 named categories. 18 of the 21 published
failure modes have real, verified test coverage (16 pre-existing + 2
written this phase, closing genuine gaps found via a full repository
grep, not assumed closed); 2 are honest by-design gaps (no production fix
exists yet to protect); 1 is a real, still-open gap, named rather than
silently skipped. Full mapping: `research/FAILURE_TAXONOMY.md`.

## 15. Remaining risks

- The existing 9-item benchmark still has no genuine TEST split — see
  `PHASE1_RESEARCH_NOTES.md`. The paper's headline comparison is
  unaffected (it never claimed one), but any *future* system change
  claiming to be validated against a "held-out" set needs new `v2` items
  collected under the stricter discipline, not a relabeling of `v1`.
- `day8_final_tables.py`'s variable-shadowing bug class (#21) has no
  regression test yet.
- No dedicated secret-scanning tool available in this environment; the
  API-key security check (item 12 above; `GEMINI_API_KEY` confirmed
  never logged, stored, or committed) was done via manual grep, a real
  but narrower check than a dedicated tool would run.
- The two parallel content-generation code paths noted in
  `AUDIT_REPORT_V2.md` §8 (technical debt) are unchanged by this phase.

## 16. What should happen in Phase 2

Per `RESEARCH_ROADMAP_V2.md`: claim-extraction recall-first prompt work
(building on this phase's new confidence/modality fields, which now
exist to *measure* whether a recall-focused rewrite actually helps);
first real use of the benchmark-collection tooling to source `v2`
candidates and populate genuine validation/test splits; an experiment
checking whether `extraction_confidence` correlates with anything real
(named in `PHASE1_RESEARCH_NOTES.md` as a concrete next experiment, not
yet run).

## 17. What has NOT yet been completed

No new benchmark items collected (deliberate, Step 8). No entity
-consistency or temporal-consistency check added to production validation
(Phases 4/5 of the roadmap, not this one). No real Gemini API call made
or tested against this phase — only the mock. `day8_final_tables.py`
regression test not written. Cross-process Gemini call-budget
coordination not implemented (single-process counters only). The
research paper is untouched, per Step 13's explicit instruction not to
rewrite it yet.

---

## PHASE 1 STATUS: COMPLETE

(for the scope this phase set out to cover — foundation infrastructure,
not benchmark expansion, which remains explicitly out of scope per Step
8 and is Phase 2's job.)

**FREE WORK COMPLETED**: all of it — every item in this report was
free/local/deterministic work; zero Gemini API calls were made against
the real service this phase.

**GEMINI WORK COMPLETED**: the quota-management infrastructure itself
(code + migration + mock-based tests). No real-API experiments run.

**GEMINI WORK PAUSED**: none paused mid-flight — none was attempted
against the real API this phase, by design.

**FILES CREATED**: 31 (listed in full under item 2).

**FILES MODIFIED**: 17 (listed in full under item 2).

**DATABASE CHANGES**: 1 migration (additive only) + 1 retroactive data
-tagging script, both applied and verified live.

**TESTS**: 201/201 passing (38 new this phase).

**FAILURES**: none outstanding; 2 found and fixed during development
(described in item 6).

**RESEARCH IMPACT**: no accuracy claim changes (none were attempted).
The real research impact is methodological: the existing benchmark's
items are now formally, honestly documented as unable to retroactively
serve as a TEST split, and the infrastructure to build a real one exists
for the first time.

**NEXT PHASE**: `RESEARCH_ROADMAP_V2.md` Phase 2 (claim extraction
improvement), gated behind actually sourcing enough `v2` benchmark
candidates via the tooling this phase built.
