#!/usr/bin/env python3
"""Recover strict target-gap candidates from high-quality near misses."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from adapters.noauth_sites.generic import matching_adapters
from collection_expansion_common import write_csv
from lib.autoharvest_engine import load_autoharvest_config
from lib.gap_recovery import candidate_from_seed, classify_and_optionally_stage, read_csv, stable_action_id, write_report
from lib.noauth_web import RouteSafety, extract_pdf_links, fetch_html_safe, same_domain
from migrate_autoharvest_gap_v2 import migrate

VIABILITY_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_acquisition_viability"
POSTMORTEM_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "zero_yield_postmortem"


def load_db_candidates(db_path: Path, run_id: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM harvest_candidates WHERE run_id=? AND gate_status='high_quality_near_miss'",
            (run_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def recovery_category(row: dict) -> str:
    reason = " ".join([row.get("target_gap_reason", ""), row.get("gate_reasons_json", ""), row.get("near_miss_category", "")]).lower()
    if "missing_explicit_target_temporal_evidence" in reason:
        return "TERM_NO_DATE"
    if "missing_controlled_term" in reason:
        return "DATE_NO_TERM"
    if ".pdf" in str(row.get("url") or "").lower() or "pdf" in reason:
        return "PDF_LINK_NOT_PROCESSED"
    if "serial" in reason or "newsletter" in reason or "journal" in reason:
        return "POSSIBLE_SERIAL_ISSUE"
    if "catalogue" in reason:
        return "POSSIBLE_CATALOGUE_RESULT"
    if "broadcast" in reason:
        return "POSSIBLE_BROADCAST_METADATA"
    return row.get("near_miss_category") or "SEARCH_FORM_NOT_USED"


def fetch_followup(url: str, route_id: str, config, session: requests.Session, execute: bool) -> tuple[str, str]:
    if not execute:
        return "", "dry_run"
    try:
        html = fetch_html_safe(
            url,
            RouteSafety(
                route_id=route_id,
                rate_limit_seconds=float(config.data.get("safety", {}).get("rate_limit_seconds_default", 3.0)),
                timeout_seconds=float(config.data.get("safety", {}).get("html_timeout_seconds", 8.0)),
            ),
            session,
        )
    except Exception:
        return "", "fetch_failed"
    return html or "", "ok" if html else "empty_or_robots"


def recover(db_path: Path, run_id: str, out_dir: Path, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = load_autoharvest_config(ROOT / "config" / "autoharvest_gap_rescue.yml")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = [row for row in read_csv(VIABILITY_DIR / "viability_candidates.csv") if row.get("gate_status") == "high_quality_near_miss"]
    rows.extend(load_db_candidates(db_path, run_id))
    if not rows:
        rows.extend(read_csv(POSTMORTEM_DIR / "near_miss_candidates.csv")[:50])
    selected = []
    seen = set()
    for row in rows:
        if row.get("gate_status") == "high_quality_near_miss" or row.get("near_miss_category"):
            key = row.get("candidate_id") or row.get("url") or row.get("source_url")
            if key and key not in seen:
                selected.append(row)
                seen.add(key)
    recovered: list[dict] = []
    unresolved: list[dict] = []
    frontier: list[dict] = []
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for row in selected:
            url = row.get("url") or row.get("source_url") or row.get("candidate_url") or ""
            route_id = row.get("route_id") or "near_miss_recovery"
            category = recovery_category(row)
            if not url.startswith(("http://", "https://")):
                unresolved.append({**row, "recovery_category": category, "recovery_status": "missing_url"})
                continue
            html, status = fetch_followup(url, route_id, config, session, execute)
            if status != "ok":
                unresolved.append({**row, "recovery_category": category, "recovery_status": status})
                if category in {"PDF_LINK_NOT_PROCESSED", "POSSIBLE_SERIAL_ISSUE", "POSSIBLE_NEWSLETTER"}:
                    frontier.append(make_frontier_addition(row, url, "PDF_OR_SERIAL_FOLLOWUP"))
                continue
            route = {
                "route_id": route_id,
                "source_name": row.get("source_name") or row.get("existing_source_name") or "",
                "source_tier": row.get("source_tier") or "B",
                "route_family": row.get("route_family") or "public_history_site",
                "state": row.get("target_state") or row.get("state") or "",
                "official_url": row.get("access_source_url") or url,
                "evidence_or_discovery": "evidence_possible",
            }
            adapters = matching_adapters(url, route)
            metadata = adapters[0].parse_item_page(html, url, route)
            candidate = candidate_from_seed(row | route, "noauth_gap_near_miss_recovery_001", metadata.title, metadata.url, metadata.snippet, metadata.date_text, metadata.item_format)
            decision, staged = classify_and_optionally_stage(conn, candidate, route, config.data, metadata.snippet, execute)
            staged["recovery_category"] = category
            if decision.target_gap_eligible:
                recovered.append(staged)
            else:
                unresolved.append({**staged, "recovery_category": category, "recovery_status": decision.reason})
            for pdf in extract_pdf_links(html, url)[:5]:
                if same_domain(url, pdf["url"]):
                    frontier.append(make_frontier_addition(row, pdf["url"], "PDF_LINK_NOT_PROCESSED"))
        if execute:
            conn.commit()
    write_csv(out_dir / "near_miss_recovered_candidates.csv", recovered, list(recovered[0].keys()) if recovered else ["candidate_id"])
    write_csv(out_dir / "near_miss_unresolved.csv", unresolved, list(unresolved[0].keys()) if unresolved else ["candidate_id"])
    write_csv(out_dir / "near_miss_frontier_additions.csv", frontier, list(frontier[0].keys()) if frontier else ["action_id"])
    write_report(
        out_dir / "near_miss_recovery_report.md",
        "Near-Miss Recovery Report",
        {
            "Run ID": run_id,
            "Execute": str(execute).lower(),
            "Near misses inspected": len(selected),
            "Recovered target-gap candidates": len(recovered),
            "Unresolved near misses": len(unresolved),
            "Frontier additions": len(frontier),
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
    )
    return {"inspected": len(selected), "recovered": len(recovered), "unresolved": len(unresolved), "frontier": len(frontier)}


def make_frontier_addition(row: dict, url: str, next_action: str) -> dict:
    return {
        "action_id": stable_action_id(row.get("candidate_id"), url, next_action),
        "route_id": row.get("route_id") or "",
        "source_name": row.get("source_name") or "",
        "source_tier": row.get("source_tier") or "",
        "route_family": row.get("route_family") or "",
        "state": row.get("target_state") or row.get("state") or "",
        "url": url,
        "next_action": next_action,
        "should_fetch": 1,
        "safety_notes": "same-domain no-auth follow-up; robots required; snippets/metadata only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(recover(Path(args.db), args.run_id, Path(args.out_dir), execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
