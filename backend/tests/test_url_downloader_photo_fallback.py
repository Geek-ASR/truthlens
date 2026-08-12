"""Photo-post fallback in url_downloader.py: when yt-dlp reports a post
has no video at all, fetch_from_url() falls back to Instagram's Open
Graph meta tags instead of failing outright. Confirmed live against a
real post (https://www.instagram.com/p/Dbrw0EPhFcU/) during development;
these tests cover the parsing logic and branching precisely so a
regression doesn't require another live network call to catch."""
import pytest

from app.core.exceptions import ProviderError
from app.services.url_downloader import (
    _OG_DESCRIPTION_PATTERN,
    _fetch_photo_via_og_tags,
    _og_tag,
    _parse_count,
    fetch_from_url,
)


# ---------------------------------------------------------------------------
# _og_tag
# ---------------------------------------------------------------------------

def test_og_tag_extracts_and_unescapes_html_entities():
    html_text = (
        '<meta property="og:description" content="13K likes, 222 comments - '
        "thenewindia2 on August 5, 2026: &quot;The second poorest state&quot;. \" />"
    )
    assert _og_tag(html_text, "og:description") == (
        '13K likes, 222 comments - thenewindia2 on August 5, 2026: "The second poorest state". '
    )


def test_og_tag_returns_none_when_missing():
    assert _og_tag("<html><head></head></html>", "og:image") is None


# ---------------------------------------------------------------------------
# _parse_count
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("222", 222),
        ("13K", 13000),
        ("1.5M", 1_500_000),
        ("2.3B", 2_300_000_000),
        ("1,234", 1234),
        ("not-a-number", None),
        ("", None),
    ],
)
def test_parse_count(raw, expected):
    assert _parse_count(raw) == expected


# ---------------------------------------------------------------------------
# _OG_DESCRIPTION_PATTERN
# ---------------------------------------------------------------------------

def test_og_description_pattern_matches_real_captured_format():
    # Exact format captured live from instagram.com/p/Dbrw0EPhFcU/.
    description = (
        '13K likes, 222 comments - thenewindia2 on August 5, 2026: '
        '"The second poorest state by income, but number one in publicity and propaganda". '
    )
    match = _OG_DESCRIPTION_PATTERN.match(description)
    assert match is not None
    likes, comments, handle, date, caption = match.groups()
    assert likes == "13K"
    assert comments == "222"
    assert handle == "thenewindia2"
    assert date == "August 5, 2026"
    assert "second poorest state" in caption


def test_og_description_pattern_tolerates_missing_engagement_counts():
    description = 'thenewindia2 on August 5, 2026: "A caption with no engagement prefix". '
    match = _OG_DESCRIPTION_PATTERN.match(description)
    assert match is not None
    likes, comments, handle, date, caption = match.groups()
    assert likes is None
    assert comments is None
    assert handle == "thenewindia2"


def test_og_description_pattern_returns_none_for_unrecognized_format():
    # A format Instagram might ship in some other locale/variant — the
    # caller must fall back to using the raw description as-is rather
    # than raising, per _fetch_photo_via_og_tags's design.
    assert _OG_DESCRIPTION_PATTERN.match("Some totally different caption text with no structure") is None


# ---------------------------------------------------------------------------
# fetch_from_url branching (network calls mocked at the function boundary)
# ---------------------------------------------------------------------------

def test_fetch_from_url_falls_back_to_photo_on_no_video_error(monkeypatch):
    import app.services.url_downloader as url_downloader

    def fake_download(url, output_dir):
        raise ProviderError("Could not fetch media: Underlying error: ERROR: [Instagram] abc123: There is no video in this post")

    sentinel = url_downloader.UrlFetchResult(
        video_path=None, thumbnail_path=None, caption_text="caption", creator_handle="someone",
        posted_at=None, view_count=None, like_count=None, comment_count=None, hashtags=[], photo_path="/tmp/x.jpg",
    )
    monkeypatch.setattr(url_downloader, "_download_with_retry", fake_download)
    monkeypatch.setattr(url_downloader, "_fetch_photo_via_og_tags", lambda url, output_dir: sentinel)

    result = fetch_from_url("https://www.instagram.com/p/abc123/", "/tmp")

    assert result is sentinel
    assert result.photo_path == "/tmp/x.jpg"


def test_fetch_from_url_reraises_unrelated_provider_errors(monkeypatch):
    import app.services.url_downloader as url_downloader

    def fake_download(url, output_dir):
        raise ProviderError("Could not fetch media: rate limited, try again later")

    monkeypatch.setattr(url_downloader, "_download_with_retry", fake_download)

    with pytest.raises(ProviderError, match="rate limited"):
        fetch_from_url("https://www.instagram.com/p/abc123/", "/tmp")


def test_fetch_photo_via_og_tags_raises_when_no_image_tag_either(monkeypatch):
    import httpx

    import app.services.url_downloader as url_downloader

    class FakeResponse:
        status_code = 200
        text = "<html><head></head></html>"

        def raise_for_status(self):
            pass

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            return FakeResponse()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    with pytest.raises(ProviderError, match="no video AND no photo"):
        _fetch_photo_via_og_tags("https://www.instagram.com/p/deleted123/", "/tmp")
