"""research/MASS_SOURCING_V2.md's promote_eligible_candidates.py --
covers _propagate_promotion_to_source_file only (the real ingestion
path needs a live DB/Ollama and is exercised live, not here).

Found live: set_promoted_item_id() only ever writes the shared, merged
candidates_v2.jsonl -- a candidate sourced from the Vishvas/Factly/
thequint pipelines also exists as a separate, un-marked copy in its own
per-pipeline file (merge_mass_candidates.py copies records, it doesn't
move them), so that copy kept showing up as "still eligible" in every
future spot-check pass even after real promotion. This is what
_propagate_promotion_to_source_file backfills."""
import json

import pytest

from research.benchmark_v2 import promote_eligible_candidates as mod


@pytest.fixture(autouse=True)
def _isolate_dataset_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_DATASET_DIR", tmp_path)
    monkeypatch.setattr(mod, "_SOURCE_FILE_BY_PREFIX", {
        "cand-vishvas-": tmp_path / "candidates_v2_mass_vishvas.jsonl",
        "cand-factly-": tmp_path / "candidates_v2_mass_factly.jsonl",
        "cand-thequint-": tmp_path / "candidates_v2_mass_thequint.jsonl",
    })
    yield tmp_path


def _write_jsonl(path, records):
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def test_backfills_promoted_item_id_onto_the_originating_source_file(tmp_path):
    source_path = tmp_path / "candidates_v2_mass_thequint.jsonl"
    _write_jsonl(source_path, [
        {"candidate_id": "cand-thequint-0001", "eligibility_status": "ELIGIBLE"},
        {"candidate_id": "cand-thequint-0002", "eligibility_status": "REJECTED"},
    ])

    mod._propagate_promotion_to_source_file("cand-thequint-0001", "item-0099")

    records = _read_jsonl(source_path)
    promoted = next(r for r in records if r["candidate_id"] == "cand-thequint-0001")
    untouched = next(r for r in records if r["candidate_id"] == "cand-thequint-0002")
    assert promoted["promoted_item_id"] == "item-0099"
    assert "promoted_item_id" not in untouched


def test_is_a_no_op_for_alt_news_candidates_already_in_the_main_file(tmp_path):
    # cand-mass-* candidates live directly in candidates_v2.jsonl, which
    # set_promoted_item_id() already updates -- there's no separate
    # per-pipeline source file for this prefix, and this must not raise.
    mod._propagate_promotion_to_source_file("cand-mass-0001", "item-0099")


def test_is_a_no_op_when_the_source_file_does_not_exist_yet(tmp_path):
    # e.g. Factly was deprioritized and its file may never have been created.
    mod._propagate_promotion_to_source_file("cand-factly-0001", "item-0099")
