class TruthLensError(Exception):
    """Base application error."""


class NotFoundError(TruthLensError):
    pass


class DuplicateFactCheckError(TruthLensError):
    def __init__(self, duplicate_of_id: str, reason: str):
        self.duplicate_of_id = duplicate_of_id
        self.reason = reason
        super().__init__(f"Duplicate of fact_check {duplicate_of_id}: {reason}")


class ValidationFailedError(TruthLensError):
    """Anti-hallucination validation failed; verdict was downgraded."""


class PublishError(TruthLensError):
    pass


class ProviderError(TruthLensError):
    """External API (LLM, search, transcription, Instagram) call failed."""
