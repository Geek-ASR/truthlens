# ENTITY_CONSISTENCY_EVALUATION.md — Phase 5

Status: 2026-08-14. Real evaluation, `backend/research/entity_consistency_eval.py`,
against the same real 9-claim / 68-source data already audited in
`VALIDATOR_EVALUATION.md`. **Not integrated into the production
validator** — this is a prototype, evaluated independently, per Rule 2
and Phase 5's own explicit instruction not to assume it helps.

## Design

For each cited evidence row where `evidence_analysis` assigned a
non-`irrelevant` stance (`supports`/`contradicts` — the stances that
actually influence a verdict), check whether at least one of the claim's
own extracted named entities (`Claim.entities`, real production data,
already populated by `claim_extraction`) appears in that evidence's own
title+passage text. No exact-string requirement beyond case-insensitivity;
one small, explicit alias group (government-institution synonyms, per
Phase 5's own example) is included and disclosed, not a general fuzzy
matcher. A claim with zero extracted entities cannot be evaluated by this
check at all.

## Headline result

10 non-irrelevant evidence rows across 9 claims; 9 evaluable (1 claim,
the "paan shop owner" case, has zero extracted entities — see below).
**7 of 9 evaluable rows were flagged as entity-consistency violations.**
Read literally this looks like a high detection rate; it is not, once
each flagged case is manually audited against the real underlying text
(below) rather than trusted at face value.

## Manual audit of all 7 flagged violations

| Claim | Evidence | Flagged as | Manual verdict |
|---|---|---|---|
| "Delhi Police are attacking children..." | "Caught on camera: Protesting students beaten with nail-studded sticks in **Burdwan, West Bengal**" (India Today, `contradicts`) | Violation | **Genuine true positive.** The cited "contradicting" evidence is about a completely different incident (West Bengal university students, not Delhi Police, no mention of Delhi at all) being treated as directly relevant to a Delhi-specific claim. This is exactly the wrong-entity/wrong-incident failure mode Phase 5 targets, and it is real, not constructed after the fact from this exact case (Karni Sena/Sri Ram Sena, a different item, motivated the check's design). |
| "In a democracy, every citizen has..." (4 rows, various sources) | Real Article 19 / constitutional-law sources | Violation $\times$4 | **False positive, and the check's own design flaw, not the underlying data's.** The claim's only extracted entity is `{"name": "Democracy", "type": "concept"}` — an abstract concept, not a person/organization/location Phase 5 actually asks this check to extract and compare. Checking whether the literal word "Democracy" appears in constitutional case law is not a meaningful entity-consistency test. **Fix, not yet applied**: filter to `type` $\in$ {person, organization, location} before evaluating; extracted `type` values are free text (`"concept"`, `"Organization"` vs. `"organization"` mixed casing), themselves a minor, disclosed data-quality gap in `claim_extraction`'s own output. |
| "Babajani Durrani held a courtesy meeting with Abhijit Dipke..." (1 of 2 rows) | Devanagari/Marathi-script news article naming "Abhijeet Deepke" | Violation | **Likely false positive from transliteration variance, not a real entity mismatch.** The evidence is plausibly about the same person (`Dipke`/`Deepke` are transliteration variants of the same Marathi name), but exact case-insensitive substring matching on the claim's own spelling ("Dipke") does not match the evidence's spelling ("Deepke"). A real, unresolved limitation of substring-only matching for names with non-standardized Latin transliteration from Devanagari/Marathi script — disclosed, not fixed in this pass. |

## The one claim this check cannot evaluate at all

"The student receiving the NEET score is the son of a paan shop owner"
(item-0001) — the exact real case this project's own taxonomy already
documents as a wrong-entity failure (a citation to a story about a
different person, "Lakshmi Shivasali," a paan vendor's *daughter*, not
the claim's anonymous "son") — has **zero extracted entities**, because
the claim itself never names anyone. This check, as designed, requires
the claim to name an entity to check against; it structurally cannot
catch a case where the claim is anonymous but the cited evidence smuggles
in a specific, unestablished identity. This is an honest, important
negative result: **the entity-consistency check, as scoped by Phase 5,
does not catch the specific historical case that most directly motivated
building it.** Catching this class of case would need a different check
entirely (e.g., flagging when cited evidence contains a specific named
person the claim itself never established), not a refinement of this one
— named as a distinct, unscoped future-work item, not conflated with what
was actually built and tested here.

## Net assessment: 1 real true positive, 4 diagnosed false positives, 1-2 likely false positives, 1 structurally unevaluable case

After excluding the 4 abstract-concept false positives (a fixable filter,
not applied yet) and treating the transliteration case as unresolved: **1
clear, real, valuable catch out of a corrected ~5 evaluable cases.** This
is directionally positive but far too small a sample to justify adding a
fifth deterministic check to the production validator
(`backend/app/pipeline/validation.py`) without more data — consistent
with Rule 2/4's discipline against adding complexity without sufficient
evaluation. **Recommendation: do not integrate into production yet.**
Concrete, scoped next steps: (1) filter entity types to
person/organization/location before any further evaluation; (2) evaluate
on a larger, ideally frozen-and-disjoint sample before integration; (3)
the transliteration-variance gap needs either a small, explicit
transliteration-alias table (same discipline as the government-synonym
group already used) or acceptance as a known limitation.

## Connection to the error budget

This finding refines `ERROR_BUDGET.md`'s item-0004 entry (previously
attributed generally to "evidence interpretation"): the specific,
concrete mechanism is at least partly a wrong-location/wrong-incident
citation (Burdwan, West Bengal, cited as if relevant to a Delhi Police
claim) being treated as `contradicts` rather than `irrelevant` —
consistent with, and now a second real example of, the same
evidence-analysis stance-classification gap `docs/SYSTEM_AUDIT.md`
already named structurally (no deterministic guard on stance
classification itself).

## Raw data

`research/results/entity_consistency_eval_20260814.json` (10 rows, full
detail per evidence row). Generator:
`backend/research/entity_consistency_eval.py`, reading claim/evidence
data pulled live from the production database on 2026-08-14 (the exact
query is in the script's own `main()` docstring context).
