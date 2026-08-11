"""Re-exports the DB-layer enums for use as API schema types. These are
plain str Enums with no ORM behavior, so sharing them between the DB and
API layers keeps verdict/claim-type/etc. vocabulary single-sourced
(see docs/DATA_MODEL.md) instead of drifting into two parallel lists."""
from app.db.models import (
    ActorType,
    ClaimStatus,
    ClaimType,
    ConfidenceBand,
    DiscoverySource,
    EvidenceDirectness,
    EvidenceStance,
    FactCheckStatus,
    IngestionStatus,
    InstagramAccountStatus,
    MetricScope,
    Platform,
    PublishingJobStatus,
    SlideType,
    SourceTier,
    TargetTier,
    UserRole,
    ValidationStatus,
    VerdictLabel,
)

__all__ = [
    "ActorType",
    "ClaimStatus",
    "ClaimType",
    "ConfidenceBand",
    "DiscoverySource",
    "EvidenceDirectness",
    "EvidenceStance",
    "FactCheckStatus",
    "IngestionStatus",
    "InstagramAccountStatus",
    "MetricScope",
    "Platform",
    "PublishingJobStatus",
    "SlideType",
    "SourceTier",
    "TargetTier",
    "UserRole",
    "ValidationStatus",
    "VerdictLabel",
]
