"""Baseline 1 (BASELINE_SPEC.md): LLM-only, no pipeline at all.

claim_text -> single LLM call (same model TruthLens defaults to, same
provider isolation as baselines 2/3 -- OllamaProvider directly, no
Gemini fallback) -> verdict. No search, no retrieved evidence, no
validation.

Day 0's version of this baseline
(research_paper/benchmark/run_naive_baseline.py) covered only the
original 2-item benchmark and used an ad-hoc 4-label schema
(TRUE/FALSE/MIXED/UNVERIFIABLE) rather than TruthLens's own
VerdictLabel vocabulary. This is a full re-implementation against the
current 9-item research/dataset/items.jsonl, using the same
BaselineVerdict schema and result-row format as baselines 2/3 for a
directly comparable Day 8 table -- the original script and its 2-item
result are kept as-is, a separate, earlier, real artifact, not deleted
or silently overwritten.

Run from the backend directory:
    cd backend && .venv/bin/python research/baselines/baseline_llm_only.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.core.config import get_settings  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from research.baselines.common import (  # noqa: E402
    BaselineVerdict,
    load_dataset,
    make_result_row,
    write_results,
)

CONFIG_NAME = "llm_only"

SYSTEM_PROMPT = (
    "You are a fact-checker. You will be given a claim. Assess whether it is true, based ONLY "
    "on what you already know from training -- you have no search access and no retrieved "
    "evidence. Choose exactly one verdict: TRUE, MOSTLY_TRUE, MISLEADING, MOSTLY_FALSE, FALSE, "
    "UNVERIFIED, OUTDATED, MISSING_CONTEXT. Use UNVERIFIED whenever you genuinely have no basis "
    "to judge the claim either way (e.g. it concerns a recent or highly specific event you "
    "cannot know about) -- do not guess to avoid an unsatisfying answer."
)


async def run_item(claim_text: str, llm_provider, settings) -> dict:
    start = time.monotonic()
    n_llm_calls = 0
    input_tokens = output_tokens = 0
    try:
        result = await llm_provider.structured_call(
            model=settings.LLM_MODEL_VERDICT,
            system_prompt=SYSTEM_PROMPT,
            user_content=f"CLAIM: {claim_text}",
            output_schema=BaselineVerdict,
            prompt_version="baseline_llm_only.v1",
        )
        n_llm_calls = 1
        input_tokens = result.input_tokens
        output_tokens = result.output_tokens
        outcome = {
            "predicted_label": result.parsed.verdict,
            "outcome_type": "resolved",
            "confidence": result.parsed.confidence,
            "reasoning": result.parsed.reasoning,
            "error": None,
            "model": result.model,
        }
    except Exception as exc:  # noqa: BLE001 — record, don't crash the batch
        outcome = {
            "predicted_label": None,
            "outcome_type": "error",
            "confidence": None,
            "reasoning": None,
            "error": str(exc),
            "model": settings.LLM_MODEL_VERDICT,
        }

    return {
        **outcome,
        "n_llm_calls": n_llm_calls,
        "n_search_queries": 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_seconds": time.monotonic() - start,
    }


async def main():
    settings = get_settings()
    llm_provider = OllamaProvider()
    items = load_dataset()

    rows = []
    for item in items:
        print(f"[{CONFIG_NAME}] {item['id']}: {item['claim_text'][:80]}...", file=sys.stderr)
        outcome = await run_item(item["claim_text"], llm_provider, settings)
        row = make_result_row(item=item, config=CONFIG_NAME, **outcome)
        rows.append(row)
        print(f"  -> {row['predicted_label']} (ground truth: {row['ground_truth_label']})", file=sys.stderr)

    out_path = write_results(CONFIG_NAME, rows)
    print(f"\nWrote {len(rows)} results to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
