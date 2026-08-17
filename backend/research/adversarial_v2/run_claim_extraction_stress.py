"""EXP-020 (research/RESEARCH_ROADMAP_V2.md Phase 11): a bounded, honest
slice of the full end-to-end adversarial suite Step 18 asks for (20
categories, 100+ cases, whole pipeline). That full build was judged not
achievable in this pass -- several of Step 18's categories (AI-generated
image, edited video, OCR/audio corruption as an INPUT signal problem
rather than a text-content problem) need real external media generation
tooling this project does not have and this pass does not build.

What this script actually does: 6 real, hand-constructed adversarial
TEXT-content cases run through the REAL, unmodified
app.pipeline.claim_extraction.extract_claims() -- the whole-pipeline
requirement satisfied for the one stage this pass covers, not simulated
or mocked. Each case is a synthetic Reel object (transient, never
persisted -- app.db.models.Reel constructed directly, never added to a
session) with deliberately adversarial transcript/OCR/caption content:

1. garbled_ocr: real garbled-OCR shape (fragments of mixed scripts,
   confidence noise) -- does extraction degrade gracefully or hallucinate?
2. caption_transcript_contradiction: caption describes one topic,
   transcript describes something completely unrelated -- does
   extraction conflate them into a false merged claim, or keep them
   distinct?
3. extremely_short: a single-word transcript -- crash or graceful
   near-empty output?
4. mixed_language_chaos: content switching between 3 scripts
   mid-sentence (a real pattern already observed live this session).
5. repetitive_spam: the same phrase repeated 40 times -- does dedup
   (this session's own claim_deduplication work) actually collapse it,
   or does the extractor itself produce 40 near-duplicate claims before
   dedup even runs?
6. near_max_tokens: content sized close to the 8192 max_tokens ceiling
   (this session's own claim_extraction.py change) -- truncation
   behavior.

Each case runs inside a transaction rolled back afterward -- nothing
persisted.

Run: cd backend && ./.venv/bin/python research/adversarial_v2/run_claim_extraction_stress.py
"""
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.db.models import MediaType, Platform, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.claim_extraction import extract_claims  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


def _cases() -> list[dict]:
    return [
        {
            "name": "garbled_ocr",
            "transcript": None,
            "ocr_text": [
                {"frame_ts": 1.0, "text": "य a eo", "confidence": 0.35},
                {"frame_ts": 2.0, "text": "Ufera ch Oz tens che TER AMT", "confidence": 0.3},
                {"frame_ts": 3.0, "text": "%*  &&^ 123 ###", "confidence": 0.2},
            ],
            "caption_text": None,
        },
        {
            "name": "caption_transcript_contradiction",
            "transcript": "Add two cups of flour and mix with the eggs, then bake at 350 degrees for twenty minutes.",
            "ocr_text": None,
            "caption_text": "Massive protest erupts in Delhi as thousands march against new policy #protest #delhi",
        },
        {
            "name": "extremely_short",
            "transcript": "No.",
            "ocr_text": None,
            "caption_text": None,
        },
        {
            "name": "mixed_language_chaos",
            "transcript": (
                "यह एक बहुत ही important announcement है और میں یہ کہنا چاہتا ہوں कि "
                "the government has decided ऐसा करने के लिए کہ سب لوگ خوش رہیں forever."
            ),
            "ocr_text": None,
            "caption_text": None,
        },
        {
            "name": "repetitive_spam",
            "transcript": "This is fake news. " * 40,
            "ocr_text": None,
            "caption_text": None,
        },
        {
            "name": "near_max_tokens",
            "transcript": (
                "The government announced a new policy today that will affect millions of citizens. "
            ) * 150,  # a genuinely long real-shaped transcript, not random noise
            "ocr_text": None,
            "caption_text": None,
        },
    ]


async def main() -> None:
    results = []
    async with AsyncSessionLocal() as db:
        for case in _cases():
            reel = Reel(
                id=uuid.uuid4(),
                source_url=f"https://instagram.com/reel/adversarial-{case['name']}",
                platform=Platform.instagram,
                media_type=MediaType.video,
                transcript=case["transcript"],
                ocr_text=case["ocr_text"],
                caption_text=case["caption_text"],
            )
            db.add(reel)
            await db.flush()

            print(f"=== {case['name']} ===", file=sys.stderr)
            try:
                claims = await extract_claims(db, reel)
                claim_detail = [{"text": c.text, "claim_type": c.claim_type.value, "importance": c.importance} for c in claims]
                outcome = "resolved"
                error = None
                print(f"  -> {len(claims)} claim(s)", file=sys.stderr)
                for c in claim_detail[:5]:
                    print(f"     - {c['text'][:70]!r}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 -- a real crash is a real, reportable outcome
                claim_detail = []
                outcome = "error"
                error = f"{type(exc).__name__}: {exc}"
                print(f"  CRASHED: {error}", file=sys.stderr)
            finally:
                await db.rollback()

            results.append({"case": case["name"], "outcome": outcome, "error": error, "claims": claim_detail})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "adversarial_claim_extraction_stress_20260818.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)
    print(f"\nCrashes: {sum(1 for r in results if r['outcome'] == 'error')}/{len(results)}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
