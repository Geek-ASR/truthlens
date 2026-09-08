"""Generates the TruthLens-202 local-only evaluation figures for
research_paper/main.tex from the REAL scored output only
(research/results/local_eval_v2_scores.json, written by
score_local_eval.py, which reads research/results/local_eval_v2.jsonl,
written by run_local_eval.py).

Nothing here is estimated or simulated. If the scores file is absent or
the run is incomplete, this script refuses to draw rather than invent a
shape. Same house style as backend/research/day10_figures.py
(matplotlib Agg, #4C72B0 bars, small IEEE-column figsizes, PDF out).

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.figures_local_eval
Writes PDFs to research_paper/figures/.
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
_SCORES = _ROOT / "research" / "results" / "local_eval_v2_scores.json"
_RESULTS = _ROOT / "research" / "results" / "local_eval_v2.jsonl"
_FIG = _ROOT / "research_paper" / "figures"

plt.rcParams.update({"font.size": 9, "figure.dpi": 150})
_BAR = "#4C72B0"
_BASE = "#888888"
_ACCENT = "#C44E52"


def _save(fig, name: str) -> None:
    _FIG.mkdir(parents=True, exist_ok=True)
    p = _FIG / name
    fig.savefig(p, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {p}")


def fig_outcomes(scores: dict) -> None:
    """Outcome distribution over all scored validation items -- the
    headline story of the local-only config is how large the
    no_verifiable_claims slice is."""
    oc = scores["outcome_distribution"]
    order = ["resolved", "no_verifiable_claims", "research_failed", "error"]
    labels = ["resolved", "no verifiable\nclaim", "research\nfailed", "error"]
    vals = [oc.get(k, 0) for k in order]
    total = sum(vals)
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    bars = ax.bar(range(len(labels)), vals, width=0.6, color=[_BAR, _ACCENT, _BASE, _BASE])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + total * 0.012,
                f"{v}\n{v / total * 100:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(labels)), labels, fontsize=8)
    ax.set_ylabel("validation items")
    ax.set_ylim(0, max(vals) * 1.28)
    ax.set_title(f"Local-only pipeline outcome (n={total})", fontsize=9)
    _save(fig, "fig9_local_eval_outcomes.pdf")


def fig_confusion(scores: dict) -> None:
    cm = scores["confusion_matrix"]  # gt_bucket -> {pred_bucket: n}
    gt_rows = ["FALSE", "MISLEADING", "TRUE"]
    pred_cols = ["FALSE", "MISLEADING", "TRUE", "UNVERIFIED"]
    mat = [[cm.get(g, {}).get(p, 0) for p in pred_cols] for g in gt_rows]
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    im = ax.imshow(mat, cmap="Blues", aspect="auto")
    ax.set_xticks(range(len(pred_cols)), pred_cols, fontsize=7.5)
    ax.set_yticks(range(len(gt_rows)), gt_rows, fontsize=7.5)
    ax.set_xlabel("predicted bucket")
    ax.set_ylabel("ground-truth bucket")
    mx = max((max(r) for r in mat), default=0)
    for i, r in enumerate(mat):
        for j, v in enumerate(r):
            ax.text(j, i, str(v), ha="center", va="center",
                    color="white" if v > mx * 0.55 else "black", fontsize=8)
    ax.set_title("Confusion matrix (resolved items)", fontsize=9)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    _save(fig, "fig10_local_eval_confusion.pdf")


def fig_perclass(scores: dict) -> None:
    pc = scores["per_class"]
    labs = [l for l in ["FALSE", "MOSTLY_FALSE", "MISLEADING", "MOSTLY_TRUE", "TRUE", "UNVERIFIED"]
            if l in pc and (pc[l]["support"] > 0 or pc[l]["tp"] + pc[l]["fp"] > 0)]
    prec = [pc[l]["precision"] for l in labs]
    rec = [pc[l]["recall"] for l in labs]
    f1 = [pc[l]["f1"] for l in labs]
    x = range(len(labs))
    w = 0.26
    fig, ax = plt.subplots(figsize=(4.6, 2.8))
    ax.bar([i - w for i in x], prec, w, label="precision", color=_BAR)
    ax.bar(list(x), rec, w, label="recall", color=_ACCENT)
    ax.bar([i + w for i in x], f1, w, label="F1", color=_BASE)
    ax.set_xticks(list(x), labs, rotation=30, ha="right", fontsize=7.5)
    ax.set_ylim(0, 1)
    ax.set_ylabel("score")
    ax.legend(fontsize=7, loc="upper right")
    ax.set_title(f"Per-class performance (macro-F1={scores['macro_f1']:.2f})", fontsize=9)
    _save(fig, "fig11_local_eval_perclass_f1.pdf")


def fig_by_vision() -> None:
    """Accuracy split by whether vision_context was available -- speaks
    to the 'deferred visual analysis on 115 items' limitation."""
    if not _RESULTS.exists():
        return
    rows = [json.loads(l) for l in _RESULTS.read_text().splitlines() if l.strip()]
    bk = {"TRUE": "T", "MOSTLY_TRUE": "T", "FALSE": "F", "MOSTLY_FALSE": "F",
          "MISLEADING": "M", "MISSING_CONTEXT": "M", "OUTDATED": "M", "UNVERIFIED": "U"}
    groups = {True: [0, 0], False: [0, 0]}
    for r in rows:
        if r.get("outcome_type") != "resolved":
            continue
        v = r.get("vision_context_available")
        if v not in (True, False):
            continue
        groups[v][0] += 1
        if bk.get((r.get("predicted_label") or "").upper()) == bk.get((r.get("ground_truth_label") or "").upper()):
            groups[v][1] += 1
    labels = [f"vision context\navailable\n(n={groups[True][0]})", f"no vision\ncontext\n(n={groups[False][0]})"]
    accs = [(groups[True][1] / groups[True][0] * 100) if groups[True][0] else 0,
            (groups[False][1] / groups[False][0] * 100) if groups[False][0] else 0]
    fig, ax = plt.subplots(figsize=(3.0, 2.8))
    bars = ax.bar(labels, accs, color=[_BAR, _BASE])
    for b, a in zip(bars, accs):
        ax.text(b.get_x() + b.get_width() / 2, a + 1, f"{a:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("bucketed accuracy (resolved)")
    ax.set_ylim(0, max(accs + [10]) * 1.3)
    ax.set_title("Accuracy by vision-context availability", fontsize=9)
    ax.tick_params(axis="x", labelsize=7.5)
    _save(fig, "fig12_local_eval_by_vision.pdf")


def main() -> None:
    if not _SCORES.exists():
        sys.exit(f"{_SCORES} not found -- run score_local_eval.py first (after run_local_eval.py completes).")
    scores = json.loads(_SCORES.read_text())
    acc = scores.get("accuracy", {})
    n_res = acc.get("n_resolved", 0)
    if n_res < 20:
        print(f"WARNING: only {n_res} resolved items -- figures will be drawn but are not yet meaningful.", file=sys.stderr)
    fig_outcomes(scores)
    fig_confusion(scores)
    fig_perclass(scores)
    fig_by_vision()
    print("done.")


if __name__ == "__main__":
    main()
