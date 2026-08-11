"""DuckDuckGo search + direct page-content retrieval — the default,
keyless SearchProvider (docs/CURRENT_ARCHITECTURE.md §4/§10). This exists
specifically because the research pipeline had zero working search
backends without a paid Tavily key, which is why every fact-check came
back UNVERIFIED with an empty evidence section: not a reasoning failure,
a missing-input failure. This makes "Ollama + free web research, no paid
key at all" actually true end to end, matching the same principle already
applied to the LLM provider.

A search result's title/snippet is NOT treated as evidence on its own —
every result page is actually fetched and its main article text extracted
(via trafilatura) before being handed to evidence_analysis. Tavily remains
available and is generally more reliable when SEARCH_API_KEY is
configured (it fetches page content server-side and doesn't risk this
process's IP getting rate-limited by search engines) — this is the free
default, not a claim that it's strictly better."""
import asyncio

import httpx
import trafilatura
from ddgs import DDGS
from ddgs.exceptions import DDGSException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.services.search.base import SearchProvider, SearchResult

logger = get_logger(__name__)

_FETCH_TIMEOUT = 15
_MAX_CONTENT_CHARS = 20000
_USER_AGENT = "Mozilla/5.0 (compatible; TruthLensBot/1.0; +automated fact-checking research)"


class DuckDuckGoSearchProvider(SearchProvider):
    async def search(
        self,
        query: str,
        *,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        max_results: int = 5,
    ) -> list[SearchResult]:
        effective_query = query
        if include_domains:
            site_filter = " OR ".join(f"site:{d}" for d in include_domains)
            effective_query = f"{query} ({site_filter})"

        raw_results = await asyncio.to_thread(self._text_search, effective_query, max_results)

        results: list[SearchResult] = []
        for item in raw_results:
            url = item.get("href")
            if not url:
                continue
            if exclude_domains and any(d in url for d in exclude_domains):
                continue
            full_content = await self._fetch_page_text(url)
            snippet = item.get("body") or ""
            results.append(
                SearchResult(
                    url=url,
                    title=item.get("title"),
                    snippet=snippet,
                    # Never invent a publish date DuckDuckGo doesn't report —
                    # left None like every other unconfirmed field in this
                    # codebase (see url_downloader.py's same convention).
                    full_content=full_content or snippet,
                    published_date=None,
                    raw=item,
                )
            )
        return results

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        retry=retry_if_exception_type(DDGSException),
    )
    def _text_search(self, query: str, max_results: int) -> list[dict]:
        return DDGS().text(query, max_results=max_results)

    async def _fetch_page_text(self, url: str) -> str | None:
        """Best-effort: retrieve the actual article text so a search
        result's title/snippet is never treated as the evidence itself.
        Failure here is not fatal to the search — falls back to the
        snippet DuckDuckGo already returned, which is thinner but still
        real, never invented text."""
        try:
            async with httpx.AsyncClient(
                timeout=_FETCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": _USER_AGENT}
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("source_page_fetch_failed", url=url, error=str(exc))
            return None

        try:
            extracted = trafilatura.extract(response.text, include_comments=False, include_tables=False)
        except Exception as exc:  # noqa: BLE001 — third-party HTML parser, never let it break the search
            logger.warning("source_page_extraction_failed", url=url, error=str(exc))
            return None
        if not extracted:
            return None
        return extracted[:_MAX_CONTENT_CHARS]


_provider: SearchProvider | None = None


def get_duckduckgo_provider() -> SearchProvider:
    global _provider
    if _provider is None:
        _provider = DuckDuckGoSearchProvider()
    return _provider
