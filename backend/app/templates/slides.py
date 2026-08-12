"""Deterministic Pillow renderers for the 4-slide carousel (product spec
§2-5, §22). Same input JSON always produces the same pixels — no
generative image model involved, so a slide can be regenerated exactly
after a caption/text edit (docs/DATA_MODEL.md slides.content_json).

Redesigned for evidence density: real per-claim evidence cards with
primary/independent source citations, a claim-by-claim table, and a real
source list — assembled from app/pipeline/reel_content.py's structured
ReelFactCheckContent rather than one free-text blob per slide."""
from PIL import Image, ImageDraw

from app.pipeline.reel_content import EvidenceCard, ReelFactCheckContent, SourceCitation
from app.templates.brand import (
    ACCENT,
    ACCENT_LIGHT,
    BORDER,
    CANVAS_SIZE,
    CARD_BG,
    HIGHLIGHT,
    INDEPENDENT_SOURCE_TAG,
    INK,
    MUTED,
    PAPER,
    PRIMARY_SOURCE_TAG,
    TAG_BG,
    VERDICT_COLORS,
    font_bold,
    font_regular,
)
from app.templates.render_utils import cover_resize, draw_wrapped_text, draw_wrapped_text_with_highlights, to_png_bytes

TEMPLATE_VERSION = "slides.v2"

_W, _H = CANVAS_SIZE
_MARGIN = 56


def _base_canvas(bg=PAPER) -> Image.Image:
    return Image.new("RGB", CANVAS_SIZE, bg)


def _draw_wordmark(draw: ImageDraw.ImageDraw, xy: tuple[int, int], color: str = INK, subtitle_color=None) -> None:
    x, y = xy
    draw.text((x, y), "TRUTHLENS", font=font_bold(30), fill=color)
    draw.text((x, y + 34), "FACT CHECK", font=font_bold(18), fill=subtitle_color or color)


def _pill(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, bg: str, fg: str, font_size: int = 22) -> tuple[int, int]:
    font = font_bold(font_size)
    x, y = xy
    text_w = draw.textlength(text, font=font)
    pad_x, pad_y = 18, 10
    box = (x, y, x + text_w + pad_x * 2, y + font.size + pad_y * 2)
    draw.rounded_rectangle(box, radius=8, fill=bg)
    draw.text((x + pad_x, y + pad_y - 2), text, font=font, fill=fg)
    return int(box[2]), int(box[3])


def _verdict_badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], verdict_label: str, font_size: int = 38) -> tuple[int, int]:
    color = VERDICT_COLORS.get(verdict_label, MUTED)
    label = verdict_label.replace("_", " ")
    return _pill(draw, xy, label, color, PAPER, font_size)


def _with_dark_overlay(image: Image.Image, opacity: int = 150) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (10, 12, 12, opacity))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _icon_badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], icon: str, color: str, size: int = 40) -> None:
    x, y = xy
    draw.ellipse((x, y, x + size, y + size), fill=color)
    font = font_bold(int(size * 0.55))
    tw = draw.textlength(icon, font=font)
    draw.text((x + (size - tw) / 2, y + size * 0.18), icon, font=font, fill=PAPER)


# ---------------------------------------------------------------------------
# Slide 1 — poster
# ---------------------------------------------------------------------------

def render_poster_slide(
    *,
    headline: str,
    highlight_phrases: list[str],
    verdict_label: str,
    date_str: str,
    platform_label: str,
    creator_handle: str | None,
    source_url: str,
    thumbnail: Image.Image | None,
) -> bytes:
    if thumbnail is not None:
        canvas = cover_resize(thumbnail.convert("RGB"), CANVAS_SIZE)
        canvas = _with_dark_overlay(canvas, opacity=175)
    else:
        canvas = _base_canvas(bg=INK)
    draw = ImageDraw.Draw(canvas)

    _draw_wordmark(draw, (_MARGIN, 50), color=PAPER, subtitle_color=ACCENT_LIGHT)
    _pill(draw, (_MARGIN, 130), "VIRAL CLAIM", TAG_BG, PAPER, font_size=20)

    draw_wrapped_text_with_highlights(
        draw,
        (_MARGIN, 200),
        headline,
        highlight_phrases,
        font_bold(52),
        _W - 2 * _MARGIN,
        PAPER,
        HIGHLIGHT,
        line_spacing=10,
        max_lines=6,
    )

    _verdict_badge(draw, (_MARGIN, _H - 260), verdict_label)
    handle_text = f"@{creator_handle}" if creator_handle else "creator handle not provided"
    draw.text((_MARGIN, _H - 165), f"{handle_text} · {platform_label}", font=font_regular(24), fill=ACCENT_LIGHT)
    draw.text((_MARGIN, _H - 130), f"Posted {date_str}", font=font_regular(22), fill=MUTED)
    draw.text((_MARGIN, _H - 95), "Independent fact-check · not affiliated with the platform or creator",
               font=font_regular(18), fill=MUTED)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 2 — what the reel claims
# ---------------------------------------------------------------------------

def render_reel_claims_slide(
    *,
    quote: str | None,
    speaker_name: str | None,
    key_points: list[str],
    creator_handle: str | None,
    source_url: str,
    thumbnail: Image.Image | None,
    content_label: str = "Reel",
) -> bytes:
    canvas = _base_canvas()
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, 44), f"WHAT THE {content_label.upper()} CLAIMS", font=font_bold(38), fill=INK)
    y = 110

    if quote:
        quote_box_h = 210
        draw.rounded_rectangle((_MARGIN, y, _W - _MARGIN, y + quote_box_h), radius=14, fill=CARD_BG, outline=BORDER)
        draw.text((_MARGIN + 24, y + 16), "“", font=font_bold(56), fill=ACCENT)
        draw_wrapped_text(
            draw, (_MARGIN + 24, y + 70), quote, font_regular(28), _W - 2 * _MARGIN - 48, INK,
            line_spacing=8, max_lines=4,
        )
        if speaker_name:
            draw.text((_MARGIN + 24, y + quote_box_h - 42), f"— {speaker_name}", font=font_bold(24), fill=ACCENT)
        y += quote_box_h + 30

    if thumbnail is not None:
        thumb_h = 260
        thumb = cover_resize(thumbnail.convert("RGB"), (_W - 2 * _MARGIN, thumb_h))
        canvas.paste(thumb, (_MARGIN, y))
        draw.rectangle((_MARGIN, y + thumb_h - 40, _W - _MARGIN, y + thumb_h), fill=(10, 12, 12))
        handle_text = f"@{creator_handle}" if creator_handle else f"Original {content_label.lower()}"
        draw.text((_MARGIN + 14, y + thumb_h - 32), handle_text, font=font_bold(20), fill=PAPER)
        y += thumb_h + 30

    draw.text((_MARGIN, y), f"KEY POINTS FROM THE {content_label.upper()}", font=font_bold(24), fill=ACCENT)
    y += 40
    remaining_h = _H - 170 - y
    max_points = max(1, min(len(key_points), remaining_h // 60))
    for point in key_points[:max_points]:
        draw.ellipse((_MARGIN, y + 10, _MARGIN + 10, y + 20), fill=ACCENT)
        y = draw_wrapped_text(
            draw, (_MARGIN + 26, y), point, font_regular(24), _W - 2 * _MARGIN - 26, INK,
            max_lines=2,
        )
        y += 14

    draw.rectangle((0, _H - 100, _W, _H), fill=CARD_BG)
    draw.text((_MARGIN, _H - 80), f"Original {content_label.lower()}:", font=font_regular(18), fill=MUTED)
    draw_wrapped_text(draw, (_MARGIN, _H - 54), source_url, font_regular(20), _W - 2 * _MARGIN, ACCENT, max_lines=1)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 3 — evidence
# ---------------------------------------------------------------------------

def _draw_source_citation(draw: ImageDraw.ImageDraw, xy: tuple[int, int], width: int, label: str, citation: SourceCitation | None, tag_color: str) -> int:
    x, y = xy
    if citation is None:
        return y
    _pill(draw, (x, y), label, tag_color, PAPER, font_size=16)
    y += 40
    name_line = citation.label[:60] + (f" · {citation.date_str}" if citation.date_str else "")
    y = draw_wrapped_text(draw, (x, y), name_line, font_bold(20), width, INK, max_lines=1)
    y += 4
    if citation.excerpt:
        y = draw_wrapped_text(draw, (x, y), f"“{citation.excerpt}”", font_regular(18), width, MUTED, max_lines=2)
    y += 4
    y = draw_wrapped_text(draw, (x, y), citation.url, font_regular(16), width, ACCENT, max_lines=1)
    return y + 14


def _evidence_card_height(card: EvidenceCard) -> int:
    height = 150
    if card.primary_source:
        height += 130
    if card.independent_source:
        height += 130
    return height


def render_evidence_slide(
    *,
    evidence_cards: list[EvidenceCard],
    key_fact: str,
) -> bytes:
    canvas = _base_canvas()
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, 40), "WHAT THE EVIDENCE SHOWS", font=font_bold(36), fill=INK)
    draw.text((_MARGIN, 84), "We checked the official rules and credible sources.", font=font_regular(20), fill=MUTED)
    y = 140

    key_fact_h = 130
    budget = _H - y - key_fact_h - 40
    cards = evidence_cards[:3] if evidence_cards else []

    for i, card in enumerate(cards):
        remaining_cards = len(cards) - i
        card_h = min(_evidence_card_height(card), max(180, budget // max(remaining_cards, 1)))
        box = (_MARGIN, y, _W - _MARGIN, y + card_h)
        draw.rounded_rectangle(box, radius=14, fill=CARD_BG, outline=BORDER)

        inner_x, inner_y = _MARGIN + 22, y + 18
        icon_color = VERDICT_COLORS.get(card.verdict_label, MUTED)
        _icon_badge(draw, (inner_x, inner_y), card.icon, icon_color, size=34)
        draw_wrapped_text(
            draw, (inner_x + 46, inner_y + 3), card.claim_text, font_bold(22), _W - 2 * _MARGIN - 46 - 22, INK,
            max_lines=2,
        )
        text_y = inner_y + 60
        text_y = draw_wrapped_text(
            draw, (inner_x, text_y), card.answer_text, font_regular(19), _W - 2 * _MARGIN - 44, INK,
            max_lines=3,
        )
        text_y += 8

        col_w = (_W - 2 * _MARGIN - 44 - 24) // 2 if (card.primary_source and card.independent_source) else _W - 2 * _MARGIN - 44
        if card.primary_source:
            _draw_source_citation(draw, (inner_x, text_y), col_w, "PRIMARY SOURCE", card.primary_source, PRIMARY_SOURCE_TAG)
        if card.independent_source:
            second_x = inner_x + col_w + 24 if card.primary_source else inner_x
            _draw_source_citation(draw, (second_x, text_y), col_w, "INDEPENDENT SOURCE", card.independent_source, INDEPENDENT_SOURCE_TAG)

        y += card_h + 20

    key_fact_top = _H - key_fact_h - 40
    draw.rounded_rectangle((_MARGIN, key_fact_top, _W - _MARGIN, _H - 40), radius=16, fill=ACCENT_LIGHT, outline=BORDER)
    draw.text((_MARGIN + 24, key_fact_top + 18), "KEY FACT", font=font_bold(20), fill=ACCENT)
    draw_wrapped_text(draw, (_MARGIN + 24, key_fact_top + 52), key_fact, font_bold(24), _W - 2 * _MARGIN - 48, INK, max_lines=3)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 4 — conclusion
# ---------------------------------------------------------------------------

def render_conclusion_slide(
    *,
    verdict_label: str,
    why_paragraph: str,
    claim_table: list,
    primary_sources: list[SourceCitation],
    independent_sources: list[SourceCitation],
    source_url: str,
    date_str: str,
) -> bytes:
    canvas = _base_canvas(bg=INK)
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, 46), "CONCLUSION", font=font_bold(28), fill=ACCENT_LIGHT)
    y = 90
    bottom = _verdict_badge(draw, (_MARGIN, y), verdict_label, font_size=42)
    y = bottom[1] + 24

    draw.text((_MARGIN, y), "WHY?", font=font_bold(20), fill=ACCENT_LIGHT)
    y += 32
    y = draw_wrapped_text(draw, (_MARGIN, y), why_paragraph, font_regular(23), _W - 2 * _MARGIN, PAPER,
                           line_spacing=8, max_lines=5)
    y += 24

    if claim_table:
        draw.text((_MARGIN, y), "CLAIM-BY-CLAIM ASSESSMENT", font=font_bold(20), fill=ACCENT_LIGHT)
        y += 34
        for row in claim_table[:4]:
            color = VERDICT_COLORS.get(row.verdict_label, MUTED)
            _icon_badge(draw, (_MARGIN, y), row.icon, color, size=26)
            tag_w = draw.textlength(row.verdict_label.replace("_", " "), font=font_bold(15)) + 24
            claim_w = _W - 2 * _MARGIN - 26 - 16 - tag_w - 10
            draw_wrapped_text(draw, (_MARGIN + 26 + 12, y + 2), row.claim_text, font_regular(18), claim_w, PAPER, max_lines=1)
            _pill(draw, (_W - _MARGIN - tag_w, y - 2), row.verdict_label.replace("_", " "), color, PAPER, font_size=14)
            y += 38
        y += 12

    sources_top = y
    footer_h = 130
    sources_bottom = _H - footer_h
    if primary_sources or independent_sources:
        draw.text((_MARGIN, sources_top), "SOURCES", font=font_bold(20), fill=ACCENT_LIGHT)
        y = sources_top + 34
        if primary_sources:
            draw.text((_MARGIN, y), "Primary", font=font_bold(16), fill=HIGHLIGHT)
            y += 26
            for s in primary_sources[:2]:
                if y > sources_bottom - 20:
                    break
                y = draw_wrapped_text(draw, (_MARGIN, y), f"• {s.label}", font_regular(18), _W - 2 * _MARGIN, PAPER, max_lines=1)
                y = draw_wrapped_text(draw, (_MARGIN + 14, y), s.url, font_regular(15), _W - 2 * _MARGIN - 14, ACCENT_LIGHT, max_lines=1)
                y += 8
        if independent_sources:
            y += 6
            draw.text((_MARGIN, y), "Independent", font=font_bold(16), fill=HIGHLIGHT)
            y += 26
            for s in independent_sources[:2]:
                if y > sources_bottom - 20:
                    break
                y = draw_wrapped_text(draw, (_MARGIN, y), f"• {s.label}", font_regular(18), _W - 2 * _MARGIN, PAPER, max_lines=1)
                y = draw_wrapped_text(draw, (_MARGIN + 14, y), s.url, font_regular(15), _W - 2 * _MARGIN - 14, ACCENT_LIGHT, max_lines=1)
                y += 8

    draw.rectangle((0, _H - footer_h, _W, _H), fill=(20, 23, 26))
    draw.text((_MARGIN, _H - footer_h + 16), f"FACT-CHECKED ON: {date_str}", font=font_bold(18), fill=PAPER)
    draw_wrapped_text(
        draw, (_MARGIN, _H - footer_h + 48), source_url, font_regular(16), _W - 2 * _MARGIN, ACCENT_LIGHT, max_lines=1
    )
    _draw_wordmark(draw, (_MARGIN, _H - 58), color=PAPER, subtitle_color=MUTED)

    return to_png_bytes(canvas)
