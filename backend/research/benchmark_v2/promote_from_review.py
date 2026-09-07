"""Review-gated promotion, step 2 of 2.

Reads research/dataset/review_batch.jsonl (filled in by a human) and, for
each row with decision == "promote", does real ingestion and appends a v2
benchmark item built from the HUMAN review fields -- reviewed_claim,
reviewed_label, label_evidence -- NOT the sourcing judge's guess (which is
retained under `_machine_screen` for provenance only).

decision == "defer" rows get their v3 candidate marked
review_status="deferred_crosspost" with the note, so build_review_batch
won't resurface them and they stay available as cross-post evidence.

Idempotent: a candidate already promoted (has promoted_item_id) is skipped.

Run: cd backend && ./.venv/bin/python -m research.benchmark_v2.promote_from_review [--dry-run]
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import update  # noqa: E402

from app.db.models import BenchmarkSplit, DatasetType, MediaType, Platform, Reel  # noqa: E402
from app.db.session import AsyncSessionLocal  # noqa: E402
from app.pipeline import ingestion, ocr, transcription, vision_context  # noqa: E402
from app.schemas.reel import ReelCreate  # noqa: E402
from app.services.storage.s3 import get_storage_client  # noqa: E402

_DS = Path(__file__).resolve().parents[3] / "research" / "dataset"
_REVIEW = _DS / "review_batch.jsonl"
_ITEMS_V1 = _DS / "items.jsonl"
_ITEMS_V2 = _DS / "items_v2.jsonl"
_SPLIT = BenchmarkSplit.validation
_VALID_LABELS = {"FALSE", "MOSTLY_FALSE", "MISLEADING", "MISSING_CONTEXT",
                 "TRUE", "MOSTLY_TRUE", "UNVERIFIED", "OUTDATED"}
_PLATFORM = {"instagram": Platform.instagram, "youtube": Platform.youtube, "x": Platform.x,
             "tiktok": Platform.tiktok, "facebook": Platform.other}


def _next_ids(n: int) -> list[str]:
    seen = set()
    for p, k in ((_ITEMS_V1, "id"), (_ITEMS_V2, "item_id")):
        if p.exists():
            for l in p.read_text().splitlines():
                if l.strip():
                    seen.add(json.loads(l)[k])
    mx = max((int(i.split("-")[-1]) for i in seen), default=0)
    return [f"item-{mx + i + 1:04d}" for i in range(n)]


def _promoted_candidate_ids() -> set[str]:
    ids = set()
    if _ITEMS_V2.exists():
        for l in _ITEMS_V2.read_text().splitlines():
            if l.strip():
                cid = json.loads(l).get("candidate_id")
                if cid:
                    ids.add(cid)
    return ids


def _mark_candidate(cid: str, **fields) -> None:
    for f in _DS.glob("candidates_v3_*.jsonl"):
        rows = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
        hit = False
        for r in rows:
            if r["candidate_id"] == cid:
                r.update(fields)
                hit = True
        if hit:
            f.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
            return


async def _ingest(db, url: str, platform: Platform):
    storage = get_storage_client()
    reel = await ingestion.ingest_reel(db, ReelCreate(source_url=url, platform=platform, auto_fetch=True), None, None)
    await db.commit()
    await db.refresh(reel)
    if reel.media_storage_key and reel.media_type == MediaType.video:
        vb = storage.get_bytes(reel.media_storage_key)
        audio_path, frames = ingestion.extract_media_artifacts(vb)
        await transcription.transcribe_reel(db, reel, audio_path)
        await ocr.ocr_reel(db, reel, frames)
        await vision_context.analyze_vision_context(db, reel, frames)
    elif reel.media_storage_key and reel.media_type == MediaType.photo:
        pb = storage.get_bytes(reel.media_storage_key)
        frames = ingestion.extract_photo_artifact(pb)
        await ocr.ocr_reel(db, reel, frames)
        await vision_context.analyze_vision_context(db, reel, frames)
    await db.commit()
    await db.refresh(reel)
    return reel


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not _REVIEW.exists():
        print("no review_batch.jsonl", file=sys.stderr)
        return
    rows = [json.loads(l) for l in _REVIEW.read_text().splitlines() if l.strip()]
    already = _promoted_candidate_ids()

    # defers
    for r in rows:
        if r.get("decision") == "defer" and r["candidate_id"] not in already:
            if not args.dry_run:
                _mark_candidate(r["candidate_id"], review_status="deferred_crosspost",
                                review_note=r.get("review_notes", ""))

    to_promote = []
    for r in rows:
        if r.get("decision") != "promote" or r["candidate_id"] in already:
            continue
        prob = []
        if not r.get("reviewed_claim") or len(r["reviewed_claim"].split()) < 5:
            prob.append("reviewed_claim missing/too short")
        if r.get("reviewed_label") not in _VALID_LABELS:
            prob.append(f"reviewed_label {r.get('reviewed_label')!r} not valid")
        if not r.get("label_evidence"):
            prob.append("label_evidence missing")
        if prob:
            print(f"  SKIP {r['candidate_id']}: {'; '.join(prob)}", file=sys.stderr)
            continue
        to_promote.append(r)

    print(f"{len(to_promote)} row(s) ready to promote from review; "
          f"{sum(1 for r in rows if r.get('decision') == 'defer')} deferred.", file=sys.stderr)
    if args.dry_run:
        for r in to_promote:
            print(f"  {r['candidate_id']} [{r['platform']}] {r['reviewed_label']:12} {r['reviewed_claim'][:90]}")
        return
    if not to_promote:
        return

    ids = _next_ids(len(to_promote))
    n = 0
    async with AsyncSessionLocal() as db:
        for r, item_id in zip(to_promote, ids):
            plat = _PLATFORM.get(r["platform"], Platform.other)
            print(f"=== {item_id} ({r['candidate_id']}, {r['platform']}): ingesting {r['social_url']} ===", file=sys.stderr)
            try:
                reel = await _ingest(db, r["social_url"], plat)
            except Exception as exc:  # noqa: BLE001
                print(f"  INGESTION FAILED: {exc}", file=sys.stderr)
                await db.rollback()
                continue
            await db.execute(update(Reel).where(Reel.id == reel.id).values(
                dataset_type=DatasetType.benchmark, benchmark_version="v2", benchmark_split=_SPLIT))
            await db.commit()
            item = {
                "item_id": item_id, "benchmark_version": "v2", "split": _SPLIT.value,
                "media": "video" if reel.media_type == MediaType.video else "photo",
                "media_hash": reel.media_content_hash, "platform": r["platform"],
                "original_url": r["social_url"], "factcheck_url": r["factcheck_url"],
                "factchecker": r["factchecker"], "publication_date": None, "factcheck_date": None,
                "ground_truth_label": r["reviewed_label"], "ground_truth_claim": r["reviewed_claim"],
                "ground_truth_notes": r["label_evidence"],
                "claim_type": r.get("claim_type") or None,
                "political_actor": r.get("political_actor") or None,
                "language": r.get("language") or None,
                "audio_available": bool(reel.transcript), "ocr_available": bool(reel.ocr_text),
                "caption_available": bool(reel.caption_text),
                "visual_information_available": reel.vision_context is not None,
                "cross_post_possible": True, "cross_post_verified": None, "difficulty": None,
                "development_split": True, "candidate_id": r["candidate_id"],
                "annotation_status": "reviewed", "labeler": r.get("reviewer", "human-review"),
                "_machine_screen": {"claim": r.get("MACHINE_GUESS_claim"),
                                    "label": r.get("MACHINE_GUESS_label"),
                                    "confidence": r.get("MACHINE_GUESS_confidence")},
            }
            with open(_ITEMS_V2, "a") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
            _mark_candidate(r["candidate_id"], promoted_item_id=item_id, review_status="promoted_reviewed")
            n += 1
            print(f"  ok: media={reel.media_type.value} transcript={len(reel.transcript or '')}c "
                  f"ocr={len(reel.ocr_text or [])} vision={bool(reel.vision_context)}", file=sys.stderr)
    print(f"\nPromoted {n} reviewed item(s) -> {_ITEMS_V2}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
