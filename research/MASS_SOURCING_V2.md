# MASS_SOURCING_V2.md — automated, high-throughput benchmark sourcing

Status: 2026-08-18, in progress. `research/DATASET_CARD.md`'s own
measured ~8% real-world sourcing hit rate made every prior sourcing
round (manual, one article at a time via `WebFetch`) too slow to reach
a several-hundred-item benchmark target in any reasonable time — this
document covers the automated pipeline built to replace that manual
process, why it needed three real fixes before it ran unattended, and
real results so far.

## Motivation

After reading the updated paper, the honest external assessment was
blunt: benchmark scale (n=15 at the time) is the binding bottleneck on
IEEE readiness, not further experiments or paper polish — see
`feedback_truthlens_benchmark_priority` (session memory). The
instruction that followed: build toward a genuinely large benchmark
(target: several hundred items), keep going for hours, don't stop.

Manual sourcing (`WebFetch` one article at a time, judge relevance by
reading) produced roughly 1 real item per 20–30 articles checked, even
after fixing a real tooling gap (see below). At that rate, reaching
hundreds of items would take dozens of hours of direct engagement —
not compatible with the ask. The fix was not "grind harder by hand,"
it was building a pipeline that removes the human/agent from every step
that doesn't require real judgment.

## Architecture

Four parallel, independent pipelines, one per fact-checker archive,
sharing a common judge/extraction core:

1. **`backend/research/benchmark_v2/mass_source_candidates.py`**
   (altnews.in): paginates `altnews.in/type/fact-check/` (confirmed
   live: 498 pages, ~6,900 articles — the broad category, not the
   narrower `viral-videos` claim-type subcategory used in earlier
   manual rounds).
2. **`backend/research/benchmark_v2/mass_source_vishvasnews.py`**
   (vishvasnews.com): sitemap-indexed (34 WordPress sitemap files,
   ~1,000 URLs each, spanning 2020–2026), filtered to the `/viral/`
   URL path.
3. **`backend/research/benchmark_v2/mass_source_factly.py`**
   (factly.in): sitemap-indexed (21 files, ~21,000 URLs total),
   filtered to the `fact-check` URL substring. **Deprioritized after
   testing**: 0 Instagram references found across its first 1,000
   fact-check articles — a real, disclosed negative result, not
   pursued further at full scale.

4. **`backend/research/benchmark_v2/mass_source_thequint.py`**
   (thequint.com's WebQoof vertical): added after the honest yield
   finding below (Alt News's entire archive → only 2 promotable items)
   made clear reaching anywhere near a several-hundred-item target
   needs independent sources, not just deeper crawling of the same
   two or three. WebQoof's listing page is JS-hydrated (confirmed
   live: `/news/webqoof?page=2` returns byte-identical links to page
   1 — pagination happens client-side, not something this pipeline
   can reach), so this crawls thequint.com's daily sitemap files
   (`sitemap-daily-YYYY-MM-DD.xml`, one HTTP request per calendar day)
   instead, filtered to the `/news/webqoof/` URL substring. Confirmed
   live via spot sampling that WebQoof content averages ~2.6
   articles/day and is present consistently back to at least 2020.
   First pass capped at the most recent 1,095 days (~3 years) —
   already a substantial crawl (1,095 sitemap-index requests before a
   single article is fetched) — extendable further given the archive
   goes back at least 5 years.

**Explicitly not built**: `newschecker.in`. Its `robots.txt` names
`ClaudeBot`/`Claude-Web`/`anthropic-ai` in an explicit `Disallow`. That
is a clear publisher directive; using a generic browser User-Agent to
route around it would be circumventing it, not a gray area. Dropped
entirely, not worked around.

### Pipeline stages

1. **CRAWL**: raw HTML page/sitemap fetch (`httpx`, not `WebFetch` —
   link/title extraction is a parsing task, not one that benefits from
   AI summarization), paginated or sitemap-walked per archive.
2. **EXTRACT**: `backend/research/benchmark_v2/extract_instagram_embed.py`
   (built in an earlier manual round) finds Instagram URLs in an
   article's raw HTML — both `data-instgrm-permalink` widget embeds
   (which `WebFetch`'s AI-summarized fetch was silently dropping) and
   plain links, so it's a strict superset of what manual sourcing could
   find.
3. **DEDUP**: skip URLs already in `items.jsonl`/`items_v2.jsonl`/any
   candidates file.
4. **VERIFY**: `yt-dlp --simulate` for retrievability; the post's own
   caption/uploader pulled directly from `yt-dlp` metadata, never
   inferred from the article.
5. **JUDGE**: a local `llama3.2` structured call (never Gemini, per
   direct instruction) decides whether the cited Instagram post's own
   caption is itself the misinformation being fact-checked — not
   merely evidence of the true original. This is the single hardest
   -won lesson from manual sourcing this session: the large majority of
   articles that DO reference Instagram cite it as the accurate
   original, with the actual false claim posted separately (often on
   X/Twitter, sometimes deleted). Getting this distinction right
   mechanically, at scale, is most of what makes automation viable here
   at all.
6. **LOG**: every candidate — accepted or rejected — is written with
   full reasoning via `candidate_tracker.py`. Nothing is silently
   dropped. Accepted candidates are marked `ELIGIBLE`, explicitly
   flagged `NOT yet human/manual-reviewed`, pending a spot-check pass
   before `promote_eligible_candidates.py` ever touches them.

### Quality control: `spot_check_eligible_candidates.py`

Auto-accepted candidates are not trusted on the judge's word alone.
Two real failure classes found live, both now checked deterministically
before promotion:

- **Self-contradicting reasoning**: one candidate's own judge reasoning
  said the caption "seems unrelated" and "does not directly address"
  the claim — while `is_own_post_the_misinformation=True`. Same class
  of failure this whole session has repeatedly found in local-model
  output (`research/FAILURE_TAXONOMY.md` #19's pattern), now caught in
  this pipeline's own judge step.
- **Hallucination / malformed output**: one candidate had
  `confidence=1.00`, empty reasoning (the substantiveness retry fired
  but still returned empty), and an extracted claim about a woman being
  raped and killed in Jharkhand. Verified directly against the real
  post caption via `yt-dlp`: *"Upcoming mising full movie - Lujeg
  BTS.."* — a movie promotional post, with nothing to do with the
  claim. A real hallucination, not a borderline call, and undetectable
  by the self-contradiction check alone since the reasoning was empty,
  not contradictory. A second candidate (from the Vishvas pipeline) had
  a `ground_truth_claim` field containing a raw markdown link instead
  of a sentence, and an empty `ground_truth_label` — also now checked
  for.

The filter runs against all three pipelines' output files (the shared
`candidates_v2.jsonl`, under the same cross-process lock described
below, plus each separate-file pipeline's own output) and downgrades
flagged candidates to `UNRESOLVED`, not silently promoting or dropping
them.

## Three real crashes, three real fixes

Built and launched fast, under real time pressure — and it showed:
three genuine bugs surfaced within the first few hours of real
unattended operation, each found via an actual crash, not anticipated
in advance. Each is disclosed here in full rather than summarized away,
matching this project's standing self-audit discipline.

### 1. Concurrent-write data loss (crashed the pipeline outright)

Running `spot_check_eligible_candidates.py` and
`promote_eligible_candidates.py` directly against the shared
`candidates_v2.jsonl` *while* the Alt News pipeline was still
concurrently writing to it lost a write outright.
`candidate_tracker.py`'s `_save_all()` does a full read-modify-write of
the whole file with no locking; `promote_eligible_candidates.py` held
its in-memory snapshot across several minutes of real ingestion work
(download, transcription, vision) and saved it at the end, silently
wiping out every candidate the sourcing pipeline had added in the
meantime. The pipeline crashed on its very next `update_status()` call
with `candidate_id not found`.

**Fixed** with real cross-process locking (`fcntl.flock`, blocking,
held across the *entire* load-modify-save cycle in
`add_candidate()`/`update_status()`, not just around the individual
read or write — locking only one half would not have prevented this
exact lost-update pattern). Added `set_promoted_item_id()` so
`promote_eligible_candidates.py` no longer holds a long-lived stale
snapshot; each candidate's promotion is now its own short, locked,
freshly-reloaded update.

**Verified both directions**, not just written and assumed: a new
regression test (`tests/test_benchmark_candidate_tracker.py::test_concurrent_writes_from_separate_processes_lose_nothing`)
uses genuinely separate OS processes (`multiprocessing`, not threads —
the real shape of the bug) and confirms 0 lost writes with the fix,
30 of 30 lost the same way (15 of 30 survive) with the fix reverted —
the exact live failure mode.

### 2. Hardcoded candidate-ID counter (crashed on restart)

`next_candidate_n` was hardcoded to `1` on every startup. Restarting
after crash #1 (with `cand-mass-0001`..`0055` already in the file from
before the crash) immediately collided: `candidate_id 'cand-mass-0001'
already exists`.

**Fixed** by deriving the starting number from the highest existing
`cand-mass-NNNN` ID already in the file, mirroring
`promote_eligible_candidates.py`'s own `_next_item_ids()` pattern.
Proactively applied the same fix to the sibling Vishvas/Factly scripts
(which had a related but distinct bug — `len(existing) + 1` instead of
`max(existing) + 1` — not yet triggered since neither had restarted,
but the same latent failure mode).

### 3. No retry/error handling around the archive page fetch (crashed on an ordinary network blip)

A genuine `httpx.ConnectTimeout` (SSL handshake timeout) — expected,
ordinary behavior over a multi-hour crawl, not a bug in itself —
crashed the entire run. `_crawl_archive_page()`'s own fetch had no
error handling at all, unlike the per-article fetch a few lines away,
which already did.

**Fixed** with a 3-attempt exponential-backoff retry (`tenacity`,
matching the pattern already used elsewhere in this codebase, e.g.
`duckduckgo.py`), and a new `_PageFetchFailed` exception distinguishing
"fetch failed after retries, skip this one page" from "got a real 200
response with zero matches, this archive is genuinely exhausted" —
conflating the two would have been a fourth, subtler bug: silently
truncating the crawl at whatever page a transient failure happened to
land on. Proactively applied the same retry treatment to the sibling
scripts' sitemap-index and sitemap-file fetches before they hit the
same wall.

## Two more real bugs — not crashes, but real quality issues

### 4. Fact-checker's-own-account reposts wasting judge calls

Spot-checking a rejected Vishvas candidate whose reasoning said the
caption was "identical to the false assertion" — yet got rejected
anyway — traced to the post's `uploader` field being `Vishvas News`
itself: the fact-checker's own repost/documentation of the claim, not
the real misinformation spreader. Checking how common this is: **30 of
~97 candidates checked by the Vishvas pipeline (31%) were the
fact-checker's own account.** Close to a third of all real `yt-dlp` +
LLM judge calls were being spent on structurally-disqualified
candidates before even reaching the judge. Fixed with a deterministic,
case-insensitive uploader check
(`_is_known_factchecker_account()`) that skips straight to `REJECTED`
before the judge call, wired into all three pipelines.

### 5. The spot-check filter's own reasoning lookup was silently broken

The most serious of the non-crash bugs. `spot_check_eligible_candidates.py`
looked for the judge's reasoning in either a `GROUND_TRUTH_VERIFIED` or
an `ELIGIBLE` status-history note, taking whichever appeared **last**.
The Alt News pipeline writes the real reasoning to `GROUND_TRUTH_VERIFIED`,
then a *separate*, later `ELIGIBLE` note with a generic
"auto-accepted, not yet reviewed" filler message — so for every single
Alt News candidate, the filter was checking the generic filler text,
which can never contain a self-contradiction phrase, instead of the
real reasoning. The filter had been silently non-functional for the
one pipeline (Alt News) producing the most candidates.

Found by manually reading candidates the filter had let through after
the Alt News archive finished: `cand-mass-0319`/`0320` (both genuinely
sweet, unrelated father-daughter posts — a First Communion celebration,
an affectionate note to a father — that the judge matched to an
"underage marriage" claim with no textual basis at all), and
`cand-mass-0321`/`0344`, whose own reasoning *explicitly* stated things
like *"does not contain the false claim being debunked; it merely
shows related real footage and is tagged/mentioned"* — literally the
judge prompt's own stated exclusion criterion — while still being
marked `is_own_post_the_misinformation=True`.

**Fixed** two ways: (1) the lookup now prefers `GROUND_TRUTH_VERIFIED`
outright when present, falling back to `ELIGIBLE` only for pipelines
that never write a separate verified-note (Vishvas/Factly's shape); (2)
the keyword list was replaced with a mix of literal phrases plus a
regex (`(does not|doesn't|did not|didn't)\s+\w+(\s+\w+){0,4}\s+(claim|
assertion|misinformation|false)`) that generalizes the whole family of
"does not [verb] the [claim/assertion]" phrasings the fixed keyword
list kept missing one variant at a time. All 4 real cases found this
way, plus 3 further Vishvas candidates with malformed
`ground_truth_label` fields (literally the string `"Fact Check"` —
leaked article-title text, not a real verdict) or an unverifiable claim
-to-content link, manually downgraded to `UNRESOLVED` rather than
promoted.

**Net effect on this batch**: of 8 candidates that reached `ELIGIBLE`
after the Alt News archive fully completed and Vishvas made further
progress, 7 were real judge errors or malformed output caught by
manual review plus the fixed filter, and 0 were promoted this round.
Sobering, and reported honestly rather than smoothed over — this is
exactly why the pipeline's own design never auto-promotes on the
judge's word alone.

## A separate, non-crash mistake: disclosed in full

While diagnosing crash #1, an unnecessary `git checkout --
research/dataset/candidates_v2.jsonl` was run to reset test data
*without checking git status first* — a real, avoidable violation of
this project's own stated safety discipline. It discarded ~50 real,
uncommitted candidate tracking records (`cand-mass-0056` through
`~0107`, mostly `REJECTED` judgments) accumulated since the last
commit. **The actual benchmark data was not affected**: items already
promoted from that batch (item-0019, item-0020) are fully intact in
`items_v2.jsonl`, since promotion copies all needed fields into that
file at the time it happens. The mistake also silently reverted
`cand-mass-0027`'s `promoted_item_id` marker (even though item-0019
was already promoted from it before the checkout) — left unfixed, the
next promotion run would have created a duplicate item. Caught via a
full consistency check across every promoted item's candidate
back-reference and fixed. item-0020's own back-reference
(`cand-mass-0088`) remains a genuine, harmless gap — that candidate
record itself was lost, not just its marker, but item-0020's real data
was already safely copied into `items_v2.jsonl`.

### 6. `confidence=-1` from llama3.2 burning retries for no benefit

Live in the Vishvas run: `judge call failed: ... confidence Input
should be greater than or equal to 0 [input_value=-1.0]` — llama3.2
occasionally emits `-1` or `-1.0` for `confidence`, seemingly its own
out-of-band "not applicable" sentinel. Checked: in every occurrence
found, it was paired with `is_own_post_the_misinformation=False`
elsewhere in the same response shape, i.e. a case that was always
going to end up `REJECTED` regardless. The strict `ge=0.0` field bound
meant Pydantic raised, tenacity burned 3 retries, and the whole judge
call still ended in the same `REJECTED` outcome, just slower — 7 of
~256 candidates checked in the Vishvas run so far (2.7%) hit this.
Fixed with a `field_validator("confidence", mode="before")` that
clamps to `[0.0, 1.0]` instead of raising — a clamped `0.0` still fails
the `>=0.7` `ELIGIBLE` bar the same way the exception would have, so
this is a pure efficiency fix, not a behavior change. Applied in
`mass_source_candidates.py`, inherited automatically by the Vishvas/
Factly pipelines since they import `SourceJudgment` via `_judge()`
rather than redefining it. The already-running Vishvas process (started
before this fix) won't pick it up until its next restart — Python
doesn't hot-reload — left running rather than interrupted, since the
efficiency loss is small and restarting would cost more time
re-walking already-checked sitemaps than it would save.

## Results so far (running total, updated as the pipelines progress)

**Alt News (altnews.in/type/fact-check/): archive fully exhausted.**
498 pages, 4,967 articles crawled, 225 with an Instagram reference, 515
candidates checked across all runs combined. After rigorous manual
review (catching the spot-check bug above), only **2 candidates from
this entire archive** were ever promoted to real benchmark items
(item-0019, item-0020) — everything else was correctly rejected as
"cited as evidence, not the misinformation source," a known-factchecker
repost, not retrievable, or (this session's final batch) a judge error
caught by manual review. This is the single most important honest
result of this effort: even a fully-automated crawl of a major fact
-checker's **entire** historical archive, applied with real rigor,
yields on the order of 1 promotable item per ~250 candidates checked —
confirming in hard numbers what the earlier 8/8 qualitative evidence
already suggested (Instagram is a comparatively small slice of where
this specific misinformation pattern gets posted, next to X/Twitter).

**Vishvas News (vishvasnews.com, `/viral/` category): still running.**
34 sitemap files, ~256 candidates checked so far (partial, mid-archive
at sitemap file 15/34 as of this writing), 3 reached `ELIGIBLE` and all
3 were rejected on manual review post-spot-check-fix (malformed
`ground_truth_label` leaking article-title text, or an unverifiable
specific-event connection) — 0 net new promotions from this source so
far.

**Factly (factly.in): deprioritized**, not run at scale, after a real
negative test result (0 Instagram references in the first 1,000
articles checked).

**Benchmark total: 20 items (9 v1 + 11 v2)**, unchanged since item-0020
— this entire batch of further automated sourcing, run in direct
response to the explicit 500-item target, has not yet produced a single
additional promotable item once real rigor is applied. This is reported
plainly rather than smoothed over: the honest conclusion is that
Instagram-only sourcing, even fully automated against complete
archives, is very unlikely to reach 500 items in any reasonable
timeframe at the yield rate actually observed (~1 per 250 candidates
from the highest-yield source found so far). See
`research/RESEARCH_ROADMAP_V2.md` (or the next commit's update to it)
for the resulting recommendation.

## Raw data / generators

`backend/research/benchmark_v2/mass_source_candidates.py`,
`mass_source_vishvasnews.py`, `mass_source_factly.py`,
`mass_source_thequint.py`, `spot_check_eligible_candidates.py`,
`merge_mass_candidates.py`. Live logs:
`research/results/mass_sourcing_live.log`,
`mass_sourcing_vishvas_live.log`, `mass_sourcing_thequint_live.log`.
Candidate records: `research/dataset/candidates_v2.jsonl` (Alt News,
shared/locked file), `candidates_v2_mass_vishvas.jsonl`,
`candidates_v2_mass_factly.jsonl`, `candidates_v2_mass_thequint.jsonl`
(separate files, avoiding the cross-process race crash #1 found).
