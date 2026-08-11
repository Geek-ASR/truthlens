"""Stage 9: render the 4-slide carousel from validated content
(product spec §2-5) and persist `Slide` rows."""
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image

from app.db.models import Claim, FactCheck, Reel, Slide, SlideType, Source, Verdict
from app.schemas.content import ContentGenerationResult
from app.services.storage.s3 import get_storage_client
from app.templates.slides import (
    TEMPLATE_VERSION,
    render_conclusion_slide,
    render_evidence_slide,
    render_original_reel_slide,
    render_poster_slide,
)

_PLATFORM_LABELS = {
    "instagram": "Instagram Reel",
    "youtube": "YouTube",
    "x": "X (Twitter)",
    "tiktok": "TikTok",
    "other": "Social media",
}


def _load_thumbnail(reel: Reel) -> Image.Image | None:
    if not reel.thumbnail_storage_key:
        return None
    storage = get_storage_client()
    data = storage.get_bytes(reel.thumbnail_storage_key)
    return Image.open(BytesIO(data))


async def generate_slides(
    db,
    *,
    fact_check: FactCheck,
    claim: Claim,
    verdict: Verdict,
    reel: Reel,
    generated: ContentGenerationResult,
    caption_sources: list[Source],
) -> list[Slide]:
    storage = get_storage_client()
    thumbnail = _load_thumbnail(reel)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%b %d, %Y")
    platform_label = _PLATFORM_LABELS.get(reel.platform.value, "Social media")

    evidence_bullets = [s.publisher or s.title or s.url for s in caption_sources[:4]]

    renders = [
        (
            SlideType.poster,
            render_poster_slide(
                claim_summary=generated.slide1_claim_summary,
                verdict_label=verdict.verdict.value,
                date_str=date_str,
                platform_label=platform_label,
                thumbnail=thumbnail,
            ),
            {
                "claim_summary": generated.slide1_claim_summary,
                "verdict_label": verdict.verdict.value,
                "date_str": date_str,
                "platform_label": platform_label,
            },
        ),
        (
            SlideType.original_reel,
            render_original_reel_slide(
                creator_handle=reel.creator_handle,
                caption_excerpt=(reel.caption_text or "")[:220] or None,
                source_url=reel.source_url,
                thumbnail=thumbnail,
            ),
            {
                "creator_handle": reel.creator_handle,
                "caption_excerpt": (reel.caption_text or "")[:220],
                "source_url": reel.source_url,
            },
        ),
        (
            SlideType.evidence,
            render_evidence_slide(
                claim_text=claim.text,
                evidence_explanation=generated.slide3_evidence_explanation,
                evidence_bullets=evidence_bullets,
                key_fact=generated.slide3_key_fact,
            ),
            {
                "claim_text": claim.text,
                "evidence_explanation": generated.slide3_evidence_explanation,
                "evidence_bullets": evidence_bullets,
                "key_fact": generated.slide3_key_fact,
            },
        ),
        (
            SlideType.conclusion,
            render_conclusion_slide(
                verdict_label=verdict.verdict.value,
                conclusion_paragraph=generated.slide4_conclusion_paragraph,
            ),
            {
                "verdict_label": verdict.verdict.value,
                "conclusion_paragraph": generated.slide4_conclusion_paragraph,
            },
        ),
    ]

    slides: list[Slide] = []
    for position, (slide_type, png_bytes, content_json) in enumerate(renders, start=1):
        key = storage.generate_key(f"slides/{fact_check.id}", "png")
        storage.put_bytes(key, png_bytes, content_type="image/png")
        slide = Slide(
            fact_check_id=fact_check.id,
            position=position,
            slide_type=slide_type,
            image_storage_key=key,
            template_version=TEMPLATE_VERSION,
            content_json=content_json,
        )
        db.add(slide)
        slides.append(slide)

    await db.flush()
    return slides
