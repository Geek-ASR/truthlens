# TruthLens — External API Requirements

For each API: what it's used for, whether Meta/platform approval is
needed, cost shape, and the env var that configures it. None of these
keys exist yet — the app must run (in a degraded/explicit-error mode)
without them, and every provider is behind an interface so it can be
swapped.

## 1. Meta / Instagram Graph API — publishing (required for Phase 4)

- **Used for:** creating media containers, publishing the 4-slide
  carousel, retrieving publish status, pulling Insights analytics.
- **Approval required:** Yes — significant.
  1. A Meta Developer account and a Meta App (App Type: Business).
  2. An **Instagram Professional account** (Business or Creator) — personal
     accounts cannot use the Publishing API at all.
  3. The Instagram account must be linked to a **Facebook Page**.
  4. The app needs the `instagram_business_content_publish`,
     `instagram_business_basic`, and (for Insights) `instagram_business_manage_insights`
     permissions/scopes. As of the current Graph API generation these are
     requested through **Meta App Review** — Meta manually reviews use-case,
     a screencast of the flow, and a privacy policy URL before granting
     access beyond the app's own test users/roles.
  5. Until App Review is approved, publishing only works for Instagram
     accounts added as "Instagram Testers"/roles on the app itself — which
     is sufficient for development and for the operator's own TruthLens
     account, but not for publishing on behalf of anyone else.
  6. Carousel publish limits: max 10 children per carousel (we use 4),
     each child must be created as its own media container first, and the
     **video-in-carousel** option exists but has extra processing-status
     polling requirements — see ARCHITECTURE §2 and METHODOLOGY §Slide 2
     for why the MVP defaults to an image (thumbnail/keyframe) for slide 2
     rather than a native video child.
  7. Rate limits are per Instagram Business Account, roughly 25
     content-publish calls per 24h (subject to change by Meta) — this
     comfortably covers `MAX_POSTS_PER_DAY = 3`.
- **Cost:** Free (subject to standard Meta platform terms).
- **Env vars:** `META_APP_ID`, `META_APP_SECRET`, `INSTAGRAM_ACCESS_TOKEN`
  (long-lived, encrypted at rest per SECURITY.md), `META_GRAPH_API_VERSION`.
- **Not used / explicitly excluded:** any endpoint or method for reading
  *other* accounts' reels, comments, or engagement — the Graph API does
  not expose that for arbitrary third parties, and this project does not
  attempt to work around that (see ARCHITECTURE §2).

## 2. Anthropic Claude API (required for Phase 1)

- **Used for:** claim extraction, research planning, evidence analysis,
  verdict generation, content generation, vision context on frames.
- **Approval required:** No — standard API key signup.
- **Cost:** token metered; see `claude-api` skill / Anthropic pricing page
  for current per-model rates. Verdict/validation-adjacent stages should
  default to a stronger model; high-volume/low-risk stages (OCR cleanup,
  simple formatting) can use a cheaper model — configurable per stage via
  `LLM_MODEL_<STAGE>` env vars so cost/quality can be tuned without a
  code change.
- **Env vars:** `ANTHROPIC_API_KEY`.

## 3. OpenAI Whisper API (default transcription provider, Phase 1)

- **Used for:** audio → timestamped transcript.
- **Approval required:** No.
- **Cost:** per-minute metered. A self-hosted `faster-whisper` fallback
  (no per-minute cost, needs a GPU or patient CPU) is supported via
  `TRANSCRIPTION_PROVIDER=local` for cost-sensitive deployments.
- **Env vars:** `OPENAI_API_KEY`.

## 4. Search API — Tavily (default, Phase 1)

- **Used for:** the research engine's web search + clean content
  extraction (§12 tiered sourcing).
- **Approval required:** No — API key signup, has a free tier.
- **Why Tavily over raw Google/Bing:** it returns already-extracted page
  text (fewer separate scraping/readability steps) and supports
  include/exclude-domain filtering, which is used to bias queries toward
  Tier 1/Tier 2 domains. This is a swappable choice — `SearchProvider`
  interface also has a documented adapter shape for Bing Web Search or
  Google Programmable Search if the operator prefers those.
- **Cost:** metered per search call, has a free tier sufficient for MVP
  development volume.
- **Env vars:** `SEARCH_API_KEY`, `SEARCH_PROVIDER=tavily`.

## 5. Object storage — S3-compatible

- **Used for:** uploaded reel media, extracted keyframes, rendered
  slides, archived full-text of fetched sources (citation integrity).
- **Approval required:** No.
- **Cost:** MinIO is free/self-hosted for local dev; Cloudflare R2 (no
  egress fees) or AWS S3 for production.
- **Env vars:** `S3_ENDPOINT_URL`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
  `S3_BUCKET`.

## 6. Discovery-phase APIs (Phase 5+, not built yet)

These are documented now so the schema has the right hooks
(`reels.discovery_source`), but are not implemented until Phase 5.

| API | Purpose | Approval |
|---|---|---|
| YouTube Data API v3 | discover political video content, comments | free API key, quota-limited |
| X API | discover trending political posts | paid tiers since 2023; Basic tier has meaningful cost |
| News RSS feeds | no API needed, standard RSS/Atom parsing | none |
| Fact-check orgs (PolitiFact, Snopes, AFP, BOOM, Alt News, etc.) | corroboration, Tier 3 sourcing | most publish RSS/sitemaps; a few offer the Google Fact Check Claim Search API (free, requires a Google Cloud API key) |
| Google Fact Check Claim Search API | structured search over existing fact-checks worldwide | free, standard Google Cloud API key |

## 7. What cannot be automated at all (documented per product spec §36.6)

- **Arbitrary third-party Instagram reel discovery/download.** No
  compliant API exists for this. Permanent human-in-the-loop step (see
  ARCHITECTURE §2). This is a legal/ToS constraint (Instagram's terms
  prohibit scraping and automated data collection outside the API), not
  a temporary technical gap.
- **Publishing on behalf of an Instagram account the operator does not
  control**, before Meta App Review is granted for the relevant scopes.
- **Verifying a speaker's subjective intent or private knowledge** (e.g.
  "did they know this was false when they said it") — out of scope for
  any fact-checking system; the product only evaluates whether the
  factual content of a claim is supported by evidence, not the speaker's
  state of mind.
