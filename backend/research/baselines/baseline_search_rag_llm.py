"""Baseline 3 (BASELINE_SPEC.md): Search + RAG + LLM.

claim_text -> one DuckDuckGoSearchProvider.search() call -> full fetched
page text for each result (the same fetch/extract path TruthLens itself
gets, via `_fetch_page_text`'s trafilatura extraction — not a weaker
re-implementation) -> concatenate up to _MAX_PASSAGE_CHARS per source
(matched to evidence_analysis.py's own _MAX_PASSAGE_CHARS=8000, for
comparability) -> single LLM call over claim + concatenated passages ->
verdict.

Differs from Baseline 2 ONLY in using full page text instead of search
snippets — isolating "does retrieval depth matter" as its own variable,
separate from "does multi-stage decomposition matter" (only the full
system tests that) and "does per-source evidence analysis before verdict
matter" (also only the full system — this baseline concatenates
everything into one call rather than analyzing each source
independently the way evidence_analysis.py does per BASELINE_SPEC.md).

Run from the backend directory:
    cd backend && .venv/bin/python research/baselines/baseline_search_rag_llm.py
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.core.config import get_settings  # noqa: E402
from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from app.services.search.duckduckgo import DuckDuckGoSearchProvider  # noqa: E402
from research.baselines.common import (  # noqa: E402
    BaselineVerdict,
    load_dataset,
    make_result_row,
    write_results,
)

CONFIG_NAME = "search_rag_llm"
N_SEARCH_RESULTS = 5
MAX_PASSAGE_CHARS = 8000  # matched to app/pipeline/evidence_analysis.py's _MAX_PASSAGE_CHARS

SYSTEM_PROMPT = (
    "You are a fact-checker. You will be given a claim and the full extracted text of "
    "several web pages retrieved for it. Based ONLY on this information (do not use "
    "outside knowledge you may already have), determine a verdict. Choose exactly one: "
    "TRUE, MOSTLY_TRUE, MISLEADING, MOSTLY_FALSE, FALSE, UNVERIFIED, OUTDATED, "
    "MISSING_CONTEXT. Use UNVERIFIED whenever the retrieved pages genuinely don't give "
    "you enough to conclude either way — do not guess to avoid an unsatisfying answer."
)


async def run_item(claim_text: str, llm_provider, search_provider, settings) -> dict:
    start = time.monotonic()
    try:
        results = await search_provider.search(claim_text, max_results=N_SEARCH_RESULTS)
    except Exception as exc:  # noqa: BLE001 — infra failure must be recorded, not crash the run
        return {
            "predicted_label": None,
            "outcome_type": "research_failed",
            "confidence": None,
            "reasoning": None,
            "n_llm_calls": 0,
            "n_search_queries": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": settings.LLM_MODEL_VERDICT,
            "error": f"search failed: {exc}",
            "latency_seconds": time.monotonic() - start,
        }

    # Full page text (falls back to the snippet only when a page couldn't
    # actually be fetched — DuckDuckGoSearchProvider already encodes that
    # fallback in `full_content`, never fabricating text for a failed fetch).
    passages_block = "\n\n---\n\n".join(
        f"[{i + 1}] {r.title or '(untitled)'} ({r.url})\n{(r.full_content or r.snippet)[:MAX_PASSAGE_CHARS]}"
        for i, r in enumerate(results)
    )
    user_content = f"CLAIM: {claim_text}\n\nRETRIEVED PAGES:\n{passages_block or '(no results found)'}"

    n_llm_calls = 0
    input_tokens = output_tokens = 0
    try:
        result = await llm_provider.structured_call(
            model=settings.LLM_MODEL_VERDICT,
            system_prompt=SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=BaselineVerdict,
            prompt_version="baseline_search_rag_llm.v1",
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
        "n_search_queries": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_seconds": time.monotonic() - start,
    }


async def main():
    settings = get_settings()
    # See baseline_search_llm.py's identical comment: OllamaProvider()
    # directly, not the factory's get_llm_provider(), so this baseline
    # doesn't silently inherit TruthLens's own Gemini-fallback behavior.
    llm_provider = OllamaProvider()
    search_provider = DuckDuckGoSearchProvider()
    items = load_dataset()

    rows = []
    for item in items:
        print(f"[{CONFIG_NAME}] {item['id']}: {item['claim_text'][:80]}...", file=sys.stderr)
        outcome = await run_item(item["claim_text"], llm_provider, search_provider, settings)
        row = make_result_row(item=item, config=CONFIG_NAME, **outcome)
        rows.append(row)
        print(f"  -> {row['predicted_label']} (ground truth: {row['ground_truth_label']})", file=sys.stderr)

    out_path = write_results(CONFIG_NAME, rows)
    print(f"\nWrote {len(rows)} results to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
