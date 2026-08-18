"""Sourcing-tooling fix (research/BENCHMARK_COLLECTION_GUIDE.md): recovers
the real Instagram post/reel URL from a fact-check article that embeds
it via Instagram's own oEmbed widget rather than a plain, quotable link
in the article text.

Real gap found live (2026-08-18): WebFetch's AI-summarized page fetch
silently drops embed-widget HTML, so any article using the widget
(rather than a plain instagram.com/p/... or /reel/... link in the
visible text) got misdiagnosed as "no Instagram link" and rejected --
at least one real, otherwise-eligible candidate (cand-2026-08-17-005)
was lost to this before being caught and reprocessed. Instagram's own
embed code always sets a `data-instgrm-permalink` attribute on the
`<blockquote class="instagram-media">` element with the exact canonical
post URL -- fetching the RAW page HTML (not an AI summary of it) and
pattern-matching against that attribute recovers it directly, with zero
new search cost for candidates already discovered.

Run standalone: cd backend && ./.venv/bin/python -m research.benchmark_v2.extract_instagram_embed <article_url>
Or import extract_instagram_urls(html_text) / fetch_and_extract(article_url)
into a sourcing script.
"""
import re
import sys

import httpx

_PERMALINK_PATTERN = re.compile(r'data-instgrm-permalink="([^"]+)"')
_PLAIN_URL_PATTERN = re.compile(r'instagram\.com/(?:p|reel|tv)/[A-Za-z0-9_-]+/?')
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def extract_instagram_urls(html_text: str) -> list[str]:
    """Returns deduplicated, canonicalized Instagram post/reel URLs found
    in raw page HTML -- both the oEmbed widget's own permalink attribute
    (the case WebFetch's summarization drops) and any plain link already
    present in visible text (so this function is a strict superset of
    what the old approach could find, not a replacement with different
    blind spots)."""
    found = set()
    for match in _PERMALINK_PATTERN.finditer(html_text):
        plain = _PLAIN_URL_PATTERN.search(match.group(1))
        if plain:
            found.add(f"https://www.{plain.group(0).rstrip('/')}/")
    for match in _PLAIN_URL_PATTERN.finditer(html_text):
        found.add(f"https://www.{match.group(0).rstrip('/')}/")
    return sorted(found)


def fetch_and_extract(article_url: str, *, timeout: float = 20.0) -> list[str]:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
        response = client.get(article_url)
        response.raise_for_status()
    return extract_instagram_urls(response.text)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: extract_instagram_embed.py <article_url>", file=sys.stderr)
        sys.exit(1)
    urls = fetch_and_extract(sys.argv[1])
    if urls:
        for u in urls:
            print(u)
    else:
        print("No Instagram post/reel URLs found (checked both embed-widget permalinks and plain links).", file=sys.stderr)
        sys.exit(1)
