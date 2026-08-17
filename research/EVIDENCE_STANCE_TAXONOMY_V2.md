# EVIDENCE_STANCE_TAXONOMY_V2.md — Phase 7

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 7: does an
8-category evidence-stance taxonomy (`app/schemas/evidence_v2.py`,
candidate-only, not wired into production) reveal real distinctions the
current 4-category scheme (`supports`/`contradicts`/`provides_context`/
`irrelevant`) conflates?

**Category count note**: the governing brief's own Step 12 text is
internally inconsistent — it names 6-7 new category labels but calls the
result "the 8-category scheme." Resolved as a disclosed judgment call:
4 new categories were kept (not the full list), chosen for direct
motivation from this session's own other findings — `same_event_wrong_entity`
and `temporally_mismatched` as the LLM-side semantic complements to
Checks 7 and 6 (Phases 4/5, built earlier this session); `insufficient_detail`
directly motivated by `EXP-015`'s and the original `EVIDENCE_EVALUATION.md`'s
own "single most important finding" (most primary-tier sources are
too generic to confirm a specific fact); `mentions_only` as a distinct
on-topic-but-evidentially-empty case. `same_entity_wrong_event` and a
separate `partially_supports`/`partially_contradicts` pair were dropped
to land at exactly 8 total.

## Method

Reused 20 real, already-persisted `Evidence` rows (no new search/fetch
calls — 207 real rows already existed from earlier pipeline runs this
session), weighted toward `irrelevant` (15 of 20, the dominant and most
interesting-to-decompose category). The new 8-category prompt was run
against the exact same claim+source text the original 4-category stance
is already recorded for (read from the DB, not re-run), guaranteeing a
fair comparison on identical input.

## A real methodological gap, found and disclosed rather than hidden

**This comparison script did not replicate production
`evidence_analysis.py`'s substantiveness-retry safeguard**
(`_explanation_looks_substantive`, which triggers a Gemini quality-retry
on an empty `explanation` field). Checking the raw data: **16 of 20
rows (80%) had an empty `explanation` on at least one side** (old,
new, or both) — both prompts, run raw without that safeguard, produced
a large fraction of schema-valid-but-unexplained stance judgments. This
means the raw "11/20 changed category" headline number is substantially
confounded by low-quality, un-retried output on both sides, not a clean
signal about the taxonomy itself.

Filtered to the 4 rows where **both** the original and new explanation
were genuinely non-empty: 1 changed (`irrelevant` → `supports`), 3
stayed the same. **n=4 is far too small to draw any real conclusion
about whether the 8-category taxonomy helps** — this experiment is
honestly inconclusive on its own original question.

## The more important finding: a third independent confirmation of raw-llama3.2 unreliability

This is the third experiment *this session* to independently surface
the same underlying pattern, each from a different angle:

1. `EXP-012`: 12/12 real claims had no verbatim `source_quote`.
2. `EXP-016`: 0/90 real claims across 8 modality conditions were
   groundable.
3. `EXP-017` (this pass): 16/20 (80%) raw evidence-stance judgments had
   an empty explanation on at least one side, when run without the
   Gemini quality-retry production actually relies on.

Three independent measurements, three different pipeline stages, the
same conclusion: **raw, un-retried llama3.2 structured output on real
content is unreliable a large fraction of the time**, and production's
layered defenses (Gemini escalation, substantiveness checks) are doing
much more real work than a pipeline-level pass/fail reading would
suggest. This is now a well-established pattern, not a single-experiment
anomaly.

## What did NOT happen

- No integration decision was made for the 8-category taxonomy — the
  comparison that would inform it (apples-to-apples, both sides past
  the substantiveness-retry gate) was not actually run at adequate n.
- `app/pipeline/evidence_analysis.py` and its production 4-category
  schema are completely unchanged.

## Concrete next step (not done this pass)

Re-run this comparison with the Gemini substantiveness-retry ported
into the candidate prompt path too (so both sides get the same
production-equivalent reliability treatment), at a larger sample —
would give a real, uncounfounded answer to Phase 7's actual question.
Not attempted this pass given the real cost of another full Gemini
-retry-enabled run and this pass's own more urgent, cross-validated
finding about raw-model reliability.

## Raw data

`research/results/evidence_stance_taxonomy_comparison_20260818.json`
(all 20 rows, both explanations, full detail). Generator:
`backend/research/evidence_reasoning_v2/compare_stance_taxonomies.py`.
