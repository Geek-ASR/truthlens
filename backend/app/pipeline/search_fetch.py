"""Stage 5: execute planned search queries and archive retrieved sources.
A `Source` row is only ever created for content this system actually
fetched — never a model-generated URL or summary
(product spec §13: "never cite an article the system did not actually
retrieve/read")."""
from datetime import datetime, timezone

from dateutil import parser as date_parser
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResearchFailedError
from app.db.models import ActorType, Claim, Source
from app.pipeline.audit import record_audit
from app.pipeline.source_scoring import TIER3_FACTCHECK_DOMAINS, classify_source_tier, score_source
from app.services.search.base import SearchProvider
from app.services.storage.s3 import get_storage_client

_RESULTS_PER_QUERY = 3
_MAX_SOURCES_PER_CLAIM = 12


async def fetch_evidence_sources(
    db: AsyncSession, claim: Claim, queries: list, search_provider: SearchProvider
) -> list[Source]:
    storage = get_storage_client()
    sources: list[Source] = []
    seen_urls: set[str] = set()
    # Distinguishes "the search infrastructure itself is broken" (every
    # query errored — RESEARCH_FAILED, must never masquerade as a
    # publishable UNVERIFIED) from "search worked but genuinely turned up
    # little/nothing" (a real, honest UNVERIFIED outcome). Conflating
    # these was the actual bug behind every fact-check coming back with
    # an empty evidence section — see docs/CURRENT_ARCHITECTURE.md §10.
    queries_errored = 0

    for query in queries:
        if len(sources) >= _MAX_SOURCES_PER_CLAIM:
            break

        include_domains = (
            list(TIER3_FACTCHECK_DOMAINS.keys()) if query.target_tier.value == "tier3_factcheck" else None
        )
        try:
            results = await search_provider.search(
                query.query_text, include_domains=include_domains, max_results=_RESULTS_PER_QUERY
            )
        except Exception as exc:  # noqa: BLE001 — a single failed query must not abort the whole claim
            queries_errored += 1
            await record_audit(
                db,
                entity_type="search_query",
                entity_id=query.id,
                actor_type=ActorType.system,
                actor="search_fetch",
                action="search_failed",
                output_summary={"error": str(exc)},
            )
            continue

        query.result_count = len(results)

        for result in results:
            if result.url in seen_urls or len(sources) >= _MAX_SOURCES_PER_CLAIM:
                continue
            seen_urls.add(result.url)

            full_text = result.full_content or result.snippet
            if not full_text.strip():
                continue  # never store a source we couldn't actually retrieve content for

            publication_date = None
            if result.published_date:
                try:
                    publication_date = date_parser.parse(result.published_date)
                except (ValueError, TypeError):
                    publication_date = None

            source_type = classify_source_tier(result.url)
            reliability_score, breakdown = score_source(
                source_type=source_type, publication_date=publication_date, author=None
            )

            text_key = storage.generate_key("sources/fulltext", "txt")
            storage.put_bytes(text_key, full_text.encode("utf-8"), content_type="text/plain")

            now = datetime.now(timezone.utc)
            source = Source(
                url=result.url,
                title=result.title,
                publisher=None,
                author=None,
                publication_date=publication_date,
                retrieved_at=now,
                source_type=source_type,
                full_text_storage_key=text_key,
                relevant_passage=(result.snippet or full_text)[:2000],
                reliability_score=reliability_score,
                reliability_breakdown=breakdown,
                retrieval_query_id=query.id,
                created_at=now,
            )
            db.add(source)
            sources.append(source)

    await db.flush()

    if queries and queries_errored == len(queries):
        await record_audit(
            db,
            entity_type="claim",
            entity_id=claim.id,
            actor_type=ActorType.system,
            actor="search_fetch",
            action="research_failed",
            input_summary={"query_count": len(queries)},
            output_summary={"queries_errored": queries_errored},
        )
        raise ResearchFailedError(
            f"All {len(queries)} search queries for claim {claim.id} failed at the infrastructure "
            f"level (search provider unavailable/misconfigured) — no query actually executed."
        )

    await record_audit(
        db,
        entity_type="claim",
        entity_id=claim.id,
        actor_type=ActorType.system,
        actor="search_fetch",
        action="fetch_evidence_sources",
        input_summary={"query_count": len(queries)},
        output_summary={"source_count": len(sources)},
    )
    return sources
