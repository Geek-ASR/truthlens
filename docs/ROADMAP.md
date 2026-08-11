# TruthLens — Roadmap

Phased per product spec §35, with concrete deliverables per phase and a
mapping to what "done" means. Phases 1-4 are what this initial build
implements; 5-8 are scoped but deferred.

## Phase 1 — Manual pipeline (this build)
Paste reel URL + upload media → transcript → OCR → claims → research →
evidence matrix → verdict → confidence.

Deliverables: `reels`, `claims`, `sources`, `evidence`, `verdicts` tables;
`/api/reels` ingestion endpoint; pipeline orchestrator running all stages
synchronously-callable (and Celery-task-wrapped for async use); structured
audit logging on every AI call.

Done when: an operator can POST a reel URL + video file, and receive back
a transcript, a list of atomic claims, and — for each verifiable claim —
an evidence matrix and verdict with confidence, all inspectable via API.

## Phase 2 — 4-slide carousel generation
Deliverables: Pillow-based slide templates (poster / original-reel /
evidence / conclusion), caption generator, `slides` table, brand
constants (`backend/app/templates/brand.py`).

Done when: a `fact_check` produces 4 rendered 1080x1350 PNGs and a
formatted caption matching the product spec's structure, from validated
evidence only.

## Phase 3 — Admin approval dashboard
Deliverables: Next.js dashboard — queue view (candidate → researching →
ready for review → approved → published), fact-check detail view
(transcript, claims, sources, evidence, verdict, confidence, slide
previews, editable caption), APPROVE / EDIT / REJECT / RESEARCH AGAIN
actions; JWT auth; role-based access.

Done when: the full flow in product spec §38 (success criteria) 1-12
works end-to-end through the UI against a running backend.

## Phase 4 — Instagram publishing
Deliverables: Meta Graph API client (`backend/app/services/instagram`),
container creation, carousel assembly, publish, status polling,
`publishing_jobs` state machine, idempotency key to block double-publish,
token refresh job.

Done when: with a real Meta App + Instagram Business account + granted
permissions (see API_REQUIREMENTS.md §1), an approved fact_check publishes
as a real carousel post and the permalink is stored. Until those
credentials/approvals exist, this ships fully coded and unit-tested
against a mocked Graph API — it is contract-complete, not
credential-complete, and that gap is external to this codebase.

## Phase 5 — Automated candidate discovery
Deliverables: pollers for news RSS, Google Fact Check Claim Search API,
YouTube Data API, (optionally X API); `reels.discovery_source` populated
automatically; a "candidate" pre-stage before a human supplies the actual
Instagram media for a story that's clearly mapped to a specific viral
reel.

## Phase 6 — Automated scheduling
Deliverables: Celery Beat schedules matching product spec §32 (discovery
every 6h, research every 1h for high-priority candidates, daily
generation, `MAX_POSTS_PER_DAY` enforcement, configurable posting
windows). Operating target is `MAX_POSTS_PER_DAY = 12` (see
`docs/API_REQUIREMENTS.md` §1 for why that's a real fraction of Meta's
publish-rate budget, not a trivial margin) — until Phase 6 ships, this
number is a ceiling Human Approval Mode enforces implicitly (nothing
publishes without a reviewer clicking Approve), not something the system
paces on its own.

## Phase 7 — Analytics
Deliverables: Instagram Insights polling job → `analytics_snapshots`;
analytics dashboard (reach, impressions, engagement, follower growth,
plus internal metrics: avg research time, avg sources per claim, human
rejection rate, correction rate, verdict distribution).

## Phase 8 — Advanced virality detection
Deliverables: full weighted virality score (METHODOLOGY §10) with
cross-platform spread detection, tunable weights, and a scoring audit
trail; likely the point at which a second Search/monitoring provider is
added for cross-platform corroboration.

## Explicitly out of scope indefinitely
- Any Instagram scraping, login automation, or anti-bot bypass.
- Automatic Mode as the default (Human Approval Mode stays default; an
  operator can later opt a narrow, high-confidence claim category into
  Automatic Mode, but that is a deliberate future decision, not a Phase
  deliverable here).
- Multi-tenant SaaS auth (this is built as a single-operator tool with
  role-based *internal* users, not a product other organizations sign up
  for, unless explicitly requested later).
