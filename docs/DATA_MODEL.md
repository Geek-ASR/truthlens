# TruthLens — Data Model

PostgreSQL 15+, with the `pgvector` extension enabled (used for claim/source
similarity search in duplicate detection). All tables use `uuid` primary
keys (`gen_random_uuid()`), `created_at`/`updated_at` timestamps, and are
append-friendly: nothing that has ever been published is hard-deleted (see
`corrections` and `audit_logs` — history must remain inspectable).

This is the literal source of truth for `backend/app/db/models.py`. If the
two ever disagree, the code wins and this file should be updated.

## Entity-relationship overview

```
users                 instagram_accounts
  │                        │
  │ (approves/edits)       │ (publishes to)
  ▼                        ▼
reels ──< claims ──< evidence >── sources
  │          │
  │          └──< verdicts (1 current + history via corrections)
  │
  └──< fact_checks ──< slides
             │  │
             │  └──< corrections
             │
             ├──< generated_posts ──< publishing_jobs
             │
             └──< analytics_snapshots

search_queries (per claim, audit trail of research planning)
audit_logs (generic append-only log, references any entity by type+id)
```

## Tables

### `users`
Admin/reviewer accounts for the dashboard (not Instagram end-users).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| email | text unique | |
| hashed_password | text | argon2 |
| role | enum(`admin`,`reviewer`,`viewer`) | role-based access, §20/§28 |
| is_active | bool default true | |
| created_at, updated_at | timestamptz | |

### `instagram_accounts`
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| ig_user_id | text unique | Instagram-scoped user id from Graph API |
| ig_username | text | |
| facebook_page_id | text | required for Graph API publishing |
| access_token_encrypted | bytea | AES-encrypted long-lived token, never returned via API |
| token_expires_at | timestamptz | long-lived tokens ~60 days; job refreshes before expiry |
| connected_by_user_id | uuid FK users | |
| status | enum(`active`,`expired`,`revoked`) | |
| created_at, updated_at | timestamptz | |

### `reels`
The source media being fact-checked. Ingested manually in Phase 1–4;
`discovery_source`/`virality_score` are populated by Phase 5+ discovery.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| source_url | text | original Instagram (or other platform) URL, required |
| platform | enum(`instagram`,`youtube`,`x`,`tiktok`,`other`) | |
| creator_handle | text nullable | as displayed, not verified identity |
| caption_text | text nullable | as posted with the reel |
| posted_at | timestamptz nullable | if known |
| view_count, like_count, comment_count, share_count | bigint nullable | best-effort, self-reported by whoever submits the reel unless from an authorized API |
| hashtags | text[] | |
| media_storage_key | text | object storage key for the uploaded video/image, required in Phase 1 flow |
| media_content_hash | text | perceptual/SHA-256 hash for duplicate detection |
| thumbnail_storage_key | text nullable | extracted keyframe used on Slide 1/2 |
| transcript | text nullable | Whisper output |
| transcript_segments | jsonb nullable | timestamped segments `[{start,end,text}]` |
| ocr_text | jsonb nullable | `[{frame_ts, text, confidence}]` |
| vision_context | jsonb nullable | Claude vision scene descriptions, advisory only, never cited as evidence |
| discovery_source | enum(`manual`,`rss`,`youtube`,`x`,`news`,`factcheck_org`,`tip`) default `manual` | |
| virality_score | float nullable | see METHODOLOGY §Virality |
| ingestion_status | enum(`uploaded`,`transcribing`,`transcribed`,`failed`) | |
| submitted_by_user_id | uuid FK users nullable | |
| created_at, updated_at | timestamptz | |

### `claims`
Atomic claims extracted from a reel. Mirrors the JSON shape in product
spec §10.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| reel_id | uuid FK reels | |
| text | text | the atomic claim, in the system's own precise wording |
| source_quote | text nullable | verbatim substring of transcript/OCR this claim was derived from |
| claim_type | enum(`factual`,`opinion`,`prediction`,`satire`,`rhetorical`) | §11 |
| verifiable | bool | only `factual` claims are typically `true` |
| time_reference | text nullable | free text, e.g. "yesterday", "2024-03" |
| location | text nullable | |
| entities | jsonb | `[{name, type}]` — people/orgs/places named |
| importance | float | 0-1, editorial significance used in triage, not evidence |
| embedding | vector(1536) nullable | for duplicate/similar-claim search |
| extraction_model | text | model id + prompt version used |
| status | enum(`extracted`,`researching`,`researched`,`skipped_not_verifiable`) | |
| created_at, updated_at | timestamptz | |

### `search_queries`
Audit trail for the research-planning stage (§16 Model 3).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| claim_id | uuid FK claims | |
| query_text | text | |
| target_tier | enum(`tier1_primary`,`tier2_secondary`,`tier3_factcheck`,`unrestricted`) | |
| provider | text | e.g. `tavily` |
| executed_at | timestamptz | |
| result_count | int | |
| raw_response_storage_key | text nullable | full provider response archived to object storage for audit |

### `sources`
Immutable once fetched — a source record is never edited after
`retrieved_at`; if content changes, a new source row is created and the
old one is retained (§13, §15: "never cite an article the system did not
actually retrieve").

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| url | text | |
| title | text nullable | |
| publisher | text nullable | |
| author | text nullable | |
| publication_date | timestamptz nullable | |
| retrieved_at | timestamptz | when TruthLens actually fetched it |
| source_type | enum(`primary_government`,`primary_legal`,`primary_data`,`news_wire`,`established_news`,`academic`,`factcheck_org`,`other`) | §12 tiers |
| full_text_storage_key | text | archived full extracted text (for citation integrity, not just a URL) |
| relevant_passage | text | the specific excerpt used |
| reliability_score | float | 0-1, see METHODOLOGY §Source Scoring |
| reliability_breakdown | jsonb | per-dimension sub-scores (primary_status, reputation, transparency, recency, directness, corroboration, conflict) |
| retrieval_query_id | uuid FK search_queries nullable | |
| created_at | timestamptz | |

### `evidence`
The claim × source evidence matrix (§14) — one row per (claim, source)
pair actually used in analysis.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| claim_id | uuid FK claims | |
| source_id | uuid FK sources | |
| stance | enum(`supports`,`contradicts`,`provides_context`,`irrelevant`) | |
| explanation | text | one/two sentence structured justification, not hidden CoT (§25) |
| directness | enum(`direct`,`indirect`) | does the passage address the claim directly |
| analysis_model | text | model id + prompt version |
| created_at | timestamptz | |

### `verdicts`
One current verdict per claim; corrections create a new row and mark the
prior one superseded rather than overwriting it (§26: never silently
rewrite).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| claim_id | uuid FK claims | |
| verdict | enum(`TRUE`,`MOSTLY_TRUE`,`MISLEADING`,`MOSTLY_FALSE`,`FALSE`,`UNVERIFIED`,`OUTDATED`,`MISSING_CONTEXT`) | §5 |
| confidence | float | 0-1 internal score, §19 |
| confidence_band | enum(`very_high`,`high`,`moderate`,`requires_review`) | derived from confidence thresholds |
| reasoning_summary | text | structured explanation citing which evidence rows drove the verdict (references `evidence.id` list) |
| cited_evidence_ids | uuid[] | must be a subset of `evidence` rows for this claim; validated (§17) |
| validation_status | enum(`passed`,`downgraded_missing_citation`,`downgraded_unfetched_source`,`downgraded_unsupported_stat`) | output of the deterministic anti-hallucination check |
| verdict_model | text | model id + prompt version |
| is_current | bool default true | |
| superseded_by_id | uuid FK verdicts nullable | |
| created_at | timestamptz | |

### `fact_checks`
The publishable unit — one reel can in principle produce more than one
fact_check if multiple independent claims each warrant their own post,
but each fact_check has exactly one primary claim it is built around.

| column | type | notes |
|---|---|---|
| id | uuid PK | used in `truthlens.example/fact-check/<id>` |
| reel_id | uuid FK reels | |
| primary_claim_id | uuid FK claims | the claim the carousel is built around |
| covered_claim_ids | uuid[] | other claims addressed in the same post, if any |
| current_verdict_id | uuid FK verdicts | snapshot pointer, updates on correction |
| status | enum(`researching`,`ready_for_review`,`approved`,`rejected`,`published`,`corrected`,`retracted`) | pipeline + review state, §20 |
| caption_text | text | full Instagram caption, human-editable |
| methodology_note | text | short public-facing methodology blurb for the web page |
| reviewed_by_user_id | uuid FK users nullable | |
| reviewed_at | timestamptz nullable | |
| review_notes | text nullable | internal reviewer comments |
| duplicate_of_fact_check_id | uuid FK fact_checks nullable | set + status forced to `rejected` if duplicate detection matches |
| public_page_published | bool default false | |
| created_at, updated_at | timestamptz | |

### `slides`
Rendered images for a fact_check (exactly 4 in the standard template).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| fact_check_id | uuid FK fact_checks | |
| position | smallint | 1-4 |
| slide_type | enum(`poster`,`original_reel`,`evidence`,`conclusion`) | |
| image_storage_key | text | rendered PNG, 1080x1350 |
| template_version | text | |
| content_json | jsonb | the structured text content used to render (so slides can be regenerated deterministically after an edit) |
| created_at, updated_at | timestamptz | |

### `generated_posts`
The finalized, review-approved creative bundle handed to the publisher.

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| fact_check_id | uuid FK fact_checks unique | one active generated_post per fact_check |
| instagram_account_id | uuid FK instagram_accounts | |
| idempotency_key | text unique | hash of `fact_check_id` + content version; prevents double-publish (§21, §27) |
| approved_by_user_id | uuid FK users | |
| approved_at | timestamptz | |
| created_at | timestamptz | |

### `publishing_jobs`
Operational tracking of the Graph API publish sequence (§21).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| generated_post_id | uuid FK generated_posts | |
| status | enum(`pending`,`containers_created`,`carousel_created`,`publishing`,`published`,`failed`) | |
| media_container_ids | jsonb | per-slide Graph API container ids |
| carousel_container_id | text nullable | |
| ig_media_id | text nullable | final published media id |
| permalink | text nullable | |
| attempt_count | int default 0 | |
| last_error | text nullable | |
| next_retry_at | timestamptz nullable | |
| created_at, updated_at | timestamptz | |

### `corrections`
| column | type | notes |
|---|---|---|
| id | uuid PK | |
| fact_check_id | uuid FK fact_checks | |
| previous_verdict_id | uuid FK verdicts | |
| new_verdict_id | uuid FK verdicts | |
| correction_reason | text | required, human-authored or AI-drafted + human-approved |
| new_evidence_source_ids | uuid[] | |
| corrected_by_user_id | uuid FK users | |
| published_correction_note | text | public-facing text shown on the web page and, if warranted, a follow-up Instagram post |
| created_at | timestamptz | |

### `audit_logs`
Append-only, generic. Every pipeline stage call and every human action
writes one row here (§25).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| entity_type | text | e.g. `claim`, `verdict`, `fact_check`, `publishing_job` |
| entity_id | uuid | |
| actor_type | enum(`ai_stage`,`human`,`system`) | |
| actor | text | model id+version, or user email, or `celery_beat` |
| action | text | e.g. `claim_extraction`, `approve`, `edit_caption`, `publish` |
| input_summary | jsonb | |
| output_summary | jsonb | structured, not raw hidden reasoning |
| prompt_version | text nullable | |
| created_at | timestamptz | |

### `analytics_snapshots`
Time-series pulls from Instagram Insights + internal pipeline metrics
(§31).

| column | type | notes |
|---|---|---|
| id | uuid PK | |
| fact_check_id | uuid FK fact_checks nullable | null for platform-wide snapshots |
| metric_scope | enum(`post`,`account`,`pipeline`) | |
| reach, impressions, likes, comments, shares, saves | int nullable | |
| follower_count, profile_visits, website_clicks | int nullable | account-level |
| pipeline_metrics | jsonb nullable | claims_processed, avg_research_time_s, avg_sources_per_claim, human_rejection_rate, correction_rate, verdict_distribution |
| captured_at | timestamptz | |

## Indices worth calling out at implementation time
- `sources(url)` — btree, to short-circuit re-fetching a URL already retrieved recently
- `claims(embedding)` — ivfflat/hnsw (pgvector) for duplicate/similar-claim search
- `reels(media_content_hash)` — unique-ish lookup for exact re-upload detection
- `fact_checks(status)`, `publishing_jobs(status)` — dashboard queue queries
- `audit_logs(entity_type, entity_id, created_at)` — timeline reconstruction
