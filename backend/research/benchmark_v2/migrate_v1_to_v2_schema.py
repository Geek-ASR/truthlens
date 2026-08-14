"""Migrates the existing 9-item benchmark (research/dataset/items.jsonl,
"v1") into the new schema (research/DATASET_SCHEMA_V2.md) as a SEPARATE
file — never edits items.jsonl in place, per the governing brief's Rule 1
("do not silently overwrite previous benchmark versions").

audio_available/ocr_available/caption_available/visual_information_available
are queried live against the real reels table (source of truth), not
guessed from the item's `modality` field — item-0004 is media_type=video
but has no caption text, item-0005 is a photo but genuinely has no audio
input by construction, etc.; a hand-written guess would get several of
these wrong. cross_post_verified is transcribed from
research/MULTIMODAL_EVALUATION.md's own documented per-item findings
(not re-derived), since re-deriving it here isn't this script's job.

Run: ./.venv/bin/python -m research.benchmark_v2.migrate_v1_to_v2_schema
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ITEMS_V1_PATH = _REPO_ROOT / "research" / "dataset" / "items.jsonl"
_OUTPUT_PATH = _REPO_ROOT / "research" / "dataset" / "items_v1_as_v2_schema.jsonl"

# Transcribed from research/MULTIMODAL_EVALUATION.md's own findings (the
# "4 of 6" cross-post table and its item-0004/item-0007 discussion) --
# not re-evaluated here. null (omitted from this dict) for item-0003
# (never ingested) and item-0008/item-0009 (excluded from that analysis
# entirely, never evaluated for this either way).
_CROSS_POST_VERIFIED = {
    "item-0001": True,
    "item-0002": True,
    "item-0004": False,
    "item-0005": True,
    "item-0006": True,
    "item-0007": "partial",
}


def _factchecker_from_labeler(labeler: str) -> str:
    # "tier-1-source:boomlive.in" -> "boomlive.in"
    return labeler.split(":", 1)[-1] if ":" in labeler else labeler


async def _availability_for(db, source_url: str) -> dict:
    result = await db.execute(select(Reel).where(Reel.source_url == source_url).limit(1))
    reel = result.scalars().first()
    if reel is None:
        return {
            "audio_available": None,
            "ocr_available": None,
            "caption_available": None,
            "visual_information_available": None,
            "media_hash": None,
        }
    return {
        "audio_available": bool(reel.transcript),
        "ocr_available": bool(reel.ocr_text),
        "caption_available": bool(reel.caption_text),
        "visual_information_available": reel.vision_context is not None,
        "media_hash": reel.media_content_hash,
    }


async def migrate() -> list[dict]:
    v2_items = []
    async with AsyncSessionLocal() as db:
        with open(_ITEMS_V1_PATH) as f:
            for line in f:
                v1 = json.loads(line)
                availability = await _availability_for(db, v1["source_url"])
                v2_items.append(
                    {
                        "item_id": v1["id"],
                        "benchmark_version": "v1",
                        # See research/DATASET_SCHEMA_V2.md "Split assignment" --
                        # deliberately "dev", not "test": these items already
                        # informed real system changes (the baseline-confound
                        # fix, the validator general fixes), so they cannot
                        # retroactively meet this program's own TEST-freeze
                        # discipline (Step 3).
                        "split": "dev",
                        "media": v1["modality"],
                        "media_hash": availability["media_hash"],
                        "platform": "instagram",
                        "original_url": v1["source_url"],
                        "factcheck_url": v1["ground_truth_source_url"],
                        "factchecker": _factchecker_from_labeler(v1["labeler"]),
                        "publication_date": v1.get("date"),
                        "factcheck_date": None,  # not tracked in v1
                        "ground_truth_label": v1["ground_truth_label"],
                        "ground_truth_claim": v1["claim_text"],
                        "claim_type": v1["claim_type"],
                        "political_actor": v1["political_actor"],
                        "language": v1["language"],
                        "audio_available": availability["audio_available"],
                        "ocr_available": availability["ocr_available"],
                        "caption_available": availability["caption_available"],
                        "visual_information_available": availability["visual_information_available"],
                        "cross_post_possible": True,
                        "cross_post_verified": _CROSS_POST_VERIFIED.get(v1["id"]),
                        "difficulty": None,  # no defined rubric exists yet -- see DATASET_SCHEMA_V2.md
                        "development_split": True,
                    }
                )
    return v2_items


async def main() -> None:
    v2_items = await migrate()
    with open(_OUTPUT_PATH, "w") as f:
        for item in v2_items:
            f.write(json.dumps(item) + "\n")
    print(f"Wrote {len(v2_items)} items to {_OUTPUT_PATH}")
    print(f"({_ITEMS_V1_PATH} left untouched)")


if __name__ == "__main__":
    asyncio.run(main())
