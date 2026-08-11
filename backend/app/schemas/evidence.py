import uuid

from pydantic import BaseModel

from app.schemas.common import EvidenceDirectness, EvidenceStance
from app.schemas.source import SourceOut


class EvidenceAnalysisItem(BaseModel):
    """Structured output contract for the evidence_analysis LLM stage.
    The model reads ONE claim + ONE retrieved passage and returns a stance
    — it is never shown other sources at this stage, so it cannot
    synthesize a stance from anything but the passage in front of it."""

    source_id: uuid.UUID
    stance: EvidenceStance
    explanation: str
    directness: EvidenceDirectness


class EvidenceOut(BaseModel):
    id: uuid.UUID
    claim_id: uuid.UUID
    source: SourceOut
    stance: EvidenceStance
    explanation: str
    directness: EvidenceDirectness

    model_config = {"from_attributes": True}
