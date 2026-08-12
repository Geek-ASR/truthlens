"""Naive-baseline comparison (paper Section VIII, item 2): "ask an LLM to
fact-check this claim" with NO pipeline -- no claim decomposition, no
search, no retrieved evidence, no deterministic validation. Just the
claim text and the same LLM access pattern TruthLens uses by default
(app.services.ai.factory.get_llm_provider(), i.e. Llama 3.2 via Ollama
with an automatic Gemini fallback on failure).

Deliberately NOT part of the backend app package -- this is a one-off
research artifact for the paper, not a product feature, and it
deliberately does NOT reuse TruthLens's carefully engineered system
prompts (the neutrality clause, the evidence-grounding instructions,
etc.), since the whole point is to measure what a naive, un-engineered
LLM call gets you, as the counterfactual to everything else in this
project.

Run from the backend directory so imports resolve:
    cd backend && .venv/bin/python ../research_paper/benchmark/run_naive_baseline.py
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.services.ai.factory import get_llm_provider  # noqa: E402

CLAIMS_FILE = Path(__file__).parent / "claims.jsonl"
OUTPUT_FILE = Path(__file__).parent / "naive_baseline_results.jsonl"

NAIVE_SYSTEM_PROMPT = (
    "You are a fact-checker. You will be given a claim. Assess whether "
    "it is true, based on what you already know. Respond with a verdict "
    "of TRUE, FALSE, MIXED, or UNVERIFIABLE (use UNVERIFIABLE only if you "
    "genuinely have no basis to judge either way), and a brief reasoning "
    "for your answer."
)


class NaiveVerdict(BaseModel):
    verdict: Literal["TRUE", "FALSE", "MIXED", "UNVERIFIABLE"]
    reasoning: str


async def main():
    settings = get_settings()
    provider = get_llm_provider()
    claims = [json.loads(line) for line in CLAIMS_FILE.read_text().splitlines() if line.strip()]

    results = []
    for c in claims:
        print(f"Running naive baseline for {c['claim_id']}...", file=sys.stderr)
        result = await provider.structured_call(
            model=settings.LLM_MODEL_VERDICT,
            system_prompt=NAIVE_SYSTEM_PROMPT,
            user_content=f"CLAIM: {c['claim_text']}",
            output_schema=NaiveVerdict,
            prompt_version="naive_baseline.v1",
        )
        row = {
            "claim_id": c["claim_id"],
            "claim_text": c["claim_text"],
            "ground_truth_label": c["ground_truth_label"],
            "naive_verdict": result.parsed.verdict,
            "naive_reasoning": result.parsed.reasoning,
            "naive_model": result.model,
        }
        results.append(row)
        print(json.dumps(row, indent=2), file=sys.stderr)

    with OUTPUT_FILE.open("w") as f:
        for row in results:
            f.write(json.dumps(row) + "\n")
    print(f"\nWrote {len(results)} results to {OUTPUT_FILE}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
