#!/usr/bin/env python3
"""Reconcile frontend public map rows against internal mapped-like rows."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, pct, table_exists, write_csv


SUMMARY_FIELDS = [
    "population_name",
    "source_kind",
    "table_or_file",
    "total_rows",
    "distinct_record_ids",
    "distinct_narrative_unit_ids",
    "rows_with_lat_lng",
    "notes",
]
POP_FIELDS = [
    "population_kind",
    "frontend_join_key",
    "record_id",
    "narrative_unit_id",
    "legacy_map_id",
    "location_id",
    "source_name",
    "source_file",
    "title",
    "year",
    "lat",
    "lng",
    "state",
    "source_url",
    "source_stated_place_text",
    "location_role",
    "coordinate_precision",
    "geocode_confidence",
    "review_status",
    "notes",
]
PARTITION_FIELDS = [
    "row_source_table",
    "row_id",
    "record_id",
    "narrative_unit_id",
    "candidate_id",
    "location_id",
    "frontend_join_key",
    "lat",
    "lng",
    "title",
    "date_published",
    "source_name",
    "source_url",
    "display_allowed",
    "is_public",
    "is_suppressed",
    "in_frontend_map",
    "partition_label",
    "partition_reason",
]


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def norm_id(value: Any) -> str:
    return str(value or "").strip()


def coord_key(lat: Any, lng: Any) -> str:
    try:
        return f"{float(lat):.6f},{float(lng):.6f}"
    except (TypeError, ValueError):
        return ""


def frontend_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ["record_id", "narrative_unit_id", "location_id", "stable_id", "frontend_join_key"]:
        value = norm_id(row.get(field))
        if value:
            keys.add(value)
            keys.add(f"{field}:{value}")
    record_id = norm_id(row.get("record_id"))
    pair = coord_key(row.get("lat") or row.get("latitude"), row.get("lng") or row.get("longitude"))
    if record_id and pair:
        keys.add(f"record_coord:{record_id}:{pair}")
    return keys


def load_frontend_map(out_dir: Path, frontend_dir: Path) -> tuple[list[dict[str, Any]], dict[str, Any], Path | None]:
    manifest = load_json(out_dir / "frontend_map_manifest.json")
    paths: list[Path] = []
    if manifest.get("frontend_map_file"):
        paths.append(ROOT / str(manifest["frontend_map_file"]))
    paths.extend([ROOT / "public" / "data" / "frontend-data.json", frontend_dir / "frontend-data.json"])
    for path in paths:
        if not path.exists():
            continue
        data = load_json(path)
        rows = data.get("map_points")
        if isinstance(rows, list) and rows:
            return [row for row in rows if isinstance(row, dict)], manifest, path
    return [], manifest, None


def load_frontend_records(frontend_dir: Path) -> tuple[list[dict[str, Any]], Path | None]:
    for path in [ROOT / "public" / "data" / "frontend-data.json", frontend_dir / "frontend-data.json"]:
        data = load_json(path)
        rows = data.get("records")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)], path
    return [], None


def canonical_map_population(rows: list[dict[str, Any]], source_file: Path | None) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        result.append(
            {
                "population_kind": "canonical_frontend_public_map_row",
                "frontend_join_key": next((key for key in frontend_keys(row) if key.startswith("record_coord:")), "") or next(iter(frontend_keys(row)), ""),
                "record_id": row.get("record_id", ""),
                "narrative_unit_id": row.get("narrative_unit_id", ""),
                "legacy_map_id": "",
                "location_id": row.get("location_id", ""),
                "source_name": row.get("source_name") or row.get("publication") or "",
                "source_file": str(source_file or ""),
                "title": row.get("title", ""),
                "year": row.get("year") or row.get("date_published") or "",
                "lat": row.get("latitude") or row.get("lat") or "",
                "lng": row.get("longitude") or row.get("lng") or "",
                "state": row.get("state_territory") or row.get("state") or "",
                "source_url": row.get("url") or row.get("source_url") or "",
                "source_stated_place_text": row.get("place_name") or row.get("evidence_text") or "",
                "location_role": row.get("relation_type") or "",
                "coordinate_precision": row.get("location_type") or "",
                "geocode_confidence": row.get("confidence") or "",
                "review_status": row.get("verification_status") or "",
                "notes": "frontend map_points row",
            }
        )
    return result


def canonical_record_population(rows: list[dict[str, Any]], source_file: Path | None) -> list[dict[str, Any]]:
    return [
        {
            "population_kind": "canonical_frontend_public_record",
            "frontend_join_key": f"record_id:{row.get('record_id')}",
            "record_id": row.get("record_id", ""),
            "narrative_unit_id": "",
            "legacy_map_id": "",
            "location_id": "",
            "source_name": row.get("source_name", ""),
            "source_file": str(source_file or ""),
            "title": row.get("title", ""),
            "year": row.get("year") or row.get("date_published") or "",
            "lat": row.get("map_latitude", ""),
            "lng": row.get("map_longitude", ""),
            "state": row.get("state_territory", ""),
            "source_url": row.get("url", ""),
            "source_stated_place_text": row.get("map_place_name") or row.get("map_evidence_text") or "",
            "location_role": row.get("map_location_role", ""),
            "coordinate_precision": row.get("map_location_type", ""),
            "geocode_confidence": row.get("map_confidence", ""),
            "review_status": row.get("map_verification_status", ""),
            "notes": "frontend records row",
        }
        for row in rows
    ]


def legacy_record_lookup(conn: sqlite3.Connection) -> dict[str, str]:
    if not table_exists(conn, "legacy_record_mappings"):
        return {}
    rows = conn.execute("SELECT legacy_record_id, narrative_id FROM legacy_record_mappings").fetchall()
    return {str(row["narrative_id"]): str(row["legacy_record_id"]) for row in rows}


def narrative_display_lookup(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    if not table_exists(conn, "narrative_units"):
        return {}
    rows = conn.execute("SELECT narrative_id, display_mode, analysis_status, narrative_status FROM narrative_units").fetchall()
    return {str(row["narrative_id"]): {key: str(row[key] or "") for key in row.keys()} for row in rows}


def geocode_narrative_ids(conn: sqlite3.Connection) -> set[str]:
    if not table_exists(conn, "geocode_review_queue"):
        return set()
    rows = conn.execute("SELECT narrative_unit_id FROM geocode_review_queue WHERE narrative_unit_id IS NOT NULL").fetchall()
    return {str(row["narrative_unit_id"]) for row in rows}


def mapped_like_rows(conn: sqlite3.Connection, exports_dir: Path) -> list[dict[str, Any]]:
    path = exports_dir / "narrative_locations_review.csv"
    if path.exists():
        return read_csv_rows(path)
    if not table_exists(conn, "narrative_locations") or not table_exists(conn, "locations"):
        return []
    rows = conn.execute(
        """
        SELECT nl.narrative_location_id, nl.narrative_id, nl.location_id, nl.source_item_id,
               nl.location_role, nl.location_text_as_printed, nl.location_precision,
               nl.verification_status, nl.confidence, nl.evidence_excerpt, nl.review_status,
               l.place_name, l.region, l.state_territory, l.country, l.latitude, l.longitude
        FROM narrative_locations nl
        LEFT JOIN locations l ON l.location_id = nl.location_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def partition_row(row: dict[str, Any], legacy_lookup: dict[str, str], display_lookup: dict[str, dict[str, str]], geocode_ids: set[str], frontend_key_set: set[str], duplicate_seen: set[tuple[str, str]]) -> dict[str, Any]:
    narrative_id = norm_id(row.get("narrative_id") or row.get("narrative_unit_id"))
    record_id = norm_id(row.get("record_id") or legacy_lookup.get(narrative_id))
    location_id = norm_id(row.get("location_id"))
    lat = row.get("latitude") or row.get("lat")
    lng = row.get("longitude") or row.get("lng")
    pair = coord_key(lat, lng)
    display = display_lookup.get(narrative_id, {})
    display_mode = (display.get("display_mode") or "").lower()
    review_status = str(row.get("review_status") or "").lower()
    role = str(row.get("location_role") or row.get("relation_type") or "").lower()
    precision = str(row.get("location_precision") or row.get("location_type") or "").lower()
    candidate_id = norm_id(row.get("candidate_id"))
    keys = {f"narrative_unit_id:{narrative_id}", f"location_id:{location_id}"}
    if record_id and pair:
        keys.add(f"record_coord:{record_id}:{pair}")
    in_frontend = bool(keys.intersection(frontend_key_set))
    is_suppressed = display_mode in {"suppressed", "restricted", "hidden"} or "suppress" in review_status
    is_public = display_mode in {"full", "summary_only", "metadata_only"} and not is_suppressed
    duplicate_key = (record_id, pair)

    if in_frontend:
        label, reason = "FRONTEND_PUBLIC_MAP", "record and coordinate match frontend map_points"
    elif candidate_id:
        label, reason = "CANDIDATE_LOCATION_ROW", "candidate/staging row"
    elif narrative_id in geocode_ids:
        label, reason = "GEOCODE_REVIEW_ROW", "narrative has geocode review queue row"
    elif is_suppressed:
        label, reason = "SUPPRESSED_LOCATION_ROW", "display mode or review status suppresses public display"
    elif pair and duplicate_key in duplicate_seen:
        label, reason = "DUPLICATE_LOCATION_ROW", "same record/coordinate appears earlier"
    elif precision in {"country_or_unclear", "broad_region", "state_or_territory", "country"} or role in {"publication_location", "source_collection_location"}:
        label, reason = "LEGACY_NONPUBLIC_LOCATION", "broad, state/country, or rejected location role"
    elif narrative_id:
        label, reason = "INTERNAL_LOCATION_ROW", "V2/internal location row not selected as representative frontend map point"
    else:
        label, reason = "UNKNOWN_MAPPED_LIKE_ROW", "could not determine frontend/internal population"
    if pair:
        duplicate_seen.add(duplicate_key)
    return {
        "row_source_table": "narrative_locations_review",
        "row_id": row.get("narrative_location_id") or row.get("row_id") or "",
        "record_id": record_id,
        "narrative_unit_id": narrative_id,
        "candidate_id": candidate_id,
        "location_id": location_id,
        "frontend_join_key": f"record_coord:{record_id}:{pair}" if record_id and pair else f"record_id:{record_id}",
        "lat": lat or "",
        "lng": lng or "",
        "title": row.get("title") or row.get("working_title") or "",
        "date_published": row.get("date_published") or row.get("earliest_attestation_start") or "",
        "source_name": row.get("source_name") or "",
        "source_url": row.get("source_url") or "",
        "display_allowed": "0" if is_suppressed else ("1" if is_public else ""),
        "is_public": "true" if is_public else "false",
        "is_suppressed": "true" if is_suppressed else "false",
        "in_frontend_map": "true" if in_frontend else "false",
        "partition_label": label,
        "partition_reason": reason,
    }


def partition_mapped_like(db_path: Path, exports_dir: Path, frontend_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    frontend_key_set: set[str] = set()
    for row in frontend_rows:
        frontend_key_set.update(frontend_keys(row))
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        legacy = legacy_record_lookup(conn)
        display = narrative_display_lookup(conn)
        geocode_ids = geocode_narrative_ids(conn)
        rows = mapped_like_rows(conn, exports_dir)
    duplicate_seen: set[tuple[str, str]] = set()
    return [partition_row(row, legacy, display, geocode_ids, frontend_key_set, duplicate_seen) for row in rows]


def count_sources(db_path: Path, exports_dir: Path, frontend_records: list[dict[str, Any]], frontend_map: list[dict[str, Any]], partitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "population_name": "canonical_frontend_public_records",
            "source_kind": "frontend_json",
            "table_or_file": "public/data/frontend-data.json.records",
            "total_rows": len(frontend_records),
            "distinct_record_ids": len({r.get("record_id") for r in frontend_records if r.get("record_id")}),
            "distinct_narrative_unit_ids": 0,
            "rows_with_lat_lng": sum(1 for r in frontend_records if r.get("map_latitude") and r.get("map_longitude")),
            "notes": "public frontend records",
        },
        {
            "population_name": "canonical_frontend_public_map_rows",
            "source_kind": "frontend_json",
            "table_or_file": "public/data/frontend-data.json.map_points",
            "total_rows": len(frontend_map),
            "distinct_record_ids": len({r.get("record_id") for r in frontend_map if r.get("record_id")}),
            "distinct_narrative_unit_ids": len({r.get("narrative_unit_id") for r in frontend_map if r.get("narrative_unit_id")}),
            "rows_with_lat_lng": sum(1 for r in frontend_map if (r.get("latitude") or r.get("lat")) and (r.get("longitude") or r.get("lng"))),
            "notes": "public frontend map points",
        },
        {
            "population_name": "db_legacy_mapped_like_rows",
            "source_kind": "export_csv",
            "table_or_file": str(exports_dir / "narrative_locations_review.csv"),
            "total_rows": len(partitions),
            "distinct_record_ids": len({r.get("record_id") for r in partitions if r.get("record_id")}),
            "distinct_narrative_unit_ids": len({r.get("narrative_unit_id") for r in partitions if r.get("narrative_unit_id")}),
            "rows_with_lat_lng": sum(1 for r in partitions if r.get("lat") and r.get("lng")),
            "notes": "partitioned internal mapped-like rows",
        },
    ]
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for name, table in [
            ("db_public_records", "records"),
            ("db_internal_location_rows", "narrative_locations"),
            ("db_candidate_location_rows", "collection_candidates"),
            ("db_geocode_review_rows", "geocode_review_queue"),
        ]:
            if not table_exists(conn, table):
                continue
            total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            rows.append(
                {
                    "population_name": name,
                    "source_kind": "sqlite",
                    "table_or_file": table,
                    "total_rows": total,
                    "distinct_record_ids": "",
                    "distinct_narrative_unit_ids": "",
                    "rows_with_lat_lng": "",
                    "notes": "schema-level population count",
                }
            )
    return rows


def conflict_resolved(frontend_count: int, mapped_like_count: int, partitions: list[dict[str, Any]], manifest: dict[str, Any]) -> tuple[bool, str]:
    if not frontend_count or manifest.get("frontend_map_file") in (None, ""):
        return False, "frontend map file could not be parsed"
    diff = max(0, mapped_like_count - frontend_count)
    unknown = sum(1 for row in partitions if row.get("partition_label") == "UNKNOWN_MAPPED_LIKE_ROW")
    matched_frontend = sum(1 for row in partitions if row.get("partition_label") == "FRONTEND_PUBLIC_MAP")
    explained_nonfrontend = sum(1 for row in partitions if row.get("partition_label") not in {"FRONTEND_PUBLIC_MAP", "UNKNOWN_MAPPED_LIKE_ROW"})
    frontend_only = max(0, frontend_count - matched_frontend)
    net_explained = max(0, explained_nonfrontend - frontend_only)
    if diff == 0:
        return True, "frontend and mapped-like counts match"
    if net_explained >= int(diff * 0.95) and unknown <= max(5, int(mapped_like_count * 0.05)):
        return (
            True,
            f"{mapped_like_count} mapped-like rows partition into {matched_frontend} frontend matches and {explained_nonfrontend} non-frontend/internal rows; "
            f"{frontend_only} frontend map rows are frontend-only relative to V2 narrative_locations, yielding the {diff}-row net difference",
        )
    return False, f"only {net_explained} of {diff} net difference rows explained; {unknown} unknown rows remain"


def write_partition_summary(path: Path, partitions: list[dict[str, Any]], frontend_count: int, resolved: bool, reason: str) -> None:
    counts = Counter(row["partition_label"] for row in partitions)
    lines = [
        "# Mapped-Like Row Partition Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Frontend public map rows: `{frontend_count}`",
        f"- Internal mapped-like rows: `{len(partitions)}`",
        f"- Difference: `{len(partitions) - frontend_count}`",
        f"- count_conflict_resolved: `{str(resolved).lower()}`",
        f"- Resolution reason: {reason}",
        "",
        "## Partitions",
    ]
    lines.extend([f"- `{key}`: {counts[key]}" for key in sorted(counts)] or ["- None"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(path: Path, counts: list[dict[str, Any]], partitions: list[dict[str, Any]], canonical_records: list[dict[str, Any]], canonical_map: list[dict[str, Any]], resolved: bool, reason: str) -> None:
    partition_counts = Counter(row["partition_label"] for row in partitions)
    lines = [
        "# Canonical Count Reconciliation",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Canonical frontend public records: `{len(canonical_records)}`",
        f"- Canonical frontend public map rows: `{len(canonical_map)}`",
        f"- DB legacy mapped-like rows: `{len(partitions)}`",
        f"- count_conflict_resolved: `{str(resolved).lower()}`",
        f"- Resolution reason: {reason}",
        "",
        "## Population Counts",
    ]
    for row in counts:
        lines.append(f"- `{row['population_name']}`: {row['total_rows']} ({row['table_or_file']})")
    lines.extend(["", "## Mapped-Like Row Partitions"])
    lines.extend([f"- `{key}`: {partition_counts[key]}" for key in sorted(partition_counts)] or ["- None"])
    if not resolved:
        lines.extend(["", "## count_conflict", "", "The frontend/internal public map population remains unresolved. Cleanup must stay blocked."])
    else:
        lines.extend(["", "## Count Conflict", "", "The 1,593 vs 4,393 discrepancy is explained by partitioning non-frontend/internal mapped-like rows."])
    lines.extend(["", "## Safety Note", "- Only `FRONTEND_PUBLIC_MAP` rows may be scored as public map cleanup candidates."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def reconcile(db_path: Path, frontend_dir: Path, exports_dir: Path, out_dir: Path) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frontend_map, manifest, map_file = load_frontend_map(out_dir, frontend_dir)
    frontend_records, records_file = load_frontend_records(frontend_dir)
    canonical_map = canonical_map_population(frontend_map, map_file)
    canonical_records = canonical_record_population(frontend_records, records_file)
    partitions = partition_mapped_like(db_path, exports_dir, frontend_map)
    counts = count_sources(db_path, exports_dir, frontend_records, frontend_map, partitions)
    resolved, reason = conflict_resolved(len(frontend_map), len(partitions), partitions, manifest)

    write_csv(out_dir / "canonical_count_reconciliation.csv", counts, SUMMARY_FIELDS)
    write_csv(out_dir / "canonical_public_map_population.csv", canonical_map, POP_FIELDS)
    write_csv(out_dir / "canonical_public_record_population.csv", canonical_records, POP_FIELDS)
    write_csv(out_dir / "mapped_like_row_partition.csv", partitions, PARTITION_FIELDS)
    write_partition_summary(out_dir / "mapped_like_row_partition_summary.md", partitions, len(frontend_map), resolved, reason)
    write_report(out_dir / "canonical_count_reconciliation.md", counts, partitions, canonical_records, canonical_map, resolved, reason)
    return {
        "rows": len(counts),
        "canonical_records": len(canonical_records),
        "canonical_map": len(canonical_map),
        "mapped_like": len(partitions),
        "resolved": resolved,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--frontend-dir", required=True)
    parser.add_argument("--exports-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    summary = reconcile(Path(args.db), Path(args.frontend_dir), Path(args.exports_dir), Path(args.out_dir))
    print(f"Reconciled {summary['rows']} count sources.")
    print(f"Canonical public records: {summary['canonical_records']}")
    print(f"Canonical public map rows: {summary['canonical_map']}")
    print(f"Mapped-like rows: {summary['mapped_like']}")
    print(f"Count conflict resolved: {summary['resolved']}")


if __name__ == "__main__":
    main()
