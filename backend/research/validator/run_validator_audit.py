"""Day 5 (research/EXPERIMENT_PLAN.md RQ1): turn the existing 28.6%
validation-downgrade telemetry into a real, auditable experiment.

Runs the REAL production pipeline (claim_extraction -> research_planning
-> search_fetch -> evidence_analysis -> verdict), unlike the Day
3/4 research scripts, which deliberately used pure Ollama to isolate
architecture/modality. Here we want the system exactly as deployed,
Gemini escalation cascade included, because the question is "how does
the deterministic validator behave on real production output," not an
isolated comparison.

For each verifiable claim, propose_verdict() is called with
SKIP_VALIDATION=True (research/BASELINE_SPEC.md's Baseline 4 flag) --
this persists the RAW proposal while validate_verdict() still runs
internally and its status is still recorded. This script then
reconstructs the exact same VerdictProposal from the persisted (raw)
Verdict row and re-runs validate_verdict() itself (a pure, deterministic,
free function -- no extra LLM cost) to recover the human-readable notes
explaining WHY, which aren't otherwise persisted when the gate is
skipped. From one real LLM call per claim we get both "WITHOUT
VALIDATION" (the raw row) and "WITH VALIDATION" (derived: pass through
unchanged if validation_status == passed, else UNVERIFIED + notes) --
never running the same claim through two separate, potentially
different, LLM calls.

Run from the backend directory:
    cd backend && .venv/bin/python research/validator/run_validator_audit.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import ResearchFailedError  # noqa: E402
from app.db.models import Claim, ClaimStatus, Evidence, MediaType, Reel, Source  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import claim_extraction, evidence_analysis, research_planning, search_fetch  # noqa: E402
from app.pipeline.validation import validate_verdict  # noqa: E402
from app.pipeline.verdict import propose_verdict  # noqa: E402
from app.schemas.verdict import VerdictProposal  # noqa: E402
from app.services.search.factory import get_search_provider  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "research" / "results"
_OUTPUT_PATH = RESULTS_DIR / f"validator_audit_{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.json"


def _write_results(results: list[dict]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(results, indent=2, default=str))

# The 6 real reels ingested during Day 4 (item-0003 excluded -- never
# successfully ingested). Re-fetched by source_url rather than re-run,
# since real media/transcript/OCR/vision already exist in the DB from
# that pass -- re-ingesting would waste a real Instagram fetch for no
# reason.
TARGET_URLS = {
    "item-0001": "https://www.instagram.com/reel/DYCLkKoBpof/",
    "item-0002": "https://www.instagram.com/reel/DbNU9W7xA9P/",
    "item-0004": "https://www.instagram.com/reel/DbCJDp8SYkn/",
    "item-0005": "https://www.instagram.com/babajanidurrani/p/Dbns78RDIXY/",
    "item-0006": "https://www.instagram.com/reel/DaVcoN2u698/",
    "item-0007": "https://www.instagram.com/reel/DbGy_XFz3mS/",
}


def _reconstruct_proposal(verdict) -> VerdictProposal:
    """Verdict row persisted under SKIP_VALIDATION=True holds the raw,
    un-mutated LLM proposal fields -- rebuild the schema object
    validate_verdict() expects from them."""
    return VerdictProposal(
        verdict=verdict.verdict,
        confidence=verdict.confidence,
        reasoning_summary=verdict.reasoning_summary,
        cited_evidence_ids=verdict.cited_evidence_ids,
        corrected_fact=verdict.corrected_fact,
        context_note=verdict.context_note,
    )


async def process_claim(db, claim, sources_by_id_for_reel):
    search_provider = get_search_provider()
    queries = await research_planning.plan_research(db, claim)
    await db.commit()
    if not queries:
        return {"outcome_type": "not_verifiable_or_no_queries"}

    try:
        sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
        await db.commit()
    except ResearchFailedError as exc:
        await db.rollback()
        return {"outcome_type": "research_failed", "error": str(exc)}

    if not sources:
        return {"outcome_type": "no_sources"}

    evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources)
    await db.commit()

    settings = get_settings()
    settings.SKIP_VALIDATION = True
    try:
        verdict = await propose_verdict(db, claim, evidence_rows, sources)
        await db.commit()
    finally:
        settings.SKIP_VALIDATION = False

    # Recover the human-readable "why" by re-running the same
    # deterministic check against the same evidence -- free, since
    # validate_verdict() makes no LLM call.
    evidence_by_id = {e.id: e for e in evidence_rows}
    source_by_evidence_id = {e.id: {s.id: s for s in sources}[e.source_id] for e in evidence_rows}
    proposal = _reconstruct_proposal(verdict)
    outcome = validate_verdict(proposal, evidence_by_id, source_by_evidence_id)

    # "WITH VALIDATION" derived exactly the way verdict.py's own
    # non-skip branch persists it, without a second LLM call.
    if outcome.status.value == "passed":
        with_validation_label = outcome.verdict.value
        with_validation_reasoning = proposal.reasoning_summary
    else:
        with_validation_label = "UNVERIFIED"
        with_validation_reasoning = f"{proposal.reasoning_summary}\n\n[VALIDATION NOTE: {'; '.join(outcome.notes)}]"

    return {
        "outcome_type": "resolved",
        "claim_id": str(claim.id),
        "claim_text": claim.text,
        "verdict_id": str(verdict.id),
        "without_validation": {
            "verdict": proposal.verdict.value,
            "confidence": proposal.confidence,
            "reasoning_summary": proposal.reasoning_summary,
            "cited_evidence_ids": [str(i) for i in proposal.cited_evidence_ids],
            "corrected_fact": proposal.corrected_fact,
            "context_note": proposal.context_note,
        },
        "with_validation": {
            "verdict": with_validation_label,
            "reasoning_summary": with_validation_reasoning,
        },
        "validation_status": outcome.status.value,
        "validation_notes": outcome.notes,
        "n_evidence_rows": len(evidence_rows),
        "n_sources": len(sources),
    }


async def main():
    all_results = []
    async with AsyncSessionLocal() as db:
        for item_id, url in TARGET_URLS.items():
            print(f"=== {item_id} ===", file=sys.stderr)
            result = await db.execute(select(Reel).where(Reel.source_url == url).order_by(Reel.created_at.desc()))
            reel = result.scalars().first()
            if not reel:
                print("  NOT FOUND in DB -- was it ingested?", file=sys.stderr)
                all_results.append({"item_id": item_id, "outcome_type": "reel_not_found"})
                continue

            try:
                claims = await claim_extraction.extract_claims(db, reel)
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — record, don't crash the batch
                print(f"  claim_extraction FAILED: {exc}", file=sys.stderr)
                await db.rollback()
                all_results.append({"item_id": item_id, "outcome_type": "claim_extraction_failed", "error": str(exc)})
                continue

            verifiable = [c for c in claims if c.verifiable]
            print(f"  {len(claims)} claims extracted, {len(verifiable)} verifiable", file=sys.stderr)
            if not verifiable:
                all_results.append({"item_id": item_id, "outcome_type": "no_verifiable_claims", "n_claims": len(claims)})
                continue

            for claim in verifiable:
                print(f"  processing claim: {claim.text[:80]}...", file=sys.stderr)
                try:
                    claim_result = await process_claim(db, claim, {})
                except Exception as exc:  # noqa: BLE001 — one claim's unexpected failure must not lose the rest
                    print(f"    UNEXPECTED FAILURE: {exc}", file=sys.stderr)
                    await db.rollback()
                    get_settings().SKIP_VALIDATION = False  # in case process_claim raised before its own finally
                    claim_result = {"outcome_type": "unexpected_error", "error": str(exc)}
                claim_result["item_id"] = item_id
                claim_result["claim_id"] = claim_result.get("claim_id", str(claim.id))
                claim_result["claim_text"] = claim_result.get("claim_text", claim.text)
                all_results.append(claim_result)
                # Write incrementally so a later crash doesn't lose earlier real results.
                _write_results(all_results)
                print(f"    -> {claim_result.get('outcome_type')}, validation_status={claim_result.get('validation_status')}", file=sys.stderr)

    _write_results(all_results)
    print(f"\nWrote {len(all_results)} claim results to {_OUTPUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
