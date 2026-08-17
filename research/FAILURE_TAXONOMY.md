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
| 21 | A table-generation script's printed output and its persisted JSON silently disagreed | research_infrastructure | `tests/regression/research_infrastructure/test_day8_final_tables_variable_shadowing.py` (**new this pass** — loads the real, unmodified script via `importlib`, runs it against synthetic fixtures sized so any cross-table variable bleed is immediately obvious, and asserts the persisted summary JSON matches the correct table's data. Verified both directions live, not just written and assumed: temporarily reintroduced the exact historical shared-variable-name bug on a scratch copy, confirmed the test fails against it, then restored the real (already-fixed) file and confirmed the test passes again.) | COVERED (new) |
| 22 | A real, live global Gemini cooldown (written by concurrent real production usage against the shared dev database) makes `test_gemini_quota_scenarios.py`'s mocked scenarios short-circuit before ever reaching their scripted mock response | test_infrastructure | — | **GAP, found live during this pass**: `QuotaAwareGeminiProvider`'s global cooldown check (correct, intended behavior — avoid burning real API quota once a real exhaustion is already known) reads the same `gemini_tasks` table real production runs write to. A real quota-exhaustion event recorded by ANY concurrent real usage of the same dev database causes these tests to hit the real cooldown short-circuit instead of `MockGeminiProvider`'s scripted response, failing with `NoResultFound` (looking for a `stage="scenario-test"` row that was never created because the call never actually reached the mock). Confirmed the root cause directly: the affected tests all query `GeminiTask.stage == "scenario-test"`, correctly scoped, but a *different*, unscoped, global `status == "quota_wait"` check inside the provider itself runs first. Not fixed this pass — doing so safely needs either a fully isolated test database/schema or a way to scope the global cooldown check itself to a test context, both bigger changes than warranted mid-session; the safe, low-risk workaround used here was re-running the suite once the concurrent real script finished, confirmed clean. **Update, same day (EXP-028, `research/EVIDENCE_STANCE_TAXONOMY_V2.md`)**: the underlying constraint is now quantified, not just observed — a real `429` response body confirmed Google's free-tier cap is exactly **20 requests/day** for `gemini-3.7-flash` on this project's key. This session's own real usage (quality-retries across claim_extraction/evidence_analysis/verdict, dataset promotion, and multiple research scripts run the same day) exhausts that cap repeatedly, so this isn't an occasional collision — it's an expected, recurring state any real-Gemini-dependent test or script run late in a heavy-usage day should anticipate. |
| 23 | `wrap_untrusted()`'s delimiter defense could be structurally bypassed by untrusted text containing the literal delimiter tokens, and (independently) a blunt direct-override prompt injection got past claim_extraction 1/5 times | claim_extraction (security) | `tests/test_prompts_injection_defense.py` (**new this pass** — before this, `grep -rn "wrap_untrusted" tests/` and a search for any injection-named test file both returned nothing; zero coverage existed for a defense that processes genuinely untrusted, attacker-reachable input on every real post) | COVERED (new) |
| 24 | Verdict-label selection does not reliably weight source reliability under direct contradiction — a 0.95-reliability primary-government source supporting a claim was outweighed by a 0.20-reliability, uncited blog contradicting it in 0/14 real trials (0/7 before, 0/7 after an attempted prompt fix); one run paired a wrong label with maximum (1.0) stated confidence | verdict | `tests/test_validation.py` (8 new tests: `test_downgrades_the_exp029_reliability_weighted_conflict_shape`, `::test_downgrades_the_reverse_direction_reliability_mismatch`, `::test_outdated_label_is_covered_by_the_reliability_check`, `::test_passes_when_verdict_correctly_favors_the_higher_reliability_source`, `::test_reliability_check_does_not_fire_on_a_close_reliability_gap`, `::test_reliability_check_does_not_fire_with_only_one_stance_cited`, `::test_reliability_check_never_fires_for_plain_object_placeholders`) | COVERED (new, EXP-030): the prompt-only fix in EXP-029 was measured insufficient, exactly as this entry originally recorded, but the deterministic validator check named there as the likely real fix was then built, evaluated (10/10 synthetic ground truth, 14/14 of EXP-029's own real observed wrong trials caught, 0/5 false positives on the genuinely ambiguous sanity-check trials, 0/34 interaction with the existing adversarial benchmark), and — clearing the same bar Checks 6/7 were held to — integrated as Check 8 (`app/pipeline/validation.py`, `ValidationStatus.downgraded_reliability_mismatch`, migration `403a421884b7`). Full detail: `research/CONTRADICTORY_SOURCES_V2.md`. |
| 25 | Two real SSRF-guard coverage gaps: `auto_fetch`'s photo-post fallback validated the operator-supplied post URL but never the second URL it extracts from that page's own `og:image` tag; the default DuckDuckGo search provider fetches arbitrary search-result URLs with no SSRF guard at all, contradicting `docs/SECURITY.md`'s own (now-corrected) claim that only fixed-base-URL requests exist outside `auto_fetch` | security (ingestion, retrieval) | `tests/test_url_downloader_photo_fallback.py::test_fetch_photo_via_og_tags_rejects_an_internal_image_url` (**new this pass**); existing `tests/test_url_safety.py` coverage of the guard itself; `tests/test_duckduckgo_search_metadata.py` updated to mock the guard so its trafilatura-focused tests keep testing what they intend to | COVERED (new): both call sites now call `app.core.url_safety.require_public_http_url()`. A related, disclosed, NOT-fixed gap remains: neither call site re-validates a redirect target after the initial check, since both use `httpx`'s `follow_redirects=True` — a real fix (disable auto-redirect, re-validate each hop) is named in `docs/SECURITY.md` §3 but not built this pass. |

## Summary

22 of 25 entries have real, passing regression-test coverage (16
pre-existing + 6 written this pass, including #21, #23, #24, and #25
closed this same pass). 3 are honest, documented gaps, not silently
omitted:

- **#6** and **#11** are gaps *by design* — no production fix exists yet
  for either, so there is nothing yet to protect with a test. Writing a
  test now would either test an unintegrated research prototype (giving
  false confidence about production behavior) or test-guard a
  deliberately-not-fixed limitation (implying a fix commitment that
  hasn't been made).
- **#22** is a genuine, real, newly-found gap in test *infrastructure*
  rather than production code — the production behavior it's colliding
  with (a global cooldown) is correct and desired. Named explicitly as a
  candidate for a future pass (proper test-database isolation) rather
  than left implicit.

## How to keep this current

Every future entry added to `research_paper/main.tex`'s failure-mode
appendix should get a row here in the same pass, per Step 19's process:
root-cause, regression test (or an honest gap marker with a reason), fix,
re-run the regression suite, re-run validation, measure collateral
damage. This file existing is itself the fix for a smaller, meta-level
version of failure #3/#21 (two things that are supposed to describe the
same reality silently drifting apart) — keep it that way by updating it
in the same commit as the paper, not a follow-up one.
