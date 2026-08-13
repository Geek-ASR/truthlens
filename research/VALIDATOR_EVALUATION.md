# Deterministic Validator Evaluation (Day 5, RQ1)

Status: **real, live-run data (9 real verdict-generation events, run
through the actual production pipeline including Gemini escalation)
scored against a single, unadjudicated draft human review
(`research/validator_results.csv`, column `draft_human_judgment`) — not
yet reviewed by Aditya or any second person.** Every number below is
small-sample and directional. This document does not repeat the
`n_evidence_rows`/`n_sources` low-level detail already in
`research/results/validator_audit_20260813T*.json` — it reports the
judgment layer on top of that raw data.

## Terminology (Rule 8, enforced literally)

Nothing in this document is called a "hallucination rate." The
validator's own downgrade rate is described as exactly what the code
checks: a **grounding-constraint violation rate**. The human-judged
quantity below is described as an **unsupported/unreliable output
rate**, since "unsupported" is what a human reviewer is actually
assessing (does the reasoning hold up), not a claim about the model's
internal cognitive process.

## What was run

`backend/research/validator/run_validator_audit.py`: the real
production pipeline (`claim_extraction.extract_claims` →
`research_planning.plan_research` → `search_fetch.fetch_evidence_sources`
→ `evidence_analysis.analyze_evidence` → `verdict.propose_verdict`),
using the system's actual configured providers (Ollama + Gemini
escalation cascade — unlike Day 3/4's baselines, which deliberately used
pure Ollama to isolate architecture; here the goal is evaluating the
validator *as actually deployed*). Ran against the 6 successfully
-ingested Day 4 items. `propose_verdict()` was called with
`SKIP_VALIDATION=True` (Baseline 4's flag) so the raw proposal is always
what gets persisted, while `validate_verdict()`'s outcome is always
still computed and recorded — giving both the "WITHOUT VALIDATION" and
(derived, no second LLM call) "WITH VALIDATION" view from one real LLM
call per claim.

**Result**: 9 verifiable claims produced a resolved verdict-generation
event across 4 items (item-0002, item-0004, item-0005, item-0001); 2
items (item-0006, item-0007) had zero verifiable claims extracted by the
real (filtered) claim-extraction path — a legitimate, honest "found
nothing checkworthy" outcome for item-0006 (matches its ground truth:
genuine comedy content with no claim of its own), and a real
claim-coverage miss for item-0007 (its checkworthy claim, per
`MULTIMODAL_EVALUATION.md`'s draft ground truth, was not extracted as
`verifiable` here either).

## A real bug found and fixed mid-audit

One of the 9 cases (item-0004) was initially downgraded
(`downgraded_unsupported_stat`) for a spurious reason: its reasoning
used a single-bracket inline citation (`[evidence_id=e9aad959-737f-49b4-
840f-f75c4b378594]`) rather than the double-bracket form
(`[[evidence_id=...]]`) an existing fix already handled — the verdict
prompt never actually specifies a bracket format, so the model is free
to vary it, and did. The UUID's own hex fragments that happen to start
with digits (`737`, `49`, `840`) leaked through the number-grounding
check as apparent "unsupported statistics." Fixed in
`backend/app/pipeline/validation.py` by stripping anything shaped like a
UUID directly (`_UUID_PATTERN`), independent of what bracket style, if
any, wraps it — a more robust fix than chasing individual bracket
variants. New regression test added
(`test_ignores_numbers_inside_single_bracket_citation_markup`,
constructed from this exact real case); full suite 146/146 passing.
Re-verified live directly against the real persisted verdict row: status
changed from `downgraded_unsupported_stat` to `passed`.

**This fix had a real, disclosed side effect, reported honestly below
rather than smoothed over**: it removed an accidental protection that
had been shielding a *substantively wrong* verdict (see item-0004's row
below) from being published as-accepted. Fixing a real false-positive
bug does not, by itself, make the overall pipeline's output more
reliable if the thing it was accidentally catching was a real problem
for an unrelated reason — this is stated as a genuine finding of this
audit, not hidden.

## Confusion matrix (draft, n=9, single unadjudicated reviewer)

| | Validator downgrades | Validator passes |
|---|---|---|
| **Human judges output unsupported/unreliable** | 1 (TP) | 5 (FN) |
| **Human judges output fine to publish** | 0 (FP) | 3 (TN) |

Three of the four "downgrade" and "pass" cells need one more caveat:
**3 of the 4 recorded downgrades in this sample are "no-op" downgrades**
— the raw (WITHOUT VALIDATION) proposal was *already* `UNVERIFIED` with
an empty `cited_evidence_ids` list, so `validate_verdict()`'s
citation-existence check (Check 1: "cited must be a non-empty subset")
fires trivially on the empty set, but the published label doesn't
actually change (`UNVERIFIED` → `UNVERIFIED`). These are counted as TN
above (nothing wrong was going to be published either way), not as a
meaningful validator "catch" — a real, previously-unremarked wrinkle in
how the existing "28.6% downgraded" telemetry should be read: some
unknown share of any reported downgrade rate may be this same
kind of no-op, not a genuine intervention. Reported explicitly rather
than left to inflate the headline number's apparent significance.

**Validator Precision** = 1/1 = **100%** (Wilson 95% CI: 20.7%–100%)
**Validator Recall** = 1/6 = **16.7%** (Wilson 95% CI: 3.0%–56.4%)
**Validator F1** ≈ **28.6%**

The F1 figure coincidentally matches the existing paper's "28.6% of
verdicts downgraded" development-telemetry number — this is a
coincidence of two completely different metrics computed on completely
different, non-overlapping samples, not a replication, and should not
be presented as one in the paper.

## Unsupported Output Rate: WITHOUT vs. WITH validation

Per-case detail in `research/validator_results.csv`. Of the 9 raw
proposals, **6 of 9 (66.7%)** are judged (draft) unsupported/unreliable
enough that publishing them as-is would be misleading:
- item-0001 "paan shop owner" (wrong-entity evidence treated as
  contradicting)
- item-0001 "BHU is a medical college" (garbled reasoning, an apparently
  fabricated alternate name for the university)
- item-0002 "democracy... right to protest" (vague, thinly-grounded
  reasoning)
- item-0002 "Rajput is Org Secretary" (label contradicts its own stated
  reasoning: "no reliable information" → labeled `MOSTLY_FALSE`, not
  `UNVERIFIED`)
- item-0004 "baton with nails" (label contradicts real-world ground
  truth: `FALSE` at confidence 0.0, when BOOM Live independently
  confirmed this claim `TRUE`)
- item-0005 "Durrani met Dipke" (label contradicts real-world ground
  truth: `FALSE` at confidence 0.8, when this specific meeting is the
  one part of the underlying story that Factly's fact-check confirms is
  genuinely true)

Of those 6, deterministic validation catches and downgrades only **1**.
**Unsupported Output Rate WITHOUT validation: 6/9 (66.7%). WITH
validation (what would actually be published): 5/9 (55.6%).** Validation
reduced the unsupported rate by roughly eleven points on this sample —
real, positive, and far more modest than the existing paper's framing
("a deterministic validation layer... caught 28.6% of generated
verdicts") might suggest to a reader about the validator's overall
error-catching power specifically (as opposed to its citation/number
-grounding-catching power, which is what it actually measures well).

## Why recall is this low: what the validator can't see

Every one of the 5 false negatives fails for a reason the validator's
three checks (citation existence, source-fetch existence, numeric
grounding) structurally cannot detect:

1. **Label/reasoning inconsistency** (2 cases: Rajput, and arguably
   Durrani-meeting): the model's own prose says "no reliable
   information" or "no sources confirm," yet the assigned label is a
   confident `MOSTLY_FALSE`/`FALSE` rather than `UNVERIFIED`. No
   existing check compares the semantic content of `reasoning_summary`
   against the chosen `verdict` label at all.
2. **Wrong-entity / irrelevant evidence treated as directly relevant**
   (paan-shop-owner case, though this one WAS caught, via an indirect
   numeric-grounding trigger — see `docs/SYSTEM_AUDIT.md` §5.3, the
   already-flagged gap that `evidence_analysis.py`'s stance
   classification has no deterministic guard of its own).
3. **Vague, thinly-grounded reasoning that still clears the ">=6 real
   words" substantiveness bar** (democracy-protest case): a check
   designed to catch citation-markup-only emptiness doesn't catch prose
   that's real words but doesn't actually say anything specific.
4. **A verdict that is simply, factually wrong relative to independent
   ground truth** (baton-nails, Durrani-meeting): the validator has no
   mechanism to check a claim against anything other than the evidence
   matrix it was given — if the model misreads or misweighs real,
   present evidence (as opposed to citing evidence that doesn't exist),
   nothing catches it. This is not a gap that can be closed with a
   stricter regex; it would need either better evidence-analysis stance
   accuracy upstream or a fundamentally different check.

## Threats to this specific result

- **n=9, one unadjudicated draft reviewer (me).** Every number above
  needs Aditya's (or another independent human's) review before it's
  trustworthy — this is explicitly flagged, not glossed over, per
  `ANNOTATION_GUIDELINES.md`.
- **The 3 "no-op downgrade" cases could reasonably be scored a different
  way** (e.g., excluded entirely rather than counted as TN, since the
  validator's citation-existence check firing on an already-empty
  citation list arguably isn't "the validator working," it's an
  artifact of how Check 1 is written). Recomputing without them: TP=1,
  FN=5, TN=0 (no true negatives at all in the reduced set), which
  doesn't change precision/recall/F1 above (TN doesn't enter those
  formulas) but does change how "3 of 9 downgraded" should be narrated
  in prose — reported both ways rather than picking whichever reads
  better.
- **Two of the six false negatives (baton-nails, Durrani-meeting) are
  judged against this project's own Tier-1 ground truth**, which is
  itself methodologically the strongest ground truth this project has
  (independent professional fact-checkers) — these two are the least
  contestable of the six.
- **This audit ran on real reels ingested days apart from when this
  document is being written**, using whatever Ollama/Gemini escalation
  behavior was live at the time — not necessarily reproducible
  bit-for-bit on a re-run (`REPRODUCIBILITY.md` already flags LLM
  sampling as unseeded).

## What's next

1. Human review/adjudication of `validator_results.csv`'s
   `draft_human_judgment` column (blocks trusting precision/recall/F1
   as final).
2. Consider whether a "label matches reasoning tenor" check is a
   tractable deterministic addition (e.g., flagging low-confidence
   verdicts assigned a definitive label, or reasoning containing
   phrases like "no reliable/no evidence" paired with a non-UNVERIFIED
   label) — a concrete, scoped candidate future-work item this audit
   directly motivates, not a vague aspiration.
3. Scale this audit past n=9 once the dataset itself grows past 7 items
   (Day 2's ongoing work) — every finding here should be treated as a
   hypothesis to re-test at a larger sample, not a settled result.
