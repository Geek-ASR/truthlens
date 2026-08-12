"""Baseline 2 (BASELINE_SPEC.md): Search + LLM, single-shot.

claim_text -> one DuckDuckGoSearchProvider.search() call -> top-N
(title, snippet) pairs ONLY -> single LLM call (same model TruthLens
itself defaults to) -> verdict.

Isolates "has search access at all" from TruthLens's specific multi
-stage decomposition/tiering/per-source-analysis/validation design —
the comparison the existing paper's Discussion section already names as
missing. No claim decomposition (the claim is taken as given, from
`items.jsonl`, not re-extracted by this baseline — see BASELINE_SPEC.md
for why that's the correct scope for RQ2). No source tiering. No
per-source evidence analysis. No deterministic validation.

Important implementation note: DuckDuckGoSearchProvider.search() always
attempts a full-page fetch internally (see
app/services/search/duckduckgo.py's `_fetch_page_text`) — there is no
"snippet-only" search API to call instead. This baseline gets the exact
same SearchResult objects Baseline 3 does, and deliberately reads only
`.snippet`, discarding `.full_content`, so it genuinely tests snippet
-only reasoning rather than accidentally strengthening itself. This is
noted here rather than left implicit, since it's the one place this
baseline's "single-shot, thin evidence" framing depends on code
discipline rather than a structurally different API call.

Run from the backend directory:
    cd backend && .venv/bin/python research/baselines/baseline_search_llm.py
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

CONFIG_NAME = "search_llm"
N_SEARCH_RESULTS = 5

SYSTEM_PROMPT = (
    "You are a fact-checker. You will be given a claim and a set of web search "
    "result titles and short snippets about it. Based ONLY on this information "
    "(do not use outside knowledge you may already have), determine a verdict. "
    "Choose exactly one: TRUE, MOSTLY_TRUE, MISLEADING, MOSTLY_FALSE, FALSE, "
    "UNVERIFIED, OUTDATED, MISSING_CONTEXT. Use UNVERIFIED whenever the search "
    "results genuinely don't give you enough to conclude either way — do not "
    "guess to avoid an unsatisfying answer."
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

    snippets_block = "\n\n".join(
        f"[{i + 1}] {r.title or '(untitled)'}\n{r.snippet or '(no snippet)'}" for i, r in enumerate(results)
    )
    user_content = f"CLAIM: {claim_text}\n\nSEARCH RESULTS:\n{snippets_block or '(no results found)'}"

    n_llm_calls = 0
    input_tokens = output_tokens = 0
    try:
        result = await llm_provider.structured_call(
            model=settings.LLM_MODEL_VERDICT,
            system_prompt=SYSTEM_PROMPT,
            user_content=user_content,
            output_schema=BaselineVerdict,
            prompt_version="baseline_search_llm.v1",
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
    # Deliberately OllamaProvider() directly, NOT app.services.ai.factory.
    # get_llm_provider() -- that factory wraps Ollama in
    # FallbackLLMProvider whenever GEMINI_API_KEY is set, silently giving
    # this baseline the same Gemini-rescue-on-failure behavior TruthLens
    # itself has. That would confound the comparison BASELINE_SPEC.md
    # calls for: Gemini is TruthLens's own architectural feature under
    # test (the escalation cascade), not something a baseline should get
    # for free. A raw Ollama failure here is recorded as outcome_type
    # "error" by run_item()'s own try/except, not silently rescued.
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
