# FAILURE_TAXONOMY.md

Status: 2026-08-14. `research/RESEARCH_ROADMAP_V2.md` Phase 1, governing
brief Step 19/Step 7. This is the canonical index for the 21 failure
modes already published in `research_paper/main.tex`'s Appendix
(`\label{sec:appendixtaxonomy}`) — every entry below carries the same
description already in the paper, plus what this pass newly added: an
explicit pointer to the regression test that protects it (existing test
file, or a new one written this pass), or an honest `GAP` marker where
none exists.

**This does not re-litigate or duplicate the paper's own text.** Full
descriptions live in the paper; this document's job is the
failure_id → regression-test mapping the paper doesn't need and this
program's own protocol requires (Step 19: "EVERY important failure must
produce... a regression test").

| # | Failure (short name) | Category | Regression test | Status |
|---|---|---|---|---|
| 1 | Schema-valid, substantively empty output (4 stages) | claim_extraction / evidence | `test_claim_extraction_substantive.py`, `test_content_generation_completeness.py`, `test_verdict_reasoning_quality.py`, `test_evidence_analysis_substantive.py` | COVERED (one test per stage) |
| 2 | Verbatim-but-misattributed quotation | claim_extraction | `test_reel_content_quote_attribution.py` | COVERED |
| 3 | Silent verdict/presentation inconsistency | aggregation | `test_fact_check_detail_endpoint.py` | COVERED |
| 4 | Bracket-matching truncation bug | database (rendering/display) | `test_reel_content_display_text.py::test_strips_validation_note_containing_a_python_list_repr` | COVERED |
| 5 | Unrepresentative thumbnail selection | database (media) | `test_thumbnail_selection.py` | COVERED |
| 6 | Entity confusion between similarly-named organizations | entity | — | **GAP, by design**: the paper's own text states this is "not currently checked anywhere in the pipeline" — there is no production fix to protect yet. The research-only prototype (`backend/research/entity_consistency_eval.py`) has its own evaluation writeup (`ENTITY_CONSISTENCY_EVALUATION.md`) but is explicitly not integrated, so a `tests/regression/entity/` test would have nothing real to exercise. Revisit once/if Phase 4 (`RESEARCH_ROADMAP_V2.md`) integrates it. |
| 7 | Downgraded reasoning reused as trusted input downstream | validator | `test_reel_content_display_text.py::test_safe_reasoning_text_hides_reasoning_from_a_downgraded_verdict`, `::test_safe_reasoning_text_hides_reasoning_for_every_downgrade_reason` | COVERED |
| 8 | Single-digit fabrication in generated headlines | claim_extraction (content generation) | `test_headline_number_grounding.py` | COVERED |
| 9 | Vision-read text silently discarded before claim extraction | claim_extraction | `test_claim_extraction_vision_text.py` | COVERED |
| 10 | Missing glyph rendering as a blank box | database (rendering) | `test_render_utils_char_substitution.py` | COVERED |
| 11 | Vision-transcription accuracy, left unresolved | — | — | **N/A, by design**: paper explicitly states this was deliberately not patched ("we chose not to patch it with an unverified heuristic"). No fix exists to regression-test. |
| 12 | Empty-string claims passing schema validation | claim_extraction | `test_claim_extraction_substantive.py` (same fix as #1's claim-extraction case) | COVERED |
| 13 | Except clause written against the wrong SDK exception hierarchy | research_infrastructure (provider layer) | `test_gemini_provider.py::test_rate_limit_exhaustion_becomes_provider_error_not_a_crash` | COVERED |
| 14 | Baseline architecture silently inheriting a rescue mechanism under evaluation | research_infrastructure | `tests/regression/research_infrastructure/test_baselines_never_use_the_gemini_fallback_factory.py` (**new this pass** — no test existed before; this was previously caught only by manual smoke-testing, per the paper's own text) | COVERED (new) |
| 15 | A second, differently-phrased "no video" error masking a fetchable photo post | retrieval (ingestion) | `test_url_downloader_photo_fallback.py` | COVERED |
| 16 | UUID hex fragments leaking through citation markup as fake unsupported numbers | validator | `test_validation.py::test_ignores_numbers_inside_internal_citation_markup`, `::test_ignores_numbers_inside_single_bracket_citation_markup` | COVERED |
| 17 | 47.1% empty explanations in per-source evidence analysis | evidence | `test_evidence_analysis_substantive.py` (same fix as #1's evidence-analysis case) | COVERED |
| 18 | Recurring vision-output prompt echo | claim_extraction (vision) | `test_vision_context_substantive.py` | COVERED |
| 19 | A label confidently contradicting the model's own stated reasoning | validator | `test_validation.py::test_downgrades_when_reasoning_says_no_evidence_but_label_is_confident`, `::test_downgrades_real_durrani_meeting_case_from_day5_audit`, `::test_no_evidence_phrase_is_a_noop_when_verdict_is_already_unverified` | COVERED |
| 20 | A `MissingGreenlet` crash from a stale ORM read after rollback | database | `tests/regression/database/test_missing_greenlet_after_rollback.py` (**new this pass** — the production instance in `app/api/routers/reels.py`'s `quick_fact_check()` had no regression test at all before this; confirmed via repo-wide grep for "greenlet"/"MissingGreenlet" across `app/` and `tests/`, which found the fix's own comment but zero test coverage of it) | COVERED (new) |
| 21 | A table-generation script's printed output and its persisted JSON silently disagreed | research_infrastructure | — | **GAP**: `backend/research/day8_final_tables.py` is a one-off analysis script, not pipeline code with an existing test harness pattern to extend. A meaningful regression test would need to construct a synthetic multi-loop scenario reproducing the exact variable-shadowing shape and assert the persisted JSON matches stdout — worth doing, not done this pass (named here rather than silently skipped). |

## Summary

18 of 21 entries have real, passing regression-test coverage (16
pre-existing + 2 written this pass). 3 are honest, documented gaps, not
silently omitted:

- **#6** and **#11** are gaps *by design* — no production fix exists yet
  for either, so there is nothing yet to protect with a test. Writing a
  test now would either test an unintegrated research prototype (giving
  false confidence about production behavior) or test-guard a
  deliberately-not-fixed limitation (implying a fix commitment that
  hasn't been made).
- **#21** is a genuine, real gap: a fixable one, just not fixed this
  pass. Named explicitly as a candidate for a future pass rather than
  left implicit.

## How to keep this current

Every future entry added to `research_paper/main.tex`'s failure-mode
appendix should get a row here in the same pass, per Step 19's process:
root-cause, regression test (or an honest gap marker with a reason), fix,
re-run the regression suite, re-run validation, measure collateral
damage. This file existing is itself the fix for a smaller, meta-level
version of failure #3/#21 (two things that are supposed to describe the
same reality silently drifting apart) — keep it that way by updating it
in the same commit as the paper, not a follow-up one.
