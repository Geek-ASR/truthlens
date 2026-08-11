import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import SourceTier


class ReliabilityBreakdown(BaseModel):
    """Sub-dimension scores that deterministically combine into
    reliability_score (docs/FACT_CHECK_METHODOLOGY.md §3). The LLM assigns
    the qualitative sub-judgments; the final score is computed in code."""

    primary_source_status: float = Field(ge=0.0, le=1.0)
    author_identity: float = Field(ge=0.0, le=1.0)
    publication_reputation: float = Field(ge=0.0, le=1.0)
    evidence_transparency: float = Field(ge=0.0, le=1.0)
    recency: float = Field(ge=0.0, le=1.0)
    directness: float = Field(ge=0.0, le=1.0)
    corroboration: float = Field(ge=0.0, le=1.0)
    conflict_of_interest: float = Field(
        ge=0.0, le=1.0, description="1.0 = no conflict detected, 0.0 = strong conflict"
    )


class SourceOut(BaseModel):
    id: uuid.UUID
    url: str
    title: str | None
    publisher: str | None
    author: str | None
    publication_date: datetime | None
    retrieved_at: datetime
    source_type: SourceTier
    relevant_passage: str
    reliability_score: float
    reliability_breakdown: dict

    model_config = {"from_attributes": True}
