"""Ollama implementation of LLMProvider — runs entirely on local hardware,
no API key, no per-token cost, no vendor usage limits. Uses Ollama's
structured-outputs API (a JSON schema passed as `format`) for the same
schema-conformant contract the Anthropic provider guarantees; see
docs/ARCHITECTURE.md §4 and §8 for the reliability tradeoffs this
implies on constrained hardware."""
import ollama
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.services.ai.base import LLMCallResult, LLMProvider, SchemaT

logger = get_logger(__name__)


class OllamaProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        self._client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((ollama.RequestError, ConnectionError)),
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
    ) -> LLMCallResult:
        user_message: dict = {"role": "user", "content": user_content}
        if images_b64:
            user_message["images"] = images_b64

        try:
            response = await self._client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    user_message,
                ],
                format=output_schema.model_json_schema(),
                options={"temperature": 0.2, "num_predict": max_tokens, "repeat_penalty": 1.3},
            )
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise ProviderError(
                    f"Ollama model '{model}' is not pulled locally — run `ollama pull {model}` "
                    f"(prompt {prompt_version})"
                ) from exc
            raise ProviderError(f"Ollama call failed ({model}, prompt {prompt_version}): {exc}") from exc
        except ollama.RequestError as exc:
            raise ProviderError(
                f"Could not reach Ollama at {get_settings().OLLAMA_BASE_URL} "
                f"({model}, prompt {prompt_version}): {exc}"
            ) from exc

        raw_text = response.message.content or ""
        try:
            parsed = output_schema.model_validate_json(raw_text)
        except ValidationError as exc:
            raise ProviderError(
                f"Ollama output for {output_schema.__name__} ({model}) failed schema validation: {exc}"
            ) from exc

        return LLMCallResult(
            parsed=parsed,
            raw_output=parsed.model_dump(mode="json"),
            model=model,
            prompt_version=prompt_version,
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )
