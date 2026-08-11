"""Ollama implementation of LLMProvider — runs entirely on local hardware,
no API key, no per-token cost, no vendor usage limits. Uses Ollama's
structured-outputs API (a JSON schema passed as `format`) for the same
schema-conformant contract the Anthropic provider guarantees; see
docs/ARCHITECTURE.md §4 and §8 for the reliability tradeoffs this
implies on constrained hardware.

Schema-validation failures are retried (unlike Anthropic's provider):
small local models occasionally emit an out-of-bound field on an
otherwise-correct response — observed live on real Instagram reel content
(a longer, code-switched transcript produced an out-of-range `importance`
value that a short synthetic test never triggered). Re-asking the same
real model again is cheap and free locally, and is not the same thing as
inventing data — if every attempt fails, this still raises rather than
guessing."""
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
            return await self._call_with_retry(
                model=model,
                system_prompt=system_prompt,
                user_content=user_content,
                output_schema=output_schema,
                prompt_version=prompt_version,
                images_b64=images_b64,
                max_tokens=max_tokens,
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
        except ValidationError as exc:
            raise ProviderError(
                f"Ollama output for {output_schema.__name__} ({model}) failed schema validation "
                f"after retries: {exc}"
            ) from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        # RequestError/ConnectionError = transient local-daemon connection hiccups.
        # ValidationError = the model produced syntactically valid JSON that
        # violates the schema (e.g. a field out of bounds) — a re-roll of
        # the same stochastic model often just fixes it. ResponseError
        # (bad model name, Ollama-side error) is deliberately NOT retried
        # here — it won't fix itself — and is handled by the caller.
        retry=retry_if_exception_type((ollama.RequestError, ConnectionError, ValidationError)),
    )
    async def _call_with_retry(
        self,
        *,
        model: str,
        system_prompt: str,
        user_content: str,
        output_schema: type[SchemaT],
        prompt_version: str,
        images_b64: list[str] | None,
        max_tokens: int,
    ) -> LLMCallResult:
        user_message: dict = {"role": "user", "content": user_content}
        if images_b64:
            user_message["images"] = images_b64

        response = await self._client.chat(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                user_message,
            ],
            format=output_schema.model_json_schema(),
            options={"temperature": 0.2, "num_predict": max_tokens, "repeat_penalty": 1.3},
        )

        raw_text = response.message.content or ""
        parsed = output_schema.model_validate_json(raw_text)  # ValidationError -> retried above

        return LLMCallResult(
            parsed=parsed,
            raw_output=parsed.model_dump(mode="json"),
            model=model,
            prompt_version=prompt_version,
            input_tokens=response.prompt_eval_count or 0,
            output_tokens=response.eval_count or 0,
        )
