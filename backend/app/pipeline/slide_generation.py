"""Stage 9: render the 4-slide carousel from validated, evidence-backed
content (product spec §2-5) and persist `Slide` rows."""
from datetime import datetime, timezone
from io import BytesIO

from PIL import Image

from app.db.models import FactCheck, Reel, Slide, SlideType
from app.pipeline.reel_content import ClaimTableRow, EvidenceCard, ReelFactCheckContent, SourceCitation
from app.services.storage.s3 import get_storage_client
from app.templates.slides import (
    TEMPLATE_VERSION,
    render_conclusion_slide,
    render_evidence_slide,
    render_poster_slide,
    render_reel_claims_slide,
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


def _citation_json(c: SourceCitation | None) -> dict | None:
    if c is None:
        return None
    return {"label": c.label, "url": c.url, "date_str": c.date_str, "excerpt": c.excerpt}


def _evidence_card_json(card: EvidenceCard) -> dict:
    return {
        "claim_text": card.claim_text,
        "verdict_label": card.verdict_label,
        "answer_text": card.answer_text,
        "primary_source": _citation_json(card.primary_source),
        "independent_source": _citation_json(card.independent_source),
    }


def _claim_row_json(row: ClaimTableRow) -> dict:
    return {"claim_text": row.claim_text, "verdict_label": row.verdict_label}


async def generate_slides(
    db,
    *,
    fact_check: FactCheck,
    reel: Reel,
    content: ReelFactCheckContent,
) -> list[Slide]:
    storage = get_storage_client()
    thumbnail = _load_thumbnail(reel)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%b %d, %Y")
    platform_label = _PLATFORM_LABELS.get(reel.platform.value, "Social media")
    content_label = "Post" if reel.media_type.value == "photo" else "Reel"
    key_fact = content.evidence_cards[0].answer_text[:140] if content.evidence_cards else content.why_paragraph[:140]

    renders = [
        (
            SlideType.poster,
            render_poster_slide(
                headline=content.headline,
                highlight_phrases=content.highlight_phrases,
                verdict_label=content.overall_verdict_label,
                date_str=date_str,
                platform_label=platform_label,
                creator_handle=reel.creator_handle,
                source_url=reel.source_url,
                thumbnail=thumbnail,
            ),
            {
                "headline": content.headline,
                "highlight_phrases": content.highlight_phrases,
                "verdict_label": content.overall_verdict_label,
                "date_str": date_str,
                "platform_label": platform_label,
            },
        ),
        (
            SlideType.original_reel,
            render_reel_claims_slide(
                quote=content.quote,
                speaker_name=content.speaker_name,
                key_points=content.key_points,
                creator_handle=reel.creator_handle,
                source_url=reel.source_url,
                thumbnail=thumbnail,
                content_label=content_label,
            ),
            {
                "quote": content.quote,
                "speaker_name": content.speaker_name,
                "key_points": content.key_points,
                "source_url": reel.source_url,
            },
        ),
        (
            SlideType.evidence,
            render_evidence_slide(evidence_cards=content.evidence_cards, key_fact=key_fact),
            {
                "evidence_cards": [_evidence_card_json(c) for c in content.evidence_cards],
                "key_fact": key_fact,
            },
        ),
        (
            SlideType.conclusion,
            render_conclusion_slide(
                verdict_label=content.overall_verdict_label,
                why_paragraph=content.why_paragraph,
                claim_table=content.claim_table,
                primary_sources=content.primary_sources,
                independent_sources=content.independent_sources,
                source_url=reel.source_url,
                date_str=date_str,
            ),
            {
                "verdict_label": content.overall_verdict_label,
                "why_paragraph": content.why_paragraph,
                "claim_table": [_claim_row_json(r) for r in content.claim_table],
                "primary_sources": [_citation_json(s) for s in content.primary_sources],
                "independent_sources": [_citation_json(s) for s in content.independent_sources],
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
