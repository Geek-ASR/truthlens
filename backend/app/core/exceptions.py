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


class ResearchFailedError(TruthLensError):
    """Every research query for a claim failed at the infrastructure level
    (search provider unavailable/misconfigured, network failure) — no
    query actually executed and returned a real result. This is distinct
    from a claim that was genuinely researched and turned up little or no
    evidence (that's a legitimate UNVERIFIED verdict). RESEARCH_FAILED
    must never be silently turned into UNVERIFIED and must never reach a
    publishable fact_check — see docs/CURRENT_ARCHITECTURE.md §10."""
