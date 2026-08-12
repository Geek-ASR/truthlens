from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from google.genai._gaos.lib import compat_errors as gaos_errors

from app.core.exceptions import ProviderError
from app.schemas.claim import ClaimExtractionResult
from app.schemas.verdict import VerdictProposal
from app.services.ai.gemini_provider import GeminiProvider, _to_gemini_schema


@pytest.fixture(autouse=True)
def _gemini_api_key(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _interaction(output_text: str, *, status="completed", input_tokens=50, output_tokens=20, errors=None):
    return SimpleNamespace(
        status=status,
        output_text=output_text,
        usage=SimpleNamespace(total_input_tokens=input_tokens, total_output_tokens=output_tokens),
        errors=errors,
    )


def _valid_verdict_json() -> str:
    return VerdictProposal(
        verdict="TRUE",
        confidence=0.9,
        reasoning_summary="Evidence directly supports the claim.",
        cited_evidence_ids=["11111111-1111-1111-1111-111111111111"],
    ).model_dump_json()


def _api_error(status_code: int, message: str) -> gaos_errors.APIError:
    # Real gap found live: the Interactions API
    # (self._client.aio.interactions.create) raises this SEPARATE error
    # hierarchy, not google.genai.errors -- a test double built from the
    # wrong hierarchy would pass even if gemini_provider.py's except
    # clauses target the wrong classes, exactly the bug this file
    # previously had (it mocked google.genai.errors.APIError, which
    # matched an except clause written against the same wrong class,
    # giving false confidence). APIError.generate() returns the same
    # concrete subclass (RateLimitError, BadRequestError, ...) the real
    # SDK would raise for a given status code.
    request = httpx.Request("POST", "https://example.test/v1/interactions")
    response = httpx.Response(status_code, request=request)
    return gaos_errors.APIError.generate(status_code, {"error": {"message": message}}, message, response)


@pytest.mark.asyncio
async def test_structured_call_parses_valid_response_and_maps_token_usage(monkeypatch):
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(return_value=_interaction(_valid_verdict_json()))

    result = await provider.structured_call(
        model="gemini-flash-latest",
        system_prompt="sys",
        user_content="user",
        output_schema=VerdictProposal,
        prompt_version="verdict.v1",
    )

    assert result.parsed.verdict == "TRUE"
    assert result.input_tokens == 50
    assert result.output_tokens == 20


@pytest.mark.asyncio
async def test_structured_call_raises_provider_error_on_incomplete_status(monkeypatch):
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(
        return_value=_interaction("", status="failed", errors=[SimpleNamespace(message="blocked", code=None)])
    )

    with pytest.raises(ProviderError, match="blocked"):
        await provider.structured_call(
            model="gemini-flash-latest",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )


@pytest.mark.asyncio
async def test_structured_call_retries_on_retryable_status_code(monkeypatch):
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(
        side_effect=[_api_error(503, "overloaded"), _interaction(_valid_verdict_json())]
    )

    result = await provider.structured_call(
        model="gemini-flash-latest",
        system_prompt="sys",
        user_content="user",
        output_schema=VerdictProposal,
        prompt_version="verdict.v1",
    )

    assert result.parsed.verdict == "TRUE"
    assert provider._client.aio.interactions.create.await_count == 2


@pytest.mark.asyncio
async def test_structured_call_does_not_retry_permanent_client_errors(monkeypatch):
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(side_effect=_api_error(400, "bad schema"))

    with pytest.raises(ProviderError, match="bad schema"):
        await provider.structured_call(
            model="gemini-flash-latest",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )
    assert provider._client.aio.interactions.create.await_count == 1


@pytest.mark.asyncio
async def test_rate_limit_exhaustion_becomes_provider_error_not_a_crash():
    # Real bug found live against https://www.instagram.com/p/Db6Dd14Cte5/:
    # Gemini's free-tier daily quota (429, non-retryable in practice --
    # retrying immediately doesn't help) was exhausted mid-pipeline. The
    # 429 kept recurring across all 3 retry attempts, and the resulting
    # RateLimitError was never caught by the old except clauses (written
    # against the wrong error hierarchy), crashing the whole /analyze
    # request as an unhandled 500 instead of a clean ProviderError the
    # caller (verdict.py, claim_extraction.py) already knows how to
    # handle.
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(
        side_effect=_api_error(429, "quota exceeded")
    )

    with pytest.raises(ProviderError, match="quota exceeded"):
        await provider.structured_call(
            model="gemini-flash-latest",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )
    # 429 IS in _RETRYABLE_STATUS_CODES, so all 3 attempts should have
    # been used before giving up -- confirms the retry path itself (not
    # just the final failure) now runs against the real error hierarchy.
    assert provider._client.aio.interactions.create.await_count == 3


@pytest.mark.asyncio
async def test_connection_error_is_retried_then_wrapped_as_provider_error():
    # Non-status errors from this hierarchy (dropped connections,
    # timeouts) don't carry a status_code at all, so they can't be
    # checked against _RETRYABLE_STATUS_CODES the way APIStatusError
    # subclasses are -- still worth a retry rather than an immediate crash.
    request = httpx.Request("POST", "https://example.test/v1/interactions")
    provider = GeminiProvider()
    provider._client.aio.interactions.create = AsyncMock(
        side_effect=gaos_errors.APIConnectionError(message="connection reset", request=request)
    )

    with pytest.raises(ProviderError, match="connection reset"):
        await provider.structured_call(
            model="gemini-flash-latest",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )
    assert provider._client.aio.interactions.create.await_count == 3


def test_constructor_raises_when_key_missing(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        GeminiProvider()


def test_to_gemini_schema_inlines_refs_and_strips_null_branches():
    converted = _to_gemini_schema(ClaimExtractionResult.model_json_schema())
    assert "$defs" not in converted
    claim_item_schema = converted["properties"]["claims"]["items"]
    assert "$ref" not in str(claim_item_schema)
    # claim_type was a $ref to an enum def — must be inlined with its enum values.
    assert claim_item_schema["properties"]["claim_type"]["enum"] == [
        "factual",
        "opinion",
        "prediction",
        "satire",
        "rhetorical",
    ]
    # source_quote was Optional[str] (anyOf [string, null]) — null branch dropped.
    assert claim_item_schema["properties"]["source_quote"]["type"] == "string"
    # nested $ref'd model (ExtractedEntity) must be fully inlined too.
    assert claim_item_schema["properties"]["entities"]["items"]["properties"]["name"]["type"] == "string"
