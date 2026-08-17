# ENTITY_CONSISTENCY_EVALUATION_V2.md — Phase 4

Status: 2026-08-18. Successor to `ENTITY_CONSISTENCY_EVALUATION.md`
(2026-08-14), which is left unedited per this program's standing rule
against overwriting a prior dated evaluation in place. That document's
own "Net assessment" section named 3 concrete, scoped fixes required
before another evaluation pass would mean anything; this pass applies
all 3, re-evaluates against real (larger, DEV-split) data, and — unlike
v1 — reaches and acts on the integrate/don't-integrate decision
`RESEARCH_ROADMAP_V2.md` Phase 4 requires.

## The 3 fixes applied

1. **Filter claim entities to PERSON/ORGANIZATION/LOCATION before
   evaluating.** v1's only 4 false positives were all one abstract
   -concept entity (`{"name": "Democracy", "type": "concept"}`) matched
   against unrelated constitutional-law text — not a meaningful
   entity-consistency test. Real `Claim.entities` `type` values observed
   live are messy free text (`"person"`, `"Organization"`,
   `"EducationalInstitution"`, `"Examination"`, `"concept"`, ...) —
   canonicalized into a fixed vocabulary (`app.pipeline.validation.
   _normalize_entity_type`) rather than guessed at. This is **not** the
   roadmap's full aspirational 7-category schema (PERSON/ORGANIZATION/
   LOCATION/EVENT/DATE/NUMBER/POLITICAL_ACTOR) — EVENT/DATE/NUMBER/
   POLITICAL_ACTOR would require a `claim_extraction` prompt/schema
   change this pass does not make. Disclosed, not silently narrowed.
2. **Real data pulled directly from the live DB** (DEV split only, per
   Phase 4's own dataset instruction), not a throwaway `/tmp`
   intermediate file — reproducible and permanent this time
   (`backend/research/entity_consistency_v2/evaluate.py`).
3. **A disclosed, separate fuzzy-match signal** for the real
   transliteration-variance gap v1 found (Dipke/Deepke).
   `difflib.SequenceMatcher` (same tool this session's claim-deduplication
   work already used), calibrated against this project's own real cases,
   not guessed: "abhijit dipke" vs "abhijeet deepke" (the real case that
   *should* match) scores 0.786; "delhi police" vs "burdwan police" and
   "karni sena" vs "sri ram sena" (the real cases that must *not*
   collapse — exactly Step 9's "Delhi Police vs Burdwan Police" test
   class) score 0.615 and 0.545. Threshold set to 0.75.

## Headline result

Real DEV-split data (grown since v1's snapshot — 4 reels now have
ingested evidence, 207 evidence rows total): 20 non-irrelevant evidence
rows, 7 evaluable (claim had ≥1 PERSON/ORGANIZATION/LOCATION entity), 13
not evaluable.

**2 of 7 evaluable rows flagged as violations — both genuine true
positives, 0 false positives.**

| Claim | Evidence | Flagged as | Assessment |
|---|---|---|---|
| "Delhi Police are attacking children..." | "Caught on camera: ... beaten with nail-studded sticks in **Burdwan, West Bengal**" (India Today, `contradicts`) | Violation | **Genuine true positive**, same case v1 found — re-confirmed, not a new artifact of the fix. |
| "Kunwar Vishnu Singh Rajput is an organizational secretary [of] Karni Sena..." | "Sri Ram Sena - Wikipedia" (`contradicts`) | Violation | **New genuine true positive**, not visible in v1's smaller sample — a different Hindu-nationalist organization ("Sri Ram Sena") cited as if relevant to a claim specifically about Karni Sena. |

The 4 abstract-concept false positives from v1 (all against the
"In a democracy, every citizen has..." claim, entity `{"name":
"Democracy", "type": "concept"}`) are gone: all 10 evidence rows for
that claim are now correctly `SKIP` (not evaluable), exactly as
predicted by the type filter, not just hoped for.

The fuzzy-match fix recovered a real case: the "Abhijit Dipke" /
"Abhijeet Deepke" evidence row that would have been a false-positive
violation under exact-match-only matching now correctly passes
(`ok(fuzzy)`), while the two real must-not-collapse cases above
(Delhi/Burdwan Police, Karni/Sri Ram Sena) both still correctly flag —
confirming the 0.75 threshold holds on live data, not just the 2
hand-picked calibration pairs it was set from.

## Decision: integrate

Per `RESEARCH_ROADMAP_V2.md` Phase 4's own stopping condition ("a
single, pre-registered decision point ... integrate or don't, based on
the measured precision/recall, not further iteration"): **integrated**,
as Check 7 in `backend/app/pipeline/validation.py`
(`ValidationStatus.downgraded_entity_mismatch`). Corrected precision on
evaluable cases: 2/2 (100%), up from v1's uncorrected ~14% (1 real out
of 7 flagged). Recall is not separately measurable from this data (no
independently labeled "should have been flagged" ground truth beyond
the cases found), consistent with v1's own limitation.

**Honest caveat, not hidden**: n=7 evaluable cases is still a small
sample. This is watched, not treated as final — Phase 8's planned
adversarial-benchmark expansion is the natural place to stress-test this
check further against synthetic wrong-entity/wrong-incident cases at
higher n, per the roadmap's own phase ordering.

## What did NOT change

- The one claim v1 found this check *cannot* evaluate at all — "The
  student receiving the NEET score is the son of a paan shop owner"
  (zero extracted entities, the claim never names anyone) — remains
  unevaluable for the same structural reason v1 documented. Still an
  honest, disclosed negative result, not revisited this pass.
- No EVENT/DATE/NUMBER/POLITICAL_ACTOR entity typing was added to
  `claim_extraction` itself — see fix #1 above.

## Raw data

`research/results/entity_consistency_eval_v2_20260818.json` (20 rows,
full detail per evidence row, including which specific entities matched
exactly vs. via fuzzy match). Generator:
`backend/research/entity_consistency_v2/evaluate.py`, importing the
exact same matching primitives Check 7 uses in production (no
reimplementation, no drift between what this report describes and what
actually runs).
