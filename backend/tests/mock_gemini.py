"""Governing brief Step 11: "Do NOT consume actual Gemini quota merely
to test quota handling. Create a mock Gemini provider." This is that
mock -- a scriptable stand-in for app.services.ai.gemini_provider.GeminiProvider,
patched in at that exact import path (the same one
QuotaAwareGeminiProvider._get_delegate() imports fresh on every call, so
patching the class there is sufficient without needing to know anything
about the quota-management layer above it).

Each test scripts a sequence of behaviors -- either a real LLMCallResult
(success) or an exception to raise (failure) -- consumed one per call.
Running out of scripted behaviors raises loudly rather than silently
returning a default, so a test can never pass by accident on an
un-configured call it didn't expect."""
from app.core.exceptions import ProviderError
from app.services.ai.base import LLMCallResult


def quota_exhausted_error(message: str = "429 RESOURCE_EXHAUSTED: Quota exceeded for quota metric") -> ProviderError:
    """Matches classify_gemini_error's QUOTA_EXHAUSTED markers."""
    return ProviderError(message)


def rate_limited_error(message: str = "429 Too Many Requests: rate limit exceeded, requests per minute") -> ProviderError:
    """Matches classify_gemini_error's RATE_LIMITED markers (and
    deliberately does NOT contain any QUOTA_EXHAUSTED marker, since
    classify_gemini_error checks quota markers first)."""
    return ProviderError(message)


def transient_error(message: str = "500 Internal Server Error") -> ProviderError:
    return ProviderError(message)


def malformed_response_error(message: str = "Gemini output failed schema validation") -> ProviderError:
    return ProviderError(message)


class MockGeminiProvider:
    """Drop-in replacement for GeminiProvider, constructed with no
    arguments (matching GeminiProvider() being instantiated fresh with
    no args by QuotaAwareGeminiProvider._get_delegate())."""

    _behaviors_by_instance: dict[int, list] = {}
    _next_behaviors: list | None = None  # set via configure() before construction

    def __init__(self):
        self.call_count = 0
        self._behaviors = list(MockGeminiProvider._next_behaviors or [])

    @classmethod
    def configure(cls, behaviors: list) -> None:
        """Set the behavior sequence the NEXT constructed instance will
        use. Needed because QuotaAwareGeminiProvider constructs a fresh
        GeminiProvider() internally -- the test can't hold a reference to
        that instance ahead of time, only configure the class before the
        call happens."""
        cls._next_behaviors = behaviors

    async def structured_call(self, **kwargs) -> LLMCallResult:
        self.call_count += 1
        if not self._behaviors:
            raise AssertionError(
                "MockGeminiProvider received a call beyond its scripted behaviors -- "
                "the test did not anticipate this many real calls to Gemini."
            )
        behavior = self._behaviors.pop(0)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


def make_success_result(*, model="gemini-mock", prompt_version="mock.v1", parsed) -> LLMCallResult:
    return LLMCallResult(parsed=parsed, raw_output=parsed.model_dump(), model=model, prompt_version=prompt_version)
