"""Stage 10: publish an approved fact_check via the official Meta Graph
API (product spec §21, docs/API_REQUIREMENTS.md §1). Only ever called
after human approval in the default configuration
(settings.HUMAN_APPROVAL_MODE)."""
import hashlib

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PublishError
from app.core.security import decrypt_secret
from app.db.models import (
    ActorType,
    FactCheck,
    FactCheckStatus,
    GeneratedPost,
    InstagramAccount,
    PublishingJob,
    PublishingJobStatus,
    Slide,
)
from app.pipeline.audit import record_audit
from app.services.instagram.graph_client import InstagramGraphClient
from app.services.storage.s3 import get_storage_client


async def publish_fact_check(
    db: AsyncSession,
    fact_check: FactCheck,
    generated_post: GeneratedPost,
    instagram_account: InstagramAccount,
    slides: list[Slide],
    job: PublishingJob,
) -> PublishingJob:
    if fact_check.status == FactCheckStatus.published:
        raise PublishError(f"fact_check {fact_check.id} is already published; refusing to publish again.")

    storage = get_storage_client()

    if not instagram_account.access_token_encrypted:
        raise PublishError(
            "This Instagram account has no stored access token. Complete OAuth connection first "
            "(see docs/API_REQUIREMENTS.md §1)."
        )
    access_token = decrypt_secret(bytes(instagram_account.access_token_encrypted))
    client = InstagramGraphClient(access_token=access_token, ig_user_id=instagram_account.ig_user_id)

    ordered_slides = sorted(slides, key=lambda s: s.position)
    image_urls = [storage.public_url(s.image_storage_key) for s in ordered_slides]

    job.status = PublishingJobStatus.publishing
    job.attempt_count += 1
    await db.flush()

    try:
        child_ids, carousel_id, ig_media_id, permalink = await client.publish_full_carousel(
            image_urls, fact_check.caption_text or ""
        )
    except PublishError as exc:
        job.status = PublishingJobStatus.failed
        job.last_error = str(exc)
        await db.flush()
        await record_audit(
            db,
            entity_type="publishing_job",
            entity_id=job.id,
            actor_type=ActorType.system,
            actor="instagram_publisher",
            action="publish_failed",
            output_summary={"error": str(exc)},
        )
        raise

    job.status = PublishingJobStatus.published
    job.media_container_ids = {"children": child_ids}
    job.carousel_container_id = carousel_id
    job.ig_media_id = ig_media_id
    job.permalink = permalink

    fact_check.status = FactCheckStatus.published
    await db.flush()

    await record_audit(
        db,
        entity_type="fact_check",
        entity_id=fact_check.id,
        actor_type=ActorType.system,
        actor="instagram_publisher",
        action="publish",
        output_summary={"ig_media_id": ig_media_id, "permalink": permalink},
    )
    return job


def build_idempotency_key(fact_check_id, slide_ids: list) -> str:
    raw = f"{fact_check_id}:" + ",".join(sorted(str(s) for s in slide_ids))
    return hashlib.sha256(raw.encode()).hexdigest()
