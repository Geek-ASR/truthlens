import uuid

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ClaimStatus, ClaimType

# Local models occasionally serialize a value intended to be exactly 0.0
# or 1.0 with tiny floating-point noise (confirmed live: llama3.2
# produced importance=-2e-18 on real reel content during
# research/RESEARCH_ROADMAP_V2.md Phase 2 experimentation) -- close
# enough to a boundary that the model's actual intent is unambiguous,
# but a raw ge=0.0/le=1.0 constraint rejects it outright. Rejecting the
# WHOLE extraction over this is the worst possible recall outcome (zero
# claims), not a meaningful quality signal, so this is clamped before
# the ge/le check rather than left to fail schema validation.
_FLOAT_BOUNDARY_EPSILON = 1e-6


def _clamp_float_boundary_noise(value):
    if isinstance(value, (int, float)):
        if -_FLOAT_BOUNDARY_EPSILON <= value < 0:
            return 0.0
        if 1.0 < value <= 1.0 + _FLOAT_BOUNDARY_EPSILON:
            return 1.0
    return value


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

    @field_validator("importance", "extraction_confidence", mode="before")
    @classmethod
    def _clamp_boundary_noise(cls, value):
        return _clamp_float_boundary_noise(value)


ClaimExtractionResult.model_rebuild()
