# VALIDATOR_SYNTHETIC_BENCHMARK.md — Phase 4

Status: 2026-08-14. Run against the real, already-shipped
`validate_verdict()` function (`backend/research/validator_benchmark/build_and_run.py`).
**Honest scope**: 28 cases (target was 60–100; not reached — each case
needed real, hand-considered construction, including fixing two real
methodology bugs found while building this benchmark itself, below).
Split 14 dev / 14 test. Because Checks 1–4 already existed, frozen,
before this benchmark was written, no new component was tuned against
this data — the dev/test split exists for reporting discipline, not to
prevent overfitting a check that was never touched.

## Two real bugs found while building this benchmark, kept and reported rather than quietly fixed

1. **Six cases (G, H, K, L, M, N) originally had no citation at all**,
   intended to isolate Check 4's phrase-matching behavior. Running them
   revealed all six were actually being caught by **Check 1** (empty
   citation list) before Check 4 was ever reached — silently testing the
   wrong thing. Fixed by giving each case a real, valid, fetched citation
   with a number-free passage, so Checks 1–3 pass cleanly and Check 4 is
   what actually gets exercised. Caught by reading `validation_status` in
   the raw output, not assumed correct from the design alone.
2. **Two "should-pass" cases with genuinely well-reasoned contrastive
   verdicts** ("the true figure is 45 crore, not the falsely claimed 100
   crore") **false-positived on Check 3**, because the *refuted* number
   (100) never appears in the cited *evidence* passage — only the
   original claim text would contain it, and Check 3 only has access to
   evidence passages. This is a real, previously undocumented limitation
   of Check 3, not a mistake in these two cases: kept in the benchmark as
   `should_be_flagged=False`, both correctly labeled false positives.

## Headline result

$n=28$, TP=9, FP=2, FN=9, TN=8.

- **Precision: 81.8% (9/11), Wilson 95% CI [52.3%, 94.9%]**
- **Recall: 50.0% (9/18), Wilson 95% CI [29.0%, 71.0%]**
- **Specificity: 80.0% (8/10), Wilson 95% CI [49.0%, 94.3%]**
- **F1: 62.1%**

## The result that actually matters: a clean split by design, not by chance

Of the 18 cases that should be flagged, 9 were pre-labeled
`checkable_by_current_checks=True` (categories A, C, D, G, H, and O1 --
structurally within what citation-existence, fetch-existence, number
-grounding, or exact-phrase label/reasoning matching can detect) and 9
were pre-labeled `False` (categories E, F, I, J, K, L, M, N, O2 --
semantic gaps, or paraphrases outside the original phrase list). **The
real system caught exactly, and only, the 9 pre-labeled-checkable cases
(9/9 = 100%) and missed exactly, and only, the 9 pre-labeled-unchecknable
cases (0/9 = 0%).** The category label assigned *before* running the
benchmark perfectly predicted the real system's behavior in all 18
cases -- this is not a coincidence of a lenient labeling scheme; it is
the cleanest possible confirmation that the four checks do exactly what
their own design says they do, no more and no less.

## This directly answers a previously-disclosed open question

`VALIDATOR_EVALUATION.md`'s addendum stated: "the 40% recall figure is
likely optimistic about how well [Check 4] generalizes to new cases with
different phrasing... untested." **It is no longer untested.** Cases K,
L, M, N gave Check 4's phrase-matching logic four real paraphrases of "no
evidence found" that were deliberately never in its original phrase list
(`_NO_EVIDENCE_FOUND_PHRASES`) -- "the data does not corroborate this,"
"insufficient corroboration exists," "the available sources do not
establish," "cannot verify this claim." **All four were missed (0/4).**
Check 4 does not generalize at all beyond its literal phrase list on this
evidence. This is a real, concrete, negative confirmation of the exact
threat to validity already disclosed, not a new problem -- but it moves
that disclosure from "we suspect this doesn't generalize" to "we tested
it and it doesn't."

## Semantic gaps: confirmed real, not structurally closeable by these checks

Categories E (wrong entity), F (evidence contradicts reasoning), I (valid
citation, wrong interpretation), J (real source, wrong specific fact),
and O2 (citation exists, doesn't entail the claim) were all missed
(0/5, plus the 4 phrase-generalization misses above = 9/9 total misses).
None of these are number-grounding, citation-existence, or exact-phrase
problems -- they require understanding whether cited text actually means
what the reasoning says it means, which is exactly the class of problem
Section~IX of the paper already argues these checks were never designed
to solve, and Phase 5's entity-consistency prototype (`ENTITY_CONSISTENCY_EVALUATION.md`)
was a first, partial, honestly-evaluated attempt at category E
specifically.

## False positives: 2/10, both the same newly-discovered Check-3 pattern

No other false-positive pattern was found among the 8 other genuinely
valid cases (spanning all 8 `VerdictLabel` values used in this project).
The false-positive rate on non-contrastive, well-grounded verdicts is
0/8 (0%) in this sample.

## Confusion matrix

| | Validator flags | Validator passes |
|---|---|---|
| Should be flagged | 9 (TP) | 9 (FN) |
| Should pass | 2 (FP) | 8 (TN) |

## Threats to this specific result

Synthetic cases, not real historical failures (except where explicitly
modeled on one, e.g., K1–N1's paraphrases were written independently of
any real case, precisely so they could test generalization honestly).
$n=28$ is small; every proportion above carries a wide Wilson interval,
reported explicitly rather than a bare percentage. The construction
itself surfaced two real bugs in this exact benchmark, both fixed and
disclosed above -- a reminder that a synthetic benchmark is not
automatically more reliable than real data just because it is
constructed deliberately.

## Raw data and regeneration

`backend/research/validator_benchmark/build_and_run.py` (case
construction + real `validate_verdict()` run) $\to$
`research/results/validator_synthetic_benchmark_20260814.json` (28 rows,
one per case, full detail).
