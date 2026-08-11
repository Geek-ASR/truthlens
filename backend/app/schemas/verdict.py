import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ConfidenceBand, ValidationStatus, VerdictLabel


class VerdictProposal(BaseModel):
    """Structured output contract for the verdict LLM stage. Must cite
    which evidence rows drove the conclusion — validated downstream by
    the deterministic anti-hallucination check
    (docs/FACT_CHECK_METHODOLOGY.md §7)."""

    verdict: VerdictLabel
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning_summary: str
    cited_evidence_ids: list[uuid.UUID]


class VerdictOut(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    verdict: VerdictLabel
    confidence: float
    confidence_band: ConfidenceBand
    reasoning_summary: str
    cited_evidence_ids: list[uuid.UUID]
    validation_status: ValidationStatus
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}
