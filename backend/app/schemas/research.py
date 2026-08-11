from pydantic import BaseModel, Field

from app.schemas.common import TargetTier


class PlannedQuery(BaseModel):
    query_text: str
    target_tier: TargetTier
    rationale: str = Field(description="One short sentence on why this query targets this tier")


class ResearchPlan(BaseModel):
    queries: list[PlannedQuery] = Field(min_length=1, max_length=5)
