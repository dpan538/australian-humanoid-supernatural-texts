#!/usr/bin/env python3
"""Convert strict-mode failures and near misses into target-gap leads."""

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

from collection_expansion_common import now_iso, table_exists
from lib.target_gap_leads import LEAD_FIELDS, load_config, make_lead, output_path, temporal_signal, term_signal, upsert_lead
from migrate_target_gap_leads_v1 import migrate


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def robots_by_near_miss() -> dict[str, dict[str, str]]:
    path = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints" / "robots_block_audit" / "robots_block_audit.csv"
    return {row.get("near_miss_id") or "": row for row in read_csv(path)}


def fetch_dicts(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def structured_near_miss_leads(conn: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "structured_endpoint_near_misses"):
        return []
    robots = robots_by_near_miss()
    rows = fetch_dicts(
        conn,
        """
        SELECT n.*, i.state, i.route_id, i.route_family, i.endpoint_url, i.domain, r.subject_terms, r.format_text, r.rights_text
        FROM structured_endpoint_near_misses n
        LEFT JOIN noauth_endpoint_inventory i ON i.endpoint_id=n.endpoint_id
        LEFT JOIN noauth_endpoint_records r ON r.endpoint_record_id=n.endpoint_record_id
        """,
    )
    leads: list[dict[str, Any]] = []
    for row in rows:
        diag = robots.get(row.get("near_miss_id") or "", {})
        row = {**row, "robots_status": diag.get("robots_status") or "", "url_issue": diag.get("url_issue") or ""}
        near_type = str(row.get("near_miss_type") or "")
        if row.get("robots_status") or row.get("url_issue") in {"DETAIL_URL_ARCHIVED_OR_ACCESS_PLATFORM"}:
            lead_type = "ROBOTS_BLOCKED_NEAR_MISS"
        elif near_type == "TERM_NO_DATE":
            lead_type = "TERM_NO_DATE_LEAD"
        elif near_type == "DATE_NO_TERM":
            lead_type = "DATE_NO_TERM_LEAD"
        elif near_type == "D_CLASS_NEEDS_ORIGINAL":
            lead_type = "ACCESS_PLATFORM_DECOMPOSITION_LEAD"
        else:
            lead_type = "ITEM_DETAIL_REQUIRED_LEAD"
        gaps = []
        if "UNKNOWN" in str(row.get("robots_status")):
            gaps.append("robots_unknown")
        if "DENIED" in str(row.get("robots_status")):
            gaps.append("robots_denied")
        if row.get("url_issue") == "DETAIL_URL_ARCHIVED_OR_ACCESS_PLATFORM":
            gaps.append("detail_fetch_unavailable")
        if near_type == "AtoM_DETAIL_REQUIRED" and "Skip to" in str(row.get("title") or ""):
            gaps.append("field_mapping_sparse")
        if near_type in {"AtoM_DETAIL_REQUIRED", "RSS_ITEM_DETAIL_REQUIRED"}:
            gaps.append("detail_fetch_unavailable")
        term = term_signal(row, config)
        temporal, year = temporal_signal(row)
        if not term:
            gaps.append("missing_term")
        if not temporal:
            gaps.append("missing_date")
        lead = make_lead(
            "structured_endpoint_near_misses",
            row.get("near_miss_id") or "",
            lead_type,
            row,
            config,
            evidence_gap=";".join(dict.fromkeys(gaps)) or None,
            robots_status=row.get("robots_status"),
            inferred_year=year,
            temporal_signal=temporal,
            term_signal=term,
        )
        leads.append(lead)
    return leads


def harvest_candidate_leads(conn: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "harvest_candidates"):
        return []
    rows = fetch_dicts(
        conn,
        """
        SELECT *
        FROM harvest_candidates
        WHERE COALESCE(target_gap_candidate, 0)=0
           OR gate_status IN ('candidate_hold','auxiliary_accepted','high_quality_near_miss','candidate')
        """,
    )
    leads: list[dict[str, Any]] = []
    for row in rows:
        term = term_signal(row, config)
        temporal, year = temporal_signal(row)
        ethics = str(row.get("ethics_status") or "")
        reasons = " ".join(str(item) for item in row.values()).lower()
        if ethics in {"sensitive", "restricted", "manual_only"}:
            lead_type = "MANUAL_SENSITIVE_HOLD"
        elif row.get("source_tier") == "D" or "d_class" in reasons:
            lead_type = "ACCESS_PLATFORM_DECOMPOSITION_LEAD"
        elif "discovery_only" in reasons:
            lead_type = "DISCOVERY_ONLY_REPLACEMENT_LEAD"
        elif "pdf" in reasons or "newsletter" in reasons:
            lead_type = "PDF_NEWSLETTER_ROUTE_LEAD"
        elif temporal and not term:
            lead_type = "DATE_NO_TERM_LEAD"
        elif term and not temporal:
            lead_type = "TERM_NO_DATE_LEAD"
        elif year and 1955 <= year <= 1976:
            lead_type = "METADATA_ONLY_1955_1976_LEAD"
        else:
            lead_type = "UNKNOWN_SOURCE_REGISTRY_LEAD" if not row.get("source_name") else "METADATA_ONLY_1955_1976_LEAD"
        lead = make_lead("harvest_candidates", row.get("candidate_id") or "", lead_type, row, config, temporal_signal=temporal, term_signal=term, inferred_year=year)
        leads.append(lead)
    return leads


def provisional_auxiliary_leads(conn: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "provisional_records"):
        return []
    rows = fetch_dicts(conn, "SELECT * FROM provisional_records WHERE COALESCE(target_gap_eligible,0)=0")
    leads = []
    for row in rows:
        temporal, year = temporal_signal(row)
        term = term_signal(row, config)
        lead_type = "METADATA_ONLY_1955_1976_LEAD" if year and 1955 <= year <= 1976 else "TERM_NO_DATE_LEAD" if term and not temporal else "DATE_NO_TERM_LEAD" if temporal and not term else "DISCOVERY_ONLY_REPLACEMENT_LEAD"
        leads.append(make_lead("provisional_records", row.get("provisional_record_id") or "", lead_type, row, config, temporal_signal=temporal, term_signal=term, inferred_year=year))
    return leads


def discovered_route_leads(conn: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "harvest_discovered_routes"):
        return []
    rows = fetch_dicts(conn, "SELECT * FROM harvest_discovered_routes")
    leads = []
    for row in rows:
        lead_type = "SEARCH_FORM_ROUTE_LEAD" if "search" in str(row.get("reason_discovered") or row.get("candidate_url") or "").lower() else "SOURCE_ATLAS_ROUTE_LEAD"
        leads.append(make_lead("harvest_discovered_routes", row.get("discovered_route_id") or "", lead_type, row, config, url=row.get("candidate_url"), source_name=row.get("candidate_source_name"), source_tier=row.get("source_tier_guess"), route_family=row.get("route_family_guess"), target_state=row.get("state_guess")))
    return leads


def structured_route_leads(conn: sqlite3.Connection, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not table_exists(conn, "noauth_endpoint_inventory"):
        return []
    rows = fetch_dicts(conn, "SELECT * FROM noauth_endpoint_inventory")
    return [make_lead("noauth_endpoint_inventory", row.get("endpoint_id") or "", "STRUCTURED_ENDPOINT_ROUTE_LEAD", row, config, url=row.get("endpoint_url"), source_family=row.get("endpoint_type")) for row in rows]


def convert(db_path: Path, config_path: Path, out: Path, execute: bool) -> dict[str, Any]:
    migrate(db_path)
    config = load_config(config_path)
    with sqlite3.connect(db_path) as conn:
        all_leads = []
        for builder in [structured_near_miss_leads, harvest_candidate_leads, provisional_auxiliary_leads, discovered_route_leads, structured_route_leads]:
            all_leads.extend(builder(conn, config))
        if execute:
            for lead in all_leads:
                upsert_lead(conn, lead)
            conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM target_gap_leads").fetchone()[0] if table_exists(conn, "target_gap_leads") else len(all_leads)
    by_type = Counter(lead["lead_type"] for lead in all_leads)
    by_blocker = Counter(lead["constraint_blocker"] for lead in all_leads)
    lead_dir = output_path(config, "lead_dir", "data/processed/v2/autoharvest/target_gap_leads")
    lead_dir.mkdir(parents=True, exist_ok=True)
    type_csv = lead_dir / "target_gap_leads_created_by_type.csv"
    with type_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["lead_type", "count"])
        writer.writeheader()
        for key, value in sorted(by_type.items()):
            writer.writerow({"lead_type": key, "count": value})
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Target-Gap Leads Created",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Leads considered this run: `{len(all_leads)}`",
        f"- Leads in DB: `{total}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## By Lead Type",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(by_type.items())] or ["- None"])
    lines.extend(["", "## By Blocker"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(by_blocker.items())] or ["- None"])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads_considered": len(all_leads), "target_gap_leads": total, "by_type": dict(by_type), "by_blocker": dict(by_blocker), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(convert(Path(args.db), Path(args.config), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
