# Held-Out Evaluation Dataset Specification

This formalizes and extends `research_paper/benchmark/PROTOCOL.md`
(already written, already vetted, already produced 2 real Tier-1 items)
into the `items.jsonl` schema this program's tooling expects. It does
not replace that protocol's methodology — the two-tier ground-truth
design (§"Ground-truth tiers" below) is taken directly from it, because
it already correctly anticipated this program's central integrity
concern: a system's own author cannot be its evaluation's sole judge.

## Target size, stated honestly

**20-30 items**, not the brief's ideal of 100 (minimum acceptable 50).
Justification, not excuse: `PROTOCOL.md` already ran the relevant pilot
— checking 22 additional BOOM Live/Alt News articles beyond the original
2 finds yielded **zero** more usable Tier-1 items (a live-Instagram-embed
still up, traceable, disjoint from development data). Combined hit rate
≈2/26 (~8%), documented as "a real, load-bearing constraint on how fast
this sourcing method can scale, not a one-off." Reaching 20-30 items
total therefore requires either (a) checking on the order of 250-375
more professional fact-check articles for Tier-1 candidates in the time
available — not impossible, but a large, literal manual-search task —
or (b) accepting more Tier-2 (single-annotator) items. This plan uses
both, and reports the resulting tier split explicitly in every results
table, never blending them into one undifferentiated "ground truth"
column.

**If 20 is not reached**, the actual number reached is reported, with
exact counts and confidence intervals, not disguised as 20. See Rule 1.

## Ground-truth tiers (from `PROTOCOL.md`, restated for this schema)

- **Tier 1 (preferred)**: the claim in this Instagram post has already
  been verdicted by an independent professional fact-checking
  organization (BOOM Live, Alt News, Factly, PolitiFact, Reuters Fact
  Check, AFP Fact Check, PIB Fact Check), and that organization's
  article demonstrably references or embeds *this specific* post (not
  just a similar claim elsewhere). Ground truth = their published
  verdict, with the article URL stored for auditability.
  `annotation_status = "tier1_professional"`.
- **Tier 2 (fallback)**: no existing professional fact-check found.
  Labeled by the available human annotator(s) — see
  `ANNOTATION_GUIDELINES.md` for the exact procedure and
  `GROUND_TRUTH.md` for the disclosed limitation this implies (§ below).
  `annotation_status = "tier2_human_labeled"`.

No item is ever labeled by TruthLens itself, or by any LLM, and then
used as ground truth. Confirmed as a hard rule, not a preference — see
Rule 2/Rule 3 of the governing instructions.

## `dataset/items.jsonl` schema

One JSON object per line, matching the brief's requested shape plus the
fields `PROTOCOL.md`'s existing tier-1 items already carry (kept, not
dropped, for continuity with the 2 items already collected):

```json
{
  "id": "item-0001",
  "source_url": "https://www.instagram.com/reel/...",
  "date": "2026-08-13",
  "language": "hi-en-mixed",
  "modality": "video",
  "political_actor": "BJP",
  "claim_type": "statistic",
  "claim_text": "...",
  "annotation_status": "tier1_professional",
  "ground_truth_label": "FALSE",
  "ground_truth_tier": 1,
  "ground_truth_source_url": "https://www.boomlive.in/...",
  "ground_truth_notes": "...",
  "is_visual_claim": false,
  "is_provenance_claim": false,
  "content_hash": "...",
  "added_date": "2026-08-13"
}
```

`modality` ∈ {video, photo}. `claim_type` ∈ {statistic, quote, law_policy,
historical, event, visual, provenance, misleading_context, true_claim}
— a superset of `ClaimType` in `db/models.py` because the dataset needs
to describe the *item's* checkworthy content before TruthLens ever
extracts anything, whereas `ClaimType` describes what TruthLens's own
extractor output looks like; these are deliberately not the same
vocabulary, and conflating them would make claim-coverage measurement
circular.

## Diversity targets (not hard quotas, given the size constraint above)

- At least 1 item where the primary checkworthy content is **visual/
  provenance** (real footage, false caption) — already have 1 (bm-0002).
  A second is the single highest-priority acquisition target for Day 2,
  since RQ3 has no statistical meaning at n=1.
- A mix of claims naming the current government and claims naming
  opposition/other political actors — tracked via `political_actor`,
  reported as a distribution in the paper, not balanced by
  construction (balancing by construction would itself bias the sample
  toward "easy to match" cases).
- At least one item expected to resolve `TRUE` or `MOSTLY_TRUE` — the
  existing 2 items are both `FALSE`; an all-false benchmark cannot
  measure whether the system correctly clears an accurate claim, which
  matters as much as catching a false one.
- English-only and English/Hindi/Urdu-mixed transcripts both
  represented, matching the system's actual deployment domain.

## Held-out discipline (Rule 3, operationalized)

1. Every item's `source_url` is checked against `media_content_hash` in
   the existing `reels` table before being added — an item already
   ingested during development is excluded, full stop, regardless of
   how useful its claim looks.
2. No prompt, threshold, or model choice may be changed based on this
   dataset's contents or TruthLens's performance on it, from the moment
   an item is added to `items.jsonl` onward. Any code change made after
   Day 2's freeze must go through the "stop changing the system after
   the evaluation set is frozen" procedure in `EXPERIMENT_PLAN.md`/Day 8
   (record → fix → version → rerun the *affected* experiment only, never
   silently).
3. `items.jsonl` is committed to git the moment it's frozen, so any
   later edit is visible in `git log`, not just in the file's current
   contents.

## Sourcing method (Day 2 execution plan)

1. Continue `PROTOCOL.md`'s method: search BOOM Live, Alt News, Factly,
   PIB Fact Check, Reuters Fact Check, AFP Fact Check for articles
   embedding a still-live Instagram post, prioritizing outlets/topics not
   already covered by the existing 2 items, and prioritizing visual/
   provenance cases specifically (the current n=1 gap).
2. For items where no Tier-1 source is found after a bounded search
   effort (documented per-item: how many outlets/articles were checked),
   fall back to Tier-2: Aditya labels directly from primary sources,
   following `ANNOTATION_GUIDELINES.md`.
3. Every accepted item gets a `content_hash` computed the same way
   `duplicate_detection.py` computes `media_content_hash`, checked
   against the existing `reels` table (item 1 above).

## What this program will NOT do

- Will not scrape Instagram at volume via automation beyond the existing,
  already-documented, opt-in, ToS-flagged `yt-dlp` auto-fetch path used
  one item at a time, the same way a human researcher would use it.
- Will not lower the Tier-1 bar to "a similar claim was fact-checked
  somewhere" — the source article must demonstrably reference *this*
  post, per `PROTOCOL.md`'s original, stricter standard.
- Will not backfill Tier-2 items' labels after seeing TruthLens's output
  on them — labeling happens first, sealed, per §"Held-out discipline."
