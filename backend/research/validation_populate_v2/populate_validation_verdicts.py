"""Populates real claims/research/evidence/verdicts for the 6 real
VALIDATION-split items (item-0010 through item-0015, promoted via
backend/research/benchmark_v2/promote_eligible_candidates.py) -- the
first genuine use of this project's validation split for anything
beyond ingestion, and the concrete prerequisite for
research/RESEARCH_ROADMAP_V2.md Phase 10 (aggregation counterfactual
re-run), which explicitly needs "VALIDATION-split items with >1
verifiable claim."

Unlike every other research script this session, this one REALLY
COMMITS -- it is not a measurement run to roll back. These 6 items are
already fully ingested (real transcript/OCR/vision_context from their
own promotion pass); this script runs exactly the second half of
app.pipeline.orchestrator.analyze_reel() (claim extraction through
verdict) unchanged, skipping only the ingestion branch (already done,
re-running it would waste real compute and risk silently overwriting
real transcript/OCR data with a different non-deterministic re-run).
Every stage -- claim_extraction, research_planning, search_fetch,
evidence_analysis, verdict (including the full validator, Checks 1-7)
-- is the real, unmodified production function.

Run: cd backend && ./.venv/bin/python research/validation_populate_v2/populate_validation_verdicts.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.exceptions import ResearchFailedError  # noqa: E402
from app.db.models import BenchmarkSplit, Claim, ClaimStatus, DatasetType, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import claim_extraction, evidence_analysis, research_planning, search_fetch  # noqa: E402
from app.pipeline import verdict as verdict_stage  # noqa: E402
from app.services.search.factory import get_search_provider  # noqa: E402


async def _populate_one(db, reel_id) -> None:
    reel = await db.get(Reel, reel_id)
    print(f"=== {reel.source_url} ===", file=sys.stderr)

    claims = await claim_extraction.extract_claims(db, reel)
    await db.commit()
    # Capture into plain values BEFORE any per-claim rollback can expire
    # them -- the same MissingGreenlet pattern already found and fixed
    # once this session (EXP-012): rollback() expires every object in
    # the session's identity map, not just the one that failed, so
    # holding onto these Claim ORM objects across a sibling claim's
    # rollback would crash on synchronous attribute access next
    # iteration. A fresh claim is re-fetched via db.get() each iteration
    # below instead.
    claim_specs = [{"id": c.id, "text": c.text, "verifiable": c.verifiable} for c in claims]
    print(f"  extracted {len(claim_specs)} claim(s)", file=sys.stderr)

    search_provider = get_search_provider()
    for spec in claim_specs:
        print(f"  claim: {spec['text'][:70]!r} (verifiable={spec['verifiable']})", file=sys.stderr)
        if not spec["verifiable"]:
            continue
        try:
            claim = await db.get(Claim, spec["id"])
            queries = await research_planning.plan_research(db, claim)
            if not queries:
                await db.commit()
                continue
            try:
                sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
            except ResearchFailedError:
                claim.status = ClaimStatus.research_failed
                await db.commit()
                print("    RESEARCH_FAILED (infra-level, every query errored)", file=sys.stderr)
                continue
            evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
            verdict = await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)
            await db.commit()
            print(f"    -> verdict={verdict.verdict.value} status={verdict.validation_status.value}", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 -- a real per-claim failure must not abort the other claims/items
            await db.rollback()
            print(f"    FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Reel.id)
            .where(Reel.dataset_type == DatasetType.benchmark, Reel.benchmark_split == BenchmarkSplit.validation)
        )
        reel_ids = [row[0] for row in result.all()]
    print(f"{len(reel_ids)} validation-split reel(s) to process", file=sys.stderr)

    async with AsyncSessionLocal() as db:
        for reel_id in reel_ids:
            await _populate_one(db, reel_id)

    print("\nDone. Real claims/verdicts committed for all validation-split reels.", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
