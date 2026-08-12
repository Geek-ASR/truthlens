"""Shared plumbing for baselines 2-3 (BASELINE_SPEC.md). Kept out of the
main `app` package deliberately — these are one-off research artifacts,
not product features, same convention as
research_paper/benchmark/run_naive_baseline.py.

Every baseline writes rows matching METRICS.md's "Raw result row schema"
so Day 10's table-generation scripts can consume any baseline's output
identically, without per-baseline special-casing."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
DATASET_FILE = PROJECT_ROOT / "research" / "dataset" / "items.jsonl"
RESULTS_DIR = PROJECT_ROOT / "research" / "results"

# Same VerdictLabel vocabulary db.models.VerdictLabel uses, duplicated as
# a plain Literal (not imported from app.db.models) so these scripts
# never need a DB connection just to know the label set — baselines 2/3
# make no DB writes at all, by design, since they're not testing
# anything about TruthLens's persistence layer.
BaselineVerdictLabel = Literal[
    "TRUE", "MOSTLY_TRUE", "MISLEADING", "MOSTLY_FALSE", "FALSE", "UNVERIFIED", "OUTDATED", "MISSING_CONTEXT"
]


class BaselineVerdict(BaseModel):
    verdict: BaselineVerdictLabel
    confidence: float
    reasoning: str


def load_dataset() -> list[dict]:
    if not DATASET_FILE.exists():
        raise FileNotFoundError(
            f"{DATASET_FILE} does not exist — run from a checkout with research/dataset/items.jsonl present."
        )
    items = [json.loads(line) for line in DATASET_FILE.read_text().splitlines() if line.strip()]
    if not items:
        raise ValueError(f"{DATASET_FILE} is empty.")
    return items


def write_results(config_name: str, rows: list[dict]) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = RESULTS_DIR / f"baseline_{config_name}_{timestamp}.jsonl"
    with out_path.open("w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return out_path


def make_result_row(
    *,
    item: dict,
    config: str,
    predicted_label: str | None,
    outcome_type: str,
    confidence: float | None,
    reasoning: str | None,
    n_llm_calls: int,
    n_search_queries: int,
    input_tokens: int,
    output_tokens: int,
    latency_seconds: float,
    model: str,
    error: str | None = None,
) -> dict:
    """Matches METRICS.md's "Raw result row schema" exactly. Fields that
    schema defines but that don't apply to a given baseline (validation_
    status, cited_source_urls beyond what was searched, n_escalations)
    are filled with baseline-appropriate defaults, never omitted, so
    every row has the same shape regardless of which config produced it."""
    return {
        "item_id": item["id"],
        "config": config,
        "predicted_label": predicted_label,
        "ground_truth_label": item.get("ground_truth_label"),
        "ground_truth_tier": item.get("ground_truth_tier"),
        "claim_ids_extracted": [],  # baselines 2/3 don't do claim extraction; see BASELINE_SPEC.md
        "claim_texts_extracted": [item.get("claim_text", "")],
        "outcome_type": outcome_type,
        "confidence": confidence,
        "validation_status": "not_applicable",  # only the full TruthLens system has this
        "cited_source_urls": [],
        "n_llm_calls": n_llm_calls,
        "n_search_queries": n_search_queries,
        "n_escalations": 0,  # baselines never use the Gemini escalation cascade
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_seconds": round(latency_seconds, 2),
        "estimated_cost_usd": 0.0,  # Ollama-only, $0 by construction
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "code_version": "backend/research/baselines (Day 3)",
        "model": model,
        "reasoning": reasoning,
        "error": error,
    }
