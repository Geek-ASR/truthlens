"""LLM provider interface. Every pipeline stage that calls an LLM goes
through this so the provider (and, per stage, the model) is swappable via
config rather than hardcoded (docs/ARCHITECTURE.md §4)."""
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMCallResult:
    def __init__(self, parsed: BaseModel, raw_output: dict, model: str, prompt_version: str):
        self.parsed = parsed
        self.raw_output = raw_output
        self.model = model
        self.prompt_version = prompt_version


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
    ) -> LLMCallResult:
        """Call the model and force its output to conform to
        `output_schema`. Implementations MUST NOT fall back to lenient
        free-text parsing — if the provider can't produce schema-conformant
        JSON, this should raise rather than guess."""
        raise NotImplementedError
