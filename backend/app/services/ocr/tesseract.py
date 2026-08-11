"""Tesseract OCR for on-screen text (docs/ARCHITECTURE.md §5 — free,
local, no API key required for MVP)."""
from dataclasses import dataclass

import pytesseract
from PIL import Image


@dataclass
class OCRFrameResult:
    frame_ts: float
    text: str
    confidence: float


def ocr_frame(image: Image.Image, frame_ts: float) -> OCRFrameResult:
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    words = [w for w in data["text"] if w.strip()]
    confidences = [float(c) for c, w in zip(data["conf"], data["text"]) if w.strip() and c != "-1"]
    text = " ".join(words)
    avg_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    return OCRFrameResult(frame_ts=frame_ts, text=text, confidence=avg_conf)
