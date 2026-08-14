import uuid

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from app.core.logging import get_logger
from app.schemas.common import ClaimStatus, ClaimType

logger = get_logger(__name__)

# Two real, distinct failure shapes observed live against llama3.2 on
# real reel content (research/RESEARCH_ROADMAP_V2.md Phase 2, EXP-009/
# EXP-010), handled differently rather than lumped into one tolerance:
#
# (1) Tiny floating-point/generation noise around a boundary the model
#     clearly meant to hit exactly (-2e-18, -1.1111111111e-06) -- close
#     enough that reporting it is silent; there's no real signal being
#     discarded, only representation noise.
#
# (2) The model genuinely writing the wrong number while still
#     expressing SOME confidence/importance judgment on roughly the
#     right kind of scale (-0.5, -1, -2, -2.3, 1.2, 4 -- all observed
#     live across EXP-009/EXP-010's real runs) -- clearly wrong as a
#     [0,1] value, but not so wild it reads as a structurally different
#     kind of error (e.g. a stray token count or index leaking into the
#     field). These are clamped to the nearer boundary too, but LOUDLY:
#     logged as a warning naming the field and the raw value, so this
#     never becomes an invisible, unmonitored data-quality problem. The
#     alternative -- rejecting the whole extraction over one confused
#     metadata field on an otherwise-real, well-formed claim -- is the
#     worst possible recall outcome (the claim text, quote, and type are
#     still perfectly usable) for a field that, per its own docstring
#     below, was never a calibrated system-level number to begin with.
#
# A value further outside PLAUSIBLE_CONFUSED_RANGE is left to fail
# validation as before -- something that far off the scale suggests a
# different, structural kind of error a blind clamp shouldn't paper over,
# and production's existing Gemini-escalation fallback (verified
# end-to-end for real in EXP-010) is the right place for that case to
# land, not a wider and wider clamp here.
_FLOAT_BOUNDARY_EPSILON = 1e-4
_PLAUSIBLE_CONFUSED_RANGE = (-10.0, 10.0)


def _clamp_float_boundary_noise(value, *, field_name: str = "value"):
    if isinstance(value, (int, float)):
        if -_FLOAT_BOUNDARY_EPSILON <= value < 0:
            return 0.0
        if 1.0 < value <= 1.0 + _FLOAT_BOUNDARY_EPSILON:
            return 1.0
        if _PLAUSIBLE_CONFUSED_RANGE[0] <= value < 0 or 1.0 < value <= _PLAUSIBLE_CONFUSED_RANGE[1]:
            clamped = 0.0 if value < 0 else 1.0
            logger.warning(
                "claim_extraction_float_field_clamped",
                field=field_name, raw_value=value, clamped_to=clamped,
            )
            return clamped
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
    def _clamp_boundary_noise(cls, value, info: ValidationInfo):
        return _clamp_float_boundary_noise(value, field_name=info.field_name)


ClaimExtractionResult.model_rebuild()
