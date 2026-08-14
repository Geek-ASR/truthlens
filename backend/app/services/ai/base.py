"""LLM provider interface. Every pipeline stage that calls an LLM goes
through this so the provider (and, per stage, the model) is swappable via
config rather than hardcoded (docs/ARCHITECTURE.md §4)."""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMCallResult:
    def __init__(
        self,
        parsed: BaseModel,
        raw_output: dict,
        model: str,
        prompt_version: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_creation_input_tokens: int = 0,
        cache_read_input_tokens: int = 0,
    ):
        self.parsed = parsed
        self.raw_output = raw_output
        self.model = model
        self.prompt_version = prompt_version
        # Real usage from the provider response — this is what
        # scripts/estimate_costs.py sums from audit_logs to answer "is this
        # actually affordable at MAX_POSTS_PER_DAY volume", instead of
        # guessing (docs/FACT_CHECK_METHODOLOGY.md's "no invented facts"
        # standard applies to our own cost accounting too).
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.cache_creation_input_tokens = cache_creation_input_tokens
        self.cache_read_input_tokens = cache_read_input_tokens

    def token_usage_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_input_tokens": self.cache_creation_input_tokens,
            "cache_read_input_tokens": self.cache_read_input_tokens,
        }


class LLMProvider(ABC):
    @abstractmethod
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
        # Gemini-quota-management-only (app/services/ai/gemini_quota.py).
        # Every provider accepts these for interface uniformity — a
        # caller doesn't need to know which concrete provider it holds —
        # but only the quota-aware Gemini provider actually uses them
        # (to persist a GeminiTask row and enforce cooldown/call caps).
        # Ollama/Anthropic implementations accept and ignore them.
        db: "AsyncSession | None" = None,
        item_id: str | None = None,
        stage: str = "unknown",
    ) -> LLMCallResult:
        """Call the model and force its output to conform to
        `output_schema`. Implementations MUST NOT fall back to lenient
        free-text parsing — if the provider can't produce schema-conformant
        JSON, this should raise rather than guess."""
        raise NotImplementedError
