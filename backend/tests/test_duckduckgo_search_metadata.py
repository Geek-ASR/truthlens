"""research/RESEARCH_ROADMAP_V2.md Phase 5 precondition check: confirmed
live that Source.publication_date was 0/223 filled across every real
source ever fetched -- traced to DuckDuckGoSearchProvider (the default,
keyless SEARCH_PROVIDER) hardcoding published_date=None unconditionally,
even though the page it already fetches for full_content usually carries
a real date in its own metadata (confirmed live against 2 real fact
-check articles: both recovered exactly). trafilatura.extract_metadata()
runs against the same already-fetched HTML the text extraction already
uses -- no second network call, no new dependency (trafilatura is
already a project dependency for exactly this fetch step).

These tests use real trafilatura calls against literal HTML fixtures
(deterministic, local, no network) -- only the httpx fetch itself is
mocked, via monkeypatching httpx.AsyncClient.get directly (this project
has no respx/httpx-mock dependency; matches the direct-method-patch
style already used in tests/test_gemini_provider.py)."""
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.search.duckduckgo import DuckDuckGoSearchProvider

_HTML_WITH_DATE = """<html><head>
<meta property="article:published_time" content="2026-05-06T10:00:00+00:00">
<title>Test Article</title>
</head><body><article><p>Some real article text that is long enough to be
extracted by trafilatura for this test to actually exercise the
extraction path meaningfully rather than being trivially empty.</p>
</article></body></html>"""

_HTML_WITHOUT_DATE = """<html><head><title>No date</title></head><body>
<article><p>Some real article text with no date metadata anywhere in this
page at all, deliberately, to confirm nothing gets invented.</p></article>
</body></html>"""


def _mock_response(html: str, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", "https://example.test/article")
    return httpx.Response(status_code, request=request, text=html)


@pytest.mark.asyncio
async def test_fetch_page_text_and_date_recovers_a_real_publication_date(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_mock_response(_HTML_WITH_DATE)))
    provider = DuckDuckGoSearchProvider()

    text, published_date = await provider._fetch_page_text_and_date("https://example.test/article")

    assert "real article text" in text
    assert published_date == "2026-05-06"


@pytest.mark.asyncio
async def test_fetch_page_text_and_date_stays_none_when_page_has_no_date(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_mock_response(_HTML_WITHOUT_DATE)))
    provider = DuckDuckGoSearchProvider()

    text, published_date = await provider._fetch_page_text_and_date("https://example.test/nodate")

    assert "no date metadata" in text
    assert published_date is None


@pytest.mark.asyncio
async def test_fetch_page_text_and_date_returns_none_none_on_fetch_failure(monkeypatch):
    async def _raise(*args, **kwargs):
        raise httpx.ConnectTimeout("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", _raise)
    provider = DuckDuckGoSearchProvider()

    text, published_date = await provider._fetch_page_text_and_date("https://example.test/unreachable")

    assert text is None
    assert published_date is None


@pytest.mark.asyncio
async def test_search_wires_the_recovered_date_into_search_result(monkeypatch):
    monkeypatch.setattr(httpx.AsyncClient, "get", AsyncMock(return_value=_mock_response(_HTML_WITH_DATE)))

    class _StubDDGS:
        def text(self, query, max_results):
            return [{"href": "https://example.test/article", "title": "Test", "body": "snippet"}]

    provider = DuckDuckGoSearchProvider()
    monkeypatch.setattr(provider, "_text_search", lambda query, max_results: _StubDDGS().text(query, max_results))

    results = await provider.search("test query")

    assert len(results) == 1
    assert results[0].published_date == "2026-05-06"
