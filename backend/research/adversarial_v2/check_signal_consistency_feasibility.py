"""EXP-022 (research_paper/main.tex Future Work item 12, named after
EXP-020's caption/transcript-contradiction finding): is a cheap,
deterministic, keyword-overlap check for caption/transcript topical
consistency actually feasible against this project's REAL data?

Real, decisive negative result, computed before any check was written
into production (calibrate against real data first, not assumed):
Jaccard similarity of stopword-filtered keywords between caption_text
and transcript, across every real benchmark reel with both fields
populated, is 0.000 -- for ALL FOUR real, legitimate, non-adversarial
reels checked. This is not because these reels are actually
inconsistent; it's because captions and transcripts are fundamentally
different text registers (a short hashtag-heavy caption vs. spoken
words) and, in this dataset, very often different LANGUAGES entirely
(a Hindi/Marathi spoken transcript under an English caption, or vice
versa) even when they describe the exact same event.

A naive keyword-overlap check calibrated on this project's own real
data would flag 100% of genuinely consistent real content as
"inconsistent" -- actively harmful if shipped, not just unhelpful.
Building this check would need real semantic understanding (a local
embedding model or an LLM judgment), not a cheap deterministic
heuristic -- a real, disclosed scope escalation, not attempted this
pass given other higher-value, more tractable open items.

Run: cd backend && ./.venv/bin/python research/adversarial_v2/check_signal_consistency_feasibility.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import DatasetType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"

_STOPWORDS = set(
    "the a an is are was were be been being to of in on at for with and or but not this "
    "that these those i you he she it we they my your his her its our their as by from up "
    "down out about into over after before again further then once here there all any both "
    "each few more most other some such no nor only own same so than too very s t can will "
    "just don should now".split()
)


def _keywords(text: str | None) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


async def main() -> None:
    results = []
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reel.source_url, Reel.caption_text, Reel.transcript)
            .where(Reel.dataset_type == DatasetType.benchmark)
        )
        seen = set()
        for url, caption, transcript in result.all():
            if url in seen:
                continue
            seen.add(url)
            if not caption or not transcript:
                continue
            kc, kt = _keywords(caption), _keywords(transcript)
            if not kc or not kt:
                continue
            jaccard = len(kc & kt) / len(kc | kt)
            results.append({
                "source_url": url,
                "jaccard": jaccard,
                "caption_keywords": sorted(kc),
                "transcript_keywords": sorted(kt),
                "shared": sorted(kc & kt),
            })
            print(f"{jaccard:.3f} | shared={len(kc & kt)} | {url}", file=sys.stderr)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "signal_consistency_feasibility_20260818.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))

    max_jaccard = max((r["jaccard"] for r in results), default=None)
    print(f"\nn={len(results)} real reels checked, max Jaccard similarity = {max_jaccard}", file=sys.stderr)
    print("CONCLUSION: keyword-overlap is not viable -- would flag legitimate content as inconsistent." if (max_jaccard == 0.0) else "Some signal found -- worth further investigation.", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
