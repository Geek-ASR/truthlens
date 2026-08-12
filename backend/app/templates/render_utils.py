"""Shared Pillow layout helpers for the slide templates."""
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

# The bundled/system fonts used for slide rendering (Arial/DejaVu Sans,
# see brand.py) don't include a glyph for some characters that show up
# routinely in this app's actual content -- found live on a real Indian
# political claim ("...spent ₹4,000 crore on advertising..."): the ₹
# glyph rendered as a "tofu" box (□) on the published slide. Substituted
# to an ASCII-safe equivalent before rendering only -- this never touches
# the underlying stored/API text, which renders the real character fine
# everywhere else (captions, JSON, the dashboard).
_RENDER_CHAR_SUBSTITUTIONS = {
    "₹": "Rs. ",  # ₹ INDIAN RUPEE SIGN
}


def _sanitize_for_render(text: str) -> str:
    for char, replacement in _RENDER_CHAR_SUBSTITUTIONS.items():
        text = text.replace(char, replacement)
    return text


def wrap_to_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    fill: str,
    line_spacing: int = 10,
    max_lines: int | None = None,
) -> int:
    """Draws wrapped text and returns the y-coordinate after the last line."""
    x, y = xy
    text = _sanitize_for_render(text)
    lines = wrap_to_width(draw, text, font, max_width)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip() + "…"
    line_height = font.size + line_spacing
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _highlight_mask(text: str, phrases: list[str]) -> list[bool]:
    mask = [False] * len(text)
    for phrase in phrases:
        if not phrase:
            continue
        start = text.find(phrase)
        if start == -1:
            continue
        for i in range(start, start + len(phrase)):
            mask[i] = True
    return mask


def draw_wrapped_text_with_highlights(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    highlight_phrases: list[str],
    font: ImageFont.FreeTypeFont,
    max_width: int,
    base_color: str,
    highlight_color: str,
    line_spacing: int = 10,
    max_lines: int | None = None,
) -> int:
    """Like draw_wrapped_text, but colors any word that's majority-covered
    by one of `highlight_phrases` (exact substrings of `text`, already
    validated by the caller — see schemas/content.py HeadlineResult)
    differently. Falls back to plain draw_wrapped_text if there's nothing
    to highlight."""
    # Sanitize both text and phrases the same way before matching -- a
    # phrase validated as a substring of the ORIGINAL text needs the
    # same substitutions applied so it's still a substring afterward
    # (character-substitution alone can't change length here since ₹'s
    # replacement is unlikely to appear mid-phrase-boundary, but keeping
    # both in lockstep is what actually guarantees it rather than luck).
    text = _sanitize_for_render(text)
    highlight_phrases = [_sanitize_for_render(p) for p in highlight_phrases]
    if not highlight_phrases:
        return draw_wrapped_text(draw, xy, text, font, max_width, base_color, line_spacing, max_lines)

    mask = _highlight_mask(text, highlight_phrases)
    words = text.split(" ")
    # Reconstruct each word's (text, is_highlighted) by walking the same
    # split the mask was built against.
    tagged_words: list[tuple[str, bool]] = []
    cursor = 0
    for word in words:
        start = cursor
        end = start + len(word)
        span = mask[start:end] if end <= len(mask) else mask[start:]
        is_highlighted = bool(span) and sum(span) > len(span) / 2
        tagged_words.append((word, is_highlighted))
        cursor = end + 1  # +1 for the space

    # Greedy wrap using plain text width (matches wrap_to_width's model).
    lines: list[list[tuple[str, bool]]] = []
    current: list[tuple[str, bool]] = []
    current_text = ""
    for word, hl in tagged_words:
        candidate = f"{current_text} {word}".strip()
        if not current or draw.textlength(candidate, font=font) <= max_width:
            current.append((word, hl))
            current_text = candidate
        else:
            lines.append(current)
            current = [(word, hl)]
            current_text = word
    if current:
        lines.append(current)

    truncated = False
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        truncated = True

    x0, y = xy
    line_height = font.size + line_spacing
    for line_idx, line in enumerate(lines):
        x = x0
        for word_idx, (word, hl) in enumerate(line):
            suffix = "…" if truncated and line_idx == len(lines) - 1 and word_idx == len(line) - 1 else ""
            draw_text = word + suffix
            draw.text((x, y), draw_text, font=font, fill=(highlight_color if hl else base_color))
            x += draw.textlength(word + " ", font=font)
        y += line_height
    return y


def to_png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def cover_resize(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    """Resize+crop an image to exactly fill target_size (like CSS
    background-size: cover), used for the reel thumbnail/keyframe."""
    target_w, target_h = target_size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    resized = image.resize((new_w, new_h))
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))
