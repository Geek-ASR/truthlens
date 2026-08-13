"""Stage 2c: multimodal vision context. Advisory only — never cited as
evidence for a verdict (docs/DATA_MODEL.md reels.vision_context note)."""
import base64
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import ActorType, Reel
from app.pipeline.audit import record_audit
from app.schemas.vision import VisionContextResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import VISION_CONTEXT_PROMPT_VERSION, VISION_CONTEXT_SYSTEM_PROMPT

logger = get_logger(__name__)

_MAX_FRAMES_FOR_VISION = 4
_WORD_PATTERN = re.compile(r"[a-z]{3,}")
# The local vision model repeatedly (research/DAY8 improvement pass, but
# first found and documented across the second pilot, item-0002,
# item-0004, and item-0006 -- 4+ separate real reels) produces
# schema-valid, non-empty output that is really just the model echoing
# fragments of its OWN system prompt back ("Describe your role as an
# image-based on... Describe: The contextualize social media base
# line...") rather than describing the actual image. Unlike the empty
# -string bug already fixed in claim_extraction.py/evidence_analysis.py,
# this output is never empty, so a substantiveness check needs a
# different signal: how much of the output's own vocabulary is drawn
# from the prompt it was given, rather than describing new content.
# Calibrated against every real garbled/real-good example collected
# this project (not tuned to any one held-out item): real garbled
# outputs scored 0.26-0.29 on this ratio; real, coherent descriptions
# scored 0.00-0.12. Threshold set in the gap between them.
_PROMPT_ECHO_RATIO_THRESHOLD = 0.20


def _looks_like_prompt_echo(scene_description: str) -> bool:
    if not scene_description or not scene_description.strip():
        return True  # the existing empty-output case, folded into the same check
    prompt_words = set(_WORD_PATTERN.findall(VISION_CONTEXT_SYSTEM_PROMPT.lower()))
    output_words = _WORD_PATTERN.findall(scene_description.lower())
    if not output_words:
        return True
    overlap = sum(1 for w in output_words if w in prompt_words)
    return (overlap / len(output_words)) >= _PROMPT_ECHO_RATIO_THRESHOLD


async def analyze_vision_context(db: AsyncSession, reel: Reel, frame_paths: list[str]) -> Reel:
    if not frame_paths:
        return reel

    settings = get_settings()
    step = max(1, len(frame_paths) // _MAX_FRAMES_FOR_VISION)
    selected = frame_paths[::step][:_MAX_FRAMES_FOR_VISION]
    images_b64 = [base64.b64encode(open(p, "rb").read()).decode() for p in selected]

    provider = get_llm_provider()
    result = await provider.structured_call(
        model=settings.LLM_MODEL_VISION,
        system_prompt=VISION_CONTEXT_SYSTEM_PROMPT,
        user_content="Describe the visual context of these sampled frames from a social media reel.",
        output_schema=VisionContextResult,
        prompt_version=VISION_CONTEXT_PROMPT_VERSION,
        images_b64=images_b64,
    )

    if (
        settings.LLM_PROVIDER == "ollama"
        and settings.GEMINI_API_KEY
        and _looks_like_prompt_echo(result.parsed.scene_description)
    ):
        logger.warning(
            "vision_context_looks_like_prompt_echo_retrying_via_gemini",
            reel_id=str(reel.id),
            model=result.model,
        )
        from app.services.ai.gemini_provider import GeminiProvider

        retry_result = await GeminiProvider().structured_call(
            model=settings.LLM_MODEL_GEMINI_FALLBACK,
            system_prompt=VISION_CONTEXT_SYSTEM_PROMPT,
            user_content="Describe the visual context of these sampled frames from a social media reel.",
            output_schema=VisionContextResult,
            prompt_version=VISION_CONTEXT_PROMPT_VERSION,
            images_b64=images_b64,
        )
        await record_audit(
            db,
            entity_type="reel",
            entity_id=reel.id,
            actor_type=ActorType.system,
            actor="vision_context",
            action="vision_context_quality_retry",
            input_summary={"original_model": result.model},
            output_summary={"retry_model": retry_result.model},
        )
        result = retry_result

    reel.vision_context = result.parsed.model_dump()
    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.ai_stage,
        actor=f"llm:{result.model}",
        action="vision_context",
        input_summary={"frame_count": len(selected)},
        output_summary=result.raw_output,
        prompt_version=result.prompt_version,
        tokens=result.token_usage_dict(),
    )
    return reel
