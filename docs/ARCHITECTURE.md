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

## 2a. Opt-in auto-fetch (`auto_fetch=true`)

The manual path in §2 is still the default and the only ToS-compliant
one. Alongside it, `POST /api/reels` also accepts `auto_fetch=true`: when
set, and no video/transcript was supplied, the backend downloads the
video and reads whatever caption/metadata the source page exposes itself
via `yt-dlp` (`app/services/url_downloader.py`), instead of requiring a
manual upload.

This is a deliberate, operator-requested exception to the "no
unauthorized scraping" rule stated above, scoped as narrowly as the
product allows:

- **Off by default**, opt-in per reel — the manual path is untouched and
  remains the compliant default for every other call site.
- **For most platforms this is uncontroversial.** `yt-dlp` covers
  hundreds of sites; for YouTube, X/Twitter, TikTok, and general public
  web/news pages, fetching a public page's own declared metadata this way
  carries no meaningful ToS conflict for a tool like this.
- **For Instagram specifically, this is a knowing ToS exception, not a
  gap that was missed.** `yt-dlp`'s Instagram support works by calling
  Instagram's private web endpoints rather than an official, sanctioned
  API — Instagram's Terms of Service prohibit exactly this. It carries
  real operational risk: rate limiting, the extractor breaking whenever
  Instagram changes its internal API (no SLA, no notice), and — the one
  that matters most here — the connected account being flagged or banned,
  which is the same account this product publishes fact-checks from. This
  was enabled after that tradeoff was explained and the operator chose to
  accept it for their own product; it is not this system's default
  recommendation for a production deployment, and disabling it again is a
  one-line change (stop passing `auto_fetch=true` from the client — no
  backend changes needed).
- **Never silently fills in what it can't confirm.** Every field on the
  resulting `Reel` is either something `yt-dlp`'s extractor actually
  reported for that URL or left null — same "no invented facts" standard
  the rest of the pipeline holds evidence to (docs/FACT_CHECK_METHODOLOGY.md).
  Manually-supplied fields always take precedence over fetched ones.
- **Auditable.** `reels.auto_fetched` records which path produced each
  reel, and the ingestion audit log entry records `auto_fetch` explicitly,
  so this is always inspectable after the fact, per §25.

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
| `transcribe` | audio → text | local `faster-whisper` (CPU, no key) | swappable to OpenAI `whisper-1` via `TRANSCRIPTION_PROVIDER=openai` |
| `ocr` | on-screen text | Tesseract (local, free) | swappable to cloud OCR later |
| `vision_context` | describe sampled frames | Ollama `llava-phi3` (local) | only used to aid claim extraction, never cited as evidence |
| `claim_extraction` | decompose transcript into atomic claims | Ollama `llama3.2` (local) | structured JSON, see DATA_MODEL |
| `research_planning` | claim → search queries | Ollama `llama3.2` (local) | must emit queries only, no verdicts |
| `evidence_analysis` | passage + claim → stance | Ollama `llama3.2` (local) | forbidden from introducing facts not in the passage |
| `verdict` | evidence matrix → verdict + confidence | Ollama `llama3.2` (local) | must cite `source_id`s used |
| `validation` | deterministic code, not an LLM | — | see §17 of product spec |
| `content_generation` | evidence matrix → slide text + caption | Ollama `llama3.2` (local) | must only restate validated content |

`LLM_PROVIDER` (default `ollama`) selects between the local Ollama
provider and Anthropic Claude — see §8 for why Ollama is the default and
what that costs in reasoning quality. Both providers use forced
schema-conformant structured output (Anthropic's tool-forced JSON;
Ollama's `format=<json schema>` API) rather than free-text parsing, and
every call is persisted to `audit_logs` with prompt version, inputs, and
output before the pipeline advances to the next stage.

## 5. Why this stack (cheapest-practical reasoning)

| Concern | Choice | Why |
|---|---|---|
| Backend | Python 3.12 + FastAPI | async-friendly, first-class Pydantic validation matches the "structured JSON everywhere" requirement, easy Celery integration |
| DB | PostgreSQL | relational integrity for the evidence graph (claims→sources→evidence→verdicts) genuinely matters here; JSONB columns cover flexible fields |
| ORM/migrations | SQLAlchemy 2.0 (async) + Alembic | standard, typed, migration history is itself part of the audit story |
| Queue/scheduler | Redis + Celery + Celery Beat | mirrors the product spec's explicit "Redis + Celery" suggestion; Beat covers the cron-like discovery/research/publish schedule in §32 |
| Frontend | Next.js 14 + TypeScript + Tailwind | admin dashboard + public fact-check pages from one codebase; SSR is useful for the public page (needs to be crawlable/shareable) |
| LLM | Ollama running local models by default (`LLM_PROVIDER=ollama`); Anthropic Claude as an opt-in swap (`LLM_PROVIDER=anthropic`) | zero cost, no API key, no vendor usage limits — see §8 for the reasoning-quality tradeoff this default accepts, and for how to switch to Claude |
| Transcription | `faster-whisper` local by default (no key, CPU); OpenAI Whisper API as a speed/quality swap | matches the $0/no-key default posture; see §8 |
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

## 8. Local-only LLM mode (Ollama)

`LLM_PROVIDER=ollama` (the default) routes every LLM-backed pipeline stage
through a local [Ollama](https://ollama.com) server instead of Anthropic's
API — `backend/app/services/ai/ollama_provider.py`, selected by
`backend/app/services/ai/factory.py`. This means: no `ANTHROPIC_API_KEY`,
$0 per-token cost regardless of `MAX_POSTS_PER_DAY`, and no vendor rate
limit — the only limits are this machine's own hardware.

**Model choice was measured, not assumed.** The dev machine this default
was picked on has 8GB RAM (Apple M1), which rules out anything past a
small (3-8B, quantized) model. All 3 already-pulled models were run
against the actual pipeline Pydantic schemas (`ClaimExtractionResult`,
`ResearchPlan`, `EvidenceAnalysisItem`, `VerdictProposal`,
`ContentGenerationResult`) with Ollama's structured-output API
(`format=<json schema>`), not toy prompts:

| Model | Size | Schema-valid | Avg latency/call |
|---|---|---|---|
| `llama3.2` | 3B, 2.0GB | 5/5 | 9.1s |
| `llama3` | 8B, 4.7GB | 4/5 (failed `importance` bound) | 28.1s |
| `mistral` | 7B, 4.1GB | 4/5 (same failure) | 21.4s |

`llama3.2` won on both axes — the two larger models weren't just slower,
they were *less* schema-reliable, both failing the same way (emitting an
integer 1-3 "importance" ranking instead of the schema's `0.0-1.0` float).
Bigger local models are not automatically better at strict structured
output. For vision, `moondream` (1.7GB) was tried first and rejected: it
hallucinated the test image's contents entirely and looped into a
non-terminating repetition that broke JSON output. `llava-phi3` (3.8B,
2.9GB) replaced it — schema-valid and roughly on-topic, good enough given
`vision_context` is advisory-only and never cited as evidence for a
verdict (§4, DATA_MODEL's `reels.vision_context` note).

**What this default actually costs.** A 3B local model is a materially
weaker reasoner than Claude at the parts of this pipeline that are not
just JSON formatting — claim decomposition judgment, evidence-stance
nuance, and verdict calibration on ambiguous evidence. The deterministic
anti-hallucination validator (`app/pipeline/validation.py`) still catches
citations that don't trace to real evidence rows, but it cannot catch a
verdict that cites real evidence and still reasons about it poorly. This
tradeoff is accepted deliberately for a $0-cost, no-API-key, no-rate-limit
default — not hidden. Switch back with `LLM_PROVIDER=anthropic` (plus
`ANTHROPIC_API_KEY`) any time higher-quality reasoning matters more than
running for free; both providers implement the same `LLMProvider`
interface (§4), so nothing else in the pipeline changes.

**Transcription is local by default too.** `TRANSCRIPTION_PROVIDER=local`
(`backend/app/services/transcription/local_whisper.py`, `faster-whisper`
"base" model, CPU, no `OPENAI_API_KEY`) — verified against a real spoken
clip: correct transcript, ~35s including one-time model download on first
run, seconds after that. `openai` (Whisper API) remains available for
speed/quality if `OPENAI_API_KEY` is set. `SEARCH_PROVIDER=tavily` is the
one remaining paid-if-scaled dependency and is deliberately unchanged: it
is not an "AI" API in the LLM sense, and there is no local substitute for
it — the research stage needs to retrieve real, current web sources to
check claims against, which a local (or any) LLM cannot do on its own
without hallucinating. Tavily's free tier (1,000 requests/month) is the
practical floor for the research stage regardless of LLM provider.

Requires `ollama serve` running locally with `llama3.2` and `llava-phi3`
pulled (`ollama pull llama3.2 && ollama pull llava-phi3`). Inside Docker
Compose, `OLLAMA_BASE_URL` defaults to `http://host.docker.internal:11434`
to reach the host's Ollama server from within the `api`/`worker`
containers (Docker Desktop only — override for other setups).

**Automatic Gemini fallback (`GEMINI_API_KEY`, optional).** Set this and
`LLM_PROVIDER=ollama` still keeps Ollama as primary, but
`FallbackLLMProvider` (`backend/app/services/ai/factory.py`) retries any
call Ollama fails on against Gemini (`LLM_MODEL_GEMINI_FALLBACK`, default
`gemini-flash-latest`) before giving up. This isn't hypothetical
belt-and-suspenders: run live against a real Instagram reel (Hindi/English
code-switched transcript), `llama3.2`'s claim extraction produced garbled,
hallucinated claim text — nonsense mixing Latin/Cyrillic/Arabic/Tamil
script fragments, not a schema violation but genuinely wrong output that
happened to be schema-valid. Gemini handled the same input correctly.
Ollama's own retry-on-validation-failure (above) catches the
schema-shaped failures; this fallback is the safety net for the case
Ollama can't self-correct — a small model being confidently wrong.

Two real gotchas hit building this, worth knowing if `gemini_provider.py`
ever needs touching again:
- Google deprecated the `generateContent` REST endpoint for API keys
  created around Aug 2026 ("no longer available to new users") in favor
  of a new **Interactions API** (`google-genai` SDK ≥2.3.0,
  `client.aio.interactions.create`). Pinned model names like
  `gemini-2.5-flash` also 404 for new keys even via the new API — only
  `-latest` aliases and `gemini-3.x` names work, which is why
  `LLM_MODEL_GEMINI_FALLBACK` uses `gemini-flash-latest` rather than a
  pinned version (avoids going stale the same way again).
- Gemini's `responseSchema` is an OpenAPI-3.0-flavored *subset* of JSON
  Schema — no `$ref`/`$defs` (must be fully inlined) and only a few
  `format` values are recognized. `_to_gemini_schema()` converts a
  Pydantic `model_json_schema()` output into that shape.
- Installing `google-genai` force-upgraded `pydantic` 2.10.3 → 2.13.4
  across the whole venv (it's a hard dependency floor). Full test suite
  passed unchanged after the bump, but it's worth knowing this wasn't a
  deliberate, isolated choice — `requirements.txt` reflects the
  now-installed version.

This tradeoff is different from Ollama's: Gemini's free tier is generous
enough for this project's volume (12 posts/day) to cost $0 in practice,
but it's still a real external API key subject to Google's rate limits
and ToS — not "no restrictions whatsoever." It only ever fires when
Ollama already failed, so the $0/no-key/offline default holds for the
common case; this is deliberately an escape hatch, not a silent primary
swap.
