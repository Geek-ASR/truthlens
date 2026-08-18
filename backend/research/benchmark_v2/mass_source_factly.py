"""Third parallel mass-sourcing pipeline, for factly.in's sitemap
-indexed archive (21 sitemap files, ~1000 URLs each, ~21,000 articles
total spanning 2019-2026 -- confirmed live). Unlike vishvasnews.com,
Factly's URLs have no clean "/viral/"-style category prefix -- fact
-checks are mixed in with its other content (data journalism,
infographics) under the same flat URL structure. Confirmed live that
the literal substring "fact-check" appears in the URL slug for its
fact-check articles specifically (distinct from "-infographic",
"-story", etc. suffixes on its other content types), so this pipeline
filters on that substring rather than checking every URL.

newschecker.in was explicitly considered and DROPPED from this
session's mass-sourcing work: its robots.txt explicitly disallows
ClaudeBot/Claude-Web/anthropic-ai. That is a clear publisher directive
to not have Anthropic's models access that site, and using a generic
User-Agent to route around it would be circumventing that directive,
not a gray area -- not done, and should not be done in any future pass
either.

Writes to its own separate file (candidates_v2_mass_factly.jsonl), same
reasoning as mass_source_vishvasnews.py: avoids a write-race against
the other concurrently-running pipelines on the shared candidates_v2.jsonl.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.mass_source_factly
"""
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import trafilatura
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from research.benchmark_v2.extract_instagram_embed import extract_instagram_urls  # noqa: E402
from research.benchmark_v2.mass_source_candidates import (  # noqa: E402
    _fetch_caption_and_uploader,
    _judge,
    _load_existing_urls,
    _post_id_from_url,
    _USER_AGENT,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO_ROOT / "research" / "results"
_CANDIDATES_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_factly.jsonl"
_STATE_PATH = _REPO_ROOT / "research" / "dataset" / "mass_sourcing_factly_checked_articles.json"

_SITEMAP_INDEX = "https://factly.in/sitemap.xml"
_MAX_SITEMAPS = 1  # TEST VALUE -- restore to 21 before the real run


@dataclass
class SimpleCandidate:
    candidate_id: str
    factchecker: str = "factly.in"
    factcheck_article: str | None = None
    social_url: str | None = None
    media_url: str | None = None
    eligibility_status: str = "DISCOVERED"
    rejection_reason: str | None = None
    ground_truth_claim: str | None = None
    ground_truth_label: str | None = None
    claim_type: str | None = None
    language: str | None = None
    media_type: str | None = None
    history: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__


def _load_all() -> list[dict]:
    if not _CANDIDATES_PATH.exists():
        return []
    with open(_CANDIDATES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _save_all(candidates: list[dict]) -> None:
    with open(_CANDIDATES_PATH, "w") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")


def _add(c: SimpleCandidate) -> None:
    candidates = _load_all()
    c.history.append({"status": c.eligibility_status, "at": datetime.now(timezone.utc).isoformat(), "note": "created"})
    candidates.append(c.to_dict())
    _save_all(candidates)


def _update(cid: str, status: str, note: str = "", rejection_reason: str | None = None, **extra) -> None:
    candidates = _load_all()
    for rec in candidates:
        if rec["candidate_id"] == cid:
            rec["eligibility_status"] = status
            if rejection_reason is not None:
                rec["rejection_reason"] = rejection_reason
            rec.update(extra)
            rec.setdefault("history", []).append({"status": status, "at": datetime.now(timezone.utc).isoformat(), "note": note})
    _save_all(candidates)


@retry(
    reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(httpx.HTTPError),
)
def _fetch_with_retry(url: str, timeout: float = 30) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.text


def _fetch_sitemap_urls(sitemap_url: str) -> list[str]:
    try:
        html = _fetch_with_retry(sitemap_url)
    except httpx.HTTPError:
        return []
    return re.findall(r"<loc>([^<]+)</loc>", html)


def _load_checked() -> set[str]:
    if _STATE_PATH.exists():
        return set(json.loads(_STATE_PATH.read_text()))
    return set()


def _save_checked(checked: set[str]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(sorted(checked)))


async def main() -> None:
    provider = OllamaProvider()
    existing_urls = _load_existing_urls()
    for rec in _load_all():
        u = rec.get("social_url")
        if u:
            existing_urls.add(u.rstrip("/"))
    checked_articles = _load_checked()
    stats = {"sitemaps_crawled": 0, "articles_seen": 0, "articles_with_instagram": 0,
              "candidates_checked": 0, "candidates_accepted": 0, "candidates_rejected": 0,
              "candidates_dedup_skipped": 0, "start_time": time.time()}
    # max existing id + 1, not len(...) + 1 -- same fix as the sibling
    # altnews.in and vishvasnews.com pipelines, proactively applied here too.
    next_n = 1
    for rec in _load_all():
        cid = rec.get("candidate_id", "")
        if cid.startswith("cand-factly-"):
            try:
                next_n = max(next_n, int(cid.rsplit("-", 1)[-1]) + 1)
            except ValueError:
                continue

    print("Fetching sitemap index...", file=sys.stderr)
    index_html = _fetch_with_retry(_SITEMAP_INDEX)
    sitemap_urls = re.findall(r"<loc>([^<]+)</loc>", index_html)[:_MAX_SITEMAPS]
    print(f"{len(sitemap_urls)} sitemap file(s) found", file=sys.stderr)

    for sitemap_url in sitemap_urls:
        article_urls = _fetch_sitemap_urls(sitemap_url)
        stats["sitemaps_crawled"] += 1
        print(f"  {sitemap_url}: {len(article_urls)} URL(s)", file=sys.stderr)

        for article_url in article_urls:
            stats["articles_seen"] += 1
            if article_url in checked_articles or "fact-check" not in article_url:
                continue
            checked_articles.add(article_url)

            try:
                with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
                    resp = client.get(article_url)
                    resp.raise_for_status()
                    article_html = resp.text
            except httpx.HTTPError:
                continue

            instagram_urls = extract_instagram_urls(article_html)
            if not instagram_urls:
                continue
            stats["articles_with_instagram"] += 1
            article_text = trafilatura.extract(article_html, include_comments=False, include_tables=False) or article_url

            for ig_url in instagram_urls:
                if ig_url.rstrip("/") in existing_urls:
                    stats["candidates_dedup_skipped"] += 1
                    continue
                existing_urls.add(ig_url.rstrip("/"))

                post_id = _post_id_from_url(ig_url)
                caption, uploader, retrievable = _fetch_caption_and_uploader(post_id)
                stats["candidates_checked"] += 1

                cid = f"cand-factly-{next_n:04d}"
                next_n += 1
                _add(SimpleCandidate(candidate_id=cid, factcheck_article=article_url, social_url=ig_url, media_url=ig_url))
                _update(cid, "SOCIAL_REFERENCE_FOUND", note="Recovered via mass_source_factly.py sitemap crawl.")

                if not retrievable:
                    _update(cid, "REJECTED", note="Not retrievable via yt-dlp.", rejection_reason="Media not retrievable.")
                    stats["candidates_rejected"] += 1
                    continue
                _update(cid, "MEDIA_RETRIEVABLE", note=f"uploader={uploader}, has_caption={bool(caption)}")

                if not caption:
                    _update(cid, "REJECTED", note="No caption available to judge.",
                            rejection_reason="Retrievable but no caption text.")
                    stats["candidates_rejected"] += 1
                    continue

                judgment = await _judge(provider, article_text, caption)
                if judgment is None:
                    _update(cid, "REJECTED", note="Judge call failed.", rejection_reason="Local LLM judgment call failed.")
                    stats["candidates_rejected"] += 1
                    continue

                if judgment.is_own_post_the_misinformation and judgment.confidence >= 0.7:
                    _update(cid, "ELIGIBLE",
                            note=f"llama3.2 judge (confidence={judgment.confidence:.2f}): {judgment.reasoning}. "
                                 "NOT yet human/manual-reviewed.",
                            ground_truth_claim=judgment.extracted_claim, ground_truth_label=judgment.extracted_verdict_label,
                            claim_type="provenance", language="en")
                    stats["candidates_accepted"] += 1
                    print(f"    [{cid}] {ig_url} -> ACCEPTED (confidence={judgment.confidence:.2f}): {judgment.extracted_claim[:80]}", file=sys.stderr)
                else:
                    _update(cid, "REJECTED", note=f"llama3.2 judge: {judgment.reasoning}",
                            rejection_reason=f"Judged not the source (confidence={judgment.confidence:.2f}): {judgment.reasoning}")
                    stats["candidates_rejected"] += 1

            if stats["candidates_checked"] % 5 == 0 and stats["candidates_checked"] > 0:
                _save_checked(checked_articles)

        _save_checked(checked_articles)
        print(f"  progress: {stats['candidates_accepted']} accepted / {stats['candidates_checked']} checked so far", file=sys.stderr)

    stats["elapsed_seconds"] = time.time() - stats["start_time"]
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"mass_sourcing_factly_run_{int(time.time())}.json"
    out_path.write_text(json.dumps(stats, indent=2))
    print("\n=== DONE ===", file=sys.stderr)
    print(json.dumps(stats, indent=2), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
