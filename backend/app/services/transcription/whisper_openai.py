"""OpenAI Whisper API transcription (default provider,
docs/API_REQUIREMENTS.md §3)."""
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.exceptions import ProviderError
from app.services.transcription.base import TranscriptionProvider, TranscriptionResult, TranscriptSegment


class WhisperOpenAIProvider(TranscriptionProvider):
    def __init__(self):
        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            self._client = None
        else:
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        if self._client is None:
            raise ProviderError("OPENAI_API_KEY is not set; cannot transcribe audio.")

        with open(audio_path, "rb") as f:
            response = await self._client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        segments = [
            TranscriptSegment(start=seg.start, end=seg.end, text=seg.text)
            for seg in (response.segments or [])
        ]
        return TranscriptionResult(
            full_text=response.text, segments=segments, language=getattr(response, "language", None)
        )


def get_transcription_provider() -> TranscriptionProvider:
    settings = get_settings()
    if settings.TRANSCRIPTION_PROVIDER == "local":
        from app.services.transcription.local_whisper import LocalWhisperProvider

        return LocalWhisperProvider()
    return WhisperOpenAIProvider()
