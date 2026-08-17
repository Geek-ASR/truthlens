"""research/RESEARCH_ROADMAP_V2.md Phase 7 (evidence reasoning) candidate
schema -- NOT wired into production (app/pipeline/evidence_analysis.py
still uses the 4-category app.schemas.evidence.EvidenceAnalysisItem).
This exists purely for the paired A/B comparison Phase 7's own stopping
condition requires before any integration decision.

Governing brief Step 12 names 6-7 new category labels but calls the
target "the 8-category scheme" -- an internal inconsistency in the
brief's own text. Resolved here as a disclosed judgment call, not
silently picked: 4 new categories, chosen for direct, motivated overlap
with real findings already made THIS session rather than the full
list verbatim --

- SAME_EVENT_WRONG_ENTITY: the semantic complement to Check 7
  (app.pipeline.validation, entity consistency, Phase 4) -- that check
  is deterministic/keyword-based and can miss cases needing real
  reading comprehension; this category is the LLM-side equivalent.
- TEMPORALLY_MISMATCHED: the semantic complement to Check 6 (temporal
  consistency, Phase 5) for the same reason.
- INSUFFICIENT_DETAIL: directly motivated by this session's own
  EXP-015 finding and the original EVIDENCE_EVALUATION.md's "single
  most important finding" -- most primary-tier sources are topically
  right but too generic (homepages, portals) to confirm one specific
  atomic fact. Currently that failure mode has nowhere to go but
  `irrelevant`, which conflates it with genuinely unrelated content.
- MENTIONS_ONLY: on-topic but evidentially empty -- the source
  mentions the claim's subject in passing with no substantive content
  bearing on whether the claim is true, distinct from both irrelevant
  (unrelated) and insufficient_detail (relevant AND has real content,
  just not specific enough).

SAME_ENTITY_WRONG_EVENT and a separate PARTIALLY_SUPPORTS/
PARTIALLY_CONTRADICTS pair from the brief's own list were deliberately
NOT added, to land at exactly 8 total (4 original + 4 new) matching the
brief's own "8-category" language, rather than the 10-11 a literal
reading of its full list would produce."""
import enum
import uuid

from pydantic import BaseModel

from app.schemas.common import EvidenceDirectness


class EvidenceStanceV2(str, enum.Enum):
    """Candidate-only -- deliberately NOT in app/db/models.py (no DB
    column, no migration) until Phase 7's own paired comparison decides
    whether to integrate. A plain schema-layer enum, not a DB enum,
    since nothing here is ever persisted."""

    supports = "supports"
    contradicts = "contradicts"
    provides_context = "provides_context"
    irrelevant = "irrelevant"
    same_event_wrong_entity = "same_event_wrong_entity"
    temporally_mismatched = "temporally_mismatched"
    insufficient_detail = "insufficient_detail"
    mentions_only = "mentions_only"


class EvidenceAnalysisItemV2(BaseModel):
    source_id: uuid.UUID
    stance: EvidenceStanceV2
    explanation: str
    directness: EvidenceDirectness
