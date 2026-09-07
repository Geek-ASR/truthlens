"""Spot-check + promote ELIGIBLE all-platform candidates
(candidates_v3_<archive>.jsonl, produced by mass_source_allplatform.py)
into real, ingested v2 benchmark items.

Same two-part discipline as the Instagram-only path
(spot_check_eligible_candidates.py + promote_eligible_candidates.py),
folded into one pass because the v3 records already carry the judge
reasoning, confidence, claim, and label inline:

  1. SPOT-CHECK (deterministic, no LLM): reuse the exact self-
     contradiction / hedging / malformed-output patterns from
     spot_check_eligible_candidates.py. A flagged record is downgraded
     ELIGIBLE -> UNRESOLVED in its own per-archive file (not dropped,
     not promoted) with the reason in its history.
  2. PROMOTE: for survivors, real ingestion via the same
     app.pipeline.ingestion.ingest_reel() call production uses --
     fetch + transcribe/OCR/vision -- then append to items_v2.jsonl
     with the candidate's REAL platform (x / youtube / facebook /
     tiktok / instagram), and write promoted_item_id back to the v3
     file so a re-run never double-promotes.

Needs Postgres + MinIO up (infra/docker-compose.yml, or a standalone
`minio server`). Split assignment: validation, same reasoning as
promote_eligible_candidates.py.

Run (dry-run first, always):
  cd backend && ./.venv/bin/python -m research.benchmark_v2.promote_allplatform_candidates --dry-run
  cd backend && ./.venv/bin/python -m research.benchmark_v2.promote_allplatform_candidates --limit 20
"""
import argparse
import asyncio
import fcntl
import json
import sys
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

from sqlalchemy import update  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, MediaType, Platform, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import ingestion, ocr, transcription, vision_context  # noqa: E402
from app.schemas.reel import ReelCreate  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402
from research.benchmark_v2.mass_source_allplatform import normalize_label  # noqa: E402
from research.benchmark_v2.spot_check_eligible_candidates import (  # noqa: E402
    _HEDGING_PHRASES,
    _LIST_LITERAL_PATTERN,
    _MARKDOWN_LINK_PATTERN,
    _SELF_CONTRADICTION_PHRASES,
    _SELF_CONTRADICTION_REGEX,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATASET_DIR = _REPO_ROOT / "research" / "dataset"
_ITEMS_V1_PATH = _DATASET_DIR / "items.jsonl"
_ITEMS_V2_PATH = _DATASET_DIR / "items_v2.jsonl"
_TARGET_SPLIT = BenchmarkSplit.validation

# facebook has no Platform enum member; everything else maps 1:1.
_PLATFORM_MAP = {
    "instagram": Platform.instagram, "youtube": Platform.youtube, "x": Platform.x,
    "tiktok": Platform.tiktok, "facebook": Platform.other,
}


@contextmanager
def _locked(path: Path):
    lock = path.with_suffix(".promote.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _v3_files(archives: list[str] | None) -> list[Path]:
    if archives:
        return [_DATASET_DIR / f"candidates_v3_{a}.jsonl" for a in archives]
    return sorted(_DATASET_DIR.glob("candidates_v3_*.jsonl"))


def _reasoning_of(rec: dict) -> str:
    """Judge reasoning as written by mass_source_allplatform._process_candidate:
    the GROUND_TRUTH_VERIFIED history note, formatted 'llama3.2 (conf=X.XX): <reasoning>'."""
    for h in rec.get("history", []):
        if h["status"] == "GROUND_TRUTH_VERIFIED" and h.get("note"):
            note = h["note"]
            return note.split("): ", 1)[1] if "): " in note else note
    return ""


def _spot_check_flag(rec: dict) -> str | None:
    """None = clean. A string = flagged; caller downgrades to UNRESOLVED.
    Same checks as spot_check_eligible_candidates.py, on the v3 shape."""
    reasoning = _reasoning_of(rec).lower()
    claim = (rec.get("ground_truth_claim") or "").strip()
    # Older v3 records stored the raw llama3.2 label ('False', 'Fake',
    # 'FALSE_CLAIM: ...'); normalize before judging it standard.
    label = normalize_label(rec.get("ground_truth_label"))
    rec["ground_truth_label"] = label

    hits = [p for p in _SELF_CONTRADICTION_PHRASES if p in reasoning]
    if hits:
        return f"self-contradicting reasoning {hits}"
    m = _SELF_CONTRADICTION_REGEX.search(reasoning)
    if m:
        return f"self-contradicting reasoning (pattern {m.group(0)!r})"
    hedging = [p for p in _HEDGING_PHRASES if p in reasoning]
    if hedging:
        return f"hedging reasoning {hedging}"
    if not claim or _MARKDOWN_LINK_PATTERN.search(claim):
        return "malformed ground_truth_claim (empty or a raw link, not a claim sentence)"
    if _LIST_LITERAL_PATTERN.match(claim):
        return "malformed ground_truth_claim (a stringified list, not a claim sentence)"
    if len(claim) < 25 or len(claim.split()) < 5:
        return f"claim too short / fragmentary ({claim!r})"
    if claim.startswith("[") or claim.startswith("("):
        return f"claim wrapped in brackets -- article text, not a clean claim ({claim[:60]!r})"
    _LEAK = ("that's not true", "is also baseless", "the claim that", "yes, that's",
             "a youtube video published", "article published", "as per the article",
             "according to the article", "the fact-check")
    cl = claim.lower()
    if any(cl.startswith(p) or f" {p}" in cl[:40] for p in _LEAK):
        return f"claim looks like leaked article/verdict text, not the claim itself ({claim[:70]!r})"
    if claim[0].islower():
        return f"claim starts mid-sentence (fragment) ({claim[:60]!r})"
    if label not in {"FALSE", "MOSTLY_FALSE", "MISLEADING", "MISSING_CONTEXT",
                     "TRUE", "MOSTLY_TRUE", "UNVERIFIED", "OUTDATED"}:
        return f"non-standard ground_truth_label ({label!r})"
    if not reasoning.strip():
        return "empty reasoning (schema-valid but substantively empty)"
    return None


def _rewrite(path: Path, rows: list[dict]) -> None:
    tmp = path.with_suffix(".jsonl.tmp")
    with open(tmp, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    tmp.replace(path)


def _next_item_ids(n: int) -> list[str]:
    existing = set()
    for path, key in ((_ITEMS_V1_PATH, "id"), (_ITEMS_V2_PATH, "item_id")):
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    existing.add(json.loads(line)[key])
    mx = max((int(i.split("-")[-1]) for i in existing), default=0)
    return [f"item-{mx + i + 1:04d}" for i in range(n)]


async def _ingest(db, source_url: str, platform: Platform):
    storage = get_storage_client()
    payload = ReelCreate(source_url=source_url, platform=platform, auto_fetch=True)
    reel = await ingestion.ingest_reel(db, payload, None, None)
    await db.commit()
    await db.refresh(reel)
    if reel.media_storage_key and reel.media_type == MediaType.video:
        vb = storage.get_bytes(reel.media_storage_key)
        audio_path, frame_paths = ingestion.extract_media_artifacts(vb)
        await transcription.transcribe_reel(db, reel, audio_path)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)
    elif reel.media_storage_key and reel.media_type == MediaType.photo:
        pb = storage.get_bytes(reel.media_storage_key)
        frame_paths = ingestion.extract_photo_artifact(pb)
        await ocr.ocr_reel(db, reel, frame_paths)
        await vision_context.analyze_vision_context(db, reel, frame_paths)
    await db.commit()
    await db.refresh(reel)
    return reel


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", help="comma-list; default = all candidates_v3_*.jsonl")
    ap.add_argument("--limit", type=int, default=0, help="max items to promote this run (0 = no limit)")
    ap.add_argument("--dry-run", action="store_true", help="spot-check + list; no ingestion, no writes to items_v2")
    args = ap.parse_args()
    archives = args.archive.split(",") if args.archive else None

    # --- pass 1: spot-check every ELIGIBLE, downgrade the flagged ones ---
    survivors: list[tuple[Path, dict]] = []
    flagged_n = 0
    for path in _v3_files(archives):
        if not path.exists():
            continue
        with _locked(path):
            rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
            changed = False
            for r in rows:
                if r["eligibility_status"] != "ELIGIBLE" or r.get("promoted_item_id"):
                    continue
                flag = _spot_check_flag(r)
                if flag:
                    flagged_n += 1
                    if not args.dry_run:
                        r["eligibility_status"] = "UNRESOLVED"
                        r.setdefault("history", []).append(
                            {"status": "UNRESOLVED", "at": "promote_allplatform_candidates.py",
                             "note": f"Downgraded from ELIGIBLE: {flag}. Needs manual review."})
                        changed = True
                    print(f"  FLAG {r['candidate_id']} [{r['platform']}]: {flag}", file=sys.stderr)
                else:
                    survivors.append((path, r))
            if changed:
                _rewrite(path, rows)

    print(f"\nSpot-check: {flagged_n} flagged, {len(survivors)} clean and ready to promote.", file=sys.stderr)
    if args.limit:
        survivors = survivors[: args.limit]
    if args.dry_run:
        for _p, r in survivors:
            print(f"  WOULD PROMOTE {r['candidate_id']} [{r['platform']}] {r['ground_truth_label']:14} "
                  f"{(r['ground_truth_claim'] or '')[:90]}")
        print(f"\n(dry run) {len(survivors)} would be promoted.")
        return

    # --- pass 2: real ingestion + append to items_v2.jsonl ---
    item_ids = _next_item_ids(len(survivors))
    promoted = 0
    async with AsyncSessionLocal() as db:
        for (path, cand), item_id in zip(survivors, item_ids):
            url, plat_str = cand["social_url"], cand["platform"]
            platform = _PLATFORM_MAP.get(plat_str, Platform.other)
            print(f"=== {item_id} ({cand['candidate_id']}, {plat_str}): ingesting {url} ===", file=sys.stderr)
            try:
                reel = await _ingest(db, url, platform)
            except Exception as exc:  # noqa: BLE001 -- a real ingestion failure is a real outcome
                print(f"  INGESTION FAILED: {exc}", file=sys.stderr)
                await db.rollback()
                continue
            await db.execute(
                update(Reel).where(Reel.id == reel.id).values(
                    dataset_type=DatasetType.benchmark, benchmark_version="v2", benchmark_split=_TARGET_SPLIT)
            )
            await db.commit()
            item = {
                "item_id": item_id, "benchmark_version": "v2", "split": _TARGET_SPLIT.value,
                "media": "video" if reel.media_type == MediaType.video else "photo",
                "media_hash": reel.media_content_hash,
                "platform": plat_str,
                "original_url": url,
                "factcheck_url": cand["factcheck_article"], "factchecker": cand["factchecker"],
                "publication_date": cand.get("publication_date"), "factcheck_date": cand.get("factcheck_date"),
                "ground_truth_label": cand["ground_truth_label"], "ground_truth_claim": cand["ground_truth_claim"],
                "claim_type": cand.get("claim_type"), "political_actor": cand.get("political_actor"),
                "language": cand.get("language"),
                "audio_available": bool(reel.transcript), "ocr_available": bool(reel.ocr_text),
                "caption_available": bool(reel.caption_text),
                "visual_information_available": reel.vision_context is not None,
                "cross_post_possible": True, "cross_post_verified": None, "difficulty": None,
                "development_split": True, "candidate_id": cand["candidate_id"],
                "judge_confidence": cand.get("judge_confidence"),
            }
            with open(_ITEMS_V2_PATH, "a") as f:
                f.write(json.dumps(item) + "\n")
            with _locked(path):
                rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
                for r in rows:
                    if r["candidate_id"] == cand["candidate_id"]:
                        r["promoted_item_id"] = item_id
                _rewrite(path, rows)
            promoted += 1
            print(f"  ingested: media={reel.media_type.value} transcript={len(reel.transcript or '')}c "
                  f"ocr={len(reel.ocr_text or [])} vision={bool(reel.vision_context)}", file=sys.stderr)

    print(f"\nPromoted {promoted} item(s) -> {_ITEMS_V2_PATH}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
