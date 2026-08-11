"""Stage 2a: speech-to-text."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import ActorType, IngestionStatus, Reel
from app.pipeline.audit import record_audit
from app.services.transcription.whisper_openai import get_transcription_provider


async def transcribe_reel(db: AsyncSession, reel: Reel, audio_path: str) -> Reel:
    settings = get_settings()
    reel.ingestion_status = IngestionStatus.transcribing
    await db.flush()

    provider = get_transcription_provider()
    try:
        result = await provider.transcribe(audio_path)
    except Exception:
        reel.ingestion_status = IngestionStatus.failed
        await db.flush()
        raise

    reel.transcript = result.full_text
    reel.transcript_segments = [s.model_dump() for s in result.segments]
    reel.ingestion_status = IngestionStatus.transcribed
    await db.flush()

    await record_audit(
        db,
        entity_type="reel",
        entity_id=reel.id,
        actor_type=ActorType.ai_stage,
        actor=f"transcription:{settings.TRANSCRIPTION_PROVIDER}",
        action="transcribe",
        input_summary={"audio_path_provided": True},
        output_summary={"segment_count": len(result.segments), "language": result.language},
    )
    return reel
