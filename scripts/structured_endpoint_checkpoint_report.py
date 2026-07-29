#!/usr/bin/env python3
"""Summarize no-credential structured endpoint marathon progress."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from migrate_structured_endpoint_harvest_v1 import migrate


def one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int((conn.execute(sql, params).fetchone() or [0])[0] or 0)


def rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def write_csv(path: Path, records: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in fields})


def checkpoint(db_path: Path, run_id: str, out_path: Path) -> dict[str, Any]:
    migrate(db_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        records_seen = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=?", (run_id,))
        target_raw = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=1", (run_id,))
        target_weight_row = conn.execute(
            "SELECT COALESCE(SUM(target_effective_weight), 0) FROM provisional_records WHERE run_id=? AND target_gap_eligible=1 AND harvest_mode='structured_endpoint_gap'",
            (run_id,),
        ).fetchone()
        target_weight = float(target_weight_row[0] or 0.0) if target_weight_row else 0.0
        near_misses = one(
            conn,
            "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=0 AND ((controlled_term_hits IS NOT NULL AND controlled_term_hits NOT IN ('[]','')) OR inferred_year IS NOT NULL)",
            (run_id,),
        )
        d_class = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND source_tier='D'", (run_id,))
        queued = one(
            conn,
            """
            SELECT COUNT(*)
            FROM noauth_endpoint_queries q
            JOIN noauth_endpoint_inventory i ON i.endpoint_id=q.endpoint_id
            WHERE q.run_id=? AND q.status='queued' AND i.status='active'
            """,
            (run_id,),
        )
        attempted = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_queries WHERE run_id=? AND status='attempted'", (run_id,))
        endpoints = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory WHERE status='active'")
        paused = one(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory WHERE status='paused'")
        by_type = [dict(row) for row in rows(conn, "SELECT endpoint_type, COUNT(*) AS records_seen, SUM(target_gap_eligible) AS target_gap_records FROM noauth_endpoint_records WHERE run_id=? GROUP BY endpoint_type ORDER BY records_seen DESC", (run_id,))]
        stats = [dict(row) for row in rows(conn, "SELECT endpoint_type, source_name, queries_attempted, records_seen, target_gap_records, near_misses, errors, recommended_action FROM noauth_endpoint_route_stats WHERE run_id=? ORDER BY target_gap_records DESC, near_misses DESC, records_seen DESC LIMIT 25", (run_id,))]
        target_examples = [dict(row) for row in rows(conn, "SELECT endpoint_record_id, source_name, source_tier, endpoint_type, title, date_text, item_url, target_gap_score FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=1 ORDER BY target_gap_score DESC LIMIT 50", (run_id,))]
        near_examples = [dict(row) for row in rows(conn, "SELECT endpoint_record_id, source_name, source_tier, endpoint_type, title, date_text, item_url, gate_reasons_json FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=0 AND (controlled_term_hits NOT NULL AND controlled_term_hits NOT IN ('[]','')) LIMIT 50", (run_id,))]

    csv_dir = out_path.parent
    write_csv(csv_dir / f"{run_id}_structured_endpoint_target_records.csv", target_examples, ["endpoint_record_id", "source_name", "source_tier", "endpoint_type", "title", "date_text", "item_url", "target_gap_score"])
    write_csv(csv_dir / f"{run_id}_structured_endpoint_near_misses.csv", near_examples, ["endpoint_record_id", "source_name", "source_tier", "endpoint_type", "title", "date_text", "item_url", "gate_reasons_json"])
    lines = [
        "# Structured Endpoint Checkpoint",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Active structured endpoints: `{endpoints}`",
        f"- Paused structured endpoints: `{paused}`",
        f"- Queries attempted: `{attempted}`",
        f"- Queries queued: `{queued}`",
        f"- Endpoint records seen: `{records_seen}`",
        f"- Target-gap raw records: `{target_raw}`",
        f"- Target-gap effective records: `{target_weight}`",
        f"- High-quality near misses: `{near_misses}`",
        f"- D-class access/discovery candidates: `{d_class}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Endpoint Types",
    ]
    lines.extend([f"- {row.get('endpoint_type') or 'UNKNOWN'}: records `{row.get('records_seen') or 0}`, targets `{row.get('target_gap_records') or 0}`" for row in by_type] or ["- None"])
    lines.extend(["", "## Top Route Stats"])
    lines.extend([f"- {row.get('endpoint_type')} / {row.get('source_name')}: queries `{row.get('queries_attempted')}`, records `{row.get('records_seen')}`, targets `{row.get('target_gap_records')}`, near `{row.get('near_misses')}`, errors `{row.get('errors')}`, action `{row.get('recommended_action')}`" for row in stats] or ["- None"])
    next_action = "continue_structured_endpoint_marathon" if queued else "run_access_platform_endpoint_mining_then_rebuild" if near_misses > 0 or d_class > 0 else "consider_no_credential_infeasibility_report"
    lines.extend(["", "## Next Action", f"- `{next_action}`"])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "records_seen": records_seen,
        "target_gap_raw": target_raw,
        "target_gap_effective": target_weight,
        "near_misses": near_misses,
        "d_class_candidates": d_class,
        "queued": queued,
        "next_action": next_action,
        "out": str(out_path),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default="noauth_structured_endpoint_001")
    parser.add_argument("--out", default="data/processed/v2/autoharvest/structured_endpoints/noauth_structured_endpoint_001_checkpoint.md")
    args = parser.parse_args()
    print(json.dumps(checkpoint(Path(args.db), args.run_id, Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
