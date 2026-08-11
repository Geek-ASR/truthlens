// Mirrors backend/app/schemas/*.py and backend/app/db/models.py enums.
// If these ever disagree with the backend, the backend wins — this file
// should be updated to match (see docs/DATA_MODEL.md conventions).

export type UserRole = "admin" | "reviewer" | "viewer";

export type Platform = "instagram" | "youtube" | "x" | "tiktok" | "other";

export type DiscoverySource =
  | "manual"
  | "rss"
  | "youtube"
  | "x"
  | "news"
  | "factcheck_org"
  | "tip";

export type IngestionStatus = "uploaded" | "transcribing" | "transcribed" | "failed";

export type ClaimType = "factual" | "opinion" | "prediction" | "satire" | "rhetorical";

export type ClaimStatus = "extracted" | "researching" | "researched" | "skipped_not_verifiable";

export type SourceTier =
  | "primary_government"
  | "primary_legal"
  | "primary_data"
  | "news_wire"
  | "established_news"
  | "academic"
  | "factcheck_org"
  | "other";

export type EvidenceStance = "supports" | "contradicts" | "provides_context" | "irrelevant";

export type EvidenceDirectness = "direct" | "indirect";

export type VerdictLabel =
  | "TRUE"
  | "MOSTLY_TRUE"
  | "MISLEADING"
  | "MOSTLY_FALSE"
  | "FALSE"
  | "UNVERIFIED"
  | "OUTDATED"
  | "MISSING_CONTEXT";

export type ConfidenceBand = "very_high" | "high" | "moderate" | "requires_review";

export type ValidationStatus =
  | "passed"
  | "downgraded_missing_citation"
  | "downgraded_unfetched_source"
  | "downgraded_unsupported_stat";

export type FactCheckStatus =
  | "researching"
  | "ready_for_review"
  | "approved"
  | "rejected"
  | "published"
  | "corrected"
  | "retracted";

export type SlideType = "poster" | "original_reel" | "evidence" | "conclusion";

export type PublishingJobStatus =
  | "pending"
  | "containers_created"
  | "carousel_created"
  | "publishing"
  | "published"
  | "failed";

export type InstagramAccountStatus = "active" | "expired" | "revoked";

export interface UserOut {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface ReelOut {
  id: string;
  source_url: string;
  platform: Platform;
  creator_handle: string | null;
  caption_text: string | null;
  posted_at: string | null;
  view_count: number | null;
  like_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  hashtags: string[] | null;
  thumbnail_storage_key: string | null;
  auto_fetched: boolean;
  transcript: string | null;
  transcript_segments: unknown[] | null;
  ocr_text: { frame_ts?: number; text?: string; confidence?: number }[] | null;
  discovery_source: DiscoverySource;
  ingestion_status: IngestionStatus;
  created_at: string;
}

export interface ExtractedEntity {
  name: string;
  type: string;
}

export interface ClaimOut {
  id: string;
  reel_id: string;
  text: string;
  source_quote: string | null;
  claim_type: ClaimType;
  verifiable: boolean;
  time_reference: string | null;
  location: string | null;
  entities: Record<string, unknown>[] | null;
  importance: number;
  status: ClaimStatus;
}

export interface SourceOut {
  id: string;
  url: string;
  title: string | null;
  publisher: string | null;
  author: string | null;
  publication_date: string | null;
  retrieved_at: string;
  source_type: SourceTier;
  relevant_passage: string;
  reliability_score: number;
  reliability_breakdown: Record<string, number>;
}

export interface EvidenceOut {
  id: string;
  claim_id: string;
  source: SourceOut;
  stance: EvidenceStance;
  explanation: string;
  directness: EvidenceDirectness;
}

export interface VerdictOut {
  id: string;
  claim_id: string;
  verdict: VerdictLabel;
  confidence: number;
  confidence_band: ConfidenceBand;
  reasoning_summary: string;
  cited_evidence_ids: string[];
  validation_status: ValidationStatus;
  is_current: boolean;
  created_at: string;
}

export interface SlideOut {
  id: string;
  position: number;
  slide_type: SlideType;
  image_url: string;
  template_version: string;
  content_json: Record<string, unknown>;
}

export interface FactCheckSummary {
  id: string;
  status: FactCheckStatus;
  reel_id: string;
  primary_claim_text: string;
  verdict: string | null;
  confidence: number | null;
  created_at: string;
}

export interface FactCheckDetail {
  id: string;
  status: FactCheckStatus;
  reel: ReelOut;
  primary_claim: ClaimOut;
  covered_claims: ClaimOut[];
  evidence: EvidenceOut[];
  current_verdict: VerdictOut | null;
  caption_text: string | null;
  methodology_note: string | null;
  slides: SlideOut[];
  review_notes: string | null;
  duplicate_of_fact_check_id: string | null;
}

export interface PublishingJobOut {
  id: string;
  status: PublishingJobStatus;
  permalink: string | null;
  attempt_count: number;
  last_error: string | null;
}

export interface InstagramAccountOut {
  id: string;
  ig_user_id: string;
  ig_username: string | null;
  status: InstagramAccountStatus;
}
