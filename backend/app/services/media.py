"""Local video processing: audio extraction + keyframe sampling, via the
`ffmpeg` CLI (must be present on PATH — installed in the Docker image).
Kept as subprocess calls rather than a heavy Python video library to keep
the dependency footprint small."""
import subprocess
from pathlib import Path

from app.core.exceptions import ProviderError

FRAME_SAMPLE_INTERVAL_SECONDS = 2.0


def extract_audio(video_path: str, output_dir: str) -> str:
    audio_path = str(Path(output_dir) / "audio.mp3")
    _run_ffmpeg(["-i", video_path, "-vn", "-acodec", "libmp3lame", "-y", audio_path])
    return audio_path


def extract_thumbnail(video_path: str, output_dir: str, at_seconds: float = 0.5) -> str:
    thumb_path = str(Path(output_dir) / "thumbnail.jpg")
    _run_ffmpeg(["-ss", str(at_seconds), "-i", video_path, "-frames:v", "1", "-y", thumb_path])
    return thumb_path


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
