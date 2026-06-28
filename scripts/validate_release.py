#!/usr/bin/env python3
"""Validate the public release export without collecting new data."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND_JSON = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_JSON_REPORT = ROOT / "data" / "processed" / "v2" / "release_validation_report.json"
DEFAULT_MD_REPORT = ROOT / "data" / "processed" / "v2" / "release_validation_report.md"

RESTRICTED_TOKENS = ("restricted", "suppressed", "rejected")
INTERNAL_FIELD_TOKENS = ("raw_", "candidate_id", "run_id", "collection_run", "crawler", "snapshot_sha")


def load_frontend_json(path: Path) -> tuple[dict[str, Any] | None, list[dict[str, Any]], list[dict[str, Any]]]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not path.exists():
        errors.append({"check": "frontend_json_present", "message": f"Missing {path}"})
        return None, errors, warnings
    try:
        return json.loads(path.read_text(encoding="utf-8")), errors, warnings
    except json.JSONDecodeError as exc:
        errors.append({"check": "frontend_json_parseable", "message": str(exc)})
        return None, errors, warnings


def add_issue(issues: list[dict[str, Any]], check: str, message: str, sample: Any = None) -> None:
    item: dict[str, Any] = {"check": check, "message": message}
    if sample is not None:
        item["sample"] = sample
    issues.append(item)


def duplicate_values(values: list[Any]) -> list[Any]:
    counts = Counter(values)
    return [value for value, count in counts.items() if count > 1]


def validate(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    records = data.get("records")
    map_points = data.get("map_points")
    map_flags = data.get("map_flags")
    summary = data.get("summary")
    date_bands = data.get("date_bands")
    sources = data.get("sources")

    if not isinstance(records, list):
        add_issue(errors, "records_array_present", "frontend data has no records array")
        records = []
    if not isinstance(map_points, list):
        add_issue(errors, "map_points_array_present", "frontend data has no map_points array")
        map_points = []
    if not isinstance(map_flags, list):
        add_issue(errors, "map_flags_array_present", "frontend data has no map_flags array")
        map_flags = []
    if not isinstance(summary, dict):
        add_issue(errors, "summary_present", "frontend data has no summary object")
        summary = {}
    if not isinstance(date_bands, list):
        add_issue(warnings, "date_bands_present", "frontend data has no date_bands array")
        date_bands = []
    if not isinstance(sources, list):
        add_issue(warnings, "sources_present", "frontend data has no sources array")
        sources = []

    record_ids = [row.get("record_id") for row in records]
    duplicate_record_ids = duplicate_values(record_ids)
    if duplicate_record_ids:
        add_issue(errors, "public_records_unique_by_record_id", "Duplicate public record IDs", duplicate_record_ids[:20])

    public_record_ids = set(record_ids)
    flag_record_ids = [row.get("record_id") for row in map_flags]
    duplicate_flag_record_ids = duplicate_values(flag_record_ids)
    if duplicate_flag_record_ids:
        add_issue(errors, "map_flags_unique_by_record_id", "Duplicate map flag record IDs", duplicate_flag_record_ids[:20])

    point_record_ids = [row.get("record_id") for row in map_points]
    duplicate_point_record_ids = duplicate_values(point_record_ids)
    if duplicate_point_record_ids:
        add_issue(errors, "map_points_unique_by_record_id", "Duplicate map point record IDs", duplicate_point_record_ids[:20])

    missing_records = [record_id for record_id in flag_record_ids if record_id not in public_record_ids]
    if missing_records:
        add_issue(errors, "every_map_flag_references_public_record", "Map flags reference records absent from public records", missing_records[:20])

    mapped_record_count = summary.get("mapped_record_count")
    if mapped_record_count != len(map_points) or mapped_record_count != len(map_flags):
        add_issue(
            errors,
            "map_flag_count_equals_mapped_record_count",
            "mapped_record_count, map_points length, and map_flags length differ",
            {
                "mapped_record_count": mapped_record_count,
                "map_points_length": len(map_points),
                "map_flags_length": len(map_flags),
            },
        )

    restricted_records = []
    for row in records:
        status_text = " ".join(
            str(row.get(key) or "")
            for key in ("publicness_level", "publicness_code", "relevance_code", "ethics_flag", "ingestion_status")
        ).lower()
        if any(token in status_text for token in RESTRICTED_TOKENS):
            restricted_records.append(row.get("record_id"))
    if restricted_records:
        add_issue(errors, "no_suppressed_rejected_restricted_records", "Restricted/suppressed/rejected records appear in public export", restricted_records[:20])

    missing_title = [row.get("record_id") for row in records if not str(row.get("title") or "").strip()]
    if missing_title:
        add_issue(errors, "every_public_record_has_title", "Public records missing title", missing_title[:20])

    missing_source = [
        row.get("record_id")
        for row in records
        if not (str(row.get("source_name") or "").strip() or str(row.get("source_organisation") or "").strip())
    ]
    if missing_source:
        add_issue(errors, "every_public_record_has_source_name", "Public records missing source name/organisation", missing_source[:20])

    missing_narrative_or_source_type = [
        row.get("record_id")
        for row in records
        if not any(row.get(key) for key in ("ontology_code", "genre", "canonical_figure_guess", "canonical_figure", "source_type"))
    ]
    if missing_narrative_or_source_type:
        add_issue(
            warnings,
            "every_public_record_has_narrative_or_source_type",
            "Public records missing available narrative/source type fields",
            missing_narrative_or_source_type[:20],
        )

    missing_url_or_identifier = [
        row.get("record_id")
        for row in records
        if not (str(row.get("url") or "").strip() or str(row.get("external_id") or "").strip())
    ]
    if missing_url_or_identifier:
        add_issue(warnings, "every_public_record_has_url_or_identifier", "Public records missing URL or stable identifier", missing_url_or_identifier[:20])

    public_field_leaks = []
    for row in records:
        keys = [key for key in row if any(token in key.lower() for token in INTERNAL_FIELD_TOKENS)]
        if keys:
            public_field_leaks.append({"record_id": row.get("record_id"), "fields": keys})
    if public_field_leaks:
        add_issue(errors, "no_raw_internal_fields_in_public_records", "Internal raw/candidate/run fields appear in public records", public_field_leaks[:20])

    if summary.get("record_count") != len(records):
        add_issue(errors, "summary_record_count_reconciles", "summary.record_count does not match records length", {"summary": summary.get("record_count"), "actual": len(records)})

    band_total = sum(int(row.get("record_count") or 0) for row in date_bands if isinstance(row, dict))
    if date_bands and band_total != len(records):
        add_issue(errors, "date_band_totals_reconcile", "date band totals do not match records length", {"date_band_total": band_total, "records": len(records)})

    source_rollup = summary.get("source_rollup")
    if isinstance(source_rollup, dict):
        source_rollup_total = sum(int(row.get("record_count") or 0) for row in source_rollup.values() if isinstance(row, dict))
        if source_rollup_total != len(records):
            add_issue(errors, "source_rollups_reconcile", "source rollup totals do not match records length", {"source_rollup_total": source_rollup_total, "records": len(records)})
    else:
        add_issue(warnings, "source_rollups_reconcile", "summary.source_rollup is missing, so source rollup reconciliation is not possible")

    mapped_state_counts = summary.get("mapped_state_counts")
    if isinstance(mapped_state_counts, dict):
        mapped_state_total = sum(int(value or 0) for value in mapped_state_counts.values())
        if mapped_state_total != len(map_flags):
            add_issue(errors, "map_state_counts_reconcile", "mapped state counts do not match map flag count", {"mapped_state_total": mapped_state_total, "map_flags": len(map_flags)})
    else:
        add_issue(warnings, "map_state_counts_reconcile", "summary.mapped_state_counts is missing")

    source_org_ids = {row.get("source_id") for row in sources if isinstance(row, dict)}
    record_source_ids = {row.get("source_id") for row in records if row.get("source_id") is not None}
    missing_source_rows = sorted(record_source_ids - source_org_ids)
    if missing_source_rows:
        add_issue(errors, "source_page_source_totals_reconcile", "Records reference sources absent from sources array", missing_source_rows[:20])

    unsupported_checks = [
        "source page UI aggregate totals require frontend runtime execution; static source IDs and source rollups were reconciled instead.",
        "stable identifier requirements vary by source family; this validator checks URL or external_id where present in the public export.",
    ]
    for note in unsupported_checks:
        add_issue(warnings, "warning_only_scope", note)

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "metrics": {
            "public_record_count": len(records),
            "mapped_record_count": summary.get("mapped_record_count"),
            "map_points_length": len(map_points),
            "map_flags_length": len(map_flags),
            "source_count": len(sources),
            "date_band_total": band_total,
        },
    }


def write_reports(result: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Release Validation Report",
        "",
        f"- Result: `{result['status'].upper()}`",
        f"- Public records: `{result['metrics']['public_record_count']}`",
        f"- Mapped records: `{result['metrics']['mapped_record_count']}`",
        f"- Map points: `{result['metrics']['map_points_length']}`",
        f"- Map flags: `{result['metrics']['map_flags_length']}`",
        "",
        "## Errors",
    ]
    if result["errors"]:
        for item in result["errors"]:
            lines.append(f"- FAIL `{item['check']}`: {item['message']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Warnings"])
    if result["warnings"]:
        for item in result["warnings"]:
            lines.append(f"- WARN `{item['check']}`: {item['message']}")
    else:
        lines.append("- None.")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-json", default=str(DEFAULT_FRONTEND_JSON))
    parser.add_argument("--json-report", default=str(DEFAULT_JSON_REPORT))
    parser.add_argument("--markdown-report", default=str(DEFAULT_MD_REPORT))
    args = parser.parse_args()

    data, load_errors, load_warnings = load_frontend_json(Path(args.frontend_json))
    if data is None:
        result = {"status": "fail", "errors": load_errors, "warnings": load_warnings, "metrics": {}}
    else:
        result = validate(data)
        result["errors"] = load_errors + result["errors"]
        result["warnings"] = load_warnings + result["warnings"]
        result["status"] = "pass" if not result["errors"] else "fail"

    write_reports(result, Path(args.json_report), Path(args.markdown_report))
    print(json.dumps({"status": result["status"], "errors": len(result["errors"]), "warnings": len(result["warnings"])}, indent=2))
    if result["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
