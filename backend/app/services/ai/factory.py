"""Selects the configured LLMProvider (docs/ARCHITECTURE.md §4). Every
pipeline stage imports get_llm_provider from here rather than importing a
concrete provider directly, so LLM_PROVIDER is the only thing that needs
to change to swap Anthropic for a local, free, unrestricted Ollama model
or back."""
from app.core.config import get_settings
from app.services.ai.base import LLMProvider

_provider: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    global _provider
    if _provider is None:
        settings = get_settings()
        if settings.LLM_PROVIDER == "ollama":
            from app.services.ai.ollama_provider import OllamaProvider

            _provider = OllamaProvider()
        else:
            from app.services.ai.anthropic_provider import AnthropicProvider

            _provider = AnthropicProvider()
    return _provider
