"""End-to-end evaluation of the FULL TruthLens pipeline over the v2
`validation` split, LOCAL-ONLY (no Gemini, no API keys) -- the
"TruthLens, local-only configuration" the paper reports.

Why this is a faithful measurement of the real system:
  * It runs the exact production stage functions -- claim_extraction,
    research_planning, search_fetch, evidence_analysis, verdict (full
    validator, Checks 1-7), then the deterministic
    overall_verdict.derive_overall_verdict() -- unmodified, the same
    call sequence as app.pipeline.orchestrator.analyze_reel()'s second
    half. Same pattern already used by
    research/validation_populate_v2/populate_validation_verdicts.py,
    extended here to (a) all 193 validation reels, (b) recording the
    reel-level overall verdict, and (c) writing a METRICS.md result row
    per item.
  * Ingestion (yt-dlp download -> MinIO -> faster-whisper -> OCR) is
    NOT re-run: every validation reel is already ingested (real
    transcript/OCR from its promotion pass). Re-running it would waste
    real compute and risk overwriting real transcript/OCR with a
    different non-deterministic pass.  vision_context is null on the
    ~115 items promoted with --skip-vision; that is a disclosed
    limitation of the corpus as it currently stands, not something this
    script papers over.
  * LOCAL-ONLY is enforced at startup: GEMINI_API_KEY must be empty and
    LLM_PROVIDER must be "ollama".  Every Gemini quality-retry call site
    is guarded by `settings.GEMINI_API_KEY` truthiness, so with it empty
    the pipeline uses the local llama3.2 result as-is -- no escalation,
    fully reproducible, $0.

Resumable: appends to research/results/local_eval_v2.jsonl and skips any
item_id already present with a terminal outcome.  Kill and re-run to
continue.

Run:
  cd backend && GEMINI_API_KEY= ./.venv/bin/python -m research.benchmark_v2.run_local_eval [--limit N] [--only item-0042]
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.exceptions import ResearchFailedError  # noqa: E402
from app.db.models import (  # noqa: E402
    BenchmarkSplit,
    Claim,
    ClaimStatus,
    DatasetType,
    Reel,
    Verdict,
)
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import claim_extraction, evidence_analysis, research_planning, search_fetch  # noqa: E402
from app.pipeline import verdict as verdict_stage  # noqa: E402
from app.pipeline.overall_verdict import derive_overall_verdict  # noqa: E402
from app.services.search.factory import get_search_provider  # noqa: E402

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ITEMS_V2 = _PROJECT_ROOT / "research" / "dataset" / "items_v2.jsonl"
_OUT = _PROJECT_ROOT / "research" / "results" / "local_eval_v2.jsonl"
_CONFIG = "full_truthlens_local"


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=str(_PROJECT_ROOT), text=True
        ).strip()
    except Exception:
        return "unknown"


def _norm_url(u: str) -> str:
    u = (u or "").strip().lower()
    for pre in ("https://", "http://"):
        if u.startswith(pre):
            u = u[len(pre) :]
    if u.startswith("www."):
        u = u[4:]
    u = u.replace("twitter.com/", "x.com/").replace("mobile.x.com/", "x.com/")
    return u.rstrip("/")


def _load_ground_truth() -> dict[str, dict]:
    """normalized original_url -> item dict (item_id, ground_truth_label, ...)."""
    gt: dict[str, dict] = {}
    for line in _ITEMS_V2.read_text().splitlines():
        if not line.strip():
            continue
        it = json.loads(line)
        gt[_norm_url(it["original_url"])] = it
    return gt


def _done_item_ids() -> set[str]:
    if not _OUT.exists():
        return set()
    done = set()
    for line in _OUT.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        # a row is terminal for every outcome_type we emit (resolved /
        # research_failed / no_verifiable_claims / error) -- re-running
        # `error` items is opt-in via --retry-errors
        done.add((row["item_id"], row["outcome_type"]))
    return done


def _append_row(row: dict) -> None:
    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with _OUT.open("a") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


async def _current_verdict(db, claim_id) -> Verdict | None:
    res = await db.execute(
        select(Verdict)
        .where(Verdict.claim_id == claim_id, Verdict.is_current.is_(True))
        .order_by(Verdict.created_at.desc())
    )
    return res.scalars().first()


async def _eval_one(db, reel_id, item: dict) -> dict:
    t0 = time.monotonic()
    reel = await db.get(Reel, reel_id)
    row: dict = {
        "item_id": item["item_id"],
        "config": _CONFIG,
        "predicted_label": None,
        "ground_truth_label": item.get("ground_truth_label"),
        "ground_truth_tier": item.get("ground_truth_tier"),
        "source_url": reel.source_url,
        "platform": item.get("platform"),
        "claim_ids_extracted": [],
        "claim_texts_extracted": [],
        "per_claim": [],
        "n_verifiable": 0,
        "n_research_failed": 0,
        "n_search_queries": 0,
        "n_llm_calls": 0,
        "outcome_type": "error",
        "overall_reasoning": None,
        "any_validation_downgrade": False,
        "confidence": None,
        "validation_status": "not_applicable",
        "cited_source_urls": [],
        "n_escalations": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
        "latency_seconds": 0.0,
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "code_version": _git_sha(),
        "model": get_settings().LLM_MODEL_VERDICT,
        "error": None,
        "vision_context_available": reel.vision_context is not None,
        "transcript_chars": len(reel.transcript or ""),
    }

    claims = await claim_extraction.extract_claims(db, reel)
    await db.commit()
    specs = [{"id": c.id, "text": c.text, "verifiable": c.verifiable, "importance": c.importance} for c in claims]
    row["claim_ids_extracted"] = [str(s["id"]) for s in specs]
    row["claim_texts_extracted"] = [s["text"] for s in specs]
    row["n_verifiable"] = sum(1 for s in specs if s["verifiable"])
    print(f"  {item['item_id']}: {len(specs)} claim(s), {row['n_verifiable']} verifiable", file=sys.stderr)

    search_provider = get_search_provider()
    for spec in specs:
        if not spec["verifiable"]:
            row["per_claim"].append({"text": spec["text"], "verifiable": False, "verdict": None, "validation_status": None})
            continue
        pc = {"text": spec["text"], "verifiable": True, "verdict": None, "validation_status": None, "error": None}
        try:
            claim = await db.get(Claim, spec["id"])
            queries = await research_planning.plan_research(db, claim)
            row["n_search_queries"] += len(queries or [])
            if not queries:
                await db.commit()
                pc["verdict"] = "NO_QUERIES"
                row["per_claim"].append(pc)
                continue
            try:
                sources = await search_fetch.fetch_evidence_sources(db, claim, queries, search_provider)
            except ResearchFailedError:
                claim.status = ClaimStatus.research_failed
                await db.commit()
                row["n_research_failed"] += 1
                pc["verdict"] = "RESEARCH_FAILED"
                row["per_claim"].append(pc)
                print(f"    RESEARCH_FAILED: {spec['text'][:60]!r}", file=sys.stderr)
                continue
            evidence_rows = await evidence_analysis.analyze_evidence(db, claim, sources) if sources else []
            for s in sources:
                if s.url and s.url not in row["cited_source_urls"]:
                    row["cited_source_urls"].append(s.url)
            v = await verdict_stage.propose_verdict(db, claim, evidence_rows, sources)
            await db.commit()
            pc["verdict"] = v.verdict.value
            pc["validation_status"] = v.validation_status.value
            if v.validation_status.value != "passed":
                row["any_validation_downgrade"] = True
            print(f"    -> {v.verdict.value} ({v.validation_status.value})", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            pc["error"] = f"{type(exc).__name__}: {exc}"
            print(f"    CLAIM FAILED: {pc['error']}", file=sys.stderr)
        row["per_claim"].append(pc)

    # Reel-level label: deterministic aggregation over is_current claim
    # verdicts, exactly as orchestrator.build_reel_fact_check does.
    pairs: list[tuple[Claim, Verdict | None]] = []
    for spec in specs:
        if not spec["verifiable"]:
            continue
        c = await db.get(Claim, spec["id"])
        pairs.append((c, await _current_verdict(db, spec["id"])))

    if row["n_verifiable"] == 0:
        row["outcome_type"] = "no_verifiable_claims"
        row["predicted_label"] = "UNVERIFIED"
        row["overall_reasoning"] = "No verifiable factual claim was extracted from this post."
    elif row["n_research_failed"] == row["n_verifiable"] and row["n_verifiable"] > 0:
        row["outcome_type"] = "research_failed"
        row["predicted_label"] = None
        row["overall_reasoning"] = "Every verifiable claim hit an infrastructure-level research failure."
    else:
        overall = derive_overall_verdict(pairs)
        row["predicted_label"] = overall.label.value
        row["overall_reasoning"] = overall.reasoning
        row["outcome_type"] = "resolved"

    row["latency_seconds"] = round(time.monotonic() - t0, 1)
    return row


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="process at most N pending reels (smoke test)")
    ap.add_argument("--only", action="append", default=None, help="only this item_id (repeatable)")
    ap.add_argument("--retry-errors", action="store_true", help="re-run items whose only prior outcome was 'error'")
    args = ap.parse_args()

    settings = get_settings()
    if settings.GEMINI_API_KEY:
        sys.exit("REFUSING TO RUN: GEMINI_API_KEY is set. This is the LOCAL-ONLY eval. "
                 "Re-run as:  GEMINI_API_KEY= ./.venv/bin/python -m research.benchmark_v2.run_local_eval")
    if settings.LLM_PROVIDER != "ollama":
        sys.exit(f"REFUSING TO RUN: LLM_PROVIDER={settings.LLM_PROVIDER!r}, expected 'ollama'.")

    gt = _load_ground_truth()
    done = _done_item_ids()
    done_ids = {iid for (iid, outcome) in done}
    if args.retry_errors:
        error_only = {iid for (iid, outcome) in done if outcome == "error"} - {
            iid for (iid, outcome) in done if outcome != "error"
        }
        done_ids -= error_only

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(Reel.id, Reel.source_url).where(
                Reel.dataset_type == DatasetType.benchmark,
                Reel.benchmark_split == BenchmarkSplit.validation,
            )
        )
        reels = res.all()

    todo = []
    unmatched = 0
    for reel_id, source_url in reels:
        item = gt.get(_norm_url(source_url))
        if item is None:
            unmatched += 1
            continue
        if args.only and item["item_id"] not in args.only:
            continue
        if item["item_id"] in done_ids and not (args.only and item["item_id"] in args.only):
            continue
        todo.append((reel_id, item))

    if unmatched:
        print(f"WARNING: {unmatched} validation reel(s) had no items_v2 ground-truth match (skipped)", file=sys.stderr)
    if args.limit:
        todo = todo[: args.limit]

    print(f"{len(reels)} validation reels; {len(done_ids)} already done; {len(todo)} to run this pass.", file=sys.stderr)

    n = 0
    async with AsyncSessionLocal() as db:
        for reel_id, item in todo:
            print(f"=== {item['item_id']}  ({item.get('ground_truth_label')})  {item['original_url'][:70]} ===", file=sys.stderr)
            try:
                row = await _eval_one(db, reel_id, item)
            except Exception as exc:  # noqa: BLE001 -- one bad item must not abort the run
                await db.rollback()
                row = {
                    "item_id": item["item_id"], "config": _CONFIG, "predicted_label": None,
                    "ground_truth_label": item.get("ground_truth_label"), "outcome_type": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "run_timestamp": datetime.now(timezone.utc).isoformat(), "code_version": _git_sha(),
                }
                print(f"  ITEM FAILED: {row['error']}", file=sys.stderr)
            _append_row(row)
            n += 1
            print(f"  [{n}/{len(todo)}] {row['item_id']} -> {row.get('predicted_label')} "
                  f"({row['outcome_type']}, {row.get('latency_seconds', 0)}s)", file=sys.stderr)

    print(f"\nDone this pass: {n} item(s) written to {_OUT}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
