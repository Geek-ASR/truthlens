"""Fifth mass-sourcing pipeline, for factcrescendo.com's
sitemap-indexed archives. Added after Vishvas's `/viral/`-only filter
was found to be missing most of its real content (see mass_source_
vishvasnews.py's docstring) -- this site has no such subcategory
structure at all, every post IS a fact-check, so no URL-substring
filter is needed or applied; every sitemap URL is in scope.

`robots.txt` is fully open (`Disallow:` with nothing after it -- no
Claude/AI-crawler block, unlike newschecker.in). Sampled 15 English
-subdomain articles before building this: only 1/15 (~7%) referenced
Instagram -- lower density than WebQoof or Alt News, closer to
Vishvas's ~4.6% -- but real.

Fact Crescendo publishes each language as a genuinely SEPARATE
subdomain (not a sub-path the way thequint.com's Hindi WebQoof edition
turned out to be -- see mass_source_thequint.py's own filter-gap fix).
Initially built for english.factcrescendo.com only; checked the other
advertised editions (Hindi/Tamil/Kannada/Telugu/Marathi/Bengali/
Malayalam) and found only tamil/marathi/malayalam actually resolve as
live subdomains today (hindi/kannada/telugu/bengali give DNS failures
-- likely retired, merged into another property, or never launched).
The three real ones have substantial archives of their own (Tamil: 5
post-sitemaps, Marathi: 3, Malayalam: 5 -- comparable combined scale to
the English edition's 4), so extended this pipeline to loop over all
four confirmed-live subdomains rather than staying English-only.

Sitemap index per subdomain (Yoast-style post-sitemap.xml/2/3/...)
rather than a daily-sitemap or page-based archive.

Same JUDGE step as the other pipelines (imported, not duplicated):
local llama3.2 only.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.mass_source_factcrescendo
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
    _is_known_factchecker_account,
    _judge,
    _load_existing_urls,
    _post_id_from_url,
    _USER_AGENT,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO_ROOT / "research" / "results"
_CANDIDATES_PATH = _REPO_ROOT / "research" / "dataset" / "candidates_v2_mass_factcrescendo.jsonl"
_STATE_PATH = _REPO_ROOT / "research" / "dataset" / "mass_sourcing_factcrescendo_checked_articles.json"

# (subdomain, language code) -- hindi/kannada/telugu/bengali checked
# live and found not to resolve (DNS failure), not included.
_SUBDOMAINS = [
    ("english", "en"),
    ("tamil", "ta"),
    ("marathi", "mr"),
    ("malayalam", "ml"),
]


@dataclass
class SimpleCandidate:
    candidate_id: str
    factchecker: str = "factcrescendo.com"
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
    next_n = 1
    for rec in _load_all():
        cid = rec.get("candidate_id", "")
        if cid.startswith("cand-factcrescendo-"):
            try:
                next_n = max(next_n, int(cid.rsplit("-", 1)[-1]) + 1)
            except ValueError:
                continue

    for subdomain, lang_code in _SUBDOMAINS:
        sitemap_index = f"https://{subdomain}.factcrescendo.com/sitemap_index.xml"
        post_sitemap_prefix = f"https://{subdomain}.factcrescendo.com/post-sitemap"
        print(f"=== {subdomain}.factcrescendo.com ===", file=sys.stderr)
        try:
            index_html = _fetch_with_retry(sitemap_index)
        except httpx.HTTPError as exc:
            print(f"  skipping {subdomain}: sitemap index fetch failed ({exc})", file=sys.stderr)
            continue
        all_sitemap_urls = re.findall(r"<loc>([^<]+)</loc>", index_html)
        sitemap_urls = [u for u in all_sitemap_urls if u.startswith(post_sitemap_prefix)]
        print(f"  {len(sitemap_urls)} post-sitemap file(s) found", file=sys.stderr)

        for sitemap_url in sitemap_urls:
            article_urls = _fetch_sitemap_urls(sitemap_url)
            stats["sitemaps_crawled"] += 1
            print(f"  {sitemap_url}: {len(article_urls)} URL(s)", file=sys.stderr)

            for article_url in article_urls:
                stats["articles_seen"] += 1
                # No URL-substring filter needed -- every post on this site
                # is a fact-check (unlike Vishvas/Factly's mixed content).
                if article_url in checked_articles or "/20" not in article_url:
                    continue  # skips non-article sitemap entries like /archive/
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

                    cid = f"cand-factcrescendo-{next_n:04d}"
                    next_n += 1
                    _add(SimpleCandidate(candidate_id=cid, factcheck_article=article_url, social_url=ig_url, media_url=ig_url))
                    _update(cid, "SOCIAL_REFERENCE_FOUND", note=f"Recovered via mass_source_factcrescendo.py sitemap crawl ({subdomain}).")

                    if not retrievable:
                        _update(cid, "REJECTED", note="Not retrievable via yt-dlp.", rejection_reason="Media not retrievable.")
                        stats["candidates_rejected"] += 1
                        continue
                    _update(cid, "MEDIA_RETRIEVABLE", note=f"uploader={uploader}, has_caption={bool(caption)}")

                    if _is_known_factchecker_account(uploader):
                        _update(cid, "REJECTED", note=f"Uploaded by the fact-checker's own account ({uploader}).",
                                rejection_reason=f"Posted by {uploader}, a known fact-checker account -- their own "
                                                  f"repost/documentation of the claim, not the real misinformation spreader.")
                        stats["candidates_rejected"] += 1
                        continue

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
                                claim_type="provenance", language=lang_code)
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
    out_path = _RESULTS_DIR / f"mass_sourcing_factcrescendo_run_{int(time.time())}.json"
    out_path.write_text(json.dumps(stats, indent=2))
    print("\n=== DONE ===", file=sys.stderr)
    print(json.dumps(stats, indent=2), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
