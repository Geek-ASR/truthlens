"""Regression coverage for a real, recurring bug: the local vision model
repeatedly produces schema-valid, non-empty output that is actually just
an echo of its own system prompt rather than a real image description.
Found across 4+ separate real reels this project (the second pilot,
item-0002, item-0004, item-0006) before this fix -- see
vision_context.py's own comment for the calibration data."""
import tempfile
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.pipeline.vision_context import _looks_like_prompt_echo, analyze_vision_context
from app.schemas.vision import VisionContextResult
from app.services.ai.base import LLMCallResult

# The exact three real garbled outputs collected this project (item-0002,
# item-0004, item-0006), used verbatim to calibrate and test the fix
# against real data, not synthetic approximations of it.
_REAL_GARBLED_EXAMPLES = [
    "Ai: AI're your description in English and Indian Reality based on this image, what is "
    "anonymity to describe itineral information about the worldwide descriptions from a picture "
    "of social media. The contextualize forenscripting as part 102nd-based humanitiescause you "
    "are not beingside: AI in your des",
    "Describe your role as an image-based on and offline in this case, Reality based upon "
    "what'outcomes forensioustering the scene or describe itinerate description of a person to "
    "beings. Describe: The contextualize social media base line outlination but notionscripts "
    "you canonbase your role sourcing inf",
    "visualization: The image-based on your description based upon this information, and what "
    "is not to describe you can'ing foreground the visualize descriptions of anytime frame a "
    "social media content in. I mean ascertainment beingside reel from base or more than 100 "
    "verify itineralism contextualizatio",
]
_REAL_GOOD_EXAMPLES = [
    "Two men are standing in front of each other with one man wearing glasses and both having beards.",
    "A man in white robes stands next to another person.",
]


@pytest.mark.parametrize("garbled", _REAL_GARBLED_EXAMPLES)
def test_real_garbled_examples_are_flagged(garbled):
    assert _looks_like_prompt_echo(garbled) is True


@pytest.mark.parametrize("good", _REAL_GOOD_EXAMPLES)
def test_real_good_examples_are_not_flagged(good):
    assert _looks_like_prompt_echo(good) is False


def test_empty_scene_description_is_flagged():
    assert _looks_like_prompt_echo("") is True
    assert _looks_like_prompt_echo("   ") is True


@pytest.mark.asyncio
async def test_garbled_output_triggers_gemini_retry(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")

    import app.pipeline.vision_context as vision_context_module
    from app.db.models import MediaType, Platform, Reel
    from app.db.session import AsyncSessionLocal

    garbled_result = LLMCallResult(
        parsed=VisionContextResult(scene_description=_REAL_GARBLED_EXAMPLES[0], notable_entities=[]),
        raw_output={},
        model="ollama-vision-test",
        prompt_version="vision_context.v1-test",
    )

    class _GarbledProvider:
        async def structured_call(self, **kwargs):
            return garbled_result

    class _FakeGeminiProvider:
        async def structured_call(self, **kwargs):
            parsed = VisionContextResult(
                scene_description="A crowd of protesters holds signs near a government building.",
                notable_entities=["protesters"],
            )
            return LLMCallResult(parsed=parsed, raw_output={}, model="gemini-test", prompt_version="vision_context.v1-test")

    monkeypatch.setattr(vision_context_module, "get_llm_provider", lambda: _GarbledProvider())
    monkeypatch.setattr("app.services.ai.gemini_provider.GeminiProvider", _FakeGeminiProvider)

    with tempfile.TemporaryDirectory() as tmpdir:
        frame_path = Path(tmpdir) / "frame.jpg"
        frame_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")

        async with AsyncSessionLocal() as db:
            reel = Reel(
                source_url="https://instagram.com/reel/vision-substantive-test",
                platform=Platform.instagram,
                media_type=MediaType.video,
            )
            db.add(reel)
            await db.flush()

            result_reel = await analyze_vision_context(db, reel, [str(frame_path)])
            await db.rollback()

    assert result_reel.vision_context["scene_description"] == "A crowd of protesters holds signs near a government building."
