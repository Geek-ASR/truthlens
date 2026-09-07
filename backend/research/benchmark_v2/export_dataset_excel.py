"""Regenerable Excel export of the TruthLens research dataset.

NOT a source of truth. The operational sources of truth stay:
  - research/dataset/items.jsonl        (benchmark_v1, frozen)
  - research/dataset/items_v2.jsonl     (benchmark_v2, growing)
  - research/dataset/candidates_v*.jsonl (sourcing/provenance audit trail)
  - the live Postgres `reels` / `claims` rows (derived + model outputs)

This script reads all of the above and writes a human-readable workbook
(research/dataset/TruthLens_Dataset.xlsx) with one sheet per concern,
keeping RAW / ANNOTATION / DERIVED / MODEL fields visibly separated
(column prefixes) per the dataset design brief. Re-run any time the
dataset changes:

  cd backend && ./.venv/bin/python -m research.benchmark_v2.export_dataset_excel

Sheets: README, Items, Claims, Provenance, Statistics, DataDictionary,
QualityReport, VersionHistory, LabelMapping.
"""
import json
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # backend/

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DS = _REPO_ROOT / "research" / "dataset"
_OUT = _DS / "TruthLens_Dataset.xlsx"

_CANON_LABELS = {"TRUE", "MOSTLY_TRUE", "FALSE", "MOSTLY_FALSE", "MISLEADING",
                 "MISSING_CONTEXT", "UNVERIFIED", "OUTDATED", "SATIRE"}

# --------------------------------------------------------------------------
# Load + normalize the two item files into one canonical row shape
# --------------------------------------------------------------------------

def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _norm_item(raw: dict) -> dict:
    """v1 (items.jsonl) and v2 (items_v2.jsonl) use different key names;
    map both onto one shape. Never invents a value -- missing stays None."""
    g = raw.get
    return {
        # --- identity / versioning / split (mutable: split only) ---
        "id__item_id": g("item_id") or g("id"),
        "id__benchmark_version": g("benchmark_version") or ("v1" if "id" in raw and "item_id" not in raw else None),
        "id__split": g("split"),
        "id__development_split": g("development_split"),
        "id__candidate_id": g("candidate_id"),
        "id__added_date": g("added_date"),
        # --- raw source (immutable) ---
        "raw__platform": g("platform"),
        "raw__original_url": g("original_url") or g("source_url"),
        "raw__factcheck_url": g("factcheck_url") or g("ground_truth_source_url"),
        "raw__publication_date": g("publication_date") or g("date"),
        "raw__language": g("language"),
        "raw__political_actor": g("political_actor"),
        "raw__media": g("media") or g("modality"),
        # --- ground truth (human/source annotation) ---
        "gt__label": g("ground_truth_label"),
        "gt__claim": g("ground_truth_claim") or g("claim_text"),
        "gt__factchecker": g("factchecker") or g("labeler"),
        "gt__factcheck_date": g("factcheck_date"),
        "gt__tier": g("ground_truth_tier"),
        "gt__notes": g("ground_truth_notes"),
        "gt__source_url": g("ground_truth_source_url") or g("factcheck_url"),
        "gt__claim_type": g("claim_type"),
        "gt__judge_confidence": g("judge_confidence"),
        # --- modality signal (derived from live reel row at ingest) ---
        "modality__audio_available": g("audio_available"),
        "modality__ocr_available": g("ocr_available"),
        "modality__caption_available": g("caption_available"),
        "modality__visual_information_available": g("visual_information_available"),
        "modality__modality": g("modality") if g("media") else None,
        "modality__is_visual_claim": g("is_visual_claim"),
        "modality__is_provenance_claim": g("is_provenance_claim"),
        # --- cross-post / provenance-of-claim ---
        "crosspost__possible": g("cross_post_possible"),
        "crosspost__verified": g("cross_post_verified"),
        # --- integrity ---
        "integrity__media_hash": g("media_hash") or g("content_hash"),
        # --- annotation status ---
        "annot__status": g("annotation_status"),
        "annot__labeler": g("labeler"),
        "annot__difficulty": g("difficulty"),
    }


# --------------------------------------------------------------------------
# Provenance: candidate audit trail
# --------------------------------------------------------------------------

def _load_candidates() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted(_DS.glob("candidates_v*.jsonl")):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = d.get("candidate_id")
            if cid:
                d["_source_file"] = p.name
                out[cid] = d
    return out


def _first_seen(cand: dict) -> str | None:
    hist = cand.get("history") or []
    return hist[0].get("at") if hist else None


def _status_trail(cand: dict) -> str:
    return " -> ".join(h.get("status", "?") for h in (cand.get("history") or []))


def _judge_note(cand: dict) -> str:
    for h in cand.get("history") or []:
        if h.get("status") == "GROUND_TRUTH_VERIFIED" and h.get("note"):
            return h["note"]
    for h in cand.get("history") or []:
        if h.get("status") == "ELIGIBLE" and h.get("note"):
            return h["note"]
    return ""


# --------------------------------------------------------------------------
# DB: model-extracted claims for ingested items (best-effort)
# --------------------------------------------------------------------------

def _load_db_claims(item_urls: set[str]) -> dict[str, list[dict]]:
    """Model-extracted claims per original_url, from the live reels/claims
    tables. Returns {} if the DB is unreachable -- the workbook still builds."""
    try:
        import asyncio
        from sqlalchemy import select
        from app.db.models import Claim, Reel
        from app.db.session import AsyncSessionLocal

        async def _run():
            by_url: dict[str, list[dict]] = defaultdict(list)
            async with AsyncSessionLocal() as db:
                rows = (await db.execute(
                    select(Reel.source_url, Claim).join(Claim, Claim.reel_id == Reel.id)
                )).all()
                for src_url, c in rows:
                    key = (src_url or "").rstrip("/")
                    by_url[key].append({
                        "claim_id": str(c.id), "model_extracted_claim_text": c.text,
                        "source_quote": c.source_quote, "claim_type": getattr(c.claim_type, "value", c.claim_type),
                        "importance": c.importance, "verifiable": c.verifiable,
                        "source_modalities": c.source_modalities, "time_reference": c.time_reference,
                        "entities": c.entities, "extraction_model": c.extraction_model,
                        "extraction_confidence": c.extraction_confidence,
                        "status": getattr(c.status, "value", c.status),
                    })
            return by_url

        return asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001
        print(f"  (DB claims unavailable: {type(exc).__name__}: {str(exc)[:120]})", file=sys.stderr)
        return {}


# --------------------------------------------------------------------------
# Quality checks -- flag, never fix
# --------------------------------------------------------------------------

def _quality_checks(items: list[dict]) -> list[dict]:
    checks: list[dict] = []

    def add(name, severity, offenders, note=""):
        checks.append({"check": name, "severity": severity, "count": len(offenders),
                       "item_ids": ", ".join(sorted(str(o) for o in offenders)[:50]), "note": note})

    ids = [it["id__item_id"] for it in items]
    add("duplicate item_id", "error", [k for k, v in Counter(ids).items() if v > 1])
    add("missing item_id", "error", [i for i, it in enumerate(items) if not it["id__item_id"]])
    add("missing original_url", "error", [it["id__item_id"] for it in items if not it["raw__original_url"]])
    add("missing factcheck_url", "warn", [it["id__item_id"] for it in items if not it["raw__factcheck_url"]])
    add("missing ground_truth_label", "error", [it["id__item_id"] for it in items if not it["gt__label"]])
    add("unsupported ground_truth_label", "error",
        [it["id__item_id"] for it in items if it["gt__label"] and it["gt__label"] not in _CANON_LABELS],
        f"allowed: {sorted(_CANON_LABELS)}")
    add("missing ground_truth_claim", "warn", [it["id__item_id"] for it in items if not it["gt__claim"]])
    add("missing provenance (candidate_id)", "warn",
        [it["id__item_id"] for it in items if not it["id__candidate_id"] and it["id__benchmark_version"] == "v2"])
    add("missing media_hash", "warn", [it["id__item_id"] for it in items if not it["integrity__media_hash"]])
    add("missing split", "warn", [it["id__item_id"] for it in items if not it["id__split"]])

    # media_hash reuse across items = duplicate/near-duplicate media
    by_hash = defaultdict(list)
    for it in items:
        if it["integrity__media_hash"]:
            by_hash[it["integrity__media_hash"]].append(it["id__item_id"])
    add("duplicate media_hash (same underlying media)", "review",
        [i for ids_ in by_hash.values() if len(ids_) > 1 for i in ids_],
        "same content_hash on >1 item -- repost/cross-post; keep + flag, do not delete")

    # same ground_truth_claim string on >1 item
    by_claim = defaultdict(list)
    for it in items:
        if it["gt__claim"]:
            by_claim[it["gt__claim"].strip().lower()].append(it["id__item_id"])
    add("duplicate ground_truth_claim text", "review",
        [i for ids_ in by_claim.values() if len(ids_) > 1 for i in ids_],
        "same claim on >1 item -- related-claim / paraphrase leakage risk across splits")

    # split leakage: same factcheck_url or media_hash across different splits
    def _cross_split(keyfn, label):
        m = defaultdict(set)
        for it in items:
            k = keyfn(it)
            if k and it["id__split"]:
                m[k].add(it["id__split"])
        return [k for k, s in m.items() if len(s) > 1], label
    fc_leak, _ = _cross_split(lambda it: it["raw__factcheck_url"], "")
    add("same factcheck_url across >1 split", "error", fc_leak, "split-leakage risk")
    mh_leak, _ = _cross_split(lambda it: it["integrity__media_hash"], "")
    add("same media_hash across >1 split", "error", mh_leak, "split-leakage risk")
    return checks


# --------------------------------------------------------------------------
# Statistics -- all auto-computed
# --------------------------------------------------------------------------

def _dist(items, keyfn):
    return Counter(keyfn(it) or "(none)" for it in items)


def _statistics(items, db_claims) -> list[tuple[str, object]]:
    S: list[tuple[str, object]] = []
    S.append(("generated_at (UTC)", datetime.now(timezone.utc).isoformat(timespec="seconds")))
    S.append(("total_items", len(items)))
    S.append(("  v1 items", sum(1 for it in items if it["id__benchmark_version"] == "v1")))
    S.append(("  v2 items", sum(1 for it in items if it["id__benchmark_version"] == "v2")))
    total_claims = sum(len(v) for v in db_claims.values()) if db_claims else 0
    S.append(("total_model_extracted_claims (DB)", total_claims))
    S.append(("items with >=1 model claim", sum(1 for it in items
              if db_claims.get((it["raw__original_url"] or "").rstrip("/")))))
    S.append(("", ""))
    for title, keyfn in [
        ("label distribution", lambda it: it["gt__label"]),
        ("platform distribution", lambda it: it["raw__platform"]),
        ("language distribution", lambda it: it["raw__language"]),
        ("split distribution", lambda it: it["id__split"]),
        ("benchmark_version distribution", lambda it: it["id__benchmark_version"]),
        ("claim_type distribution", lambda it: it["gt__claim_type"]),
        ("media (video/photo) distribution", lambda it: it["raw__media"]),
        ("factchecker distribution", lambda it: it["gt__factchecker"]),
        ("ground-truth tier distribution", lambda it: it["gt__tier"]),
        ("difficulty distribution", lambda it: it["annot__difficulty"]),
        ("annotation_status distribution", lambda it: it["annot__status"]),
    ]:
        S.append((f"--- {title} ---", ""))
        for k, v in sorted(_dist(items, keyfn).items(), key=lambda x: -x[1]):
            S.append((f"    {k}", v))
    S.append(("--- modality availability (true count) ---", ""))
    for f in ("audio_available", "ocr_available", "caption_available", "visual_information_available"):
        S.append((f"    {f}", sum(1 for it in items if it[f"modality__{f}"] is True)))
    S.append(("--- cross-post ---", ""))
    S.append(("    cross_post_possible = true", sum(1 for it in items if it["crosspost__possible"] is True)))
    S.append(("    cross_post_verified = true", sum(1 for it in items if it["crosspost__verified"] is True)))
    S.append(("--- missing-field rates ---", ""))
    n = max(len(items), 1)
    for label, keyfn in [
        ("no factcheck_url", lambda it: not it["raw__factcheck_url"]),
        ("no publication_date", lambda it: not it["raw__publication_date"]),
        ("no media_hash", lambda it: not it["integrity__media_hash"]),
        ("no split", lambda it: not it["id__split"]),
        ("no difficulty", lambda it: not it["annot__difficulty"]),
        ("no candidate_id (provenance)", lambda it: not it["id__candidate_id"]),
    ]:
        c = sum(1 for it in items if keyfn(it))
        S.append((f"    {label}", f"{c}/{len(items)} ({100*c//n}%)"))
    return S


# --------------------------------------------------------------------------
# Data dictionary
# --------------------------------------------------------------------------

_DATA_DICTIONARY = [
    # field, sheet, type, meaning, allowed_values, required, origin, mutable, example
    ("id__item_id", "Items", "string", "Unique dataset item id", "item-NNNN", "yes", "derived", "no", "item-0023"),
    ("id__benchmark_version", "Items", "string", "Which benchmark generation", "v1 | v2", "yes", "derived", "no", "v2"),
    ("id__split", "Items", "string|null", "DEV/VALIDATION/TEST assignment", "dev | validation | test | null", "no", "human_annotation", "yes (until v1.0 freeze)", "validation"),
    ("id__candidate_id", "Items", "string|null", "Back-reference to the sourcing candidate record (provenance)", "cand-*", "no", "derived", "no", "cand-ap-altnews-0038"),
    ("raw__platform", "Items", "string", "Originating social platform", "instagram|x|youtube|facebook|tiktok|other", "yes", "raw_source", "no", "x"),
    ("raw__original_url", "Items", "string", "The social post being fact-checked", "URL", "yes", "raw_source", "no", "https://twitter.com/.../status/..."),
    ("raw__factcheck_url", "Items", "string", "The professional fact-check article establishing ground truth", "URL", "yes", "raw_source", "no", "https://www.altnews.in/..."),
    ("raw__publication_date", "Items", "date|null", "The post's own publication date", "ISO date | null", "no", "raw_source", "no", "2026-05-05"),
    ("raw__language", "Items", "string|null", "Primary language of the claim/caption", "ISO 639-1 | free text", "no", "raw_source/derived", "no", "en"),
    ("raw__political_actor", "Items", "string|null", "Main political entity referenced", "free text | null", "no", "human_annotation", "yes", "BJP"),
    ("raw__media", "Items", "string", "Media kind", "video | photo", "yes", "derived", "no", "video"),
    ("gt__label", "Items", "string", "Ground-truth verdict", " | ".join(sorted(_CANON_LABELS)), "yes", "human_annotation", "yes (adjudication)", "FALSE"),
    ("gt__claim", "Items", "string", "The claim the fact-check debunks (dataset ground-truth claim, NOT model-extracted)", "free text", "yes", "human_annotation", "yes", "A video shows ..."),
    ("gt__factchecker", "Items", "string", "Fact-check organisation", "domain | free text", "yes", "raw_source", "no", "altnews.in"),
    ("gt__factcheck_date", "Items", "date|null", "Fact-check article publication date", "ISO date | null", "no", "raw_source", "no", "2026-08-13"),
    ("gt__tier", "Items", "string|null", "Source-quality tier for the fact-checker", "tier-1 | tier-2 | null", "no", "human_annotation", "yes", "tier-1"),
    ("gt__notes", "Items", "string|null", "Why this label -- the evidence/qualification behind the verdict", "free text", "no", "human_annotation", "yes", "geolocated to Patna, not Jharkhand"),
    ("gt__claim_type", "Items", "string|null", "Dataset claim-type vocabulary (distinct from app ClaimType)", "provenance | numeric | event | attribution | ...", "no", "human_annotation/model", "yes", "provenance"),
    ("gt__judge_confidence", "Items", "float|null", "Local-LLM sourcing-judge confidence that the post is the misinfo source (screening only, NOT ground truth)", "0.0-1.0 | null", "no", "model_output", "no", "1.0"),
    ("modality__audio_available", "Items", "bool|null", "Ingested reel has a non-empty transcript", "true|false|null", "no", "derived", "no", "true"),
    ("modality__ocr_available", "Items", "bool|null", "Ingested reel has non-empty OCR text", "true|false|null", "no", "derived", "no", "false"),
    ("modality__caption_available", "Items", "bool|null", "Post has caption text", "true|false|null", "no", "derived", "no", "true"),
    ("modality__visual_information_available", "Items", "bool|null", "Vision-context analysis produced output", "true|false|null", "no", "derived", "no", "true"),
    ("crosspost__possible", "Items", "bool|null", "Item structure allows the cross-post attribution problem to apply", "true|false|null", "no", "derived", "no", "true"),
    ("crosspost__verified", "Items", "bool|'partial'|null", "Human confirmed the checkworthy claim lives outside this post's own content", "true|false|partial|null", "no", "human_annotation", "yes", "true"),
    ("integrity__media_hash", "Items", "string|null", "media_content_hash of the ingested media (dedup / cross-post / leakage key)", "sha256 hex | null", "no", "derived", "no", "64464baf..."),
    ("annot__status", "Items", "string|null", "Annotation lifecycle state", "auto_eligible | reviewed | adjudicated | ...", "no", "human_annotation", "yes", "auto_eligible"),
    ("annot__difficulty", "Items", "string|null", "Evidence-difficulty rating (rubric TBD)", "easy | medium | hard | null", "no", "human_annotation", "yes", "null"),
    ("claim_id", "Claims", "string", "Model-extracted claim id (app claims table)", "uuid", "n/a", "model_output", "no", "f6fe3ec9-..."),
    ("model_extracted_claim_text", "Claims", "string", "Claim text produced by TruthLens claim extraction -- distinct from gt__claim", "free text", "n/a", "model_output", "no", "The video depicts ..."),
    ("source_quote", "Claims", "string|null", "Verbatim span the claim was extracted from", "free text | null", "n/a", "model_output", "no", "..."),
    ("source_modalities", "Claims", "list|null", "Modalities the claim was drawn from", "[caption|audio|ocr|visual]", "n/a", "model_output", "no", "['caption']"),
    ("candidate_id", "Provenance", "string", "Sourcing candidate id", "cand-*", "n/a", "derived", "no", "cand-ap-altnews-0038"),
    ("discovery_pipeline", "Provenance", "string", "Which sourcing script found it", "mass_source_allplatform | mass_source_* | manual", "n/a", "derived", "no", "candidates_v3_altnews.jsonl"),
    ("first_seen_utc", "Provenance", "datetime", "When the candidate was first recorded (collection timestamp)", "ISO datetime", "n/a", "derived", "no", "2026-09-07T14:00:00Z"),
    ("status_trail", "Provenance", "string", "Full status history of the candidate", "A -> B -> C", "n/a", "derived", "no", "DISCOVERED -> ... -> ELIGIBLE"),
    ("judge_note", "Provenance", "string", "Local-LLM screening-judge reasoning (screening only)", "free text", "n/a", "model_output", "no", "the caption asserts ..."),
]


# --------------------------------------------------------------------------
# Workbook assembly
# --------------------------------------------------------------------------

_HDR_FILL = PatternFill("solid", fgColor="1F3864")
_HDR_FONT = Font(color="FFFFFF", bold=True)
_GRP_FILL = {"id__": "DDEBF7", "raw__": "E2EFDA", "gt__": "FFF2CC", "modality__": "FCE4D6",
             "crosspost__": "EAD1DC", "integrity__": "D9D9D9", "annot__": "D0CECE"}


def _sheet(wb, title, rows: list[dict], cols: list[str]):
    ws = wb.create_sheet(title)
    for j, c in enumerate(cols, 1):
        cell = ws.cell(1, j, c)
        cell.fill = _HDR_FILL
        cell.font = _HDR_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        pref = next((p for p in _GRP_FILL if c.startswith(p)), None)
        if pref:
            ws.cell(2, j)  # ensure row exists; group tint applied per data cell below
    for i, r in enumerate(rows, 2):
        for j, c in enumerate(cols, 1):
            v = r.get(c)
            if isinstance(v, (list, dict)):
                v = json.dumps(v, ensure_ascii=False)
            ws.cell(i, j, v)
    ws.freeze_panes = "A2"
    for j, c in enumerate(cols, 1):
        w = max(12, min(60, max([len(str(c))] + [len(str(r.get(c, ""))) for r in rows[:200]]) + 2))
        ws.column_dimensions[get_column_letter(j)].width = w
    return ws


def _kv_sheet(wb, title, pairs, headers=("field", "value")):
    ws = wb.create_sheet(title)
    for j, h in enumerate(headers, 1):
        ws.cell(1, j, h).fill = _HDR_FILL
        ws.cell(1, j).font = _HDR_FONT
    for i, row in enumerate(pairs, 2):
        for j, v in enumerate(row, 1):
            ws.cell(i, j, v)
    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 48
    for j in range(2, len(headers) + 1):
        ws.column_dimensions[get_column_letter(j)].width = 90 if title == "README" else 40
    return ws


def main() -> None:
    v1 = _load_jsonl(_DS / "items.jsonl")
    v2 = _load_jsonl(_DS / "items_v2.jsonl")
    items = [_norm_item(r) for r in v1] + [_norm_item(r) for r in v2]
    cands = _load_candidates()
    db_claims = _load_db_claims({it["raw__original_url"] for it in items})

    try:
        git_rev = subprocess.run(["git", "-C", str(_REPO_ROOT), "rev-parse", "--short", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        git_rev = "unknown"

    wb = Workbook()
    wb.remove(wb.active)

    # README
    readme = [
        ("TruthLens research dataset -- Excel export", ""),
        ("generated_at (UTC)", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ("git revision", git_rev),
        ("regenerate with", "cd backend && ./.venv/bin/python -m research.benchmark_v2.export_dataset_excel"),
        ("", ""),
        ("SOURCE OF TRUTH", "This workbook is a VIEW, not the source of truth."),
        ("  items", "research/dataset/items.jsonl (v1, frozen) + items_v2.jsonl (v2, growing)"),
        ("  provenance", "research/dataset/candidates_v*.jsonl (append-only audit trail w/ status history)"),
        ("  derived + model", "live Postgres reels / claims rows"),
        ("", ""),
        ("RAW vs DERIVED vs MODEL", "Column prefixes keep these separate, per the dataset brief:"),
        ("  raw__*", "immutable source facts (platform, URLs, caption, dates)"),
        ("  gt__*", "human/source ground truth (label, claim, factchecker, evidence notes)"),
        ("  modality__*", "derived at ingest from the real reel row (audio/ocr/caption/visual availability)"),
        ("  integrity__*", "content hashes for dedup / cross-post / leakage detection"),
        ("  annot__*", "annotation lifecycle (status, difficulty, adjudication)"),
        ("  Claims sheet: model_extracted_claim_text", "TruthLens's own extraction -- NEVER overwrites gt__claim"),
        ("  Provenance sheet: judge_note / judge_confidence", "local-LLM SCREENING only -- NOT ground truth"),
        ("", ""),
        ("Sheets", "Items | Claims | Provenance | Statistics | DataDictionary | QualityReport | VersionHistory | LabelMapping"),
        ("NOTE", "Statistics & QualityReport are recomputed on every run. QualityReport flags, never fixes."),
    ]
    _kv_sheet(wb, "README", readme)

    # Items
    item_cols = list(_norm_item({}).keys())
    for it in items:
        cid = it["id__candidate_id"]
        c = cands.get(cid or "", {})
        it["prov__discovery_file"] = c.get("_source_file")
        it["prov__first_seen_utc"] = _first_seen(c) if c else None
    _sheet(wb, "Items", items, item_cols + ["prov__discovery_file", "prov__first_seen_utc"])

    # Claims (model-extracted) + the dataset ground-truth claim as origin=dataset_ground_truth
    claim_rows = []
    for it in items:
        key = (it["raw__original_url"] or "").rstrip("/")
        claim_rows.append({
            "item_id": it["id__item_id"], "origin": "dataset_ground_truth",
            "claim_text": it["gt__claim"], "claim_type": it["gt__claim_type"],
            "ground_truth_label": it["gt__label"],
        })
        for mc in db_claims.get(key, []):
            claim_rows.append({"item_id": it["id__item_id"], "origin": "model_extracted", **mc})
    ccols = ["item_id", "origin", "claim_text", "model_extracted_claim_text", "ground_truth_label",
             "claim_type", "importance", "verifiable", "source_quote", "source_modalities",
             "time_reference", "entities", "extraction_model", "extraction_confidence", "status", "claim_id"]
    _sheet(wb, "Claims", claim_rows, ccols)

    # Provenance
    prov_rows = []
    promoted_cids = {it["id__candidate_id"] for it in items if it["id__candidate_id"]}
    for cid, c in sorted(cands.items()):
        if c.get("eligibility_status") not in ("ELIGIBLE",) and cid not in promoted_cids:
            continue  # keep the sheet to what became / could become an item
        prov_rows.append({
            "candidate_id": cid, "promoted_item_id": c.get("promoted_item_id"),
            "eligibility_status": c.get("eligibility_status"),
            "factchecker": c.get("factchecker"), "platform": c.get("platform"),
            "social_url": c.get("social_url"), "factcheck_article": c.get("factcheck_article"),
            "discovery_pipeline": c.get("_source_file"),
            "first_seen_utc": _first_seen(c), "status_trail": _status_trail(c),
            "judge_confidence": c.get("judge_confidence"),
            "ground_truth_label_screen": c.get("ground_truth_label"),
            "ground_truth_claim_screen": c.get("ground_truth_claim"),
            "judge_note": _judge_note(c), "rejection_reason": c.get("rejection_reason"),
        })
    _sheet(wb, "Provenance", prov_rows,
           ["candidate_id", "promoted_item_id", "eligibility_status", "factchecker", "platform",
            "social_url", "factcheck_article", "discovery_pipeline", "first_seen_utc", "status_trail",
            "judge_confidence", "ground_truth_label_screen", "ground_truth_claim_screen",
            "judge_note", "rejection_reason"])

    # Statistics
    _kv_sheet(wb, "Statistics", _statistics(items, db_claims), headers=("metric", "value"))

    # Data dictionary
    _sheet(wb, "DataDictionary",
           [dict(zip(["field", "sheet", "type", "meaning", "allowed_values", "required",
                      "origin", "mutable", "example"], row)) for row in _DATA_DICTIONARY],
           ["field", "sheet", "type", "meaning", "allowed_values", "required", "origin", "mutable", "example"])

    # Quality report
    _sheet(wb, "QualityReport", _quality_checks(items),
           ["check", "severity", "count", "item_ids", "note"])

    # Version history (from git log of the item files + a seed)
    vh = [("v0.x", "see research/DATASET_SCHEMA_V2.md + DATASET_CARD.md", "", "")]
    try:
        log = subprocess.run(
            ["git", "-C", str(_REPO_ROOT), "log", "--format=%ad|%h|%s", "--date=short",
             "--", "research/dataset/items.jsonl", "research/dataset/items_v2.jsonl"],
            capture_output=True, text=True).stdout.strip().splitlines()
        for line in log:
            d, h, s = (line.split("|", 2) + ["", "", ""])[:3]
            vh.append((d, h, s, ""))
    except Exception:  # noqa: BLE001
        pass
    _kv_sheet(wb, "VersionHistory", vh, headers=("date", "commit", "change", "notes"))

    # Label mapping (source label -> TruthLens taxonomy, rationale, review flag)
    lm = [("(populate as non-canonical source labels appear)", "", "", ""),
          ("FALSE", "FALSE", "direct", "no"),
          ("Fake / False / false claim:", "FALSE", "normalize_label() in mass_source_allplatform.py", "no"),
          ("Partly false / Partially false", "MOSTLY_FALSE", "synonym map", "review"),
          ("Half true / Missing context", "MISLEADING / MISSING_CONTEXT", "synonym map", "review"),
          ("Satire", "MISLEADING", "synonym map -- ambiguous", "review")]
    _kv_sheet(wb, "LabelMapping", lm, headers=("source_label", "truthlens_label", "mapping_rationale", "needs_human_review"))

    wb.save(_OUT)
    print(f"wrote {_OUT}  ({len(items)} items, {len(claim_rows)} claim rows, {len(prov_rows)} provenance rows)")
    errs = [c for c in _quality_checks(items) if c["severity"] == "error" and c["count"]]
    if errs:
        print("  QUALITY ERRORS:", file=sys.stderr)
        for c in errs:
            print(f"    [{c['count']}] {c['check']}: {c['item_ids']}", file=sys.stderr)


if __name__ == "__main__":
    main()
