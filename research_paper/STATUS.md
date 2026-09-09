# Paper status

Last updated: 2026-09-09 (fourteenth update: length compression pass,
34 -> 27 pages). See below; prior updates preserved unedited underneath.

## Latest update (this pass, 2026-09-09) -- compress to 27 pages

Brought the paper from 34 to 27 pages (target 25-28) by summarising
prose, with **zero diagrams, charts, tables or findings removed** (9
`\includegraphics` + 1 TikZ architecture diagram + 18 tables, all
intact; every numeric result and disclosure kept). Source `main.tex`
3556 -> 2712 lines.

What was compressed (prose only, essence kept):

- **Appendix "Full Taxonomy of Failure Modes"** -- the 24 entries, each
  a ~10-line paragraph, condensed to one line each (symptom + fix).
  ~248 -> ~32 lines.
- **Appendix "Extended Foundation-Phase Detail"** -- 19 per-experiment
  `\subsection`s condensed to a one-line-per-experiment list keeping
  every number. ~233 -> ~50 lines.
- **Body "Foundation-Phase System Extensions"** -- the per-EXP
  narrative collapsed to dense subsections; all load-bearing findings
  kept (Checks 6/7 + 81.8/50.0 -> 87.5/60.9; the 4x reliability
  finding; prompt-injection 1/5 -> 0/5; verdict-reliability 0/14 +
  Check 8; mass-sourcing ~1-per-900 yield; the platform-relaxation
  bridge to TruthLens-202). ~413 -> ~216 lines.
- **Conclusion** -- 6 re-narrating paragraphs -> 3 tight ones. 165 ->
  ~69 lines.
- **Future Work** -- 16 items (many already "addressed") -> 8 focused
  items. 124 -> ~47 lines.
- **Discussion** -- trimmed ~25%, table `tab:whenhelps` kept intact.
- **Appendix "Threats to Validity: Full Reasoning"** -- extra reasoning
  per threat tightened; stale "ten threats" -> "twelve". 83 -> ~59.

Compile: `tectonic` clean -- no undefined refs/citations, no
multiply-defined labels, `main.out` stable (no rerun), **0 overfull
hboxes**, 27 pages. Visually spot-checked the compressed Foundation-Phase
section, Future Work, and Conclusion pages -- two-column layout intact,
no overflow, reads professionally.

## Prior update (thirteenth, 2026-09-09) -- V3 pre-registration + defect fix

Sets up "one more experimental iteration" (improved claim extraction ->
run on all 193 -> baselines on 193 -> full metric report -> second-pass
annotation). A multi-agent design pass produced the plan; its verifier
agents hit a session limit, so the author reconciled it against the
rigor + feasibility lenses directly.

**New pre-registration artifacts (committed before any V3 run):**

- `research/EXPERIMENT_PROTOCOL_V3.md` -- the frozen protocol. Key
  decisions: (1) claim-extraction v2 = 8B model for the extraction
  stage ONLY (downstream stays 3B; an 8B smoke test measured ~90s/call
  on this 8GB box, so all-stages-8B is infeasible) + a v5 prompt (6
  changes, each tied to one observed failure type) + a deterministic
  post-filter (F1 triviality / F2 recitation / F3a debunk-framing / F4
  quote-sanitation / F5 incidental). (2) The proposed article-echo leak
  guard (F3b) is CUT -- comparing the system's own output against
  fact-check text and then scoring it is fatal contamination. (3)
  Framing is post-registered, NOT blind: the failure types were read
  off the published 3B run, so v2 is tuned only on the 9 dev items + a
  synthetic diagnostic set and the 193 run is one held-out confirmation
  shot. (4) Full-193 configs: C0 (3B+v4, frozen) / C1 (3B+v5+filter,
  new) / C3 (8B-extraction+v5+filter, new); C2 (8B-extraction+v4) on
  dev + a 40-item subsample; post-filter on/off is a free re-score. (5)
  Baselines B1/B2/B3 x {SHARED = every config gets the same frozen v5
  extraction claims; ORACLE = every config gets the reviewer's
  ground_truth_claim, labeled a non-comparable upper bound}; verdict on
  3B; one shared on-disk search cache so retrieval is held constant and
  DuckDuckGo rate-limiting can't bias later configs. (6) Deterministic
  n=56 second-pass subsample, PABAK/Gwet's AC1 as the headline agreement
  stat (kappa paradox under 83% FALSE), disclosed as intra-project
  LLM-assisted re-annotation, NOT an independent-human IAA study. (7) A
  provenance no-claim adjudication rubric -- bin the no_verifiable_claims
  items (i) correct scope-limited abstention / (ii) genuine text-coverage
  failure / (iii) degraded input, judged against the actual ingested
  text; report the adjusted coverage-failure rate as the lead number,
  65.3% as deployment reality. (8) Pre-declared falsification criteria
  (confirms / stronger-form / falsifies a-e / inconclusive band) with
  each branch's paper rewrite drafted before the C3 numbers are seen.
- `research/METRICS_ADDENDUM_V3.md` -- 12 metric definitions
  pre-registered before the freeze (balanced accuracy on both
  denominators; corpus-level bucketed accuracy; the false-abstention
  relabel; macro-F1 scope; resolution & no-claim-rate formulas; the
  baseline extraction-source condition; the ORACLE reference row;
  claim-extraction instrumentation; is_visual_claim handling;
  support-validity stratified sampling; constant-predictor references;
  the ground_truth_tier backfill rule).

**Live-defect fix applied to the shipped draft this pass:**

- `score_local_eval.py` and Table VI called
  `(UNVERIFIED-resolved + no_verifiable_claims)/193 = 155/193 = 80.3%`
  the **"false-abstention rate"**. METRICS.md defines that term strictly
  as UNVERIFIED *outputs* on Tier-1 items / Tier-1 items = **29/193 =
  15.0%**. Table VI now shows the strict 15.0% AND relabels the 80.3%
  figure as a **"declined-to-answer / non-response rate"**; the scorer
  emits both under the correct names. Paper recompiles clean, 34 pages,
  0 overfull.
- `items_v2.jsonl`: `ground_truth_tier` backfilled to `1` on all 193
  (every item traces to a professional fact-check with a verbatim anchor
  quote -> Tier-1 by construction, which the scorer already assumed).

No experiment has been run yet -- this pass only froze the protocol and
fixed the metric label. The V3 runs are the next work.

## Prior update (twelfth, 2026-09-09) -- tighten and polish

Structural/readability pass, no new results:

- **Results section reordered** so the two evaluations are cleanly
  separated: VII-A methodological correction -> VII-B six-item headline
  -> VII-C "a real gap found and fixed during the six-item re-run"
  (retitled from "...during this exact run" -- ambiguous once there are
  two runs) -> VII-D \textsc{TruthLens-202} local-only evaluation
  ($n$=193). All six-item material now precedes all 193-item material.
- **All 7 overfull hboxes eliminated (now 0).** Fixes: `\tabcolsep`
  reduced and headers shortened on the related-work table (Tab.~I), the
  RQ-status table (Tab.~II), the six-item comparison table
  (Tab.~V: "Superseded Acc." -> "Superseded", etc.), and the per-item
  conditions table (Tab.~whenhelps: "TruthLens" -> "TL"); the
  \textsc{TruthLens-202} composition table (Tab.~IV) switched to
  wrapping `p{}` columns with abbreviated row labels; one TikZ
  architecture-diagram node reworded ("substantiveness-check" ->
  "quality-check"); one long appendix URL made line-breakable with
  `\allowbreak`.
- Compile clean via `tectonic` 0.17.0: 0 overfull, no undefined
  refs/citations, no multiply-defined labels (only the standing
  `TU/ptm` font-substitution notes). 34 pages, unchanged. Visually
  re-verified pages 4, 9, 11, 12.

## Prior update (eleventh, 2026-09-09) -- TruthLens-202 local-only evaluation

Runs the full pipeline over all 193 `validation` items in the local
-only configuration (every LLM stage on local `llama3.2` 3B, keyless
DuckDuckGo search, `GEMINI_API_KEY` unset so every escalation path is
inert -- the $0/no-key config the project targets) and folds the real
numbers into the paper. No prompt/threshold/model choice was changed in
response to the results; reported as a first-run floor.

**How it was run (no app redesign):**

- New `backend/research/benchmark_v2/run_local_eval.py` -- resumable
  harness that executes the exact production stage functions
  (`claim_extraction` -> `research_planning` -> `search_fetch` ->
  `evidence_analysis` -> `verdict`) in `orchestrator.analyze_reel`
  order, then `derive_overall_verdict`, one METRICS.md-schema row per
  item. Refuses to start if a Gemini key is present. Ingestion not
  re-run (reuses each item's real transcript/OCR from promotion).
- New `score_local_eval.py` -- METRICS.md-exact scoring: bucketed
  accuracy over `resolved` items, balanced accuracy, macro/per-class
  F1, confusion matrix, abstention / false-abstention / research-failed
  rates reported separately, Wilson CIs, breakdowns by
  platform/label/language/vision-availability.
- New `figures_local_eval.py` -- `fig9` (outcome distribution) and
  `fig11` (per-class P/R/F1) into `research_paper/figures/`, house
  style; refuses to draw if the run is incomplete.
- Raw output: `research/results/local_eval_v2.jsonl` (193 rows),
  `LOCAL_EVAL_V2_REPORT.md`, `local_eval_v2_scores.json`.

**The result (real, first-run, local-only):**

- Outcome split: **67/193 resolved (34.7%)**, **126/193
  `no_verifiable_claims` (65.3%)**, 0 `research_failed`, 0 `error`.
- Bucketed accuracy on resolved: **20/67 = 29.9%**, Wilson 95% CI
  [20.2%, 41.7%]. Balanced accuracy **22.2%** -- *below* an
  always-`FALSE` predictor's 33.3%. Macro-F1 **0.194**.
- Per-class: `FALSE` P .80 / R .21; `MISLEADING` **0/7**; `TRUE` 1/3.
- Abstention 43.3% of resolved; false-abstention 80.3% of all items.
- The 11 "false claim -> affirmative verdict" cases are
  claim-*coverage* failures (a dialogue fragment extracted instead of
  the post's assertion), not verdict-reasoning failures.
- Vision context gave no benefit (27.6% with vs 31.6% without).
- Firm transferable finding: with a local 3B model, **claim extraction
  -- not retrieval, not verdict reasoning -- is the binding
  constraint**; it fails on ~2/3 of real posts.

**Paper edits (main.tex):**

- Abstract contribution (3) rewritten from "no accuracy reported" to
  the full local-only result, framed as a floor.
- New Results subsection `sec:tl202eval` ("TruthLens-202: local-only
  end-to-end evaluation, n=193") -- config rationale, outcome +
  headline table (Tab.~VI), per-class table (Tab.~VII), confusion
  matrix (Tab.~VIII), Fig.~4/5, failure decomposition, breakdowns,
  "what this is and is not".
- `sec:truthlens202` limitation (1) changed from "not yet evaluated" to
  "one configuration evaluated so far".
- Contributions bullet 7, Intro, `sec:dataset` preamble,
  `sec:massSourcing` bridge, Future Work items 1 & 8, Threats to
  Validity (last two bullets), Conclusion -- all updated from
  "corpus/artifact, no result" to "evaluated once, local-only floor;
  stronger configs (8B local, vision-first extraction, metered cloud
  escalation) reported as a capability/cost ablation is the open work".

**Compile:** `tectonic` 0.17.0, clean -- no undefined refs/citations,
no multiply-defined labels; 7 overfull hboxes, all pre-existing
appendix/bib region, none new. **32 -> 34 pages.** Visually verified
pages 1 (abstract), 11-12 (new subsection + 3 tables + 2 figures) via
`pdftoppm`; two cosmetic fixes applied (paragraph-heading double
punctuation; Fig.~4 x-axis label overlap) and re-verified.

**Not changed:** the `[Affiliation placeholder -- TODO]` on page 1. The
frozen 6-item comparison and all `n=6` results are untouched -- the
local-only run writes to the separate `validation` split only.

## Prior update (tenth, 2026-09-08) -- TruthLens-202 + quality pass

Folds in the all-platform, review-gated benchmark-scaling session that
grew the `validation` split from 13 to 193 items (202 with the frozen
9-item `dev` set): the **TruthLens-202** corpus. Also a general
professional-quality pass over the abstract and framing per explicit
instruction ("make it like a professional research paper, emphasis on
quality").

**What changed in `main.tex`:**

- **Abstract** rewritten into an explicit three-contributions arc
  (methodological correction / support-validity construct + validator
  recall 16.7->40% + claim-decomposition counterfactual n=4 / the
  TruthLens-202 artifact). Scope line broadened from "Instagram Reels"
  to "short-form political video and image posts". States loudly, in
  the abstract itself, that **no reel-level accuracy on TruthLens-202
  is reported here** -- it is a contributed artifact, not a contributed
  result.
- **New `\subsection{TruthLens-202}` (`sec:truthlens202`, Section VI-F)**
  before Results, with subsubsections: why the platform scope was
  relaxed (the measured Instagram-only ~1-per-900 yield, cross
  -referenced to the existing `sec:massSourcing` finding, not a new
  claim); sourcing pipeline (11,544 candidates screened across seven
  archives); review-gated annotation protocol (four recorded fields,
  ground truth anchored to a verbatim fact-check quote); composition +
  **new Table IV**; leakage/split discipline; and five plainly-stated
  limitations (not yet evaluated / single LLM-assisted reviewer, no IAA
  / ~88% single-source Alt News / visual-context deferred on 115 /
  still Indian-domain, English-majority).
- **`sec:massSourcing`** given a forward bridge ("this finding was
  subsequently acted on"); the stale "dataset stands at 22 items" line
  removed.
- **Intro, Contributions (new bullet 7), Threats to Validity (+2
  bullets, "Ten threats" -> "Twelve"), Future Work (items 1 and 8),
  Conclusion** all updated to introduce TruthLens-202 consistently and
  to state end-to-end evaluation + a second annotator as the immediate
  open work.

**Every number in the new material was verified against the actual
dataset files this pass** (`items.jsonl`, `items_v2.jsonl`,
`candidates_v3_*.jsonl`, `review_batch.jsonl`), and three drafted
figures were corrected to match: Language row `English 146, Hindi 52,
Bengali 3, Arabic 1` (a spurious "mixed 1" removed); Media row
`video 200, photo 2` (was 199/3); and the annotation-protocol prose now
carries the real ledger -- 372 adjudicated (166 promote / 148 defer /
58 reject), 165 completing ingestion, 206 `deferred_crosspost` markers,
28 pre-protocol items (9 `needs_review` + 19 unmarked), arithmetic
shown as `165 + 28 = 193`. Label/platform/claim-type/fact-checker
/modality rows were checked and already matched.

**Compile:** `tectonic` 0.17.0, same engine as every prior compiled
update. Clean -- no undefined references, no undefined citations, no
multiply-defined labels; only the pre-existing font-shape and two
-column line-breaking badness warnings (7 overfull hboxes, all in the
pre-existing appendix/bib region, none new). **Page count 30 -> 32.**
`main.pdf` regenerated (373 KiB).

**Visually verified** via `pdftoppm` (100 dpi PNGs): page 1 (abstract,
three-contribution arc sets correctly), page 8 (start of
`sec:truthlens202`, two subsubsections, two-column layout intact), page
9 (review-gated-protocol paragraph with the corrected ledger + Table IV
with the corrected Language and Media rows, no overflow, fits the
column), page 10 (composition tail + limitations (4)-(5), clean
transition into Section VII Results). No `??`, no missing glyphs, no
broken cross-references on any page checked.

**Not changed:** the `[Affiliation placeholder -- TODO]` on page 1
(same deliberate placeholder logged in every prior update). The frozen
6-item paired comparison and all `n=6` results are untouched --
TruthLens-202 is a strictly separate `validation` split with no result
reported on it.

## Prior update (ninth, 2026-09-07) -- recompile only

Closes the one open item the eighth update (below) left behind: that
pass edited `main.tex` (the `sec:publishing` and `sec:massSourcing`
subsections, plus Abstract/Conclusion/Future-Work additions) but had no
LaTeX toolchain available, so it was never compiled or visually
verified. `tectonic` 0.17.0 was available this pass. Recompiled with it,
same engine as every prior compiled update:

- **Clean compile.** BibTeX ran clean (`main.blg`: `Done.`, no
  warnings). No undefined references, no undefined citations, no
  multiply-defined labels, no "rerun to get cross-references right"
  (`rerunfilecheck` confirms `main.out` stable). Only the pre-existing
  `TU/ptm` font-shape substitution warnings and two-column
  hbox/vbox-badness line-breaking warnings that every prior compile of
  this document also emitted -- none new.
- **Page count 28 -> 30**, matching the eighth update's own note that
  the two new subsections plus abstract/conclusion additions grew the
  paper. `main.pdf` regenerated (this is the only file changed).
- **Visually verified** via `pdftoppm` (110 dpi PNGs): page 1
  (Abstract, both new sentences present and set correctly), page 6
  (new "E. Stage 10: human-approval-gated publishing" subsection,
  renders fully, two-column layout intact), page 18 (mass-sourcing
  result paragraph + start of the failure-mode taxonomy, now "24
  entries"), page 21 (Conclusion + Future Work items 13-16 with updated
  status text), page 30 (end of Appendix + References, 13 refs, document
  terminates cleanly). No overflow, no missing glyphs, no `??`.
- **Not changed:** the `[Affiliation placeholder -- TODO]` on page 1 is
  the same deliberate placeholder logged in prior updates -- left as-is,
  not this pass's call to fill in.

`main.tex` itself was not edited this pass -- content is exactly as the
eighth update left it; this pass only produced the compiled artifact it
was missing.

## Prior update (eighth, 2026-08-18) -- project paused

Folded in the mass-sourcing/benchmark-scaling session
(`research/MASS_SOURCING_V2.md`) and the Instagram-publishing pipeline
verification, both run after the second autonomous pass above. New
content: a `sec:publishing` subsection under Architecture (Stage 10 --
human-approval-gated Meta Graph API publishing, present since the
initial build but newly given 18 tests after a zero-coverage gap was
found; not yet exercised against a live account); a `sec:massSourcing`
subsection under Foundation-Phase (five independent fact-checker
archives crawled via a new automated judge pipeline, two real filter
-coverage bugs found and fixed, benchmark grown 15$\to$22, and the
central disclosed result -- a blended yield of roughly one promotable
item per 900 candidates checked, an order of magnitude below the prior
$\sim$8\% estimate, reported as a structural finding about where this
misinformation pattern is actually posted, not a tooling gap); a closing
paragraph in the Conclusion and a corresponding Abstract addition,
matching this paper's standing practice of never letting the abstract
undersell what the body now supports; Future Work item 1 updated to
reflect the re-measured binding constraint.

**Disclosed limitation on this update specifically**: no LaTeX toolchain
(`pdflatex`/`xelatex`/`lualatex`) was available in the environment this
pass ran in, so unlike every prior update logged below, this one was
**not** recompiled or visually verified page-by-page via `pdftoppm`.
What was checked instead: brace balance across the full document (equal
open/close counts), every new `\label{}` confirmed non-duplicate, and
every `\ref{}` (new and pre-existing) confirmed to resolve to a real
label -- catching the class of error most likely from hand-edits, but
not a substitute for an actual compile. Recompiling and visually
verifying the new pages is the first thing that should happen before
this version is treated as final.

## Prior update (seventh, 2026-08-18)

Folded in everything from EXP-021 through EXP-029 (`backend` commits
`a06cb9f` through `491d4b5`), across two further autonomous passes that
followed the foundation-phase program below. New content: a
`sec:followup` subsection (EXP-021-024: `source_quote` prompt fix
measured negative; input-signal consistency check found infeasible;
multilingual-extraction bias corrected after checking a much larger
sample; real VALIDATION-split data populated for the first time) --
this was written in an earlier pass but not yet logged here -- plus a
new `sec:secondpass` subsection (EXP-025-029): the aggregation
counterfactual unlocked on real VALIDATION data ($n=1$); cross-post
stage 2 diagnosed as blocked on a concrete, confirmed infrastructure
gap (no local embedding support); a prompt-injection defense with zero
prior test coverage measured live (1/5 attempts succeeded pre-fix, 0/5
after a structural delimiter fix plus a hardened prompt, with the
downstream validator independently confirmed to neutralize the pre-fix
success); a genuinely new, reproducible verdict-stage reliability
-weighting failure found and honestly reported as unresolved after a
measured, insufficient prompt fix (0/14 real trials correct, before and
after); and the evidence-stance taxonomy re-run with its named
confound fixed, surfacing a deeper, now-quantified constraint (a
confirmed 20-requests/day Gemini free-tier cap) rather than a clean
answer.

The failure-mode taxonomy grew from 21 to 24 entries (3 new: a
Gemini-quota test-isolation gap, the prompt-injection delimiter
-spoofing structural fix plus its measured partial mitigation, and the
verdict reliability-weighting gap) -- Appendix A and
Section~XIII/\ref{sec:failuremodes} both updated, plus every "21" count
elsewhere in the paper. Future Work items 3 and 14 updated from
"undone" to "diagnosed, concrete blocker named"; two new items (15, 16)
added. Abstract and Conclusion both extended with a summary paragraph,
matching this paper's standing practice of never letting the abstract
undersell what the body now supports. Recompiled clean (0 errors, 0
undefined references), 25$\to$28 pages, every new page visually
verified against source content via `pdftoppm`, not just checked for
compiler success.

## Prior update (fifth, 2026-08-18, foundation-phase program)

Folded in the foundation-phase research program (`research/
RESEARCH_ROADMAP_V2.md`, experiments EXP-009 through EXP-020, `backend`
commits through `6b37ccb`): a new Section XII ("Foundation-Phase System
Extensions", `sec:foundationphase`) and a matching new Appendix A
subsection ("Extended Foundation-Phase Detail", `sec:appendixfoundation`)
reporting real, measured, component-level work run since the last
update. Explicit scope discipline stated in the new section itself:
none of it re-measures reel-level accuracy or touches the frozen paired
six-item comparison (Section VII) -- the new benchmark items are held in
a genuinely separate `validation` split, and the roadmap's own formal
freeze (its Phase 12) has not occurred.

**What's new, in one paragraph**: the benchmark grew 9$\to$15 items
(12 FALSE/2 MISLEADING/1 TRUE); two new deterministic validator checks
(temporal consistency, entity consistency) were integrated only after
each cleared its own evaluation bar, measurably improving the
adversarial synthetic benchmark (81.8%/50.0% $\to$ 87.5%/60.9%
precision/recall, zero new false positives, and a direct re-test
closing a previously-named, explicitly-disclosed gap case); and, most
consequentially, four independent experiments -- none of them a
dedicated reliability study -- converged on the same finding: raw,
un-retried local-model (llama3.2) output on real content is
substantively empty or unusable a large fraction of the time, and this
system's Gemini-escalation defenses are carrying more of the real
reliability burden than a component-level pass/fail reading would
suggest. Three further extensions were built and measured with real,
disclosed (not assumed) results: structured 5-query retrieval (a
genuine mixed-to-negative finding, root-caused to one claim with no
natural institutional subject), a full 8-combination multimodal
re-analysis (reproduces rather than resolves the original non-monotonic
surprise), and a perceptual-hash cross-post detector's first stage
(validated against real video frames; stages 2-3 not yet built). A
bounded six-case adversarial stress test of claim extraction found zero
crashes but surfaced two newly-named, not-yet-investigated structural
gaps (input-signal consistency, multilingual extraction bias).

Abstract, Future Work (5 items updated to reflect real progress, 3 new
items added), and Conclusion were all updated to match. Recompiled
cleanly via `tectonic` (zero undefined references, zero missing
-character warnings, only pre-existing font-shape substitution warnings
common to IEEEtran/Times) and visually re-verified page-by-page via
`pdftoppm` -- new Section XII (pages 13-14), new Appendix A subsections
(pages 22-23), and the updated abstract/Future Work/Conclusion pages
all confirmed rendering correctly, no overflow, no broken cross
-references. **Page count grew 21$\to$24** -- disclosed here plainly,
not hidden; this pass prioritized completeness and honesty of the new
material over the page-trimming discipline earlier passes applied, per
explicit instruction to add all of this session's findings. A future
pass should revisit trimming if a specific venue's page limit requires
it -- not attempted this pass.

## Prior update (fourth, 2026-08-13)
in). Still genuinely multi-session.

## Latest update (this pass)

Folded in the third live-testing round (`backend` commit `dbd04ae`): a
new Evaluation subsection (`sec:thirdpilot`, new Section V-J) reporting
a real Instagram post that surfaced two infrastructure bugs outside the
LLM reasoning stages — claim extraction silently accepting
schema-valid-but-empty-string claims (invisible to the existing
grounding check, which is a no-op whenever every claim comes back
non-verifiable), and a Gemini provider wrapper whose error handling was
written against the wrong SDK exception hierarchy, letting a routine
daily-quota 429 crash an in-flight request after ~40 minutes instead of
failing fast. Both fixed and live-reverified; a pre-existing unit test
for the second bug had mocked the same wrong exception type the
production code mishandled, so it was rewritten against real instances
of the SDK's actual hierarchy. Reported honestly as a mixed result —
this specific post still has no finished fact-check, since Gemini's
quota was exhausted by the time both fixes were verified. Updated
Section IV-C's cascade methodology to document the new claim-extraction
substantiveness check (it previously only described the grounding
check), added two Section VI taxonomy entries, a Section VII
threats-to-validity paragraph, and touched the abstract/conclusion.
`main.tex` is now 13 pages, recompiled cleanly via `tectonic` (no
undefined references, no missing-character warnings), visually
re-verified page-by-page.

## Prior update (primary-source-retrieval fix)

Folded in the primary-source-retrieval fix (`backend` commit
`6671d75`): a new Evaluation subsection (`sec:primarysourcefix`, new
Section V-F) reporting real, live-tested before/after numbers —
pooled 19 of 20 (95%) sources landing in a primary tier across four
successful `tier1_primary` queries, versus the paper's existing 8 of 72
(~11%) baseline — plus the honest negative results alongside it: 3 of 7
real queries returned zero results, a "Karni Sena" query showed
domain-correct sources can still be topically irrelevant, and a newly
found `.gov.in` page-fetch-reliability gap (403s and TLS certificate
failures on several ministry/state sites, masked by falling back to
search-snippet text) was deliberately left unresolved rather than
patched with an under-examined certificate-verification change. Updated
Future Work item 5 (was a pure aspiration, now "substantially addressed,
one gap remaining"), added a Discussion/threats-to-validity paragraph
specifically about the fetch-reliability gap, and updated the
Abstract/Conclusion to reflect the fix. `main.tex` is now 12 pages,
recompiled cleanly via `tectonic` with no undefined references and no
missing-character warnings, visually re-verified page-by-page via
`pdftoppm`.

## Prior update (photo-post + grounded-corrections)

Folded in everything from the photo-post-support and grounded-corrections
engineering work: a new System Architecture subsection on multi-modal
(video/photo) ingestion; a new Methodology subsection on the
`corrected_fact`/`context_note` mechanism, including the explicit,
motivated decision NOT to build consequence-speculation; a new
Evaluation subsection (`sec:secondpilot`) reporting the second
out-of-sample pilot in full, including the three-downgrades-then-one
-clean-pass pattern that real-world-tested the verification-gated
cascade under conditions we didn't script; four new taxonomy entries
(single-digit headline fabrication, discarded vision-read text, missing
₹ glyph, unresolved vision-transcription accuracy); a new Future Work
item; two new Discussion/threats-to-validity notes (both new mechanisms
are single-case-tested); and abstract/contributions/conclusion updates.
`main.tex` is now 11 pages. One real embarrassment caught before it
shipped: a draft sentence used the literal "₹" character to describe the
missing-glyph bug and hit the exact same missing-glyph problem in the
paper's own PDF (Latin Modern also lacks that glyph) — replaced with
words, not the character, same fix philosophy as the actual code.

## What's real and done

- `main.tex` — full draft, IEEEtran conference format, 11 pages, all
  with real content. Nothing in it is fabricated: every citation is in
  `references.bib` and traceable in `SOURCES.md`;
  every evaluation number is either a live query result against the
  actual TruthLens database, a real `POST /api/reels/quick` run against a
  genuinely new reel, or a real LLM call to the naive-baseline script.
- `references.bib` / `SOURCES.md` — 14 references, all fully verified
  (title/authors/venue/year) via direct fetch of the paper's own page.
  A real citation error (statistic attributed to the wrong paper) was
  caught and fixed during this verification pass — see SOURCES.md.
- `main.pdf` compiles cleanly via `tectonic` (no sudo/BasicTeX needed).
  Visually verified page-by-page; two real LaTeX layout bugs were found
  and fixed this way (table column overflow; description-list label
  overlap).
- **`benchmark/` — a real out-of-sample pilot, not just development
  telemetry.** Two Instagram reels TruthLens had never seen, each
  independently fact-checked by a professional Indian fact-checking org
  (BOOM Live, Alt News), sourced by fetching the org's own article and
  extracting the live Instagram post it had embedded as evidence — see
  `benchmark/PROTOCOL.md` for the sourcing method and
  `benchmark/results.md` for full results. On both, TruthLens's
  reel-level verdict agreed with the independent ground truth. But the
  pilot's more important finding: on the second case, the label match
  was coincidental, not earned — TruthLens's text-derived claim
  extraction missed the actual (purely visual) misinformation entirely.
  This is now written up in the paper itself (Section V-F, and two new
  entries in the Section VI taxonomy) as the top Future Work item.
- **A real bug found and fixed via this pilot, not just documented**:
  a verdict the deterministic validator had already downgraded still had
  its full free-text reasoning (including an entity-confused,
  unsupported claim about a real organization) reused verbatim on a
  rendered slide and as input to a downstream LLM call. Fixed in
  `backend/app/pipeline/reel_content.py` and
  `backend/app/pipeline/validation.py` (commit `2c12e36`), verified
  directly against the real database row that caused it, and the full
  backend test suite (93 tests) still passes. Never reached a real
  audience — caught in the local review queue.
- **A first naive-baseline comparison, run for real** (`benchmark/
  run_naive_baseline.py`, `benchmark/naive_baseline_results.jsonl`): the
  same two claims sent directly to TruthLens's default LLM with no
  pipeline at all. Both came back `UNVERIFIABLE` (the model correctly
  recognized it can't know about mid-2026 events), where TruthLens's
  full pipeline reached the correct label on both. Written up in the
  paper (Section V-G) with the honest caveat that this specific
  comparison mostly demonstrates the value of having search access at
  all, not yet the value of TruthLens's specific multi-stage
  architecture over a simpler search-equipped competitor — the paper
  says this explicitly rather than overclaiming it.
- **Searched for more Tier-1 benchmark candidates and got a real,
  informative negative result.** Checked 22 more recent BOOM
  Live/Alt News articles beyond the original 2 finds — zero more had a
  usable live Instagram embed. Combined hit rate ≈2/26 (~8%), now
  documented in `PROTOCOL.md` as a real, load-bearing constraint on how
  fast this sourcing method can scale, not a one-off.

## What's explicitly NOT done, and why the paper says so

In descending order of how much they'd strengthen the paper:

1. **No held-out labeled benchmark at scale.** Still n=2. The proven
   sourcing method has a real ~8% hit rate against BOOM/Alt News alone
   (see above) — scaling past a handful of entries will need either more
   outlets (Factly 403s automated fetches; try Newschecker, India Today
   Fact Check, Vishvas News), a much larger number of articles checked,
   or loosening Tier 1 to accept a fact-checked claim paired with an
   independently-sourced still-live post making the same claim. Still
   the single highest-leverage next step.
2. **Baseline comparison exists but is too coarse.** We have a real
   result now (see above), but it isolates "has search" vs. "has no
   search," not TruthLens's specific architecture vs. a comparably
   -equipped competitor. The next version needs the baseline to also get
   one search query, so the comparison actually targets the paper's
   central claim.
3. **No bias audit.** The neutrality clause is a prompt-level mitigation,
   asserted but not measured.
4. **Author affiliation is a placeholder.** `main.tex` has a visible
   `[Affiliation placeholder -- TODO]` rather than a guessed institution.
5. **Video-provenance verification is entirely unbuilt.** The pilot's
   biggest finding: TruthLens likely can't catch the dominant real-world
   failure pattern in this domain (real footage, false caption about
   what it shows) at all, because it has no visual-provenance capability.
   Top item in Future Work. Not attempted yet — a real capability gap,
   not a polish item.

## Suggested next steps, in order

1. Decide affiliation / how you want to be listed as author.
2. Scale the benchmark past n=2 — needs either more outlets tried or a
   Tier-1 definition loosened per PROTOCOL.md, given the ~8% hit rate
   already found against the two easiest sources.
3. Build the search-equipped baseline (one query + one LLM call), the
   actual comparison the paper's central claim needs.
4. Decide whether video-provenance verification is worth prototyping
   (even a minimal version) before submission, given the pilot suggests
   it's the most consequential gap.
5. Target venue selection — current draft is a general IEEE conference
   paper; different venues want different framing/length.
6. One more full citation re-verification pass immediately before
   submission (arXiv preprints can be revised after being cited).

Mechanical cleanup (LaTeX compilation, all 14 citations verified, the
misattributed-statistic fix) is done — nothing in that category is
blocking. The validation-gap bug found via the pilot is fixed and
tested.
