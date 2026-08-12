"""Tests for extract_thumbnail's multi-candidate frame selection
(app/services/media.py). Uses real ffmpeg against small synthetic clips
built with the lavfi test sources — no network, no real video needed, and
it exercises the actual subprocess calls rather than mocking them."""
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from app.services.media import _frame_quality_score, extract_thumbnail


def _build_clip(path: str, *, blank_seconds: float, busy_seconds: float) -> None:
    """A clip that's flat black for the first `blank_seconds`, then a busy
    generated test pattern for `busy_seconds`. Candidate fractions land in
    both halves for a clip a few seconds long, so a working selector
    should always prefer a frame from the busy half."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c=black:s=320x240:d={blank_seconds}",
            "-f", "lavfi", "-i", f"testsrc=s=320x240:d={busy_seconds}",
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
            "-map", "[v]", "-y", path,
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


@pytest.fixture(autouse=True)
def _skip_if_no_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, timeout=10)
        subprocess.run(["ffprobe", "-version"], check=True, capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg/ffprobe not available in this environment")


def test_prefers_a_visually_busy_frame_over_a_blank_one(tmp_path):
    clip_path = str(tmp_path / "clip.mp4")
    _build_clip(clip_path, blank_seconds=3.0, busy_seconds=3.0)

    thumb_path = extract_thumbnail(clip_path, str(tmp_path))

    assert Path(thumb_path).exists()
    with Image.open(thumb_path) as img:
        # A flat black frame has ~zero pixel variance; the busy test
        # pattern is full of edges/color. Confirms the selector actually
        # picked from the busy half, not just whatever ffmpeg gave it
        # first.
        assert img.convert("L").getextrema()[1] > 40


def test_falls_back_to_a_single_frame_when_duration_cannot_be_probed(tmp_path, monkeypatch):
    import app.services.media as media_module

    monkeypatch.setattr(media_module, "_probe_duration_seconds", lambda video_path: None)
    clip_path = str(tmp_path / "clip.mp4")
    _build_clip(clip_path, blank_seconds=1.0, busy_seconds=1.0)

    thumb_path = extract_thumbnail(clip_path, str(tmp_path))

    assert Path(thumb_path).exists()


def test_frame_quality_score_is_higher_for_busy_images_than_blank_ones(tmp_path):
    blank_path = str(tmp_path / "blank.jpg")
    busy_path = str(tmp_path / "busy.jpg")
    Image.new("RGB", (100, 100), color=(10, 10, 10)).save(blank_path)
    # A checkerboard has high pixel-value variance, unlike a flat fill.
    checkerboard = Image.new("RGB", (100, 100))
    pixels = checkerboard.load()
    for x in range(100):
        for y in range(100):
            pixels[x, y] = (255, 255, 255) if (x // 10 + y // 10) % 2 == 0 else (0, 0, 0)
    checkerboard.save(busy_path)

    assert _frame_quality_score(busy_path) > _frame_quality_score(blank_path)
