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
from dataclasses import dataclass
from pathlib import Path

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


def fetch_from_url(url: str, output_dir: str) -> UrlFetchResult:
    """Downloads video + thumbnail and extracts whatever metadata the
    extractor for this site provides. Never invents a field it can't
    confirm — every value here is either directly reported by yt-dlp's
    extractor or left None (consistent with docs/FACT_CHECK_METHODOLOGY.md's
    "no invented facts" standard applying to reel metadata too, not just
    evidence)."""
    require_public_http_url(url)
    info = _download_with_retry(url, output_dir)

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
