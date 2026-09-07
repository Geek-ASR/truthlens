"""One-off remediation for all-platform items promoted before the
promote spot-check was hardened (2026-09-07).

Two defects the auto-promoter let through:
  1. ground_truth_label == "UNVERIFIED" -- the sourcing judge failed to
     extract a verdict; the fact-check article DID reach one. We infer a
     best-guess label from the fact-check URL slug and flag the item
     annotation_status="label_inferred_needs_review" -- NOT presented as
     verified.
  2. ground_truth_claim is a raw caption / article paragraph (>22 words
     or article-text phrasing). We keep the item, stash the raw string
     in ground_truth_claim_raw, and flag annotation_status carries
     "claim_needs_rewrite".

Nothing is deleted. Original values are preserved in a per-item
`_remediation_history` list (old -> new, reason, timestamp), per the
dataset brief's "never silently overwrite" rule. Re-runnable / idempotent.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.cleanup_allplatform_items
"""
import json
from datetime import datetime, timezone
from pathlib import Path

_ITEMS = Path(__file__).resolve().parents[3] / "research" / "dataset" / "items_v2.jsonl"

_NEG = ("did-not", "does-not", "didnt", "no-", "-false", "falsely", "fake", "not-",
        "baseless", "unrelated", "scripted", "edited", "old-video", "misattributed",
        "misleading", "out-of-context", "morphed", "ai-generated", "deepfake")
_MISLEADING_HINT = ("misleading", "missing-context", "partly", "half-true", "out-of-context",
                    "old-video", "unrelated")
_LEAK = ("this claim was", "this claim is", "the claim is", "the claim that", "was amplified by",
         "was shared by", "several bjp", "right-wing influencers", "according to the article",
         "as per the article", "yes, that's", "the fact-check")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _infer_label(slug: str) -> str | None:
    s = slug.lower()
    if not any(k in s for k in _NEG):
        return None
    return "MISLEADING" if any(k in s for k in _MISLEADING_HINT) else "FALSE"


def _bad_claim(claim: str) -> str | None:
    c = (claim or "").strip()
    cl = c.lower()
    if len(c.split()) > 22:
        return "claim >22 words -- likely raw caption/article paragraph"
    if any(cl.startswith(p) or f" {p}" in cl[:45] for p in _LEAK):
        return "claim reads as article/verdict text, not the claim itself"
    return None


def main() -> None:
    rows = [json.loads(l) for l in _ITEMS.read_text().splitlines() if l.strip()]
    changed = 0
    for r in rows:
        if not str(r.get("candidate_id", "")).startswith("cand-ap-"):
            continue
        hist = r.setdefault("_remediation_history", [])
        notes = []

        if r.get("ground_truth_label") == "UNVERIFIED":
            inferred = _infer_label(r.get("factcheck_url", ""))
            if inferred:
                hist.append({"field": "ground_truth_label", "old": "UNVERIFIED", "new": inferred,
                             "reason": "sourcing judge returned no verdict; inferred from fact-check URL slug",
                             "at": _now(), "by": "cleanup_allplatform_items.py"})
                r["ground_truth_label"] = inferred
                r["ground_truth_label_inferred"] = True
                notes.append(f"label inferred ({inferred}) from fact-check slug -- NEEDS HUMAN CONFIRMATION")
                changed += 1

        bad = _bad_claim(r.get("ground_truth_claim", ""))
        if bad and "ground_truth_claim_raw" not in r:
            r["ground_truth_claim_raw"] = r.get("ground_truth_claim")
            hist.append({"field": "ground_truth_claim", "old": r.get("ground_truth_claim"),
                         "new": "(unchanged -- flagged for rewrite)", "reason": bad,
                         "at": _now(), "by": "cleanup_allplatform_items.py"})
            notes.append(f"claim flagged for rewrite: {bad}")
            changed += 1

        if notes:
            r["annotation_status"] = "needs_review"
            existing = r.get("ground_truth_notes") or ""
            add = " | ".join(notes)
            r["ground_truth_notes"] = f"{existing} | {add}".strip(" |") if existing else add

    _ITEMS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    flagged = sum(1 for r in rows if r.get("annotation_status") == "needs_review")
    print(f"remediated {changed} field(s); {flagged} item(s) now annotation_status=needs_review")
    from collections import Counter
    print("label distribution now:",
          dict(Counter(r.get("ground_truth_label") for r in rows)))


if __name__ == "__main__":
    main()
