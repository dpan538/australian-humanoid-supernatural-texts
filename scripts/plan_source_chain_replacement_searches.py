#!/usr/bin/env python3
"""Create stronger-evidence search tasks for weak source-chain rows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, write_csv, now_iso
from audit_frontend_source_concentration import source_family


FIELDS = [
    "task_id",
    "record_id",
    "title",
    "date_published",
    "current_source_name",
    "current_source_url",
    "source_chain_bucket",
    "priority_reason",
    "target_state",
    "target_locality",
    "suggested_route_ids_json",
    "suggested_queries_json",
    "collection_mode",
    "reviewer_notes",
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def year(value: Any) -> int | None:
    raw = str(value or "")
    return int(raw[:4]) if len(raw) >= 4 and raw[:4].isdigit() else None


def slug_terms(url: str) -> list[str]:
    tail = str(url or "").rstrip("/").split("/")[-1]
    words = [word for word in re.split(r"[-_+%20]+", tail) if len(word) > 2 and not word.isdigit()]
    return words[:5]


def route_ids(registry: list[dict[str, Any]], state: str, date_year: int | None) -> list[str]:
    preferred = []
    for route in registry:
        family = str(route.get("route_family") or "")
        source_id = str(route.get("source_id") or "")
        if route.get("evidence_or_discovery") == "manual_only_sensitive":
            continue
        if date_year and date_year < 1955 and source_id == "trove_newspapers_gazettes":
            preferred.append(source_id)
        if source_id == "nla_catalogue":
            preferred.append(source_id)
        if state in (route.get("states") or []) and family in {"state_library_catalogue", "state_archive_catalogue", "local_history_serial", "council_local_studies", "museum_heritage_page", "heritage_register"}:
            preferred.append(source_id)
        if date_year and date_year >= 1955 and family == "broadcast_catalogue":
            preferred.append(source_id)
    return list(dict.fromkeys(preferred))[:5]


def query_strings(row: dict[str, Any], map_row: dict[str, Any]) -> list[str]:
    parts = [
        str(map_row.get("title") or row.get("existing_source_name") or ""),
        str(map_row.get("year") or ""),
        str(map_row.get("source_stated_place_text") or ""),
        *slug_terms(str(row.get("existing_source_url") or "")),
    ]
    base = " ".join(part for part in parts if part).strip()
    queries = [base] if base else []
    title = str(map_row.get("title") or "")
    locality = str(map_row.get("source_stated_place_text") or "")
    if title and locality:
        queries.append(f'"{title}" "{locality}"')
    if locality:
        queries.append(f'"{locality}" ghost OR yowie')
    return list(dict.fromkeys(queries))[:5]


def make_task(row: dict[str, Any], map_by_record: dict[str, dict[str, Any]], registry: list[dict[str, Any]]) -> dict[str, Any] | None:
    bucket = row.get("machine_bucket")
    if bucket not in {"RED_DISCOVERY_ONLY_LEAKAGE", "AMBER_UNKNOWN_SOURCE"}:
        return None
    record_id = str(row.get("record_id") or "")
    map_row = map_by_record.get(record_id, {})
    date_year = year(map_row.get("year"))
    state = str(map_row.get("state") or "")
    current_source = row.get("existing_source_name") or ""
    family = source_family(current_source)
    routes = route_ids(registry, state, date_year)
    if not routes:
        routes = ["nla_catalogue"]
    priority = []
    if map_row:
        priority.append("frontend_public_map_row")
    if date_year and 1926 <= date_year <= 1976:
        priority.append("1926_1976")
    if family == "AYR_FAMILY" or bucket == "RED_DISCOVERY_ONLY_LEAKAGE":
        priority.append("discovery_only_or_ayr_family")
    mode = "automated_metadata_possible" if any(route == "trove_newspapers_gazettes" for route in routes) else "semi_automated_catalogue_search"
    if bucket == "AMBER_UNKNOWN_SOURCE":
        mode = "semi_automated_catalogue_search"
    task_raw = "|".join([record_id, bucket or "", str(row.get("existing_source_url") or "")])
    return {
        "task_id": "replace_" + hashlib.sha256(task_raw.encode("utf-8")).hexdigest()[:16],
        "record_id": record_id,
        "title": map_row.get("title") or "",
        "date_published": map_row.get("year") or "",
        "current_source_name": current_source,
        "current_source_url": row.get("existing_source_url") or "",
        "source_chain_bucket": bucket,
        "priority_reason": ";".join(priority) or "source_chain_review",
        "target_state": state,
        "target_locality": map_row.get("source_stated_place_text") or "",
        "suggested_route_ids_json": json.dumps(routes),
        "suggested_queries_json": json.dumps(query_strings(row, map_row)),
        "collection_mode": mode,
        "reviewer_notes": "",
    }


def plan_tasks(source_scores: Path, registry_path: Path, canonical_map: Path, out_path: Path, report_path: Path, max_tasks: int) -> list[dict[str, Any]]:
    source_rows = read_rows(source_scores)
    registry = load_registry(registry_path)
    map_rows = read_rows(canonical_map)
    map_by_record = {str(row.get("record_id")): row for row in map_rows if row.get("record_id")}
    tasks = [task for row in source_rows if (task := make_task(row, map_by_record, registry))]
    tasks.sort(
        key=lambda row: (
            "frontend_public_map_row" not in row["priority_reason"],
            "1926_1976" not in row["priority_reason"],
            "discovery_only_or_ayr_family" not in row["priority_reason"],
            row["record_id"],
        )
    )
    unknown_reserve = min(max_tasks // 5, 100)
    selected: list[dict[str, Any]] = []
    for task in tasks:
        if len(selected) >= max_tasks - unknown_reserve:
            break
        if task["source_chain_bucket"] != "AMBER_UNKNOWN_SOURCE":
            selected.append(task)
    for task in tasks:
        if len(selected) >= max_tasks:
            break
        if task["source_chain_bucket"] == "AMBER_UNKNOWN_SOURCE" and task not in selected:
            selected.append(task)
    for task in tasks:
        if len(selected) >= max_tasks:
            break
        if task not in selected:
            selected.append(task)
    tasks = selected[:max_tasks]
    write_csv(out_path, tasks, FIELDS)
    write_report(report_path, tasks)
    return tasks


def write_report(path: Path, tasks: list[dict[str, Any]]) -> None:
    routes = Counter(route for task in tasks for route in json.loads(task.get("suggested_route_ids_json") or "[]"))
    frontend = sum(1 for task in tasks if "frontend_public_map_row" in task.get("priority_reason", ""))
    gap = sum(1 for task in tasks if "1926_1976" in task.get("priority_reason", ""))
    ayr = sum(1 for task in tasks if "discovery_only_or_ayr_family" in task.get("priority_reason", ""))
    unknown = sum(1 for task in tasks if task.get("source_chain_bucket") == "AMBER_UNKNOWN_SOURCE")
    lines = [
        "# Source Chain Replacement Search Tasks",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total tasks created: `{len(tasks)}`",
        f"- Tasks for frontend public map rows: `{frontend}`",
        f"- Tasks for 1926-1976 rows: `{gap}`",
        f"- AYR-family/discovery-only replacement tasks: `{ayr}`",
        f"- Unknown-source registry tasks: `{unknown}`",
        "",
        "## Top Suggested Routes",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in routes.most_common(20)] or ["- None"])
    lines.extend(["", "## Next Recommended Batch", "- Review the top 100 frontend-public/1926-1976 replacement tasks first."])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-chain-scores", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--canonical-map", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-tasks", type=int, default=500)
    args = parser.parse_args()
    tasks = plan_tasks(Path(args.source_chain_scores), Path(args.registry), Path(args.canonical_map), Path(args.out), Path(args.report), args.max_tasks)
    print(f"Wrote replacement search tasks: {len(tasks)}")


if __name__ == "__main__":
    main()
