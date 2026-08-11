"""Source reliability scoring (docs/FACT_CHECK_METHODOLOGY.md §3).

Six of the eight dimensions are computed deterministically at fetch time
from tier classification and metadata. `directness` and `corroboration`
start at a neutral prior and are refined by `update_after_evidence()` once
the (LLM-produced) evidence_analysis stage has actually read the source
against the specific claim — that keeps the LLM's role limited to
judgments it's actually shown evidence for, while the final numeric score
is always a fixed, auditable formula rather than something a model
outputs directly (see METHODOLOGY §3: "the LLM never assigns the final
number directly")."""
from datetime import datetime, timezone
from urllib.parse import urlparse

from app.db.models import SourceTier

_WEIGHTS = {
    "primary_source_status": 0.20,
    "author_identity": 0.05,
    "publication_reputation": 0.20,
    "evidence_transparency": 0.10,
    "recency": 0.10,
    "directness": 0.15,
    "corroboration": 0.15,
    "conflict_of_interest": 0.05,
}

_TIER1_HINTS = (".gov", ".gov.", "parliament", "legislature", "election-commission", "eci.gov")
_TIER2_DOMAINS = {
    "reuters.com": SourceTier.news_wire,
    "apnews.com": SourceTier.news_wire,
    "bbc.com": SourceTier.established_news,
    "bbc.co.uk": SourceTier.established_news,
    "ft.com": SourceTier.established_news,
}
TIER3_FACTCHECK_DOMAINS = {
    "snopes.com": SourceTier.factcheck_org,
    "politifact.com": SourceTier.factcheck_org,
    "factcheck.org": SourceTier.factcheck_org,
    "afp.com": SourceTier.factcheck_org,
    "boomlive.in": SourceTier.factcheck_org,
    "altnews.in": SourceTier.factcheck_org,
    "thequint.com": SourceTier.factcheck_org,
    "indiatoday.in": SourceTier.factcheck_org,
}

_PUBLICATION_REPUTATION_BY_TIER = {
    SourceTier.primary_government: 0.95,
    SourceTier.primary_legal: 0.95,
    SourceTier.primary_data: 0.9,
    SourceTier.news_wire: 0.9,
    SourceTier.established_news: 0.8,
    SourceTier.academic: 0.85,
    SourceTier.factcheck_org: 0.75,
    SourceTier.other: 0.4,
}

_PRIMARY_STATUS_BY_TIER = {
    SourceTier.primary_government: 1.0,
    SourceTier.primary_legal: 1.0,
    SourceTier.primary_data: 1.0,
    SourceTier.news_wire: 0.3,
    SourceTier.established_news: 0.3,
    SourceTier.academic: 0.6,
    SourceTier.factcheck_org: 0.4,
    SourceTier.other: 0.1,
}


def classify_source_tier(url: str) -> SourceTier:
    domain = urlparse(url).netloc.lower().removeprefix("www.")
    if any(hint in domain for hint in _TIER1_HINTS):
        return SourceTier.primary_government
    if domain in _TIER2_DOMAINS:
        return _TIER2_DOMAINS[domain]
    if domain in TIER3_FACTCHECK_DOMAINS:
        return TIER3_FACTCHECK_DOMAINS[domain]
    if domain.endswith(".edu") or domain.endswith(".ac.uk"):
        return SourceTier.academic
    return SourceTier.other


def _recency_score(publication_date: datetime | None) -> float:
    if publication_date is None:
        return 0.5
    now = datetime.now(timezone.utc)
    pub = publication_date if publication_date.tzinfo else publication_date.replace(tzinfo=timezone.utc)
    age_days = max((now - pub).days, 0)
    if age_days <= 30:
        return 1.0
    if age_days <= 365:
        return 0.75
    if age_days <= 365 * 3:
        return 0.5
    return 0.3


def score_source(
    *,
    source_type: SourceTier,
    publication_date: datetime | None,
    author: str | None,
) -> tuple[float, dict]:
    breakdown = {
        "primary_source_status": _PRIMARY_STATUS_BY_TIER[source_type],
        "author_identity": 1.0 if author else 0.4,
        "publication_reputation": _PUBLICATION_REPUTATION_BY_TIER[source_type],
        "evidence_transparency": 0.8 if source_type != SourceTier.other else 0.5,
        "recency": _recency_score(publication_date),
        "directness": 0.6,  # neutral prior, refined by update_after_evidence()
        "corroboration": 0.5,  # neutral prior, refined by update_after_evidence()
        "conflict_of_interest": 0.8,  # no known conflict by default
    }
    score = sum(_WEIGHTS[k] * v for k, v in breakdown.items())
    return round(score, 4), breakdown


def rescore_with_breakdown(breakdown: dict) -> float:
    return round(sum(_WEIGHTS[k] * v for k, v in breakdown.items()), 4)


def update_after_evidence(
    breakdown: dict, *, directness: str, agreeing_count: int, total_independent_count: int
) -> tuple[float, dict]:
    """Refines `directness` and `corroboration` once evidence_analysis has
    actually read this source against the claim, then recomputes the
    final score from the fixed formula (never set directly by the LLM)."""
    updated = dict(breakdown)
    updated["directness"] = 1.0 if directness == "direct" else 0.5
    corroboration = (
        agreeing_count / total_independent_count if total_independent_count > 0 else 0.5
    )
    updated["corroboration"] = min(max(corroboration, 0.0), 1.0)
    return rescore_with_breakdown(updated), updated
