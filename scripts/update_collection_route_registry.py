#!/usr/bin/env python3
"""Render and maintain the collection route registry.

The registry is deliberately file-based so a collector can consult it before
probing a route, and a human reviewer can see exactly why a route is blocked,
paused, or productive.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "collection_routes.yml"
DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "v2" / "collection_route_registry.csv"
DEFAULT_MD = PROJECT_ROOT / "data" / "processed" / "v2" / "collection_route_registry.md"

ROUTE_FIELDS = [
    "route_id",
    "source_name",
    "organisation",
    "domain",
    "jurisdiction",
    "source_class",
    "retrieval_method",
    "endpoint_or_seed_url",
    "authentication_required",
    "credentials_available",
    "robots_status",
    "terms_status",
    "publicness_status",
    "first_attempted_at",
    "last_attempted_at",
    "attempt_count",
    "candidates_seen",
    "accepted_count",
    "duplicate_count",
    "lead_count",
    "rejected_count",
    "acceptance_rate",
    "average_seconds_per_candidate",
    "blocker",
    "failure_reason",
    "retry_condition",
    "next_action",
    "route_status",
]

BLOCKED_STATUSES = {
    "exhausted",
    "blocked_auth",
    "blocked_robots",
    "blocked_access_control",
    "manual_only",
    "rejected_source",
}

VALID_ROUTE_STATUSES = {
    "untested",
    "probe_ready",
    "productive",
    "low_yield",
    "exhausted",
    "blocked_auth",
    "blocked_robots",
    "blocked_access_control",
    "manual_only",
    "discovery_only",
    "rejected_source",
    "paused",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_routes(path: Path) -> tuple[str, list[dict[str, Any]]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schema_version = str(raw.get("schema_version") or "collection-routes/v1")
    routes = raw.get("routes") or []
    if not isinstance(routes, list):
        raise SystemExit("collection_routes.yml must contain a list under `routes`.")
    seen: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for route in routes:
        if not isinstance(route, dict):
            raise SystemExit("Every route entry must be a mapping.")
        route_id = str(route.get("route_id") or "").strip()
        if not route_id:
            raise SystemExit("Every route must have route_id.")
        if route_id in seen:
            raise SystemExit(f"Duplicate route_id in registry: {route_id}")
        seen.add(route_id)
        status = str(route.get("route_status") or "untested")
        if status not in VALID_ROUTE_STATUSES:
            raise SystemExit(f"{route_id}: invalid route_status `{status}`")
        row = {field: route.get(field, "") for field in ROUTE_FIELDS}
        row["route_id"] = route_id
        row["route_status"] = status
        row["acceptance_rate"] = acceptance_rate(row)
        normalized.append(row)
    return schema_version, normalized


def acceptance_rate(row: dict[str, Any]) -> str:
    try:
        seen = int(row.get("candidates_seen") or 0)
        accepted = int(row.get("accepted_count") or 0)
    except (TypeError, ValueError):
        return ""
    if seen <= 0:
        return ""
    return f"{accepted / seen:.4f}"


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROUTE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in ROUTE_FIELDS})


def write_markdown(path: Path, schema_version: str, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    status_counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("route_status") or "untested")
        status_counts[status] = status_counts.get(status, 0) + 1
    lines = [
        "# Collection Route Registry",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Schema version: `{schema_version}`",
        f"- Routes: `{len(rows)}`",
        "",
        "## Status Counts",
    ]
    for status in sorted(status_counts):
        lines.append(f"- `{status}`: {status_counts[status]}")
    lines.extend(
        [
            "",
            "## Stop Rule",
            "",
            "Collectors must not retry routes marked `exhausted`, `blocked_auth`, `blocked_robots`, `blocked_access_control`, `manual_only`, or `rejected_source` unless the route's explicit retry condition has changed.",
            "",
            "## Routes",
            "",
            "| route_id | status | organisation | method | seen | accepted | duplicates | rejected | blocker | next_action |",
            "|---|---:|---|---|---:|---:|---:|---:|---|---|",
        ]
    )
    for row in rows:
        clean = {field: "" if row.get(field) is None else str(row.get(field)).replace("|", "/") for field in ROUTE_FIELDS}
        lines.append(
            "| {route_id} | {route_status} | {organisation} | {retrieval_method} | {candidates_seen} | {accepted_count} | {duplicate_count} | {rejected_count} | {blocker} | {next_action} |".format(
                **clean
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def registry_by_id(path: Path = DEFAULT_CSV) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {row["route_id"]: row for row in csv.DictReader(handle) if row.get("route_id")}


def route_allows_probe(route: dict[str, str]) -> tuple[bool, str]:
    status = route.get("route_status") or "untested"
    if status not in BLOCKED_STATUSES:
        return True, ""
    retry_condition = route.get("retry_condition") or "retry condition not specified"
    return False, f"Route `{route.get('route_id')}` is `{status}`. Retry only when: {retry_condition}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Route registry YAML")
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="CSV output")
    parser.add_argument("--markdown", default=str(DEFAULT_MD), help="Markdown output")
    parser.add_argument("--check-route", help="Exit non-zero if route is blocked by registry policy")
    args = parser.parse_args()

    schema_version, rows = load_routes(Path(args.config))
    write_csv(Path(args.csv), rows)
    write_markdown(Path(args.markdown), schema_version, rows)

    if args.check_route:
        route = {row["route_id"]: row for row in rows}.get(args.check_route)
        if route is None:
            raise SystemExit(f"Unknown route_id: {args.check_route}")
        allowed, reason = route_allows_probe({field: str(route.get(field, "") or "") for field in ROUTE_FIELDS})
        if not allowed:
            raise SystemExit(reason)

    print(f"Wrote route registry: {args.csv}")
    print(f"Wrote route report: {args.markdown}")


if __name__ == "__main__":
    main()
