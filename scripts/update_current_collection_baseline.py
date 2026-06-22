#!/usr/bin/env python3
"""Calculate the current collection baseline from the database and frontend JSON."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect, table_names
from aus_humanoid.utils import PROJECT_ROOT


DEFAULT_FRONTEND_JSON = PROJECT_ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_JSON_OUTPUT = PROJECT_ROOT / "data" / "processed" / "v2" / "current_collection_baseline.json"
DEFAULT_MD_OUTPUT = PROJECT_ROOT / "data" / "processed" / "v2" / "current_collection_baseline.md"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_counts(conn, query: str) -> dict[str, int]:
    rows = conn.execute(query).fetchall()
    return {str(row[0] if row[0] not in (None, "") else "unknown"): int(row[1]) for row in rows}


def scalar(conn, query: str) -> int:
    return int(conn.execute(query).fetchone()[0])


def load_frontend(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build_baseline(db_path: Path, frontend_json_path: Path) -> dict[str, Any]:
    frontend = load_frontend(frontend_json_path)
    records = frontend.get("records") or []
    map_points = frontend.get("map_points") or []
    map_flags = frontend.get("map_flags") or []
    summary = frontend.get("summary") or {}

    frontend_record_ids = [int(record["record_id"]) for record in records if record.get("record_id") is not None]
    map_flag_record_ids = [int(flag["record_id"]) for flag in map_flags if flag.get("record_id") is not None]
    map_point_record_ids = [int(point["record_id"]) for point in map_points if point.get("record_id") is not None]

    with connect(db_path) as conn:
        tables = table_names(conn)
        db: dict[str, Any] = {
            "legacy_records_total": scalar(conn, "SELECT COUNT(*) FROM records"),
            "legacy_records_public_exportable": scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM records r
                LEFT JOIN coding c ON c.record_id = r.record_id
                WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
                  AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
                """,
            ),
            "sources_total": scalar(conn, "SELECT COUNT(*) FROM sources"),
            "queries_total": scalar(conn, "SELECT COUNT(*) FROM queries"),
        }
        if "source_items" in tables:
            db["source_items_total"] = scalar(conn, "SELECT COUNT(*) FROM source_items")
            db["source_items_by_source_type"] = fetch_counts(
                conn, "SELECT COALESCE(source_type, 'unknown'), COUNT(*) FROM source_items GROUP BY 1 ORDER BY 2 DESC"
            )
            db["source_items_by_organisation"] = fetch_counts(
                conn,
                "SELECT COALESCE(publication_or_organisation, 'unknown'), COUNT(*) FROM source_items GROUP BY 1 ORDER BY 2 DESC LIMIT 40",
            )
        else:
            db["source_items_total"] = 0
            db["source_items_by_source_type"] = {}
            db["source_items_by_organisation"] = {}
        if "narrative_units" in tables:
            db["narrative_units_total"] = scalar(conn, "SELECT COUNT(*) FROM narrative_units")
            db["narrative_units_by_type"] = fetch_counts(
                conn, "SELECT COALESCE(narrative_type, secondary_role, 'unknown'), COUNT(*) FROM narrative_units GROUP BY 1 ORDER BY 2 DESC"
            )
        else:
            db["narrative_units_total"] = 0
            db["narrative_units_by_type"] = {}
        if "collection_candidates_v2" in tables:
            db["collection_candidates_total"] = scalar(conn, "SELECT COUNT(*) FROM collection_candidates_v2")
            db["collection_candidates_by_status"] = fetch_counts(
                conn, "SELECT candidate_status, COUNT(*) FROM collection_candidates_v2 GROUP BY 1 ORDER BY 1"
            )
            db["accepted_candidates_by_source_type"] = fetch_counts(
                conn,
                """
                SELECT COALESCE(source_type, 'unknown'), COUNT(*)
                FROM collection_candidates_v2
                WHERE candidate_status = 'accepted'
                GROUP BY 1
                ORDER BY 2 DESC
                """,
            )
            db["accepted_candidates_by_organisation"] = fetch_counts(
                conn,
                """
                SELECT COALESCE(publication_or_organisation, source_name, 'unknown'), COUNT(*)
                FROM collection_candidates_v2
                WHERE candidate_status = 'accepted'
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 40
                """,
            )
        else:
            db["collection_candidates_total"] = 0
            db["collection_candidates_by_status"] = {}
            db["accepted_candidates_by_source_type"] = {}
            db["accepted_candidates_by_organisation"] = {}

    record_count_by_source_type = Counter(record.get("source_type") or "unknown" for record in records)
    record_count_by_source_org = Counter(record.get("publication") or record.get("source_name") or "unknown" for record in records)
    record_count_by_narrative_type = Counter(record.get("ontology_code") or record.get("ontology_default") or "uncoded" for record in records)
    record_count_by_date_band = Counter(record.get("date_band") or "undated" for record in records)
    record_count_by_state = Counter(record.get("state_territory") or "unmapped" for record in records)
    map_flag_count_by_state = Counter(flag.get("state_territory") or "unknown" for flag in map_flags)

    invariant = {
        "mapped_record_count": len(set(map_flag_record_ids)),
        "map_flags_length": len(map_flags),
        "public_map_points_length": len(map_points),
        "unique_map_point_record_count": len(set(map_point_record_ids)),
        "summary_map_flag_count": int(summary.get("map_flag_count") or 0),
        "summary_mapped_record_count": int(summary.get("mapped_record_count") or 0),
    }
    invariant["passes"] = len(
        {
            invariant["mapped_record_count"],
            invariant["map_flags_length"],
            invariant["public_map_points_length"],
            invariant["unique_map_point_record_count"],
            invariant["summary_map_flag_count"],
            invariant["summary_mapped_record_count"],
        }
    ) == 1

    return {
        "generated_at": now_iso(),
        "db_path": str(db_path),
        "frontend_json_path": str(frontend_json_path),
        "database": db,
        "frontend": {
            "schema_version": frontend.get("schema_version"),
            "total_accepted_display_records": len(records),
            "unique_public_records": len(set(frontend_record_ids)),
            "duplicate_frontend_record_ids": len(frontend_record_ids) - len(set(frontend_record_ids)),
            "mapped_public_records": invariant["mapped_record_count"],
            "record_count_by_source_organisation": dict(record_count_by_source_org.most_common(40)),
            "record_count_by_source_type": dict(record_count_by_source_type.most_common()),
            "record_count_by_narrative_type": dict(record_count_by_narrative_type.most_common()),
            "record_count_by_state_or_territory": dict(record_count_by_state.most_common()),
            "map_flag_count_by_state_or_territory": dict(map_flag_count_by_state.most_common()),
            "record_count_by_date_band": dict(record_count_by_date_band.most_common()),
        },
        "public_map_invariant": invariant,
    }


def markdown_table(title: str, counts: dict[str, int], limit: int = 20) -> list[str]:
    lines = [f"## {title}", "", "| key | count |", "|---|---:|"]
    for key, count in list(counts.items())[:limit]:
        lines.append(f"| {key} | {count} |")
    if not counts:
        lines.append("| none | 0 |")
    lines.append("")
    return lines


def write_markdown(path: Path, data: dict[str, Any]) -> None:
    frontend = data["frontend"]
    db = data["database"]
    invariant = data["public_map_invariant"]
    lines = [
        "# Current Collection Baseline",
        "",
        f"- Generated: `{data['generated_at']}`",
        f"- SQLite database: `{data['db_path']}`",
        f"- Frontend JSON: `{data['frontend_json_path']}`",
        "",
        "## Headline Counts",
        "",
        f"- Total accepted display records: `{frontend['total_accepted_display_records']}`",
        f"- Unique public records: `{frontend['unique_public_records']}`",
        f"- Duplicate frontend record IDs: `{frontend['duplicate_frontend_record_ids']}`",
        f"- Mapped public records: `{frontend['mapped_public_records']}`",
        f"- Accepted source items: `{db.get('source_items_total', 0)}`",
        f"- Narrative units: `{db.get('narrative_units_total', 0)}`",
        f"- Collection candidates: `{db.get('collection_candidates_total', 0)}`",
        "",
        "## Public Map Invariant",
        "",
        f"- Passes: `{invariant['passes']}`",
        f"- mapped_record_count: `{invariant['mapped_record_count']}`",
        f"- map_flags length: `{invariant['map_flags_length']}`",
        f"- public_map_points length: `{invariant['public_map_points_length']}`",
        f"- summary mapped record count: `{invariant['summary_mapped_record_count']}`",
        "",
    ]
    lines.extend(markdown_table("Collection Candidates By Status", db.get("collection_candidates_by_status", {})))
    lines.extend(markdown_table("Display Records By Source Organisation", frontend["record_count_by_source_organisation"]))
    lines.extend(markdown_table("Display Records By Source Type", frontend["record_count_by_source_type"]))
    lines.extend(markdown_table("Display Records By Narrative Type", frontend["record_count_by_narrative_type"]))
    lines.extend(markdown_table("Display Records By State/Territory", frontend["record_count_by_state_or_territory"]))
    lines.extend(markdown_table("Map Flags By State/Territory", frontend["map_flag_count_by_state_or_territory"]))
    lines.extend(markdown_table("Display Records By Date Band", frontend["record_count_by_date_band"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--frontend-json", default=str(DEFAULT_FRONTEND_JSON), help="Frontend data JSON")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON_OUTPUT), help="Baseline JSON output")
    parser.add_argument("--markdown-output", default=str(DEFAULT_MD_OUTPUT), help="Baseline Markdown output")
    args = parser.parse_args()

    data = build_baseline(Path(args.db), Path(args.frontend_json))
    json_path = Path(args.json_output)
    md_path = Path(args.markdown_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, data)
    print(f"Wrote baseline JSON: {json_path}")
    print(f"Wrote baseline report: {md_path}")
    if not data["public_map_invariant"]["passes"]:
        raise SystemExit("Public map invariant failed.")


if __name__ == "__main__":
    main()
