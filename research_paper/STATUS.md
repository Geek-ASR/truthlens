# Paper status

Last updated: 2026-08-12 (session 1 of an expected multi-session effort —
this is genuinely not a one-sitting task if it's going to be honest).

## What's real and done

- `main.tex` — full draft, IEEEtran conference format, 9 sections
  (8 pages compiled), all with real content. Nothing in it is fabricated:
  every citation is in `references.bib` and traceable in `SOURCES.md`;
  every evaluation number is either a live query result against the
  actual TruthLens database or a real, live `POST /api/reels/quick` run
  against a genuinely new reel.
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

## What's explicitly NOT done, and why the paper says so

In descending order of how much they'd strengthen the paper:

1. **No held-out labeled benchmark at scale.** The pilot above is n=2 —
   real progress, explicitly not treated as sufficient. Scaling this to
   15-20 reels (Item 1 in Future Work) is still the single
   highest-leverage next step. The sourcing method (fetch a professional
   fact-checker's article, extract the embedded live post) is now proven
   to work — see `benchmark/PROTOCOL.md`'s "real constraint found"
   section for its limits (most fact-check articles don't preserve a
   live original-post URL; only ones that embed a source video as
   evidence reliably do).
2. **No baseline comparison.** Still not run — the second highest
   -leverage next step.
3. **No bias audit.** The neutrality clause is a prompt-level mitigation,
   asserted but not measured.
4. **Author affiliation is a placeholder.** `main.tex` has a visible
   `[Affiliation placeholder -- TODO]` rather than a guessed institution.
5. **Video-provenance verification is entirely unbuilt.** The pilot's
   biggest finding: TruthLens likely can't catch the dominant real-world
   failure pattern in this domain (real footage, false caption about
   what it shows) at all, because it has no visual-provenance capability.
   Now the top item in Future Work, arguably ahead of the primary-source
   -retrieval gap found earlier. Not attempted yet — a real capability
   gap, not a polish item.

## Suggested next steps, in order

1. Decide affiliation / how you want to be listed as author.
2. Scale the benchmark: more reels via the same sourcing method (BOOM
   Live / Alt News / Factly article → embedded live Instagram post), or
   decide the n=2 pilot is enough to motivate future work without fully
   building it out now.
3. Once the benchmark is large enough, add the naive-baseline comparison
   run.
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
