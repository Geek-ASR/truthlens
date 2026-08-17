"""Failure taxonomy entry #21 (research_paper/main.tex Appendix,
research/FAILURE_TAXONOMY.md): research/day8_final_tables.py reused the
same two variable names (k, n) across three separate computations --
Table 1's full-TruthLens row, a per-baseline loop building Table 2, and
Table 3's decomposition ablation -- each printed correctly to stdout
immediately after being computed, but the summary JSON was assembled at
the end of the function from whatever those two names last held,
silently combining one table's counts with another's into a
fabricated-looking result that appeared nowhere in the script's own
printed tables.

The fix (distinctly-named variables per computation: full_tl_k/full_tl_n,
pk/pn inside the per-baseline loop, single_k/multi_k/decomp_n, ck/cn) is
already in the current script -- this file is the regression test that
was still missing, per PHASE1_COMPLETION_REPORT.md's own disclosed gap.
It reproduces the bug's exact shape with synthetic fixtures sized so any
cross-table variable bleed is immediately obvious (Table 1's
full-TruthLens n/k are deliberately different from every other table's),
runs the real, unmodified main() against them (loaded via importlib
from research/day8_final_tables.py, which lives outside any importable
Python package), and asserts the written summary's
table1_all_9_items.full_truthlens_n6 entry matches Table 1's own real
data, not any other table's."""
import importlib.util
import json
from pathlib import Path

_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "research" / "day8_final_tables.py"


def _load_day8_module():
    spec = importlib.util.spec_from_file_location("day8_final_tables_under_test", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_fixtures(results_dir: Path) -> None:
    # Table 1/2 baselines -- deliberately small, n=2 each, so their
    # counts can never accidentally equal Table 1's full-TruthLens or
    # Table 3's decomposition counts below.
    baseline_row = lambda item_id, pred, gt: {"item_id": item_id, "predicted_label": pred, "ground_truth_label": gt}
    for filename in (
        "baseline_llm_only_20260813T091300Z.jsonl",
        "baseline_search_llm_20260813T090758Z.jsonl",
        "baseline_search_rag_llm_20260813T091225Z.jsonl",
    ):
        rows = [baseline_row("item-0001", "FALSE", "FALSE"), baseline_row("item-0002", "TRUE", "FALSE")]
        (results_dir / filename).write_text("\n".join(json.dumps(r) for r in rows))

    # Table 1's full-TruthLens data: deliberately n=4, 3 correct -- the
    # exact real historical bug's own fabricated numbers
    # (research_paper/main.tex Appendix names "full_truthlens_n6: {n: 4,
    # correct: 3}" as the wrong, silently-substituted value), used here
    # on purpose so a regression would reproduce that exact wrong shape.
    full_tl = [
        {"item_id": "item-0001", "ground_truth": "FALSE", "full_truthlens_label": "FALSE"},
        {"item_id": "item-0002", "ground_truth": "FALSE", "full_truthlens_label": "FALSE"},
        {"item_id": "item-0004", "ground_truth": "TRUE", "full_truthlens_label": "TRUE"},
        {"item_id": "item-0005", "ground_truth": "MISLEADING", "full_truthlens_label": "FALSE"},
    ]
    (results_dir / "full_truthlens_reel_level_day8.json").write_text(json.dumps(full_tl))

    # Table 3's decomposition data: deliberately a DIFFERENT n (6) and
    # DIFFERENT correct count (5) than Table 1's full-TruthLens data
    # above -- the original bug substituted exactly this table's counts
    # into Table 1's summary entry.
    decomp = [
        {
            "item_id": f"item-000{i}", "n_claims": 2, "ground_truth": "FALSE",
            "single_claim_label": "FALSE", "single_claim_match": True,
            "multi_claim_label": "FALSE", "multi_claim_match": i != 6,  # 5 of 6 match
        }
        for i in range(1, 7)
    ]
    (results_dir / "claim_decomposition_ablation.json").write_text(json.dumps(decomp))


def test_summary_json_full_truthlens_entry_matches_table1_not_table3(tmp_path, monkeypatch, capsys):
    _write_fixtures(tmp_path)
    module = _load_day8_module()
    monkeypatch.setattr(module, "RESULTS_DIR", tmp_path)

    module.main()
    capsys.readouterr()  # discard stdout -- this test checks the persisted artifact, not the print output

    summary = json.loads((tmp_path / "day8_summary.json").read_text())
    full_tl_entry = summary["table1_all_9_items"]["full_truthlens_n6"]

    # The real, correct values from the Table 1 fixture above (3 correct
    # of 4) -- NOT Table 3's decomposition counts (5 of 6), which is
    # exactly what the original bug silently substituted instead.
    assert full_tl_entry == {"n": 4, "correct": 3}, (
        f"full_truthlens_n6 entry is {full_tl_entry}, expected {{'n': 4, 'correct': 3}} "
        "(Table 1's own real data) -- if this is {'n': 6, 'correct': 5} instead, "
        "Table 3's decomposition-ablation variables have silently leaked into "
        "Table 1's summary entry, exactly reproducing failure taxonomy entry #21."
    )
