from abc import ABC, abstractmethod

from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResult(BaseModel):
    full_text: str
    segments: list[TranscriptSegment]
    language: str | None = None


class TranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        raise NotImplementedError
