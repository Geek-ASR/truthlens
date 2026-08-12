"""Local video processing: audio extraction + keyframe sampling, via the
`ffmpeg` CLI (must be present on PATH — installed in the Docker image).
Kept as subprocess calls rather than a heavy Python video library to keep
the dependency footprint small."""
import subprocess
from pathlib import Path

from PIL import Image, ImageStat

from app.core.exceptions import ProviderError

FRAME_SAMPLE_INTERVAL_SECONDS = 2.0

# Fractions of the video's total duration to try as thumbnail candidates.
# The old behavior grabbed exactly one frame at a hardcoded t=0.5s, with no
# fallback — live testing turned up a case where that landed on an
# unflattering extreme close-up mid-gesture (docs/CURRENT_ARCHITECTURE.md).
# Sampling a spread across the video and scoring each candidate isn't real
# scene- or face-aware selection, but it materially cuts the odds of
# publishing the single worst frame in the clip.
_THUMBNAIL_CANDIDATE_FRACTIONS = (0.15, 0.3, 0.45, 0.6, 0.75)


def extract_audio(video_path: str, output_dir: str) -> str:
    audio_path = str(Path(output_dir) / "audio.mp3")
    _run_ffmpeg(["-i", video_path, "-vn", "-acodec", "libmp3lame", "-y", audio_path])
    return audio_path


def extract_thumbnail(video_path: str, output_dir: str) -> str:
    duration = _probe_duration_seconds(video_path)
    timestamps = [duration * f for f in _THUMBNAIL_CANDIDATE_FRACTIONS] if duration else [0.5]

    candidates: list[tuple[str, float]] = []
    for i, ts in enumerate(timestamps):
        frame_path = str(Path(output_dir) / f"thumbnail_candidate_{i}.jpg")
        try:
            _run_ffmpeg(["-ss", str(ts), "-i", video_path, "-frames:v", "1", "-y", frame_path])
        except ProviderError:
            continue
        if Path(frame_path).exists():
            candidates.append((frame_path, _frame_quality_score(frame_path)))

    if not candidates:
        # Every timed candidate failed (e.g. a very short clip where the
        # sampled fractions land past the last decodable frame) — fall
        # back to the original single-shot behavior rather than raising.
        frame_path = str(Path(output_dir) / "thumbnail.jpg")
        _run_ffmpeg(["-ss", "0.5", "-i", video_path, "-frames:v", "1", "-y", frame_path])
        return frame_path

    best_path, _ = max(candidates, key=lambda c: c[1])
    return best_path


def _probe_duration_seconds(video_path: str) -> float | None:
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", video_path,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return float(result.stdout.decode().strip())
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


def _frame_quality_score(frame_path: str) -> float:
    # Cheap, deterministic proxy for "this frame has real visual content"
    # rather than being blank, a solid color, or mid-transition: standard
    # deviation of grayscale pixel values. Not a substitute for actual
    # composition/face-aware scoring — just a floor against the worst
    # candidates in the sampled set.
    with Image.open(frame_path) as img:
        grayscale = img.convert("L")
        return ImageStat.Stat(grayscale).stddev[0]


def sample_frames(video_path: str, output_dir: str, interval: float = FRAME_SAMPLE_INTERVAL_SECONDS) -> list[str]:
    pattern = str(Path(output_dir) / "frame_%04d.jpg")
    _run_ffmpeg(["-i", video_path, "-vf", f"fps=1/{interval}", "-y", pattern])
    return sorted(str(p) for p in Path(output_dir).glob("frame_*.jpg"))


def _run_ffmpeg(args: list[str]) -> None:
    try:
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", *args],
            check=True,
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise ProviderError("ffmpeg is not installed / not on PATH.") from exc
    except subprocess.CalledProcessError as exc:
        raise ProviderError(f"ffmpeg failed: {exc.stderr.decode(errors='ignore')}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProviderError("ffmpeg timed out processing video.") from exc
