# CROSS_POST_DETECTION_V2.md — Phase 9

Status: 2026-08-18. `research/RESEARCH_ROADMAP_V2.md` Phase 9: build
cross-post detection using perceptual/frame hashing as a first-pass
filter (a genuinely new dependency, confirmed absent before this phase),
`Claim.embedding` for claim-level clustering as a second pass, Gemini
escalation only for ambiguous pairs.

## What was built this pass: stage 1 only (perceptual hashing)

`app/services/media_hashing.py` — `imagehash.phash` (perceptual hash,
DCT-based) over video frames, `frame_set_similarity()` comparing two
frame sets by taking, for each frame in set A, its minimum Hamming
distance to any frame in set B (appropriate since cross-posted videos
are not expected to be frame-aligned — different trims, different
sampling — only to share *some* visually near-identical frames if
they're really the same footage). `imagehash==4.3.2` added to
`requirements.txt`.

**Stages 2 (claim-embedding clustering) and 3 (Gemini escalation for
ambiguous pairs) were NOT built this pass** — the 3-stage decomposition
is itself named in the roadmap as "the main deliverable, independent of
the final numbers"; this pass delivers stage 1 for real, rather than a
thin stub of all 3.

## A real bug found via this module's own tests

`frame_set_similarity()`'s `is_match` field initially returned a numpy
`bool_`, not a Python `bool` — `imagehash`'s `__sub__` (Hamming distance)
returns a numpy integer, so a plain `<=` comparison inherits numpy's
type. Caught by an `is True`/`is False` identity assertion in this
module's own test, not assumed — fixed with an explicit `bool(...)` cast.

## A real, live-discovered pathological case: solid-color images

The first version of this module's tests used solid-color synthetic
images (pure white vs. pure black) as a "very different images" negative
control — and it failed: solid colors hash far closer together than
intuition suggests, because `phash` is DCT-based on a downscaled
grayscale image, and a textureless solid fill carries almost no
frequency-domain structure to distinguish one flat color from another.
Fixed by using seeded random-noise images (real per-pixel structure)
instead — a real, disclosed limitation of perceptual hashing worth
keeping in mind for any future real cross-post pair that happens to
include large solid-color regions (e.g. letterboxing, blank
title-cards).

## Real-data verification (EXP-018)

Synthetic-image unit tests (5, `tests/test_media_hashing.py`) cover the
hashing/comparison logic in isolation. Separately, ran the same
functions against REAL frames re-extracted from real, already-ingested
benchmark videos (`app.pipeline.ingestion.extract_media_artifacts`, the
exact function real ingestion uses — not a reimplementation):

- **Same-video positive control** (one real reel's video, frames
  independently re-extracted twice via two separate ffmpeg sampling
  passes): `min_distance = 0`, `is_match = True`. Confirms the pipeline
  works end-to-end against real video frames, not just clean synthetic
  images — a necessary, if trivial (it's literally the same source
  video), sanity check.
- **Different-video negative control** (two different, unrelated real
  reels): `min_distance = 20`, well above the threshold (10),
  `is_match = False`.

## What was attempted but not achieved: a genuine two-post cross-post pair

`research/dataset/items.jsonl`'s item-0002 documents a real, specific
cross-post case with a named original source (Alt News:
"flowmexicanoofficial", posted 2026-06-27, a Mexico World Cup
celebration video later miscaptioned as Delhi CJP protest footage).
A live web search located and confirmed the real Alt News article
describing this source, but the original Instagram post's own URL is
embedded in the article via an Instagram embed widget rather than
plain, quotable text — the same tooling limitation encountered earlier
this session (research/RESEARCH_ROADMAP_V2.md Phase 1 sourcing pass,
`cand-2026-08-17-005`) — and could not be extracted through available
tooling within reasonable effort this pass. **Disclosed honestly rather
than forced or faked**: this pass's real validation is the same-video/
different-video controls above, not a genuine two-independently-posted
-same-footage match. A future pass with direct browser access could
complete this specific check.

## What did NOT happen

- No integration into the live pipeline (this remains, like the entity
  -consistency prototype originally was, an unintegrated capability
  until stages 2-3 exist and a real evaluation against constructed
  same-video-different-caption pairs can inform an integrate/don't
  -integrate decision, per the roadmap's own precedent for this kind of
  capability).
- `media_content_hash` (byte-identical dedup, existing) is unchanged --
  this new capability is additive, not a replacement.

## Raw data

`research/results/cross_post_perceptual_hash_verification_20260818.json`.
Generator: `backend/research/cross_post_v2/verify_perceptual_hash.py`.
