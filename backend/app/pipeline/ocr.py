"""Stage 2b: on-screen text OCR, sampled every N seconds
(services/media.py FRAME_SAMPLE_INTERVAL_SECONDS)."""
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActorType, Reel
from app.pipeline.audit import record_audit
from app.services.media import FRAME_SAMPLE_INTERVAL_SECONDS
from app.services.ocr.tesseract import ocr_frame

_MIN_OCR_CONFIDENCE = 0.35


async def ocr_reel(db: AsyncSession, reel: Reel, frame_paths: list[str]) -> Reel:
    results = []
    for i, frame_path in enumerate(frame_paths):
        ts = i * FRAME_SAMPLE_INTERVAL_SECONDS
        img = Image.open(frame_path)
        result = ocr_frame(img, ts)
        if result.text.strip() and result.confidence >= _MIN_OCR_CONFIDENCE:
            results.append({"frame_ts": result.frame_ts, "text": result.text, "confidence": result.confidence})

    reel.ocr_text = results
    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.ai_stage,
        actor="ocr:tesseract",
        action="ocr",
        input_summary={"frame_count": len(frame_paths)},
        output_summary={"frames_with_text": len(results)},
    )
    return reel
