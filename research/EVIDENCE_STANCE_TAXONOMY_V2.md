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

## Re-run with the confound fixed (EXP-028) -- the concrete next step above, done

`backend/research/evidence_reasoning_v2/compare_stance_taxonomies_v2.py`
is identical to the original script except the new-taxonomy call now
goes through the same `_explanation_looks_substantive` check + Gemini
quality-retry `app/pipeline/evidence_analysis.py` itself uses, so both
sides of the comparison get the same real-world quality safety net.

**Result: still inconclusive, but for a newly-identified, concrete
reason rather than an uncontrolled one.** Two full runs:

- **Attempt 1**: every retry attempt hit a still-active Gemini cooldown
  (`next_retry_at=2026-08-17T23:01:26Z`, a real quota exhaustion from
  concurrent work earlier this session) — 0/20 retries fired, clean
  rows only inched up to 6/20 (vs. the original 4/20) from ordinary
  sampling variance, not the fix.
- **Attempt 2**, run after that cooldown's own end time: the very first
  retry attempt returned a real, fresh `429` from the Gemini API,
  revealing the actual constraint plainly for the first time this
  session: **`generativelanguage.googleapis.com/generate_content_free_tier_requests`
  is capped at 20 requests/day for `gemini-3.7-flash`** on this
  project's key. That set a new cooldown (`until
  2026-08-18T00:02:13Z`), so the remaining 19 items' retry attempts all
  failed the same way. Clean rows: 5/20.

This means the substantiveness-retry fix is correctly wired (confirmed
by the real `429` response body, not a code path that silently no-ops)
but the daily Gemini free-tier quota is simply too small to cover a
20-item comparison on top of this session's other real Gemini usage the
same day — a hard, external, non-code constraint, not a bug in this
experiment's fix. See `research/FAILURE_TAXONOMY.md` #22, updated with
this concrete number.

One clean row from attempt 2 is worth reporting on its own merits, with
an honest caveat: claim "The Indian central government introduced new
regulations requiring social media platforms to remove content within
three hours..." was originally `contradicts` (correctly — the real
source describes a 2-hour window for some content, 3-hour for
directed-takedown content) and the new taxonomy re-labeled it
`temporally_mismatched`, reasoning that the source's rules were dated
February 10, 2026, a "different time period." **This reclassification
looks like a real taxonomy-application error, not an improvement**: the
source's substantive disagreement (different specific deadline) is what
actually matters, not the change being dated — the original 4-category
`contradicts` reads as the more accurate label here. Reported honestly
rather than cherry-picked as a positive example, since it's the only
clean instance of the new taxonomy actually being used on a real
"contradicts" row.

**Overall conclusion, combining the original run and both re-runs
(three independent attempts, clean-row counts 4/20, 6/20, 5/20)**: this
experiment remains genuinely inconclusive about whether the 8-category
taxonomy helps -- not because of an uncontrolled confound anymore (that
part is fixed and verified), but because the real, external daily
Gemini quota is too small relative to this session's overall real usage
to reliably produce a large clean sample on demand. A future pass with
either a fresh daily quota reserved specifically for this comparison,
or a paid tier, would be needed for a real answer -- not attempted
further this pass.

## Raw data

`research/results/evidence_stance_taxonomy_comparison_20260818.json`
(original run, all 20 rows). `research/results/evidence_stance_taxonomy_comparison_v2_20260818.json`
(EXP-028 re-run, most recent of the two attempts; the first attempt's
output was overwritten by the second run at the same path, with its
numbers preserved above and in `experiments/registry.jsonl`).
Generators: `backend/research/evidence_reasoning_v2/compare_stance_taxonomies.py`,
`backend/research/evidence_reasoning_v2/compare_stance_taxonomies_v2.py`.
