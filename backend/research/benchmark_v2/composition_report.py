"""Benchmark composition/diversity report (governing brief Step 6).
Reads a dataset file in the v2 schema (research/DATASET_SCHEMA_V2.md)
and reports label/claim-type/language/media/modality/political-actor/
single-vs-multi-claim/cross-post distributions. Never changes a label —
purely descriptive, to make imbalance visible, not to fix it.

single_vs_multi_claim is queried live against the real `claims` table
(joined via each item's original_url -> reels.source_url), not
estimated, since the real per-item claim count already exists and
guessing would risk quietly contradicting it.

Run: ./.venv/bin/python research/benchmark_v2/composition_report.py [path-to-jsonl]
Defaults to research/dataset/items_v1_as_v2_schema.jsonl.
"""
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import func, select  # noqa: E402

from app.db.models import Claim, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "research" / "dataset" / "items_v1_as_v2_schema.jsonl"


async def _claim_count_for(db, original_url: str) -> int | None:
    # Checked as two queries, deliberately: a single JOIN+count collapses
    # "no reel row exists for this URL" and "the reel exists with zero
    # extracted claims" into the same count=0 result -- those are two
    # different, non-interchangeable facts (item-0003's never-ingested
    # status vs. item-0006/0007's real zero-verifiable-claim extractions
    # are exactly this distinction in the real dataset) and conflating
    # them would silently misreport which.
    reel_result = await db.execute(select(Reel.id).where(Reel.source_url == original_url).limit(1))
    reel_id = reel_result.scalar_one_or_none()
    if reel_id is None:
        return None
    count_result = await db.execute(select(func.count(Claim.id)).where(Claim.reel_id == reel_id))
    return count_result.scalar_one()


async def build_report(path: Path) -> dict:
    with open(path) as f:
        items = [json.loads(line) for line in f]

    counters = {
        "ground_truth_label": Counter(),
        "claim_type": Counter(),
        "language": Counter(),
        "media": Counter(),
        "political_actor": Counter(),
        "cross_post_verified": Counter(),
        "difficulty": Counter(),
        "split": Counter(),
    }
    single_vs_multi = Counter()

    async with AsyncSessionLocal() as db:
        for item in items:
            for field_name, counter in counters.items():
                counter[str(item.get(field_name))] += 1

            claim_count = await _claim_count_for(db, item["original_url"])
            if claim_count == 0:
                single_vs_multi["zero_claims"] += 1
            elif claim_count == 1:
                single_vs_multi["single_claim"] += 1
            elif claim_count and claim_count > 1:
                single_vs_multi["multi_claim"] += 1
            else:
                single_vs_multi["unknown"] += 1

    return {
        "n": len(items),
        **{name: dict(counter) for name, counter in counters.items()},
        "single_vs_multi_claim": dict(single_vs_multi),
    }


def _print_report(report: dict) -> None:
    print(f"n = {report['n']}")
    for key, value in report.items():
        if key == "n":
            continue
        print(f"\n{key}:")
        for label, count in sorted(value.items(), key=lambda kv: -kv[1]):
            print(f"  {label}: {count}")


async def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_PATH
    report = await build_report(path)
    _print_report(report)


if __name__ == "__main__":
    asyncio.run(main())
