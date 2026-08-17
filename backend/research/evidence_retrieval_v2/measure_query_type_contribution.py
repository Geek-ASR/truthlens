"""EXP-015 (research/RESEARCH_ROADMAP_V2.md Phase 6): does the new
5-query structure (research_planning.v2, Step 13: exact_claim/
entity_focused/primary_source/contradiction/context_history) show a
measurable per-query-type contribution to usable evidence -- and how
does the new system's aggregate numbers compare to the already
-documented baseline (research/EVIDENCE_EVALUATION.md: 23.5%
source-tier-classification rate, 68.75% relevant-primary-source rate,
18.75% usable-evidence rate, n=68 sources / 9 claims)?

Runs the REAL research chain (research_planning.plan_research ->
search_fetch.fetch_evidence_sources -> evidence_analysis.analyze_evidence)
against real DEV-split claims, inside a transaction rolled back after
each claim -- no Source/Evidence/SearchQuery rows are left attached to
the live benchmark-tagged reels. Source.retrieval_query_id (already
existing production schema, not added for this experiment) is what
makes the per-query-type breakdown possible without any new column.

"Relevant" (metric 2 of the baseline's own four-way metric) is a manual
judgment, same discipline as the original: this script prints every
primary-tier source's title/passage for direct human review rather than
guessing a relevance heuristic -- the resulting judgments are recorded
by hand into the experiment's registry entry, not computed here.

Run: cd backend && ./.venv/bin/python research/evidence_retrieval_v2/measure_query_type_contribution.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkSplit, Claim, DatasetType, Reel, SourceTier  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import evidence_analysis, research_planning, search_fetch  # noqa: E402
from app.services.search.factory import get_search_provider  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"

# 4 real DEV claims, chosen for topical diversity (not all from the same
# claim-cluster) -- real claim ids queried live from the DB.
_TARGET_CLAIM_IDS = [
    "8dad1c21-bb51-4cef-8d1f-9305938bb2bb",  # Delhi Police attacking children
    "056f8350-5988-497b-bd31-285728f67821",  # Babajani Durrani / Abhijit Dipke meeting
    "e414a765-95ee-4c5a-b3a8-0a09405f867b",  # Education Minister of Bihar / BJP
    "5d4df076-2d10-43da-9ad3-fe5c821dde98",  # Kunwar Vishnu Singh Rajput / Karni Sena
]

_PRIMARY_TIERS = {SourceTier.primary_government, SourceTier.primary_legal, SourceTier.primary_data}


async def main() -> None:
    all_results = []
    search_provider = get_search_provider()

    async with AsyncSessionLocal() as db:
        for claim_id in _TARGET_CLAIM_IDS:
            result = await db.execute(select(Claim).where(Claim.id == claim_id))
            claim = result.scalars().first()
            if claim is None:
                print(f"SKIP {claim_id}: not found", file=sys.stderr)
                continue

            print(f"=== {claim_id}: {claim.text[:60]!r} ===", file=sys.stderr)
            claim_result = {"claim_id": claim_id, "claim_text": claim.text, "queries": [], "sources": []}
            try:
                queries = await research_planning.plan_research(db, claim)
                for q in queries:
                    print(f"  [{q.query_type.value}] {q.query_text}", file=sys.stderr)
                    claim_result["queries"].append({"id": str(q.id), "query_type": q.query_type.value, "query_text": q.query_text})

                sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
                query_type_by_id = {str(q.id): q.query_type.value for q in queries}
                for s in sources:
                    query_type = query_type_by_id.get(str(s.retrieval_query_id), "unknown")
                    claim_result["sources"].append({
                        "url": s.url,
                        "title": s.title,
                        "source_type": s.source_type.value,
                        "is_primary_tier": s.source_type in _PRIMARY_TIERS,
                        "query_type": query_type,
                        "relevant_passage": (s.relevant_passage or "")[:400],
                    })
                    print(
                        f"    -> [{query_type}] tier={s.source_type.value} {s.url}",
                        file=sys.stderr,
                    )

                evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
                evidence_by_source = {str(e.source_id): e.stance.value for e in evidence_rows}
                for src_entry in claim_result["sources"]:
                    matching_source = next((s for s in sources if s.url == src_entry["url"]), None)
                    src_entry["stance"] = evidence_by_source.get(str(matching_source.id)) if matching_source else None

            except Exception as exc:  # noqa: BLE001 -- a real failure is a real, reportable outcome
                claim_result["error"] = str(exc)
                print(f"  FAILED: {exc}", file=sys.stderr)
            finally:
                await db.rollback()

            all_results.append(claim_result)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "evidence_retrieval_v2_query_type_contribution_20260818.json"
    out_path.write_text(json.dumps(all_results, indent=2, default=str))
    print(f"\nWrote {out_path}", file=sys.stderr)

    # Summary: primary-tier source count per query type, for a quick read
    # before the manual relevance review.
    from collections import Counter

    per_type_primary = Counter()
    per_type_total = Counter()
    per_type_usable = Counter()
    for cr in all_results:
        for s in cr.get("sources", []):
            per_type_total[s["query_type"]] += 1
            if s["is_primary_tier"]:
                per_type_primary[s["query_type"]] += 1
            if s.get("stance") and s["stance"] != "irrelevant":
                per_type_usable[s["query_type"]] += 1

    print("\nPer-query-type summary (total sources / primary-tier / usable(non-irrelevant)):", file=sys.stderr)
    for qt in ["exact_claim", "entity_focused", "primary_source", "contradiction", "context_history"]:
        print(f"  {qt:18s}: total={per_type_total[qt]:3d} primary={per_type_primary[qt]:3d} usable={per_type_usable[qt]:3d}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
