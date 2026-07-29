#!/usr/bin/env python3
"""Run research-layer volume expansion without public promotion."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from build_research_volume_expansion_scheduler import build as build_schedule_report
from lib.research_volume import materialize_auxiliary, materialize_target_lead, insert_volume_item, summarize_items
from migrate_research_volume_expansion_v1 import migrate
from research_volume_milestone_audit import audit as milestone_audit


DEFAULT_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "research_volume"


def read_schedule(path: Path) -> list[dict[str, object]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for key in ["inferred_year", "is_priority_item", "is_target_period", "is_non_aggregator"]:
            row[key] = int(row.get(key) or 0)
        row["priority_score"] = float(row.get("priority_score") or 0)
    return rows


def run(db_path: Path, run_id: str, target_new_items: int, execute: bool, out_dir: Path = DEFAULT_DIR) -> dict[str, object]:
    migrate(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    schedule_path = out_dir / "volume_expansion_schedule.csv"
    schedule_report = out_dir / "volume_expansion_schedule.md"
    build_schedule_report(db_path, run_id, target_new_items, schedule_path, schedule_report, True)
    schedule = read_schedule(schedule_path)
    started = now_iso()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_volume_runs (run_id, status, target_new_items, started_at, notes)
            VALUES (?, 'running', ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET status='running', target_new_items=excluded.target_new_items, started_at=excluded.started_at, notes=excluded.notes
            """,
            (run_id, target_new_items, started, "volume expansion across research layers; no public mutation"),
        )
        if execute:
            for row in schedule:
                if row["planned_layer"] in {"target_gap_lead", "metadata_only_lead"}:
                    linked_id = materialize_target_lead(conn, row)
                    insert_volume_item(conn, row, "target_gap_leads", linked_id)
                elif row["planned_layer"] == "auxiliary_source_intelligence":
                    linked_id = materialize_auxiliary(conn, row)
                    insert_volume_item(conn, row, "auxiliary_source_intelligence", linked_id)
            summary = summarize_items(conn, run_id)
            conn.execute(
                """
                UPDATE research_volume_runs
                SET status=?, finished_at=?, new_items=?, provisional_records=?, target_gap_leads=?,
                    metadata_only_leads=?, auxiliary_source_intelligence=?, priority_items=?,
                    target_period_items=?, non_aggregator_items=?, public_records_mutated=0,
                    map_flags_mutated=0, frontend_artifacts_mutated=0
                WHERE run_id=?
                """,
                (
                    "complete" if summary["total_new_items"] >= target_new_items else "partial",
                    now_iso(),
                    summary["total_new_items"],
                    summary["provisional_records"],
                    summary["target_gap_leads"],
                    summary["metadata_only_leads"],
                    summary["auxiliary_source_intelligence"],
                    summary["priority_items"],
                    summary["target_period_items"],
                    summary["non_aggregator_items"],
                    run_id,
                ),
            )
            conn.commit()
        else:
            summary = {
                "total_new_items": 0,
                "provisional_records": 0,
                "target_gap_leads": 0,
                "metadata_only_leads": 0,
                "auxiliary_source_intelligence": 0,
                "priority_items": 0,
                "target_period_items": 0,
                "non_aggregator_items": 0,
            }
            conn.commit()
    milestone_reports = []
    if execute:
        for milestone in [5000, 10000, 25000]:
            if summary["total_new_items"] >= milestone:
                milestone_reports.append(milestone_audit(db_path, run_id, milestone, out_dir / f"milestone_{milestone}"))
    layers = Counter(row["planned_layer"] for row in schedule)
    lines = [
        "# Research Volume Expansion Operator Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Scheduled items: `{len(schedule)}`",
        f"- New research-layer items materialized: `{summary['total_new_items']}`",
        f"- Provisional records: `{summary['provisional_records']}`",
        f"- Target-gap leads: `{summary['target_gap_leads']}`",
        f"- Metadata-only leads: `{summary['metadata_only_leads']}`",
        f"- Auxiliary source-intelligence rows: `{summary['auxiliary_source_intelligence']}`",
        f"- Priority leads or provisional candidates: `{summary['priority_items']}`",
        f"- 1926-1976 targeted items: `{summary['target_period_items']}`",
        f"- Non-aggregator items: `{summary['non_aggregator_items']}`",
        "- Accepted public records created: `0`",
        "- Public records mutated: `no`",
        "- Map flags changed: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Scheduled Layers",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in layers.most_common()] or ["- None"])
    lines.extend(["", "## Milestone Reports"])
    lines.extend([f"- `{row['milestone']}`: {row['report']}" for row in milestone_reports] or ["- None reached"])
    summary_path = out_dir / "research_volume_expansion_operator_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {**summary, "run_id": run_id, "milestones": [row["milestone"] for row in milestone_reports], "summary": str(summary_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default="research_volume_expansion_001")
    parser.add_argument("--target-new-items", type=int, default=25000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(Path(args.db), args.run_id, args.target_new_items, bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
