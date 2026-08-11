"""Celery app (docs/ARCHITECTURE.md §5 — Redis + Celery). Phase 1-4 call
the pipeline synchronously from the FastAPI request handlers for
simplicity and easy debugging; these tasks wrap the same orchestrator
functions so Phase 5/6 (automated discovery + scheduling, see
docs/ROADMAP.md) can move to background execution without rewriting
pipeline logic — only the caller changes."""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("truthlens", broker=settings.REDIS_URL, backend=settings.REDIS_URL)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

celery_app.autodiscover_tasks(["app.workers"])
