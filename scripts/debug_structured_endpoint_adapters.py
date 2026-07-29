#!/usr/bin/env python3
"""Report parser and adapter coverage for structured endpoint records."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv, write_jsonl
from lib.structured_endpoint_recovery import has_record_term, has_target_date, safe_json
from migrate_structured_near_miss_v1 import migrate


def pct(part: int, whole: int) -> float:
    return 0.0 if whole == 0 else round(part / whole * 100.0, 2)


def recommendation(row: dict[str, Any]) -> str:
    endpoint_type = row.get("endpoint_type") or "UNKNOWN"
    records = int(row.get("records_seen") or 0)
    title_pct = float(row.get("title_mapped_pct") or 0)
    date_pct = float(row.get("date_mapped_pct") or 0)
    desc_pct = float(row.get("description_mapped_pct") or 0)
    term_pct = float(row.get("controlled_term_extraction_pct") or 0)
    near_pct = float(row.get("near_miss_rate_pct") or 0)
    if records == 0 and endpoint_type in {"WORDPRESS_REST", "OMEKA_API"}:
        return "adapter_or_query_repair_or_pause_zero_record_endpoint"
    if endpoint_type == "ATOM_AtoM" and near_pct >= 20 and (date_pct < 50 or term_pct < 50):
        return "fix_atomt_anchor_filter_and_detail_page_parser"
    if title_pct < 80 or desc_pct < 50:
        return "improve_field_mapping_for_title_description"
    if date_pct < 30:
        return "improve_temporal_field_mapping_or_detail_enrichment"
    if term_pct < 30:
        return "improve_subject_term_mapping_or_fetch_item_detail"
    return "adapter_coverage_acceptable_monitor"


def debug(db_path: Path, run_id: str, out_dir: Path) -> dict[str, Any]:
    migrate(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        records = [
            dict(row)
            for row in conn.execute(
                """
                SELECT r.*, i.route_family, i.state
                FROM noauth_endpoint_records r
                LEFT JOIN noauth_endpoint_inventory i ON i.endpoint_id=r.endpoint_id
                WHERE r.run_id=?
                """,
                (run_id,),
            ).fetchall()
        ]
        endpoints = [
            dict(row)
            for row in conn.execute(
                """
                SELECT i.endpoint_id, i.endpoint_type, i.source_name, i.source_tier, i.route_family, i.status,
                       COUNT(r.endpoint_record_id) AS records_seen
                FROM noauth_endpoint_inventory i
                LEFT JOIN noauth_endpoint_records r ON r.endpoint_id=i.endpoint_id AND r.run_id=?
                GROUP BY i.endpoint_id
                ORDER BY i.endpoint_type, i.source_name
                """,
                (run_id,),
            ).fetchall()
        ]
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    route_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        endpoint_type = record.get("endpoint_type") or "UNKNOWN"
        groups[endpoint_type].append(record)
        route_groups[(endpoint_type, record.get("source_name") or "UNKNOWN")].append(record)

    field_rows: list[dict[str, Any]] = []
    for endpoint_type, items in sorted(groups.items()):
        total = len(items)
        title = sum(1 for row in items if row.get("title"))
        date = sum(1 for row in items if row.get("date_text") or row.get("inferred_year") or row.get("coverage_start_year") or row.get("coverage_end_year"))
        desc = sum(1 for row in items if row.get("description"))
        subject = sum(1 for row in items if row.get("subject_terms"))
        url = sum(1 for row in items if row.get("item_url"))
        term = sum(1 for row in items if has_record_term(row))
        temporal = sum(1 for row in items if has_target_date(row))
        near = sum(1 for row in items if row.get("target_gap_eligible") == 0 and (has_record_term(row) or has_target_date(row)))
        targets = sum(1 for row in items if row.get("target_gap_eligible") == 1)
        row = {
            "endpoint_type": endpoint_type,
            "records_seen": total,
            "title_mapped_pct": pct(title, total),
            "date_mapped_pct": pct(date, total),
            "description_mapped_pct": pct(desc, total),
            "subject_mapped_pct": pct(subject, total),
            "url_mapped_pct": pct(url, total),
            "controlled_term_extraction_pct": pct(term, total),
            "temporal_extraction_pct": pct(temporal, total),
            "near_miss_rate_pct": pct(near, total),
            "target_rate_pct": pct(targets, total),
            "common_missing_fields": ", ".join(field for field, count in {"title": title, "date": date, "description": desc, "subject": subject, "url": url}.items() if count < total),
        }
        row["recommended_adapter_fix"] = recommendation(row)
        field_rows.append(row)

    route_rows: list[dict[str, Any]] = []
    for (endpoint_type, source_name), items in sorted(route_groups.items()):
        total = len(items)
        date = sum(1 for row in items if has_target_date(row))
        term = sum(1 for row in items if has_record_term(row))
        near = sum(1 for row in items if row.get("target_gap_eligible") == 0 and (has_record_term(row) or has_target_date(row)))
        row = {
            "endpoint_type": endpoint_type,
            "source_name": source_name,
            "records_seen": total,
            "date_mapped_pct": pct(date, total),
            "controlled_term_extraction_pct": pct(term, total),
            "near_miss_rate_pct": pct(near, total),
            "recommended_adapter_fix": "",
        }
        row["recommended_adapter_fix"] = recommendation({**row, "title_mapped_pct": 100, "description_mapped_pct": 100})
        route_rows.append(row)

    existing = {(row["endpoint_type"], row["source_name"]) for row in route_rows}
    for endpoint in endpoints:
        key = (endpoint.get("endpoint_type") or "UNKNOWN", endpoint.get("source_name") or "UNKNOWN")
        if key in existing or int(endpoint.get("records_seen") or 0) != 0:
            continue
        route_rows.append(
            {
                "endpoint_type": key[0],
                "source_name": key[1],
                "records_seen": 0,
                "date_mapped_pct": 0,
                "controlled_term_extraction_pct": 0,
                "near_miss_rate_pct": 0,
                "recommended_adapter_fix": recommendation({"endpoint_type": key[0], "records_seen": 0}),
            }
        )

    failure_rows: list[dict[str, Any]] = []
    for row in field_rows:
        failure_rows.append(
            {
                "endpoint_type": row["endpoint_type"],
                "failure_modes": "; ".join(part for part in [row["common_missing_fields"], row["recommended_adapter_fix"]] if part),
                "records_seen": row["records_seen"],
                "near_miss_rate_pct": row["near_miss_rate_pct"],
                "recommended_adapter_fix": row["recommended_adapter_fix"],
            }
        )
    zero_counts = Counter(endpoint.get("endpoint_type") or "UNKNOWN" for endpoint in endpoints if int(endpoint.get("records_seen") or 0) == 0)
    for endpoint_type, count in zero_counts.items():
        failure_rows.append(
            {
                "endpoint_type": endpoint_type,
                "failure_modes": "zero_record_endpoint",
                "records_seen": 0,
                "near_miss_rate_pct": 0,
                "recommended_adapter_fix": recommendation({"endpoint_type": endpoint_type, "records_seen": 0}),
                "endpoint_count": count,
            }
        )

    samples: list[dict[str, Any]] = []
    for record in records[:100]:
        samples.append(
            {
                "endpoint_record_id": record.get("endpoint_record_id"),
                "endpoint_type": record.get("endpoint_type"),
                "source_name": record.get("source_name"),
                "title": (record.get("title") or "")[:160],
                "date_text": record.get("date_text"),
                "inferred_year": record.get("inferred_year"),
                "item_url_host": record.get("item_url", "").split("/", 3)[:3],
                "gate_reasons": safe_json(record.get("gate_reasons_json"), []),
                "metadata_redacted": str(record.get("metadata_json") or "")[:500],
            }
        )

    write_csv(
        out_dir / "field_mapping_coverage.csv",
        field_rows,
        [
            "endpoint_type",
            "records_seen",
            "title_mapped_pct",
            "date_mapped_pct",
            "description_mapped_pct",
            "subject_mapped_pct",
            "url_mapped_pct",
            "controlled_term_extraction_pct",
            "temporal_extraction_pct",
            "near_miss_rate_pct",
            "target_rate_pct",
            "common_missing_fields",
            "recommended_adapter_fix",
        ],
    )
    write_csv(out_dir / "endpoint_type_failure_modes.csv", failure_rows, ["endpoint_type", "failure_modes", "records_seen", "near_miss_rate_pct", "recommended_adapter_fix", "endpoint_count"])
    write_csv(out_dir / "source_route_adapter_recommendations.csv", route_rows, ["endpoint_type", "source_name", "records_seen", "date_mapped_pct", "controlled_term_extraction_pct", "near_miss_rate_pct", "recommended_adapter_fix"])
    write_jsonl(out_dir / "sample_metadata_redacted.jsonl", samples)

    wa = next((row for row in route_rows if row.get("endpoint_type") == "ATOM_AtoM" and row.get("source_name") == "Western Australian Museum"), None)
    lines = [
        "# Structured Endpoint Adapter Debug Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Endpoint records inspected: `{len(records)}`",
        f"- Endpoint types inspected: `{len(field_rows)}`",
        f"- Zero-record endpoints: `{sum(zero_counts.values())}`",
        "",
        "## Endpoint Type Coverage",
    ]
    lines.extend(
        [
            f"- `{row['endpoint_type']}`: records `{row['records_seen']}`, title `{row['title_mapped_pct']}`%, date `{row['date_mapped_pct']}`%, term `{row['controlled_term_extraction_pct']}`%, recommendation `{row['recommended_adapter_fix']}`"
            for row in field_rows
        ]
        or ["- None"]
    )
    lines.extend(["", "## Special Focus"])
    if wa:
        lines.append(
            f"- ATOM_AtoM / Western Australian Museum: records `{wa['records_seen']}`, date `{wa['date_mapped_pct']}`%, term `{wa['controlled_term_extraction_pct']}`%, near `{wa['near_miss_rate_pct']}`%, recommendation `{wa['recommended_adapter_fix']}`"
        )
    else:
        lines.append("- ATOM_AtoM / Western Australian Museum: no records found in current durable record table.")
    lines.extend(["", "## Outputs", f"- `{out_dir / 'field_mapping_coverage.csv'}`", f"- `{out_dir / 'endpoint_type_failure_modes.csv'}`", f"- `{out_dir / 'source_route_adapter_recommendations.csv'}`", f"- `{out_dir / 'sample_metadata_redacted.jsonl'}`"])
    (out_dir / "adapter_debug_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"records": len(records), "endpoint_types": len(field_rows), "zero_record_endpoints": sum(zero_counts.values()), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(debug(Path(args.db), args.run_id, Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
