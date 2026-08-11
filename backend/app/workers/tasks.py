"""Background task wrappers. Each task opens its own DB session and runs
the same pipeline stage functions the synchronous API routes use
(app.pipeline.*) — see celery_app.py docstring for why these exist
alongside the synchronous request-handler path."""
import asyncio

from sqlalchemy import select

from app.core.logging import get_logger
from app.db.models import Claim, Reel
from app.db.session import AsyncSessionLocal
from app.pipeline.orchestrator import analyze_reel, build_fact_check
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


def _run(coro):
    return asyncio.run(coro)


@celery_app.task(name="truthlens.analyze_reel", bind=True, max_retries=2, default_retry_delay=60)
def analyze_reel_task(self, reel_id: str) -> str:
    async def _do():
        async with AsyncSessionLocal() as db:
            reel = (await db.execute(select(Reel).where(Reel.id == reel_id))).scalar_one()
            await analyze_reel(db, reel)
            await db.commit()
            return str(reel.id)

    try:
        return _run(_do())
    except Exception as exc:  # noqa: BLE001
        logger.error("analyze_reel_task_failed", reel_id=reel_id, error=str(exc))
        raise self.retry(exc=exc) from exc


@celery_app.task(name="truthlens.build_fact_check", bind=True, max_retries=1)
def build_fact_check_task(self, claim_id: str) -> str:
    async def _do():
        async with AsyncSessionLocal() as db:
            claim = (await db.execute(select(Claim).where(Claim.id == claim_id))).scalar_one()
            fact_check = await build_fact_check(db, claim)
            await db.commit()
            return str(fact_check.id)

    return _run(_do())
