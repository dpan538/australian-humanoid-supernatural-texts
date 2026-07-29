#!/usr/bin/env python3
"""Audit autoharvest provisional records and write a promotion proposal."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv


def fetch_rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def eligible(row: dict[str, Any]) -> tuple[bool, str]:
    reasons: list[str] = []
    if row.get("source_tier") not in {"A", "B", "C"}:
        reasons.append("source_tier_not_abc")
    if not row.get("evidence_source_name") or not row.get("evidence_source_url"):
        reasons.append("missing_evidence_source")
    if row.get("ethics_status") in {"sensitive", "restricted", "manual_only"}:
        reasons.append("sensitive_or_restricted")
    if row.get("metadata_only") not in {1, "1", True}:
        reasons.append("not_metadata_only")
    if not row.get("date_published") and not row.get("time_band") and not row.get("inferred_year"):
        reasons.append("missing_date_or_time_band")
    return not reasons, ";".join(reasons)


def run_audit(db_path: Path, run_id: str, target: int, out_dir: Path) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        rows = fetch_rows(conn, "SELECT * FROM provisional_records WHERE run_id=?", (run_id,)) if table_exists(conn, "provisional_records") else []
        route_rows = fetch_rows(conn, "SELECT * FROM harvest_route_stats WHERE run_id=?", (run_id,)) if table_exists(conn, "harvest_route_stats") else []
    audit_rows: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    holds: list[dict[str, Any]] = []
    for row in rows:
        ok, reason = eligible(row)
        audit = {**row, "audit_status": "promotion_proposal" if ok else "hold", "audit_reason": reason}
        audit_rows.append(audit)
        if ok:
            proposals.append(audit)
        else:
            holds.append(audit)
    write_csv(out_dir / "provisional_record_audit.csv", audit_rows, list(audit_rows[0].keys()) if audit_rows else ["provisional_record_id", "audit_status", "audit_reason"])
    write_csv(out_dir / "promotion_proposal.csv", proposals, list(audit_rows[0].keys()) if audit_rows else ["provisional_record_id", "audit_status", "audit_reason"])
    write_csv(out_dir / "rejection_or_hold_reasons.csv", holds, list(audit_rows[0].keys()) if audit_rows else ["provisional_record_id", "audit_status", "audit_reason"])
    for name, counter in {
        "source_concentration_after_growth.csv": Counter(row.get("source_name") or "unknown" for row in rows),
        "temporal_gap_after_growth.csv": Counter(row.get("time_band") or "unknown" for row in rows),
        "map_balance_after_growth.csv": Counter(row.get("target_state") or "unknown" for row in rows),
        "source_chain_quality_after_growth.csv": Counter(row.get("source_tier") or "unknown" for row in rows),
        "duplicate_cluster_report.csv": Counter(row.get("duplicate_key") or "unknown" for row in rows),
    }.items():
        write_csv(out_dir / name, [{"key": key, "count": count} for key, count in counter.most_common()], ["key", "count"])
    write_csv(out_dir / "route_yield_report.csv", route_rows, list(route_rows[0].keys()) if route_rows else ["route_id", "yield_score"])
    weighted = sum(float(row.get("growth_weight") or 0) for row in rows)
    lines = [
        "# Autoharvest Milestone Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target effective records: `{target}`",
        f"- Raw provisional records: `{len(rows)}`",
        f"- Weighted growth: `{round(weighted, 2)}`",
        f"- Promotion proposals: `{len(proposals)}`",
        f"- Holds/rejections: `{len(holds)}`",
        "- Public records mutated: `no`",
        "- Promotion proposal applied: `no`",
    ]
    (out_dir / "milestone_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"provisional": len(rows), "proposals": len(proposals), "holds": len(holds)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-effective-records", type=int, default=2000)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    summary = run_audit(Path(args.db), args.run_id, args.target_effective_records, Path(args.out_dir))
    print(f"Wrote milestone audit: {args.out_dir}")
    print(summary)


if __name__ == "__main__":
    main()
