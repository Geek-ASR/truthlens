"""Integration tests against real Postgres for the RESEARCH_FAILED vs
UNVERIFIED distinction (docs/CURRENT_ARCHITECTURE.md §10). This is the
regression test for the actual bug reported: infrastructure-level
research failure (e.g. no working search backend) was silently producing
a normal-looking, publishable UNVERIFIED fact-check with an empty
evidence section — indistinguishable from a claim that was genuinely
researched and found to lack evidence."""
from datetime import datetime, timezone

import pytest

from app.core.exceptions import ResearchFailedError
from app.db.models import Claim, ClaimStatus, ClaimType, Platform, Reel, SearchQuery, TargetTier
from app.db.session import AsyncSessionLocal
from app.pipeline.orchestrator import build_reel_fact_check
from app.pipeline.search_fetch import fetch_evidence_sources
from app.services.search.base import SearchProvider, SearchResult


class _AlwaysErrorsSearchProvider(SearchProvider):
    """Every query fails at the infrastructure level — e.g. no search
    backend configured at all, or the provider is down."""

    async def search(self, query, *, include_domains=None, exclude_domains=None, max_results=5):
        raise RuntimeError("search backend unreachable")


class _SucceedsWithZeroResultsProvider(SearchProvider):
    """The search itself works fine, it just genuinely finds nothing —
    a real, legitimate "insufficient evidence" outcome, not a failure."""

    async def search(self, query, *, include_domains=None, exclude_domains=None, max_results=5):
        return []


async def _make_claim(db, *, text="A claim needing research.") -> tuple[Reel, Claim]:
    reel = Reel(source_url="https://instagram.com/reel/research-failed-test", platform=Platform.instagram)
    db.add(reel)
    await db.flush()
    claim = Claim(reel_id=reel.id, text=text, claim_type=ClaimType.factual, verifiable=True)
    db.add(claim)
    await db.flush()
    return reel, claim


async def _make_queries(db, claim: Claim, count: int = 3) -> list[SearchQuery]:
    now = datetime.now(timezone.utc)
    queries = []
    for i in range(count):
        q = SearchQuery(
            claim_id=claim.id,
            query_text=f"query {i}",
            target_tier=TargetTier.unrestricted,
            provider="test",
            executed_at=now,
            result_count=0,
        )
        db.add(q)
        queries.append(q)
    await db.flush()
    return queries


@pytest.mark.asyncio
async def test_all_queries_failing_at_infra_level_raises_research_failed_not_empty_sources():
    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        queries = await _make_queries(db, claim)

        with pytest.raises(ResearchFailedError):
            await fetch_evidence_sources(db, claim, queries, _AlwaysErrorsSearchProvider())
        await db.rollback()


@pytest.mark.asyncio
async def test_search_succeeding_with_zero_results_does_not_raise_research_failed():
    # This is the critical distinction: a search backend that actually ran
    # and genuinely found nothing must NOT be treated the same as one that
    # never ran at all. Only the latter is RESEARCH_FAILED.
    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        queries = await _make_queries(db, claim)

        sources = await fetch_evidence_sources(db, claim, queries, _SucceedsWithZeroResultsProvider())
        await db.rollback()

    assert sources == []


@pytest.mark.asyncio
async def test_partial_query_failure_does_not_raise_research_failed():
    # A mix of failing and succeeding queries is not a research failure —
    # only 100% failure at the infra level is.
    class _MixedProvider(SearchProvider):
        def __init__(self):
            self.calls = 0

        async def search(self, query, *, include_domains=None, exclude_domains=None, max_results=5):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("transient failure")
            return []

    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        queries = await _make_queries(db, claim, count=2)

        sources = await fetch_evidence_sources(db, claim, queries, _MixedProvider())
        await db.rollback()

    assert sources == []


@pytest.mark.asyncio
async def test_build_reel_fact_check_refuses_when_every_verifiable_claim_research_failed():
    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        claim.status = ClaimStatus.research_failed
        await db.flush()

        with pytest.raises(ValueError, match="[Rr]esearch failed"):
            await build_reel_fact_check(db, reel)
        await db.rollback()
