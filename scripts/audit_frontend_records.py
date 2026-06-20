#!/usr/bin/env python3
"""Audit frontend record-card readiness and map display coverage."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "frontend_record_card_sample_audit.md"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def deterministic_sample(records: list[dict[str, Any]], size: int) -> list[dict[str, Any]]:
    if len(records) <= size:
        return records
    if size <= 1:
        return records[:size]
    step = (len(records) - 1) / (size - 1)
    return [records[round(index * step)] for index in range(size)]


def has_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def body_text(record: dict[str, Any]) -> str:
    return (
        record.get("snippet")
        or record.get("coding_notes")
        or record.get("location_summary")
        or "Public record with insufficient excerpt in the frontend export."
    )


def card_issues(record: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not isinstance(record.get("record_id"), int):
        issues.append("missing_record_id")
    if not has_text(record.get("title")) and not has_text(record.get("canonical_figure_guess")) and not has_text(record.get("canonical_figure")):
        issues.append("missing_title_or_label")
    if record.get("year") is None and not has_text(record.get("date_published")):
        issues.append("missing_date_signal")
    if not has_text(record.get("source_name")) and not has_text(record.get("source_type")):
        issues.append("missing_source_signal")
    if not has_text(record.get("publicness_level")) and not has_text(record.get("publicness_code")):
        issues.append("missing_publicness_signal")
    if not has_text(body_text(record)):
        issues.append("missing_body_text")
    if record.get("publicness_level") == "restricted_excluded" or record.get("publicness_code") == "restricted_excluded":
        issues.append("restricted_record_in_frontend")
    return issues


def map_coverage(data: dict[str, Any], records: list[dict[str, Any]]) -> dict[int, str]:
    coverage: dict[int, str] = {}
    for point in data.get("map_points", []):
        record_id = point.get("record_id")
        if isinstance(record_id, int):
            coverage[record_id] = "precise_point"

    state_clusters = {
        cluster.get("state_territory")
        for cluster in data.get("map_clusters", [])
        if cluster.get("record_count", 0) > 0
    }
    for location in data.get("locations", []):
        record_id = location.get("record_id")
        state = location.get("state_territory")
        if isinstance(record_id, int) and record_id not in coverage and state in state_clusters:
            coverage[record_id] = "state_cluster"

    for record in records:
        record_id = record.get("record_id")
        if isinstance(record_id, int):
            coverage.setdefault(record_id, "not_mapped")
    return coverage


def write_report(data: dict[str, Any], sample_size: int, output: Path) -> Path:
    records = data.get("records", [])
    if not isinstance(records, list):
        raise TypeError("frontend data records field must be a list")

    sample = deterministic_sample(records, sample_size)
    coverage = map_coverage(data, records)
    issue_counts: Counter[str] = Counter()
    map_counts: Counter[str] = Counter()
    sample_rows: list[tuple[dict[str, Any], list[str], str]] = []

    for record in sample:
        issues = card_issues(record)
        issue_counts.update(issues or ["ok"])
        map_status = coverage.get(record.get("record_id"), "not_mapped")
        map_counts[map_status] += 1
        sample_rows.append((record, issues, map_status))

    all_map_counts = Counter(coverage.values())
    summary = data.get("summary", {})
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    lines = [
        "# Frontend Record Card Sample Audit",
        "",
        f"- Generated at: `{generated_at}`",
        f"- Frontend schema: `{data.get('schema_version', 'unknown')}`",
        f"- Total records: `{len(records)}`",
        f"- Sample size: `{len(sample)}`",
        f"- Precise map points: `{summary.get('precise_point_count', 0)}`",
        f"- State/territory map clusters: `{summary.get('map_cluster_count', 0)}`",
        "",
        "## Sample Card Readiness",
        "",
    ]
    for key, value in sorted(issue_counts.items()):
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Whole-Corpus Map Display Coverage", ""])
    for key, value in sorted(all_map_counts.items()):
        lines.append(f"- {key}: `{value}`")

    lines.extend(["", "## Sample Rows", "", "| record_id | year | title/label | source | map_status | issues |", "| --- | --- | --- | --- | --- | --- |"])
    for record, issues, map_status in sample_rows:
        title = record.get("title") or record.get("canonical_figure_guess") or record.get("canonical_figure") or ""
        title = str(title).replace("|", "/")[:80]
        source = record.get("source_name") or record.get("source_type") or ""
        source = str(source).replace("|", "/")[:42]
        issue_text = ", ".join(issues) if issues else "ok"
        lines.append(
            f"| {record.get('record_id')} | {record.get('year') or ''} | {title} | {source} | {map_status} | {issue_text} |"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA), help="Path to public frontend-data.json")
    parser.add_argument("--output", default=str(DEFAULT_REPORT), help="Markdown report output path")
    parser.add_argument("--sample-size", type=int, default=50, help="Deterministic sample size")
    args = parser.parse_args()

    data = load_json(Path(args.data))
    report = write_report(data, args.sample_size, Path(args.output))
    print(f"Wrote frontend record-card audit to: {report}")


if __name__ == "__main__":
    main()
