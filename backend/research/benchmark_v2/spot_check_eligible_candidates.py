"""Deterministic consistency filter applied to every ELIGIBLE,
un-promoted candidate from ANY mass-sourcing pipeline (altnews.in,
vishvasnews.com, factly.in) before promotion.

Two real failure classes found live, both now checked:

1. Self-contradicting reasoning (cand-mass-0085): the judge's own
   reasoning stated the post's caption is "unrelated" to the article's
   claim and "does not directly address or refute" it, yet still set
   is_own_post_the_misinformation=True. Same class of failure this
   whole session has repeatedly found in local-model output (a label
   confidently contradicting its own stated reasoning,
   research/FAILURE_TAXONOMY.md #19's pattern).
2. Empty reasoning paired with a hallucinated claim (cand-mass-0124):
   confidence=1.00, reasoning="" (the substantiveness retry in _judge()
   fired but still came back empty), and the extracted claim ("a woman
   was raped and killed in Jharkhand") turned out, on direct
   verification against the real post caption via yt-dlp, to have
   NOTHING to do with the actual post content ("Upcoming mising full
   movie - Lujeg BTS..") -- a real hallucination, not just a borderline
   judgment call. A companion case (cand-vishvas-0064) had a non-empty
   but visibly broken response (ground_truth_claim containing a raw
   markdown link instead of a claim sentence, empty ground_truth_label,
   hedging reasoning) that this script also now flags via the same
   "does the output look well-formed" checks.

Both are purely mechanical checks (same tradeoff every other regex/
keyword check in this codebase already accepts -- natural language has
unlimited ways to produce bad output; a heuristic catches the clearest
cases, not all of them). Any candidate this script flags is downgraded
from ELIGIBLE to UNRESOLVED (not silently dropped, not silently
promoted) for a real second look before promote_eligible_candidates.py
ever touches it. This does NOT replace manually verifying a sample
against the real source -- it catches the mechanically-detectable
subset of a broader reliability problem.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.spot_check_eligible_candidates
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from research.benchmark_v2.candidate_tracker import _locked  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAIN_CANDIDATES_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2.jsonl"
# (path, needs_locking) -- the main file is concurrently written by a
# still-running mass-sourcing pipeline (needs the same cross-process
# lock candidate_tracker.py uses); the others are each written by only
# one single-process pipeline apiece, so no lock is needed for them.
_ALL_FILES = [
    (_MAIN_CANDIDATES_PATH, True),
    (_REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_vishvas.jsonl", False),
    (_REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_factly.jsonl", False),
]

_SELF_CONTRADICTION_PHRASES = (
    "unrelated", "does not directly address", "does not address", "does not refute",
    "does not relate", "no direct connection", "not directly related", "not related to",
    "does not make", "does not assert", "does not claim", "seems unrelated",
    "not the misinformation", "does not appear to", "cannot be considered",
)
_HEDGING_PHRASES = (
    "no clear evidence", "might have been", "could just be", "not necessarily",
    "unclear whether", "hard to say", "not certain",
)
_MARKDOWN_LINK_PATTERN = re.compile(r"\[.*?\]\(https?://")


def _find_flag_reason(c: dict) -> str | None:
    reasoning = ""
    for h in c.get("history", []):
        if h["status"] in ("GROUND_TRUTH_VERIFIED", "ELIGIBLE") and h.get("note"):
            reasoning = h["note"]
    reasoning_lower = reasoning.lower()

    hit_contradiction = [p for p in _SELF_CONTRADICTION_PHRASES if p in reasoning_lower]
    if hit_contradiction:
        return f"self-contradicting reasoning {hit_contradiction}"

    hit_hedging = [p for p in _HEDGING_PHRASES if p in reasoning_lower]
    if hit_hedging:
        return f"hedging reasoning {hit_hedging}"

    claim = (c.get("ground_truth_claim") or "").strip()
    label = (c.get("ground_truth_label") or "").strip()
    if not claim or _MARKDOWN_LINK_PATTERN.search(claim):
        return "malformed ground_truth_claim (empty or contains a raw link instead of a claim sentence)"
    if not label:
        return "empty ground_truth_label"
    if not reasoning.strip():
        return "empty reasoning (schema-valid but substantively empty -- cannot be verified without checking the real source directly)"

    return None


def _process_file(path: Path, needs_lock: bool) -> tuple[int, int]:
    if not path.exists():
        return 0, 0

    def _do() -> tuple[int, int]:
        with open(path) as f:
            candidates = [json.loads(line) for line in f if line.strip()]

        n_checked, n_flagged = 0, 0
        for c in candidates:
            if c["eligibility_status"] != "ELIGIBLE" or c.get("promoted_item_id"):
                continue
            n_checked += 1
            reason = _find_flag_reason(c)
            if reason:
                c["eligibility_status"] = "UNRESOLVED"
                c["rejection_reason"] = f"Auto-flagged by spot_check_eligible_candidates.py: {reason}"
                c.setdefault("history", []).append({
                    "status": "UNRESOLVED", "at": "spot_check_eligible_candidates.py",
                    "note": f"Downgraded from ELIGIBLE: {reason}. Needs manual review, not auto-promoted.",
                })
                n_flagged += 1
                print(f"  FLAGGED {c['candidate_id']} ({path.name}): {reason}", file=sys.stderr)

        with open(path, "w") as f:
            for c in candidates:
                f.write(json.dumps(c) + "\n")
        return n_checked, n_flagged

    if needs_lock:
        with _locked():
            return _do()
    return _do()


def main() -> None:
    total_checked, total_flagged = 0, 0
    for path, needs_lock in _ALL_FILES:
        print(f"=== {path.name} ===", file=sys.stderr)
        checked, flagged = _process_file(path, needs_lock)
        total_checked += checked
        total_flagged += flagged

    print(f"\nChecked {total_checked} ELIGIBLE candidate(s) across all sources, flagged {total_flagged} for manual review.", file=sys.stderr)
    print(f"{total_checked - total_flagged} remain ELIGIBLE for promotion.", file=sys.stderr)


if __name__ == "__main__":
    main()
