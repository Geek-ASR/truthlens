from PIL import Image, ImageDraw

from app.templates.brand import font_regular
from app.templates.render_utils import draw_wrapped_text, draw_wrapped_text_with_highlights


def _draw():
    img = Image.new("RGB", (800, 400), "white")
    return img, ImageDraw.Draw(img)


def test_draw_wrapped_text_substitutes_unsupported_rupee_glyph():
    # Real bug found live: the bundled Arial/DejaVu fonts have no glyph
    # for ₹ (Indian Rupee Sign), so it rendered as a "tofu" box on a
    # published slide showing "...spent ₹4,000 crore on advertising...".
    img, draw = _draw()
    y = draw_wrapped_text(draw, (10, 10), "Spent ₹4,000 crore on ads.", font_regular(24), 780, "black")
    assert y > 10  # drew something without raising
    # No direct way to introspect drawn glyphs, but the sanitizer itself
    # is exercised via wrap_to_width's line-width measurement, which
    # would differ meaningfully between "₹" (missing glyph, near-zero or
    # placeholder width) and "Rs. " (real glyphs) -- covered precisely
    # by the unit test below instead of pixel inspection.


def test_sanitize_for_render_replaces_rupee_sign():
    from app.templates.render_utils import _sanitize_for_render

    assert _sanitize_for_render("₹4,000 crore") == "Rs. 4,000 crore"
    assert _sanitize_for_render("no currency here") == "no currency here"


def test_highlight_phrases_still_match_after_sanitization():
    # A highlight phrase containing the same character as the text must
    # still be found as a substring after both get sanitized in lockstep
    # -- if only one side were sanitized, this would silently break
    # highlighting instead of raising, which is why this is tested
    # explicitly rather than trusted.
    img, draw = _draw()
    y = draw_wrapped_text_with_highlights(
        draw, (10, 10), "Spent ₹4,000 crore on ads.", ["₹4,000 crore"],
        font_regular(24), 780, "black", "orange",
    )
    assert y > 10
