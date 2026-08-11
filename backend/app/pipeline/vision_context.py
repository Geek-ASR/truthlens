"""Stage 2c: multimodal vision context. Advisory only — never cited as
evidence for a verdict (docs/DATA_MODEL.md reels.vision_context note)."""
import base64

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ActorType, Reel
from app.pipeline.audit import record_audit
from app.schemas.vision import VisionContextResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import VISION_CONTEXT_PROMPT_VERSION, VISION_CONTEXT_SYSTEM_PROMPT

_MAX_FRAMES_FOR_VISION = 4


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
