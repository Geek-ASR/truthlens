"""Review-gated promotion, step 1 of 2.

Assembles a human-review packet for un-promoted all-platform candidates:
for each, the fact-check article's extracted text + the post's real
caption/uploader (re-fetched via yt-dlp, never inferred) + the sourcing
judge's guess (clearly marked as a machine guess, NOT ground truth).

Writes research/dataset/review_batch.jsonl with the context fields
filled and the review fields BLANK, for a human to complete:

    reviewed_claim      <- one clean standalone claim sentence
    reviewed_label      <- FALSE | MOSTLY_FALSE | MISLEADING | MISSING_CONTEXT
                           | TRUE | MOSTLY_TRUE | UNVERIFIED | OUTDATED
    label_evidence      <- short quote/paraphrase from the article that
                           establishes the verdict (the "why", per the brief)
    claim_type          <- provenance | event | numeric | quote | attribution | ...
    political_actor     <- main entity, or null
    language            <- ISO code of the claim/caption
    decision            <- promote | reject | defer
    review_notes        <- anything worth recording

Then run promote_from_review.py to ingest the decision==promote rows
using the HUMAN fields (not the judge's).

Idempotent: never re-adds a candidate already in review_batch.jsonl or
already promoted. YouTube is skipped (download 403s without auth).

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.build_review_batch --n 12
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import httpx
import trafilatura

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

_YT_DLP = str(Path(sys.prefix) / "bin" / "yt-dlp")
_DS = Path(__file__).resolve().parents[3] / "research" / "dataset"
_REVIEW = _DS / "review_batch.jsonl"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

_REVIEW_BLANKS = {
    "reviewed_claim": "", "reviewed_label": "", "label_evidence": "",
    "claim_type": "", "political_actor": "", "language": "", "decision": "",
    "review_notes": "",
}


def _existing_review_ids() -> set[str]:
    if not _REVIEW.exists():
        return set()
    return {json.loads(l)["candidate_id"] for l in _REVIEW.read_text().splitlines() if l.strip()}


def _un_promoted_candidates() -> list[dict]:
    out = []
    for f in sorted(_DS.glob("candidates_v3_*.jsonl")):
        for line in f.read_text().splitlines():
            if not line.strip() or "cand-ap-" not in line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("promoted_item_id") or r["eligibility_status"] not in ("ELIGIBLE", "UNRESOLVED"):
                continue
            r["_file"] = f.name
            out.append(r)
    # ELIGIBLE before UNRESOLVED; X/facebook before youtube; higher judge conf first
    order = {"ELIGIBLE": 0, "UNRESOLVED": 1}
    plat = {"x": 0, "facebook": 0, "instagram": 0, "tiktok": 0, "youtube": 9}
    out.sort(key=lambda r: (order.get(r["eligibility_status"], 2), plat.get(r["platform"], 5),
                            -(r.get("judge_confidence") or 0)))
    return out


def _fetch_article(url: str) -> str:
    try:
        with httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent": _UA}) as c:
            html = c.get(url).text
        return (trafilatura.extract(html, include_comments=False, include_tables=False) or "")[:2800]
    except Exception as exc:  # noqa: BLE001
        return f"(could not fetch article: {type(exc).__name__})"


def _fetch_caption(url: str) -> tuple[str, str]:
    try:
        p = subprocess.run(
            [_YT_DLP, "--simulate", "--no-warnings", "-R", "1", "--socket-timeout", "8",
             "--extractor-args", "twitter:api=syndication",
             "--print", "%(description)s|||%(uploader)s"],
            capture_output=True, text=True, timeout=40, input="", check=False,
        )
        if "|||" in p.stdout:
            cap, up = p.stdout.strip().split("|||", 1)
            return cap.strip()[:1500], up.strip()
    except Exception:  # noqa: BLE001
        pass
    return "", ""


def _judge_reasoning(cand: dict) -> str:
    for h in cand.get("history", []):
        if h.get("status") == "GROUND_TRUTH_VERIFIED" and h.get("note"):
            return h["note"]
    return cand.get("rejection_reason") or ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--include-youtube", action="store_true")
    args = ap.parse_args()

    done = _existing_review_ids()
    pool = [c for c in _un_promoted_candidates() if c["candidate_id"] not in done]
    if not args.include_youtube:
        pool = [c for c in pool if c["platform"] != "youtube"]
    batch = pool[: args.n]
    if not batch:
        print("Nothing left to add to the review batch.")
        return

    with open(_REVIEW, "a") as f:
        for c in batch:
            url = c["social_url"]
            print(f"  fetching {c['candidate_id']} ({c['platform']}) ...", file=sys.stderr, flush=True)
            cap, uploader = _fetch_caption(url)
            rec = {
                "candidate_id": c["candidate_id"], "source_file": c["_file"],
                "platform": c["platform"], "social_url": url,
                "factcheck_url": c["factcheck_article"], "factchecker": c["factchecker"],
                "post_uploader": uploader, "post_caption": cap or "(no caption retrieved)",
                "factcheck_excerpt": _fetch_article(c["factcheck_article"]),
                "MACHINE_GUESS_claim": c.get("ground_truth_claim"),
                "MACHINE_GUESS_label": c.get("ground_truth_label"),
                "MACHINE_GUESS_confidence": c.get("judge_confidence"),
                "machine_judge_reasoning": _judge_reasoning(c),
                "prior_eligibility_status": c["eligibility_status"],
                **_REVIEW_BLANKS,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Added {len(batch)} record(s) to {_REVIEW}  (total now {len(done) + len(batch)})")
    print("Next: fill reviewed_claim / reviewed_label / label_evidence / claim_type / decision, "
          "then run promote_from_review.py")


if __name__ == "__main__":
    main()
