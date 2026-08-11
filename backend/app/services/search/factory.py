"""Selects the configured SearchProvider (docs/CURRENT_ARCHITECTURE.md
§4/§10). Default is "duckduckgo" — no key required, matching the same
$0/no-key-required principle already applied to LLM_PROVIDER. Set
SEARCH_PROVIDER=tavily (+ SEARCH_API_KEY) for a generally more reliable,
paid alternative that fetches page content server-side instead of from
this process's own IP."""
from app.core.config import get_settings
from app.services.search.base import SearchProvider

_provider: SearchProvider | None = None


def get_search_provider() -> SearchProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.SEARCH_PROVIDER == "tavily":
            from app.services.search.tavily import TavilySearchProvider

            _provider = TavilySearchProvider()
        else:
            from app.services.search.duckduckgo import DuckDuckGoSearchProvider

            _provider = DuckDuckGoSearchProvider()
    return _provider
