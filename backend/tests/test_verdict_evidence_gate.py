"""Integration tests against real Postgres for the "no evidence -> no
guess" gate (product spec's "EVIDENCE -> ANALYSIS -> VERDICT, never
VERDICT -> FIND EVIDENCE" principle) and basic source-retrieval hygiene
(dedup, never storing an inaccessible/empty-content source)."""
from datetime import datetime, timezone

import pytest

from app.db.models import Claim, ClaimType, Platform, Reel, SearchQuery, TargetTier, VerdictLabel
from app.db.session import AsyncSessionLocal
from app.pipeline.search_fetch import fetch_evidence_sources
from app.pipeline.verdict import propose_verdict
from app.services.search.base import SearchProvider, SearchResult


async def _make_claim(db, *, text="A claim needing research.") -> tuple[Reel, Claim]:
    reel = Reel(source_url="https://instagram.com/reel/verdict-gate-test", platform=Platform.instagram)
    db.add(reel)
    await db.flush()
    claim = Claim(reel_id=reel.id, text=text, claim_type=ClaimType.factual, verifiable=True)
    db.add(claim)
    await db.flush()
    return reel, claim


@pytest.mark.asyncio
async def test_zero_evidence_never_calls_the_llm_and_produces_unverified(monkeypatch):
    """Critical test: an empty evidence matrix must never reach the LLM to
    "ask if it's true" — it should short-circuit to UNVERIFIED
    deterministically, since there is nothing for a model to reason
    about without inventing something."""

    class _PoisonedProvider:
        async def structured_call(self, **kwargs):
            raise AssertionError("LLM must never be called when evidence_rows is empty")

    import app.pipeline.verdict as verdict_module

    monkeypatch.setattr(verdict_module, "get_llm_provider", lambda: _PoisonedProvider())

    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        verdict = await propose_verdict(db, claim, evidence_rows=[], sources=[])
        await db.rollback()

    assert verdict.verdict == VerdictLabel.UNVERIFIED
    assert verdict.confidence == 0.0
    assert verdict.cited_evidence_ids == []
    assert "no evidence" in verdict.reasoning_summary.lower()


async def _make_queries(db, claim: Claim, count: int = 1) -> list[SearchQuery]:
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
async def test_duplicate_urls_across_queries_are_not_stored_twice():
    class _DuplicateUrlProvider(SearchProvider):
        async def search(self, query, *, include_domains=None, exclude_domains=None, max_results=5):
            return [
                SearchResult(url="https://example.test/same-article", title="Same article", full_content="Real content here."),
                SearchResult(url="https://example.test/same-article", title="Same article again", full_content="Real content here."),
            ]

    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        queries = await _make_queries(db, claim, count=2)  # two queries, both return the same URL

        sources = await fetch_evidence_sources(db, claim, queries, _DuplicateUrlProvider())
        await db.rollback()

    urls = [s.url for s in sources]
    assert urls.count("https://example.test/same-article") == 1


@pytest.mark.asyncio
async def test_result_with_no_actual_content_is_never_stored_as_a_source():
    """A search result whose page couldn't actually be fetched (empty
    snippet AND empty full_content) must never become a Source row — a
    title/URL alone is not evidence (product requirement)."""

    class _EmptyContentProvider(SearchProvider):
        async def search(self, query, *, include_domains=None, exclude_domains=None, max_results=5):
            return [
                SearchResult(url="https://example.test/inaccessible", title="Looks relevant", snippet="", full_content=""),
                SearchResult(url="https://example.test/real", title="Real one", full_content="Actual retrieved text."),
            ]

    async with AsyncSessionLocal() as db:
        reel, claim = await _make_claim(db)
        queries = await _make_queries(db, claim, count=1)

        sources = await fetch_evidence_sources(db, claim, queries, _EmptyContentProvider())
        await db.rollback()

    urls = [s.url for s in sources]
    assert "https://example.test/inaccessible" not in urls
    assert "https://example.test/real" in urls
