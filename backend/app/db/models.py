"""SQLAlchemy models. Literal source of truth is docs/DATA_MODEL.md —
keep the two in sync."""
import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    LargeBinary,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


# ---------------------------------------------------------------------------
# Enums (mirrors docs/DATA_MODEL.md)
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    admin = "admin"
    reviewer = "reviewer"
    viewer = "viewer"


class InstagramAccountStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


class Platform(str, enum.Enum):
    instagram = "instagram"
    youtube = "youtube"
    x = "x"
    tiktok = "tiktok"
    other = "other"


class MediaType(str, enum.Enum):
    video = "video"
    photo = "photo"


class DiscoverySource(str, enum.Enum):
    manual = "manual"
    rss = "rss"
    youtube = "youtube"
    x = "x"
    news = "news"
    factcheck_org = "factcheck_org"
    tip = "tip"


class IngestionStatus(str, enum.Enum):
    uploaded = "uploaded"
    transcribing = "transcribing"
    transcribed = "transcribed"
    failed = "failed"


class ClaimType(str, enum.Enum):
    factual = "factual"
    opinion = "opinion"
    prediction = "prediction"
    satire = "satire"
    rhetorical = "rhetorical"


class ClaimStatus(str, enum.Enum):
    extracted = "extracted"
    researching = "researching"
    researched = "researched"
    skipped_not_verifiable = "skipped_not_verifiable"
    # Every research query failed at the infrastructure level (search
    # provider down/misconfigured) — distinct from "researched" with zero
    # evidence, which is a legitimate, publishable UNVERIFIED outcome.
    # A claim in this state has no Verdict row and build_fact_check()
    # refuses to build a fact-check from it (docs/CURRENT_ARCHITECTURE.md §10).
    research_failed = "research_failed"


class SourceTier(str, enum.Enum):
    primary_government = "primary_government"
    primary_legal = "primary_legal"
    primary_data = "primary_data"
    news_wire = "news_wire"
    established_news = "established_news"
    academic = "academic"
    factcheck_org = "factcheck_org"
    other = "other"


class EvidenceStance(str, enum.Enum):
    supports = "supports"
    contradicts = "contradicts"
    provides_context = "provides_context"
    irrelevant = "irrelevant"


class EvidenceDirectness(str, enum.Enum):
    direct = "direct"
    indirect = "indirect"


class VerdictLabel(str, enum.Enum):
    TRUE = "TRUE"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    MISLEADING = "MISLEADING"
    MOSTLY_FALSE = "MOSTLY_FALSE"
    FALSE = "FALSE"
    UNVERIFIED = "UNVERIFIED"
    OUTDATED = "OUTDATED"
    MISSING_CONTEXT = "MISSING_CONTEXT"


class ConfidenceBand(str, enum.Enum):
    very_high = "very_high"
    high = "high"
    moderate = "moderate"
    requires_review = "requires_review"


class ValidationStatus(str, enum.Enum):
    passed = "passed"
    downgraded_missing_citation = "downgraded_missing_citation"
    downgraded_unfetched_source = "downgraded_unfetched_source"
    downgraded_unsupported_stat = "downgraded_unsupported_stat"
    # Added after the Day 5 validator audit (research/VALIDATOR_EVALUATION.md)
    # found 2 of 5 real false negatives were the same pattern: reasoning_
    # summary states no evidence/reliable information was found, yet the
    # verdict is a confident label other than UNVERIFIED (e.g. "the
    # evidence matrix does not provide any reliable sources... " paired
    # with FALSE at confidence 0.8). A general, keyword-based check for
    # this internal inconsistency -- not tuned to any specific test
    # item's correct answer, only to whether the model's own stated
    # reasoning logically supports its own chosen label.
    downgraded_reasoning_label_mismatch = "downgraded_reasoning_label_mismatch"
    # research/RESEARCH_ROADMAP_V2.md Phase 5 (temporal consistency,
    # app/pipeline/validation.py's Check 6): claim asserts an explicit
    # date, but every cited source with a known publication_date predates
    # it -- the "old footage presented as current" misinformation pattern.
    downgraded_temporal_mismatch = "downgraded_temporal_mismatch"
    # research/RESEARCH_ROADMAP_V2.md Phase 4 (entity consistency,
    # app/pipeline/validation.py's Check 7): none of the claim's own
    # named entities appear in a cited, non-irrelevant-stance evidence's
    # text -- the "wrong entity, wrong incident" pattern (e.g. Delhi
    # Police claim cited against a Burdwan, West Bengal police incident).
    downgraded_entity_mismatch = "downgraded_entity_mismatch"


class FactCheckStatus(str, enum.Enum):
    researching = "researching"
    ready_for_review = "ready_for_review"
    approved = "approved"
    rejected = "rejected"
    published = "published"
    corrected = "corrected"
    retracted = "retracted"


class SlideType(str, enum.Enum):
    poster = "poster"
    original_reel = "original_reel"
    evidence = "evidence"
    conclusion = "conclusion"


class PublishingJobStatus(str, enum.Enum):
    pending = "pending"
    containers_created = "containers_created"
    carousel_created = "carousel_created"
    publishing = "publishing"
    published = "published"
    failed = "failed"


class ActorType(str, enum.Enum):
    ai_stage = "ai_stage"
    human = "human"
    system = "system"


class MetricScope(str, enum.Enum):
    post = "post"
    account = "account"
    pipeline = "pipeline"


class TargetTier(str, enum.Enum):
    tier1_primary = "tier1_primary"
    tier2_secondary = "tier2_secondary"
    tier3_factcheck = "tier3_factcheck"
    unrestricted = "unrestricted"


# research/RESEARCH_ROADMAP_V2.md Phase 6 (evidence retrieval, Step 13):
# distinct from TargetTier above -- TargetTier is about SOURCE
# credibility (which domains a query should prefer), QueryType is about
# QUERY INTENT (what angle on the claim this specific query is trying to
# surface). The two are orthogonal: a "contradiction" query can still
# target tier1_primary domains. `unspecified` exists only for rows
# created before this schema existed (server_default on the migration
# that added this column) -- never assigned to a newly-planned query.
class QueryType(str, enum.Enum):
    exact_claim = "exact_claim"
    entity_focused = "entity_focused"
    primary_source = "primary_source"
    contradiction = "contradiction"
    context_history = "context_history"
    unspecified = "unspecified"


# research/RESEARCH_ROADMAP_V2.md Phase-1 finding: the live dev DB had no
# way to distinguish a reel used for ad-hoc development/manual testing
# from one that is part of a frozen, versioned benchmark — so a query
# meant to scope "the benchmark" could silently pull in arbitrary dev
# records. Every reel now carries an explicit dataset_type.
class DatasetType(str, enum.Enum):
    development = "development"
    benchmark = "benchmark"
    regression = "regression"
    synthetic = "synthetic"


# Real-content benchmark splits only (research/dataset/items.jsonl and its
# successors). Synthetic/regression cases use their own "dev"/"test"
# convention inside their own files (e.g.
# research/results/validator_synthetic_benchmark_20260814.json) and are
# never mixed with these.
class BenchmarkSplit(str, enum.Enum):
    dev = "dev"
    validation = "validation"
    test = "test"


# research/RESEARCH_ROADMAP_V2.md Phase 2/8: what modality(ies) a claim's
# text/source_quote actually came from. A claim may legitimately have more
# than one (e.g. asserted in both the transcript and on-screen text), so
# this lives on Claim as a list, never a single value forced to pick one.
class ClaimSourceModality(str, enum.Enum):
    audio = "AUDIO"
    ocr = "OCR"
    caption = "CAPTION"
    vision = "VISION"
    multimodal = "MULTIMODAL"
    cross_post = "CROSS_POST"


# Deliberately richer than the pre-existing boolean `verifiable` column
# (kept, unchanged, for backward compatibility — every existing caller
# still reads it). UNCERTAIN exists because "not verifiable" and "the
# extractor could not tell" are different claims about the world and
# collapsing them loses information the brief explicitly asked to keep.
class ClaimVerifiability(str, enum.Enum):
    verifiable = "VERIFIABLE"
    not_verifiable = "NOT_VERIFIABLE"
    uncertain = "UNCERTAIN"


# research/RESEARCH_ROADMAP_V2.md Phase 0 finding: Gemini's two
# previously-independent call sites had no shared state. Every Gemini
# call — cascade fallback or per-stage quality retry alike — now creates
# or updates exactly one GeminiTask row, giving a single, queryable
# source of truth for "is Gemini currently in cooldown" and "what's
# pending." See app/services/ai/gemini_quota.py.
class GeminiTaskStatus(str, enum.Enum):
    pending = "PENDING"
    running = "RUNNING"
    completed = "COMPLETED"
    failed = "FAILED"
    quota_wait = "QUOTA_WAIT"
    permanent_failure = "PERMANENT_FAILURE"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"), default=UserRole.reviewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InstagramAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "instagram_accounts"

    ig_user_id: Mapped[str] = mapped_column(String(64), unique=True)
    ig_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facebook_page_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    access_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_expires_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[InstagramAccountStatus] = mapped_column(
        Enum(InstagramAccountStatus, name="instagram_account_status"),
        default=InstagramAccountStatus.active,
    )


class Reel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reels"

    source_url: Mapped[str] = mapped_column(Text)
    platform: Mapped[Platform] = mapped_column(Enum(Platform, name="platform"), default=Platform.instagram)
    creator_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    view_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    like_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    share_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hashtags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    media_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_content_hash: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    # What media_storage_key actually holds — a video (the original
    # behavior) or a photo, for posts with no video stream at all (e.g. a
    # single-image or carousel Instagram post). Defaults to video so
    # existing rows, all of which predate photo support, stay correct
    # without a backfill. Drives branching in orchestrator.analyze_reel:
    # a photo has no audio to transcribe, so transcription is skipped,
    # but OCR and vision-context analysis both run on the single image.
    media_type: Mapped[MediaType] = mapped_column(Enum(MediaType, name="media_type"), default=MediaType.video)
    auto_fetched: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # media fetched via yt-dlp rather than manual upload; see docs/ARCHITECTURE.md §2a

    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_segments: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    ocr_text: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    vision_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    discovery_source: Mapped[DiscoverySource] = mapped_column(
        Enum(DiscoverySource, name="discovery_source"), default=DiscoverySource.manual
    )
    virality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Dataset scoping (research/RESEARCH_ROADMAP_V2.md Phase 1). Defaults
    # to `development` so every pre-existing row and every ordinary manual
    # upload is unambiguously NOT silently treated as benchmark data —
    # only a reel explicitly tagged `benchmark` (by the retroactive
    # backfill script or by benchmark ingestion tooling going forward)
    # counts as one. benchmark_version/benchmark_split are only meaningful
    # when dataset_type == benchmark; both null otherwise.
    dataset_type: Mapped[DatasetType] = mapped_column(
        Enum(DatasetType, name="dataset_type"), default=DatasetType.development
    )
    benchmark_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    benchmark_split: Mapped[BenchmarkSplit | None] = mapped_column(
        Enum(BenchmarkSplit, name="benchmark_split"), nullable=True
    )
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status"), default=IngestionStatus.uploaded
    )
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    claims: Mapped[list["Claim"]] = relationship(back_populates="reel", cascade="all, delete-orphan")


class Claim(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "claims"

    reel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reels.id"))
    text: Mapped[str] = mapped_column(Text)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_type: Mapped[ClaimType] = mapped_column(Enum(ClaimType, name="claim_type"))
    verifiable: Mapped[bool] = mapped_column(Boolean, default=False)
    time_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    importance: Mapped[float] = mapped_column(Float, default=0.0)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)
    extraction_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ClaimStatus] = mapped_column(
        Enum(ClaimStatus, name="claim_status"), default=ClaimStatus.extracted
    )
    # Provenance/confidence (research/RESEARCH_ROADMAP_V2.md Phase 2/8).
    # Nullable/empty-default so every pre-existing row stays valid
    # unbackfilled — these are populated going forward by
    # claim_extraction.py, never backfilled by guessing at historical rows.
    source_modalities: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # This is the extraction LLM's own self-reported confidence, asked
    # for directly in the prompt — it is NOT a calibrated probability and
    # must never be presented as one (Section IV-D/Bias-Calibration
    # discussion in research_paper/main.tex already makes this same
    # distinction for verdict confidence; extraction_confidence inherits
    # it). confidence_type exists specifically so no future caller can
    # silently start treating this as SYSTEM_CONFIDENCE (an empirically
    # calibrated, e.g. temperature-scaled, estimate) without that being a
    # deliberate, visible schema decision, not a naming accident.
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "MODEL_CONFIDENCE" today, always
    verifiability: Mapped[ClaimVerifiability | None] = mapped_column(
        Enum(ClaimVerifiability, name="claim_verifiability"), nullable=True
    )
    # Structured backward traceability (Step 4): which specific
    # transcript segment / OCR frame / vision-context field the claim's
    # source_quote was matched against, so "why did TruthLens believe
    # this claim existed" has a structured answer, not just a free-form
    # log line. Shape: {"modality": "OCR", "segment_index": 3,
    # "matched_text": "..."} or None when source_quote itself is null.
    provenance_detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    reel: Mapped["Reel"] = relationship(back_populates="claims")
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="claim", cascade="all, delete-orphan")
    verdicts: Mapped[list["Verdict"]] = relationship(back_populates="claim", cascade="all, delete-orphan")


class SearchQuery(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "search_queries"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    query_text: Mapped[str] = mapped_column(Text)
    target_tier: Mapped[TargetTier] = mapped_column(Enum(TargetTier, name="target_tier"))
    query_type: Mapped[QueryType] = mapped_column(
        Enum(QueryType, name="query_type"), server_default=QueryType.unspecified.value
    )
    provider: Mapped[str] = mapped_column(String(64))
    executed_at: Mapped[str] = mapped_column(DateTime(timezone=True))
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_response_storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)


class Source(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "sources"

    url: Mapped[str] = mapped_column(Text, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    publication_date: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[str] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[SourceTier] = mapped_column(Enum(SourceTier, name="source_tier"))
    full_text_storage_key: Mapped[str] = mapped_column(Text)
    relevant_passage: Mapped[str] = mapped_column(Text)
    reliability_score: Mapped[float] = mapped_column(Float)
    reliability_breakdown: Mapped[dict] = mapped_column(JSONB)
    retrieval_query_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("search_queries.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="source")


class Evidence(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evidence"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"))
    stance: Mapped[EvidenceStance] = mapped_column(Enum(EvidenceStance, name="evidence_stance"))
    explanation: Mapped[str] = mapped_column(Text)
    directness: Mapped[EvidenceDirectness] = mapped_column(Enum(EvidenceDirectness, name="evidence_directness"))
    analysis_model: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))

    claim: Mapped["Claim"] = relationship(back_populates="evidence")
    source: Mapped["Source"] = relationship(back_populates="evidence")


class Verdict(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "verdicts"

    claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    verdict: Mapped[VerdictLabel] = mapped_column(Enum(VerdictLabel, name="verdict_label"))
    confidence: Mapped[float] = mapped_column(Float)
    confidence_band: Mapped[ConfidenceBand] = mapped_column(Enum(ConfidenceBand, name="confidence_band"))
    reasoning_summary: Mapped[str] = mapped_column(Text)
    cited_evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)))
    # "What the evidence actually shows instead" and "broader context the
    # evidence provides" -- populated by the same verdict-proposal LLM
    # call, from the same evidence matrix, and independently
    # number-grounded by validate_verdict() the same way reasoning_summary
    # is. Null whenever the model didn't have a specific grounded
    # correction/context to offer, or whenever what it wrote failed
    # grounding -- never filled with a guess. Only meaningful (and only
    # ever displayed) when verdict != TRUE and validation_status == passed.
    corrected_fact: Mapped[str | None] = mapped_column(Text, nullable=True)
    context_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, name="validation_status"), default=ValidationStatus.passed
    )
    verdict_model: Mapped[str] = mapped_column(String(255))
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verdicts.id"), nullable=True
    )
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))

    claim: Mapped["Claim"] = relationship(back_populates="verdicts")


class FactCheck(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fact_checks"

    reel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reels.id"))
    primary_claim_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("claims.id"))
    covered_claim_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=True)
    current_verdict_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("verdicts.id"), nullable=True
    )
    status: Mapped[FactCheckStatus] = mapped_column(
        Enum(FactCheckStatus, name="fact_check_status"), default=FactCheckStatus.researching
    )
    caption_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of_fact_check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fact_checks.id"), nullable=True
    )
    public_page_published: Mapped[bool] = mapped_column(Boolean, default=False)
    # The verdict actually shown on the carousel/caption — derived from
    # ALL covered claims (app/pipeline/overall_verdict.py), which can
    # legitimately differ from current_verdict (one single claim's own
    # verdict, e.g. the primary/highest-importance claim). Storing it
    # explicitly, rather than only on the rendered slide's content_json,
    # is what keeps the dashboard and the published carousel from ever
    # disagreeing about what verdict this fact-check actually asserts —
    # a real bug found live (docs/CURRENT_ARCHITECTURE.md): the dashboard
    # showed one claim's UNVERIFIED while the carousel showed the reel's
    # overall MOSTLY_TRUE.
    overall_verdict_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    overall_verdict_reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)

    slides: Mapped[list["Slide"]] = relationship(back_populates="fact_check", cascade="all, delete-orphan")


class Slide(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "slides"

    fact_check_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fact_checks.id"))
    position: Mapped[int] = mapped_column(SmallInteger)
    slide_type: Mapped[SlideType] = mapped_column(Enum(SlideType, name="slide_type"))
    image_storage_key: Mapped[str] = mapped_column(Text)
    template_version: Mapped[str] = mapped_column(String(32))
    content_json: Mapped[dict] = mapped_column(JSONB)

    fact_check: Mapped["FactCheck"] = relationship(back_populates="slides")


class GeneratedPost(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "generated_posts"

    fact_check_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fact_checks.id"), unique=True
    )
    instagram_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instagram_accounts.id")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    approved_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    approved_at: Mapped[str] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))


class PublishingJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publishing_jobs"

    generated_post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generated_posts.id")
    )
    status: Mapped[PublishingJobStatus] = mapped_column(
        Enum(PublishingJobStatus, name="publishing_job_status"), default=PublishingJobStatus.pending
    )
    media_container_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    carousel_container_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ig_media_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    permalink: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Correction(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "corrections"

    fact_check_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("fact_checks.id"))
    previous_verdict_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verdicts.id"))
    new_verdict_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verdicts.id"))
    correction_reason: Mapped[str] = mapped_column(Text)
    new_evidence_source_ids: Mapped[list[uuid.UUID] | None] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=True
    )
    corrected_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    published_correction_note: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True))


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"

    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_type"))
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(128))
    input_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), index=True)


class AnalyticsSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "analytics_snapshots"

    fact_check_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fact_checks.id"), nullable=True
    )
    metric_scope: Mapped[MetricScope] = mapped_column(Enum(MetricScope, name="metric_scope"))
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follower_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_visits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    website_clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_metrics: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    captured_at: Mapped[str] = mapped_column(DateTime(timezone=True))


class GeminiTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The single persistent record every Gemini call creates or updates
    — see app/services/ai/gemini_quota.py. Serves three purposes at once:
    (1) a durable PENDING_GEMINI_TASK queue that survives a process
    restart, (2) the source of truth for "are we currently in cooldown"
    (derived from the most recent row with status=quota_wait), and (3) a
    same-input cache (result_json) so an identical input+prompt+model
    call is never repeated. item_id/stage are free-text rather than a
    foreign key, deliberately: a Gemini call can be scoped to a reel, a
    claim, or nothing at all (a research script), and this table must not
    force every caller to have a claims/reels row to point at."""
    __tablename__ = "gemini_tasks"

    item_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String(64), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    status: Mapped[GeminiTaskStatus] = mapped_column(
        Enum(GeminiTaskStatus, name="gemini_task_status"), default=GeminiTaskStatus.pending, index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
