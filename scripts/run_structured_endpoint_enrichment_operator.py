#!/usr/bin/env python3
"""Run structured endpoint near-miss enrichment recovery phases."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_structured_endpoint_metrics import audit as audit_metrics
from autoharvest_watchdog import run_watchdog
from collection_expansion_common import now_iso, table_exists
from debug_structured_endpoint_adapters import debug as debug_adapters
from enrich_structured_near_misses import enrich as enrich_near_misses
from materialize_structured_near_misses import materialize as materialize_near_misses
from migrate_structured_near_miss_v1 import migrate
from rebuild_structured_queries_from_materialized_near_misses import rebuild as rebuild_queries


BASE_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
REVIEW_DIR = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"


def count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int((conn.execute(sql, params).fetchone() or [0])[0] or 0)


def operator(db_path: Path, base_run_id: str, run_id: str, target_gap_effective_records: int, execute: bool) -> dict[str, Any]:
    migrate(db_path)
    metrics = audit_metrics(db_path, base_run_id, BASE_DIR / "metrics_audit")
    materialized = materialize_near_misses(
        db_path,
        base_run_id,
        REVIEW_DIR / f"{base_run_id}_near_misses_materialized.csv",
        BASE_DIR / "near_miss_materialization_report.md",
        execute=execute,
    )
    adapter = debug_adapters(db_path, base_run_id, BASE_DIR / "adapter_debug")
    enrichment = enrich_near_misses(db_path, base_run_id, 200, execute=execute)

    with sqlite3.connect(db_path) as conn:
        enriched_targets = count(conn, "SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=? AND target_gap_eligible=1", (base_run_id,)) if table_exists(conn, "structured_endpoint_enriched_records") else 0
        recoverable_remaining = (
            count(
                conn,
                """
                SELECT COUNT(*)
                FROM structured_endpoint_near_misses
                WHERE run_id=? AND recovery_status IN ('queued','paused_fetch_failed','enriched_near_miss') AND recoverability_score >= 50
                """,
                (base_run_id,),
            )
            if table_exists(conn, "structured_endpoint_near_misses")
            else 0
        )
        target_weight = (
            float(
                (conn.execute(
                    """
                    SELECT COALESCE(SUM(target_effective_weight), 0)
                    FROM provisional_records
                    WHERE run_id=? AND target_gap_eligible=1
                      AND harvest_mode='structured_endpoint_enriched_gap'
                    """,
                    (base_run_id,),
                ).fetchone() or [0])[0]
                or 0
            )
            if table_exists(conn, "provisional_records")
            else 0.0
        )

    rebuilt = {"queries_written": 0}
    if execute and (enriched_targets > 0 or recoverable_remaining > 0):
        rebuilt = rebuild_queries(
            db_path,
            base_run_id,
            "noauth_structured_endpoint_enriched_001",
            BASE_DIR / "enriched_query_rebuild_report.md",
            execute=True,
        )

    watchdog = run_watchdog(db_path, "noauth_marathon_001", BASE_DIR / f"{base_run_id}_watchdog.md")
    if watchdog.get("safety_stopped"):
        stop_status = "safety_stopped"
    elif target_weight >= target_gap_effective_records:
        stop_status = "target_reached"
    elif enriched_targets > 0:
        stop_status = "continue_structured_endpoint_marathon_with_enrichment"
    elif recoverable_remaining > 0:
        stop_status = "paused_recoverable_near_misses_remaining"
    else:
        stop_status = "paused_near_misses_exhausted_no_targets"

    summary = {
        "run_id": run_id,
        "base_run_id": base_run_id,
        "execute": execute,
        "metrics": metrics,
        "materialized": materialized,
        "adapter_debug": adapter,
        "enrichment": enrichment,
        "enriched_targets": enriched_targets,
        "target_gap_effective_weight": target_weight,
        "recoverable_remaining": recoverable_remaining,
        "rebuilt_queries": rebuilt,
        "watchdog": watchdog,
        "stop_status": stop_status,
        "structured_endpoint_marathon_resumed": False,
        "public_records_mutated": False,
        "map_flags_mutated": False,
        "frontend_mutated": False,
    }
    lines = [
        "# Structured Endpoint Enrichment Operator Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Base run ID: `{base_run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Materialized near misses: `{materialized.get('materialized', 0)}`",
        f"- Enriched records: `{enrichment.get('enriched_records', 0)}`",
        f"- Enriched target-gap records: `{enriched_targets}`",
        f"- Target-gap effective weight: `{target_weight}`",
        f"- Recoverable near misses remaining: `{recoverable_remaining}`",
        f"- Rebuilt targeted queries: `{rebuilt.get('queries_written', 0)}`",
        f"- Stop status: `{stop_status}`",
        "- Structured endpoint marathon resumed: `no`",
        f"- Watchdog hard violations: `{watchdog.get('hard', 0)}`",
        f"- Safety stopped: `{str(bool(watchdog.get('safety_stopped'))).lower()}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Phase Outputs",
        f"- Metrics audit: `{BASE_DIR / 'metrics_audit' / 'structured_endpoint_metrics_audit.md'}`",
        f"- Near-miss materialization: `{BASE_DIR / 'near_miss_materialization_report.md'}`",
        f"- Adapter debug: `{BASE_DIR / 'adapter_debug' / 'adapter_debug_summary.md'}`",
        f"- Enrichment report: `{BASE_DIR / 'enrichment_report.md'}`",
        f"- Query rebuild report: `{BASE_DIR / 'enriched_query_rebuild_report.md'}`",
        f"- Watchdog: `{BASE_DIR / f'{base_run_id}_watchdog.md'}`",
    ]
    out = BASE_DIR / f"{run_id}_operator_summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--base-run-id", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = operator(Path(args.db), args.base_run_id, args.run_id, args.target_gap_effective_records, execute=bool(args.execute and not args.dry_run))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
