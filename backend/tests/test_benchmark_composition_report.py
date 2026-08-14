import json

import pytest

from research.benchmark_v2.composition_report import build_report


@pytest.mark.asyncio
async def test_build_report_counts_fields_and_never_touches_labels(tmp_path):
    path = tmp_path / "items.jsonl"
    items = [
        {
            "item_id": "item-A",
            "original_url": "https://instagram.com/reel/report-test-a",
            "ground_truth_label": "FALSE",
            "claim_type": "provenance",
            "language": "en",
            "media": "video",
            "political_actor": "BJP",
            "cross_post_verified": True,
            "difficulty": None,
            "split": "dev",
        },
        {
            "item_id": "item-B",
            "original_url": "https://instagram.com/reel/report-test-b",
            "ground_truth_label": "TRUE",
            "claim_type": "statistic",
            "language": "hi",
            "media": "photo",
            "political_actor": "Congress",
            "cross_post_verified": None,
            "difficulty": None,
            "split": "test",
        },
    ]
    with open(path, "w") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")

    report = await build_report(path)

    assert report["n"] == 2
    assert report["ground_truth_label"] == {"FALSE": 1, "TRUE": 1}
    assert report["split"] == {"dev": 1, "test": 1}
    # Neither input item's label was ever read back mutated -- the
    # report is purely descriptive.
    assert set(report["ground_truth_label"].keys()) == {"FALSE", "TRUE"}
    # Neither item has a real reel/claims row in the DB -- both should
    # land in "unknown", not be silently miscounted as zero_claims.
    assert report["single_vs_multi_claim"].get("unknown", 0) == 2
