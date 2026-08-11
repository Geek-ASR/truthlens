from unittest.mock import AsyncMock

import ollama
import pytest

from app.core.exceptions import ProviderError
from app.schemas.verdict import VerdictProposal
from app.services.ai.ollama_provider import OllamaProvider


def _chat_response(content: str, *, prompt_eval_count=50, eval_count=20) -> ollama.ChatResponse:
    return ollama.ChatResponse(
        model="llama3.2",
        message=ollama.Message(role="assistant", content=content),
        prompt_eval_count=prompt_eval_count,
        eval_count=eval_count,
    )


def _valid_verdict_json() -> str:
    return VerdictProposal(
        verdict="TRUE",
        confidence=0.9,
        reasoning_summary="Evidence directly supports the claim.",
        cited_evidence_ids=["11111111-1111-1111-1111-111111111111"],
    ).model_dump_json()


@pytest.mark.asyncio
async def test_structured_call_parses_valid_response_and_maps_token_usage():
    provider = OllamaProvider()
    provider._client.chat = AsyncMock(return_value=_chat_response(_valid_verdict_json()))

    result = await provider.structured_call(
        model="llama3.2",
        system_prompt="sys",
        user_content="user",
        output_schema=VerdictProposal,
        prompt_version="verdict.v1",
    )

    assert result.parsed.verdict == "TRUE"
    assert result.input_tokens == 50
    assert result.output_tokens == 20
    # Local models have no per-token price — cache fields must stay zero,
    # not silently inherited from some other provider's accounting.
    assert result.cache_creation_input_tokens == 0
    assert result.cache_read_input_tokens == 0


@pytest.mark.asyncio
async def test_structured_call_raises_provider_error_on_schema_violation():
    provider = OllamaProvider()
    provider._client.chat = AsyncMock(return_value=_chat_response('{"verdict": "NOT_A_REAL_LABEL"}'))

    with pytest.raises(ProviderError):
        await provider.structured_call(
            model="llama3.2",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )


@pytest.mark.asyncio
async def test_structured_call_raises_helpful_error_when_model_not_pulled():
    provider = OllamaProvider()
    provider._client.chat = AsyncMock(side_effect=ollama.ResponseError("model 'x' not found", status_code=404))

    with pytest.raises(ProviderError, match="ollama pull"):
        await provider.structured_call(
            model="some-unpulled-model",
            system_prompt="sys",
            user_content="user",
            output_schema=VerdictProposal,
            prompt_version="verdict.v1",
        )


@pytest.mark.asyncio
async def test_structured_call_passes_images_through_to_the_user_message():
    provider = OllamaProvider()
    mock_chat = AsyncMock(return_value=_chat_response(_valid_verdict_json()))
    provider._client.chat = mock_chat

    await provider.structured_call(
        model="llava-phi3",
        system_prompt="sys",
        user_content="describe this",
        output_schema=VerdictProposal,
        prompt_version="v1",
        images_b64=["base64data"],
    )

    sent_messages = mock_chat.call_args.kwargs["messages"]
    user_message = next(m for m in sent_messages if m["role"] == "user")
    assert user_message["images"] == ["base64data"]
