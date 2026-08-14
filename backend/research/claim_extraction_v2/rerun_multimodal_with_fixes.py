"""EXP-011 (research/RESEARCH_ROADMAP_V2.md, bridging Phase 2 -> Phase 3):
does this session's float-boundary-noise/confused-value clamp
(app/schemas/claim.py) change the original multimodal claim-coverage
result (EXP-004, research/MULTIMODAL_EVALUATION.md) at all?

Reuses research/multimodal/run_claim_coverage.py's own run_condition()/
_masked_reel()/MODALITY_CONDITIONS unchanged (so this is genuinely the
same measurement, not a reimplementation that could drift) but skips its
ingest_item() step -- the 6 already-ingested items already have real
transcript/OCR/vision_context data sitting in the dev DB from the
original run, so re-fetching would just waste real network/compute time
and risk creating yet another duplicate reel row without changing what's
actually being measured.

Run: ./.venv/bin/python research/claim_extraction_v2/rerun_multimodal_with_fixes.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from research.multimodal.run_claim_coverage import (  # noqa: E402
    DATASET_FILE,
    MODALITY_CONDITIONS,
    run_condition,
)

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


async def main() -> None:
    settings = get_settings()
    llm_provider = OllamaProvider()  # matches the original: pure Ollama, no Gemini fallback
    items = [json.loads(line) for line in DATASET_FILE.read_text().splitlines() if line.strip()]

    all_results = []
    async with AsyncSessionLocal() as db:
        for item in items:
            result = await db.execute(select(Reel).where(Reel.source_url == item["source_url"]).limit(1))
            reel = result.scalars().first()
            if reel is None or not (reel.transcript or reel.ocr_text or reel.caption_text):
                print(f"SKIP {item['id']}: no already-ingested reel with real content found", file=sys.stderr)
                all_results.append({"item_id": item["id"], "skipped": True})
                continue

            print(f"=== {item['id']} (reusing already-ingested reel {reel.id}) ===", file=sys.stderr)
            item_result = {"item_id": item["id"], "reel_id": str(reel.id), "conditions": {}}
            for condition in MODALITY_CONDITIONS:
                outcome = await run_condition(llm_provider, settings, reel, condition)
                item_result["conditions"][condition] = outcome
                print(f"  {condition}: {len(outcome['claims'])} claims, outcome={outcome['outcome_type']}", file=sys.stderr)
            all_results.append(item_result)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "multimodal_claim_extraction_rerun_with_clamp_fix_20260815.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nWrote {len(all_results)} item results to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
