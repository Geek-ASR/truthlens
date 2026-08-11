"""Stage 3: decompose reel content into atomic claims
(docs/FACT_CHECK_METHODOLOGY.md §1, product spec §10-11)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ActorType, Claim, ClaimStatus, Reel
from app.pipeline.audit import record_audit
from app.schemas.claim import ClaimExtractionResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import (
    CLAIM_EXTRACTION_PROMPT_VERSION,
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    wrap_untrusted,
)


def _build_user_content(reel: Reel) -> str:
    parts = ["Analyze the following reel content and extract atomic claims.\n"]
    if reel.transcript:
        parts.append(f"TRANSCRIPT:\n{wrap_untrusted(reel.transcript)}")
    if reel.ocr_text:
        ocr_joined = "\n".join(f"[{f['frame_ts']}s] {f['text']}" for f in reel.ocr_text)
        parts.append(f"ON-SCREEN TEXT (OCR):\n{wrap_untrusted(ocr_joined)}")
    if reel.caption_text:
        parts.append(f"POSTED CAPTION:\n{wrap_untrusted(reel.caption_text)}")
    if reel.vision_context:
        parts.append(
            f"VISUAL CONTEXT (advisory, not evidence):\n"
            f"{wrap_untrusted(reel.vision_context.get('scene_description', ''))}"
        )
    if len(parts) == 1:
        raise ValueError("Reel has no transcript, OCR text, or caption to extract claims from.")
    return "\n\n".join(parts)


async def extract_claims(db: AsyncSession, reel: Reel) -> list[Claim]:
    settings = get_settings()
    user_content = _build_user_content(reel)

    provider = get_llm_provider()
    result = await provider.structured_call(
        model=settings.LLM_MODEL_CLAIM_EXTRACTION,
        system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
        user_content=user_content,
        output_schema=ClaimExtractionResult,
        prompt_version=CLAIM_EXTRACTION_PROMPT_VERSION,
    )

    claims: list[Claim] = []
    for extracted in result.parsed.claims:
        claim = Claim(
            reel_id=reel.id,
            text=extracted.text,
            source_quote=extracted.source_quote,
            claim_type=extracted.claim_type,
            verifiable=extracted.verifiable and extracted.claim_type.value == "factual",
            time_reference=extracted.time_reference,
            location=extracted.location,
            entities=[e.model_dump() for e in extracted.entities],
            importance=extracted.importance,
            extraction_model=f"{result.model}:{result.prompt_version}",
            status=ClaimStatus.extracted,
        )
        db.add(claim)
        claims.append(claim)

    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.ai_stage,
        actor=f"llm:{result.model}",
        action="claim_extraction",
        input_summary={"content_length": len(user_content)},
        output_summary={"claim_count": len(claims)},
        prompt_version=result.prompt_version,
        tokens=result.token_usage_dict(),
    )
    return claims
