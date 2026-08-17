"""Perceptual frame hashing (research/RESEARCH_ROADMAP_V2.md Phase 9,
cross-post provenance detection). A genuinely new dependency
(`imagehash`, confirmed absent from this project before this phase) --
free, local, deterministic, no API key, matching this project's
standing $0/no-key-first discipline. First-pass filter only: a
perceptual-hash match is necessary-but-not-sufficient evidence two
videos share the same underlying footage (compression/re-encoding
differences can still shift a hash slightly, hence the distance
threshold rather than exact equality) -- the real cross-post detection
pipeline (not built this pass) layers this under a second,
claim-embedding-based pass and only escalates ambiguous pairs to
Gemini, per the roadmap's own 3-stage design."""
import imagehash
from PIL import Image

# 0 = identical hash. Calibrated empirically against this project's own
# real frame data (see backend/research/cross_post_v2/verify_perceptual_hash.py's
# module docstring for the exact same-video/different-video distances
# this threshold was set from) -- not a default from the imagehash
# library's own docs.
DEFAULT_MATCH_THRESHOLD = 10


def phash_for_frame(frame_path: str) -> imagehash.ImageHash:
    with Image.open(frame_path) as img:
        return imagehash.phash(img)


def frame_set_similarity(frame_paths_a: list[str], frame_paths_b: list[str]) -> dict:
    """Real, deterministic comparison: for every pair of frames across
    the two sets, compute the perceptual-hash Hamming distance and keep
    the minimum distance found for each frame in set A (its best match
    anywhere in set B) -- appropriate for cross-post detection since the
    two videos are not expected to be frame-aligned (different
    trim points, different frame-rate sampling), only to share SOME
    visually near-identical frames if they're really the same footage."""
    if not frame_paths_a or not frame_paths_b:
        return {"best_match_distances": [], "min_distance": None, "is_match": False, "threshold": DEFAULT_MATCH_THRESHOLD}

    hashes_a = [phash_for_frame(p) for p in frame_paths_a]
    hashes_b = [phash_for_frame(p) for p in frame_paths_b]

    best_match_distances = []
    for ha in hashes_a:
        distances = [ha - hb for hb in hashes_b]  # imagehash.ImageHash defines __sub__ as Hamming distance
        best_match_distances.append(min(distances))

    min_distance = min(best_match_distances)
    return {
        "best_match_distances": best_match_distances,
        "min_distance": min_distance,
        # bool(...) explicitly -- imagehash's __sub__ returns a numpy
        # integer, so the raw comparison is numpy.bool_, which fails an
        # `is True`/`is False` identity check even though it's == True.
        # Found live via this module's own tests, not assumed.
        "is_match": bool(min_distance <= DEFAULT_MATCH_THRESHOLD),
        "threshold": DEFAULT_MATCH_THRESHOLD,
    }
