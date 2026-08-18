"""Promotes ELIGIBLE candidates (research/dataset/candidates_v2.jsonl,
BENCHMARK_COLLECTION_GUIDE.md) into real, ingested v2 benchmark items --
the deliberate manual step the guide describes, not something
candidate_tracker.py does automatically on reaching ELIGIBLE.

Does REAL ingestion per candidate (fetch, transcribe, OCR, vision) via
the exact same app.pipeline.ingestion.ingest_reel() call production and
research/multimodal/run_claim_coverage.py's ingest_item() both use --
not a reimplementation. audio_available/ocr_available/caption_available/
visual_information_available are read back from the real ingested Reel
row afterward (DATASET_SCHEMA_V2.md's own discipline: derived from live
data, never guessed).

Split assignment: every promoted item this run gets split="validation",
not "dev" or "test". Reasoning (not a default): DEV already has all 9
v1 items and real usage history; VALIDATION currently has zero items
anywhere in the project, which already blocks Phase 3's stopping
condition and Phase 10's dataset requirement in RESEARCH_ROADMAP_V2.md;
and TEST must stay unpopulated until Phase 12's deliberate freeze
(Step 3's "TEST is frozen once created" rule) -- assigning to TEST here,
via a routine sourcing-pass script, would be exactly the kind of quiet
scope creep that rule exists to prevent.

Writes to research/dataset/items_v2.jsonl (new file -- genuinely new v2
-collected items, as opposed to items_v1_as_v2_schema.jsonl which is
v1's existing 9 items re-expressed under the v2 schema, not new
content). Tags each promoted candidate's own JSONL record with
promoted_item_id so a re-run never double-promotes it, and tags the
live reels row dataset_type=benchmark/benchmark_version=v2/
benchmark_split=validation, mirroring tag_existing_benchmark_reels.py's
existing pattern for v1.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.promote_eligible_candidates
"""
import asyncio
import fcntl
import json
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import update  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, MediaType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import ingestion, ocr, transcription, vision_context  # noqa: E402
from app.schemas.reel import ReelCreate  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402
from research.benchmark_v2.candidate_tracker import _load_all, set_promoted_item_id  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ITEMS_V1_PATH = _REPO_ROOT / "research" / "dataset" / "items.jsonl"
_ITEMS_V2_PATH = _REPO_ROOT / "research" / "dataset" / "items_v2.jsonl"
_DATASET_DIR = _REPO_ROOT / "research" / "dataset"

_TARGET_SPLIT = BenchmarkSplit.validation

# set_promoted_item_id() only ever touches candidates_v2.jsonl (the
# shared, merged file candidate_tracker.py owns). Candidates sourced
# from the Vishvas/Factly/thequint pipelines also exist as a SEPARATE,
# still-unmarked copy in their own per-pipeline file (merge_mass_
# candidates.py copies, it doesn't move) -- found live: cand-thequint
# -0182, already promoted to item-0021 via the main file, still showed
# up as "ELIGIBLE, un-promoted" in spot_check_eligible_candidates.py
# because its origin file, candidates_v2_mass_thequint.jsonl, never got
# the promoted_item_id marker. Not a duplicate-promotion risk today
# (promote() and merge_mass_candidates.py both only ever read the main
# file), but it wastes real review time re-flagging an already-settled
# candidate on every future spot-check pass -- fixed by writing the
# marker back to whichever per-pipeline file the ID actually came from.
_SOURCE_FILE_BY_PREFIX = {
    "cand-vishvas-": _DATASET_DIR / "candidates_v2_mass_vishvas.jsonl",
    "cand-factly-": _DATASET_DIR / "candidates_v2_mass_factly.jsonl",
    "cand-thequint-": _DATASET_DIR / "candidates_v2_mass_thequint.jsonl",
    "cand-factcrescendo-": _DATASET_DIR / "candidates_v2_mass_factcrescendo.jsonl",
}


@contextmanager
def _locked_file(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _propagate_promotion_to_source_file(candidate_id: str, item_id: str) -> None:
    source_path = next(
        (path for prefix, path in _SOURCE_FILE_BY_PREFIX.items() if candidate_id.startswith(prefix)), None,
    )
    if source_path is None or not source_path.exists():
        return  # cand-mass-* candidates already live directly in the main, locked file
    with _locked_file(source_path.with_suffix(".lock")):
        with open(source_path) as f:
            records = [json.loads(line) for line in f if line.strip()]
        for rec in records:
            if rec["candidate_id"] == candidate_id:
                rec["promoted_item_id"] = item_id
        with open(source_path, "w") as f:
            for rec in records:
                f.write(json.dumps(rec) + "\n")


async def _ingest(db, source_url: str):
    """Mirrors research/multimodal/run_claim_coverage.py's ingest_item()
    exactly -- real fetch + transcribe/OCR/vision, stopping short of
    claim extraction (not this script's job)."""
    storage = get_storage_client()
    payload = ReelCreate(source_url=source_url, platform="instagram", auto_fetch=True)
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


def _next_item_ids(n: int) -> list[str]:
    existing = set()
    for path, key in ((_ITEMS_V1_PATH, "id"), (_ITEMS_V2_PATH, "item_id")):
        if path.exists():
            with open(path) as f:
                for line in f:
                    if line.strip():
                        existing.add(json.loads(line)[key])
    max_n = max((int(item_id.split("-")[-1]) for item_id in existing), default=0)
    return [f"item-{max_n + i + 1:04d}" for i in range(n)]


async def promote() -> list[dict]:
    candidates = _load_all()
    eligible = [c for c in candidates if c["eligibility_status"] == "ELIGIBLE" and not c.get("promoted_item_id")]
    if not eligible:
        print("No un-promoted ELIGIBLE candidates found.")
        return []

    item_ids = _next_item_ids(len(eligible))
    promoted_items = []

    async with AsyncSessionLocal() as db:
        for candidate, item_id in zip(eligible, item_ids):
            source_url = candidate["social_url"]
            print(f"=== {item_id} ({candidate['candidate_id']}): ingesting real media from {source_url} ===", file=sys.stderr)
            try:
                reel = await _ingest(db, source_url)
            except Exception as exc:  # noqa: BLE001 -- a real ingestion failure is a real, reportable outcome
                print(f"  INGESTION FAILED: {exc}", file=sys.stderr)
                await db.rollback()
                continue

            await db.execute(
                update(Reel)
                .where(Reel.id == reel.id)
                .values(dataset_type=DatasetType.benchmark, benchmark_version="v2", benchmark_split=_TARGET_SPLIT)
            )
            await db.commit()

            print(
                f"  ingested: media_type={reel.media_type.value}, "
                f"transcript_len={len(reel.transcript or '')}, "
                f"ocr_frames={len(reel.ocr_text or [])}, "
                f"has_vision_context={bool(reel.vision_context)}",
                file=sys.stderr,
            )

            v2_item = {
                "item_id": item_id,
                "benchmark_version": "v2",
                "split": _TARGET_SPLIT.value,
                "media": "video" if reel.media_type == MediaType.video else "photo",
                "media_hash": reel.media_content_hash,
                "platform": "instagram",
                "original_url": source_url,
                "factcheck_url": candidate["factcheck_article"],
                "factchecker": candidate["factchecker"],
                "publication_date": candidate.get("publication_date"),
                "factcheck_date": candidate.get("factcheck_date"),
                "ground_truth_label": candidate["ground_truth_label"],
                "ground_truth_claim": candidate["ground_truth_claim"],
                "claim_type": candidate["claim_type"],
                "political_actor": candidate.get("political_actor"),
                "language": candidate.get("language"),
                "audio_available": bool(reel.transcript),
                "ocr_available": bool(reel.ocr_text),
                "caption_available": bool(reel.caption_text),
                "visual_information_available": reel.vision_context is not None,
                "cross_post_possible": True,
                "cross_post_verified": None,  # not yet evaluated for this item -- see MULTIMODAL_EVALUATION.md's discipline of not guessing this
                "difficulty": None,
                "development_split": True,
                "candidate_id": candidate["candidate_id"],  # traceability back to the sourcing record, not part of v1's schema
            }
            promoted_items.append(v2_item)
            # Written immediately (not batched into one save at the end) --
            # this is a short, freshly-reloaded, locked update per
            # candidate, safe against a concurrently-running mass-sourcing
            # pipeline adding new candidates during this loop's real,
            # multi-minute-per-item ingestion work.
            with open(_ITEMS_V2_PATH, "a") as f:
                f.write(json.dumps(v2_item) + "\n")
            set_promoted_item_id(candidate["candidate_id"], item_id)
            _propagate_promotion_to_source_file(candidate["candidate_id"], item_id)

    return promoted_items


async def main() -> None:
    promoted = await promote()
    print(f"\nPromoted {len(promoted)} item(s) to {_ITEMS_V2_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
