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
    # research/RESEARCH_ROADMAP_V2.md Phase 2 provenance fields. All
    # optional/nullable — unpopulated on any claim extracted before this
    # schema existed (never backfilled by guessing).
    source_modalities: list[str] | None = None
    extraction_confidence: float | None = None
    confidence_type: str | None = None
    verifiability: str | None = None
    provenance_detail: dict | None = None

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
        default=None,
        description=(
            "ONLY set this when someone in the reel actually said or displayed these exact words — "
            "a verbatim substring of the transcript (spoken) or OCR (on-screen text). Never fill this "
            "with your own paraphrase or description of an event, even if that description is itself "
            "a verbatim substring of the caption. Leave null if the claim is inferred/summarized rather "
            "than quoting a specific spoken or on-screen line."
        ),
    )
    claim_type: ClaimType
    verifiable: bool
    time_reference: str | None = None
    location: str | None = None
    entities: list[ExtractedEntity] = Field(default_factory=list)
    importance: float = Field(ge=0.0, le=1.0)
    # research/RESEARCH_ROADMAP_V2.md Phase 2. The model's own self
    # -reported confidence that this claim is a real, correctly-extracted
    # assertion (not a probability of it being TRUE — that's the verdict
    # stage's job entirely). Persisted as MODEL_CONFIDENCE
    # (Claim.confidence_type), never treated as a calibrated system
    # -level probability; see claim_extraction.py's persistence comment.
    extraction_confidence: float = Field(
        ge=0.0, le=1.0,
        description=(
            "Your own confidence that this is a real, correctly-extracted claim from the actual "
            "content (not a probability that the claim itself is true). Low for a marginal or "
            "ambiguous extraction, high for an unambiguous, clearly-stated assertion."
        ),
    )


ClaimExtractionResult.model_rebuild()
