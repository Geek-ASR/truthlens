"""EXP-012 (research/PHASE1_RESEARCH_NOTES.md's own named-but-unrun next
experiment): does extraction_confidence correlate with anything real?

extraction_confidence is the extraction LLM's own self-reported
MODEL_CONFIDENCE (app/schemas/claim.py's own docstring: confidence that
this is a real, correctly-extracted claim, NOT a probability the claim
itself is true). This project has no per-claim human annotation of
extraction correctness, so "precision" in the literal sense isn't
measurable without new annotation work this pass doesn't do. The
honestly-measurable proxy available today: whether the claim's own
source_quote is independently, deterministically verifiable as a real
verbatim substring of the reel's actual transcript/OCR/caption --
exactly what app.pipeline.claim_extraction._infer_source_modalities()
already computes for production (Phase 2's provenance work), reused
here unchanged rather than reimplemented. A claim with a grounded quote
is a real, checkable extraction; a claim with no quote or an
ungroundable one is either a summarized/inferred claim (legitimately
unquoted) or a fabricated one -- either way, a different reliability
category than a verbatim-grounded claim, which is exactly the
distinction extraction_confidence's own docstring says it's supposed to
track.

Runs production's REAL extract_claims() -- full stack, quality-retry,
Gemini escalation, dedup -- against every DEV-split reel with real
ingested content (8 of the 9 v1 items; item-0003 was never ingestible).
VALIDATION-split items (the 6 new v2 items) are deliberately excluded:
this is exploratory/diagnostic measurement against extraction_confidence
itself, the kind of DEV-only experimentation Phase 3's own text reserves
VALIDATION from until its later confirmatory use.

Each attempt runs inside a transaction that is always rolled back --
every needed field is read into plain Python data BEFORE rollback
-- no residual Claim rows are left in the DB (mirrors
verify_production_safety_net.py's established pattern).

Run: cd backend && ./.venv/bin/python research/claim_extraction_v2/extraction_confidence_correlation.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

import numpy as np  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.claim_extraction import extract_claims  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


async def main() -> None:
    all_claims = []
    per_item_log = []

    # Plain (id, source_url) pairs only -- never ORM objects held across a
    # rollback (tests/regression/database/test_missing_greenlet_after_rollback.py:
    # rollback() expires every object already loaded in the session, not
    # just the one touched by extract_claims(), so holding a list of Reel
    # ORM objects across the loop's own per-item rollback crashes on the
    # NEXT iteration's attribute read, not the current one).
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reel.id, Reel.source_url)
            .where(Reel.dataset_type == DatasetType.benchmark, Reel.benchmark_split == BenchmarkSplit.dev)
        )
        seen_urls: set[str] = set()
        targets: list[tuple[object, str]] = []
        for reel_id, source_url in result.all():
            if source_url in seen_urls:
                continue  # a handful of source_urls have multiple ingested rows (re-ingestion during development) -- one pass is enough
            seen_urls.add(source_url)
            targets.append((reel_id, source_url))

    async with AsyncSessionLocal() as db:
        for reel_id, source_url in targets:
            reel = await db.get(Reel, reel_id)  # fresh load each iteration -- never reused across a rollback
            if not (reel.transcript or reel.ocr_text or reel.caption_text):
                print(f"SKIP {source_url}: no real content", file=sys.stderr)
                continue

            print(f"=== {source_url}: running production extract_claims() ===", file=sys.stderr)
            try:
                claims = await extract_claims(db, reel)
                item_claims = [
                    {
                        "text": c.text,
                        "extraction_confidence": c.extraction_confidence,
                        "confidence_type": c.confidence_type,
                        "source_modalities": c.source_modalities,
                        "grounded": bool(c.source_modalities),
                        "has_source_quote": bool(c.source_quote),
                    }
                    for c in claims
                ]  # captured into plain dicts BEFORE rollback -- the fix
                all_claims.extend(item_claims)
                per_item_log.append({"source_url": source_url, "n_claims": len(item_claims), "error": None})
                print(f"  -> {len(item_claims)} claim(s)", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 -- a real extraction failure is a real, reportable outcome
                per_item_log.append({"source_url": source_url, "n_claims": 0, "error": str(exc)})
                print(f"  FAILED: {exc}", file=sys.stderr)
            finally:
                await db.rollback()  # never persist -- this is a measurement run, not real ingestion

    with_confidence = [c for c in all_claims if c["extraction_confidence"] is not None]

    report = {
        "n_reels_attempted": len(per_item_log),
        "n_claims_total": len(all_claims),
        "n_claims_with_confidence": len(with_confidence),
        "per_item_log": per_item_log,
        "claims": all_claims,
    }

    if len(with_confidence) >= 2 and len({c["grounded"] for c in with_confidence}) == 2:
        confidences = np.array([c["extraction_confidence"] for c in with_confidence])
        grounded = np.array([1.0 if c["grounded"] else 0.0 for c in with_confidence])
        corr = float(np.corrcoef(confidences, grounded)[0, 1])
        report["point_biserial_correlation_confidence_vs_grounded"] = corr
        report["mean_confidence_grounded"] = float(confidences[grounded == 1].mean()) if (grounded == 1).any() else None
        report["mean_confidence_ungrounded"] = float(confidences[grounded == 0].mean()) if (grounded == 0).any() else None
        report["n_grounded"] = int((grounded == 1).sum())
        report["n_ungrounded"] = int((grounded == 0).sum())
    else:
        report["point_biserial_correlation_confidence_vs_grounded"] = None
        report["note"] = "Not enough variation (need >=2 claims and both grounded/ungrounded present) to compute a correlation."

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "extraction_confidence_correlation_20260817.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))

    print(f"\nn_claims_with_confidence = {report['n_claims_with_confidence']}", file=sys.stderr)
    print(f"correlation = {report.get('point_biserial_correlation_confidence_vs_grounded')}", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
