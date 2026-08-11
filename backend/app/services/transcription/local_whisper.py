"""Self-hosted transcription (TRANSCRIPTION_PROVIDER=local, the default —
see docs/ARCHITECTURE.md §8): no per-minute API cost, no OPENAI_API_KEY,
at the expense of local CPU time. `faster-whisper` is a regular
requirements.txt dependency (no torch — ctranslate2 + onnxruntime only),
so it's installed by default rather than opt-in."""
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
                    "TRANSCRIPTION_PROVIDER=local requires the `faster-whisper` package "
                    "(pip install -r requirements.txt)."
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
