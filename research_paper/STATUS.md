# Paper status

Last updated: 2026-08-18 (fifth update; foundation-phase program folded
in). See below for this pass's summary; prior updates preserved
unedited underneath.

## Latest update (this pass, 2026-08-18)

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
