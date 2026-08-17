"""research/RESEARCH_ROADMAP_V2.md Phase 6 (Step 13's 5-query structure).
No test coverage existed for app/schemas/research.py or
app/pipeline/research_planning.py before this change -- a real,
pre-existing gap, not made worse here."""
import pytest
from pydantic import ValidationError

from app.db.models import ClaimType, Platform, Reel, TargetTier
from app.db.models import QueryType
from app.db.session import AsyncSessionLocal
from app.pipeline.research_planning import plan_research
from app.schemas.research import PlannedQuery, ResearchPlan
from app.services.ai.base import LLMCallResult
from app.services.ai.prompts import RESEARCH_PLANNING_PROMPT_VERSION


def _planned_query(query_type: QueryType, text: str) -> PlannedQuery:
    return PlannedQuery(
        query_text=text, target_tier=TargetTier.unrestricted, query_type=query_type, rationale="test"
    )


def _full_plan() -> ResearchPlan:
    return ResearchPlan(
        queries=[
            _planned_query(QueryType.exact_claim, "exact claim query"),
            _planned_query(QueryType.entity_focused, "entity query"),
            _planned_query(QueryType.primary_source, "site:.gov query"),
            _planned_query(QueryType.contradiction, "debunked query"),
            _planned_query(QueryType.context_history, "history of query"),
        ]
    )


def test_research_plan_requires_exactly_five_queries():
    _full_plan()  # must not raise

    with pytest.raises(ValidationError):
        ResearchPlan(queries=[_planned_query(QueryType.exact_claim, "only one")])


def test_planned_query_requires_a_query_type():
    with pytest.raises(ValidationError):
        PlannedQuery(query_text="x", target_tier=TargetTier.unrestricted, rationale="test")


def test_rejects_a_plan_with_a_duplicated_and_a_missing_type():
    # Real output observed live from llama3.2 (research/RESEARCH_ROADMAP_V2.md
    # Phase 6): 5 schema-valid queries, but primary_source duplicated and
    # context_history dropped entirely -- passes length/enum checks alone,
    # useless for a clean per-query-type comparison.
    with pytest.raises(ValidationError):
        ResearchPlan(
            queries=[
                _planned_query(QueryType.exact_claim, "q1"),
                _planned_query(QueryType.entity_focused, "q2"),
                _planned_query(QueryType.primary_source, "q3"),
                _planned_query(QueryType.primary_source, "q4"),  # duplicate
                _planned_query(QueryType.contradiction, "q5"),
                # context_history missing entirely
            ]
        )


@pytest.mark.asyncio
async def test_plan_research_persists_all_five_query_types(monkeypatch):
    import app.pipeline.research_planning as research_planning_module

    plan = _full_plan()

    class _FakeProvider:
        async def structured_call(self, **kwargs):
            return LLMCallResult(parsed=plan, raw_output={}, model="test-model", prompt_version=RESEARCH_PLANNING_PROMPT_VERSION)

    monkeypatch.setattr(research_planning_module, "get_llm_provider", lambda: _FakeProvider())

    async with AsyncSessionLocal() as db:
        reel = Reel(source_url="https://instagram.com/reel/research-plan-schema-test", platform=Platform.instagram)
        db.add(reel)
        await db.flush()
        from app.db.models import Claim

        claim = Claim(reel_id=reel.id, text="A claim needing research.", claim_type=ClaimType.factual, verifiable=True)
        db.add(claim)
        await db.flush()

        queries = await plan_research(db, claim)
        await db.rollback()

    assert len(queries) == 5
    assert {q.query_type for q in queries} == {
        QueryType.exact_claim,
        QueryType.entity_focused,
        QueryType.primary_source,
        QueryType.contradiction,
        QueryType.context_history,
    }
