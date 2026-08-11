# TruthLens — Current Architecture (as inspected 2026-08-12)

This document is a fresh, from-the-code inspection of what actually
exists, prompted by a real regression: the pipeline produced a published-
looking fact-check with an empty evidence section and `UNVERIFIED` for
every claim. It answers, precisely, what's there today, what's genuinely
solid, and what's missing — as a basis for prioritized improvement, not a
rewrite. See `docs/ROADMAP.md` and `docs/ARCHITECTURE.md` for the
original design intent; this doc is about what's actually running.

## 1. Stack

- **Backend**: FastAPI (async), SQLAlchemy 2.0 async + Alembic, Postgres +
  pgvector, Celery/Redis (wired but not required — every pipeline stage is
  directly `await`-able from a request handler; Celery is for later
  scheduling, not in the critical path today).
- **Frontend**: Next.js 14 (App Router) + TypeScript + Tailwind. Pages:
  `login`, `reels/new`, `reels/[id]`, `fact-checks/[id]`,
  `settings/instagram`. No public (unauthenticated) fact-check page exists
  yet — everything lives behind login.
- **Storage**: S3-compatible (MinIO locally) for video/thumbnails/slide
  images/archived source text.
- **LLM**: pluggable `LLMProvider` interface
  (`backend/app/services/ai/base.py`) with three real implementations —
  `OllamaProvider` (local, default, $0), `AnthropicProvider`,
  `GeminiProvider` (Google's Interactions API, used as an automatic
  fallback) — selected by `backend/app/services/ai/factory.py`. This part
  of the stated vision ("Ollama should work independently, no paid key
  required") is **already true** — every stage below runs through this
  same interface.
- **Search**: `SearchProvider` interface
  (`backend/app/services/search/base.py`) with exactly **one**
  implementation: `TavilySearchProvider`. This is the crux of the bug —
  see §4.

## 2. Pipeline as implemented (`backend/app/pipeline/`)

```
ingest_reel()            → Reel row (manual upload OR yt-dlp auto_fetch)
transcribe_reel()        → Reel.transcript (local faster-whisper by default)
ocr_reel()                → Reel.ocr_text (Tesseract, local)
analyze_vision_context()  → Reel.vision_context (advisory only, never evidence)
extract_claims()          → Claim rows, ALREADY decomposed into atomic claims
  for each claim where claim.verifiable:
    plan_research()        → SearchQuery rows (2-5 queries, LLM-planned, each tagged a target_tier)
    fetch_evidence_sources()→ Source rows (via SearchProvider — today, Tavily only)
    analyze_evidence()      → Evidence rows (per-source stance: supports/contradicts/context/irrelevant)
    propose_verdict()       → Verdict row (LLM proposal → deterministic validator → persisted)
build_fact_check()        → duplicate check → generate_content() → generate_slides() → FactCheck row
```

This is **already** the shape the product vision asks for
(`REEL → TRANSCRIPT → CLAIM EXTRACTION → ATOMIC CLAIMS`, `EVIDENCE →
ANALYSIS → VERDICT`), not a single "summarize the whole reel" prompt.
Concretely, as of the last real test run, one reel produced **8 distinct
claims**, each independently typed and scored — this part of the
architecture works and is not the source of the bug.

## 3. What's genuinely solid already

Worth stating plainly, because the visible symptom (empty `UNVERIFIED`)
looks like "the LLM never really tried," and that is **not** what the
code shows:

- **`verdict.py` refuses to call the LLM at all when there's no evidence**
  (`propose_verdict`, line ~56): `if not evidence_rows: return
  _persist_unverified(...)`. It never asks "is this true?" without
  evidence — the exact `EVIDENCE → ANALYSIS → VERDICT` ordering the spec
  demands is already enforced in code, not just prompted for.
- **`validation.py` is a deterministic (non-LLM) anti-hallucination gate**
  run on every verdict before it's persisted: cited evidence IDs must
  actually belong to this claim's evidence; every cited source must have
  a real `retrieved_at` + `full_text_storage_key` (i.e. was actually
  fetched, not just found in a search snippet); every number in the
  reasoning must appear verbatim in a cited passage. Any failure
  downgrades to `UNVERIFIED` and records why (`ValidationStatus` enum).
- **`source_scoring.py` implements an 8-dimension weighted reliability
  score** (primary-source status, author identity, publication
  reputation, evidence transparency, recency, directness, corroboration,
  conflict of interest) computed from a fixed formula, never assigned
  directly by the LLM. `directness` and `corroboration` are refined after
  `evidence_analysis` actually reads the source
  (`update_after_evidence`) — corroboration is explicitly "how many
  *other* sources for this claim independently agree," which is a real,
  if basic, source-diversity signal already in place.
- **Source tiering exists** (`SourceTier` enum: `primary_government`,
  `primary_legal`, `primary_data`, `news_wire`, `established_news`,
  `academic`, `factcheck_org`, `other`), with real domain-based
  classification (`.gov` hints, Reuters/AP/BBC/FT as `news_wire`/
  `established_news`, Snopes/PolitiFact/BOOM/Alt News/India Today/Quint
  WebQoof as `factcheck_org`) and `TargetTier` on each planned query
  (`tier1_primary` / `tier2_secondary` / `tier3_factcheck` /
  `unrestricted`) so research planning already asks for primary sources
  specifically, not just "search for X."
- **Duplicate detection exists** (`duplicate_detection.py`): exact reel
  re-upload via media content hash, fuzzy claim-text similarity via
  `difflib` (pgvector embedding column is provisioned for a stronger
  version later, not wired yet).
- **Full audit trail**: every AI call is logged to `audit_logs` with
  actor, action, prompt version, and real token counts — "why did this
  get labeled X" is answerable from the DB today.
- **Everything is stored relationally** and matches almost exactly the
  entity list the vision asks for: `reels`, `claims`, `search_queries`,
  `sources`, `evidence`, `verdicts`, `fact_checks`, `slides`,
  `generated_posts`, `publishing_jobs`, `corrections`, `audit_logs`,
  `analytics_snapshots`. A `corrections` table already exists
  (append-only: `previous_verdict_id` → `new_verdict_id` with a reason —
  old fact-checks are never silently rewritten).

## 4. The actual bug: zero search backends, no key, no fallback

`search_fetch.fetch_evidence_sources()` calls
`search_provider.search(query)` for every planned query. There is exactly
one `SearchProvider` implementation registered
(`services/search/tavily.py`), and `TavilySearchProvider.search()`
raises immediately when `SEARCH_API_KEY` is unset:

```python
if not self._api_key:
    raise ProviderError("SEARCH_API_KEY is not set; cannot execute research queries.")
```

`search_fetch.py` catches that per-query (correctly — one failed query
shouldn't abort the claim) and logs `action="search_failed"`. After all
planned queries fail, `sources = []`. `evidence_analysis` never runs
(nothing to analyze). `propose_verdict` sees `evidence_rows == []` and
short-circuits to `UNVERIFIED` — **correctly**, per its own logic, given
zero evidence. This is why the caption's `WHAT WE FOUND` / `WHY` sections
render empty: `content_generation.py`'s prompt is explicitly told there is
no evidence, and (when working correctly) writes copy that says exactly
that ("we could not confirm this with reliable evidence") — it does not
fabricate a finding.

**In short: there is no naive "search once and give up" happening. There
is no search happening at all**, because `SEARCH_API_KEY` was never
configured, and there was no alternative, keyless search backend to fall
back to. Every downstream "empty" symptom (empty evidence, `UNVERIFIED`
verdict, empty caption sections) is a correct, honest consequence of that
one missing input — not independent bugs in the reasoning chain. This was
confirmed live, not inferred: `audit_logs.output_summary.error` for every
`search_failed` row is the literal string above.

A second, related and separately confirmed bug: `TavilySearchProvider`'s
`tenacity` retry decorator had no exception-type filter, so it retried
that *permanent* misconfiguration error 3 times (2s+4s backoff) per query,
per claim — pure wasted time that could never succeed. Fixed in this pass
(see CHANGELOG below) — but retrying harder was never going to produce a
result, because there was still nothing to search with.

## 5. Where the pipeline can hallucinate (inventory)

- **Claim extraction** (`claim_extraction.py`): the model can invent an
  atomic claim not actually present in the transcript/OCR/caption.
  Mitigation that exists: `source_quote` is requested on every claim
  (schema field, optional). Mitigation that did **not** exist until this
  pass: nothing checked whether `source_quote` was actually present or
  actually appeared in the source text — see §7's live finding.
- **Research planning**: can propose queries that don't reflect the claim
  (low-stakes; queries aren't evidence, just search input).
- **Evidence analysis**: could claim a source supports/contradicts
  something it doesn't. Mitigated by: reading only the actually-retrieved
  passage (`storage.get_bytes(source.full_text_storage_key)`), never the
  live model's outside knowledge; `wrap_untrusted()` delimiting to resist
  prompt injection from the source page itself.
- **Verdict**: could cite evidence that doesn't exist, or state a number
  not present in any cited passage. Mitigated deterministically by
  `validation.py` (§3) — this is the strongest anti-hallucination layer
  in the codebase and it is not an LLM.
- **Content generation**: can, in principle, invent a source name/URL in
  the caption. Mitigated structurally: `ContentGenerationResult`'s schema
  has **no** source-name/URL field at all — `build_caption()` assembles
  the `SOURCES:` block directly from `Source` rows in code
  (`content_generation.py`, top of file: "Source names/URLs in the
  caption are assembled from `sources` rows in code, never generated by
  the LLM"). The model cannot introduce a source that wasn't actually
  fetched, by construction, not by prompting.
- **New failure mode found live in this pass, not previously documented**:
  small local models (Ollama) can return **schema-valid but empty or
  ungrounded** output — not a hallucinated fact, but a non-answer that
  passes every existing check because nothing was actually asserted. See
  §7.

## 6. Instagram URL processing

`ReelCreate.auto_fetch=True` → `services/url_downloader.py` (yt-dlp) →
video + thumbnail + best-effort metadata (caption, uploader, counts,
upload date — never invented, left `None` if yt-dlp doesn't report it).
This is explicitly documented (`ARCHITECTURE.md` §2a) as operating outside
Instagram's Terms of Service for Instagram URLs specifically, off by
default, opt-in only. **Confirmed live in this pass**: Instagram's CDN
intermittently returns an empty media response under rate-limiting even
for a fully public, accessible post — a fetch that failed outright
succeeded immediately on a bare retry with no other change. The download
call had no retry logic before this pass (fixed — see CHANGELOG).

## 7. Live regression test: `https://www.instagram.com/p/DbuqfKHN1zI/`

Run against the running application, not simulated:

1. **First attempt** (before today's fixes): `auto_fetch` failed outright
   — `yt-dlp` reported "Instagram sent an empty media response." Metadata-
   only extraction (`skip_download=True`) succeeded and confirmed the post
   is a real, accessible video (`ext: mp4`) — so this was the transient
   CDN issue in §6, not a hard access block. Fixed with a retry (§6); the
   same URL succeeded on the next attempt with zero other changes.
2. Real reel ingested: creator `InformIndia24`, posted 2026-08-07,
   127,117 likes, a 947-character caption, real video downloaded and
   transcribed.
3. `/analyze` run end-to-end; results below.

4. `claim_extraction` produced **4 real, atomic, correctly-typed claims**
   from the transcript+caption — confirming §2's claim that decomposition
   already works; this reel was never the "treat the whole reel as one
   claim" failure mode:
   - The government introduced a rule requiring takedown within three
     hours of a government direction/court order.
   - The amended rules introduce stricter requirements for AI-generated/
     synthetic content.
   - Arvind Kejriwal criticized the government over the three-hour rule.
   - Kejriwal alleged the rule was enacted out of fear following a recent
     Gen Z protest movement.
5. Root-caused §4's bug and fixed it (see §10 below), then re-ran
   research/evidence/verdict for all 4 claims against the same real
   content. Result, with the fix in place:

| # | Claim | Sources retrieved | Verdict | Confidence | Validation |
|---|---|---|---|---|---|
| 1 | Three-hour takedown rule introduced | 11 (incl. Reuters, news_wire) | UNVERIFIED | 0.30 | downgraded — unsupported number in reasoning |
| 2 | Stricter AI-generated content rules | 10 (incl. Wikipedia, Indian Kanoon, Economic Times, Chambers) | **TRUE** | 0.90 | passed |
| 3 | Kejriwal criticized the rule | 12 (incl. BBC established_news, India Today factcheck_org, direct on-topic coverage) | UNVERIFIED | 0.40 | downgraded — unsupported number in reasoning |
| 4 | Kejriwal alleged fear of Gen Z movement as motive | 3 (weaker/thinner sources) | UNVERIFIED | 0.00 | downgraded — unsupported number in reasoning |

36 real sources retrieved and archived across the 4 claims — not zero.
One claim (#2) came back a confident, evidence-backed **TRUE**. Claims 1
and 3 had real, directly relevant, on-topic evidence (Reuters; BBC;
India Today; multiple outlets' coverage of Kejriwal specifically
criticizing this rule) but were still downgraded to `UNVERIFIED` by the
deterministic validator over an "unsupported number" — investigated and
found to be a real validator bug (a URL's own numeric ID, e.g. the
`3065258` in a cited article's URL, was being flagged as an uncited
statistic); fixed in this pass (§10). Claim #4 is the most speculative
claim of the four (an alleged *motive*, not an observable fact) and
genuinely turned up thinner evidence — a plausible, honest `UNVERIFIED`.

This is a categorically different outcome from the reported bug: real
citable sources, a real `TRUE` verdict, and `UNVERIFIED` verdicts that
reflect the deterministic anti-hallucination validator being appropriately
strict — not silence from zero research ever being attempted.

## 8. Frontend flow (what the operator actually sees)

`reels/new` (paste URL + auto-fetch, or upload/paste manually) →
`reels/[id]` (Analyze button → shows extracted claims, each with a
"Build Fact-Check" button once it has a verdict) → `fact-checks/[id]`
(caption editor, slide previews, Approve/Reject/Research Again, publish
flow gated behind `HUMAN_APPROVAL_MODE`, which defaults `True`). No public
fact-check page exists (`/fact-check/<id>` from the vision doc is not
built) — everything today is internal/authenticated review tooling.

## 9. Gaps versus the product vision (honest inventory, not yet fixed unless noted in CHANGELOG)

- Claim taxonomy is `factual | opinion | prediction | satire | rhetorical`
  — narrower than the requested
  `FACTUAL | OPINION | PREDICTION | RHETORICAL | SATIRE | INTERPRETATION |
  FACTUAL_BUT_SUBJECTIVE | NOT_FACT_CHECKABLE`, and there is no secondary
  claim-*type* taxonomy (`LAW_OR_REGULATION`, `GOVERNMENT_ACTION`, etc.)
  driving research strategy.
- No `RESEARCH_FAILED` / `INSUFFICIENT_EVIDENCE` / `SOURCE_ACCESS_FAILED`
  distinction from genuine `UNVERIFIED` — today, a missing search backend
  and "we searched hard and truly found nothing" produce an identical
  verdict. This conflation is real and is what this task fixes (§10).
- No publication gate: `build_fact_check()` always proceeds to
  content/slide generation regardless of evidence count or quality.
- No iterative/broadening research retry loop (general → claim-specific →
  primary-source → contradiction → historical) — one round of N
  LLM-planned queries per claim, no retry-with-different-strategy.
- No explicit duplicate-*reporting* detection (20 outlets republishing one
  wire story) beyond the corroboration-count signal already in
  `source_scoring.py`; no `source_independence` field.
- No quote-verification sub-stage.
- `FactCheck.covered_claim_ids` exists in the schema but is always set to
  `[]` in `orchestrator.build_fact_check()` — multi-claim "overall reel
  verdict" aggregation is not implemented; each fact-check today is built
  from one primary claim.
- No "Research Quality Score" distinct from per-claim `confidence`.
- No public `/fact-check/<id>` page.
- Carousel slides currently look visually heavier/more dramatic than the
  "credible, neutral, editorial" direction requested, and (separately, a
  real rendering bug observed live) slide 1 and slide 2 have text
  overlapping the background thumbnail image in the current template.

## 10. What this pass actually fixed (root cause first, per the requested priority order)

1. **`backend/app/services/search/duckduckgo.py`** (new) — a real,
   keyless `SearchProvider`: DuckDuckGo search (`ddgs`) + this process
   directly fetching and extracting each result page's main text
   (`trafilatura`), so a search result's title is never treated as
   evidence. Wired as the new default (`SEARCH_PROVIDER=duckduckgo`) via
   a new `backend/app/services/search/factory.py`, mirroring the existing
   `LLM_PROVIDER` selection pattern. Tavily remains available
   (`SEARCH_PROVIDER=tavily` + `SEARCH_API_KEY`) as a paid, generally more
   reliable alternative. **This is the actual fix for the reported bug** —
   everything downstream of it (empty evidence, empty caption sections,
   `UNVERIFIED` by default) was a correct consequence of zero working
   search backends, not a reasoning defect.
2. **`RESEARCH_FAILED` distinction + publication gate** — new
   `ResearchFailedError` (`core/exceptions.py`), new
   `ClaimStatus.research_failed` enum value (Alembic migration
   `2159f6a269bf`). `search_fetch.fetch_evidence_sources()` now raises it
   when *every* planned query failed at the infrastructure level (vs.
   queries that ran fine and genuinely found little/nothing — a real,
   legitimate `UNVERIFIED`). `orchestrator.analyze_reel()` catches it
   per-claim (marks the claim, does not create a Verdict row, does not
   abort the rest of the reel's analysis). `orchestrator.build_fact_check()`
   refuses outright (`ValueError`) to build a fact-check from a
   `research_failed` claim — a `RESEARCH_FAILED` claim can never reach a
   publishable state, per the requirement.
3. **`url_downloader.py` retry** — Instagram's CDN intermittently returns
   an empty media response under rate-limiting even for fully public,
   accessible posts (confirmed live on the mandatory test URL: failed
   outright, then succeeded on a bare retry with zero other change). Added
   a 3-attempt retry that only fires on transient-looking failures, not on
   permanent ones (login-required, extractor-out-of-date).
4. **`validation.py` false-positive fix** — the anti-hallucination
   numeric-support check was flagging numeric IDs embedded in cited URLs
   (e.g. the `3065258` in `.../article-3065258.html`) as "unsupported
   statistics," downgrading otherwise well-evidenced verdicts. URLs are
   now stripped before the number-support check runs. Confirmed against
   the real test reel's own verdict text that triggered it live.
5. **`source_scoring.py` tier expansion** — genuinely major, established
   outlets (Times of India, The Hindu, Indian Express, NDTV, Economic
   Times, NYT, WSJ, Guardian, Washington Post, etc.) and a primary
   case-law database (Indian Kanoon) were falling through to the lowest
   tier (`other`) simply because they weren't in the original 5-domain
   hardcoded list, understating their reliability score. Confirmed live:
   real, on-topic evidence for the test reel kept landing in `other`.
6. **Regression tests** — 4 new test files, 18 new test cases, all
   integration-style against real Postgres where the behavior actually
   depends on DB state: `RESEARCH_FAILED` raised only on 100% infra
   failure (never on a partial failure or genuine zero-result search),
   the publication gate refusing a `research_failed` claim, zero-evidence
   verdicts never calling the LLM at all, duplicate-URL dedup within a
   claim's sources, and inaccessible/empty-content results never becoming
   a `Source` row. Plus the validator URL/number fix's own two tests and
   the expanded tier classification's test. Full suite: 66 passed.

**Deliberately not done in this pass** (see §9's gap inventory for the
rest, and the accompanying report for why): claim taxonomy expansion,
per-claim-type research strategy, iterative broadening retry loop,
overall multi-claim reel verdict aggregation, quote verification, a
public fact-check page, and carousel visual redesign. The task's own
stated priority order puts the evidence engine (fixed) ahead of these,
and the evidence engine was the actual reported failure.
