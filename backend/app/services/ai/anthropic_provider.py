"""Anthropic implementation of LLMProvider. Uses forced tool-use to get
schema-conformant structured output instead of parsing free text
(docs/ARCHITECTURE.md §4: "Where possible, use structured JSON outputs")."""
import anthropic
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.services.ai.base import LLMCallResult, LLMProvider, SchemaT

logger = get_logger(__name__)

_OUTPUT_TOOL_NAME = "emit_result"


class AnthropicProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        if not settings.ANTHROPIC_API_KEY:
            logger.warning("anthropic_api_key_missing", note="AI stages will raise ProviderError until set")
        self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY or "missing")

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((anthropic.APIConnectionError, anthropic.RateLimitError)),
    )
    async def structured_call(
        self,
        *,
        model: str,
        system_prompt: str,
        user_content: str,
        output_schema: type[SchemaT],
        prompt_version: str,
        images_b64: list[str] | None = None,
        max_tokens: int = 4096,
        db=None,  # unused — Gemini-quota-management-only, see app/services/ai/base.py
        item_id: str | None = None,
        stage: str = "unknown",
    ) -> LLMCallResult:
        tool = {
            "name": _OUTPUT_TOOL_NAME,
            "description": f"Emit the result conforming to {output_schema.__name__}.",
            "input_schema": output_schema.model_json_schema(),
        }

        content: list[dict] = []
        if images_b64:
            for img in images_b64:
                content.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": img},
                    }
                )
        content.append({"type": "text", "text": user_content})

        try:
            response = await self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                tools=[tool],
                tool_choice={"type": "tool", "name": _OUTPUT_TOOL_NAME},
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.APIError as exc:
            raise ProviderError(f"Anthropic call failed ({model}, prompt {prompt_version}): {exc}") from exc

        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use_block is None:
            raise ProviderError(f"Anthropic response for {model} had no tool_use block")

        raw_output = tool_use_block.input
        try:
            parsed = output_schema.model_validate(raw_output)
        except ValidationError as exc:
            raise ProviderError(
                f"Anthropic output for {output_schema.__name__} failed schema validation: {exc}"
            ) from exc

        usage = response.usage
        return LLMCallResult(
            parsed=parsed,
            raw_output=raw_output,
            model=model,
            prompt_version=prompt_version,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
        )
