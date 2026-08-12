"""Day 4 (research/EXPERIMENT_PLAN.md RQ3): real ingestion of each
dataset item's actual media, then claim extraction run 3 times per item
under different input-modality restrictions, to measure Claim Coverage
(research/METRICS.md §2) as a function of modality.

Honest note on "4 modes": the brief that motivated this experiment named
four conditions (text-only / +OCR / +OCR+vision / "full multimodal").
TruthLens's actual architecture has exactly three distinct input
signals feeding claim extraction (transcript+caption, OCR, vision
-context) -- there is no fourth, separately-capable signal beyond "all
three together." Rather than invent a fabricated fourth condition, this
script runs three: text-only, text+OCR, text+OCR+vision (== "full
multimodal" for this system, stated as identical rather than presented
as two different results).

This does REAL ingestion (fetch, transcribe, OCR, vision) once per item
-- the expensive part -- then reuses the same ingested Reel row for all
three modality conditions, calling the LLM directly with a
duck-typed stand-in object rather than app.pipeline.claim_extraction.
extract_claims() itself, so no extra Claim rows are written to the
production DB for conditions that are purely a research comparison.

Run from the backend directory:
    cd backend && .venv/bin/python research/multimodal/run_claim_coverage.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.core.config import get_settings  # noqa: E402
from app.db.models import MediaType  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import ingestion, ocr, transcription, vision_context  # noqa: E402
from app.pipeline.claim_extraction import _build_user_content  # noqa: E402
from app.schemas.claim import ClaimExtractionResult  # noqa: E402
from app.schemas.reel import ReelCreate  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from app.services.ai.prompts import CLAIM_EXTRACTION_PROMPT_VERSION, CLAIM_EXTRACTION_SYSTEM_PROMPT  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATASET_FILE = PROJECT_ROOT / "research" / "dataset" / "items.jsonl"
RESULTS_DIR = PROJECT_ROOT / "research" / "results"

MODALITY_CONDITIONS = ["text_only", "text_ocr", "text_ocr_vision"]


def _masked_reel(real_reel, condition: str):
    """Duck-typed stand-in with only the 4 attributes
    _build_user_content() reads, masked per condition. NOT a real Reel
    ORM object -- deliberately, so this never risks a stray DB write."""
    return SimpleNamespace(
        transcript=real_reel.transcript,
        caption_text=real_reel.caption_text,
        ocr_text=real_reel.ocr_text if condition in ("text_ocr", "text_ocr_vision") else None,
        vision_context=real_reel.vision_context if condition == "text_ocr_vision" else None,
    )


async def ingest_item(db, item: dict):
    """Real fetch + transcribe/OCR/vision -- mirrors
    orchestrator.analyze_reel()'s first branch exactly, but stops before
    claim_extraction so this script controls that stage itself."""
    storage = get_storage_client()
    payload = ReelCreate(source_url=item["source_url"], platform="instagram", auto_fetch=True)
    reel = await ingestion.ingest_reel(db, payload, None, None)
    await db.commit()
    await db.refresh(reel)

    if reel.media_storage_key and reel.media_type == MediaType.video:
        video_bytes = storage.get_bytes(reel.media_storage_key)
        audio_path, frame_paths = ingestion.extract_media_artifacts(video_bytes)
        await transcription.transcribe_reel(db, reel, audio_path)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)
    elif reel.media_storage_key and reel.media_type == MediaType.photo:
        photo_bytes = storage.get_bytes(reel.media_storage_key)
        frame_paths = ingestion.extract_photo_artifact(photo_bytes)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)
    await db.commit()
    await db.refresh(reel)
    return reel


async def run_condition(llm_provider, settings, real_reel, condition: str) -> dict:
    masked = _masked_reel(real_reel, condition)
    start = time.monotonic()
    try:
        user_content = _build_user_content(masked)
    except ValueError as exc:
        # "no transcript/OCR/caption to extract from at all" -- a real,
        # honest outcome for e.g. text_only on a photo post with no
        # caption and no transcribable audio, not an error to hide.
        return {
            "condition": condition,
            "claims": [],
            "outcome_type": "no_input_content",
            "error": str(exc),
            "latency_seconds": time.monotonic() - start,
            "input_tokens": 0,
            "output_tokens": 0,
        }

    try:
        result = await llm_provider.structured_call(
            model=settings.LLM_MODEL_CLAIM_EXTRACTION,
            system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=ClaimExtractionResult,
            prompt_version=CLAIM_EXTRACTION_PROMPT_VERSION,
        )
        claims = [c.model_dump(mode="json") for c in result.parsed.claims]
        return {
            "condition": condition,
            "claims": claims,
            "outcome_type": "resolved",
            "error": None,
            "latency_seconds": time.monotonic() - start,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }
    except Exception as exc:  # noqa: BLE001 — record, don't crash the batch
        return {
            "condition": condition,
            "claims": [],
            "outcome_type": "error",
            "error": str(exc),
            "latency_seconds": time.monotonic() - start,
            "input_tokens": 0,
            "output_tokens": 0,
        }


async def main():
    settings = get_settings()
    llm_provider = OllamaProvider()  # pure Ollama, no Gemini fallback — see BASELINE_SPEC.md's own fix
    items = [json.loads(line) for line in DATASET_FILE.read_text().splitlines() if line.strip()]

    all_results = []
    async with AsyncSessionLocal() as db:
        for item in items:
            print(f"=== {item['id']}: ingesting real media from {item['source_url']} ===", file=sys.stderr)
            try:
                reel = await ingest_item(db, item)
            except Exception as exc:  # noqa: BLE001 — a real fetch failure is a real, reportable outcome
                print(f"  INGESTION FAILED: {exc}", file=sys.stderr)
                all_results.append({"item_id": item["id"], "ingestion_error": str(exc)})
                await db.rollback()
                continue

            print(
                f"  ingested: media_type={reel.media_type.value}, "
                f"transcript_len={len(reel.transcript or '')}, "
                f"ocr_frames={len(reel.ocr_text or [])}, "
                f"has_vision_context={bool(reel.vision_context)}",
                file=sys.stderr,
            )

            item_result = {"item_id": item["id"], "reel_id": str(reel.id), "conditions": {}}
            for condition in MODALITY_CONDITIONS:
                print(f"  running condition: {condition}...", file=sys.stderr)
                outcome = await run_condition(llm_provider, settings, reel, condition)
                item_result["conditions"][condition] = outcome
                print(f"    -> {len(outcome['claims'])} claims, outcome={outcome['outcome_type']}", file=sys.stderr)

            all_results.append(item_result)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_path = RESULTS_DIR / f"multimodal_claim_extraction_{timestamp}.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nWrote {len(all_results)} item results to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
