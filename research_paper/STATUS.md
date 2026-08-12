# Paper status

Last updated: 2026-08-12 (session 1 of an expected multi-session effort —
this is genuinely not a one-sitting task if it's going to be honest).

## What's real and done

- `main.tex` — full draft, IEEEtran conference format, 9 sections
  (9 pages compiled), all with real content. Nothing in it is fabricated:
  every citation is in `references.bib` and traceable in `SOURCES.md`;
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
