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
    corrected_fact: str | None = Field(
        default=None,
        max_length=400,
        description=(
            "ONLY when verdict is not TRUE: what the evidence matrix actually shows instead of the "
            "claim, IF it establishes something specific (e.g. a different number, a different date, "
            "a different actual event) — not a restatement of the verdict. Every number/date/name here "
            "must appear in a source's passage text, same standard as reasoning_summary. Leave null if "
            "the evidence doesn't establish a specific alternative fact, rather than guessing."
        ),
    )
    context_note: str | None = Field(
        default=None,
        max_length=400,
        description=(
            "Broader context for this claim, ONLY if it is explicitly present in the evidence matrix's "
            "source passages (e.g. background a source article gives for why this is being discussed, "
            "what preceded it, or how it fits a pattern the source itself describes). Never predict, "
            "speculate, or state your own opinion about implications or consequences — leave null if no "
            "evidence source provides context, rather than inventing one."
        ),
    )


class VerdictOut(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    verdict: VerdictLabel
    confidence: float
    confidence_band: ConfidenceBand
    reasoning_summary: str
    cited_evidence_ids: list[uuid.UUID]
    corrected_fact: str | None
    context_note: str | None
    validation_status: ValidationStatus
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}
