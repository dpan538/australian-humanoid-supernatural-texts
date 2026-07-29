#!/usr/bin/env python3
"""Run the robots-aware structured endpoint near-miss rescue sequence."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from assert_no_public_artifact_diff import check_baseline, create_baseline
from audit_near_miss_robots_block import audit as audit_robots
from autoharvest_watchdog import run_watchdog
from collection_expansion_common import now_iso
from discover_allowed_detail_alternatives import discover as discover_alternatives
from enrich_allowed_detail_alternatives import enrich_alternatives
from enrich_from_existing_endpoint_metadata import enrich_existing_metadata
from enrich_rss_items_inline import enrich_rss_inline
from lib.structured_robots_rescue import ensure_near_miss_tables, target_and_remaining_counts
from no_credential_infeasibility_report import report as infeasibility_report
from repair_atom_atomm_adapter import repair_atom
from structured_endpoint_checkpoint_report import checkpoint


STRUCTURED_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
REVIEW_DIR = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"
BASELINE = ROOT / "data" / "processed" / "v2" / "autoharvest" / "public_artifact_baseline.json"
SUMMARY = STRUCTURED_DIR / "robots_aware_near_miss_rescue_operator_report.md"


def db_counts(db_path: Path, run_id: str) -> dict[str, int]:
    ensure_near_miss_tables(db_path)
    with sqlite3.connect(db_path) as conn:
        near = int(conn.execute("SELECT COUNT(*) FROM structured_endpoint_near_misses WHERE run_id=?", (run_id,)).fetchone()[0] or 0)
        safe_remaining = target_and_remaining_counts(conn, run_id)
    return {"materialized_near_misses": near, **safe_remaining}


def run_operator(db_path: Path, run_id: str, target_gap_effective_records: int, execute: bool) -> dict[str, Any]:
    STRUCTURED_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    phases: dict[str, Any] = {}
    if execute:
        phases["public_artifact_baseline"] = create_baseline(ROOT, BASELINE)
    phases["robots_audit"] = audit_robots(db_path, run_id, STRUCTURED_DIR / "robots_block_audit")
    phases["existing_metadata"] = enrich_existing_metadata(
        db_path,
        run_id,
        REVIEW_DIR / "existing_metadata_enrichment_candidates.csv",
        STRUCTURED_DIR / "existing_metadata_enrichment_report.md",
        execute,
    )
    phases["atom_atomm_repair"] = repair_atom(db_path, run_id, STRUCTURED_DIR / "atom_atomm_repair", execute)
    phases["rss_inline_enrichment"] = enrich_rss_inline(db_path, run_id, STRUCTURED_DIR / "rss_inline_enrichment", execute)
    alternatives_path = STRUCTURED_DIR / "allowed_detail_alternatives.csv"
    phases["allowed_alternatives"] = discover_alternatives(db_path, run_id, alternatives_path, STRUCTURED_DIR / "allowed_detail_alternatives_report.md", execute)
    phases["allowed_detail_enrichment"] = enrich_alternatives(db_path, alternatives_path, run_id, 200, execute)
    phases["checkpoint"] = checkpoint(db_path, run_id, STRUCTURED_DIR / f"{run_id}_checkpoint.md")
    phases["watchdog"] = run_watchdog(db_path, run_id, STRUCTURED_DIR / "robots_aware_rescue_watchdog.md")
    if execute:
        phases["public_artifact_check"] = check_baseline(ROOT, BASELINE)
    counts = db_counts(db_path, run_id)
    if phases["watchdog"].get("hard"):
        status = "safety_stopped"
    elif counts["target_gap_records"] >= target_gap_effective_records or counts["target_gap_records"] > 0:
        status = "target_gap_records_found"
    elif int(phases["allowed_alternatives"].get("safe_to_fetch") or 0) > 0:
        status = "continue_structured_enrichment"
    elif counts["recoverable_remaining"] > 0:
        robots_counts = phases["robots_audit"].get("robots_status_counts", {})
        unknown = sum(int(robots_counts.get(key, 0) or 0) for key in ["ROBOTS_UNKNOWN_TIMEOUT", "ROBOTS_UNKNOWN_HTTP_ERROR", "ROBOTS_UNKNOWN_MISSING_ROBOTS"])
        status = "robots_uncertainty_blocked" if unknown else "continue_structured_enrichment"
    else:
        phases["infeasibility_report"] = infeasibility_report(
            db_path,
            run_id,
            ROOT / "data" / "processed" / "v2" / "autoharvest" / "noauth_gap_recovery_operator_summary.md",
            STRUCTURED_DIR / f"{run_id}_checkpoint.md",
            ROOT / "data" / "processed" / "v2" / "autoharvest" / "no_credential_infeasibility_report.md",
        )
        status = "strict_no_credential_exhausted" if phases["infeasibility_report"].get("no_credential_strict_mode_exhausted") else phases["infeasibility_report"].get("status", "paused_no_targets")
    summary = {"run_id": run_id, "execute": execute, "stop_status": status, **counts, "phases": phases}
    lines = [
        "# Robots-Aware Near-Miss Rescue Operator",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Stop status: `{status}`",
        f"- Materialized near misses: `{counts['materialized_near_misses']}`",
        f"- Target-gap records found: `{counts['target_gap_records']}`",
        f"- Recoverable near misses remaining: `{counts['recoverable_remaining']}`",
        f"- Safe alternatives discovered: `{phases['allowed_alternatives'].get('safe_to_fetch', 0)}`",
        f"- Watchdog hard violations: `{phases['watchdog'].get('hard', 0)}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Phase Reports",
        f"- Robots audit: `{STRUCTURED_DIR / 'robots_block_audit' / 'robots_block_audit.md'}`",
        f"- Existing metadata: `{STRUCTURED_DIR / 'existing_metadata_enrichment_report.md'}`",
        f"- AtoM repair: `{STRUCTURED_DIR / 'atom_atomm_repair' / 'atom_atomm_repair_report.md'}`",
        f"- RSS inline: `{STRUCTURED_DIR / 'rss_inline_enrichment' / 'rss_inline_enrichment_report.md'}`",
        f"- Alternatives: `{STRUCTURED_DIR / 'allowed_detail_alternatives_report.md'}`",
        f"- Allowed detail enrichment: `{STRUCTURED_DIR / 'allowed_detail_enrichment_report.md'}`",
        f"- Watchdog: `{STRUCTURED_DIR / 'robots_aware_rescue_watchdog.md'}`",
    ]
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary["report"] = str(SUMMARY)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_operator(Path(args.db), args.run_id, args.target_gap_effective_records, bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
