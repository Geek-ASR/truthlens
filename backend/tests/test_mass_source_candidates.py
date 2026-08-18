"""research/MASS_SOURCING_V2.md tooling. Only the pure, deterministic
logic (no network, no Ollama, no filesystem state) -- the pipeline's
own crawl/judge/promote behavior is exercised live, not here."""
from research.benchmark_v2.mass_source_candidates import (
    SourceJudgment,
    _is_known_factchecker_account,
    _post_id_from_url,
)


def test_recognizes_known_factchecker_accounts_case_insensitively():
    assert _is_known_factchecker_account("Vishvas News") is True
    assert _is_known_factchecker_account("vishvas news") is True
    assert _is_known_factchecker_account("Alt News") is True
    assert _is_known_factchecker_account("BOOM Live") is True
    assert _is_known_factchecker_account("Factly") is True


def test_does_not_flag_a_real_looking_unrelated_account():
    # Found live (research/MASS_SOURCING_V2.md): 31% of one pipeline's
    # candidates were the fact-checker's own repost, not a real account
    # -- this must stay narrow enough not to also reject genuine accounts.
    assert _is_known_factchecker_account("Rakhi Sawant") is False
    assert _is_known_factchecker_account("Dwayne Johnson") is False


def test_handles_none_and_empty_uploader():
    assert _is_known_factchecker_account(None) is False
    assert _is_known_factchecker_account("") is False


def test_post_id_extraction_handles_all_three_url_shapes():
    assert _post_id_from_url("https://www.instagram.com/p/ABC123/") == "ABC123"
    assert _post_id_from_url("https://www.instagram.com/reel/DEF456/") == "DEF456"
    assert _post_id_from_url("https://www.instagram.com/tv/GHI789/") == "GHI789"


def test_post_id_extraction_falls_back_to_the_whole_url_when_unmatched():
    assert _post_id_from_url("not-a-real-url") == "not-a-real-url"


def test_out_of_range_confidence_is_clamped_not_rejected():
    # Found live (research/MASS_SOURCING_V2.md): llama3.2 occasionally
    # emits confidence=-1 or -1.0, always paired with
    # is_own_post_the_misinformation=False -- clamping avoids burning
    # retries on a case that was always going to be REJECTED anyway.
    j = SourceJudgment(
        is_own_post_the_misinformation=False, extracted_claim="x",
        extracted_verdict_label="FALSE", confidence=-1.0, reasoning="r",
    )
    assert j.confidence == 0.0

    j2 = SourceJudgment(
        is_own_post_the_misinformation=True, extracted_claim="x",
        extracted_verdict_label="FALSE", confidence=1.5, reasoning="r",
    )
    assert j2.confidence == 1.0

    j3 = SourceJudgment(
        is_own_post_the_misinformation=True, extracted_claim="x",
        extracted_verdict_label="FALSE", confidence=0.85, reasoning="r",
    )
    assert j3.confidence == 0.85
