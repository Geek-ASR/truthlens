# ADVERSARIAL_EVALUATION_V2.md — Phase 11 (bounded slice)

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 11: a full
end-to-end adversarial suite (Step 18: 20 categories, 100+ cases, whole
pipeline). **Honest scope disclosure**: the full build was judged not
achievable within this session — several of Step 18's categories
(AI-generated image, edited video, OCR/audio corruption as a genuine
input-signal problem rather than a text-content problem) need real
external media-generation tooling this project does not have and this
pass does not build. What follows is a real, bounded slice: 6 real,
hand-constructed adversarial *text-content* cases run through the real,
unmodified `app.pipeline.claim_extraction.extract_claims()` — the
whole-pipeline requirement satisfied for the one stage this pass covers,
not simulated or mocked, and not claimed to be the full 20-category
suite.

## Result: 0/6 crashes

Real, positive robustness finding: no adversarial input caused an
uncaught exception. Per-case detail:

| Case | Outcome | Claims |
|---|---|---|
| `garbled_ocr` | resolved | 0 |
| `caption_transcript_contradiction` | resolved | 1 |
| `extremely_short` | resolved | 0 |
| `mixed_language_chaos` | resolved | 2 |
| `repetitive_spam` | resolved | 1 |
| `near_max_tokens` | resolved | 0 (confounded — see below) |

## Real findings, each genuine and disclosed as found

- **Garbled OCR and near-empty transcript both correctly produce zero
  claims, not hallucinated ones.** Safe, graceful degradation on the two
  clearest "nothing real here" cases.
- **Caption/transcript contradiction did not produce a hallucinated
  merged claim.** Given a caption about a Delhi protest and a completely
  unrelated transcript (a baking recipe), the extractor surfaced only
  the caption-derived claim and silently dropped the recipe content
  entirely — a safe outcome (no false synthesis), but it also means
  **no signal was raised that the two inputs disagree**. This project
  has no check anywhere for input-signal internal consistency (distinct
  from any of the 7 validator checks, which all operate on verdict
  reasoning vs. evidence, never on claim-extraction's own multi-signal
  inputs) — a real, structural gap, named here for the first time this
  session, not fixed.
- **Mixed-language chaos (Hindi/Urdu/English interleaved) extracted only
  the English-script portions.** Both real extracted claims come from
  the English segments; the Hindi and Urdu segments produced nothing,
  even though the constructed sentence was a single continuous thought
  spanning all three scripts. A real, disclosed possible multilingual
  bias — genuinely checkworthy content expressed only in a non-Latin
  script may be silently dropped rather than extracted or flagged as
  unparseable. Worth a dedicated follow-up, not chased further this pass.
- **Repetitive spam (40x the same sentence) collapsed to exactly 1
  claim**, not 40 near-duplicates — a good result, though this pass
  cannot tell whether this reflects the extractor's own behavior or
  this session's earlier deduplication work (`_deduplicate_claims`,
  Phase 2) — both operate before persistence, and this script does not
  distinguish which one is responsible.
- **`near_max_tokens` is a genuine confound, not a clean finding.** The
  raw log shows llama3.2 DID produce 1 claim initially, which then
  triggered the existing "ungrounded, retry via Gemini" quality check —
  but that retry hit a REAL `QUOTA_EXHAUSTED` error (Gemini's free-tier
  daily quota, exhausted by this session's own cumulative usage across
  many earlier experiments), and the fallback path returned 0 claims.
  This is the SAME quota-aware cooldown behavior verified correct in
  `EXP-010` — not a new bug — but it means this specific case's 0-claim
  result reflects quota exhaustion timing, not a clean measurement of
  how the pipeline handles long/repetitive content on its own. Reported
  honestly as inconclusive, not presented as a finding about length.

## What did NOT happen

- No categories requiring real media generation (AI-generated image,
  edited video) were attempted.
- No post-claim-extraction stages (research_planning, evidence
  retrieval, verdict) were run for these adversarial cases — this pass
  is bounded to claim_extraction's own robustness.
- Not re-run with fresh Gemini quota to get a clean `near_max_tokens`
  read — the honest, disclosed limitation stands rather than being
  silently worked around.

## Follow-up (EXP-031): Step 18 category #19, "multiple claims"

A distinct category from anything above: does compound-sentence
splitting (`CLAIM_EXTRACTION_SYSTEM_PROMPT`'s own instruction --
"Compound statements... must be split into separate atomic claims")
hold up against adversarial compound sentences? 6 real cases
(causal chains, multi-actor conjunctions, same-subject compound
actions, attributed nested sub-claims, numeric compounds across two
time periods, and an internally-tense compound), run through the real
`extract_claims()`.

**A methodology mistake, caught and corrected before being reported as
a result**: this experiment's own metric (claim count $\geq$ an
expected minimum) is too crude -- it can't distinguish *correct* atomic
splitting from *pathological over-fragmentation*, and initially scored
one case as "meeting expectations" that, read manually, clearly wasn't.
Corrected below rather than reported as designed.

| Case | Claims | Qualitative outcome |
|---|---|---|
| `causal_chain_three_deep` | 3 | Clean: each causal link is its own coherent, verifiable claim |
| `three_way_conjunction_different_actors` | 3 | Clean: 3 independent actor claims, the opinion one correctly marked non-verifiable |
| `compound_same_subject_two_actions` | 3 | Mostly clean, one inconsistency (see below) |
| `attribution_with_nested_sub_claims` | 0 | **Real failure: zero claims extracted** |
| `numeric_compound_two_time_periods` | 7 | **Real failure: pathological over-fragmentation, not correct splitting** |
| `contradictory_compound_tension` | 3 | Clean: each side of the tension is its own coherent, verifiable claim |

**4 of 6 cases show genuinely correct atomic decomposition** -- multi
-actor conjunctions and causal chains, exactly the pattern the prompt's
own worked example targets, are handled well.

**A real, novel failure mode: pathological over-fragmentation.** The
numeric-compound case ("Inflation rose to 8.2% in January... then fell
to 5.4% in February...") did not produce the 2 coherent claims a
correct reading would give -- it produced 7 incomplete fragments:
`"inflation rose"`, `"rose to 8.2%"`, `"in January this year"`,
`"fell to"`, `"to 5.4%"`, `"in February"`,
`"according to the latest government data"`. None of these fragments is
independently checkable on its own; several (`"rose to 8.2%"` with no
subject) are not even grammatical claims. A naive claim-count metric
would call this a success (7 $\geq$ 2 expected) -- it is the opposite: a
distinct failure mode from every other case in this document, over
-splitting rather than under-splitting or merging, not previously
observed this session.

**A real, complete extraction failure**: the attribution case ("According
to police, the accused confessed to the robbery and named two
accomplices who are still at large") produced zero claims -- both
llama3.2's raw attempt and the Gemini quality-retry failed, the latter
hitting the same real, quantified `429` quota exhaustion documented in
`FAILURE_TAXONOMY.md` #22 (20 requests/day, already exhausted by this
session's own concurrent usage). Whether llama3.2 alone would have
produced something reasonable without the retry is not established --
disclosed as inconclusive on that specific point, consistent with this
document's own `near_max_tokens` precedent above, rather than re-run
speculatively.

**A minor, disclosed inconsistency**: `compound_same_subject_two_actions`
split "the health minister inaugurated a hospital" as
`verifiable=False` while a near-duplicate fragment, "a 200-bed hospital
was built", was marked `verifiable=True` -- an odd, inconsistent call
(a minister inaugurating a hospital is clearly a checkable fact) but not
a splitting failure per se, and consistent with this session's broader,
already-well-documented pattern of raw local-model output being
unreliable a meaningful fraction of the time.

Raw data: `research/results/compound_claim_stress_20260818.json`.
Generator: `backend/research/adversarial_v2/run_compound_claim_stress.py`.

## Raw data

`research/results/adversarial_claim_extraction_stress_20260818.json`.
Generator:
`backend/research/adversarial_v2/run_claim_extraction_stress.py`.
