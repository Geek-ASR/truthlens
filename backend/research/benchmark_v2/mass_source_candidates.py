"""Automated, high-throughput sourcing pipeline (research/BENCHMARK_COLLECTION_GUIDE.md),
replacing the one-article-at-a-time manual WebFetch workflow that made
this session's earlier sourcing rounds slow. Built specifically because
manual verification could not plausibly reach a several-hundred-item
target in "several hours" -- this automates every step that doesn't
require real judgment, and uses ONLY the local Ollama model (llama3.2,
explicitly NOT Gemini, per direct instruction) for the one step that
does.

Pipeline, per fact-checker archive:
1. CRAWL: paginate the archive's raw HTML (httpx, not WebFetch --
   article title/URL extraction is a pure parsing task, not one that
   benefits from AI summarization) up to _MAX_PAGES.
2. EXTRACT: for each article, run extract_instagram_embed.py's
   fetch_and_extract() to find Instagram URLs (widget permalinks +
   plain links, both).
3. DEDUP: skip URLs already in items.jsonl/items_v2.jsonl/candidates_v2.jsonl.
4. VERIFY: yt-dlp --simulate for retrievability; pull the post's own
   caption/uploader directly via yt-dlp metadata (never inferred from
   the article).
5. JUDGE: a local llama3.2 structured call, given (a) the article's own
   full text (trafilatura-extracted, not AI-summarized-then-re-read)
   and (b) the Instagram post's own real caption, decides whether THAT
   caption itself asserts the claim being fact-checked (this session's
   key, hard-won lesson: most cited Instagram posts are the accurate
   ORIGINAL a fact-checker links as evidence, not the misinformation
   itself -- see research/results/mass_sourcing_*.json for the running
   tally of this distinction).
6. LOG: every candidate (accepted or rejected) is written to
   candidates_v2.jsonl with full reasoning via candidate_tracker.py --
   nothing is silently dropped. High-confidence accepted candidates are
   marked ELIGIBLE for a follow-up promote_eligible_candidates.py run;
   everything else is REJECTED with the judge's own stated reasoning.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.mass_source_candidates
"""
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx
import trafilatura
from pydantic import BaseModel, Field

_YT_DLP_BIN = str(Path(sys.prefix) / "bin" / "yt-dlp")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from research.benchmark_v2.candidate_tracker import Candidate, add_candidate, update_status  # noqa: E402
from research.benchmark_v2.extract_instagram_embed import extract_instagram_urls  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO_ROOT / "research" / "results"
_STATE_PATH = _REPO_ROOT / "research" / "dataset" / "mass_sourcing_checked_articles.json"

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
# research/RESEARCH_ROADMAP_V2.md-adjacent finding: altnews.in/type/fact-check/
# (the broad category, not the narrower viral-videos claim-type subcategory)
# paginates cleanly via raw HTML through page 498 -- confirmed live via
# binary search -- roughly 6,900+ articles total, a much larger real pool
# than the ~150-article viral-videos subcategory alone.
_MAX_PAGES_PER_ARCHIVE = 498
_MODEL = "llama3.2"  # explicitly local -- never Gemini for this pipeline

_ARCHIVES = [
    {"name": "altnews-fact-check", "factchecker": "altnews.in",
     "url_template": "https://www.altnews.in/type/fact-check/page/{page}/",
     "article_url_prefix": "https://www.altnews.in/"},
]
# boomlive.in/fact-check is JS-rendered (Next.js) -- confirmed live that its
# raw server HTML contains no real article links, only nav/footer/tag
# boilerplate, so it cannot be crawled this way. Individual BOOM article
# PAGES still fetch fine (used elsewhere this session via
# extract_instagram_embed.py) -- only the LISTING page is unreachable
# without a JS-executing fetch this pipeline doesn't have. Not included in
# _ARCHIVES; BOOM candidates from earlier manual rounds remain valid.

_NON_ARTICLE_SLUGS = {
    "donate", "methodology-for-fact-checking", "sourcing-of-information", "editorial-policy",
    "correction-policy", "transparency-of-funding", "about-us", "contact-us", "team",
    "fact-check", "fact_checks_claim_type",
}


class SourceJudgment(BaseModel):
    is_own_post_the_misinformation: bool = Field(
        description="True only if THIS Instagram post's own caption/text itself asserts the false claim "
        "the article is debunking -- not merely referenced as evidence, comparison, or the true original."
    )
    extracted_claim: str = Field(description="The specific false claim being fact-checked, in one sentence.")
    extracted_verdict_label: str = Field(
        description="One of: FALSE, MOSTLY_FALSE, MISLEADING, MISSING_CONTEXT, TRUE, MOSTLY_TRUE, UNVERIFIED, OUTDATED"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence the post IS the misinformation source.")
    reasoning: str = Field(description="One or two sentences justifying the judgment, citing specific text from the caption or article.")


_JUDGE_SYSTEM_PROMPT = """You are helping build a fact-checking research benchmark. You will be given \
the full text of a professional fact-check article, and the actual caption/text of a specific \
Instagram post the article references.

Your ONLY job: decide whether THIS Instagram post's own caption is itself the misinformation being \
debunked -- i.e. does the post's own text assert the false claim? Many fact-check articles cite an \
Instagram post as evidence of the TRUE, accurate original event, while the actual false claim was \
posted separately (often on X/Twitter, sometimes deleted) by a different account. In that common case, \
is_own_post_the_misinformation must be False, even though the post is clearly relevant to the story.

Only set is_own_post_the_misinformation=True when the caption text itself makes the specific false \
assertion the article is fact-checking -- not when the post merely shows related real footage, is \
tagged/mentioned, or is cited as a comparison/rebuttal."""


def _crawl_archive_page(url: str) -> list[tuple[str, str]]:
    with httpx.Client(timeout=20, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
        response = client.get(url)
        if response.status_code != 200:
            return []
        html = response.text
    matches = re.findall(r'<a[^>]+href="(https://www\.(?:altnews|boomlive)\.in/[a-z0-9/-]+/?)"[^>]*>([^<]{15,150})</a>', html)
    seen, out = set(), []
    for article_url, title in matches:
        slug = article_url.rstrip("/").split("/")[-1]
        # /author/, /hindi/, /type/, /fact_checks_claim_type/ are bylines,
        # translated-duplicate pages, and category links, not real articles.
        if (
            slug in _NON_ARTICLE_SLUGS
            or article_url in seen
            or "/author/" in article_url
            or "/hindi/" in article_url
            or "/type/" in article_url
            or "/fact_checks_claim_type/" in article_url
            or "/page/" in article_url
        ):
            continue
        seen.add(article_url)
        out.append((article_url, title.strip()))
    return out


def _load_existing_urls() -> set[str]:
    urls = set()
    for fn in ("items.jsonl", "items_v2.jsonl"):
        path = _REPO_ROOT / "research" / "dataset" / fn
        if path.exists():
            with open(path) as f:
                for line in f:
                    d = json.loads(line)
                    u = d.get("original_url") or d.get("source_url")
                    if u:
                        urls.add(u.rstrip("/"))
    candidates_path = _REPO_ROOT / "research" / "dataset" / "candidates_v2.jsonl"
    if candidates_path.exists():
        with open(candidates_path) as f:
            for line in f:
                d = json.loads(line)
                u = d.get("social_url")
                if u:
                    urls.add(u.rstrip("/"))
    return urls


def _load_checked_articles() -> set[str]:
    if _STATE_PATH.exists():
        return set(json.loads(_STATE_PATH.read_text()))
    return set()


def _save_checked_articles(checked: set[str]) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(sorted(checked)))


def _post_id_from_url(url: str) -> str:
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else url


def _fetch_caption_and_uploader(post_id: str) -> tuple[str | None, str | None, bool]:
    """Returns (caption, uploader, retrievable). Never raises -- a real
    fetch failure is a real, reportable outcome, not a crash."""
    import subprocess

    try:
        result = subprocess.run(
            [_YT_DLP_BIN, "--simulate", "--no-warnings", "--print", "%(description)s|||UPLOADER|||%(uploader)s",
             f"https://www.instagram.com/p/{post_id}/"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0 and "No video formats found" not in result.stderr and "no video in this post" not in result.stderr.lower():
            return None, None, False
        out = result.stdout.strip()
        if "|||UPLOADER|||" in out:
            caption, uploader = out.split("|||UPLOADER|||", 1)
            return (caption.strip() or None), (uploader.strip() or None), True
        return None, None, True  # retrievable but no metadata line (e.g. multi-item carousel)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None, None, False


async def _judge(provider: OllamaProvider, article_text: str, caption: str) -> SourceJudgment | None:
    user_content = (
        f"FACT-CHECK ARTICLE TEXT:\n{article_text[:6000]}\n\n"
        f"INSTAGRAM POST'S OWN CAPTION:\n{caption[:2000]}"
    )
    try:
        result = await provider.structured_call(
            model=_MODEL, system_prompt=_JUDGE_SYSTEM_PROMPT, user_content=user_content,
            output_schema=SourceJudgment, prompt_version="mass_sourcing_judge.v1",
        )
        judgment = result.parsed
        # Same "schema-valid but substantively empty" pattern this whole
        # session found in every other LLM stage -- one retry, but ONLY on
        # the accept path (this is a triage pipeline optimized for
        # throughput; rejections don't need a human-readable reason to
        # stay correctly rejected, but an accepted candidate does, since it
        # heads toward a follow-up spot-check that needs something to check).
        if judgment.is_own_post_the_misinformation and not judgment.reasoning.strip():
            retry_result = await provider.structured_call(
                model=_MODEL, system_prompt=_JUDGE_SYSTEM_PROMPT, user_content=user_content,
                output_schema=SourceJudgment, prompt_version="mass_sourcing_judge.v1",
            )
            if retry_result.parsed.reasoning.strip():
                judgment = retry_result.parsed
        return judgment
    except Exception as exc:  # noqa: BLE001 -- one bad judgment call must not kill the whole run
        print(f"    judge call failed: {exc}", file=sys.stderr)
        return None


def _next_candidate_n() -> int:
    """Derived from the highest existing cand-mass-NNNN id, not hardcoded
    to 1 -- found live: restarting this script after a crash with
    existing cand-mass-0001..0055 records still in candidates_v2.jsonl
    (from before the crash) immediately collided on 'cand-mass-0001
    already exists' and crashed again, since a hardcoded start ignores
    whatever this same pipeline already created in a prior run. Mirrors
    promote_eligible_candidates.py's own _next_item_ids() pattern."""
    from research.benchmark_v2.candidate_tracker import _load_all as _load_all_candidates

    max_n = 0
    for c in _load_all_candidates():
        cid = c.get("candidate_id", "")
        if cid.startswith("cand-mass-"):
            try:
                max_n = max(max_n, int(cid.rsplit("-", 1)[-1]))
            except ValueError:
                continue
    return max_n + 1


async def main() -> None:
    provider = OllamaProvider()
    existing_urls = _load_existing_urls()
    checked_articles = _load_checked_articles()
    stats = {"pages_crawled": 0, "articles_seen": 0, "articles_with_instagram": 0,
              "candidates_checked": 0, "candidates_accepted": 0, "candidates_rejected": 0,
              "candidates_dedup_skipped": 0, "start_time": time.time()}
    next_candidate_n = _next_candidate_n()

    for archive in _ARCHIVES:
        print(f"\n=== Archive: {archive['name']} ===", file=sys.stderr)
        for page in range(1, _MAX_PAGES_PER_ARCHIVE + 1):
            url = archive["url_template"].format(page=page)
            articles = _crawl_archive_page(url)
            stats["pages_crawled"] += 1
            if not articles:
                print(f"  page {page}: empty, stopping this archive", file=sys.stderr)
                break
            print(f"  page {page}: {len(articles)} article(s)", file=sys.stderr)

            for article_url, title in articles:
                stats["articles_seen"] += 1
                if article_url in checked_articles:
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

                article_text = trafilatura.extract(article_html, include_comments=False, include_tables=False) or title

                for ig_url in instagram_urls:
                    if ig_url.rstrip("/") in existing_urls:
                        stats["candidates_dedup_skipped"] += 1
                        continue
                    existing_urls.add(ig_url.rstrip("/"))  # dedupe within this same run too

                    post_id = _post_id_from_url(ig_url)
                    caption, uploader, retrievable = _fetch_caption_and_uploader(post_id)
                    stats["candidates_checked"] += 1

                    cid = f"cand-mass-{next_candidate_n:04d}"
                    next_candidate_n += 1
                    c = Candidate(candidate_id=cid, factchecker=archive["factchecker"],
                                   factcheck_article=article_url, social_url=ig_url, media_url=ig_url,
                                   eligibility_status="DISCOVERED")
                    add_candidate(c)
                    update_status(cid, "ARTICLE_FOUND", note=f"Title: {title}")
                    update_status(cid, "SOCIAL_REFERENCE_FOUND",
                                   note="Recovered via automated mass-sourcing pipeline (research/benchmark_v2/mass_source_candidates.py).")

                    if not retrievable:
                        update_status(cid, "REJECTED", note="Not retrievable via yt-dlp.",
                                       rejection_reason="Media not retrievable (deleted/private/geo-restricted).")
                        stats["candidates_rejected"] += 1
                        print(f"    [{cid}] {ig_url} -> not retrievable", file=sys.stderr)
                        continue
                    update_status(cid, "MEDIA_RETRIEVABLE", note=f"uploader={uploader}, has_caption={bool(caption)}")

                    if not caption:
                        update_status(cid, "REJECTED", note="No caption available to judge.",
                                       rejection_reason="Retrievable but no caption text (e.g. multi-item carousel or blank caption) -- cannot verify whether this post's own content makes the claim.")
                        stats["candidates_rejected"] += 1
                        print(f"    [{cid}] {ig_url} -> retrievable, no caption", file=sys.stderr)
                        continue

                    judgment = await _judge(provider, article_text, caption)
                    if judgment is None:
                        update_status(cid, "REJECTED", note="Judge call failed.",
                                       rejection_reason="Local LLM judgment call failed after retries.")
                        stats["candidates_rejected"] += 1
                        continue

                    if judgment.is_own_post_the_misinformation and judgment.confidence >= 0.7:
                        update_status(
                            cid, "GROUND_TRUTH_VERIFIED",
                            note=f"llama3.2 judge (confidence={judgment.confidence:.2f}): {judgment.reasoning}",
                        )
                        candidates_all = None  # placeholder, fields set via direct update below
                        from research.benchmark_v2.candidate_tracker import _load_all, _save_all
                        all_c = _load_all()
                        for rec in all_c:
                            if rec["candidate_id"] == cid:
                                rec["ground_truth_claim"] = judgment.extracted_claim
                                rec["ground_truth_label"] = judgment.extracted_verdict_label
                                rec["claim_type"] = "provenance"
                                rec["language"] = "en"
                                rec["media_type"] = "photo" if caption and not uploader else "video"
                        _save_all(all_c)
                        update_status(cid, "ELIGIBLE",
                                       note="Auto-accepted by mass-sourcing pipeline; NOT yet human/manual-reviewed -- flagged for a follow-up spot-check pass before being treated as fully trusted.")
                        stats["candidates_accepted"] += 1
                        print(f"    [{cid}] {ig_url} -> ACCEPTED (confidence={judgment.confidence:.2f}): {judgment.extracted_claim[:80]}", file=sys.stderr)
                    else:
                        update_status(cid, "REJECTED", note=f"llama3.2 judge: {judgment.reasoning}",
                                       rejection_reason=f"Judged NOT the misinformation source (confidence={judgment.confidence:.2f}): {judgment.reasoning}")
                        stats["candidates_rejected"] += 1
                        print(f"    [{cid}] {ig_url} -> rejected (confidence={judgment.confidence:.2f})", file=sys.stderr)

                if stats["candidates_checked"] % 5 == 0 and stats["candidates_checked"] > 0:
                    _save_checked_articles(checked_articles)

            _save_checked_articles(checked_articles)

    stats["elapsed_seconds"] = time.time() - stats["start_time"]
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _RESULTS_DIR / f"mass_sourcing_run_{int(time.time())}.json"
    out_path.write_text(json.dumps(stats, indent=2))
    print(f"\n=== DONE ===", file=sys.stderr)
    print(json.dumps(stats, indent=2), file=sys.stderr)
    print(f"Wrote {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
