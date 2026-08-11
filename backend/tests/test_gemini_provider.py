from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from google.genai import errors as genai_errors

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


def _api_error(code: int, message: str) -> genai_errors.APIError:
    return genai_errors.APIError(code, {"error": {"message": message, "status": "X"}})


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
