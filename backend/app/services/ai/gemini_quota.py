"""Centralized Gemini call path (research/RESEARCH_ROADMAP_V2.md Phase 0
finding, Phase 1 fix).

Before this module existed, Gemini was called from two independent
places with no shared state: `FallbackLLMProvider` (factory.py, on a
primary-provider connection failure) and five separate per-stage
"quality retry" call sites, each doing `GeminiProvider()` directly. A
daily-quota-exhausted 429 was retried identically to a transient 5xx
(tenacity, 3 attempts, seconds of backoff) with no cooldown and no
memory of the exhaustion across calls -- confirmed live in the Phase-0
audit and directly contradicts the governing brief's explicit
"do not retry repeatedly, do not block the project, persist the task,
continue everything else" requirement.

Every Gemini call now goes through `get_gemini_provider()`, which
returns the single `QuotaAwareGeminiProvider` instance for this process.
It:

1. Classifies every failure as QUOTA_EXHAUSTED / RATE_LIMITED /
   TRANSIENT / PERMANENT (`classify_gemini_error`).
2. Persists one `GeminiTask` row per call attempt -- durable, so
   "what's pending" and "are we in cooldown" both survive a process
   restart, not just an in-memory flag.
3. Enforces GEMINI_ENABLED, GEMINI_MAX_CALLS_PER_RUN,
   GEMINI_MAX_CALLS_PER_ITEM, and cooldown-after-quota-exhaustion
   *before* attempting a call, not just after one fails.
4. Caches by input_hash (model + prompt_version + system_prompt +
   user_content + images) so an identical call is never repeated.
5. Raises `GeminiUnavailableError` (a `ProviderError` subclass) when it
   declines to call Gemini at all -- callers catch this specifically to
   fall back to their existing local result and keep going, rather than
   letting a bare `ProviderError` propagate and crash the whole
   pipeline stage (the exact failure mode this module replaces).
"""
import hashlib
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.core.logging import get_logger
from app.db.models import GeminiTask, GeminiTaskStatus
from app.services.ai.base import LLMCallResult, LLMProvider, SchemaT

logger = get_logger(__name__)

# Substring match against the exception's string form -- deliberately
# loose rather than parsing a specific SDK exception hierarchy, since
# gemini_provider.py's own docstring already documents one real incident
# where the SDK raised an error type from an *undocumented internal
# module* that didn't match the documented one. Matching on the message
# text Google actually returns is more robust to that kind of surprise
# than depending on a specific class again.
_QUOTA_EXHAUSTED_MARKERS = (
    "resource_exhausted",
    "quota exceeded",
    "daily quota",
    "quota_exceeded",
)
_RATE_LIMITED_MARKERS = (
    "rate limit",
    "requests per minute",
    "429",
)


class GeminiErrorCategory:
    QUOTA_EXHAUSTED = "QUOTA_EXHAUSTED"
    RATE_LIMITED = "RATE_LIMITED"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"


def classify_gemini_error(exc: Exception) -> str:
    """Best-effort classification from the exception's own text. A
    RESOURCE_EXHAUSTED/quota message is treated as QUOTA_EXHAUSTED
    (long cooldown, per GEMINI_COOLDOWN_SECONDS) even though Gemini also
    uses 429 for simple per-minute rate limiting (short, retryable) --
    the quota-specific phrases are checked first and take priority
    specifically to avoid conflating the two, which is the exact bug
    this module exists to fix."""
    text = str(exc).lower()
    if any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS):
        return GeminiErrorCategory.QUOTA_EXHAUSTED
    if any(marker in text for marker in _RATE_LIMITED_MARKERS):
        return GeminiErrorCategory.RATE_LIMITED
    if any(code in text for code in ("500", "502", "503", "504", "timeout", "connection")):
        return GeminiErrorCategory.TRANSIENT
    return GeminiErrorCategory.PERMANENT


class GeminiUnavailableError(ProviderError):
    """Raised when the quota manager declines to attempt a Gemini call
    at all (disabled, cooldown active, or a call cap reached) -- distinct
    from a `ProviderError` raised after a call was actually attempted
    and failed. Callers should catch this specifically to fall back to
    their existing local-model result rather than crash."""


def _hash_input(
    *,
    model: str,
    system_prompt: str,
    user_content: str,
    prompt_version: str,
    images_b64: list[str] | None,
    output_schema_name: str,
) -> str:
    # output_schema_name guards against a same-prompt_version collision
    # across two structurally different call sites ever silently
    # returning a cached result of the wrong shape — cheap to include,
    # and a real (test-only) instance of exactly this collision was
    # caught while building this module (see the delegate-memoization
    # fix in QuotaAwareGeminiProvider._get_delegate's docstring).
    images_fingerprint = hashlib.sha256("".join(sorted(images_b64 or [])).encode()).hexdigest()[:16]
    payload = f"{model}|{prompt_version}|{output_schema_name}|{system_prompt}|{user_content}|{images_fingerprint}"
    return hashlib.sha256(payload.encode()).hexdigest()


class QuotaAwareGeminiProvider(LLMProvider):
    """Wraps the real `GeminiProvider`. Every call is gated by, and
    recorded through, `GeminiTask` rows in the database -- see module
    docstring. `_calls_this_run`/`_calls_this_item` are process-local
    counters (Step 3's "current execution" concept); cooldown state is
    read fresh from the database each time, so it survives a restart."""

    def __init__(self):
        self._calls_this_run = 0
        self._calls_by_item: dict[str, int] = {}

    def _get_delegate(self):
        # Constructed fresh on every call rather than memoized: this
        # provider is a process-lifetime singleton (get_gemini_provider()
        # below), and memoizing the delegate instance would mean a test
        # that monkeypatches `gemini_provider.GeminiProvider` after some
        # earlier test already constructed one gets silently ignored --
        # a real bug caught by this module's own test suite. The
        # constructor itself is cheap (reads settings, builds an SDK
        # client object; makes no network call).
        from app.services.ai.gemini_provider import GeminiProvider

        return GeminiProvider()

    async def _current_cooldown_until(self, db: AsyncSession) -> datetime | None:
        result = await db.execute(
            select(GeminiTask)
            .where(GeminiTask.status == GeminiTaskStatus.quota_wait)
            .order_by(GeminiTask.created_at.desc())
            .limit(1)
        )
        latest = result.scalars().first()
        if latest is None or latest.next_retry_at is None:
            return None
        return latest.next_retry_at

    async def _cached_result(
        self, db: AsyncSession, input_hash: str, output_schema: type[SchemaT]
    ) -> LLMCallResult | None:
        result = await db.execute(
            select(GeminiTask)
            .where(GeminiTask.input_hash == input_hash, GeminiTask.status == GeminiTaskStatus.completed)
            .order_by(GeminiTask.completed_at.desc())
            .limit(1)
        )
        task = result.scalars().first()
        if task is None or not task.result_json:
            return None
        cached = task.result_json
        parsed = output_schema.model_validate(cached["parsed"])
        return LLMCallResult(
            parsed=parsed,
            raw_output=cached["parsed"],
            model=cached["model"],
            prompt_version=cached["prompt_version"],
            input_tokens=cached.get("input_tokens", 0),
            output_tokens=cached.get("output_tokens", 0),
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
        db: AsyncSession | None = None,
        item_id: str | None = None,
        stage: str = "unknown",
    ) -> LLMCallResult:
        settings = get_settings()
        input_hash = _hash_input(
            model=model, system_prompt=system_prompt, user_content=user_content,
            prompt_version=prompt_version, images_b64=images_b64,
            output_schema_name=output_schema.__qualname__,
        )

        if not settings.GEMINI_ENABLED:
            raise GeminiUnavailableError("Gemini is disabled (GEMINI_ENABLED=false).")

        if self._calls_this_run >= settings.GEMINI_MAX_CALLS_PER_RUN:
            raise GeminiUnavailableError(
                f"GEMINI_MAX_CALLS_PER_RUN ({settings.GEMINI_MAX_CALLS_PER_RUN}) reached this run."
            )
        if item_id is not None and self._calls_by_item.get(item_id, 0) >= settings.GEMINI_MAX_CALLS_PER_ITEM:
            raise GeminiUnavailableError(
                f"GEMINI_MAX_CALLS_PER_ITEM ({settings.GEMINI_MAX_CALLS_PER_ITEM}) reached for item {item_id}."
            )

        if db is not None:
            cached = await self._cached_result(db, input_hash, output_schema)
            if cached is not None:
                logger.info("gemini_call_served_from_cache", stage=stage, item_id=item_id, model=model)
                return cached

            cooldown_until = await self._current_cooldown_until(db)
            if cooldown_until is not None and cooldown_until > datetime.now(timezone.utc):
                raise GeminiUnavailableError(
                    f"Gemini in cooldown until {cooldown_until.isoformat()} (quota previously exhausted)."
                )

        task = None
        if db is not None:
            task = GeminiTask(
                item_id=item_id, stage=stage, input_hash=input_hash,
                prompt_version=prompt_version, model=model,
                status=GeminiTaskStatus.running, attempt_count=1,
            )
            db.add(task)
            await db.flush()

        self._calls_this_run += 1
        if item_id is not None:
            self._calls_by_item[item_id] = self._calls_by_item.get(item_id, 0) + 1

        try:
            result = await self._get_delegate().structured_call(
                model=model, system_prompt=system_prompt, user_content=user_content,
                output_schema=output_schema, prompt_version=prompt_version,
                images_b64=images_b64, max_tokens=max_tokens,
            )
        except ProviderError as exc:
            category = classify_gemini_error(exc)
            logger.warning(
                "gemini_call_failed", stage=stage, item_id=item_id, model=model,
                category=category, error=str(exc),
            )
            if task is not None:
                task.attempt_count += 1
                task.last_error = str(exc)[:2000]
                if category == GeminiErrorCategory.QUOTA_EXHAUSTED:
                    task.status = GeminiTaskStatus.quota_wait
                    task.next_retry_at = datetime.now(timezone.utc) + timedelta(
                        seconds=settings.GEMINI_COOLDOWN_SECONDS
                    )
                elif category == GeminiErrorCategory.RATE_LIMITED:
                    task.status = GeminiTaskStatus.quota_wait
                    task.next_retry_at = datetime.now(timezone.utc) + timedelta(
                        seconds=settings.GEMINI_RETRY_BASE_SECONDS * 30
                    )
                elif task.attempt_count >= settings.GEMINI_MAX_RETRIES:
                    task.status = GeminiTaskStatus.permanent_failure
                else:
                    task.status = GeminiTaskStatus.failed
                await db.flush()
            if category in (GeminiErrorCategory.QUOTA_EXHAUSTED, GeminiErrorCategory.RATE_LIMITED):
                raise GeminiUnavailableError(f"Gemini {category.lower()}: {exc}") from exc
            raise
        else:
            if task is not None:
                task.status = GeminiTaskStatus.completed
                task.completed_at = datetime.now(timezone.utc)
                task.result_json = {
                    "parsed": json.loads(result.parsed.model_dump_json()),
                    "model": result.model,
                    "prompt_version": result.prompt_version,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                }
                await db.flush()
            return result


_gemini_provider: QuotaAwareGeminiProvider | None = None


def get_gemini_provider() -> QuotaAwareGeminiProvider:
    """The one shared instance every call site (factory.py's cascade
    fallback and every per-stage quality retry) must use instead of
    constructing `GeminiProvider()` directly -- this is what gives the
    two previously-independent Gemini call paths shared quota state."""
    global _gemini_provider
    if _gemini_provider is None:
        _gemini_provider = QuotaAwareGeminiProvider()
    return _gemini_provider


def reset_gemini_provider_for_tests() -> None:
    """Test-only: clear the singleton and its in-memory run/item
    counters between test cases."""
    global _gemini_provider
    _gemini_provider = None
