"""Stage 4: turn a verifiable claim into targeted search queries
(product spec §16 Model 3 "Research planning"). Emits queries only —
never a verdict; see prompts.RESEARCH_PLANNING_SYSTEM_PROMPT."""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ActorType, Claim, ClaimStatus, SearchQuery
from app.pipeline.audit import record_audit
from app.schemas.research import ResearchPlan
from app.services.ai.anthropic_provider import get_llm_provider
from app.services.ai.prompts import RESEARCH_PLANNING_PROMPT_VERSION, RESEARCH_PLANNING_SYSTEM_PROMPT


async def plan_research(db: AsyncSession, claim: Claim) -> list[SearchQuery]:
    if not claim.verifiable:
        claim.status = ClaimStatus.skipped_not_verifiable
        await db.flush()
        return []

    settings = get_settings()
    user_content = (
        f"CLAIM: {claim.text}\n"
        f"TIME REFERENCE: {claim.time_reference or 'unspecified'}\n"
        f"LOCATION: {claim.location or 'unspecified'}\n"
        f"ENTITIES: {claim.entities or []}"
    )

    provider = get_llm_provider()
    result = await provider.structured_call(
        model=settings.LLM_MODEL_RESEARCH_PLANNING,
        system_prompt=RESEARCH_PLANNING_SYSTEM_PROMPT,
        user_content=user_content,
        output_schema=ResearchPlan,
        prompt_version=RESEARCH_PLANNING_PROMPT_VERSION,
    )

    queries: list[SearchQuery] = []
    now = datetime.now(timezone.utc)
    for planned in result.parsed.queries:
        sq = SearchQuery(
            claim_id=claim.id,
            query_text=planned.query_text,
            target_tier=planned.target_tier,
            provider=settings.SEARCH_PROVIDER,
            executed_at=now,
            result_count=0,
        )
        db.add(sq)
        queries.append(sq)

    claim.status = ClaimStatus.researching
    await db.flush()

    await record_audit(
        db,
        entity_type="claim",
        entity_id=claim.id,
        actor_type=ActorType.ai_stage,
        actor=f"llm:{result.model}",
        action="research_planning",
        input_summary={"claim_text": claim.text},
        output_summary={"query_count": len(queries)},
        prompt_version=result.prompt_version,
    )
    return queries
