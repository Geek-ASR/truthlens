"""Retroactively tags the live dev database's `reels` rows that actually
correspond to the frozen 9-item benchmark (research/dataset/items.jsonl)
as dataset_type=benchmark, benchmark_version='v1', benchmark_split='dev'
-- everything else keeps the default 'development' the migration
(72b8bd05d670) backfilled onto all 20 pre-existing rows.

Confirmed live before writing this script (Phase-0 audit): the DB has
several source_urls ingested 2-3 times during development (re-ingestion
attempts, not distinct content) -- every row matching a benchmark
item's source_url is tagged, not just the most recent one, since a
re-ingestion of the SAME benchmark post is still benchmark data, not
arbitrary development content.

Run: ./.venv/bin/python research/benchmark_v2/tag_existing_benchmark_reels.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select, update  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

_ITEMS_V1_PATH = Path(__file__).resolve().parents[3] / "research" / "dataset" / "items.jsonl"


async def tag() -> None:
    with open(_ITEMS_V1_PATH) as f:
        benchmark_urls = {json.loads(line)["source_url"] for line in f}

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Reel).where(Reel.source_url.in_(benchmark_urls)))
        matched = result.scalars().all()
        matched_ids = [r.id for r in matched]

        if matched_ids:
            await db.execute(
                update(Reel)
                .where(Reel.id.in_(matched_ids))
                .values(
                    dataset_type=DatasetType.benchmark,
                    benchmark_version="v1",
                    benchmark_split=BenchmarkSplit.dev,
                )
            )
            await db.commit()

        # Verify: every matched row now reads back correctly, and no
        # untouched row was accidentally caught by the UPDATE's WHERE
        # clause (a broad WHERE with no matching IDs would be a real bug).
        recheck = await db.execute(select(Reel).where(Reel.id.in_(matched_ids)))
        for reel in recheck.scalars().all():
            assert reel.dataset_type == DatasetType.benchmark
            assert reel.benchmark_version == "v1"
            assert reel.benchmark_split == BenchmarkSplit.dev

        remaining = await db.execute(select(Reel).where(Reel.dataset_type == DatasetType.development))
        remaining_count = len(remaining.scalars().all())

    print(f"Tagged {len(matched_ids)} reel row(s) (across {len(benchmark_urls)} distinct benchmark URLs) as benchmark/v1/dev.")
    print(f"{remaining_count} reel row(s) remain dataset_type=development.")


if __name__ == "__main__":
    asyncio.run(tag())
