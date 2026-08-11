"""Shared helper for writing to audit_logs. Every pipeline stage call and
every human dashboard action must go through this (docs/DATA_MODEL.md
audit_logs, docs/ARCHITECTURE.md §25: "do not rely on hidden LLM reasoning
as the audit trail — store concise structured explanations")."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ActorType, AuditLog


async def record_audit(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_type: ActorType,
    actor: str,
    action: str,
    input_summary: dict | None = None,
    output_summary: dict | None = None,
    prompt_version: str | None = None,
    tokens: dict | None = None,
) -> AuditLog:
    """`tokens` (from LLMCallResult.token_usage_dict()) is merged into
    output_summary under a "tokens" key for every ai_stage call — this is
    what scripts/estimate_costs.py sums to answer real cost/volume
    questions instead of guessing (see docs/API_REQUIREMENTS.md §2)."""
    merged_output = dict(output_summary or {})
    if tokens is not None:
        merged_output["tokens"] = tokens

    log = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_type=actor_type,
        actor=actor,
        action=action,
        input_summary=input_summary,
        output_summary=merged_output or None,
        prompt_version=prompt_version,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()
    return log
