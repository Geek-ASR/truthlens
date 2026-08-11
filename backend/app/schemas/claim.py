import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ClaimStatus, ClaimType


class ExtractedEntity(BaseModel):
    name: str
    type: str  # person | organization | place | policy | other


class ClaimOut(BaseModel):
    id: uuid.UUID
    reel_id: uuid.UUID
    text: str
    source_quote: str | None
    claim_type: ClaimType
    verifiable: bool
    time_reference: str | None
    location: str | None
    entities: list[dict] | None
    importance: float
    status: ClaimStatus

    model_config = {"from_attributes": True}


class ClaimExtractionResult(BaseModel):
    """Structured output contract for the claim_extraction LLM stage
    (docs/ARCHITECTURE.md §4). The model must return exactly this shape —
    enforced via Anthropic tool-forced structured output, not free text
    parsing."""

    claims: list["ExtractedClaim"]


class ExtractedClaim(BaseModel):
    text: str = Field(description="The atomic claim, precisely worded, in the system's own words")
    source_quote: str | None = Field(
        default=None, description="Verbatim substring of the transcript/OCR this was derived from"
    )
    claim_type: ClaimType
    verifiable: bool
    time_reference: str | None = None
    location: str | None = None
    entities: list[ExtractedEntity] = Field(default_factory=list)
    importance: float = Field(ge=0.0, le=1.0)


ClaimExtractionResult.model_rebuild()
