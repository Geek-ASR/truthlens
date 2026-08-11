from datetime import datetime, timedelta, timezone

from app.db.models import SourceTier
from app.pipeline.source_scoring import classify_source_tier, score_source, update_after_evidence


def test_classifies_known_tier2_and_tier3_domains():
    assert classify_source_tier("https://www.reuters.com/world/some-story") == SourceTier.news_wire
    assert classify_source_tier("https://www.snopes.com/fact-check/thing") == SourceTier.factcheck_org
    assert classify_source_tier("https://randomblog.example/post") == SourceTier.other


def test_classifies_gov_domains_as_primary():
    assert classify_source_tier("https://ministry.gov.in/press-release") == SourceTier.primary_government


def test_classifies_major_established_outlets_beyond_the_original_hardcoded_few():
    # Regression test for a real gap found live (docs/CURRENT_ARCHITECTURE.md
    # §10): genuinely major, established outlets and a primary case-law
    # database were falling through to "other" simply because they weren't
    # US/UK names, understating their reliability score for no real reason.
    assert classify_source_tier("https://timesofindia.indiatimes.com/india/x") == SourceTier.established_news
    assert classify_source_tier("https://www.thehindu.com/news/national/x") == SourceTier.established_news
    assert classify_source_tier("https://indiankanoon.org/doc/167974121/") == SourceTier.primary_legal
    assert classify_source_tier("https://www.nytimes.com/2026/x") == SourceTier.established_news


def test_primary_government_scores_higher_than_random_blog():
    now = datetime.now(timezone.utc)
    gov_score, _ = score_source(source_type=SourceTier.primary_government, publication_date=now, author="Ministry")
    other_score, _ = score_source(source_type=SourceTier.other, publication_date=now, author=None)
    assert gov_score > other_score


def test_recency_reduces_score_for_old_sources():
    now = datetime.now(timezone.utc)
    old_date = now - timedelta(days=365 * 5)
    recent_score, _ = score_source(source_type=SourceTier.established_news, publication_date=now, author="A")
    old_score, _ = score_source(source_type=SourceTier.established_news, publication_date=old_date, author="A")
    assert recent_score > old_score


def test_update_after_evidence_raises_corroboration_when_sources_agree():
    _, breakdown = score_source(source_type=SourceTier.established_news, publication_date=None, author=None)
    new_score, new_breakdown = update_after_evidence(
        breakdown, directness="direct", agreeing_count=3, total_independent_count=3
    )
    assert new_breakdown["corroboration"] == 1.0
    assert new_breakdown["directness"] == 1.0

    lonely_score, lonely_breakdown = update_after_evidence(
        breakdown, directness="indirect", agreeing_count=0, total_independent_count=3
    )
    assert lonely_breakdown["corroboration"] == 0.0
    assert new_score > lonely_score


def test_update_after_evidence_clamps_corroboration_to_one():
    # Regression test: agreeing_count must never be able to exceed
    # total_independent_count in practice, but the clamp is a defensive
    # backstop so a mismatched caller can't push the score above 1.0.
    _, breakdown = score_source(source_type=SourceTier.established_news, publication_date=None, author=None)
    _, new_breakdown = update_after_evidence(
        breakdown, directness="direct", agreeing_count=5, total_independent_count=2
    )
    assert new_breakdown["corroboration"] == 1.0
