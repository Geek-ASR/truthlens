import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.claim import ClaimOut
from app.schemas.common import FactCheckStatus, PublishingJobStatus, SlideType
from app.schemas.evidence import EvidenceOut
from app.schemas.reel import ReelOut
from app.schemas.verdict import VerdictOut


class SlideOut(BaseModel):
    id: uuid.UUID
    position: int
    slide_type: SlideType
    image_url: str
    template_version: str
    content_json: dict

    model_config = {"from_attributes": True}


class FactCheckSummary(BaseModel):
    """Row shape for the admin queue view (docs/ROADMAP.md Phase 3)."""

    id: uuid.UUID
    status: FactCheckStatus
    reel_id: uuid.UUID
    primary_claim_text: str
    verdict: str | None
    confidence: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class FactCheckDetail(BaseModel):
    """Full detail view: everything a reviewer needs to approve/edit/reject
    without leaving the page (product spec §20/§30)."""

    id: uuid.UUID
    status: FactCheckStatus
    reel: ReelOut
    primary_claim: ClaimOut
    covered_claims: list[ClaimOut]
    evidence: list[EvidenceOut]
    current_verdict: VerdictOut | None
    # The verdict actually shown on the carousel/caption, derived from
    # every covered claim (app/pipeline/overall_verdict.py) — NOT the
    # same thing as current_verdict, which is one single claim's own
    # verdict. Always prefer this field for display; current_verdict is
    # kept for claim-level traceability, not as the headline verdict.
    overall_verdict_label: str | None
    overall_verdict_reasoning: str | None
    caption_text: str | None
    methodology_note: str | None
    slides: list[SlideOut]
    review_notes: str | None
    duplicate_of_fact_check_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class FactCheckEditRequest(BaseModel):
    caption_text: str | None = None
    review_notes: str | None = None


class FactCheckApproveRequest(BaseModel):
    instagram_account_id: uuid.UUID
    review_notes: str | None = None


class FactCheckRejectRequest(BaseModel):
    review_notes: str


class PublishingJobOut(BaseModel):
    id: uuid.UUID
    status: PublishingJobStatus
    permalink: str | None
    attempt_count: int
    last_error: str | None

    model_config = {"from_attributes": True}


class CorrectionCreate(BaseModel):
    correction_reason: str
    new_evidence_source_ids: list[uuid.UUID] = []
    published_correction_note: str
