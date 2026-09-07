"""All-platform mass-sourcing pipeline (authorized 2026-09-07).

Supersedes the Instagram-only constraint the five earlier `mass_source_*`
pipelines enforced. Those crawled the same six Indian fact-checker
archives to completion and yielded ~4 promotable items from ~3,600
Instagram candidates -- a blended ~1/900, traced structurally to the
fact that this misinformation pattern (real footage + false caption)
is attached and spread on X/Twitter far more than Instagram
(research/MASS_SOURCING_V2.md, feedback_truthlens_benchmark_priority).

The benchmark target was raised to n=200; that is only reachable by
dropping the platform filter. This pipeline keeps every OTHER bar the
earlier ones held:
  - a real professional fact-check article establishing the claim + verdict
  - the social post must still be live and retrievable (yt-dlp --simulate)
  - the post's OWN text must itself assert the false claim (local llama3.2
    judge), not merely be cited as evidence / the true original
  - the fact-checker's own account is skipped deterministically

What changed vs. mass_source_candidates.py:
  - extract_social_urls(): Instagram + X/Twitter + Facebook + YouTube +
    TikTok, both embed-widget and plain-link forms
  - yt-dlp is given the post's real URL directly (it handles all five
    platforms natively) instead of a reconstructed instagram.com/p/ URL
  - the judge prompt says "social media post", not "Instagram post"
  - its own candidate store (candidates_v3_allplatform.jsonl) + state
    files, so the frozen Instagram-only records are untouched
  - four archives run as independent processes via `--archive`; verify+
    judge within an archive run concurrently (Semaphore)

Run one archive:
  cd backend && ./.venv/bin/python -m research.benchmark_v2.mass_source_allplatform --archive altnews
Smoke test / measurement:
  ... --archive altnews --limit-articles 60 --stats-only
"""
import argparse
import asyncio
import fcntl
import json
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import trafilatura
from pydantic import BaseModel, Field, field_validator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from app.services.ai.ollama_provider import OllamaProvider  # noqa: E402
from research.benchmark_v2.mass_source_candidates import _is_known_factchecker_account  # noqa: E402

_YT_DLP_BIN = str(Path(sys.prefix) / "bin" / "yt-dlp")
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATASET_DIR = _REPO_ROOT / "research" / "dataset"
_RESULTS_DIR = _REPO_ROOT / "research" / "results"
_STATE_DIR = _DATASET_DIR / "allplatform_state"

# Per-archive candidate file, set in main() from --archive. Each archive
# process writes only its own file -- no cross-process lock contention
# (the first launch collapsed all archives onto one shared, O(n)-rewrite,
# lock-serialized file and ground to ~17 candidates/min). Records are
# APPEND-ONLY: each candidate is built fully in memory and written with a
# single locked append at its terminal state, not read-modify-written
# once per status transition.
_CANDIDATES_PATH: Path = _DATASET_DIR / "candidates_v3_allplatform.jsonl"
_LOCK_PATH: Path = _DATASET_DIR / ".candidates_v3_allplatform.lock"


def _set_archive_paths(archive: str) -> None:
    global _CANDIDATES_PATH, _LOCK_PATH
    _CANDIDATES_PATH = _DATASET_DIR / f"candidates_v3_{archive}.jsonl"
    _LOCK_PATH = _DATASET_DIR / f".candidates_v3_{archive}.lock"

_MODEL = "llama3.2"  # local only, never Gemini for sourcing (standing rule)
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_VERIFY_JUDGE_CONCURRENCY = 6
_YT_DLP_TIMEOUT = 18  # unretrievable media (30-40% of candidates on some archives)
                     # almost never becomes retrievable with more time -- a long
                     # timeout here was the single biggest throughput sink.

# Handles that are, by definition, never the originating misinformation
# spreader: official government/platform fact-check accounts and the
# fact-check orgs' own channels. Skipped before the judge call (saves a
# yt-dlp+LLM round-trip and removes a real source of judge confusion --
# the smoke test burned calls on PIBFactCheck, AltNewsVideos, etc.).
# Deliberately NOT including news wires (PTI/ANI/etc.) or individual
# debunkers -- those occasionally DO carry a claim that gets
# fact-checked, so the judge should still see them.
_NEVER_THE_SOURCE_HANDLES = {
    "pibfactcheck", "pib_india", "pibindia", "mygovindia",
    "altnewsvideos", "altnews", "boomlive", "boomlive_in", "vishvasnews",
    "factlyindia", "newschecker", "thequint", "webqoof",
    "factcrescendo", "afpfactcheck", "prfchecker",
    # US / international fact-checkers (added with the non-Indian archives)
    "politifact", "snopes", "snopescom", "leadstories", "leadstoriescom",
    "factcheckdotorg", "factcheck_org", "checkyourfact", "fullfact",
    "reutersfacts", "reuters", "apnews", "apfactcheck", "usatoday",
    "washingtonpost", "cnn", "leadstoriesfeed", "misbar", "logically",
}


# --------------------------------------------------------------------------
# Social-URL extraction (all platforms, embed-widget + plain link)
# --------------------------------------------------------------------------

_INSTAGRAM_PLAIN = re.compile(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(?:p|reel|tv)/[A-Za-z0-9_-]+")
_INSTAGRAM_PERMALINK = re.compile(r'data-instgrm-permalink="([^"]+)"')

_TWITTER_PLAIN = re.compile(r"(?:twitter|x)\.com/[A-Za-z0-9_]{1,15}/status/[0-9]+")

_YOUTUBE_WATCH = re.compile(r"youtube\.com/watch\?[^\s\"'<>]*v=([A-Za-z0-9_-]{11})")
_YOUTUBE_SHORT = re.compile(r"youtu\.be/([A-Za-z0-9_-]{11})")
_YOUTUBE_SHORTS = re.compile(r"youtube\.com/shorts/([A-Za-z0-9_-]{11})")
_YOUTUBE_EMBED = re.compile(r"youtube(?:-nocookie)?\.com/embed/([A-Za-z0-9_-]{11})")

_FACEBOOK_PLAIN = re.compile(
    r"facebook\.com/(?:"
    r"[A-Za-z0-9_.-]+/(?:videos|posts)/[0-9]+"
    r"|watch/?\?v=[0-9]+"
    r"|reel/[0-9]+"
    r"|permalink\.php\?story_fbid=[0-9]+&id=[0-9]+"
    r")"
)
_FBWATCH = re.compile(r"fb\.watch/[A-Za-z0-9_-]+")
_FB_DATA_HREF = re.compile(r'data-href="(https?://(?:www\.)?facebook\.com/[^"]+)"')

_TIKTOK_PLAIN = re.compile(r"tiktok\.com/@[A-Za-z0-9_.]+/video/[0-9]+")
_TIKTOK_SHORT = re.compile(r"(?:vm|vt)\.tiktok\.com/[A-Za-z0-9]+")
_TIKTOK_EMBED = re.compile(r'<blockquote[^>]+class="tiktok-embed"[^>]+cite="([^"]+)"')

# Amp/junk query params to strip when canonicalizing for dedup.
_TRACKING_PARAMS = re.compile(r"[?&](utm_[^=&]+|igshid|igsh|fbclid|si|feature|app|s|t|__tn__|__cft__\[[0-9]+\])=[^&]*")


def extract_social_urls(html: str) -> list[tuple[str, str]]:
    """Return deduplicated (canonical_url, platform) pairs found in raw
    article HTML. platform in {instagram, x, youtube, facebook, tiktok}.
    A strict superset of extract_instagram_embed.extract_instagram_urls:
    same Instagram coverage (widget permalink + plain link) plus the
    other four platforms."""
    found: dict[str, str] = {}  # canonical_url -> platform

    def add(raw: str, platform: str) -> None:
        raw = raw.strip().strip("\"'<>)")
        if not raw.startswith("http"):
            raw = "https://" + raw.lstrip("/")
        canon = _canonical_url(raw, platform)
        if canon:
            found.setdefault(canon, platform)

    for m in _INSTAGRAM_PERMALINK.finditer(html):
        inner = _INSTAGRAM_PLAIN.search(m.group(1))
        if inner:
            add(inner.group(0), "instagram")
    for m in _INSTAGRAM_PLAIN.finditer(html):
        add(m.group(0), "instagram")

    for m in _TWITTER_PLAIN.finditer(html):
        add(m.group(0), "x")

    for rx in (_YOUTUBE_WATCH, _YOUTUBE_SHORT, _YOUTUBE_SHORTS, _YOUTUBE_EMBED):
        for m in rx.finditer(html):
            add(f"youtube.com/watch?v={m.group(1)}", "youtube")

    for m in _FACEBOOK_PLAIN.finditer(html):
        add(m.group(0), "facebook")
    for m in _FBWATCH.finditer(html):
        add(m.group(0), "facebook")
    for m in _FB_DATA_HREF.finditer(html):
        if _FACEBOOK_PLAIN.search(m.group(1)) or _FBWATCH.search(m.group(1)):
            add(m.group(1), "facebook")

    for m in _TIKTOK_PLAIN.finditer(html):
        add(m.group(0), "tiktok")
    for m in _TIKTOK_SHORT.finditer(html):
        add(m.group(0), "tiktok")
    for m in _TIKTOK_EMBED.finditer(html):
        if _TIKTOK_PLAIN.search(m.group(1)):
            add(_TIKTOK_PLAIN.search(m.group(1)).group(0), "tiktok")

    return sorted(found.items())


def _canonical_url(url: str, platform: str) -> str | None:
    """Platform-aware canonical form used for dedup and as the stored
    social_url. Returns None if the URL doesn't actually contain a
    resolvable post id for its platform."""
    url = url.split("#")[0]
    if platform == "instagram":
        m = re.search(r"instagram\.com/(?:[A-Za-z0-9_.]+/)?(p|reel|tv)/([A-Za-z0-9_-]+)", url)
        return f"https://www.instagram.com/{m.group(1)}/{m.group(2)}/" if m else None
    if platform == "x":
        m = re.search(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})/status/([0-9]+)", url)
        return f"https://twitter.com/{m.group(1)}/status/{m.group(2)}" if m else None
    if platform == "youtube":
        m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url) or re.search(r"(?:youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})", url)
        return f"https://www.youtube.com/watch?v={m.group(1)}" if m else None
    if platform == "facebook":
        if "fb.watch/" in url:
            m = re.search(r"fb\.watch/([A-Za-z0-9_-]+)", url)
            return f"https://fb.watch/{m.group(1)}" if m else None
        u = re.sub(r"^https?://(www\.|m\.|web\.|d\.)?facebook\.com", "https://www.facebook.com", url)
        keep_query = "story_fbid=" in u or "watch/?v=" in u or "watch?v=" in u
        u = u if keep_query else u.split("?")[0]
        u = _TRACKING_PARAMS.sub("", u)
        return u.rstrip("/").rstrip("?")
    if platform == "tiktok":
        m = re.search(r"tiktok\.com/@([A-Za-z0-9_.]+)/video/([0-9]+)", url)
        if m:
            return f"https://www.tiktok.com/@{m.group(1)}/video/{m.group(2)}"
        return url.rstrip("/") if re.search(r"(?:vm|vt)\.tiktok\.com/", url) else None
    return None


# --------------------------------------------------------------------------
# Judge (local llama3.2) -- generalized from mass_source_candidates.py
# --------------------------------------------------------------------------

class SocialSourceJudgment(BaseModel):
    is_own_post_the_misinformation: bool = Field(
        description="True ONLY if THIS social media post's own caption/text itself asserts the "
        "false claim the article is debunking -- not merely referenced as evidence, comparison, "
        "context, or the true original."
    )
    extracted_claim: str = Field(description="The specific false claim being fact-checked, in one sentence.")
    extracted_verdict_label: str = Field(
        description="One of: FALSE, MOSTLY_FALSE, MISLEADING, MISSING_CONTEXT, TRUE, MOSTLY_TRUE, UNVERIFIED, OUTDATED"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence the post IS the misinformation source.")
    reasoning: str = Field(description="One or two sentences citing specific text from the caption or article.")

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v):
        try:
            return max(0.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


_JUDGE_SYSTEM_PROMPT = """You are helping build a fact-checking research benchmark. You will be given \
the full text of a professional fact-check article, and the actual caption/text of a specific \
social media post (Instagram, X/Twitter, Facebook, YouTube, or TikTok) that the article references.

Your ONLY job: decide whether THIS post's own caption/text is itself the misinformation being \
debunked -- i.e. does the post's own text assert the false claim? Many fact-check articles cite a \
post as evidence of the TRUE, accurate original event, while the actual false claim was posted \
separately by a different account. In that common case, is_own_post_the_misinformation must be \
False, even though the post is clearly relevant to the story.

Only set is_own_post_the_misinformation=True when the caption/text itself makes the specific false \
assertion the article is fact-checking -- not when the post merely shows related real footage, is \
tagged/mentioned, or is cited as a comparison or rebuttal.

The article and/or the post caption may be in Hindi, Tamil, Marathi, Malayalam, Bengali, or another \
language, not just English. Judge on MEANING, not language: a Hindi caption that asserts the false \
claim counts exactly the same as an English one. If the caption is in a script/language you cannot \
read well enough to be sure it makes the claim, set is_own_post_the_misinformation=False and say so \
in reasoning -- do not guess."""


_LABEL_CANON = {"FALSE", "MOSTLY_FALSE", "MISLEADING", "MISSING_CONTEXT",
                "TRUE", "MOSTLY_TRUE", "UNVERIFIED", "OUTDATED"}
_LABEL_SYNONYMS = {
    "FAKE": "FALSE", "INCORRECT": "FALSE", "PARTLY_FALSE": "MOSTLY_FALSE",
    "PARTIALLY_FALSE": "MOSTLY_FALSE", "HALF_TRUE": "MISLEADING", "PARTLY_TRUE": "MISLEADING",
    "MISSING": "MISSING_CONTEXT", "NEEDS_CONTEXT": "MISSING_CONTEXT", "DISTORTED": "MISLEADING",
    "CORRECT": "TRUE", "MOSTLY_ACCURATE": "MOSTLY_TRUE", "UNPROVEN": "UNVERIFIED",
    "UNSUBSTANTIATED": "UNVERIFIED", "UNPROVED": "UNVERIFIED", "SATIRE": "MISLEADING",
}


def normalize_label(raw: str | None) -> str:
    """llama3.2 emits 'False', 'FALSE_CLAIM: ...', 'Fake' etc. -- collapse
    to the 8 canonical labels. Returns 'UNVERIFIED' only when nothing
    recognizable is present (rare); the spot-check still flags that."""
    if not raw:
        return "UNVERIFIED"
    t = raw.strip().upper().replace("-", "_").replace(" ", "_")
    t = t.split(":")[0].split("_CLAIM")[0].strip("_")
    if t in _LABEL_CANON:
        return t
    if t in _LABEL_SYNONYMS:
        return _LABEL_SYNONYMS[t]
    for canon in ("MOSTLY_FALSE", "MOSTLY_TRUE", "MISSING_CONTEXT", "FALSE", "MISLEADING",
                  "TRUE", "OUTDATED", "UNVERIFIED"):
        if canon in t:
            return canon
    return "UNVERIFIED"


async def _judge(provider: OllamaProvider, article_text: str, caption: str, platform: str) -> SocialSourceJudgment | None:
    user_content = (
        f"FACT-CHECK ARTICLE TEXT:\n{article_text[:6000]}\n\n"
        f"{platform.upper()} POST'S OWN CAPTION/TEXT:\n{caption[:2000]}"
    )
    try:
        result = await provider.structured_call(
            model=_MODEL, system_prompt=_JUDGE_SYSTEM_PROMPT, user_content=user_content,
            output_schema=SocialSourceJudgment, prompt_version="mass_sourcing_allplatform_judge.v1",
            stage="mass_sourcing_allplatform", max_tokens=512,
        )
        judgment = result.parsed
        if judgment.is_own_post_the_misinformation and not judgment.reasoning.strip():
            retry_result = await provider.structured_call(
                model=_MODEL, system_prompt=_JUDGE_SYSTEM_PROMPT, user_content=user_content,
                output_schema=SocialSourceJudgment, prompt_version="mass_sourcing_allplatform_judge.v1",
                stage="mass_sourcing_allplatform", max_tokens=512,
            )
            if retry_result.parsed.reasoning.strip():
                judgment = retry_result.parsed
        return judgment
    except Exception as exc:  # noqa: BLE001 -- one bad judge call must not kill the run
        print(f"    judge call failed: {exc}", file=sys.stderr)
        return None


# --------------------------------------------------------------------------
# Media verification (platform-agnostic: real URL straight to yt-dlp)
# --------------------------------------------------------------------------

async def _verify_media(url: str) -> tuple[str | None, str | None, bool, bool]:
    """(caption, uploader, retrievable, is_video). Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            _YT_DLP_BIN, "--simulate", "--no-warnings", "--no-playlist",
            "-R", "1", "--socket-timeout", "8",
            "--extractor-args", "twitter:api=syndication",
            "--print", "%(description)s|||F|||%(uploader)s|||F|||%(uploader_id)s|||F|||%(vcodec)s",
            url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=_YT_DLP_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return None, None, False, False
    except (FileNotFoundError, OSError):
        return None, None, False, False

    out, err = out_b.decode("utf-8", "replace").strip(), err_b.decode("utf-8", "replace")
    benign = ("No video formats found" in err or "no video in this post" in err.lower()
              or "There are no video" in err)
    if proc.returncode != 0 and not benign:
        return None, None, False, False
    parts = out.split("|||F|||")
    caption = (parts[0].strip() if parts and parts[0].strip() not in ("", "NA", "None") else None)
    uploader = (parts[2].strip() if len(parts) > 2 and parts[2].strip() not in ("", "NA", "None") else None)
    if uploader is None and len(parts) > 4 and parts[4].strip() not in ("", "NA", "None"):
        uploader = parts[4].strip()
    vcodec = parts[5].strip().lower() if len(parts) > 5 else ""
    is_video = vcodec not in ("", "none", "na")
    return caption, uploader, True, is_video


# --------------------------------------------------------------------------
# Candidate store -- APPEND-ONLY, one write per candidate, per-archive file.
# --------------------------------------------------------------------------

def _new_rec(cid: str, factchecker: str, article: str, url: str, platform: str) -> dict:
    return {
        "candidate_id": cid, "factchecker": factchecker, "factcheck_article": article,
        "social_url": url, "media_url": url, "platform": platform,
        "media_type": None, "ground_truth_claim": None, "ground_truth_label": None,
        "claim_type": "provenance", "language": "en",
        "eligibility_status": "DISCOVERED", "rejection_reason": None, "judge_confidence": None,
        "history": [{"status": "DISCOVERED", "at": _now(), "note": "created"}],
    }


def _step(rec: dict, status: str, note: str = "", *, rejection_reason: str | None = None, **fields) -> None:
    """Advance an in-memory record. No disk I/O -- _flush writes it once."""
    rec["eligibility_status"] = status
    if rejection_reason is not None:
        rec["rejection_reason"] = rejection_reason
    rec.update(fields)
    rec["history"].append({"status": status, "at": _now(), "note": note})


def _flush(rec: dict) -> None:
    """Single locked append of the finished record."""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            with open(_CANDIDATES_PATH, "a") as f:
                f.write(json.dumps(rec) + "\n")
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _load_all() -> list[dict]:
    if not _CANDIDATES_PATH.exists():
        return []
    with open(_CANDIDATES_PATH) as f:
        return [json.loads(line) for line in f if line.strip()]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _known_social_urls() -> set[str]:
    """Every social URL already in the benchmark, in any earlier candidate
    file, or in this pipeline's own file -- so a broadened run never
    re-checks or double-counts one."""
    urls: set[str] = set()
    for fn in ("items.jsonl", "items_v2.jsonl"):
        p = _DATASET_DIR / fn
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip():
                    d = json.loads(line)
                    u = d.get("original_url") or d.get("source_url")
                    if u:
                        urls.add(u.rstrip("/"))
    for p in _DATASET_DIR.glob("candidates*.jsonl"):
        for line in p.read_text().splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for k in ("social_url", "media_url"):
                    if d.get(k):
                        urls.add(d[k].rstrip("/"))
    return urls


# --------------------------------------------------------------------------
# Archive crawlers -- yield (article_url, factchecker), logic lifted from
# the five proven mass_source_* scripts (same archives, same quirks).
# --------------------------------------------------------------------------

@retry(reraise=True, stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15),
       retry=retry_if_exception_type(httpx.HTTPError))
def _get(url: str, timeout: float = 25) -> str:
    with httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as c:
        r = c.get(url)
        r.raise_for_status()
        return r.text


def _locs(xml: str) -> list[str]:
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def crawl_altnews():
    for page in range(1, 520):
        try:
            html = _get(f"https://www.altnews.in/type/fact-check/page/{page}/")
        except httpx.HTTPError:
            continue
        links = re.findall(r'href="(https://www\.altnews\.in/[a-z0-9][a-z0-9/-]+/?)"', html)
        real = []
        for u in dict.fromkeys(links):
            if any(s in u for s in ("/author/", "/hindi/", "/type/", "/page/", "/fact_checks_claim_type/")):
                continue
            slug = u.rstrip("/").split("/")[-1]
            if slug in ("fact-check", "donate", "about-us", "contact-us", "team", "editorial-policy"):
                continue
            real.append(u)
        if not real:
            return
        for u in real:
            yield u, "altnews.in"


def crawl_vishvas():
    try:
        idx = _get("https://www.vishvasnews.com/sitemap_index.xml")
    except httpx.HTTPError:
        return
    for sm in _locs(idx)[:40]:
        try:
            body = _get(sm)
        except httpx.HTTPError:
            continue
        for u in _locs(body):
            if "/viral/" in u or "fact-check" in u.lower():
                yield u, "vishvasnews.com"


def crawl_thequint():
    today = date.today()
    for i in range(0, 2300):
        day = (today - timedelta(days=i)).isoformat()
        try:
            body = _get(f"https://www.thequint.com/sitemap/sitemap-daily-{day}.xml")
        except httpx.HTTPError:
            continue
        for u in _locs(body):
            if "/webqoof/" in u:
                yield u, "thequint.com"


def crawl_factcrescendo():
    subs = [("english", "en"), ("tamil", "ta"), ("marathi", "mr"), ("malayalam", "ml"),
            ("hindi", "hi"), ("bangla", "bn")]
    for sub, _lang in subs:
        try:
            idx = _get(f"https://{sub}.factcrescendo.com/sitemap_index.xml")
        except httpx.HTTPError:
            continue
        pref = f"https://{sub}.factcrescendo.com/post-sitemap"
        for sm in [u for u in _locs(idx) if u.startswith(pref)]:
            try:
                body = _get(sm)
            except httpx.HTTPError:
                continue
            for u in _locs(body):
                if "/20" in u and u.rstrip("/").split("/")[-1]:
                    yield u, "factcrescendo.com"


def crawl_factly():
    try:
        idx = _get("https://factly.in/sitemap_index.xml")
    except httpx.HTTPError:
        return
    for sm in _locs(idx):
        if "post-sitemap" not in sm:
            continue
        try:
            body = _get(sm)
        except httpx.HTTPError:
            continue
        for u in _locs(body):
            if "fact-check" in u.lower() or "/fact-" in u.lower():
                yield u, "factly.in"


# --- Non-Indian English fact-checkers (authorized 2026-09-07, "Both A and B").
# Broadens the benchmark from Indian-only to political misinformation generally
# -- the paper's framing/dataset card need a matching rewrite once these land.
# NOT included: snopes.com (robots.txt explicitly Disallow: / for ClaudeBot --
# same publisher-directive call as newschecker.in in MASS_SOURCING_V2.md);
# factcheck.afp.com (hard 403 on any non-allowlisted UA).

def crawl_leadstories():
    """leadstories.com/sitemap.txt -- flat URL list, ~10k /hoax-alert/ posts
    (US viral social misinformation, heavily Facebook/X). Follows
    sitemap-N.txt continuations if present."""
    n = 0
    while True:
        sm_url = "https://leadstories.com/sitemap.txt" if n == 0 else f"https://leadstories.com/sitemap-{n}.txt"
        try:
            body = _get(sm_url)
        except httpx.HTTPError:
            return
        lines = [ln.strip() for ln in body.splitlines() if ln.strip().startswith("http")]
        if not lines:
            return
        # sitemap.txt is oldest-first; 2020-2021 hoax posts are almost all
        # deleted now. Walk it newest-first so live, retrievable posts
        # (far higher yield) come first.
        for u in reversed(lines):
            if "/hoax-alert/" in u and u.endswith(".html"):
                yield u, "leadstories.com"
        n += 1
        if n > 20:
            return


def crawl_politifact():
    """politifact.com/factchecks/list/?page=N -- 20 links/page,
    /factchecks/YYYY/mon/DD/slug/. Stops when a page adds no new URLs
    (its pagination silently repeats page 1 past the real end)."""
    seen: set[str] = set()
    for page in range(1, 1200):
        try:
            html = _get(f"https://www.politifact.com/factchecks/list/?page={page}")
        except httpx.HTTPError:
            continue
        links = set(re.findall(r'/factchecks/20[0-9]{2}/[a-z]{3}/[0-9]{1,2}/[a-z0-9-]+/', html))
        fresh = links - seen
        if not fresh:
            return
        seen |= fresh
        for path in sorted(fresh):
            yield f"https://www.politifact.com{path}", "politifact.com"


def crawl_checkyourfact():
    """checkyourfact.com/page/N/ -- articles are hosted on dailycaller.com
    (/YYYY/MM/DD/fact-check-slug). Stops when a page adds nothing new."""
    seen: set[str] = set()
    for page in range(1, 800):
        try:
            html = _get(f"https://checkyourfact.com/page/{page}/")
        except httpx.HTTPError:
            continue
        links = set(re.findall(r'https://dailycaller\.com/20[0-9]{2}/[0-9]{2}/[0-9]{2}/fact-check-[a-z0-9-]+', html))
        fresh = links - seen
        if not fresh:
            return
        seen |= fresh
        for u in sorted(fresh):
            yield u, "checkyourfact.com"


def crawl_fullfact():
    """fullfact.org/sitemap.xml -- individual fact-checks live under topic
    paths and end '-fact-checked/' or are under /online/ /health/ /economy/
    /europe/ /crime/ etc. Filter to the article-shaped ones."""
    try:
        body = _get("https://fullfact.org/sitemap.xml")
    except httpx.HTTPError:
        return
    for u in _locs(body):
        low = u.lower()
        if u.rstrip("/").count("/") >= 4 and (
            low.endswith("-fact-checked/") or "/online/" in low or "/health/" in low
            or "/economy/" in low or "/europe/" in low or "/crime/" in low or "/law/" in low
        ):
            yield u, "fullfact.org"


_ARCHIVES = {
    "altnews": crawl_altnews,
    "vishvas": crawl_vishvas,
    "thequint": crawl_thequint,
    "factcrescendo": crawl_factcrescendo,
    "leadstories": crawl_leadstories,
    "politifact": crawl_politifact,
    "checkyourfact": crawl_checkyourfact,
    "fullfact": crawl_fullfact,
    "factly": crawl_factly,
}


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def _state_path(archive: str) -> Path:
    return _STATE_DIR / f"{archive}_checked.json"


def _load_checked(archive: str) -> set[str]:
    p = _state_path(archive)
    return set(json.loads(p.read_text())) if p.exists() else set()


def _save_checked(archive: str, checked: set[str]) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_path(archive).write_text(json.dumps(sorted(checked)))


def _next_n(prefix: str) -> int:
    n = 0
    for r in _load_all():
        cid = r.get("candidate_id", "")
        if cid.startswith(prefix):
            try:
                n = max(n, int(cid.rsplit("-", 1)[-1]))
            except ValueError:
                pass
    return n + 1


async def _process_candidate(provider, cid, factchecker, article_url, article_text, url, platform, stats):
    rec = _new_rec(cid, factchecker, article_url, url, platform)
    _step(rec, "SOCIAL_REFERENCE_FOUND", f"{platform} ref via mass_source_allplatform.py")

    caption, uploader, retrievable, is_video = await _verify_media(url)
    stats["checked"] += 1
    stats["by_platform"][platform] = stats["by_platform"].get(platform, 0) + 1

    if not retrievable:
        _step(rec, "REJECTED", "yt-dlp could not retrieve.",
              rejection_reason="Media not retrievable (deleted/private/geo/auth-walled).")
        stats["rej_unretrievable"] += 1
        _flush(rec)
        return
    _step(rec, "MEDIA_RETRIEVABLE", f"uploader={uploader} caption={bool(caption)} video={is_video}",
          media_type="video" if is_video else "photo")

    handle = (uploader or "").lower().lstrip("@").replace(" ", "")
    if _is_known_factchecker_account(uploader) or handle in _NEVER_THE_SOURCE_HANDLES:
        _step(rec, "REJECTED", f"Never-the-source account ({uploader}).",
              rejection_reason=f"Posted by {uploader}, an official fact-check / platform / fact-checker account -- "
                               f"documentation of the claim, not the originating misinformation spreader.")
        stats["rej_factchecker_acct"] += 1
        _flush(rec)
        return
    if not caption:
        _step(rec, "REJECTED", "No caption/text to judge.",
              rejection_reason="Retrievable but no caption/description text -- cannot verify the post itself makes the claim.")
        stats["rej_no_caption"] += 1
        _flush(rec)
        return

    judgment = await _judge(provider, article_text, caption, platform)
    if judgment is None:
        _step(rec, "REJECTED", "Judge failed.", rejection_reason="Local LLM judge call failed after retries.")
        stats["rej_judge_failed"] += 1
        _flush(rec)
        return

    if judgment.is_own_post_the_misinformation and judgment.confidence >= 0.7:
        _step(rec, "GROUND_TRUTH_VERIFIED", f"llama3.2 (conf={judgment.confidence:.2f}): {judgment.reasoning}",
              ground_truth_claim=judgment.extracted_claim,
              ground_truth_label=normalize_label(judgment.extracted_verdict_label),
              ground_truth_label_raw=judgment.extracted_verdict_label,
              judge_confidence=judgment.confidence)
        _step(rec, "ELIGIBLE", "Auto-accepted; NOT yet spot-checked. Pending spot_check + promote pass.")
        stats["eligible"] += 1
        print(f"    [{cid}] ELIGIBLE {platform} conf={judgment.confidence:.2f} :: {judgment.extracted_claim[:90]}",
              file=sys.stderr, flush=True)
    else:
        _step(rec, "REJECTED", f"llama3.2: {judgment.reasoning}",
              rejection_reason=f"Judged NOT the misinformation source (conf={judgment.confidence:.2f}): {judgment.reasoning}")
        stats["rej_not_source"] += 1
    _flush(rec)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True,
                    help="one archive, a comma-list (processed in order), or 'all'. "
                         f"choices: {', '.join(_ARCHIVES)}")
    ap.add_argument("--limit-articles", type=int, default=0, help="stop after N articles WITH a social ref (0 = no limit)")
    ap.add_argument("--target-eligible", type=int, default=0, help="stop once this many ELIGIBLE reached this run (0 = no limit)")
    ap.add_argument("--concurrency", type=int, default=_VERIFY_JUDGE_CONCURRENCY)
    ap.add_argument("--stats-only", action="store_true", help="don't write candidates, just measure the funnel")
    args = ap.parse_args()

    archives = list(_ARCHIVES) if args.archive == "all" else args.archive.split(",")
    bad = [a for a in archives if a not in _ARCHIVES]
    if bad:
        ap.error(f"unknown archive(s): {bad}; choices: {list(_ARCHIVES)}")
    provider = OllamaProvider()
    known = _known_social_urls()
    stats = {"archives": archives, "articles_seen": 0, "articles_with_social": 0, "checked": 0,
             "eligible": 0, "rej_unretrievable": 0, "rej_no_caption": 0, "rej_factchecker_acct": 0,
             "rej_judge_failed": 0, "rej_not_source": 0, "dedup_skipped": 0, "by_platform": {},
             "start": time.time()}
    sem = asyncio.Semaphore(args.concurrency)

    for archive in archives:
        _set_archive_paths(archive)
        prefix = f"cand-ap-{archive}-"
        n = _next_n(prefix)
        checked = _load_checked(archive)
        print(f"\n=== {archive} (resume: {len(checked)} articles checked, {n - 1} candidates on file) ===",
              file=sys.stderr, flush=True)

        for article_url, factchecker in _ARCHIVES[archive]():
            stats["articles_seen"] += 1
            if article_url in checked:
                continue
            checked.add(article_url)
            if len(checked) % 40 == 0:  # persist the frontier often -- a kill/restart
                _save_checked(archive, checked)  # otherwise re-crawls everything since the last save
                _dump_stats(stats)

            try:
                html = _get(article_url, timeout=20)
            except httpx.HTTPError:
                continue

            social = [(u, p) for (u, p) in extract_social_urls(html) if u.rstrip("/") not in known]
            skipped = len(extract_social_urls(html)) - len(social)
            stats["dedup_skipped"] += skipped
            if not social:
                continue
            stats["articles_with_social"] += 1

            article_text = trafilatura.extract(html, include_comments=False, include_tables=False) or article_url

            if args.stats_only:
                for u, p in social:
                    known.add(u.rstrip("/"))
                    stats["by_platform"][p] = stats["by_platform"].get(p, 0) + 1
                    stats["checked"] += 1
            else:
                tasks = []
                for u, p in social:
                    known.add(u.rstrip("/"))
                    cid = f"{prefix}{n:04d}"
                    n += 1

                    async def _guarded(cid=cid, u=u, p=p):
                        async with sem:
                            await _process_candidate(provider, cid, factchecker, article_url,
                                                     article_text, u, p, stats)
                    tasks.append(_guarded())
                await asyncio.gather(*tasks)

            if args.limit_articles and stats["articles_with_social"] >= args.limit_articles:
                print(f"  hit --limit-articles {args.limit_articles}", file=sys.stderr)
                break
            if args.target_eligible and stats["eligible"] >= args.target_eligible:
                print(f"  hit --target-eligible {args.target_eligible}", file=sys.stderr)
                break

        _save_checked(archive, checked)

    _dump_stats(stats, final=True)


def _dump_stats(stats: dict, final: bool = False) -> None:
    stats["elapsed_seconds"] = round(time.time() - stats["start"], 1)
    if stats["checked"]:
        stats["seconds_per_candidate"] = round(stats["elapsed_seconds"] / stats["checked"], 2)
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    tag = "_".join(stats["archives"])
    (_RESULTS_DIR / f"allplatform_{tag}_live.json").write_text(json.dumps(stats, indent=2))
    if final:
        print("\n=== DONE ===\n" + json.dumps(stats, indent=2), file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
