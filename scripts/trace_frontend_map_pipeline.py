#!/usr/bin/env python3
"""Trace the generated frontend public-map data pipeline without mutating data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv


MAP_TERMS = {
    "map",
    "mapped",
    "lat",
    "lng",
    "latitude",
    "longitude",
    "records",
    "locations",
    "density",
    "figures",
    "frontend",
    "public",
}
SCAN_EXTS = {".js", ".jsx", ".ts", ".tsx", ".json", ".csv", ".py", ".html"}
MANIFEST_FIELDS = [
    "frontend_map_file",
    "frontend_map_count",
    "id_fields_present",
    "canonical_join_key_strategy",
    "export_script_candidates",
    "db_table_candidates",
    "confidence",
    "unresolved_questions",
]
ID_FIELDS = [
    "frontend_join_key",
    "record_id",
    "narrative_unit_id",
    "location_id",
    "stable_id",
    "title",
    "date_published",
    "lat",
    "lng",
    "source_name",
    "source_url",
    "source_file",
]


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def composite_frontend_key(row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            norm(row.get("record_id")),
            norm(row.get("narrative_unit_id")),
            norm(row.get("location_id")),
            norm(row.get("title")),
            norm(row.get("date") or row.get("date_published") or row.get("year")),
            norm(row.get("lat") or row.get("latitude")),
            norm(row.get("lng") or row.get("longitude")),
            norm(row.get("source_url") or row.get("url")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def coord_pair(row: dict[str, Any]) -> str:
    lat = row.get("lat") or row.get("latitude") or row.get("map_latitude") or row.get("y")
    lng = row.get("lng") or row.get("longitude") or row.get("map_longitude") or row.get("x")
    try:
        return f"{float(lat):.6f},{float(lng):.6f}"
    except (TypeError, ValueError):
        return ""


def looks_like_map_data_file(path: Path, text: str) -> bool:
    lower = text.lower()
    return (
        ("lat" in lower or "latitude" in lower)
        and ("lng" in lower or "longitude" in lower)
        and ("record" in lower or "figure" in lower or "location" in lower)
    )


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def scan_source_files(repo_root: Path, frontend_dir: Path) -> list[dict[str, Any]]:
    roots = [frontend_dir, repo_root / "public", repo_root / "scripts", repo_root / "src"]
    seen: set[Path] = set()
    hits: list[dict[str, Any]] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path in seen or not path.is_file() or path.suffix.lower() not in SCAN_EXTS:
                continue
            seen.add(path)
            if path.stat().st_size > 5_000_000 and path.suffix.lower() != ".json":
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lower = text.lower()
            terms = sorted(term for term in MAP_TERMS if term in lower)
            if not terms:
                continue
            if path.name != "frontend-data.json" and path.suffix == ".json" and path.parent.name == "data":
                # Avoid filling the trace with large historical generated variants.
                continue
            hits.append(
                {
                    "path": safe_rel(path, repo_root),
                    "terms": ",".join(terms),
                    "looks_like_map_data": looks_like_map_data_file(path, text),
                    "mentions_frontend_data": "frontend-data.json" in text,
                    "mentions_map_points": "map_points" in text,
                }
            )
    return hits


def extract_json_like(text: str) -> Any | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"(?:export\s+default|module\.exports\s*=|const\s+\w+\s*=)\s*(\[.*\]|\{.*\})\s*;?\s*$", text, re.S)
    if not match:
        return None
    candidate = match.group(1)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    try:
        return json.loads(candidate)
    except Exception:
        return None


def find_frontend_map_payload(repo_root: Path, frontend_dir: Path) -> tuple[Path | None, list[dict[str, Any]], dict[str, Any], list[str]]:
    candidates = [
        repo_root / "public" / "data" / "frontend-data.json",
        frontend_dir / "data" / "frontend-data.json",
        frontend_dir / "src" / "data" / "frontend-data.json",
    ]
    candidates.extend(sorted((repo_root / "public" / "data").glob("*.json")) if (repo_root / "public" / "data").exists() else [])
    unresolved: list[str] = []
    best_path: Path | None = None
    best_rows: list[dict[str, Any]] = []
    best_data: dict[str, Any] = {}
    for path in candidates:
        if not path.exists() or not path.is_file():
            continue
        try:
            data = extract_json_like(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception as exc:
            unresolved.append(f"Could not parse {safe_rel(path, repo_root)}: {exc}")
            continue
        if not isinstance(data, dict):
            continue
        map_points = data.get("map_points")
        if isinstance(map_points, list) and map_points:
            if path.name == "frontend-data.json":
                return path, [row for row in map_points if isinstance(row, dict)], data, unresolved
            if len(map_points) > len(best_rows):
                best_path, best_rows, best_data = path, [row for row in map_points if isinstance(row, dict)], data
    if not best_path:
        unresolved.append("No parseable frontend map data file with a non-empty map_points array was found.")
    return best_path, best_rows, best_data, unresolved


def id_candidate_rows(path: Path | None, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    source_file = str(path or "")
    for row in rows:
        result.append(
            {
                "frontend_join_key": composite_frontend_key(row),
                "record_id": row.get("record_id", ""),
                "narrative_unit_id": row.get("narrative_unit_id", ""),
                "location_id": row.get("location_id", ""),
                "stable_id": row.get("stable_id", ""),
                "title": row.get("title", ""),
                "date_published": row.get("date_published") or row.get("date") or row.get("year") or "",
                "lat": row.get("lat") or row.get("latitude") or row.get("y") or "",
                "lng": row.get("lng") or row.get("longitude") or row.get("x") or "",
                "source_name": row.get("source_name") or row.get("publication") or "",
                "source_url": row.get("source_url") or row.get("url") or "",
                "source_file": source_file,
            }
        )
    return result


def export_script_candidates(repo_root: Path, scan_hits: list[dict[str, Any]]) -> list[str]:
    candidates = [
        hit["path"]
        for hit in scan_hits
        if hit["path"].endswith(".py") and ("frontend-data.json" in hit["path"] or hit.get("mentions_map_points") or hit.get("mentions_frontend_data"))
    ]
    explicit = repo_root / "scripts" / "export_frontend_json.py"
    if explicit.exists():
        rel = safe_rel(explicit, repo_root)
        candidates.insert(0, rel)
    return sorted(dict.fromkeys(candidates))


def db_table_candidates(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        found = []
        for name in ["records", "record_locations", "locations", "narrative_locations", "geocode_review_queue", "collection_candidates"]:
            if table_exists(conn, name):
                found.append(name)
        return found


def build_manifest(repo_root: Path, db_path: Path, frontend_dir: Path, map_path: Path | None, map_rows: list[dict[str, Any]], scan_hits: list[dict[str, Any]], unresolved: list[str]) -> dict[str, Any]:
    id_fields = sorted({field for row in map_rows for field in ["record_id", "narrative_unit_id", "location_id", "stable_id"] if row.get(field) not in (None, "")})
    coord_counts = Counter(coord_pair(row) for row in map_rows)
    duplicate_coords = sum(count - 1 for key, count in coord_counts.items() if key and count > 1)
    strategy = "record_id+coordinate_pair" if "record_id" in id_fields else "composite_frontend_key"
    scripts = export_script_candidates(repo_root, scan_hits)
    db_tables = db_table_candidates(db_path)
    confidence = "high" if map_path and map_rows and scripts and {"records", "record_locations", "locations"}.issubset(set(db_tables)) else "medium"
    return {
        "generated_at": now_iso(),
        "frontend_map_file": safe_rel(map_path, repo_root) if map_path else "",
        "frontend_map_count": len(map_rows),
        "distinct_record_ids": len({str(row.get("record_id")) for row in map_rows if row.get("record_id") not in (None, "")}),
        "distinct_narrative_unit_ids": len({str(row.get("narrative_unit_id")) for row in map_rows if row.get("narrative_unit_id") not in (None, "")}),
        "distinct_coordinate_pairs": len([key for key in coord_counts if key]),
        "duplicate_coordinate_rows": duplicate_coords,
        "rows_with_suppression_or_display_fields": sum(1 for row in map_rows if any(key in row for key in ["display_allowed", "display_mode", "display_suppression_reason"])),
        "id_fields_present": id_fields,
        "canonical_join_key_strategy": strategy,
        "export_script_candidates": scripts,
        "db_table_candidates": db_tables,
        "confidence": confidence,
        "unresolved_questions": unresolved,
        "source_evidence": {
            "public_map_policy_function": "scripts/export_frontend_json.py:is_public_map_location",
            "frontend_map_array": "map_points",
            "frontend_flag_array": "map_flags",
            "derived_from": "record_locations JOIN locations JOIN records",
        },
    }


def write_report(path: Path, manifest: dict[str, Any], scan_hits: list[dict[str, Any]]) -> None:
    lines = [
        "# Frontend Map Pipeline Trace",
        "",
        f"- Generated: `{manifest.get('generated_at')}`",
        f"- Frontend map file: `{manifest.get('frontend_map_file') or 'unresolved'}`",
        f"- Frontend map rows: `{manifest.get('frontend_map_count')}`",
        f"- Join key strategy: `{manifest.get('canonical_join_key_strategy')}`",
        f"- Confidence: `{manifest.get('confidence')}`",
        "",
        "## Pipeline",
        "",
        "- The public frontend map is generated into `public/data/frontend-data.json`.",
        "- `scripts/export_frontend_json.py` writes the `map_points` and `map_flags` arrays.",
        "- `map_points` are selected from `record_locations` joined to `locations` and `records` by `is_public_map_location`, with one representative public map point per record.",
        "- Internal V2 `narrative_locations` rows are audit/review rows and are not automatically public map flags.",
        "",
        "## Manifest",
        f"- ID fields present: `{','.join(manifest.get('id_fields_present') or [])}`",
        f"- Distinct record IDs: `{manifest.get('distinct_record_ids')}`",
        f"- Distinct coordinate pairs: `{manifest.get('distinct_coordinate_pairs')}`",
        f"- Duplicate coordinate rows: `{manifest.get('duplicate_coordinate_rows')}`",
        f"- Rows with display/suppression fields: `{manifest.get('rows_with_suppression_or_display_fields')}`",
        "",
        "## Export Script Candidates",
    ]
    lines.extend([f"- `{item}`" for item in manifest.get("export_script_candidates", [])] or ["- None found"])
    lines.extend(["", "## DB Table Candidates"])
    lines.extend([f"- `{item}`" for item in manifest.get("db_table_candidates", [])] or ["- None found"])
    lines.extend(["", "## Unresolved Questions"])
    lines.extend([f"- {item}" for item in manifest.get("unresolved_questions", [])] or ["- None"])
    lines.extend(["", "## Source Search Hits"])
    for hit in scan_hits[:100]:
        if hit.get("mentions_map_points") or hit.get("mentions_frontend_data") or hit.get("looks_like_map_data"):
            lines.append(f"- `{hit['path']}` terms={hit['terms']}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def trace(repo_root: Path, db_path: Path, frontend_dir: Path, exports_dir: Path, out_dir: Path) -> dict[str, Any]:
    del exports_dir
    repo_root = repo_root.resolve()
    frontend_dir = (repo_root / frontend_dir).resolve() if not frontend_dir.is_absolute() else frontend_dir
    scan_hits = scan_source_files(repo_root, frontend_dir)
    map_path, map_rows, _data, unresolved = find_frontend_map_payload(repo_root, frontend_dir)
    manifest = build_manifest(repo_root, db_path, frontend_dir, map_path, map_rows, scan_hits, unresolved)
    id_rows = id_candidate_rows(map_path, map_rows)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frontend_map_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(
        out_dir / "frontend_map_manifest.csv",
        [
            {
                "frontend_map_file": manifest.get("frontend_map_file", ""),
                "frontend_map_count": manifest.get("frontend_map_count", 0),
                "id_fields_present": ",".join(manifest.get("id_fields_present") or []),
                "canonical_join_key_strategy": manifest.get("canonical_join_key_strategy", ""),
                "export_script_candidates": ";".join(manifest.get("export_script_candidates") or []),
                "db_table_candidates": ";".join(manifest.get("db_table_candidates") or []),
                "confidence": manifest.get("confidence", ""),
                "unresolved_questions": ";".join(manifest.get("unresolved_questions") or []),
            }
        ],
        MANIFEST_FIELDS,
    )
    write_csv(out_dir / "frontend_map_id_candidates.csv", id_rows, ID_FIELDS)
    write_report(out_dir / "frontend_map_pipeline_trace.md", manifest, scan_hits)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--frontend-dir", required=True)
    parser.add_argument("--exports-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    manifest = trace(Path(args.repo_root), Path(args.db), Path(args.frontend_dir), Path(args.exports_dir), Path(args.out_dir))
    print(f"Frontend map file: {manifest.get('frontend_map_file') or 'unresolved'}")
    print(f"Frontend map rows: {manifest.get('frontend_map_count')}")
    print(f"Confidence: {manifest.get('confidence')}")


if __name__ == "__main__":
    main()
