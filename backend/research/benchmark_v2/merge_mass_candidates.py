"""Merges candidates_v2_mass_vishvas.jsonl (and any other separate
mass-sourcing output file) into the main candidates_v2.jsonl -- kept as
an explicit, separate step rather than having the parallel pipelines
write directly to the shared file, since a naive full-file
read-modify-write with no coordination could silently drop writes if
another process touches candidates_v2.jsonl at the same moment (the
exact class of bug candidate_tracker.py's own _locked() was built to
fix -- reused here rather than writing the main file unprotected,
since promote_eligible_candidates.py already writes it under this same
lock and this script racing against that would reintroduce the same
failure mode on the shared file specifically).

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.merge_mass_candidates
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from research.benchmark_v2.candidate_tracker import _locked  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAIN_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2.jsonl"
_SOURCES = [
    _REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_vishvas.jsonl",
    _REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_factly.jsonl",
    _REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_thequint.jsonl",
]


def main() -> None:
    with _locked():
        main_candidates = []
        if _MAIN_PATH.exists():
            with open(_MAIN_PATH) as f:
                main_candidates = [json.loads(line) for line in f if line.strip()]
        existing_ids = {c["candidate_id"] for c in main_candidates}

        total_merged = 0
        for source_path in _SOURCES:
            if not source_path.exists():
                continue
            with open(source_path) as f:
                source_candidates = [json.loads(line) for line in f if line.strip()]
            new_ones = [c for c in source_candidates if c["candidate_id"] not in existing_ids]
            for c in new_ones:
                existing_ids.add(c["candidate_id"])
                main_candidates.append(c)
            print(f"{source_path.name}: {len(new_ones)} new / {len(source_candidates)} total", file=sys.stderr)
            total_merged += len(new_ones)

        with open(_MAIN_PATH, "w") as f:
            for c in main_candidates:
                f.write(json.dumps(c) + "\n")

    n_eligible = sum(1 for c in main_candidates if c["eligibility_status"] == "ELIGIBLE" and not c.get("promoted_item_id"))
    print(f"\nMerged {total_merged} new candidate(s) into {_MAIN_PATH}", file=sys.stderr)
    print(f"Total un-promoted ELIGIBLE candidates now: {n_eligible}", file=sys.stderr)


if __name__ == "__main__":
    main()
