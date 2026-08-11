"""Deterministic Pillow renderers for the 4-slide carousel (product spec
§2-5, §22). Same input JSON always produces the same pixels — no
generative image model involved, so a slide can be regenerated exactly
after a caption/text edit (docs/DATA_MODEL.md slides.content_json)."""
from PIL import Image, ImageDraw

from app.templates.brand import (
    ACCENT,
    ACCENT_LIGHT,
    BORDER,
    CANVAS_SIZE,
    INK,
    MUTED,
    PAPER,
    VERDICT_COLORS,
    font_bold,
    font_regular,
)
from app.templates.render_utils import cover_resize, draw_wrapped_text, to_png_bytes

TEMPLATE_VERSION = "slides.v1"

_W, _H = CANVAS_SIZE
_MARGIN = 64


def _base_canvas(bg=PAPER) -> Image.Image:
    return Image.new("RGB", CANVAS_SIZE, bg)


def _draw_wordmark(draw: ImageDraw.ImageDraw, xy: tuple[int, int], color: str = INK) -> None:
    draw.text(xy, "TRUTHLENS", font=font_bold(34), fill=color)


def _verdict_badge(draw: ImageDraw.ImageDraw, xy: tuple[int, int], verdict_label: str) -> tuple[int, int]:
    color = VERDICT_COLORS.get(verdict_label, MUTED)
    label = verdict_label.replace("_", " ")
    font = font_bold(40)
    text_w = draw.textlength(label, font=font)
    pad_x, pad_y = 28, 16
    x, y = xy
    box = (x, y, x + text_w + pad_x * 2, y + font.size + pad_y * 2)
    draw.rounded_rectangle(box, radius=12, fill=color)
    draw.text((x + pad_x, y + pad_y - 2), label, font=font, fill=PAPER)
    return int(box[2]), int(box[3])


def _with_dark_overlay(image: Image.Image, opacity: int = 150) -> Image.Image:
    overlay = Image.new("RGBA", image.size, (10, 12, 12, opacity))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


# ---------------------------------------------------------------------------
# Slide 1 — poster
# ---------------------------------------------------------------------------

def render_poster_slide(
    *,
    claim_summary: str,
    verdict_label: str,
    date_str: str,
    platform_label: str,
    thumbnail: Image.Image | None,
) -> bytes:
    if thumbnail is not None:
        canvas = cover_resize(thumbnail.convert("RGB"), CANVAS_SIZE)
        canvas = _with_dark_overlay(canvas, opacity=165)
    else:
        canvas = _base_canvas(bg=INK)
    draw = ImageDraw.Draw(canvas)

    _draw_wordmark(draw, (_MARGIN, 56), color=PAPER)
    draw.text((_MARGIN, 100), "FACT CHECK", font=font_bold(30), fill=PAPER)

    draw.text((_MARGIN, 420), "VIRAL CLAIM", font=font_bold(24), fill=ACCENT_LIGHT)
    draw_wrapped_text(
        draw,
        (_MARGIN, 465),
        f"“{claim_summary}”",
        font_bold(56),
        _W - 2 * _MARGIN,
        PAPER,
        line_spacing=8,
        max_lines=5,
    )

    _verdict_badge(draw, (_MARGIN, _H - 260), verdict_label)
    draw.text((_MARGIN, _H - 150), f"{platform_label} · {date_str}", font=font_regular(26), fill=ACCENT_LIGHT)
    draw.text((_MARGIN, _H - 100), "Independent fact-check · not affiliated with the platform or creator",
               font=font_regular(20), fill=MUTED)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 2 — original reel representation
# ---------------------------------------------------------------------------

def render_original_reel_slide(
    *,
    creator_handle: str | None,
    caption_excerpt: str | None,
    source_url: str,
    thumbnail: Image.Image | None,
) -> bytes:
    if thumbnail is not None:
        canvas = cover_resize(thumbnail.convert("RGB"), CANVAS_SIZE)
        canvas = _with_dark_overlay(canvas, opacity=120)
    else:
        canvas = _base_canvas(bg=INK)
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, 66), "ORIGINAL REEL", font=font_bold(30), fill=PAPER)

    handle_text = creator_handle or "creator handle not provided"
    draw.text((_MARGIN, 140), handle_text, font=font_bold(34), fill=ACCENT_LIGHT)

    if caption_excerpt:
        draw_wrapped_text(
            draw, (_MARGIN, 200), caption_excerpt, font_regular(28), _W - 2 * _MARGIN, PAPER,
            max_lines=6,
        )

    footer_y = _H - 190
    draw.rectangle((0, footer_y - 20, _W, _H), fill=(20, 23, 26))
    draw.text((_MARGIN, footer_y), "This is a thumbnail/keyframe representation of the original reel.",
              font=font_regular(22), fill=MUTED)
    draw.text((_MARGIN, footer_y + 40), "Full original reel:", font=font_regular(22), fill=MUTED)
    draw_wrapped_text(draw, (_MARGIN, footer_y + 74), source_url, font_regular(24), _W - 2 * _MARGIN, ACCENT_LIGHT,
                       max_lines=2)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 3 — evidence
# ---------------------------------------------------------------------------

def render_evidence_slide(
    *,
    claim_text: str,
    evidence_explanation: str,
    evidence_bullets: list[str],
    key_fact: str,
) -> bytes:
    canvas = _base_canvas()
    draw = ImageDraw.Draw(canvas)

    _draw_wordmark(draw, (_MARGIN, 50))
    y = 130

    draw.text((_MARGIN, y), "WHAT THE REEL CLAIMS", font=font_bold(28), fill=ACCENT)
    y += 44
    y = draw_wrapped_text(draw, (_MARGIN, y), f"“{claim_text}”", font_regular(30), _W - 2 * _MARGIN, INK,
                           max_lines=4)
    y += 30

    draw.text((_MARGIN, y), "WHAT THE EVIDENCE SHOWS", font=font_bold(28), fill=ACCENT)
    y += 44
    y = draw_wrapped_text(draw, (_MARGIN, y), evidence_explanation, font_regular(28), _W - 2 * _MARGIN, INK,
                           max_lines=6)
    y += 30

    draw.text((_MARGIN, y), "EVIDENCE", font=font_bold(28), fill=ACCENT)
    y += 44
    for bullet in evidence_bullets[:4]:
        y = draw_wrapped_text(draw, (_MARGIN, y), f"• {bullet}", font_regular(26), _W - 2 * _MARGIN, INK,
                               max_lines=2)
        y += 6

    key_fact_top = max(y + 30, _H - 260)
    draw.rounded_rectangle((_MARGIN, key_fact_top, _W - _MARGIN, _H - 90), radius=16, fill=ACCENT_LIGHT,
                            outline=BORDER)
    draw.text((_MARGIN + 28, key_fact_top + 24), "KEY FACT", font=font_bold(24), fill=ACCENT)
    draw_wrapped_text(draw, (_MARGIN + 28, key_fact_top + 64), key_fact, font_bold(30),
                       _W - 2 * _MARGIN - 56, INK, max_lines=3)

    return to_png_bytes(canvas)


# ---------------------------------------------------------------------------
# Slide 4 — conclusion
# ---------------------------------------------------------------------------

def render_conclusion_slide(*, verdict_label: str, conclusion_paragraph: str) -> bytes:
    canvas = _base_canvas(bg=INK)
    draw = ImageDraw.Draw(canvas)

    draw.text((_MARGIN, 70), "CONCLUSION", font=font_bold(30), fill=ACCENT_LIGHT)
    bottom = _verdict_badge(draw, (_MARGIN, 130), verdict_label)

    draw_wrapped_text(
        draw, (_MARGIN, bottom[1] + 60), conclusion_paragraph, font_regular(34), _W - 2 * _MARGIN, PAPER,
        line_spacing=14, max_lines=8,
    )

    draw.text((_MARGIN, _H - 190), "Check the sources in the caption.", font=font_regular(26), fill=MUTED)
    _draw_wordmark(draw, (_MARGIN, _H - 110), color=PAPER)

    return to_png_bytes(canvas)
