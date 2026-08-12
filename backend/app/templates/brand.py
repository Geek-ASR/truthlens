"""TruthLens visual identity (product spec §22-23). Deliberately plain —
does not resemble an official government seal or imply affiliation with
Instagram, Meta, any political party, or any existing fact-checking
organization."""
from PIL import ImageFont

CANVAS_SIZE = (1080, 1350)  # 4:5 Instagram portrait, product spec §22

# Colors
INK = "#14171A"
PAPER = "#FAF9F6"
ACCENT = "#1B4B43"  # deep neutral green — not tied to any party color
ACCENT_LIGHT = "#E7F0EC"
MUTED = "#6B7280"
BORDER = "#D8D8D2"
HIGHLIGHT = "#E8A33D"  # warm amber for emphasized phrases within poster headline text
CARD_BG = "#F4F1EA"  # warm off-white for evidence/source cards, distinct from PAPER
TAG_BG = "#B23A2E"  # muted brick red for the "VIRAL CLAIM" tag — not a party color, just an alert tone
PRIMARY_SOURCE_TAG = "#1B4B43"
INDEPENDENT_SOURCE_TAG = "#4A5A6A"

VERDICT_COLORS = {
    "TRUE": "#1B6E3C",
    "MOSTLY_TRUE": "#3E8E5A",
    "MISLEADING": "#B8860B",
    "MOSTLY_FALSE": "#C06A2C",
    "FALSE": "#A6321F",
    "UNVERIFIED": "#5B6472",
    "OUTDATED": "#7A5C9E",
    "MISSING_CONTEXT": "#946B1F",
}

_FONT_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]
_FONT_CANDIDATES_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]

_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    key = (candidates[0], size)
    if key in _font_cache:
        return _font_cache[key]
    for path in candidates:
        try:
            font = ImageFont.truetype(path, size)
            _font_cache[key] = font
            return font
        except OSError:
            continue
    font = ImageFont.load_default(size=size)
    _font_cache[key] = font
    return font


def font_bold(size: int) -> ImageFont.FreeTypeFont:
    return _load_font(_FONT_CANDIDATES_BOLD, size)


def font_regular(size: int) -> ImageFont.FreeTypeFont:
    return _load_font(_FONT_CANDIDATES_REGULAR, size)
