# RESEARCH_ROADMAP_V2.md

Status: 2026-08-14. Successor to the completed 27-phase audit program
(`AUDIT_REPORT.md` et al.) and this session's two-pass page-length trim.
Organized per the governing brief's Step 1 (13 named phases). Step 36's
separate 18-item PHASE 0–17 *work order* sequences these same phases
plus infrastructure-first sub-steps (Gemini cooldown config, split
schema, regression/adversarial benchmarks) ahead of them — see the
"Work order" note at the end of this file for the exact mapping. Every
phase below states a falsifiable hypothesis; "the intervention doesn't
help" is a valid, publishable outcome for every one of them, not a
failure of the roadmap.

Cross-cutting rules inherited from the governing brief, restated here
because every phase is bound by them: (1) free/local/deterministic work
before any Gemini call; (2) TEST is frozen once created — a TEST failure
becomes a TEST-v2/regression case, never a reason to retune against TEST
itself; (3) every experiment gets recorded before/after metrics, not
just a final number; (4) a negative result is preserved with the same
prominence as a positive one.

---

## PHASE 1 — Benchmark expansion

**Hypothesis**: a stratified benchmark of 25–60 real, independently
fact-checked items (vs. today's 9) will narrow every confidence interval
in the paper enough to make the headline comparison and the
decomposition/multimodal ablations individually informative, not just
directionally suggestive.

**Intervention**: build sourcing infrastructure (Priority-1, free/local)
that searches professional fact-checking outlets, computes
`media_content_hash` against both `items.jsonl` and the live DB's 20
`reels` rows to exclude anything already used in development, and
stratifies incoming candidates against the target distribution (Step 2).

**Baseline**: the current 9-item set and its documented $\sim$8% hit
rate (`DATASET_CARD.md`).

**Dataset**: new, disjoint Instagram/YouTube-Shorts/TikTok posts sourced
from BOOM Live, Alt News, Factly, PIB Fact Check, Reuters Fact Check, AFP
Fact Check (the same pool `DATASET_CARD.md` already documents plus any
newly identified outlets).

**Metrics**: raw sourcing hit rate (n usable / n articles checked);
final composition vs. target stratification (FALSE 20–25, MISLEADING
8–12, TRUE 8–12; claim-type/language/modality spread per Step 2);
duplicate-rejection count against the live DB.

**Expected outcome**: hit rate stays near the observed $\sim$8%
(this is a property of how many professional fact-checks embed a
still-live post, not something sourcing effort changes); reaching the
"good" 40-item target therefore requires checking on the order of
400–500 articles, a bounded but large manual/semi-automated task.

**Failure condition**: if the true distribution cannot approach the
target stratification even after exhausting reasonable sourcing effort
(e.g., TRUE claims remain structurally underrepresented because
fact-checkers publish far more debunks than confirmations — already
observed at $n=9$), the roadmap does not force artificial balance; it
documents the real, achieved distribution as a disclosed limitation, per
Step 2's explicit instruction.

**Stopping condition**: sourcing continues until either 60 items are
reached, or three consecutive sourcing passes each add fewer than 3 new
usable items (diminishing-returns signal, matching the discipline
already used once for the original 9-item set).

**2026-08-18 update — target revised upward, hit rate confirmed even
lower than predicted**: a direct instruction superseded the 60-item
target with a 500-item target, explicitly local-models-only (no
Gemini), automated (see `research/MASS_SOURCING_V2.md`). Built four
parallel crawl pipelines (Alt News, Vishvas News, Factly, thequint.com
WebQoof) against full historical archives, not just a sample. Real
result: Alt News's **entire** 498-page/4,967-article archive, applied
with real judge + manual-review rigor, produced only 2 promotable
items — roughly 1 per 250 candidates checked, well below even this
phase's own pessimistic ~8% prediction (that 8% figure was measured
against "any usable fact-check candidate"; the automated pipeline's bar
is stricter — specifically requiring the Instagram post's OWN caption
to assert the claim, not just be cited as evidence, AND still be
retrievable via `yt-dlp`). At the confirmed yield rate, 500 items would
require checking on the order of 100,000+ candidates from
Instagram-specific sources — not achievable through deeper crawling of
the same source type in any bounded timeframe. This matches, in hard
numbers, the qualitative 8/8 finding from earlier in this session that
X/Twitter, not Instagram, is where most of this misinformation pattern
actually gets posted (a scope-relaxation option that was explicitly
declined when offered — Instagram-only sourcing continues by direct
instruction, slow pace accepted). Sourcing continues via the fourth
source (WebQoof) and any further sources found, but 500 items is not
expected to be reached through this method alone; this is disclosed
here rather than smoothed over, per this project's stated audit
discipline.

**2026-08-18 final addendum — sourcing effort concluded, project
paused**: two more sources were added (Fact Crescendo, across all four
of its live language subdomains) and two real filter-coverage bugs were
found and fixed (Vishvas and WebQoof were both silently excluding a
majority of their real content — see `research/MASS_SOURCING_V2.md`).
Final tally across all six sources checked: roughly 3,600 real
candidates judged, 4 promoted (items 19–22), a blended yield of
**roughly 1 per 900 candidates** — worse than the mid-session ~1-per
-250 estimate above, since two of the four contributing sources
(Vishvas, WebQoof) yielded only 1 promotion each across their *entire*
archives despite the filter fixes finding real additional volume.
Benchmark stands at 22 items (9 v1 + 13 v2). This finding, plus a
separate verification pass confirming the system's existing
Instagram-publishing pipeline works and adding test coverage it lacked,
are the last work done before this project was put on hold. See
`research_paper/main.tex` (`sec:massSourcing`, `sec:publishing`,
Conclusion) for the versions of these findings written for the paper.

---

## PHASE 2 — Claim extraction improvement

**Hypothesis**: today's claim extraction under-recalls (produces zero
verifiable claims on 2 of 6 usable benchmark items, per the existing
paper) because the prompt is not recall-optimized and provides no
per-claim provenance/confidence signal a downstream consumer could use
to distinguish a confident extraction from a marginal one.

**Intervention**: (a) add `source_modalities` (list),
`extraction_confidence` (float), and a `provenance` enum
(`POST_LOCAL`/`CAPTION_DERIVED`/`AUDIO_DERIVED`/`OCR_DERIVED`/
`VISION_INFERRED`/`CROSS_POST`/`MULTIMODAL`/`UNKNOWN`, Step 8) to the
`Claim` schema and extraction prompt; (b) rewrite the extraction prompt
to explicitly instruct recall-first decomposition (Step 5); (c) add
deterministic + semantic deduplication (Step 6) using the
already-provisioned but currently-unused `Claim.embedding` (pgvector)
column.

**Baseline**: current `claim_extraction.v2` prompt (`prompts.py:29-61`),
current `Claim` schema (no provenance/confidence fields — confirmed this
audit).

**Dataset**: DEV split of Phase-1's expanded benchmark, plus the
existing 9-item set as a regression check that recall gains don't
regress the 2 already-working items.

**Metrics**: claim recall against a newly-annotated "every checkworthy
assertion in the post" ground truth (not just fact-check-claim
coverage, which is a different, narrower metric already tracked);
claim precision; duplicate rate before/after dedup; per-provenance-
category claim count.

**Expected outcome**: recall-optimized prompting increases raw claim
count and duplicate rate together; the dedup stage (Phase 2c) is
required to net out ahead, not the prompt change alone — this
decomposition into two sub-experiments is itself a finding, not a
formality.

**Failure condition**: if higher recall does not translate into higher
downstream verdict accuracy (e.g., more claims but the *important*
claim is still missed, or more noise for the aggregation stage to
filter), report that explicitly — extraction recall and end-to-end
accuracy are logically separable per the brief's Core Research
Principle and must be measured as such, not collapsed.

**Stopping condition**: recall improves and precision does not fall
below the current baseline's precision on a held-out DEV slice; if
three prompt iterations fail to clear that bar, stop and report the
negative result rather than iterating indefinitely against DEV.

---

## PHASE 3 — Multimodal fusion

**Hypothesis**: TruthLens's existing three-condition multimodal
comparison (`text_only`/`text_ocr`/`text_ocr_vision`, $n=6$) already
shows a directional signal (33.3% vs. 16.7% vs. 0.0% coverage) that a
larger, properly-split benchmark can turn into a real, adequately
-powered result, and that per-modality recall/precision (not just
coverage) will identify which modality recovers claims the others miss.

**Intervention**: re-run the existing `run_claim_coverage.py`-style
experiment across all 8 modality combinations named in Step 7
(audio-only through all-modalities) on Phase-1's expanded benchmark, and
add per-modality claim precision (not just recall) alongside coverage.

**Baseline**: the existing 3-condition, $n=6$ result already in
`main.tex` Section X and `MULTIMODAL_EVALUATION.md`.

**Dataset**: DEV split, stratified subset with confirmed audio+OCR+
caption+visual availability recorded per item (a new structured field,
since today's schema only has a free-text `modality` value, not
per-signal availability booleans — Step 4).

**Metrics**: claim recall/precision/duplicate-rate per modality
combination; downstream verdict accuracy per combination.

**Expected outcome**: `text_ocr_vision` (full multimodal) continues to
dominate on recall; the specific finding that `text_ocr` alone scored
*below* `text_only` (already reported as real, not suppressed) is
re-tested at higher $n$ to see if it's noise or a real interaction
effect.

**Failure condition**: if the effect direction reverses at higher $n$,
report the reversal with the same prominence the original baseline
-confound reversal got — this program has direct precedent for treating
a reversed finding as a feature, not an embarrassment.

**Stopping condition**: once VALIDATION-split results are consistent
with DEV-split results (no large swing), freeze the modality-fusion
design and move to Phase 4; do not keep re-tuning against DEV
indefinitely.

---

## PHASE 4 — Entity consistency

**Hypothesis**: the existing entity-consistency prototype
(`entity_consistency_eval.py`, 1 genuine true positive on $n=9$/10) is
too small to justify production integration, but a larger sample will
show whether its true-positive rate clears a bar worth a 5th
deterministic validator check.

**Intervention**: extend the prototype's alias-table approach with
structured entity typing (PERSON/ORGANIZATION/LOCATION/EVENT/DATE/
NUMBER/POLITICAL_ACTOR, Step 9) and run it against Phase-1's expanded
benchmark's evidence rows; build the regression tests Step 9 requires
(the "Delhi Police vs. Burdwan Police" case class) before any
integration decision.

**Baseline**: `ENTITY_CONSISTENCY_EVALUATION.md`'s existing 1 TP / 4 FP
/ 1-2 likely-FP / 1 unevaluable result on $n=9$.

**Dataset**: DEV split's evidence rows (all claims with $\geq$1 cited
evidence row).

**Metrics**: entity-consistency check precision/recall against a
manually-audited sample (same audit discipline as the original
prototype); false-positive rate specifically on abstract-concept
entities (the prototype's main diagnosed failure mode).

**Expected outcome**: precision improves with typed entities (fewer
"Democracy"-as-entity false positives); recall remains bounded by cases
with zero extractable entities (a structural, not fixable-by-more-data,
limitation already named in the prototype's own writeup).

**Failure condition**: if true-positive rate at the new $n$ still
doesn't clear a cost/benefit bar for a 5th validator check (Rule 4 of
the original governing brief — no complexity without experimental
justification), do not integrate; publish the negative result exactly
as the original prototype already did.

**Stopping condition**: a single, pre-registered decision point after
this phase's evaluation completes — integrate or don't, based on the
measured precision/recall, not further iteration.

---

## PHASE 5 — Temporal consistency

**Hypothesis**: TruthLens currently has zero temporal-reasoning
capability (confirmed this audit: `time_reference` is an unstructured
free-text field, no check anywhere compares claim date to evidence
date), and this is a plausible, currently *undiagnosed* contributor to
verdict errors — "old footage presented as current" is a named,
real-world misinformation pattern this system cannot currently detect
in principle.

**Intervention**: structurally represent claim and evidence dates (not
string matching); add a deterministic temporal-consistency check (Step
10) as a 6th validator check, following the same pattern as the
existing 5 (a pure function over already-fetched data, no new LLM
call).

**Baseline**: zero — this is new capability, not an improvement to an
existing one. The "baseline" is TruthLens-without-this-check on the same
items, i.e., an ablation in the same sense as the existing validation
ablation (B4).

**Dataset**: any benchmark item where the claim asserts or implies a
specific time and cited evidence carries a `publication_date`
(`Source.publication_date` already exists in schema, confirmed unused
for this purpose today).

**Metrics**: temporal-mismatch detection precision/recall against a
hand-labeled sample; false-positive rate on legitimately time
-unanchored claims.

**Expected outcome**: a small but real catch rate, similar in kind to
the entity-consistency prototype's 1-TP-on-9 result — genuinely useful
regardless of whether it's large enough to integrate.

**Failure condition**: if source publication dates are too sparse or
unreliable (a real, plausible outcome given `Source.publication_date`
is nullable and its fill rate has never been measured) to support the
check at all, report that as the finding — a data-availability
limitation, not a reasoning failure.

**Stopping condition**: same pre-registered integrate/don't-integrate
decision pattern as Phase 4, one evaluation pass, not iterative tuning.

---

## PHASE 6 — Evidence retrieval

**Hypothesis**: the already-measured gap between primary-source
relevance (68.75%) and usable-evidence extraction (18.75%) — this
paper's own "single most important finding" of the evidence-quality
analysis — means retrieval quality is not the bottleneck; structured,
multi-query retrieval (Step 13) should therefore improve usable-evidence
rate more than it improves relevance rate, and that asymmetry itself is
the thing to test.

**Intervention**: implement the 5-query structure from Step 13
(exact-claim, entity-focused, primary-source, contradiction, context/
history) replacing today's simpler research-planning query generation;
measure each query type's individual contribution.

**Baseline**: current single/few-query `research_planning.py` output
and its measured 23.5% tier-classification / 68.75% relevance / 18.75%
usable-evidence rates ($n=68$ sources).

**Dataset**: DEV split.

**Metrics**: per-query-type search relevance, primary-source rate,
fetch-success rate, usable-evidence rate (the existing four-way metric,
Step 13's explicit instruction to optimize for usable evidence, not
relevance alone).

**Expected outcome**: the contradiction-query and primary-source-query
types disproportionately drive usable-evidence gains, since they target
specificity directly rather than topical relevance.

**Failure condition**: if usable-evidence rate does not move
meaningfully, the bottleneck is downstream of retrieval (e.g.
evidence-analysis stance-labeling quality, or claims that are too
general for any query to resolve — already a diagnosed root cause in
the existing "second major bug" finding) — report that explicitly rather
than attributing the gap to retrieval by default.

**Stopping condition**: once per-query-type contribution is measured and
ranked, keep only query types with a measurable positive contribution on
DEV; freeze before touching VALIDATION.

---

## PHASE 7 — Evidence reasoning

**Hypothesis**: expanding evidence-stance labels beyond the current 4
(supports/contradicts/provides_context/irrelevant) to the 8-category
scheme in Step 12 will separate two currently-conflated failure modes
that the existing "wrong entity, wrong event" and "insufficient detail"
qualitative findings already hint at, without those distinctions being
formally tracked.

**Intervention**: add the 4 new stance categories
(SAME_EVENT_WRONG_ENTITY, SAME_ENTITY_WRONG_EVENT,
TEMPORALLY_MISMATCHED, PARTIALLY_SUPPORTS/PARTIALLY_CONTRADICTS,
INSUFFICIENT_DETAIL, MENTIONS_ONLY) to `EvidenceStance`; test whether
downstream verdict reasoning quality improves when the model sees this
richer taxonomy vs. the current 4-way one (an A/B prompt comparison, not
just a schema change).

**Baseline**: current 4-category `EvidenceStance` enum and its measured
85.3% irrelevant / 11.8% contradicts / 2.9% supports distribution
($n=68$).

**Dataset**: DEV split's evidence rows.

**Metrics**: downstream verdict accuracy with 4-category vs. 8-category
stance (paired comparison on the same claims); category-assignment
inter-annotator agreement on a hand-labeled sub-sample (categories that
can't be reliably assigned by a human annotator aren't worth asking an
LLM to assign either).

**Expected outcome**: per Step 12's own instruction, categories are kept
only if they measurably improve downstream reasoning — this is
explicitly not a complexity-for-its-own-sake exercise.

**Failure condition**: if the richer taxonomy doesn't move verdict
accuracy and doesn't reach acceptable IAA, revert to the 4-category
scheme and report why — a negative schema-design result, same standing
as any other.

**Stopping condition**: one paired A/B comparison on DEV, decided before
touching VALIDATION.

---

## PHASE 8 — Validator improvement

**Hypothesis**: the 5 existing deterministic checks (citation existence,
source-fetched, numeric grounding, reasoning/label consistency,
supplementary-field grounding) plus any new checks that survive Phases
4/5/7 (entity, temporal, expanded evidence-consistency) together clear
meaningfully more of the "unsupported output" space than the current
40% recall (already measured, `VALIDATOR_SYNTHETIC_BENCHMARK.md`) — and
that the existing 100+-case adversarial suite (Step 18) is the right
instrument to measure this precisely, not the smaller real-data audit
alone.

**Intervention**: integrate whichever of Phases 4/5/7's new checks
individually cleared their own stopping-condition bar; re-run the
adversarial benchmark (expanded from today's 28 cases toward Step 18's
100+ target, adding the 20 categories it lists) against the *new*
combined check set.

**Baseline**: today's 4-check validator, 81.8% precision / 50.0% recall
on the existing 28-case synthetic benchmark; 100% precision / 40%
recall on the real 9-claim audit.

**Dataset**: REGRESSION split (Step 3) — 100–200 synthetic/adversarial
cases, expanding the existing 28.

**Metrics**: precision/recall/F1 per check and combined; per-category
catch rate (does each new category from Step 18 get caught by at least
one check, and by which).

**Expected outcome**: recall improves meaningfully (the existing 9/18
"checkable-by-design" cases were caught at 100%; the new checks target
exactly the categories the old 4 structurally cannot reach — wrong
entity, wrong date — so this is a real, motivated expectation, not a
hope).

**Failure condition**: if a new check's false-positive rate on the
`valid`-labeled cases rises, that check is not integrated even if its
recall contribution looks good — precision has held at 100% on real
data and 81.8% on synthetic data throughout this program's history, and
that discipline does not get relaxed to chase recall.

**Stopping condition**: once the REGRESSION suite is frozen (Step 3's
explicit requirement) and every existing test continues to pass, no
further validator changes without a new REGRESSION case justifying them.

---

## PHASE 9 — Cross-post provenance

**Hypothesis**: the already-formalized cross-post attribution problem
(4 of 6 scoreable benchmark items have their real false claim living
outside the specific post) is detectable at useful precision using only
free/local methods (perceptual hashing, embeddings, metadata), without
needing Gemini for the detection step itself.

**Intervention**: build cross-post detection (Step 16) using perceptual
/frame hashing (a genuinely new dependency — none exists today, confirmed
this audit) as the first-pass filter, `Claim.embedding` (pgvector,
already provisioned but unused) for claim-level similarity clustering as
a second pass, and only escalate to Gemini for a semantic cross-check on
pairs the free methods flag as ambiguous.

**Baseline**: zero — `media_content_hash` today only catches
byte-identical re-uploads, confirmed unable to catch the actual
cross-post scenario (re-encoded/re-uploaded video).

**Dataset**: a deliberately-constructed small set of known same-video
-different-caption pairs (needs manual construction/verification, since
this doesn't exist anywhere yet) plus the existing benchmark's 4
already-diagnosed cross-post items as a sanity check.

**Metrics**: cross-post detection precision/recall (perceptual-hash
stage alone, then + embedding stage, then + Gemini escalation stage —
reported as 3 separate numbers per Step 16, not one collapsed metric);
claim-recovery rate (does detecting the cross-post actually let the
system recover the claim that was missing).

**Expected outcome**: perceptual hashing alone likely has low recall
(re-encoding/cropping/logo-overlay defeats simple hashing) but high
precision; the embedding stage should raise recall at some precision
cost — this three-stage decomposition is itself the main deliverable,
independent of the final numbers.

**Failure condition**: if free/local methods cannot reach useful
precision/recall at all, this becomes a disclosed, named limitation
(exactly as the current paper already treats the problem) rather than a
forced integration.

**Stopping condition**: once the 3-stage pipeline is measured on the
constructed pair-set, decide whether to attempt integration into the
live pipeline or keep it a documented, unintegrated capability, matching
this program's existing precedent for the entity-consistency prototype.

---

## PHASE 10 — Aggregation

**Hypothesis**: the existing deterministic aggregation rule
(`derive_overall_verdict()`) already shows a real, measured benefit
(50.0% vs. 25.0%, $n=4$, the claim-decomposition counterfactual) that a
larger benchmark will either confirm at higher power or reveal to be an
artifact of the specific 4 items involved.

**Intervention**: re-run the same counterfactual reanalysis methodology
(single-claim-only vs. full-decomposition aggregation, using
already-collected per-claim verdicts, no new LLM calls) on Phase-1's
expanded benchmark's multi-claim items.

**Baseline**: the existing $n=4$ result already in the paper.

**Dataset**: all VALIDATION-split items with $>1$ verifiable claim.

**Metrics**: paired accuracy (single-claim vs. full aggregation),
McNemar's exact test once $n$ is large enough for it to be informative
(explicitly not claimed informative at $n=4$, per the existing paper's
own honest caveat).

**Expected outcome**: the direction holds (aggregation helps) at a
narrower, more defensible confidence interval.

**Failure condition**: if the effect shrinks or reverses at higher $n$,
report that as a real update to the paper's central architectural claim,
not a result to explain away.

**Stopping condition**: one re-run at each of VALIDATION and (once
frozen) TEST; no further tuning of the aggregation rule table based on
either result.

---

## PHASE 11 — Adversarial evaluation

**Hypothesis**: the REGRESSION suite built across Phases 8 (validator
-specific) can be extended into a full end-to-end adversarial suite (the
20 categories in Step 18: wrong entity/event/date/number/unit/speaker,
partial support, contradictory sources, irrelevant source, hallucinated
citations, OCR/audio corruption, caption mismatch, cross-post mismatch,
old footage, AI-generated image, edited video, mixed-language, multiple
claims) covering the *whole pipeline*, not just the validator in
isolation.

**Intervention**: construct 100+ synthetic/adversarial end-to-end cases
per Step 18's categories; run the full pipeline (not just
`validate_verdict()` in isolation) against each.

**Baseline**: today's real-content-only evaluation has no adversarial
end-to-end coverage at all — this is new capability.

**Dataset**: the REGRESSION split, explicitly **not** used as ground
truth for the main real-world benchmark (Step 18's explicit
instruction).

**Metrics**: per-category pass/fail rate across the whole pipeline (not
just the validator); which pipeline stage is the earliest point of
failure per category (an error-budget-style breakdown, extending
`ERROR_BUDGET.md`'s existing method to synthetic cases).

**Expected outcome**: categories the validator alone can't reach (Step
18's #12 OCR corruption, #13 audio corruption, #17 AI-generated image,
#18 edited video) surface failures upstream, in ingestion/transcription/
OCR/vision — genuinely new information the validator-only benchmark
structurally cannot provide.

**Failure condition**: none in the traditional sense — this phase is
diagnostic by design; every failure found is a success for the phase's
actual goal (find failure modes), logged per Step 19's process
(root-cause, regression test, fix, re-run regression + validation,
measure collateral damage).

**Stopping condition**: 100 cases minimum reached, or three consecutive
category-additions produce zero new distinct failure modes (the same
diminishing-returns signal used in Phase 1).

---

## PHASE 12 — Final frozen benchmark

**Hypothesis**: none — this is a process phase, not an experimental one.

**Intervention**: freeze TEST (Step 3's explicit requirement) once
Phases 1–11's system changes are complete; tag the freeze point in git
per this program's existing precedent (`truthlens-day8-frozen`,
`truthlens-day9-general-fixes`); from this point forward, no prompt/
threshold/model/retrieval/validator/aggregation change may be justified
by a TEST result — any TEST failure becomes a TEST-v2 or REGRESSION
case, never a reason to retune the frozen system.

**Baseline**: n/a.

**Dataset**: the full Phase-1 expanded benchmark, split into DEV/
VALIDATION/TEST per Step 3's targets (50–100/20–30/40+, scaled down
proportionally against whatever total $n$ Phase 1 actually reaches,
since the ideal targets assume more items than a single sourcing effort
may realistically produce).

**Metrics**: split sizes and composition (reported honestly against
target, per Phase 1's own precedent of not forcing artificial balance).

**Expected outcome**: a genuinely frozen, disjoint TEST set exists for
the first time in this program's history — today's "held-out" 9-item
set is held out from *development*, but was never partitioned from a
larger pool with its own DEV/VALIDATION siblings.

**Failure condition**: n/a.

**Stopping condition**: freeze is permanent for the remainder of this
roadmap version; only a new roadmap version (V3) may unfreeze it.

---

## PHASE 13 — Paper update

**Hypothesis**: none — synthesis phase.

**Intervention**: update `research_paper/main.tex` **only** with
measured TEST-split results from Phases 1–12, following this program's
existing, already-proven discipline (Rule 1: no fabrication; Rule 3:
negative results reported with equal prominence; Step 31's claim
-discipline — every sentence traceable to a specific experiment or
explicitly labeled hypothesis/future work). Update
`CLAIM_EVIDENCE_MATRIX.md` in the same pass so every new number is
traceable, exactly as the existing matrix already does for the current
18 tracked claims.

**Baseline**: the current paper (21pp total, $\sim$16pp counted body,
committed `c2951cd`).

**Dataset**: n/a (writing phase).

**Metrics**: n/a — the deliverable is the paper itself, plus a re-run of
the existing IEEE 3-reviewer + area-chair simulation against the new
draft (this program already has a working method for this,
`IEEE_REVIEW.md`).

**Expected outcome**: a paper whose headline comparison has real
statistical power for the first time, with RQ5 (bias) and RQ3
(multimodal) upgraded from "directional" to "supported" if their
respective phases clear that bar — and downgraded, disclosed, or
withdrawn if they don't.

**Failure condition**: if a claim currently in the paper is contradicted
by Phase 1–12 results at higher $n$, the paper is corrected, not
defended — exactly the standing precedent from the baseline-confound
reversal.

**Stopping condition**: paper update is complete when every claim passes
the Step 31 test ("what exact experiment supports this?") and the
IEEE review simulation's page-length/density objections (the only
objections without a correctness component, per the existing
`IEEE_REVIEW.md`) are re-assessed against the new content volume.

---

## Work order note (mapping to Step 36)

Step 36's PHASE 0–17 work order interleaves infrastructure-first
sub-steps ahead of the 13 phases above. Read as: **PHASE 0** = this
audit (`AUDIT_REPORT_V2.md`); **PHASE 1** (work-order) = existing
-benchmark audit, done next in this same session; **PHASE 2–3**
(work-order) = Benchmark V2 + regression infrastructure, feeding
**PHASE 1** above; **PHASE 4–12** (work-order) map one-to-one onto
**PHASE 2–10** above in the same order; **PHASE 13** (work-order) =
large-scale local experiments, cutting across **PHASE 1–11** above;
**PHASE 14** (work-order) = the Gemini cross-check experiment (Step 22),
which is deliberately *not* one of the 13 named phases above since it's
explicitly gated as "only after all reasonable free/local work is
complete" (Priority 2/3) rather than owning its own phase; **PHASE
15–17** (work-order) = **PHASE 12–13** above.
