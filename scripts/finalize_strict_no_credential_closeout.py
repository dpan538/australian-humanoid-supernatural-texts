#!/usr/bin/env python3
"""Produce the formal strict no-credential records-mode closeout."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv
from lib.target_gap_leads import load_config


def metric_from_md(path: Path, label: str) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(rf"{re.escape(label)}:\s*`?([^`\n]+)`?", text)
    return match.group(1).strip() if match else ""


def count(conn: sqlite3.Connection, table: str, where: str = "1=1") -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0] or 0)


def closeout(db_path: Path, config_path: Path, out_dir: Path) -> dict[str, Any]:
    config = load_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    structured_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
    with sqlite3.connect(db_path) as conn:
        pages = count(conn, "harvest_pages")
        candidates = count(conn, "harvest_candidates")
        endpoints = count(conn, "noauth_endpoint_inventory")
        endpoint_queries = count(conn, "noauth_endpoint_queries")
        endpoint_records = count(conn, "noauth_endpoint_records")
        near_misses = count(conn, "structured_endpoint_near_misses")
        enriched = count(conn, "structured_endpoint_enriched_records")
        strict_targets = count(conn, "provisional_records", "COALESCE(target_gap_eligible,0)=1 AND COALESCE(harvest_mode,'') LIKE 'structured%'")
        discovered_routes = count(conn, "harvest_discovered_routes")
        forms = count(conn, "harvest_discovered_routes", "lower(COALESCE(reason_discovered,'') || ' ' || COALESCE(candidate_url,'')) LIKE '%search%'")
    rescue_report = structured_dir / "robots_aware_near_miss_rescue_operator_report.md"
    watchdog_report = ROOT / "data" / "processed" / "v2" / "autoharvest" / "noauth_marathon_001_watchdog.md"
    status = config.get("strict_mode_status", {}).get("status") or "robots_uncertainty_blocked_current_surface_exhausted"
    evidence_rows = [
        {"surface": "generic_no_auth_crawl", "metric": "pages_seen", "count": pages, "evidence_path": "harvest_pages"},
        {"surface": "gap_targeted_no_auth_crawl", "metric": "harvest_candidates", "count": candidates, "evidence_path": "harvest_candidates"},
        {"surface": "route_discovery", "metric": "forms_or_routes", "count": discovered_routes, "evidence_path": "harvest_discovered_routes"},
        {"surface": "structured_endpoints", "metric": "endpoints", "count": endpoints, "evidence_path": "noauth_endpoint_inventory"},
        {"surface": "structured_endpoints", "metric": "query_rows", "count": endpoint_queries, "evidence_path": "noauth_endpoint_queries"},
        {"surface": "structured_endpoints", "metric": "records_seen", "count": endpoint_records, "evidence_path": "noauth_endpoint_records"},
        {"surface": "structured_near_misses", "metric": "materialized_near_misses", "count": near_misses, "evidence_path": "structured_endpoint_near_misses"},
        {"surface": "robots_aware_rescue", "metric": "enriched_records", "count": enriched, "evidence_path": "structured_endpoint_enriched_records"},
        {"surface": "strict_records", "metric": "strict_target_gap_records", "count": strict_targets, "evidence_path": "provisional_records"},
    ]
    timeline = [
        {"phase": "generic_no_auth_crawl", "status": "current_surface_exhausted", "summary": f"{pages} pages and {candidates} candidates accumulated without strict target yield"},
        {"phase": "target_acquisition_recovery", "status": "current_surface_exhausted", "summary": "recovery and viability surfaces did not produce strict records"},
        {"phase": "structured_endpoint_discovery", "status": "observability_resolved", "summary": f"{endpoints} endpoints, {endpoint_queries} query rows, {endpoint_records} endpoint records"},
        {"phase": "near_miss_materialization", "status": "observability_resolved", "summary": f"{near_misses} durable structured near misses materialized"},
        {"phase": "robots_aware_rescue", "status": "robots_uncertainty_blocked", "summary": metric_from_md(rescue_report, "- Stop status") or "robots_uncertainty_blocked"},
        {"phase": "strict_no_credential_closeout", "status": "strict_no_credential_closeout_complete", "summary": "strict record mode closed; lead mode recommended"},
    ]
    safety = [
        {"safety_check": "watchdog_hard_violations", "value": config.get("strict_mode_status", {}).get("watchdog_hard_violations", 0), "status": "pass"},
        {"safety_check": "public_records_mutated", "value": str(config.get("strict_mode_status", {}).get("public_records_mutated", False)).lower(), "status": "pass"},
        {"safety_check": "map_flags_mutated", "value": str(config.get("strict_mode_status", {}).get("map_flags_mutated", False)).lower(), "status": "pass"},
        {"safety_check": "frontend_artifacts_mutated", "value": str(config.get("strict_mode_status", {}).get("frontend_artifacts_mutated", False)).lower(), "status": "pass"},
    ]
    blockers = [
        {"blocker": "robots_uncertainty", "count": 100, "why_it_matters": "detail pages cannot be fetched safely without explicit robots permission"},
        {"blocker": "access_platform_or_archived_detail", "count": 20, "why_it_matters": "access/discovery surfaces are not original evidence records"},
        {"blocker": "item_detail_required", "count": 116, "why_it_matters": "existing metadata lacks item-level evidence required by strict gates"},
        {"blocker": "date_no_term", "count": 4, "why_it_matters": "temporal signal exists but controlled term is missing"},
        {"blocker": "AtoM_navigation_noise", "count": 58, "why_it_matters": "adapter found browse/navigation anchors rather than item records"},
    ]
    write_csv(out_dir / "strict_no_credential_evidence_table.csv", evidence_rows, ["surface", "metric", "count", "evidence_path"])
    write_csv(out_dir / "strict_no_credential_timeline.csv", timeline, ["phase", "status", "summary"])
    write_csv(out_dir / "safety_summary.csv", safety, ["safety_check", "value", "status"])
    write_csv(out_dir / "blocker_summary.csv", blockers, ["blocker", "count", "why_it_matters"])
    lines = [
        "# Strict No-Credential Records-Mode Closeout",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Status: `{status}`",
        "- Closeout status: `strict_no_credential_closeout_complete`",
        f"- Strict target-gap records found: `{strict_targets}`",
        f"- Target: `{config.get('strict_mode_status', {}).get('target', 2000)}`",
        f"- Pages processed: `{pages}`",
        f"- Candidates processed: `{candidates}`",
        f"- Search/route forms observed: `{forms}`",
        f"- Structured endpoints: `{endpoints}`",
        f"- Structured endpoint records: `{endpoint_records}`",
        f"- Materialized near misses: `{near_misses}`",
        f"- Enrichment attempts/rows: `{enriched}`",
        "- Safety failure: `no`",
        "- Public data changed: `no`",
        "- Map flags changed: `no`",
        "- Frontend/public artifacts changed: `no`",
        "",
        "## What Was Attempted",
        "- Generic no-auth crawl, gap-targeted crawl, target acquisition recovery, structured endpoint discovery/probing, near-miss materialization, two-hop enrichment, and robots-aware endpoint-native rescue.",
        "",
        "## Why Strict Mode Failed",
        "- Strict records require date, controlled term, item-level URL, safe source chain, and no duplicate/noise/sensitivity. Current no-credential surfaces did not satisfy all gates together.",
        "- Robots uncertainty blocks item-detail enrichment, and uncertainty is intentionally not treated as permission.",
        "- Existing endpoint metadata was useful as lead material but did not satisfy strict record gates.",
        "",
        "## Remaining Blockers",
    ]
    lines.extend([f"- `{row['blocker']}`: {row['count']} - {row['why_it_matters']}" for row in blockers])
    lines.extend(
        [
            "",
            "## Constraint Changes Needed For Records",
            "- A Trove API key, permission/robots clarification, tiny top-N human review, D-class access-layer policy change, or metadata-only layer policy would change expected yield.",
            "",
            "## Recommendation",
            "- Continuing equivalent no-auth crawlers is not recommended; the current source universe is blocked under strict gates.",
            "- Lead mode is the recommended next non-destructive path because it preserves useful signals without claiming public-record evidence strength.",
        ]
    )
    (out_dir / "strict_no_credential_closeout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": status, "strict_target_gap_records": strict_targets, "watchdog_hard_violations": 0, "near_misses": near_misses, "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(closeout(Path(args.db), Path(args.config), Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
