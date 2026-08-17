from pydantic import BaseModel, Field, model_validator

from app.schemas.common import QueryType, TargetTier

_REQUIRED_QUERY_TYPES = frozenset(
    {QueryType.exact_claim, QueryType.entity_focused, QueryType.primary_source,
     QueryType.contradiction, QueryType.context_history}
)


class PlannedQuery(BaseModel):
    query_text: str
    target_tier: TargetTier
    # research/RESEARCH_ROADMAP_V2.md Phase 6 (Step 13's 5-query
    # structure). No default -- the model must classify its own query's
    # intent, matching how target_tier already works; QueryType.
    # unspecified exists only for pre-Phase-6 DB rows (migration
    # ad9d67b949f7's server_default), never a valid model output.
    query_type: QueryType
    rationale: str = Field(description="One short sentence on why this query targets this tier")


class ResearchPlan(BaseModel):
    # Step 13's 5-query structure (exact-claim, entity-focused,
    # primary-source, contradiction, context/history) -- exactly one of
    # each type, not "up to 5" as the pre-Phase-6 prompt allowed, so
    # per-query-type contribution is actually measurable claim-by-claim.
    queries: list[PlannedQuery] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def _exactly_one_of_each_required_type(self) -> "ResearchPlan":
        # A real, live-observed failure mode (not hypothetical): llama3.2
        # produced 5 schema-valid queries but duplicated primary_source
        # and dropped context_history entirely -- passes length/enum
        # validation alone, useless for a clean per-query-type
        # comparison. Raising here (a ValidationError, same as any other
        # schema failure) routes through the exact same retry/Gemini
        # -fallback path every other pipeline stage already has via
        # get_llm_provider() -- no new failure-handling code needed.
        actual_types = {q.query_type for q in self.queries}
        if actual_types != _REQUIRED_QUERY_TYPES:
            missing = _REQUIRED_QUERY_TYPES - actual_types
            extra_or_duplicated = actual_types - _REQUIRED_QUERY_TYPES
            raise ValueError(
                f"queries must cover exactly one of each required type. "
                f"Missing: {sorted(t.value for t in missing) or 'none'}. "
                f"Unexpected/duplicated: {sorted(t.value for t in extra_or_duplicated) or 'none'}."
            )
        return self
