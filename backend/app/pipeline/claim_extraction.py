"""Stage 3: decompose reel content into atomic claims
(docs/FACT_CHECK_METHODOLOGY.md §1, product spec §10-11)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import ActorType, Claim, ClaimStatus, Reel
from app.pipeline.audit import record_audit
from app.schemas.claim import ClaimExtractionResult, ExtractedClaim
from app.services.ai.base import LLMCallResult
from app.services.ai.factory import get_llm_provider
from app.services.ai.prompts import (
    CLAIM_EXTRACTION_PROMPT_VERSION,
    CLAIM_EXTRACTION_SYSTEM_PROMPT,
    wrap_untrusted,
)

logger = get_logger(__name__)

# Minimum share of would-be-verifiable claims that must actually be
# grounded (a real `source_quote` substring of the source text) before we
# trust the extraction. Cheap and deterministic — no extra LLM call to
# decide whether to retry. Calibrated against a real failure: on a real
# Instagram reel with a code-switched transcript, Ollama's llama3.2
# returned 8 schema-VALID claims where every single one had an empty
# source_quote — including two ("Beda", "Garak") marked verifiable that
# were really just bare words from the caption, not atomic claims. A
# ProviderError-only fallback (FallbackLLMProvider) never sees this kind
# of failure, since nothing raised — the model was just confidently wrong.
_MIN_GROUNDED_SHARE = 0.5


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _is_verifiable(extracted: ExtractedClaim) -> bool:
    return extracted.verifiable and extracted.claim_type.value == "factual"


def _extraction_looks_grounded(claims: list[ExtractedClaim], source_text: str) -> bool:
    verifiable = [c for c in claims if _is_verifiable(c)]
    if not verifiable:
        return True  # nothing downstream will act on this extraction either way
    normalized_source = _normalize(source_text)
    grounded = sum(
        1
        for c in verifiable
        if c.source_quote and c.source_quote.strip() and _normalize(c.source_quote) in normalized_source
    )
    return grounded / len(verifiable) >= _MIN_GROUNDED_SHARE


def _extraction_looks_substantive(claims: list[ExtractedClaim]) -> bool:
    """Same "schema-valid but empty" failure already guarded against in
    content_generation.py's _content_looks_complete and verdict.py's
    _reasoning_looks_substantive, found here too via live testing: on a
    real reel whose OCR text contained multiple checkable claims (a
    funding-source dispute, an "AI-generated" document assertion),
    Ollama returned two claims with claim_type=satire, verifiable=False,
    and text="" -- schema-valid (an empty string is still a str) but
    nothing for a human or the rest of the pipeline to act on. This is
    invisible to _extraction_looks_grounded above, which only ever
    evaluates verifiable claims' source_quote and is a no-op whenever
    every extracted claim comes back non-verifiable, exactly as happened
    here."""
    if not claims:
        return True  # a genuine "found nothing" result, not a failure
    return any(c.text.strip() for c in claims)


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
        # visible_text_or_graphics is on-screen TEXT the vision model
        # read off the image/frames -- the same kind of signal OCR
        # produces, just via a different mechanism, and was being
        # silently dropped here. Real gap found live: a photo post's
        # OCR stage returned nothing, but vision analysis of that exact
        # same image correctly read a specific, checkable on-screen
        # claim ("...spent ₹94 crores on advertising... in eight
        # years") into this field -- which claim_extraction never saw,
        # because only scene_description (a much vaguer, more
        # hallucination-prone general description) was ever included
        # here. Given equivalent weight to OCR text, not lumped in with
        # the "advisory" scene description.
        visible_text = reel.vision_context.get("visible_text_or_graphics")
        if visible_text:
            parts.append(f"ON-SCREEN TEXT (detected via image analysis):\n{wrap_untrusted(visible_text)}")
        scene_description = reel.vision_context.get("scene_description")
        if scene_description:
            parts.append(f"VISUAL CONTEXT (advisory, not evidence):\n{wrap_untrusted(scene_description)}")
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

    if settings.LLM_PROVIDER == "ollama" and settings.GEMINI_API_KEY and (
        not _extraction_looks_grounded(result.parsed.claims, user_content)
        or not _extraction_looks_substantive(result.parsed.claims)
    ):
        logger.warning(
            "claim_extraction_ungrounded_retrying_via_gemini",
            reel_id=str(reel.id),
            model=result.model,
            claim_count=len(result.parsed.claims),
        )
        from app.services.ai.gemini_quota import GeminiUnavailableError, get_gemini_provider

        try:
            retry_result: LLMCallResult = await get_gemini_provider().structured_call(
                model=settings.LLM_MODEL_GEMINI_FALLBACK,
                system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
                user_content=user_content,
                output_schema=ClaimExtractionResult,
                prompt_version=CLAIM_EXTRACTION_PROMPT_VERSION,
                db=db,
                item_id=str(reel.id),
                stage="claim_extraction",
            )
        except GeminiUnavailableError as exc:
            # Gemini declined (disabled/cooldown/call cap) or genuinely
            # failed with a quota/rate-limit error — keep the original
            # local result rather than crash the whole extraction; the
            # attempt is already durably recorded as a GeminiTask row by
            # get_gemini_provider(), so nothing is silently lost.
            logger.warning(
                "claim_extraction_gemini_retry_unavailable", reel_id=str(reel.id), error=str(exc)
            )
        else:
            await record_audit(
                db,
                entity_type="reel",
                entity_id=reel.id,
                actor_type=ActorType.system,
                actor="claim_extraction",
                action="claim_extraction_quality_retry",
                input_summary={"original_model": result.model, "original_claim_count": len(result.parsed.claims)},
                output_summary={
                    "retry_model": retry_result.model,
                    "retry_claim_count": len(retry_result.parsed.claims),
                },
            )
            result = retry_result

    claims: list[Claim] = []
    for extracted in result.parsed.claims:
        if not extracted.text.strip():
            # Never persist a claim record with no actual content, even
            # after the retry above -- same "don't store what we can't
            # actually use" discipline as never storing a Source row for
            # a page we couldn't fetch (search_fetch.py).
            continue
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
