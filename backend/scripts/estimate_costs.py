"""Reports real Claude token usage from audit_logs, per pipeline stage and
per fact-check, and projects it to a configurable daily posting volume.

This exists because "will it be enough tokens" is an empirical question,
not one to guess at — per docs/FACT_CHECK_METHODOLOGY.md's "no invented
facts" standard, which this script holds itself to: every number here is
summed from `audit_logs.output_summary.tokens`, populated from the real
Anthropic API `usage` field on every structured_call
(app/services/ai/anthropic_provider.py), not estimated.

Usage:
    python scripts/estimate_costs.py                        # last 7 days
    python scripts/estimate_costs.py --days 1                # last 24h
    python scripts/estimate_costs.py --daily-target 12       # override MAX_POSTS_PER_DAY

Needs real audit_logs data to say anything useful — run a few fact-checks
through the pipeline first (with a real ANTHROPIC_API_KEY configured).
With zero AI-stage audit rows this just reports zero and says so; it does
not fill the gap with a guess.
"""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import ActorType, AuditLog
from app.db.session import AsyncSessionLocal

# Anthropic first-party pricing, USD per 1M tokens. Verify at
# https://platform.claude.com/docs/en/pricing before trusting this for a
# real budget decision — pricing changes, and introductory rates expire
# (Sonnet 5's $2/$10 intro rate below runs through 2026-08-31; after that
# it reverts to $3/$15 — check the date before reading the number).
_PRICING_USD_PER_MTOK = {
    "claude-sonnet-5": {"input": 2.00, "output": 10.00},  # intro rate through 2026-08-31
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}
_CACHE_READ_MULTIPLIER = 0.1  # cache reads bill at ~10% of base input price
_UNKNOWN_MODEL_NOTE = (
    "no pricing entry for this model in this script — add one from "
    "platform.claude.com/pricing before trusting the $ total"
)

_AI_STAGE_ACTIONS = {
    "claim_extraction",
    "research_planning",
    "evidence_analysis",
    "verdict",
    "content_generation",
    "vision_context",
}


def _model_from_actor(actor: str) -> str:
    # actor is stored as "llm:<model>" for ai_stage rows (see
    # app/pipeline/audit.py call sites).
    return actor.split(":", 1)[1] if ":" in actor else actor


def _cost_usd(model: str, tokens: dict) -> float | None:
    rates = _PRICING_USD_PER_MTOK.get(model)
    if rates is None:
        return None
    input_cost = tokens.get("input_tokens", 0) / 1_000_000 * rates["input"]
    cache_read_cost = (
        tokens.get("cache_read_input_tokens", 0) / 1_000_000 * rates["input"] * _CACHE_READ_MULTIPLIER
    )
    output_cost = tokens.get("output_tokens", 0) / 1_000_000 * rates["output"]
    return input_cost + cache_read_cost + output_cost


async def main(days: int, daily_target: int) -> None:
    settings = get_settings()
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(AuditLog).where(
                    AuditLog.actor_type == ActorType.ai_stage,
                    AuditLog.action.in_(_AI_STAGE_ACTIONS),
                    AuditLog.created_at >= since,
                )
            )
        ).scalars().all()

        # Distinct claims touched, as a proxy for "how many claims did this
        # volume of tokens actually cover" — entity_id is the claim_id (or
        # reel_id for claim_extraction/vision_context) depending on stage.
        fact_check_count = (
            await db.execute(
                select(AuditLog.entity_id)
                .where(AuditLog.action == "claim_extraction", AuditLog.created_at >= since)
                .distinct()
            )
        ).scalars().all()

    if not rows:
        print(
            f"No AI-stage audit_logs rows found in the last {days} day(s).\n"
            "This script reports real usage only — it will not guess. Run at least "
            "one reel through /api/reels/{id}/analyze with a real ANTHROPIC_API_KEY, "
            "then re-run this script."
        )
        return

    by_stage: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cost_usd": 0.0}
    )
    total_cost = 0.0
    total_calls = 0
    unknown_model_seen = set()

    for row in rows:
        tokens = (row.output_summary or {}).get("tokens")
        if not tokens:
            continue  # pre-migration rows with no token data — skip, don't guess
        model = _model_from_actor(row.actor)
        cost = _cost_usd(model, tokens)
        if cost is None:
            unknown_model_seen.add(model)
            cost = 0.0

        bucket = by_stage[row.action]
        bucket["calls"] += 1
        bucket["input_tokens"] += tokens.get("input_tokens", 0)
        bucket["output_tokens"] += tokens.get("output_tokens", 0)
        bucket["cache_read_input_tokens"] += tokens.get("cache_read_input_tokens", 0)
        bucket["cost_usd"] += cost
        total_cost += cost
        total_calls += 1

    n_fact_checks = max(len(fact_check_count), 1)

    print(f"=== Real token usage, last {days} day(s) ({total_calls} AI calls) ===\n")
    print(f"{'Stage':<22}{'Calls':>8}{'Input tok':>12}{'Output tok':>12}{'Cost ($)':>10}")
    for stage, b in sorted(by_stage.items(), key=lambda kv: -kv[1]["cost_usd"]):
        print(f"{stage:<22}{b['calls']:>8}{b['input_tokens']:>12}{b['output_tokens']:>12}{b['cost_usd']:>10.4f}")
    print(f"\nTotal cost this window: ${total_cost:.4f}")
    print(f"Fact-checks (reels analyzed) this window: {len(fact_check_count)}")

    if unknown_model_seen:
        print(
            f"\nWARNING: {_UNKNOWN_MODEL_NOTE} — models seen with no pricing entry: "
            f"{', '.join(sorted(unknown_model_seen))}. Their cost is reported as $0, "
            f"so the total above is an UNDERCOUNT."
        )

    if len(fact_check_count) > 0:
        per_fact_check_calls = total_calls / n_fact_checks
        per_fact_check_cost = total_cost / n_fact_checks
        print(f"\n=== Per fact-check (averaged over {len(fact_check_count)} observed) ===")
        print(f"AI calls per fact-check: {per_fact_check_calls:.1f}")
        print(f"Cost per fact-check:     ${per_fact_check_cost:.4f}")

        print(f"\n=== Projection at {daily_target} fact-checks/day (MAX_POSTS_PER_DAY={settings.MAX_POSTS_PER_DAY}) ===")
        print(f"Calls/day:  {per_fact_check_calls * daily_target:.0f}")
        print(f"Cost/day:   ${per_fact_check_cost * daily_target:.2f}")
        print(f"Cost/month: ${per_fact_check_cost * daily_target * 30:.2f}")
        print(
            "\nThese are extrapolations from real observed calls, not a fixed formula — "
            "re-run after more real fact-checks for a tighter estimate, especially once "
            "claim counts and source counts per reel stabilize."
        )
    else:
        print(
            "\nNo fully-completed fact-check runs (claim_extraction rows) in this window — "
            "can't project a per-fact-check or daily cost yet."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days (default: 7)")
    parser.add_argument(
        "--daily-target", type=int, default=None, help="Fact-checks/day to project (default: MAX_POSTS_PER_DAY)"
    )
    args = parser.parse_args()
    target = args.daily_target if args.daily_target is not None else get_settings().MAX_POSTS_PER_DAY
    asyncio.run(main(args.days, target))
