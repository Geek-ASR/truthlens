"""EXP-025 (research/RESEARCH_ROADMAP_V2.md Phase 10): re-run the
single-claim-only vs. full-decomposition aggregation counterfactual
(the same methodology behind the original n=4 result,
Section "Claim-decomposition counterfactual" in research_paper/main.tex)
against real VALIDATION-split multi-claim items -- unlocked by EXP-024
populating real claims/verdicts for the first time.

No new LLM calls -- uses the real, already-persisted Claim/Verdict rows
from EXP-024, and the real, unmodified app.pipeline.overall_verdict.
derive_overall_verdict() function (not reimplemented) for the
multi-claim condition. The single-claim-only condition uses just the
highest-importance ("primary") claim's own already-computed verdict,
the same "primary_claim" selection rule
app.pipeline.orchestrator.build_reel_fact_check() itself uses.

Run: cd backend && ./.venv/bin/python research/aggregation_v2/rerun_decomposition_counterfactual.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.db.models import BenchmarkSplit, Claim, ClaimStatus, DatasetType, Reel, Verdict  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline.overall_verdict import derive_overall_verdict  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parents[3] / "research" / "results"


def _bucket(label: str) -> str:
    return {"TRUE": "TRUE_ADJ", "MOSTLY_TRUE": "TRUE_ADJ", "FALSE": "FALSE_ADJ", "MOSTLY_FALSE": "FALSE_ADJ"}.get(
        label, label
    )


async def main() -> None:
    ground_truth = {}
    with open(Path(__file__).resolve().parents[3] / "research" / "dataset" / "items_v2.jsonl") as f:
        for line in f:
            d = json.loads(line)
            ground_truth[d["original_url"]] = d["ground_truth_label"]

    results = []
    async with AsyncSessionLocal() as db:
        reels_result = await db.execute(
            select(Reel)
            .where(Reel.dataset_type == DatasetType.benchmark, Reel.benchmark_split == BenchmarkSplit.validation)
        )
        reels = reels_result.scalars().unique().all()

        for reel in reels:
            claims_result = await db.execute(select(Claim).where(Claim.reel_id == reel.id))
            all_claims = list(claims_result.scalars().all())
            verifiable = [c for c in all_claims if c.verifiable]
            if len(verifiable) < 2:
                continue  # Phase 10's own dataset requirement: >1 verifiable claim

            claim_verdict_pairs = []
            for claim in verifiable:
                v_result = await db.execute(
                    select(Verdict)
                    .where(Verdict.claim_id == claim.id, Verdict.is_current.is_(True))
                    .order_by(Verdict.created_at.desc())
                )
                claim_verdict_pairs.append((claim, v_result.scalars().first()))

            resolved_pairs = [(c, v) for c, v in claim_verdict_pairs if v is not None]
            if len(resolved_pairs) < 2:
                continue

            gt = ground_truth.get(reel.source_url)
            primary_claim, primary_verdict = max(resolved_pairs, key=lambda cv: cv[0].importance)
            single_claim_label = primary_verdict.verdict.value
            single_claim_match = _bucket(single_claim_label) == _bucket(gt)

            overall = derive_overall_verdict(claim_verdict_pairs)
            multi_claim_label = overall.label.value
            multi_claim_match = _bucket(multi_claim_label) == _bucket(gt)

            item_result = {
                "source_url": reel.source_url,
                "ground_truth": gt,
                "n_claims": len(resolved_pairs),
                "primary_claim_text": primary_claim.text,
                "single_claim_label": single_claim_label,
                "single_claim_match": single_claim_match,
                "multi_claim_label": multi_claim_label,
                "multi_claim_match": multi_claim_match,
                "multi_claim_reasoning": overall.reasoning,
            }
            results.append(item_result)
            print(f"=== {reel.source_url} (gt={gt}) ===", file=sys.stderr)
            print(f"  single-claim: {single_claim_label} ({'match' if single_claim_match else 'MISS'})", file=sys.stderr)
            print(f"  multi-claim:  {multi_claim_label} ({'match' if multi_claim_match else 'MISS'})", file=sys.stderr)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "decomposition_counterfactual_validation_20260818.json"
    out_path.write_text(json.dumps(results, indent=2, default=str))

    n = len(results)
    single_correct = sum(1 for r in results if r["single_claim_match"])
    multi_correct = sum(1 for r in results if r["multi_claim_match"])
    print(f"\nn={n} VALIDATION-split multi-claim items", file=sys.stderr)
    print(f"single-claim-only accuracy: {single_correct}/{n}", file=sys.stderr)
    print(f"multi-claim (full decomposition) accuracy: {multi_correct}/{n}", file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
