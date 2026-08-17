"""Optional URL-based media fetch, using yt-dlp (docs/ARCHITECTURE.md §2a).

This is an explicit, operator-opted-in alternative to manual upload. For
Instagram specifically, yt-dlp works by talking to Instagram's private
web endpoints rather than an official API — this is outside Instagram's
Terms of Service and carries real risk (rate limiting, IP/account
flags) to the account you use it from. It is OFF by default
(`ReelCreate.auto_fetch=False`) and was enabled at the operator's
explicit request after being told about that risk; see
docs/ARCHITECTURE.md §2a and docs/SECURITY.md §8 before turning it on
for a real Instagram publishing account.

yt-dlp supports hundreds of sites (YouTube, X/Twitter, TikTok, and most
public web video embeds) with no ToS conflict for the vast majority of
them — Instagram is the one platform where this module's use crosses a
line this project otherwise avoids everywhere else in the codebase.
"""
import html
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
import yt_dlp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.exceptions import ProviderError
from app.core.url_safety import require_public_http_url

# Instagram's CDN intermittently returns an empty media response under
# rate-limiting even for fully public, accessible posts — observed live
# during regression testing (docs/CURRENT_ARCHITECTURE.md): a post that
# failed on the first attempt succeeded immediately on retry with no
# other change. This is a transient-download problem, not an
# access-denied problem, so it's worth a few quick retries before
# surfacing ProviderError to the caller.
_RETRYABLE_MESSAGES = ("empty media response", "timed out", "connection reset", "temporary failure")

# yt-dlp's Instagram extractor reports "this post has no video" in more
# than one distinct phrasing depending on which internal code path
# detects it -- found live (research/dataset item-0005, a real photo
# post): yt-dlp raised "No video formats found!" for this post, which
# "no video in this post" alone never matched, so the photo-post
# fallback below never triggered and a genuine, fetchable photo post
# failed ingestion outright instead of falling back to Open Graph tags.
# A tuple of markers, same pattern as _RETRYABLE_MESSAGES above, rather
# than a single fixed string.
_NO_VIDEO_MESSAGES = ("no video in this post", "no video formats found")

# Same identifiable, honest bot UA used for search-result fetching
# (app/services/search/duckduckgo.py) — confirmed live that Instagram
# actually serves richer Open Graph tags to a declared bot UA than to a
# spoofed-browser one (it appears to special-case known crawler UAs for
# link-preview purposes, the same mechanism Slack/Facebook link previews
# rely on), so this isn't just consistency for its own sake.
_USER_AGENT = "Mozilla/5.0 (compatible; TruthLensBot/1.0; +automated fact-checking research)"
_OG_FETCH_TIMEOUT = 15

_IMAGE_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}

# Instagram's og:description format, e.g. "13K likes, 222 comments -
# thenewindia2 on August 5, 2026: "caption text"." — likes/comments are
# omitted for some posts (private-adjacent engagement counts), so both
# are optional groups. Best-effort only: if this doesn't match, the raw
# og:description is used as caption_text with no structured fields
# rather than guessing.
_OG_DESCRIPTION_PATTERN = re.compile(
    r"^(?:([\d.,]+[KMB]?) likes?, )?(?:([\d.,]+[KMB]?) comments? - )?"
    r"([A-Za-z0-9_.]+) on ([A-Za-z]+ \d{1,2}, \d{4}): (.*)$"
)


@dataclass
class UrlFetchResult:
    video_path: str | None
    thumbnail_path: str | None
    caption_text: str | None
    creator_handle: str | None
    posted_at: str | None  # ISO date string, best-effort
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    hashtags: list[str]
    # Set only for posts with no video stream at all (a photo or photo
    # -carousel post) — see _fetch_photo_via_og_tags. None for every
    # video fetch, unchanged from before photo support existed.
    photo_path: str | None = None


def fetch_from_url(url: str, output_dir: str) -> UrlFetchResult:
    """Downloads video + thumbnail and extracts whatever metadata the
    extractor for this site provides. Never invents a field it can't
    confirm — every value here is either directly reported by yt-dlp's
    extractor or left None (consistent with docs/FACT_CHECK_METHODOLOGY.md's
    "no invented facts" standard applying to reel metadata too, not just
    evidence).

    Falls back to a photo-post fetch (Open Graph meta tags, not yt-dlp)
    when the extractor reports there's no video in the post at all --
    yt-dlp's Instagram extractor refuses outright rather than returning
    partial data for image posts."""
    require_public_http_url(url)
    try:
        info = _download_with_retry(url, output_dir)
    except ProviderError as exc:
        if any(marker in str(exc).lower() for marker in _NO_VIDEO_MESSAGES):
            return _fetch_photo_via_og_tags(url, output_dir)
        raise

    video_path = _find_downloaded_file(output_dir, exclude_suffixes=(".jpg", ".jpeg", ".png", ".webp"))
    thumbnail_path = _find_downloaded_file(output_dir, include_suffixes=(".jpg", ".jpeg", ".png", ".webp"))

    hashtags = info.get("tags") or []
    hashtags = [h for h in hashtags if isinstance(h, str)]

    upload_date = info.get("upload_date")  # yt-dlp format: YYYYMMDD
    posted_at = None
    if upload_date and len(upload_date) == 8:
        posted_at = f"{upload_date[0:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

    return UrlFetchResult(
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        caption_text=info.get("description"),
        creator_handle=info.get("uploader") or info.get("uploader_id"),
        posted_at=posted_at,
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
        comment_count=info.get("comment_count"),
        hashtags=hashtags,
    )


def _og_tag(html_text: str, prop: str) -> str | None:
    match = re.search(rf'<meta property="{re.escape(prop)}" content="([^"]*)"', html_text)
    return html.unescape(match.group(1)) if match else None


def _parse_count(raw: str) -> int | None:
    raw = raw.strip().replace(",", "")
    multiplier = 1
    if raw and raw[-1] in "KMB":
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[raw[-1]]
        raw = raw[:-1]
    try:
        return int(float(raw) * multiplier)
    except ValueError:
        return None


def _fetch_photo_via_og_tags(url: str, output_dir: str) -> UrlFetchResult:
    with httpx.Client(timeout=_OG_FETCH_TIMEOUT, follow_redirects=True, headers={"User-Agent": _USER_AGENT}) as client:
        try:
            page = client.get(url)
            page.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Could not fetch this post's page to look for a photo: {exc}") from exc

        image_url = _og_tag(page.text, "og:image")
        if not image_url:
            raise ProviderError(
                f"{url} has no video AND no photo Open Graph tag — it may be private, "
                f"deleted, or require login to view."
            )
        # This URL comes from the fetched page's own HTML (an og:image meta
        # tag), not from the operator-supplied url itself -- require_public_
        # http_url() above only validated that one. Without this second
        # check, a compromised/malicious operator account (this module's own
        # documented threat model) could point fetch_from_url() at a page
        # whose og:image tag names an internal address, and this code would
        # fetch and write it to disk with zero validation.
        require_public_http_url(image_url)

        try:
            image_resp = client.get(image_url)
            image_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Found a photo URL for this post but could not download it: {exc}") from exc

    content_type = image_resp.headers.get("content-type", "").split(";")[0].strip().lower()
    ext = _IMAGE_CONTENT_TYPE_EXT.get(content_type, "jpg")
    photo_path = str(Path(output_dir) / f"download.{ext}")
    Path(photo_path).write_bytes(image_resp.content)

    description = _og_tag(page.text, "og:description") or ""
    og_url = _og_tag(page.text, "og:url") or ""

    like_count = comment_count = None
    creator_handle = None
    posted_at = None
    caption_text = description or None

    match = _OG_DESCRIPTION_PATTERN.match(description)
    if match:
        likes_raw, comments_raw, handle, date_raw, caption_raw = match.groups()
        if likes_raw:
            like_count = _parse_count(likes_raw)
        if comments_raw:
            comment_count = _parse_count(comments_raw)
        creator_handle = handle
        try:
            from datetime import datetime

            posted_at = datetime.strptime(date_raw, "%B %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            posted_at = None
        # One combined strip call, not chained ones: str.strip(chars) removes
        # any of the given characters from each end repeatedly until a
        # non-matching one is hit, so a trailing '". ' (quote, period,
        # space) is fully peeled in one pass. Chaining .strip('"').rstrip(".")
        # separately would miss the quote when it sits behind a trailing
        # period rather than at the very end.
        caption_text = caption_raw.strip(' "“”.') or None

    if not creator_handle:
        # og:url is typically https://www.instagram.com/<handle>/p/<shortcode>/
        handle_match = re.search(r"instagram\.com/([A-Za-z0-9_.]+)/", og_url)
        if handle_match and handle_match.group(1) not in ("p", "reel", "tv"):
            creator_handle = handle_match.group(1)

    return UrlFetchResult(
        video_path=None,
        thumbnail_path=None,
        caption_text=caption_text,
        creator_handle=creator_handle,
        posted_at=posted_at,
        view_count=None,  # Open Graph tags don't expose view counts (photos have none anyway)
        like_count=like_count,
        comment_count=comment_count,
        hashtags=[],  # not reliably present in og:description; claim extraction still reads caption_text directly
        photo_path=photo_path,
    )


class _RetryableDownloadError(Exception):
    pass


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_RetryableDownloadError),
)
def _download_with_retry(url: str, output_dir: str) -> dict:
    outtmpl = str(Path(output_dir) / "download.%(ext)s")
    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "mp4/best",
        "writethumbnail": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(url, download=True)
    except yt_dlp.utils.DownloadError as exc:
        message = str(exc).lower()
        if any(marker in message for marker in _RETRYABLE_MESSAGES):
            raise _RetryableDownloadError(str(exc)) from exc
        raise ProviderError(
            f"Could not fetch media from {url}. The source site may require login, "
            f"have rate-limited this request, or yt-dlp's extractor for it may be "
            f"out of date. Underlying error: {exc}"
        ) from exc


def _find_downloaded_file(
    directory: str, *, include_suffixes: tuple[str, ...] = (), exclude_suffixes: tuple[str, ...] = ()
) -> str | None:
    for path in sorted(Path(directory).glob("download.*")):
        suffix = path.suffix.lower()
        if include_suffixes and suffix not in include_suffixes:
            continue
        if exclude_suffixes and suffix in exclude_suffixes:
            continue
        return str(path)
    return None
