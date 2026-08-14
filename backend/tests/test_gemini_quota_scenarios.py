"""Governing brief Step 10: the seven required Gemini scenarios, tested
against the real QuotaAwareGeminiProvider (app/services/ai/gemini_quota.py)
with a scripted MockGeminiProvider standing in for the real SDK client --
no real Gemini quota is consumed by this file.

Scenario letters below match the brief's own lettering exactly (A-G)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from app.core.exceptions import ProviderError
from app.db.models import GeminiTask, GeminiTaskStatus, Platform, Reel
from app.db.session import AsyncSessionLocal
from app.schemas.vision import VisionContextResult
from app.services.ai.gemini_quota import GeminiUnavailableError, get_gemini_provider
from tests.mock_gemini import (
    MockGeminiProvider,
    make_success_result,
    quota_exhausted_error,
    rate_limited_error,
    transient_error,
)


@pytest.fixture(autouse=True)
def _patch_gemini_provider(monkeypatch):
    monkeypatch.setattr("app.services.ai.gemini_provider.GeminiProvider", MockGeminiProvider)


async def _call(db, *, item_id="scenario-item", stage="scenario-test"):
    return await get_gemini_provider().structured_call(
        model="gemini-mock",
        system_prompt="describe the image",
        user_content="frame data",
        output_schema=VisionContextResult,
        prompt_version="mock.v1",
        db=db,
        item_id=item_id,
        stage=stage,
    )


@pytest.mark.asyncio
async def test_scenario_a_gemini_succeeds():
    MockGeminiProvider.configure(
        [make_success_result(parsed=VisionContextResult(scene_description="two people talking"))]
    )
    async with AsyncSessionLocal() as db:
        result = await _call(db)
        assert result.parsed.scene_description == "two people talking"

        tasks = (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test"))).scalars().all()
        assert len(tasks) == 1
        assert tasks[0].status == GeminiTaskStatus.completed
        await db.rollback()


@pytest.mark.asyncio
async def test_scenario_b_transient_500_is_not_treated_as_quota_exhaustion():
    MockGeminiProvider.configure([transient_error()])
    async with AsyncSessionLocal() as db:
        with pytest.raises(ProviderError) as exc_info:
            await _call(db)
        # A transient failure must NOT be reclassified as
        # GeminiUnavailableError (that's reserved for quota/rate-limit
        # specifically) -- the caller should see a plain ProviderError.
        assert not isinstance(exc_info.value, GeminiUnavailableError)

        task = (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test"))).scalars().one()
        assert task.status == GeminiTaskStatus.permanent_failure  # attempt_count reached GEMINI_MAX_RETRIES
        await db.rollback()


@pytest.mark.asyncio
async def test_scenario_c_429_rate_limit_triggers_short_cooldown_not_long_one():
    MockGeminiProvider.configure([rate_limited_error()])
    async with AsyncSessionLocal() as db:
        with pytest.raises(GeminiUnavailableError):
            await _call(db)

        task = (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test"))).scalars().one()
        assert task.status == GeminiTaskStatus.quota_wait
        # Short cooldown (GEMINI_RETRY_BASE_SECONDS * 30 = 60s default),
        # not the long GEMINI_COOLDOWN_SECONDS (3600s) reserved for a
        # genuine quota exhaustion -- this is the exact distinction the
        # Phase-0 audit found missing in the pre-existing code.
        assert task.next_retry_at < datetime.now(timezone.utc) + timedelta(seconds=120)
        await db.rollback()


@pytest.mark.asyncio
async def test_scenario_d_quota_exhausted_triggers_long_cooldown():
    MockGeminiProvider.configure([quota_exhausted_error()])
    async with AsyncSessionLocal() as db:
        with pytest.raises(GeminiUnavailableError):
            await _call(db)

        task = (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test"))).scalars().one()
        assert task.status == GeminiTaskStatus.quota_wait
        # Long cooldown (GEMINI_COOLDOWN_SECONDS default 3600s) -- this is
        # the specific fix for the Phase-0 audit finding: a daily-quota
        # 429 was previously retried identically to a transient 5xx with
        # only seconds of backoff.
        assert task.next_retry_at > datetime.now(timezone.utc) + timedelta(minutes=30)
        await db.rollback()


@pytest.mark.asyncio
async def test_scenario_e_gemini_remains_unavailable_blocks_further_calls_without_attempting_them():
    MockGeminiProvider.configure([quota_exhausted_error()])
    async with AsyncSessionLocal() as db:
        with pytest.raises(GeminiUnavailableError):
            await _call(db)  # first call: genuinely attempted, exhausts quota

        # Second call: MockGeminiProvider has nothing scripted for it. If
        # QuotaAwareGeminiProvider actually attempted a real call here
        # (rather than short-circuiting on the cooldown it just recorded),
        # MockGeminiProvider would raise AssertionError, not
        # GeminiUnavailableError -- this test would then fail with the
        # WRONG exception type, which is exactly the signal that the
        # short-circuit isn't working.
        with pytest.raises(GeminiUnavailableError):
            await _call(db)

        tasks = (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test"))).scalars().all()
        # Only ONE task row -- the second call was blocked before ever
        # creating a task record for an attempt that never happened.
        assert len(tasks) == 1
        await db.rollback()


@pytest.mark.asyncio
async def test_scenario_f_local_model_succeeds_while_gemini_is_unavailable():
    """End-to-end through a real pipeline stage (vision_context.py),
    proving the actual production behavior this module exists to fix:
    when Gemini is unavailable, the pipeline keeps the local model's
    result and completes successfully rather than crashing."""
    from app.pipeline.vision_context import _looks_like_prompt_echo, analyze_vision_context
    from app.services.ai.base import LLMCallResult

    assert _looks_like_prompt_echo("") is True  # sanity check on the fixture used below

    # Force the local result to look bad enough to trigger a Gemini
    # retry, then make Gemini quota-exhausted for that retry.
    garbled_local_result = LLMCallResult(
        parsed=VisionContextResult(scene_description="", notable_entities=[]),
        raw_output={},
        model="ollama-vision-local",
        prompt_version="vision_context.v1",
    )
    MockGeminiProvider.configure([quota_exhausted_error()])

    class _GarbledLocalProvider:
        async def structured_call(self, **kwargs):
            return garbled_local_result

    import app.pipeline.vision_context as vision_context_module

    original_get_llm_provider = vision_context_module.get_llm_provider
    vision_context_module.get_llm_provider = lambda: _GarbledLocalProvider()
    try:
        async with AsyncSessionLocal() as db:
            reel = Reel(
                source_url="https://instagram.com/reel/scenario-f-test",
                platform=Platform.instagram,
                caption_text="test",
            )
            db.add(reel)
            await db.flush()

            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as tmpdir:
                frame_path = Path(tmpdir) / "frame.jpg"
                frame_path.write_bytes(b"\xff\xd8\xff\xe0fake")
                result_reel = await analyze_vision_context(db, reel, [str(frame_path)])

            # No crash, and the (empty, garbled) LOCAL result was kept --
            # this is "continue with the local result," not "fabricate a
            # Gemini result" and not "crash the whole request."
            assert result_reel.vision_context["scene_description"] == ""
            await db.rollback()
    finally:
        vision_context_module.get_llm_provider = original_get_llm_provider


@pytest.mark.asyncio
async def test_scenario_g_pending_task_resumes_once_cooldown_has_passed():
    MockGeminiProvider.configure([quota_exhausted_error()])
    async with AsyncSessionLocal() as db:
        with pytest.raises(GeminiUnavailableError):
            await _call(db)  # exhausts quota, records a quota_wait task with a future next_retry_at

        # Blocked immediately after.
        with pytest.raises(GeminiUnavailableError):
            await _call(db)

        # Simulate the cooldown having already elapsed -- directly
        # updating next_retry_at into the past, rather than actually
        # sleeping in a test.
        await db.execute(
            update(GeminiTask)
            .where(GeminiTask.stage == "scenario-test")
            .values(next_retry_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        )
        await db.flush()

        # The pending work can now resume: script a real success and
        # confirm the call actually goes through this time.
        MockGeminiProvider.configure([make_success_result(parsed=VisionContextResult(scene_description="resumed"))])
        result = await _call(db)
        assert result.parsed.scene_description == "resumed"

        tasks = (
            (await db.execute(select(GeminiTask).where(GeminiTask.stage == "scenario-test").order_by(GeminiTask.created_at)))
            .scalars()
            .all()
        )
        assert [t.status for t in tasks] == [GeminiTaskStatus.quota_wait, GeminiTaskStatus.completed]
        await db.rollback()
