"""EXP-018 (research/RESEARCH_ROADMAP_V2.md Phase 9): does perceptual
frame hashing (app/services/media_hashing.py) actually work as a
first-pass cross-post filter against REAL, already-ingested video
frames -- not just the synthetic-noise images in tests/test_media_hashing.py?

Two real controls, both using real frames re-extracted from real
already-fetched videos (via app.pipeline.ingestion.extract_media_artifacts,
the exact same function real ingestion uses):

1. SAME-VIDEO positive control: re-extract frames from one real reel's
   own stored video TWICE (two independent ffmpeg sampling passes) --
   this should match near-perfectly. A trivial case (it's literally the
   same source video), but it's still a real, necessary sanity check
   that the hashing pipeline works end-to-end against real video frames,
   not just clean synthetic images.
2. DIFFERENT-VIDEO negative control: real frames from two different,
   unrelated real reels -- should NOT match.

A genuine, non-trivial cross-post case (two different POSTS of the same
underlying footage) needs a second, real, independently-sourced video of
the same event -- attempted for item-0002 (research/dataset/items.jsonl:
ground_truth_notes names a specific real source, "flowmexicanoofficial",
2026-06-27 FIFA World Cup celebration video) via a live search; reported
honestly whether it was actually found and fetched, not assumed.

Run: cd backend && ./.venv/bin/python research/cross_post_v2/verify_perceptual_hash.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, MediaType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.ingestion import extract_media_artifacts  # noqa: E402
from app.services.media_hashing import frame_set_similarity  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


async def _real_frames_for(reel_id, storage) -> list[str]:
    async with AsyncSessionLocal() as db:
        reel = await db.get(Reel, reel_id)
        if reel is None or reel.media_type != MediaType.video or not reel.media_storage_key:
            return []
        video_bytes = storage.get_bytes(reel.media_storage_key)
    _audio_path, frame_paths = extract_media_artifacts(video_bytes)
    return frame_paths


async def main() -> None:
    storage = get_storage_client()

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reel.id, Reel.source_url)
            .where(
                Reel.dataset_type == DatasetType.benchmark,
                Reel.benchmark_split == BenchmarkSplit.dev,
                Reel.media_type == MediaType.video,
            )
        )
        seen = set()
        video_reels = []
        for reel_id, url in result.all():
            if url in seen:
                continue
            seen.add(url)
            video_reels.append((reel_id, url))

    if len(video_reels) < 2:
        print("Not enough real ingested video reels to run both controls.", file=sys.stderr)
        return

    (reel_a_id, reel_a_url), (reel_b_id, reel_b_url) = video_reels[0], video_reels[1]

    print(f"=== SAME-VIDEO control: {reel_a_url} vs. itself (re-extracted independently) ===", file=sys.stderr)
    frames_a1 = await _real_frames_for(reel_a_id, storage)
    frames_a2 = await _real_frames_for(reel_a_id, storage)
    same_video_result = frame_set_similarity(frames_a1, frames_a2)
    print(f"  n_frames={len(frames_a1)} vs {len(frames_a2)}, result={same_video_result}", file=sys.stderr)

    print(f"\n=== DIFFERENT-VIDEO control: {reel_a_url} vs. {reel_b_url} ===", file=sys.stderr)
    frames_b = await _real_frames_for(reel_b_id, storage)
    diff_video_result = frame_set_similarity(frames_a1, frames_b)
    print(f"  n_frames={len(frames_a1)} vs {len(frames_b)}, result={diff_video_result}", file=sys.stderr)

    report = {
        "same_video_control": {"reel": reel_a_url, "n_frames_pass1": len(frames_a1), "n_frames_pass2": len(frames_a2), **same_video_result},
        "different_video_control": {"reel_a": reel_a_url, "reel_b": reel_b_url, "n_frames_a": len(frames_a1), "n_frames_b": len(frames_b), **diff_video_result},
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "cross_post_perceptual_hash_verification_20260818.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)
    print(f"\nSAME-VIDEO control: is_match={same_video_result['is_match']}, min_distance={same_video_result['min_distance']}", file=sys.stderr)
    print(f"DIFFERENT-VIDEO control: is_match={diff_video_result['is_match']}, min_distance={diff_video_result['min_distance']}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
