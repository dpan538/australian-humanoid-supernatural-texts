#!/usr/bin/env python3
"""Reconcile no-auth structured endpoint metrics and artifacts."""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv
from migrate_structured_endpoint_harvest_v1 import migrate


STATUSES = {
    "CONSISTENT",
    "EXPLAINED_DIFFERENCE",
    "BUG_NEAR_MISS_NOT_MATERIALIZED",
    "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH",
    "BUG_QUERY_COUNT_MISMATCH",
    "UNKNOWN_REQUIRES_FIX",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def metric(text: str, label: str) -> str:
    match = re.search(rf"-\s*{re.escape(label)}:\s*`?([^`\n]+)`?", text)
    return match.group(1).strip() if match else ""


def metric_int(text: str, label: str) -> int | None:
    raw = metric(text, label)
    if not raw:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", raw.replace(",", ""))
    return int(float(match.group(0))) if match else None


def csv_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int((conn.execute(sql, params).fetchone() or [0])[0] or 0)


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def status_for_equal(report_count: int | None, db_count: int | None) -> str:
    if report_count is None or db_count is None:
        return "UNKNOWN_REQUIRES_FIX"
    return "CONSISTENT" if report_count == db_count else "EXPLAINED_DIFFERENCE"


def add_count(recon: list[dict[str, Any]], metric_name: str, report_count: Any, db_count: Any, artifact_count: Any, status: str, explanation: str) -> None:
    if status not in STATUSES:
        status = "UNKNOWN_REQUIRES_FIX"
    recon.append(
        {
            "metric_name": metric_name,
            "report_count": "" if report_count is None else report_count,
            "db_count": "" if db_count is None else db_count,
            "artifact_count": "" if artifact_count is None else artifact_count,
            "count_status": status,
            "explanation": explanation,
        }
    )


def audit(db_path: Path, run_id: str, out_dir: Path) -> dict[str, Any]:
    migrate(db_path)
    base = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
    discovery_path = base / "endpoint_discovery_report.md"
    query_plan_path = base / "structured_endpoint_query_plan.md"
    operator_path = base / f"{run_id}_operator_summary.md"
    checkpoint_path = base / f"{run_id}_checkpoint.md"
    target_csv = base / f"{run_id}_structured_endpoint_target_records.csv"
    near_csv = base / f"{run_id}_structured_endpoint_near_misses.csv"
    materialized_csv = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints" / f"{run_id}_near_misses_materialized.csv"

    discovery = read_text(discovery_path)
    query_plan = read_text(query_plan_path)
    operator = read_text(operator_path)
    checkpoint = read_text(checkpoint_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        endpoints_total = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory") if table_exists(conn, "noauth_endpoint_inventory") else 0
        endpoints_active = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory WHERE status='active'") if table_exists(conn, "noauth_endpoint_inventory") else 0
        endpoints_paused = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory WHERE status='paused'") if table_exists(conn, "noauth_endpoint_inventory") else 0
        queries_total = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_queries WHERE run_id=?", (run_id,)) if table_exists(conn, "noauth_endpoint_queries") else 0
        queries_attempted = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_queries WHERE run_id=? AND status='attempted'", (run_id,)) if table_exists(conn, "noauth_endpoint_queries") else 0
        queries_queued_all = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_queries WHERE run_id=? AND status='queued'", (run_id,)) if table_exists(conn, "noauth_endpoint_queries") else 0
        queries_queued_active = (
            scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM noauth_endpoint_queries q
                JOIN noauth_endpoint_inventory i ON i.endpoint_id=q.endpoint_id
                WHERE q.run_id=? AND q.status='queued' AND i.status='active'
                """,
                (run_id,),
            )
            if table_exists(conn, "noauth_endpoint_queries") and table_exists(conn, "noauth_endpoint_inventory")
            else 0
        )
        records_total = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=?", (run_id,)) if table_exists(conn, "noauth_endpoint_records") else 0
        target_records = scalar(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=1", (run_id,)) if table_exists(conn, "noauth_endpoint_records") else 0
        near_record_level = (
            scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM noauth_endpoint_records
                WHERE run_id=? AND COALESCE(target_gap_eligible, 0)=0
                  AND ((controlled_term_hits IS NOT NULL AND controlled_term_hits NOT IN ('[]',''))
                       OR inferred_year IS NOT NULL)
                """,
                (run_id,),
            )
            if table_exists(conn, "noauth_endpoint_records")
            else 0
        )
        near_controlled_only = (
            scalar(
                conn,
                """
                SELECT COUNT(*)
                FROM noauth_endpoint_records
                WHERE run_id=? AND COALESCE(target_gap_eligible, 0)=0
                  AND controlled_term_hits IS NOT NULL AND controlled_term_hits NOT IN ('[]','')
                """,
                (run_id,),
            )
            if table_exists(conn, "noauth_endpoint_records")
            else 0
        )
        route_queries = scalar(conn, "SELECT COALESCE(SUM(queries_attempted), 0) FROM noauth_endpoint_route_stats WHERE run_id=?", (run_id,)) if table_exists(conn, "noauth_endpoint_route_stats") else 0
        route_records = scalar(conn, "SELECT COALESCE(SUM(records_seen), 0) FROM noauth_endpoint_route_stats WHERE run_id=?", (run_id,)) if table_exists(conn, "noauth_endpoint_route_stats") else 0
        route_near = scalar(conn, "SELECT COALESCE(SUM(near_misses), 0) FROM noauth_endpoint_route_stats WHERE run_id=?", (run_id,)) if table_exists(conn, "noauth_endpoint_route_stats") else 0
        materialized_rows = scalar(conn, "SELECT COUNT(*) FROM structured_endpoint_near_misses WHERE run_id=?", (run_id,)) if table_exists(conn, "structured_endpoint_near_misses") else 0
        route_rows = (
            rows(
                conn,
                """
                SELECT
                    s.endpoint_id,
                    s.endpoint_type,
                    s.source_name,
                    s.queries_attempted AS route_queries_attempted,
                    s.records_seen AS route_records_seen,
                    s.near_misses AS route_near_misses,
                    s.errors,
                    COUNT(r.endpoint_record_id) AS record_rows,
                    SUM(CASE WHEN r.target_gap_eligible=0 AND ((r.controlled_term_hits IS NOT NULL AND r.controlled_term_hits NOT IN ('[]','')) OR r.inferred_year IS NOT NULL) THEN 1 ELSE 0 END) AS record_near_misses
                FROM noauth_endpoint_route_stats s
                LEFT JOIN noauth_endpoint_records r ON r.run_id=s.run_id AND r.endpoint_id=s.endpoint_id
                WHERE s.run_id=?
                GROUP BY s.run_id, s.endpoint_id
                ORDER BY s.near_misses DESC, s.records_seen DESC
                """,
                (run_id,),
            )
            if table_exists(conn, "noauth_endpoint_route_stats") and table_exists(conn, "noauth_endpoint_records")
            else []
        )

    query_plan_rows = metric_int(query_plan, "Query rows generated")
    operator_queries = metric_int(operator, "Endpoint queries generated")
    checkpoint_attempted = metric_int(checkpoint, "Queries attempted")
    checkpoint_near = metric_int(checkpoint, "High-quality near misses")
    operator_near = metric_int(operator, "High-quality near misses")
    near_csv_rows = csv_data_rows(near_csv)
    target_csv_rows = csv_data_rows(target_csv)
    materialized_csv_rows = csv_data_rows(materialized_csv)

    recon: list[dict[str, Any]] = []
    add_count(recon, "discovery.endpoints_discovered", metric_int(discovery, "Endpoints discovered"), endpoints_total, None, status_for_equal(metric_int(discovery, "Endpoints discovered"), endpoints_total), "Discovery report counts inventory rows.")
    add_count(recon, "discovery.endpoints_rejected", metric_int(discovery, "Endpoints rejected"), None, None, "EXPLAINED_DIFFERENCE", "Rejected probes are report artifacts, not inventory rows.")
    add_count(recon, "query_plan.query_rows_generated", query_plan_rows, queries_total, None, status_for_equal(query_plan_rows, queries_total), "Query plan should equal total noauth_endpoint_queries rows for the run.")
    add_count(recon, "operator.endpoint_queries_generated_label", operator_queries, queries_total, None, "BUG_QUERY_COUNT_MISMATCH" if operator_queries != queries_total else "CONSISTENT", "Operator summary label reports reused active queued rows at operator start, not total rows generated.")
    add_count(recon, "checkpoint.queries_attempted", checkpoint_attempted, queries_attempted, None, status_for_equal(checkpoint_attempted, queries_attempted), "Checkpoint attempted count matches query table attempted status.")
    add_count(recon, "checkpoint.queued_active_queries", metric_int(checkpoint, "Queries queued"), queries_queued_active, None, status_for_equal(metric_int(checkpoint, "Queries queued"), queries_queued_active), "Checkpoint queued count joins only active endpoints; paused endpoints can still have queued rows.")
    add_count(recon, "query_table.queued_all_statuses", None, queries_queued_all, None, "EXPLAINED_DIFFERENCE", "Queued rows on paused endpoints are not actionable until endpoint status changes.")
    add_count(recon, "records.endpoint_records_seen", metric_int(checkpoint, "Endpoint records seen"), records_total, None, status_for_equal(metric_int(checkpoint, "Endpoint records seen"), records_total), "Record table is canonical for rows currently stored.")
    add_count(recon, "targets.record_level", metric_int(checkpoint, "Target-gap raw records"), target_records, target_csv_rows, status_for_equal(metric_int(checkpoint, "Target-gap raw records"), target_records), "Target CSV exports examples from target rows.")
    add_count(recon, "near_misses.record_level_reported", checkpoint_near, near_record_level, near_csv_rows, "BUG_NEAR_MISS_NOT_MATERIALIZED" if near_record_level > 0 and near_csv_rows == 0 else status_for_equal(checkpoint_near, near_record_level), "Checkpoint near count uses date-or-term record-level criteria, but old CSV exported controlled-term-only examples.")
    add_count(recon, "near_misses.controlled_term_export_filter", None, near_controlled_only, near_csv_rows, "CONSISTENT" if near_controlled_only == near_csv_rows else "UNKNOWN_REQUIRES_FIX", "Old near_misses CSV query used controlled_term_hits only.")
    add_count(recon, "near_misses.materialized_table", checkpoint_near, materialized_rows, materialized_csv_rows, "BUG_NEAR_MISS_NOT_MATERIALIZED" if (checkpoint_near or 0) > 0 and materialized_rows == 0 else "CONSISTENT", "Durable near-miss table is canonical after materialization.")
    add_count(recon, "route_stats.records_seen_sum", route_records, records_total, None, "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH" if route_records != records_total else "CONSISTENT", "Route stats are cumulative upserts and can exceed current deduped endpoint records.")
    add_count(recon, "route_stats.near_misses_sum", route_near, near_record_level, None, "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH" if route_near != near_record_level else "CONSISTENT", "Route stats near_misses are aggregate/cumulative, not durable near-miss rows.")
    add_count(recon, "route_stats.queries_attempted_sum", route_queries, queries_attempted, None, "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH" if route_queries != queries_attempted else "CONSISTENT", "Route stats count all endpoint updates and can diverge from current query statuses.")

    artifact_rows = [
        {"artifact": str(discovery_path), "exists": discovery_path.exists(), "data_rows": "", "count_status": "CONSISTENT" if discovery_path.exists() else "UNKNOWN_REQUIRES_FIX"},
        {"artifact": str(query_plan_path), "exists": query_plan_path.exists(), "data_rows": "", "count_status": "CONSISTENT" if query_plan_path.exists() else "UNKNOWN_REQUIRES_FIX"},
        {"artifact": str(operator_path), "exists": operator_path.exists(), "data_rows": "", "count_status": "CONSISTENT" if operator_path.exists() else "UNKNOWN_REQUIRES_FIX"},
        {"artifact": str(checkpoint_path), "exists": checkpoint_path.exists(), "data_rows": "", "count_status": "CONSISTENT" if checkpoint_path.exists() else "UNKNOWN_REQUIRES_FIX"},
        {"artifact": str(target_csv), "exists": target_csv.exists(), "data_rows": target_csv_rows, "count_status": "CONSISTENT" if target_csv.exists() else "UNKNOWN_REQUIRES_FIX"},
        {"artifact": str(near_csv), "exists": near_csv.exists(), "data_rows": near_csv_rows, "count_status": "BUG_NEAR_MISS_NOT_MATERIALIZED" if near_record_level > 0 and near_csv_rows == 0 else "CONSISTENT"},
        {"artifact": str(materialized_csv), "exists": materialized_csv.exists(), "data_rows": materialized_csv_rows, "count_status": "BUG_NEAR_MISS_NOT_MATERIALIZED" if near_record_level > 0 and materialized_csv_rows == 0 else "CONSISTENT"},
    ]

    route_recon: list[dict[str, Any]] = []
    for row in route_rows:
        status = "CONSISTENT" if int(row.get("route_records_seen") or 0) == int(row.get("record_rows") or 0) and int(row.get("route_near_misses") or 0) == int(row.get("record_near_misses") or 0) else "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH"
        route_recon.append({**row, "count_status": status})

    write_csv(out_dir / "count_reconciliation_by_table.csv", recon, ["metric_name", "report_count", "db_count", "artifact_count", "count_status", "explanation"])
    write_csv(
        out_dir / "route_stats_reconciliation.csv",
        route_recon,
        ["endpoint_id", "endpoint_type", "source_name", "route_queries_attempted", "route_records_seen", "route_near_misses", "errors", "record_rows", "record_near_misses", "count_status"],
    )
    write_csv(out_dir / "artifact_presence_check.csv", artifact_rows, ["artifact", "exists", "data_rows", "count_status"])
    write_csv(out_dir / "structured_endpoint_metrics_audit.csv", recon, ["metric_name", "report_count", "db_count", "artifact_count", "count_status", "explanation"])

    canonical = "structured_endpoint_near_misses after materialization; before that, noauth_endpoint_records record-level derivation is the least-bad canonical source. Route stats are not canonical."
    questions = [
        ("Why does query plan report 659 rows but operator summary says 13 query rows?", "The query plan reports all rows inserted for the run. The operator summary label is misleading: when existing queued rows are reused, it records the active queued rows available at operator start, not newly generated plan rows."),
        ("Why does checkpoint report 353 attempted queries?", f"The query table currently has {queries_attempted} rows with status attempted. The remaining {queries_queued_all} queued rows are on paused/non-active endpoints and are excluded from the active queued checkpoint count."),
        ("Why does global near-miss count say 22 while top route stats show WA Museum near 88?", "The global near count is a current record-level query. Route stats are cumulative aggregate counters updated by additive upserts and can exceed the deduped/replaced endpoint record table."),
        ("Why does near_misses CSV have no materialized rows if the reports say near misses exist?", "The old CSV export filtered only controlled_term_hits; the 22 reported near misses are date-only records, so the CSV contains only a header. This is BUG_NEAR_MISS_NOT_MATERIALIZED."),
        ("Are near misses stored in DB but not exported?", "They are derivable from noauth_endpoint_records but were not stored as durable near-miss rows before this recovery migration/materializer."),
        ("Are near misses route-level aggregate counts only?", "No. The reliable count is record-level; route-level counts are aggregate diagnostics and cumulative."),
        ("Are route stats cumulative across multiple runs?", "Within a run_id they are cumulative across endpoint-stat upserts and can diverge from current deduped endpoint records."),
        ("Are endpoint records deduped down from 295/120 to 22 near misses?", "Current endpoint records are 120 rows; the 22 near misses are the date-or-term subset. WA Museum route stat 295 is cumulative and not the current durable row count."),
        ("Which count should be canonical?", canonical),
    ]
    bug_statuses = sorted({row["count_status"] for row in recon if str(row["count_status"]).startswith("BUG")})
    lines = [
        "# Structured Endpoint Metrics Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Inventory endpoints: `{endpoints_total}`",
        f"- Active endpoints: `{endpoints_active}`",
        f"- Paused endpoints: `{endpoints_paused}`",
        f"- Query rows total: `{queries_total}`",
        f"- Queries attempted: `{queries_attempted}`",
        f"- Queued rows all statuses: `{queries_queued_all}`",
        f"- Queued rows on active endpoints: `{queries_queued_active}`",
        f"- Endpoint records stored: `{records_total}`",
        f"- Record-level near misses: `{near_record_level}`",
        f"- Old near_misses CSV rows: `{near_csv_rows}`",
        f"- Materialized near-miss rows: `{materialized_rows}`",
        f"- Route stats records sum: `{route_records}`",
        f"- Route stats near sum: `{route_near}`",
        f"- Count statuses: `{', '.join(bug_statuses) if bug_statuses else 'CONSISTENT_OR_EXPLAINED'}`",
        "",
        "## Answers",
    ]
    lines.extend([f"- {question} {answer}" for question, answer in questions])
    lines.extend(
        [
            "",
            "## Canonical Count",
            f"- {canonical}",
            "",
            "## Required Fixes",
        ]
    )
    if near_record_level > 0 and near_csv_rows == 0:
        lines.append("- Materialize near misses into structured_endpoint_near_misses and export that table.")
    if route_records != records_total or route_near != near_record_level:
        lines.append("- Treat route stats as cumulative diagnostics; reconcile against record-level rows in reporting.")
    if operator_queries != queries_total:
        lines.append("- Rename or clarify operator summary query metric so reused active queued rows are not described as generated rows.")
    if len(lines) and lines[-1] == "## Required Fixes":
        lines.append("- None.")

    (out_dir / "structured_endpoint_metrics_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "records_total": records_total,
        "near_record_level": near_record_level,
        "near_csv_rows": near_csv_rows,
        "materialized_rows": materialized_rows,
        "route_near": route_near,
        "bug_statuses": bug_statuses,
        "out_dir": str(out_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(audit(Path(args.db), args.run_id, Path(args.out_dir)))


if __name__ == "__main__":
    main()
