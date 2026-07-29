#!/usr/bin/env python3
"""Sync config/source_registry.yml into collection route review tables."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import bool_int, load_registry, now_iso, table_exists


REPORT_PATH = ROOT / "data" / "processed" / "v2" / "source_registry_sync_report.md"


def upsert_route(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    ts = now_iso()
    route_id = item.get("route_id") or item["source_id"]
    conn.execute(
        """
        INSERT INTO collection_routes (
            route_id, source_id, source_name, institution, route_family,
            source_tier, evidence_or_discovery, scope, states_json,
            years_likely, access_method, base_url, search_url_template,
            allowed_content_mode, full_text_allowed, robots_check_required,
            rate_limit_seconds, temporal_gap_value, regional_balance_value,
            mappability_likelihood, duplicate_risk, ethics_risk, notes,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(route_id) DO UPDATE SET
            source_id=excluded.source_id,
            source_name=excluded.source_name,
            institution=excluded.institution,
            route_family=excluded.route_family,
            source_tier=excluded.source_tier,
            evidence_or_discovery=excluded.evidence_or_discovery,
            scope=excluded.scope,
            states_json=excluded.states_json,
            years_likely=excluded.years_likely,
            access_method=excluded.access_method,
            base_url=excluded.base_url,
            search_url_template=excluded.search_url_template,
            allowed_content_mode=excluded.allowed_content_mode,
            full_text_allowed=excluded.full_text_allowed,
            robots_check_required=excluded.robots_check_required,
            rate_limit_seconds=excluded.rate_limit_seconds,
            temporal_gap_value=excluded.temporal_gap_value,
            regional_balance_value=excluded.regional_balance_value,
            mappability_likelihood=excluded.mappability_likelihood,
            duplicate_risk=excluded.duplicate_risk,
            ethics_risk=excluded.ethics_risk,
            notes=excluded.notes,
            updated_at=excluded.updated_at
        """,
        (
            route_id,
            item["source_id"],
            item["source_name"],
            item.get("institution"),
            item.get("route_family"),
            item.get("source_tier"),
            item.get("evidence_or_discovery"),
            item.get("scope"),
            json.dumps(item.get("states", []), ensure_ascii=False),
            item.get("years_likely"),
            item.get("access_method"),
            item.get("base_url"),
            item.get("search_url_template"),
            item.get("allowed_content_mode"),
            bool_int(item.get("full_text_allowed"), default=False),
            bool_int(item.get("robots_check_required"), default=True),
            float(item.get("rate_limit_seconds", 2.0)),
            item.get("temporal_gap_value"),
            item.get("regional_balance_value"),
            item.get("mappability_likelihood"),
            item.get("duplicate_risk"),
            item.get("ethics_risk"),
            item.get("notes"),
            ts,
            ts,
        ),
    )


def upsert_source_quality_review(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    ts = now_iso()
    review_id = f"sqr_{item['source_id']}"
    conn.execute(
        """
        INSERT INTO source_quality_reviews (
            source_quality_review_id, source_id, source_name, institution,
            source_tier, evidence_or_discovery, review_status, robots_status,
            terms_status, allowed_content_mode, notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_quality_review_id) DO UPDATE SET
            source_name=excluded.source_name,
            institution=excluded.institution,
            source_tier=excluded.source_tier,
            evidence_or_discovery=excluded.evidence_or_discovery,
            robots_status=excluded.robots_status,
            terms_status=excluded.terms_status,
            allowed_content_mode=excluded.allowed_content_mode,
            notes=excluded.notes,
            updated_at=excluded.updated_at
        """,
        (
            review_id,
            item["source_id"],
            item["source_name"],
            item.get("institution"),
            item.get("source_tier"),
            item.get("evidence_or_discovery"),
            "needs_review",
            "requires_check" if item.get("robots_check_required", True) else "not_required",
            str(item.get("terms_status") or "requires_review"),
            item.get("allowed_content_mode"),
            item.get("notes"),
            ts,
            ts,
        ),
    )


def sync_registry(db_path: Path, config_path: Path, dry_run: bool = False) -> dict[str, Any]:
    registry = load_registry(config_path)
    tier_counts: dict[str, int] = {}
    mode_counts: dict[str, int] = {}
    for item in registry:
        tier_counts[item["source_tier"]] = tier_counts.get(item["source_tier"], 0) + 1
        mode_counts[item["evidence_or_discovery"]] = mode_counts.get(item["evidence_or_discovery"], 0) + 1

    if not dry_run:
        with sqlite3.connect(db_path) as conn:
            missing = [table for table in ("collection_routes", "source_quality_reviews") if not table_exists(conn, table)]
            if missing:
                raise RuntimeError(
                    "Missing migration tables: "
                    + ", ".join(missing)
                    + ". Run scripts/migrate_collection_expansion_v2.py first."
                )
            for item in registry:
                upsert_route(conn, item)
                upsert_source_quality_review(conn, item)
            conn.commit()

    return {
        "registry_count": len(registry),
        "tier_counts": tier_counts,
        "mode_counts": mode_counts,
        "dry_run": dry_run,
    }


def write_report(summary: dict[str, Any], config_path: Path, db_path: Path) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Source Registry Sync Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Config: `{config_path}`",
        f"- Database: `{db_path}`",
        f"- Dry run: `{summary['dry_run']}`",
        f"- Routes validated: `{summary['registry_count']}`",
        "",
        "## Tier Counts",
    ]
    for key in sorted(summary["tier_counts"]):
        lines.append(f"- `{key}`: {summary['tier_counts'][key]}")
    lines.append("")
    lines.append("## Evidence Mode Counts")
    for key in sorted(summary["mode_counts"]):
        lines.append(f"- `{key}`: {summary['mode_counts'][key]}")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--config", required=True, help="source_registry.yml path")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing to SQLite")
    args = parser.parse_args()

    summary = sync_registry(Path(args.db), Path(args.config), dry_run=args.dry_run)
    write_report(summary, Path(args.config), Path(args.db))
    action = "validated" if args.dry_run else "synced"
    print(f"Source registry {action}: {summary['registry_count']} routes.")
    print(f"Wrote report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
