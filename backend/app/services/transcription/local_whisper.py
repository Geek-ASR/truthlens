"""Self-hosted transcription fallback (TRANSCRIPTION_PROVIDER=local),
avoids per-minute API cost at the expense of needing local compute
(docs/ARCHITECTURE.md §5). Requires the optional `faster-whisper` package
— not installed by default; see requirements-local-whisper.txt."""
from app.core.exceptions import ProviderError
from app.services.transcription.base import TranscriptionProvider, TranscriptionResult, TranscriptSegment

_MODEL_SIZE = "base"


class LocalWhisperProvider(TranscriptionProvider):
    def __init__(self):
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise ProviderError(
                    "TRANSCRIPTION_PROVIDER=local requires `pip install -r "
                    "requirements-local-whisper.txt` (faster-whisper)."
                ) from exc
            self._model = WhisperModel(_MODEL_SIZE, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        model = self._load()
        segments_iter, info = model.transcribe(audio_path, beam_size=5)
        segments = [
            TranscriptSegment(start=seg.start, end=seg.end, text=seg.text) for seg in segments_iter
        ]
        full_text = " ".join(s.text.strip() for s in segments)
        return TranscriptionResult(full_text=full_text, segments=segments, language=info.language)
