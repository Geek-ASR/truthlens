# TruthLens held-out benchmark: labeling protocol

Goal: a small but methodologically sound labeled set of short-form
political video claims, disjoint from anything used during TruthLens
development, that lets Section VI of the paper report real
precision/recall instead of development-time telemetry, and lets us run
a naive-baseline comparison (Section VIII, item 2).

## Why this design, not just "label some reels yourself"

Simply asking one person (me building the system, or you funding it) to
personally judge true/false is a real weakness reviewers will flag —
it's the system's author grading the system's own homework. The design
below fixes that in two ways:

1. **Prefer claims an independent professional fact-checking
   organization has already verdicted**, and use their published verdict
   as ground truth rather than our own judgment. This is the gold-standard
   tier below.
2. **Where no professional fact-check exists**, fall back to independent
   human labeling with a second labeler and reported inter-annotator
   agreement, not a single person's judgment presented as ground truth.

## Corpus construction

- **Target size:** 15-20 reels, expected to yield ~45-70 extracted claims
  (based on the one data point we have: ~3-4 claims/reel), of which
  perhaps 25-40 will be `verifiable` factual claims — the population
  TruthLens's verdict stage actually scores.
- **Disjointness:** none of these reels may be the mandatory test reel
  (`instagram.com/p/DbuqfKHN1zI/`) or any repost/duplicate of it (checked
  by content hash, same mechanism TruthLens already uses for duplicate
  detection).
- **Diversity, to avoid a skewed sample:**
  - Multiple creators/publishers, not concentrated in one channel.
  - A mix of topics within Indian political short-form video, not all
    the same news cycle.
  - Deliberately include some reels expected to be accurate and some
    expected to be false/misleading, not just "whatever comes up
    first" — an all-`UNVERIFIED` or all-`TRUE` benchmark can't
    measure discrimination.
  - A mix of English-only and English/Hindi/Urdu-mixed transcripts, since
    that mix is a stated part of TruthLens's target domain.

## Ground-truth tiers

**Tier 1 (preferred): claims independently pre-verdicted.**
Source candidate claims by searching established fact-checkers (BOOM
Live, Alt News, Factly, PolitiFact, Reuters Fact Check, AFP Fact Check,
PIB Fact Check for government-scheme claims) for articles that reference
or embed a specific Instagram Reel, or that verdict a claim closely
matching one made in a Reel we can independently locate. Ground truth =
that organization's own published verdict, with the article URL stored
alongside the label for auditability. This is the only tier that lets
the paper claim genuinely independent ground truth.

**Tier 2 (fallback): no existing professional fact-check found.**
Two independent labelers (ideally not just the system's author) each
assign a verdict from the simplified schema below without seeing the
other's label or TruthLens's output, working only from primary sources
(the same kind of official records/wire-service reporting the pipeline
itself is supposed to find). Report Cohen's kappa across the label set.
Disagreements go to a documented adjudication discussion, not a
majority-of-one override.

Every claim in the final benchmark file must record which tier it came
from — Tier 1 and Tier 2 claims should also be reported separately in
Section VI, not silently pooled, since they carry different evidentiary
weight.

## Label schema

TruthLens's own 8-way `VerdictLabel` (`TRUE`, `MOSTLY_TRUE`,
`MISLEADING`, `MOSTLY_FALSE`, `FALSE`, `UNVERIFIED`, `OUTDATED`,
`MISSING_CONTEXT`) is too fine-grained for reliable human agreement at
this sample size — even LIAR's 6-way scheme is a known source of
inter-annotator disagreement in the literature. Ground-truth labels use
a collapsed 4-way scheme instead:

| Ground-truth label | Maps from TruthLens labels |
|---|---|
| `TRUE` | `TRUE`, `MOSTLY_TRUE` |
| `FALSE` | `FALSE`, `MOSTLY_FALSE` |
| `MIXED` | `MISLEADING`, `OUTDATED`, `MISSING_CONTEXT` |
| `UNVERIFIABLE` | `UNVERIFIED` (both as ground truth *and* as a valid, correct TruthLens output when the claim genuinely lacks enough public evidence) |

Note `UNVERIFIABLE` is a legitimate ground-truth label, not just a
TruthLens output — some claims genuinely can't be resolved from public
sources, and a system that correctly says so should score as correct,
not be penalized for not inventing a verdict.

## File format

`research_paper/benchmark/claims.jsonl` — one JSON object per line:

```json
{
  "claim_id": "bm-0001",
  "reel_url": "https://www.instagram.com/p/.../",
  "claim_text": "...",
  "ground_truth_label": "TRUE|FALSE|MIXED|UNVERIFIABLE",
  "ground_truth_tier": 1,
  "ground_truth_source_url": "https://www.boomlive.in/...",
  "ground_truth_notes": "short justification, or labeler notes for Tier 2",
  "labeler": "tier-1-source | initials for Tier 2",
  "added_date": "2026-08-12"
}
```

## Scoring procedure (once the file has enough entries)

1. Run each `reel_url` through `POST /api/reels/quick` (already built and
   working) to get TruthLens's real, current output — not a re-run of
   old cached results.
2. Map each TruthLens claim's `VerdictLabel` onto the same 4-way scheme.
3. Match TruthLens claims to benchmark claims by semantic similarity
   (TruthLens's own claim wording won't exactly match the benchmark
   claim text) — this matching step needs its own manual spot-check,
   since it's a place a systematic error could sneak in.
4. Report accuracy, and precision/recall per class, not just overall
   accuracy — an "always predict UNVERIFIABLE" baseline could otherwise
   look deceptively good given how UNVERIFIED-heavy the dev telemetry
   already was.
5. Report the same metrics for the naive single-shot baseline (Section
   VIII item 2) run over the same claim texts, for the direct comparison
   the paper is currently missing.

## Status

Schema and process defined. `claims.jsonl` has 2 real, individually
-verified Tier 1 entries as of 2026-08-12, proving the sourcing method
works:

- **bm-0001**: sourced from a BOOM Live fact-check (NEET 2026 result-day
  videos, verdicted False). Found by fetching the raw HTML of a BOOM
  article and extracting its embedded `instagram.com/reel/...`
  permalinks — professional fact-check *summaries* often don't surface
  the original post URL in visible text, but the underlying page HTML,
  fetched directly (not via a summarizing tool), usually does when the
  outlet embedded the original post as evidence.
- **bm-0002**: sourced the same way from an Alt News fact-check (a video
  falsely claimed to show misconduct at a Delhi protest, actually Mexico
  World Cup celebration footage). This one is cleaner than bm-0001: the
  live reel IS the exact post making the false claim (not just a source
  video referenced within a claim about a different, now-dead post).

Both are being run through `POST /api/reels/quick` to check TruthLens's
own output against these independent verdicts — see
`../STATUS.md` for the result once available.

**Real constraint found while doing this:** most fact-check articles
describe or screenshot the misleading post rather than linking a
persistently live URL — the actual originating post is often already
taken down or only in an archive.is snapshot by the time the fact-check
is published, which yt-dlp/auto_fetch cannot retrieve. Only articles
where the outlet *embedded* the original (or a directly relevant source)
video as evidence reliably yield a fetchable URL. This will bottleneck
how fast the corpus can grow — worth factoring into the "how many reels
are feasible" scoping conversation.
