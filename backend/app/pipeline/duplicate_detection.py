"""Stage: duplicate detection before a fact_check can enter the review
queue (product spec §27, docs/FACT_CHECK_METHODOLOGY.md §8).

MVP implementation checks (a) exact reel re-upload via
`media_content_hash` and (b) fuzzy claim-text similarity against existing
fact-checks' primary claims via difflib — no extra embedding API call
required. `claims.embedding` (pgvector) is provisioned in the schema for
a stronger semantic version later; this function is the seam to upgrade
without changing callers."""
from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Claim, FactCheck, FactCheckStatus, Reel

_CLAIM_SIMILARITY_THRESHOLD = 0.85


@dataclass
class DuplicateMatch:
    fact_check_id: object
    reason: str


async def find_duplicate(db: AsyncSession, reel: Reel, primary_claim: Claim) -> DuplicateMatch | None:
    if reel.media_content_hash:
        result = await db.execute(
            select(FactCheck)
            .join(Reel, FactCheck.reel_id == Reel.id)
            .where(
                Reel.media_content_hash == reel.media_content_hash,
                Reel.id != reel.id,
                FactCheck.status != FactCheckStatus.rejected,
                FactCheck.duplicate_of_fact_check_id.is_(None),
            )
        )
        existing = result.scalars().first()
        if existing:
            return DuplicateMatch(existing.id, "Same reel media (content hash match) already fact-checked.")

    result = await db.execute(
        select(FactCheck, Claim)
        .join(Claim, FactCheck.primary_claim_id == Claim.id)
        .where(
            Claim.id != primary_claim.id,
            FactCheck.status != FactCheckStatus.rejected,
            FactCheck.duplicate_of_fact_check_id.is_(None),
        )
    )
    for fact_check, claim in result.all():
        similarity = SequenceMatcher(None, claim.text.lower(), primary_claim.text.lower()).ratio()
        if similarity >= _CLAIM_SIMILARITY_THRESHOLD:
            return DuplicateMatch(
                fact_check.id, f"Similar claim already fact-checked (text similarity {similarity:.2f})."
            )

    return None
