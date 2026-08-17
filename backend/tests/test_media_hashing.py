"""research/RESEARCH_ROADMAP_V2.md Phase 9 (cross-post provenance,
first-pass perceptual-hash filter). Synthetic PIL images here test the
hashing/comparison LOGIC deterministically -- real-world validation
against genuine ingested video frames is a separate concern, covered by
backend/research/cross_post_v2/verify_perceptual_hash.py, not this
unit-test file (matches this project's existing split between fast
logic tests and live-data verification scripts elsewhere)."""
import random
from pathlib import Path

from PIL import Image

from app.services.media_hashing import DEFAULT_MATCH_THRESHOLD, frame_set_similarity, phash_for_frame


def _make_image(path: Path, seed: int, size=(64, 64)) -> str:
    # Solid-color images are a real, live-discovered pathological case
    # for perceptual hashing (phash is DCT-based on a downscaled
    # grayscale image -- a textureless solid fill carries almost no
    # frequency-domain structure to distinguish one color from another,
    # so two solid colors can hash far closer than intuition suggests).
    # Random per-pixel noise, seeded for determinism, gives every test
    # image real structure instead.
    rng = random.Random(seed)
    img = Image.new("RGB", size)
    img.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(size[0] * size[1])])
    img.save(path)
    return str(path)


def test_identical_images_hash_to_zero_distance(tmp_path):
    a = _make_image(tmp_path / "a.png", seed=1)
    b = _make_image(tmp_path / "b.png", seed=1)
    assert phash_for_frame(a) - phash_for_frame(b) == 0


def test_very_different_images_hash_to_a_large_distance(tmp_path):
    a = _make_image(tmp_path / "a.png", seed=1)
    b = _make_image(tmp_path / "b.png", seed=2)
    assert phash_for_frame(a) - phash_for_frame(b) > DEFAULT_MATCH_THRESHOLD


def test_frame_set_similarity_matches_when_any_frame_pair_is_close(tmp_path):
    # Two "videos" (frame sets) that share one identical frame among
    # otherwise different content -- the intended real-world shape (two
    # posts aren't frame-aligned, but genuinely-shared footage should
    # still produce at least one close pair).
    frames_a = [
        _make_image(tmp_path / "a1.png", seed=1),
        _make_image(tmp_path / "a2.png", seed=2),
    ]
    frames_b = [
        _make_image(tmp_path / "b1.png", seed=3),
        _make_image(tmp_path / "b2.png", seed=2),  # identical to a2
    ]
    result = frame_set_similarity(frames_a, frames_b)
    assert result["is_match"] is True
    assert result["min_distance"] == 0


def test_frame_set_similarity_no_match_when_all_frames_differ(tmp_path):
    frames_a = [_make_image(tmp_path / "a1.png", seed=1)]
    frames_b = [_make_image(tmp_path / "b1.png", seed=99)]
    result = frame_set_similarity(frames_a, frames_b)
    assert result["is_match"] is False


def test_frame_set_similarity_handles_empty_frame_lists():
    result = frame_set_similarity([], ["irrelevant"])
    assert result["is_match"] is False
    assert result["min_distance"] is None
