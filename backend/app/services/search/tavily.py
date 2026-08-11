"""Tavily search provider (docs/API_REQUIREMENTS.md §4). Returns
already-extracted page content, which becomes the archived
`sources.full_text_storage_key` payload — never a hallucinated summary."""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.services.search.base import SearchProvider, SearchResult

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    def __init__(self):
        settings = get_settings()
        self._api_key = settings.SEARCH_API_KEY

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[SearchResult]:
        if not self._api_key:
            raise ProviderError("SEARCH_API_KEY is not set; cannot execute research queries.")

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
            try:
                response = await client.post(_TAVILY_URL, json=payload)
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise ProviderError(f"Tavily search failed for query {query!r}: {exc}") from exc

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
