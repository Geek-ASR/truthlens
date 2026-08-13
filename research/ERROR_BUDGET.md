# ERROR_BUDGET.md — Phase 11: Earliest-Causal-Failure Analysis

Status: 2026-08-14. **$n=4$ wrong item-level verdicts** (out of 6 scored),
plus 5 claim-level validator false negatives from the same real audit
(`research/results/validator_audit_20260813T073200Z.json`, cross-checked
against `research/VALIDATOR_EVALUATION.md` and
`research/MULTIMODAL_EVALUATION.md`). This is a small-$n$, directional
analysis, not a stable failure-rate estimate — stated up front, per Rule
1, rather than implied by a table that looks more precise than it is.

## Method

For each wrong verdict, we trace forward through the 14-stage taxonomy
(ingestion → transcription → OCR → vision → claim extraction → query
generation → retrieval → source relevance → evidence extraction →
evidence interpretation → verdict reasoning → deterministic validation →
aggregation → rendering) and identify the **earliest** stage at which a
real, already-diagnosed defect occurred. A downstream stage that merely
propagates an upstream defect (e.g., claim extraction correctly finding
nothing because transcription already failed) is not counted as an
independent failure at that downstream stage.

## Item-level error budget ($n=6$ scored items, 4 wrong)

| Item | Verdict (GT) | Earliest causal stage | Real, already-diagnosed cause |
|---|---|---|---|
| item-0004 | FALSE (TRUE) | **10. Evidence interpretation** | Confident wrong label from misweighing real, present evidence — `VALIDATOR_EVALUATION.md`: "the validator has no mechanism to check a claim against anything other than the evidence matrix it was given... would need better evidence-analysis stance accuracy upstream." **Refined 2026-08-14** (`ENTITY_CONSISTENCY_EVALUATION.md`, Phase 5): a concrete mechanism confirmed — the cited "contradicting" evidence is a real India Today article about an unrelated incident in Burdwan, West Bengal, containing no mention of Delhi Police at all, treated as directly relevant to a Delhi-specific claim. |
| item-0005 | UNVERIFIED (MISLEADING) | **5. Claim extraction** (secondary: 10) | The item's true structure needs a "meeting occurred" claim (true) *and* a separate context/characterization claim to land on `MISLEADING`; only one claim covering the meeting was extracted, so aggregation had no context claim to combine it with. The original confident-FALSE misreading (stage 10) was separately caught and downgraded by Check 4 (Section IX) — the remaining wrongness is a decomposition-coverage gap, not the original evidence-misreading one. |
| item-0006 | UNVERIFIED (FALSE) | **2. Transcription** | Whisper transcript "badly garbled nonsense" on chaotic disaster-footage audio (`MULTIMODAL_EVALUATION.md`) — claim extraction correctly found nothing from unusable input; not an independent claim-extraction defect. |
| item-0007 | UNVERIFIED (FALSE) | **2. Transcription** | Transcript "degraded and repetitive" (`MULTIMODAL_EVALUATION.md`) — same propagation pattern as item-0006. |

## Stage summary table (Phase 11's requested format)

| Stage | Errors originating here | Rate (of 4 wrong) | Final incorrect verdicts caused |
|---|---|---|---|
| 2. Transcription | 2 | 50.0% | item-0006, item-0007 |
| 5. Claim extraction | 1 | 25.0% | item-0005 |
| 10. Evidence interpretation | 1 (+1 secondary, now fixed) | 25.0% | item-0004 |
| All other stages (1, 3, 4, 6–9, 11–14) | 0 | 0.0% | — |

**Reading this table honestly**: at $n=4$, "50\% of errors originate in
transcription" means exactly two items, both already-diagnosed, real
cases — not a stable rate for this failure mode in general. It is,
however, consistent with a broader pattern this project has repeatedly
found: input-quality failures upstream of any reasoning stage (garbled
audio, empty OCR, prompt-echoed vision output) are at least as
consequential as anything in claim reasoning, evidence retrieval, or
verdict generation — none of which contributed an earliest-causal error
to any of these four items.

## Claim-level detail: the 5 original validator false negatives

A finer-grained, claim-level view from the same real audit (before Check
4; two of these five are now caught, see `VALIDATOR_EVALUATION.md`'s
addendum) adds detail the item-level table alone does not show:

| Claim (item) | Earliest causal stage | Cause |
|---|---|---|
| "Rajput is Org Secretary" (item-0002) | **11. Verdict reasoning** | Label (`MOSTLY_FALSE`) contradicted the reasoning's own "no reliable information" conclusion — now caught by Check 4. |
| "Durrani met Dipke" (item-0005) | **10. Evidence interpretation** | Confident `FALSE` at 0.8 confidence contradicted by real Tier-1 ground truth — now caught by Check 4 (downgraded to `UNVERIFIED`, item-0005's remaining item-level error is the separate decomposition-coverage gap above). |
| "Paan shop owner" (item-0001) | **10. Evidence interpretation** | Wrong-entity evidence (a different human-interest story) treated as directly contradicting — still uncaught; the entity-consistency validator scoped in Section~V (paper) / Phase 5 below is the concrete, motivated fix. |
| "BHU is a medical college" (item-0001) | **11. Verdict reasoning** | Garbled bracket-only citations plus an apparently fabricated alternate name for the university, no ungrounded number involved so the existing numeric check is blind to it — still uncaught. |
| "Democracy/protest rights" (item-0002) | **5. Claim extraction** | Claim extracted too generally (no specific person/place/date), so unrelated-event government sources about protest restrictions anywhere become plausible-looking "evidence" — a claim-specificity problem more than a pure evidence-relevance one (`EVIDENCE_EVALUATION.md`). |

**Claim-level stage summary**: evidence interpretation (stage 10) and
verdict reasoning (stage 11) each account for 2 of 5 claim-level false
negatives; claim extraction (stage 5) accounts for 1. No claim-level
false negative in this sample originates in ingestion, transcription,
OCR, vision, query generation, retrieval, source relevance, evidence
extraction, deterministic validation, aggregation, or rendering.

## What this analysis motivates, concretely

1. **Transcription robustness** is the single highest-leverage item-level
   fix available (2 of 4 item-level errors) -- not a claim-reasoning or
   retrieval problem at all.
2. **Evidence interpretation** (stance-classification correctness) is the
   most common claim-level failure category and the one this project's
   own architecture has the least deterministic coverage for -- it is
   the direct motivation for the entity-consistency validator (Phase 5),
   scoped specifically at the one clear evidence-interpretation failure
   mode (wrong-entity evidence) that has a tractable, auditable
   deterministic check.
3. **Claim-extraction specificity** (not just claim-extraction
   *coverage*, already well-documented elsewhere in this paper) is a
   distinct, real failure mode -- a claim can be successfully extracted
   and still be too general to be checked precisely.
4. No item-level or claim-level error in this sample originates in
   retrieval, source relevance, or aggregation -- consistent with, and a
   useful complement to, Section IX's four-way evidence metric (which
   shows retrieval finding real, on-topic sources at a meaningfully
   higher rate than the system's own usable-evidence rate would suggest).

## Threats to this analysis

Same $n=4$/$n=5$ caveats as everywhere else in this program: too small to
generalize a stable per-stage error rate. The "earliest causal stage"
judgment for evidence-interpretation and verdict-reasoning cases required
a human (this project's own draft review) to read the real reasoning text
and assign a category — not a formula — so these two categories in
particular carry the same single-annotator caveat as the underlying
validator audit itself (`research/VALIDATOR_EVALUATION.md`).
