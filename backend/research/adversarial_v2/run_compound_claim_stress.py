"""EXP-031 (research/RESEARCH_ROADMAP_V2.md Phase 11, Step 18 category
#19 "multiple claims" -- not yet covered by this session's other
adversarial work). CLAIM_EXTRACTION_SYSTEM_PROMPT already instructs the
model: "Compound statements (e.g. 'X happened, and because of it Y
happened') must be split into separate atomic claims, since causation
itself is a separate claim from each half of the sentence." This has
never been specifically stress-tested with adversarial compound
sentences beyond that one prompt example.

6 real cases (synthetic, unpersisted Reel transcripts), run through the
real, unmodified claim_extraction.extract_claims(), checking whether
each independently-checkable assertion becomes its own claim rather
than being merged, dropped, or left as one vague compound claim.

Research-only: rolled back, not persisted, per this session's default.

Run: cd backend && ./.venv/bin/python research/adversarial_v2/run_compound_claim_stress.py
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
            "name": "causal_chain_three_deep",
            "transcript": (
                "The factory shut down last month, which caused 400 workers to lose their jobs, "
                "which led to a sharp rise in local unemployment claims."
            ),
            "expected_min_claims": 3,
            "note": "3 chained causal assertions: factory shutdown, job losses, unemployment claims rise",
        },
        {
            "name": "three_way_conjunction_different_actors",
            "transcript": (
                "The mayor cut the ribbon on the new bridge, the governor announced a statewide "
                "infrastructure fund, and the opposition leader called the project a waste of money."
            ),
            "expected_min_claims": 3,
            "note": "3 independent actor-specific assertions joined by 'and'",
        },
        {
            "name": "compound_same_subject_two_actions",
            "transcript": (
                "The health minister announced a new vaccination drive today and also inaugurated "
                "a 200-bed hospital in the district."
            ),
            "expected_min_claims": 2,
            "note": "same subject, two independently-checkable actions",
        },
        {
            "name": "attribution_with_nested_sub_claims",
            "transcript": (
                "According to police, the accused confessed to the robbery and named two accomplices "
                "who are still at large."
            ),
            "expected_min_claims": 2,
            "note": "attributed statement containing 2 sub-assertions (confession, accomplices at large)",
        },
        {
            "name": "numeric_compound_two_time_periods",
            "transcript": (
                "Inflation rose to 8.2% in January this year, then fell to 5.4% in February "
                "according to the latest government data."
            ),
            "expected_min_claims": 2,
            "note": "2 distinct numeric claims about different months",
        },
        {
            "name": "contradictory_compound_tension",
            "transcript": (
                "The engineering report declared the bridge structurally safe just six months before "
                "it collapsed during rush hour, killing at least a dozen commuters."
            ),
            "expected_min_claims": 2,
            "note": "2 claims in real tension: safety declaration and later collapse",
        },
    ]


async def main() -> None:
    results = []
    async with AsyncSessionLocal() as db:
        for case in _cases():
            reel = Reel(
                id=uuid.uuid4(),
                source_url=f"https://instagram.com/reel/compound-{case['name']}",
                platform=Platform.instagram,
                media_type=MediaType.video,
                transcript=case["transcript"],
            )
            db.add(reel)
            await db.flush()

            print(f"=== {case['name']} ===", file=sys.stderr)
            print(f"    transcript: {case['transcript']}", file=sys.stderr)
            try:
                claims = await extract_claims(db, reel)
                claim_detail = [
                    {"text": c.text, "claim_type": c.claim_type.value, "verifiable": c.verifiable}
                    for c in claims
                ]
                n_verifiable = sum(1 for c in claim_detail if c["verifiable"])
                meets_expectation = len(claim_detail) >= case["expected_min_claims"]
                outcome, error = "resolved", None
                print(f"  -> {len(claim_detail)} claim(s) ({n_verifiable} verifiable), "
                      f"expected>={case['expected_min_claims']}, meets_expectation={meets_expectation}", file=sys.stderr)
                for c in claim_detail:
                    print(f"     - {c['text'][:90]!r} (verifiable={c['verifiable']})", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                claim_detail, n_verifiable, meets_expectation, outcome, error = [], 0, False, "error", f"{type(exc).__name__}: {exc}"
                print(f"  CRASHED: {error}", file=sys.stderr)
            finally:
                await db.rollback()

            results.append({
                "case": case["name"], "note": case["note"], "expected_min_claims": case["expected_min_claims"],
                "outcome": outcome, "error": error, "claims": claim_detail,
                "n_claims": len(claim_detail), "n_verifiable": n_verifiable, "meets_expectation": meets_expectation,
            })

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "compound_claim_stress_20260818.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))
    n_met = sum(1 for r in results if r["meets_expectation"])
    print(f"\nCases meeting expected minimum claim count: {n_met}/{len(results)}", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
