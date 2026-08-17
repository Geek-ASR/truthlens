"""EXP-016 (research/RESEARCH_ROADMAP_V2.md Phase 3, Step 7's 8 modality
combinations). The original 3-condition experiment (research/multimodal/
run_claim_coverage.py, EXP-004/EXP-011) bundled transcript(audio) and
caption together as one always-on "text" signal and only toggled OCR/
vision -- disclosed there as an honest simplification ("no fourth,
separately-capable signal beyond 'all three together'"), not a
limitation of the underlying pipeline: app.pipeline.claim_extraction.
_build_user_content() already checks transcript, ocr_text, caption_text,
and vision_context as 4 fully INDEPENDENT `if` blocks.

This script keeps caption ALWAYS on (it's user-authored text, not a
system-sensed "modality" in the RQ3 sense -- there's no pipeline stage
that "extracts" it, unlike audio->transcript, OCR, and vision) and
toggles the 3 real sensed modalities independently: audio (transcript),
OCR, vision. 2^3 = 8 combinations, matching Step 7's own count exactly.

Reuses claim_extraction._build_user_content() directly (imported, not
reimplemented) -- the only new code is the masking function that decides
which of the 4 real fields to pass through per condition, mirroring
run_claim_coverage.py's own _masked_reel() pattern exactly.

Per-modality PRECISION (Phase 3's own explicitly-requested metric,
"not just coverage"): reuses the same deterministic groundedness check
already built for claim provenance (app.pipeline.claim_extraction.
_infer_source_modalities) as a real, non-invented proxy -- a claim whose
source_quote is a genuine verbatim substring of the reel's actual
(unmasked-condition) content is precision-countable; one with no
verbatim quote is not, regardless of how confident the extraction looked.

Run: cd backend && ./.venv/bin/python research/multimodal_v2/run_8way_coverage.py
"""
import asyncio
import itertools
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.models import BenchmarkSplit, DatasetType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.claim_extraction import _build_user_content, _infer_source_modalities  # noqa: E402
from app.schemas.claim import ClaimExtractionResult  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from app.services.ai.prompts import CLAIM_EXTRACTION_PROMPT_VERSION, CLAIM_EXTRACTION_SYSTEM_PROMPT  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"

_SIGNALS = ["audio", "ocr", "vision"]
_CONDITIONS = [
    frozenset(combo)
    for r in range(len(_SIGNALS) + 1)
    for combo in itertools.combinations(_SIGNALS, r)
]  # 8 combinations: {}, {audio}, {ocr}, {vision}, {audio,ocr}, {audio,vision}, {ocr,vision}, {audio,ocr,vision}


def _condition_name(enabled: frozenset) -> str:
    return "+".join(sorted(enabled)) if enabled else "caption_only"


def _masked_reel(real_reel: Reel, enabled: frozenset):
    """Caption always on (not a toggle -- see module docstring); audio/
    ocr/vision independently masked per condition."""
    return SimpleNamespace(
        transcript=real_reel.transcript if "audio" in enabled else None,
        caption_text=real_reel.caption_text,
        ocr_text=real_reel.ocr_text if "ocr" in enabled else None,
        vision_context=real_reel.vision_context if "vision" in enabled else None,
    )


async def _run_condition(llm_provider, settings, real_reel: Reel, enabled: frozenset) -> dict:
    masked = _masked_reel(real_reel, enabled)
    start = time.monotonic()
    try:
        user_content = _build_user_content(masked)
    except ValueError as exc:
        return {"condition": _condition_name(enabled), "claims": [], "outcome_type": "no_input_content", "error": str(exc)}

    try:
        result = await llm_provider.structured_call(
            model=settings.LLM_MODEL_CLAIM_EXTRACTION,
            system_prompt=CLAIM_EXTRACTION_SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=ClaimExtractionResult,
            prompt_version=CLAIM_EXTRACTION_PROMPT_VERSION,
        )
    except Exception as exc:  # noqa: BLE001 -- record, don't crash the batch
        return {"condition": _condition_name(enabled), "claims": [], "outcome_type": "error", "error": str(exc)}

    claims_detail = []
    for c in result.parsed.claims:
        if not c.text.strip():
            continue
        # Groundedness checked against the REAL, UNMASKED reel -- a
        # claim is "precision-countable" if its quote is verbatim
        # somewhere in the item's real content, regardless of which
        # masked subset the model actually saw when it produced it (a
        # claim grounded in real vision_context text is still a real,
        # correct claim even if this condition also had OCR enabled).
        modalities, _ = _infer_source_modalities(c, real_reel)
        claims_detail.append({"text": c.text, "grounded": bool(modalities), "source_modalities": modalities})

    return {
        "condition": _condition_name(enabled),
        "claims": claims_detail,
        "outcome_type": "resolved",
        "error": None,
        "latency_seconds": time.monotonic() - start,
    }


async def main() -> None:
    settings = get_settings()
    llm_provider = OllamaProvider()  # matches the original experiment's isolation design -- no Gemini fallback

    all_results = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reel.id, Reel.source_url)
            .where(Reel.dataset_type == DatasetType.benchmark, Reel.benchmark_split == BenchmarkSplit.dev)
        )
        seen_urls: set[str] = set()
        targets = []
        for reel_id, source_url in result.all():
            if source_url in seen_urls:
                continue
            seen_urls.add(source_url)
            targets.append((reel_id, source_url))

    async with AsyncSessionLocal() as db:
        for reel_id, source_url in targets:
            reel = await db.get(Reel, reel_id)
            if not (reel.transcript or reel.ocr_text or reel.caption_text):
                print(f"SKIP {source_url}: no real content", file=sys.stderr)
                continue

            print(f"=== {source_url} ===", file=sys.stderr)
            item_result = {"source_url": source_url, "reel_id": str(reel_id), "conditions": {}}
            for enabled in _CONDITIONS:
                outcome = await _run_condition(llm_provider, settings, reel, enabled)
                item_result["conditions"][outcome["condition"]] = outcome
                n_grounded = sum(1 for c in outcome["claims"] if c["grounded"])
                print(
                    f"  {outcome['condition']:20s}: {len(outcome['claims'])} claims "
                    f"({n_grounded} grounded), outcome={outcome['outcome_type']}",
                    file=sys.stderr,
                )
            all_results.append(item_result)
            await db.rollback()  # never persist -- measurement run only

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "multimodal_8way_coverage_20260818.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)

    # Aggregate summary per condition: total claims, grounded claims (=
    # precision-countable, Phase 3's own explicit metric beyond coverage).
    agg = {_condition_name(c): {"n_items": 0, "n_claims": 0, "n_grounded": 0} for c in _CONDITIONS}
    for item in all_results:
        for cond_name, outcome in item["conditions"].items():
            if outcome["outcome_type"] != "resolved":
                continue
            agg[cond_name]["n_items"] += 1
            agg[cond_name]["n_claims"] += len(outcome["claims"])
            agg[cond_name]["n_grounded"] += sum(1 for c in outcome["claims"] if c["grounded"])

    print("\nPer-condition summary (claims / grounded / precision%):", file=sys.stderr)
    for cond_name in [_condition_name(c) for c in _CONDITIONS]:
        a = agg[cond_name]
        precision = (a["n_grounded"] / a["n_claims"] * 100) if a["n_claims"] else 0.0
        print(f"  {cond_name:20s}: claims={a['n_claims']:3d} grounded={a['n_grounded']:3d} precision={precision:5.1f}%", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
