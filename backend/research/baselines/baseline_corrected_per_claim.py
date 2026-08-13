"""Corrected re-run of Baselines 1-3, fixing AUDIT_REPORT.md Finding 1:
`common.py`'s `make_result_row()` was feeding baselines
`items.jsonl["claim_text"]` -- a human-written summary of the claim,
authored during dataset construction by reading the professional
fact-check article -- instead of "the claim as already extracted by
TruthLens's own claim-extraction stage," which is what BASELINE_SPEC.md
has always specified. That bug has been present, unnoticed, in every
baseline run since Day 3 (`common.py` has never been edited since).

This script re-runs baselines 1-3 the way BASELINE_SPEC.md actually
describes: per real extracted claim, then aggregated with the exact same
deterministic rule (`derive_overall_verdict`) TruthLens itself uses to
turn per-claim verdicts into one reel-level verdict. This holds claim
-extraction constant across every configuration, which is what RQ2 is
supposed to isolate.

Real extracted claims used below are not re-extracted here (that would
burn new Gemini/Ollama claim-extraction calls and introduce fresh LLM
non-determinism into a fix that doesn't need it) -- they are the exact
claim_id/claim_text/importance values already real, already published,
and already cross-checked elsewhere in this project:
  - claim_id/claim_text: research/results/validator_audit_20260813T073200Z.json
    (the frozen Day 5/8 validator audit, itself a real run of
    claim_extraction.extract_claims() against the real ingested reels)
  - importance: live `claims` table, queried by the exact claim_id above
    (2026-08-14; verified against the same claim_id values)
item-0003 stays excluded (never ingested, no extraction possible, same as
every other table in this program). items 0006/0007 genuinely extracted
ZERO verifiable claims in the real run (not a data gap -- a real result,
already reported in MULTIMODAL_EVALUATION.md/DAY8_RESULTS.md) -- both are
included here with that same real, zero-claim outcome, which is the
correct, honest input for a baseline too: if TruthLens's own extractor
found nothing checkworthy, a fair per-claim-input comparison gives the
baseline nothing to search either, rather than quietly handing it the
dataset's own clean claim summary as this bug previously did.

Run: cd backend && .venv/bin/python research/baselines/baseline_corrected_per_claim.py
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.core.config import get_settings  # noqa: E402
from app.db.models import ClaimStatus, VerdictLabel  # noqa: E402
from app.pipeline.overall_verdict import derive_overall_verdict  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from app.services.search.duckduckgo import DuckDuckGoSearchProvider  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/research/
from baselines import baseline_llm_only, baseline_search_llm, baseline_search_rag_llm  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "research" / "results"
DATASET_FILE = PROJECT_ROOT / "research" / "dataset" / "items.jsonl"

# item_id -> [(claim_id, claim_text, importance), ...]
# Source: research/results/validator_audit_20260813T073200Z.json (claim_id,
# claim_text) cross-joined with the live `claims` table (importance),
# both verified 2026-08-14 -- see this file's own docstring above.
REAL_CLAIMS = {
    "item-0001": [
        ("d81496e8-073d-46bb-8df7-b181257a1554",
         "A student scored or is expected to score 681 out of 720 in the NEET exam.", 0.85),
        ("ddfdd0c8-ff16-42ca-b5b5-aba054a3773c",
         "The student receiving the NEET score is the son of a paan shop owner.", 0.75),
        ("0336b50e-e0dd-4d3c-9202-762ca3e58c05",
         "Banaras Hindu University (BHU) is a medical college located in Uttar Pradesh, India.", 0.6),
        ("2b3fe4e7-4103-47f7-9744-508d67287283",
         "A NEET score of 681 allows admission into top medical colleges in India, such as Banaras Hindu University (BHU).", 0.8),
    ],
    "item-0002": [
        ("34800526-5642-4123-9921-7e3b7fbd9f15",
         "In a democracy, every citizen has the right to express their views and protest peacefully.", 0.7),
        ("5d4df076-2d10-43da-9ad3-fe5c821dde98",
         "Kunwar Vishnu Singh Rajput is an Organization Secretary of Karni Sena.", 0.5),
    ],
    "item-0004": [
        ("8dad1c21-bb51-4cef-8d1f-9305938bb2bb",
         "Delhi Police are attacking children using lathis/sticks embedded with nails.", 0.95),
    ],
    "item-0005": [
        ("056f8350-5988-497b-bd31-285728f67821",
         "Babajani Durrani held a courtesy meeting with Abhijit Dipke at Dipke's residence in Chhatrapati Sambhajinagar.", 0.8),
        ("0a5c9958-7216-40ec-991d-370e1d402294",
         "Abhijit Dipke is an activist/youth leader from the Marathwada region.", 0.6),
    ],
    "item-0006": [],  # genuine, real zero-verifiable-claims outcome
    "item-0007": [],  # genuine, real zero-verifiable-claims outcome
}


@dataclass
class _ClaimStub:
    text: str
    importance: float
    status: ClaimStatus = ClaimStatus.researched


@dataclass
class _VerdictStub:
    verdict: VerdictLabel


async def run_one_claim(config: str, claim_text: str, llm_provider, search_provider, settings) -> dict:
    if config == "llm_only":
        return await baseline_llm_only.run_item(claim_text, llm_provider, settings)
    if config == "search_llm":
        return await baseline_search_llm.run_item(claim_text, llm_provider, search_provider, settings)
    if config == "search_rag_llm":
        return await baseline_search_rag_llm.run_item(claim_text, llm_provider, search_provider, settings)
    raise ValueError(config)


async def run_item_corrected(item: dict, config: str, llm_provider, search_provider, settings) -> dict:
    claims = REAL_CLAIMS[item["id"]]
    if not claims:
        return {
            "item_id": item["id"],
            "config": config,
            "predicted_label": VerdictLabel.UNVERIFIED.value,
            "ground_truth_label": item["ground_truth_label"],
            "ground_truth_tier": item["ground_truth_tier"],
            "n_real_claims_used": 0,
            "per_claim_results": [],
            "outcome_type": "no_verifiable_claims",
            "n_llm_calls": 0,
            "n_search_queries": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "latency_seconds": 0.0,
            "aggregation_reasoning": "No claims from this reel could be fully researched and verified.",
        }

    per_claim_outcomes = []
    pairs = []
    total_llm_calls = total_in = total_out = 0
    total_latency = 0.0
    t0 = time.monotonic()
    for claim_id, claim_text, importance in claims:
        outcome = await run_one_claim(config, claim_text, llm_provider, search_provider, settings)
        per_claim_outcomes.append({"claim_id": claim_id, "claim_text": claim_text, **outcome})
        total_llm_calls += outcome.get("n_llm_calls", 0) or 0
        total_in += outcome.get("input_tokens", 0) or 0
        total_out += outcome.get("output_tokens", 0) or 0
        total_latency += outcome.get("latency_seconds", 0.0) or 0.0
        if outcome.get("predicted_label"):
            pairs.append((
                _ClaimStub(text=claim_text, importance=importance),
                _VerdictStub(verdict=VerdictLabel(outcome["predicted_label"])),
            ))
        else:
            pairs.append((_ClaimStub(text=claim_text, importance=importance, status=ClaimStatus.research_failed), None))

    overall = derive_overall_verdict(pairs)
    return {
        "item_id": item["id"],
        "config": config,
        "predicted_label": overall.label.value,
        "ground_truth_label": item["ground_truth_label"],
        "ground_truth_tier": item["ground_truth_tier"],
        "n_real_claims_used": len(claims),
        "per_claim_results": per_claim_outcomes,
        "outcome_type": "resolved",
        "n_llm_calls": total_llm_calls,
        "n_search_queries": sum(1 for c in claims) if config != "llm_only" else 0,
        "input_tokens": total_in,
        "output_tokens": total_out,
        "latency_seconds": round(time.monotonic() - t0, 2),
        "aggregation_reasoning": overall.reasoning,
    }


async def main():
    settings = get_settings()
    llm_provider = OllamaProvider()
    search_provider = DuckDuckGoSearchProvider()

    items = {json.loads(l)["id"]: json.loads(l) for l in DATASET_FILE.read_text().splitlines() if l.strip()}
    target_items = [items[i] for i in REAL_CLAIMS.keys()]

    all_rows = {"llm_only": [], "search_llm": [], "search_rag_llm": []}
    for config in ("llm_only", "search_llm", "search_rag_llm"):
        for item in target_items:
            print(f"[{config}] {item['id']} ({len(REAL_CLAIMS[item['id']])} real claims)...", file=sys.stderr)
            row = await run_item_corrected(item, config, llm_provider, search_provider, settings)
            all_rows[config].append(row)
            print(f"  -> {row['predicted_label']} (gt={row['ground_truth_label']})", file=sys.stderr)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "baselines_corrected_per_claim_20260814.json"
    out_path.write_text(json.dumps(all_rows, indent=2))
    print(f"\nWrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
