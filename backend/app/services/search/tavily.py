"""Tavily search provider (docs/API_REQUIREMENTS.md §4). Returns
already-extracted page content, which becomes the archived
`sources.full_text_storage_key` payload — never a hallucinated summary."""
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.services.search.base import SearchProvider, SearchResult

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.SEARCH_API_KEY

    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[SearchResult]:
        # Missing key is a permanent misconfiguration, not a transient
        # failure — fail immediately rather than let it eat 3 retries'
        # worth of backoff per query (it will never succeed no matter how
        # many times we ask). Observed live: with SEARCH_API_KEY unset,
        # this alone accounted for most of the wall-clock time on a
        # multi-claim reel before this fix.
        if not self._api_key:
            raise ProviderError("SEARCH_API_KEY is not set; cannot execute research queries.")

        try:
            return await self._call_with_retry(
                query, include_domains=include_domains, exclude_domains=exclude_domains, max_results=max_results
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Tavily search failed for query {query!r}: {exc}") from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        # Only real transient network/HTTP failures are worth retrying —
        # anything else (auth, bad request) will just fail the same way
        # again immediately.
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def _call_with_retry(
        self,
        query: str,
        *,
        include_domains: list[str] | None,
        exclude_domains: list[str] | None,
        max_results: int,
    ) -> list[SearchResult]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "advanced",
            "include_raw_content": True,
            "max_results": max_results,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(_TAVILY_URL, json=payload)
            response.raise_for_status()

        data = response.json()
        results = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    url=item["url"],
                    title=item.get("title"),
                    snippet=item.get("content") or "",
                    full_content=item.get("raw_content") or item.get("content") or "",
                    published_date=item.get("published_date"),
                    raw=item,
                )
            )
        return results


_provider: SearchProvider | None = None


def get_search_provider() -> SearchProvider:
    global _provider
    if _provider is None:
        _provider = TavilySearchProvider()
    return _provider
