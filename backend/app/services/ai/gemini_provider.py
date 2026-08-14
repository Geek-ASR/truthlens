"""Google Gemini implementation of LLMProvider. Used as an automatic
fallback when the local Ollama provider fails (see FallbackLLMProvider in
factory.py) — for real-world content the small local model just isn't
reliable enough on. Observed live: Ollama's llama3.2 produced garbled,
hallucinated claim text on a real, longer, code-switched (Hindi/English)
Instagram reel transcript, something a short English synthetic test never
surfaced.

Uses the `google-genai` SDK's Interactions API — the older `generateContent`
REST endpoint returns 404 ("no longer available to new users") for API keys
created around Aug 2026, so this deliberately does NOT hand-roll REST calls
against that endpoint. Structured output goes through `response_format`'s
JSON schema (an OpenAPI-3.0-flavored SUBSET of JSON Schema: no $ref/$defs,
only a few `format` values recognized) — _to_gemini_schema() converts a
Pydantic model_json_schema() output into that shape."""
from google import genai

# The Interactions API used below (self._client.aio.interactions.create)
# raises a SEPARATE error hierarchy from the documented google.genai.errors
# module — its own APIError/RateLimitError etc. are not subclasses of
# google.genai.errors.APIError (confirmed live:
# issubclass(RateLimitError, errors.APIError) is False). There is no
# public re-export of these types anywhere under google.genai; this
# internal module is the only place they exist. Found live: a real
# Gemini 429 (daily free-tier quota exhausted) raised
# google.genai._gaos.lib.compat_errors.RateLimitError, which an except
# clause written against google.genai.errors.APIError never matched,
# crashing the whole /analyze request as an unhandled 500 instead of
# degrading to the already-computed local-model result.
from google.genai._gaos.lib import compat_errors as gaos_errors
from pydantic import ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.services.ai.base import LLMCallResult, LLMProvider, SchemaT

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_SUPPORTED_STRING_FORMATS = {"date-time", "date", "time"}


class _RetryableAPIError(Exception):
    pass


def _to_gemini_schema(schema: dict) -> dict:
    defs = schema.get("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                ref_name = node["$ref"].rsplit("/", 1)[-1]
                return resolve(defs[ref_name])

            out = {}
            # anyOf: [{type: X}, {type: "null"}] is Pydantic's Optional[X]
            # encoding — Gemini's schema has no null type, so collapse it
            # to the non-null branch (the field just becomes non-required
            # in practice, since Optional fields aren't in `required`).
            if "anyOf" in node:
                branches = [b for b in node["anyOf"] if b.get("type") != "null"]
                if len(branches) == 1:
                    resolved = resolve(branches[0])
                    for k in ("description", "title"):
                        if k in node and k not in resolved:
                            resolved[k] = node[k]
                    return resolved
                out["anyOf"] = [resolve(b) for b in branches]

            for key, value in node.items():
                if key in ("$ref", "anyOf", "$defs", "default"):
                    continue
                if key == "format":
                    if value in _SUPPORTED_STRING_FORMATS:
                        out[key] = value
                    continue
                if key == "properties":
                    out[key] = {k: resolve(v) for k, v in value.items()}
                elif key == "items":
                    out[key] = resolve(value)
                elif key not in out:
                    out[key] = value
            return out
        return node

    return resolve({k: v for k, v in schema.items() if k != "$defs"})


class GeminiProvider(LLMProvider):
    def __init__(self):
        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            raise ProviderError("GEMINI_API_KEY is not set; cannot use the Gemini provider.")
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

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
        db=None,  # unused here — this is the raw provider; app/services/ai/gemini_quota.py's
        item_id: str | None = None,  # QuotaAwareGeminiProvider wraps this class and is what
        stage: str = "unknown",  # actually persists/enforces quota using these three.
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
        except _RetryableAPIError as exc:
            raise ProviderError(
                f"Gemini call failed after retries ({model}, prompt {prompt_version}): {exc}"
            ) from exc
        except gaos_errors.GeminiNextGenAPIClientError as exc:
            raise ProviderError(
                f"Gemini call failed ({model}, prompt {prompt_version}): "
                f"{getattr(exc, 'status_code', None)} {exc}"
            ) from exc
        except ValidationError as exc:
            raise ProviderError(
                f"Gemini output for {output_schema.__name__} ({model}) failed schema validation "
                f"after retries: {exc}"
            ) from exc

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type((_RetryableAPIError, ValidationError)),
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
        input_content: list[dict] = []
        if images_b64:
            for img in images_b64:
                input_content.append({"type": "image", "mime_type": "image/jpeg", "data": img})
        input_content.append({"type": "text", "text": user_content})

        try:
            interaction = await self._client.aio.interactions.create(
                model=model,
                input=input_content,
                system_instruction=system_prompt,
                # NOTE: do not also pass a top-level response_mime_type here —
                # empirically, setting both it and response_format together
                # raises "responseFormat must be set when responseMimeType is
                # set" even though response_format IS set. response_format's
                # own nested mime_type is sufficient.
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": _to_gemini_schema(output_schema.model_json_schema()),
                },
                generation_config={"max_output_tokens": max_tokens},
                store=False,
            )
        except gaos_errors.GeminiNextGenAPIClientError as exc:
            # APIConnectionError/APITimeoutError are ALSO APIError
            # subclasses but never got an HTTP response at all, so
            # status_code stays at APIError's class-level default of
            # None -- treated as retryable too (a dropped connection is
            # exactly the kind of transient failure worth one retry
            # pass), not just the explicit 429/5xx status codes.
            status_code = getattr(exc, "status_code", None)
            if status_code is None or status_code in _RETRYABLE_STATUS_CODES:
                raise _RetryableAPIError(f"{status_code} {exc}") from exc
            raise

        if interaction.status != "completed":
            error_detail = "; ".join(
                (e.message or e.code or "") for e in (interaction.errors or [])
            )
            raise ProviderError(
                f"Gemini interaction did not complete (status={interaction.status}, {model}, "
                f"prompt {prompt_version}): {error_detail}"
            )

        parsed = output_schema.model_validate_json(interaction.output_text or "")  # ValidationError -> retried above

        usage = interaction.usage
        return LLMCallResult(
            parsed=parsed,
            raw_output=parsed.model_dump(mode="json"),
            model=model,
            prompt_version=prompt_version,
            input_tokens=(usage.total_input_tokens if usage else 0) or 0,
            output_tokens=(usage.total_output_tokens if usage else 0) or 0,
        )
