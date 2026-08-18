"""Deterministic consistency filter applied to every ELIGIBLE,
un-promoted candidate from ANY mass-sourcing pipeline (altnews.in,
vishvasnews.com, factly.in) before promotion -- found live and
necessary: cand-mass-0085's own judge reasoning stated the post's
caption is "unrelated" to the article's claim and "does not directly
address or refute" it, yet the judge still set
is_own_post_the_misinformation=True. Same class of failure this whole
session has repeatedly found in local-model output (a label
confidently contradicting its own stated reasoning,
research/FAILURE_TAXONOMY.md #19's pattern) -- now caught in this
pipeline's own judge step too, not assumed absent just because it's a
different call site.

This is a purely mechanical, keyword-based check (same tradeoff every
other regex/keyword check in this codebase already accepts -- natural
language has unlimited ways to say "this doesn't match," a heuristic
catches the clearest cases, not all of them). A candidate whose
reasoning contains a self-contradiction phrase is downgraded from
ELIGIBLE to UNRESOLVED (not silently dropped, not silently promoted)
for a real second look before promote_eligible_candidates.py ever
touches it.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.spot_check_eligible_candidates
"""
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CANDIDATES_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2.jsonl"

_SELF_CONTRADICTION_PHRASES = (
    "unrelated", "does not directly address", "does not address", "does not refute",
    "does not relate", "no direct connection", "not directly related", "not related to",
    "does not make", "does not assert", "does not claim", "seems unrelated",
    "not the misinformation", "does not appear to", "cannot be considered",
)


def main() -> None:
    if not _CANDIDATES_PATH.exists():
        print("No candidates file found.", file=sys.stderr)
        return

    with open(_CANDIDATES_PATH) as f:
        candidates = [json.loads(line) for line in f if line.strip()]

    n_checked, n_flagged = 0, 0
    for c in candidates:
        if c["eligibility_status"] != "ELIGIBLE" or c.get("promoted_item_id"):
            continue
        n_checked += 1
        # The judge's reasoning lives in the GROUND_TRUTH_VERIFIED history note.
        reasoning = ""
        for h in c.get("history", []):
            if h["status"] == "GROUND_TRUTH_VERIFIED":
                reasoning = h.get("note", "")
        reasoning_lower = reasoning.lower()
        hit_phrases = [p for p in _SELF_CONTRADICTION_PHRASES if p in reasoning_lower]
        if hit_phrases:
            c["eligibility_status"] = "UNRESOLVED"
            c.setdefault("history", []).append({
                "status": "UNRESOLVED",
                "at": "spot_check_eligible_candidates.py",
                "note": f"Downgraded from ELIGIBLE: judge reasoning contains self-contradiction "
                        f"phrase(s) {hit_phrases} while is_own_post_the_misinformation=True. "
                        f"Needs manual review, not auto-promoted.",
            })
            n_flagged += 1
            print(f"FLAGGED {c['candidate_id']}: {hit_phrases} in reasoning: {reasoning[:150]}", file=sys.stderr)

    with open(_CANDIDATES_PATH, "w") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")

    print(f"\nChecked {n_checked} ELIGIBLE candidate(s), flagged {n_flagged} for manual review.", file=sys.stderr)
    print(f"{n_checked - n_flagged} remain ELIGIBLE for promotion.", file=sys.stderr)


if __name__ == "__main__":
    main()
