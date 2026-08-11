"""Selects the configured LLMProvider (docs/ARCHITECTURE.md §4). Every
pipeline stage imports get_llm_provider from here rather than importing a
concrete provider directly, so LLM_PROVIDER is the only thing that needs
to change to swap Anthropic for a local, free, unrestricted Ollama model
or back."""
from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.services.ai.base import LLMCallResult, LLMProvider, SchemaT

logger = get_logger(__name__)


class FallbackLLMProvider(LLMProvider):
    """Tries `primary` first; on ProviderError, retries the same request
    against `fallback` (using `fallback_model` instead of the caller's
    `model`, since that name is meaningful only to `primary`). Built for
    LLM_PROVIDER="ollama" + GEMINI_API_KEY set: local/free by default,
    with a real cloud model to catch it when small-model output isn't
    good enough — observed live, not hypothetical (a real Instagram
    reel's code-switched transcript produced garbled, hallucinated claim
    text from Ollama's llama3.2 that Gemini handled correctly)."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider, fallback_model: str):
        self._primary = primary
        self._fallback = fallback
        self._fallback_model = fallback_model

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
    ) -> LLMCallResult:
        try:
            return await self._primary.structured_call(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                output_schema=output_schema,
                prompt_version=prompt_version,
                images_b64=images_b64,
                max_tokens=max_tokens,
            )
        except ProviderError as primary_exc:
            logger.warning(
                "llm_primary_failed_falling_back",
                model=model,
                fallback_model=self._fallback_model,
                prompt_version=prompt_version,
                error=str(primary_exc),
            )
            try:
                return await self._fallback.structured_call(
                    model=self._fallback_model,
                    system_prompt=system_prompt,
                    user_content=user_content,
                    output_schema=output_schema,
                    prompt_version=prompt_version,
                    images_b64=images_b64,
                    max_tokens=max_tokens,
                )
            except ProviderError as fallback_exc:
                raise ProviderError(
                    f"Both primary and fallback LLM providers failed (prompt {prompt_version}). "
                    f"Primary: {primary_exc}. Fallback: {fallback_exc}."
                ) from fallback_exc


_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.LLM_PROVIDER == "ollama":
            from app.services.ai.ollama_provider import OllamaProvider

            primary: LLMProvider = OllamaProvider()
            if settings.GEMINI_API_KEY:
                from app.services.ai.gemini_provider import GeminiProvider

                _provider = FallbackLLMProvider(
                    primary=primary,
                    fallback=GeminiProvider(),
                    fallback_model=settings.LLM_MODEL_GEMINI_FALLBACK,
                )
            else:
                _provider = primary
        elif settings.LLM_PROVIDER == "gemini":
            from app.services.ai.gemini_provider import GeminiProvider

            _provider = GeminiProvider()
        else:
            from app.services.ai.anthropic_provider import AnthropicProvider

            _provider = AnthropicProvider()
    return _provider
