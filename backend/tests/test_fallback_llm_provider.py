from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import ProviderError
from app.schemas.verdict import VerdictProposal
from app.services.ai.factory import FallbackLLMProvider


def _verdict() -> VerdictProposal:
    return VerdictProposal(
        verdict="TRUE",
        confidence=0.9,
        reasoning_summary="ok",
        cited_evidence_ids=[],
    )


def _result(model: str):
    from app.services.ai.base import LLMCallResult

    return LLMCallResult(parsed=_verdict(), raw_output={}, model=model, prompt_version="v1")


@pytest.mark.asyncio
async def test_uses_primary_result_when_primary_succeeds():
    primary = AsyncMock()
    primary.structured_call.return_value = _result("llama3.2")
    fallback = AsyncMock()

    provider = FallbackLLMProvider(primary=primary, fallback=fallback, fallback_model="gemini-flash-latest")
    result = await provider.structured_call(
        model="llama3.2", system_prompt="sys", user_content="user", output_schema=VerdictProposal, prompt_version="v1"
    )

    assert result.model == "llama3.2"
    fallback.structured_call.assert_not_called()


@pytest.mark.asyncio
async def test_falls_back_on_primary_failure_using_fallback_model_not_primarys():
    primary = AsyncMock()
    primary.structured_call.side_effect = ProviderError("llama3.2 produced garbage")
    fallback = AsyncMock()
    fallback.structured_call.return_value = _result("gemini-flash-latest")

    provider = FallbackLLMProvider(primary=primary, fallback=fallback, fallback_model="gemini-flash-latest")
    result = await provider.structured_call(
        model="llama3.2", system_prompt="sys", user_content="user", output_schema=VerdictProposal, prompt_version="v1"
    )

    assert result.model == "gemini-flash-latest"
    # The fallback provider must be called with ITS OWN model name, not
    # the primary's — "llama3.2" means nothing to Gemini.
    assert fallback.structured_call.call_args.kwargs["model"] == "gemini-flash-latest"


@pytest.mark.asyncio
async def test_raises_combined_error_when_both_primary_and_fallback_fail():
    primary = AsyncMock()
    primary.structured_call.side_effect = ProviderError("ollama down")
    fallback = AsyncMock()
    fallback.structured_call.side_effect = ProviderError("gemini also down")

    provider = FallbackLLMProvider(primary=primary, fallback=fallback, fallback_model="gemini-flash-latest")
    with pytest.raises(ProviderError, match="ollama down.*gemini also down"):
        await provider.structured_call(
            model="llama3.2",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="v1",
        )
