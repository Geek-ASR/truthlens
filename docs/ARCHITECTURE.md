# TruthLens — Technical Architecture

## 0. Status of the repository

This was an empty directory with no prior code, no git history, and no
framework decisions made. Everything in this document is a fresh proposal,
not a description of existing state. This is the starting point for all
other documents in `/docs`.

## 1. Guiding constraints (from product spec, restated as engineering rules)

1. **No unofficial Instagram automation.** No Selenium/Playwright login
   automation, no cookie reuse, no private API reverse-engineering, no
   scraping of arbitrary public reels. Only the official Meta Graph API
   (Instagram Content Publishing API, requires an Instagram **Business or
   Creator** account linked to a Facebook Page) is used to publish.
2. **No fabrication.** Every fact used in a verdict must trace to a
   retrieved, stored source document. If evidence is insufficient, the
   verdict is `UNVERIFIED`, never a guess.
3. **Human approval is the default gate.** Nothing reaches Instagram without
   an explicit `APPROVE` action, until/unless the operator later opts into
   Automatic Mode for a narrow, trusted claim category.
4. **Neutrality is structural, not just prompt-level.** The same research →
   evidence → verdict pipeline runs regardless of which political actor is
   named in the claim; there is no "target" concept anywhere in the schema.
5. **Everything is auditable.** Every AI call is logged with input, model,
   prompt version, and a structured (non-hidden-reasoning) justification.

## 2. The reel-acquisition gap (read this first)

The Instagram Graph API **does not** provide a way to fetch an arbitrary
third-party public reel's video file, transcript, or engagement metrics.
The Graph API only exposes content owned by the Instagram Business account
that has authorized the app. There is no compliant, official way to
"discover trending political reels on Instagram" by polling Instagram
itself.

Consequently, Phase 1–4 of this build (the actual MVP) uses a
**human-in-the-loop ingestion model**: the operator supplies a reel URL
*and* the media itself (an uploaded video file, or a screen recording, or a
pasted transcript/caption), rather than the system scraping Instagram to
obtain it. This is not a workaround to be removed later — it is the
permanent, compliant acquisition path for Instagram-sourced content.

Automated *discovery* (Phase 5+) instead watches sources that do have
legitimate APIs or licensing-permitted access: news RSS feeds, established
fact-checking organizations' feeds/APIs, YouTube Data API, X API, and
operator-submitted tip lines. Those sources can be polled automatically.
When a discovered story maps to a specific Instagram reel that is going
viral, the system still needs a human to supply the reel media, per above.
This limitation is documented, not hidden, in the product itself (see
§15 "Limitations" in the methodology doc).

## 3. High-level pipeline (as implemented)

```
┌─────────────────┐
│ Reel Input       │  URL (required) + uploaded video file OR pasted
│ (manual, Ph.1)   │  transcript/caption (at least one media source required)
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Ingestion        │  store raw file in object storage, extract metadata,
│                  │  compute perceptual hash for duplicate detection
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Transcription    │  Whisper (audio → text, timestamped)
│ + OCR            │  Tesseract (on-screen text, sampled frames)
│ + Vision context │  Claude vision (scene description, on-screen graphics)
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Claim Extraction │  Claude, structured JSON output → atomic claims,
│ (Model: claims)  │  each tagged factual / opinion / prediction / satire /
│                  │  rhetorical, with entities + time/location refs
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Research Planner │  Claude turns each verifiable claim into 2-5 targeted
│ (Model: plan)    │  search queries, tiered by source-type preference
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Search + Fetch   │  Search API (Tavily) executes queries → candidate URLs
│                  │  → full-text fetch + readability extraction → stored
│                  │  as immutable Source records with retrieved_at stamps
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Source Scoring   │  deterministic + LLM-assisted reliability scoring
│                  │  (tier, corroboration, recency, directness)
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Evidence Analysis│  Claude reads claim + retrieved passages only (no open
│ (Model: analyze) │  web access at this stage) → stance per source
│                  │  (supports/contradicts/context) + evidence matrix
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Verdict          │  Claude proposes verdict + confidence from the
│ (Model: verdict) │  evidence matrix only; must cite which sources drove it
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Anti-Hallucin.   │  deterministic validator: every cited source_id must
│ Validation       │  exist in DB, every URL must have been fetched, every
│                  │  quoted stat must appear in a stored passage. Verdict
│                  │  is downgraded to UNVERIFIED if validation fails.
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Content Gen      │  Claude drafts slide text + caption from the *validated*
│ (Model: content) │  evidence matrix; Pillow renders 4 slides (1080x1350)
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Duplicate Check  │  compare claim embedding + reel hash against existing
│                  │  fact_checks before allowing queue entry
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Human Review     │  Admin dashboard: approve / edit / reject / re-research
│ (default gate)   │
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Publish          │  Meta Graph API: create containers → create carousel →
│                  │  publish → poll status → store permalink
└────────┬─────────┘
         ▼
┌─────────────────┐
│ Public page +    │  truthlens.example/fact-check/<id> (Next.js SSR page)
│ Analytics        │  + Instagram Insights polling job
└──────────────────┘
```

## 4. Multi-stage AI architecture

No single LLM call produces a verdict. Each stage is a separate call with
a narrow, structured contract, logged independently (see §16/§25 of the
product spec). Stage → model mapping used in this codebase
(`backend/app/services/ai/*`):

| Stage | Purpose | Default model | Notes |
|---|---|---|---|
| `transcribe` | audio → text | Whisper (`whisper-1` via OpenAI, or local `faster-whisper`) | swappable via `TRANSCRIPTION_PROVIDER` |
| `ocr` | on-screen text | Tesseract (local, free) | swappable to cloud OCR later |
| `vision_context` | describe sampled frames | Claude (vision) | only used to aid claim extraction, never cited as evidence |
| `claim_extraction` | decompose transcript into atomic claims | Claude | structured JSON, see DATA_MODEL |
| `research_planning` | claim → search queries | Claude | must emit queries only, no verdicts |
| `evidence_analysis` | passage + claim → stance | Claude | forbidden from introducing facts not in the passage |
| `verdict` | evidence matrix → verdict + confidence | Claude | must cite `source_id`s used |
| `validation` | deterministic code, not an LLM | — | see §17 of product spec |
| `content_generation` | evidence matrix → slide text + caption | Claude | must only restate validated content |

All Claude calls use Anthropic's structured/tool-output mode (forced JSON
schema) rather than free text parsing, and every call is persisted to
`audit_logs` with prompt version, inputs, and output before the pipeline
advances to the next stage.

## 5. Why this stack (cheapest-practical reasoning)

| Concern | Choice | Why |
|---|---|---|
| Backend | Python 3.12 + FastAPI | async-friendly, first-class Pydantic validation matches the "structured JSON everywhere" requirement, easy Celery integration |
| DB | PostgreSQL | relational integrity for the evidence graph (claims→sources→evidence→verdicts) genuinely matters here; JSONB columns cover flexible fields |
| ORM/migrations | SQLAlchemy 2.0 (async) + Alembic | standard, typed, migration history is itself part of the audit story |
| Queue/scheduler | Redis + Celery + Celery Beat | mirrors the product spec's explicit "Redis + Celery" suggestion; Beat covers the cron-like discovery/research/publish schedule in §32 |
| Frontend | Next.js 14 + TypeScript + Tailwind | admin dashboard + public fact-check pages from one codebase; SSR is useful for the public page (needs to be crawlable/shareable) |
| LLM | Anthropic Claude (Sonnet 5 default, Opus 5 for verdict/validation-adjacent steps if quality demands it) | structured outputs, long context for evidence passages |
| Transcription | OpenAI Whisper API by default; `faster-whisper` local as a cost-reduction swap | MVP simplicity first, self-hosting is a documented Phase-2 optimization |
| OCR | Tesseract via `pytesseract` | free, local, no API key required for MVP |
| Web search | Tavily API | built for LLM/agentic research, returns cleaned page content (reduces a separate scraping step), has a source-domain filter useful for tiering |
| Image generation | Pillow, deterministic templates | avoids a headless-browser dependency; fully deterministic (same input → same pixels), which matters for an evidence-preserving product |
| Object storage | MinIO locally (S3 API-compatible) → Cloudflare R2 or S3 in prod | zero-cost local dev, drop-in prod swap |
| Deployment (later) | Backend: Render/Railway. DB: Neon/Supabase. Frontend: Vercel. Redis: Upstash. | matches product spec's suggested low-cost options; Docker Compose covers local/self-hosted from day one |

All provider choices are behind thin interfaces in `backend/app/services/`
(`SearchProvider`, `TranscriptionProvider`, `LLMProvider`) so swapping
Tavily→Brave or Whisper→faster-whisper is a config change, not a rewrite.

## 6. Folder structure

```
/docs                          product/architecture/legal docs (this set)
/backend
  /app
    /api                       FastAPI routers (one module per resource)
    /core                      settings, security, logging, exceptions
    /db                        SQLAlchemy models, session, base
    /pipeline                  the 10 pipeline stages, one module each,
                                orchestrated by pipeline/orchestrator.py
    /schemas                   Pydantic request/response + internal DTOs
    /services
      /ai                      LLMProvider (Anthropic), prompt templates
      /search                  SearchProvider (Tavily)
      /transcription            TranscriptionProvider (Whisper)
      /ocr                      OCRProvider (Tesseract)
      /instagram                Meta Graph API client
      /storage                  S3/MinIO client
    /workers                   Celery app + tasks (discovery, research,
                                publish, analytics polling)
    /templates                 Pillow slide templates (slide1..slide4)
    /static/fonts               bundled fonts for deterministic rendering
  /alembic                     migrations
  /tests
  Dockerfile, pyproject.toml
/frontend                      Next.js admin dashboard + public fact-check
                                pages
/infra                         docker-compose.yml, .env.example
```

## 7. What Claude Code is building now vs. deferring

Building now (Phases 1–4 of the product spec's own phasing, §35):
manual URL+media ingestion, transcription/OCR, claim extraction, research,
evidence matrix, verdict + confidence, anti-hallucination validation,
4-slide carousel generation, caption generation, duplicate detection,
audit log, admin review dashboard, and a complete (but credential-gated,
not live-fired) Instagram publishing client.

Deferred (Phases 5–8): automated multi-source discovery + virality
scoring, Celery Beat cron schedules, and the analytics dashboard beyond
stub endpoints. The DB schema and API already have the hooks for these
(`reels.discovery_source`, `reels.virality_score`, `publishing_jobs`,
`analytics` tables exist from day one) so Phase 5+ is additive, not a
rewrite. See `/docs/ROADMAP.md` for the milestone breakdown.
