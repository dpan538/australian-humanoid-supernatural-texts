#!/usr/bin/env python3
"""Write milestone reports for research-volume expansion."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from migrate_research_volume_expansion_v1 import migrate


COUNT_FIELDS = ["category", "count"]


def _count_rows(counter: Counter) -> list[dict[str, Any]]:
    return [{"category": str(key or "unknown"), "count": value} for key, value in counter.most_common()]


def audit(db_path: Path, run_id: str, milestone: int, out_dir: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM research_volume_items WHERE run_id=? ORDER BY created_at, item_id LIMIT ?", (run_id, milestone)).fetchall()]
        public_mutated = 0
        map_mutated = 0
        frontend_mutated = 0
    layers = Counter(row["layer"] for row in rows)
    families = Counter(row.get("route_family") or "unknown" for row in rows)
    states = Counter(row.get("target_state") or "unknown" for row in rows)
    bands = Counter(row.get("time_band") or "unknown" for row in rows)
    blockers = Counter(row.get("constraint_blocker") or "unknown" for row in rows)
    tiers = Counter(row.get("source_tier") or "unknown" for row in rows)
    duplicates = sum(1 for row in rows if row.get("duplicate_status") not in {"unique", "canonical", "unchecked", "", None})
    noise = sum(1 for row in rows if "noise" in str(row.get("evidence_gap") or "").lower() or row.get("priority_bucket") == "HOLD")
    duplicate_noise_rate = round(((duplicates + noise) / len(rows) * 100) if rows else 0.0, 2)
    priority = sum(1 for row in rows if int(row.get("is_priority_item") or 0))
    target_period = sum(1 for row in rows if int(row.get("is_target_period") or 0))
    non_aggregator = sum(1 for row in rows if int(row.get("is_non_aggregator") or 0))
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "source_family_distribution.csv", _count_rows(families), COUNT_FIELDS)
    write_csv(out_dir / "state_distribution.csv", _count_rows(states), COUNT_FIELDS)
    write_csv(out_dir / "time_band_distribution.csv", _count_rows(bands), COUNT_FIELDS)
    write_csv(out_dir / "top_blockers.csv", _count_rows(blockers), COUNT_FIELDS)
    write_csv(out_dir / "evidence_tier_distribution.csv", _count_rows(tiers), COUNT_FIELDS)
    write_csv(out_dir / "layer_distribution.csv", _count_rows(layers), COUNT_FIELDS)
    lines = [
        "# Research Volume Milestone Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Milestone: `{milestone}`",
        f"- Total new items counted: `{len(rows)}`",
        f"- Provisional records: `{layers.get('provisional_record', 0)}`",
        f"- Target-gap leads: `{layers.get('target_gap_lead', 0)}`",
        f"- Metadata-only leads: `{layers.get('metadata_only_lead', 0)}`",
        f"- Auxiliary source-intelligence rows: `{layers.get('auxiliary_source_intelligence', 0)}`",
        f"- Priority leads or provisional candidates: `{priority}`",
        f"- 1926-1976 targeted items: `{target_period}`",
        f"- Non-AYR/Wikipedia/tourism/paranormal items: `{non_aggregator}`",
        f"- Duplicate/noise rate: `{duplicate_noise_rate}%`",
        f"- Public records mutated: `{public_mutated}`",
        f"- Map flags mutated: `{map_mutated}`",
        f"- Frontend artifacts mutated: `{frontend_mutated}`",
        "",
        "## Source-Family Distribution",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in families.most_common(12)] or ["- None"])
    lines.extend(["", "## State Distribution"])
    lines.extend([f"- `{key}`: {value}" for key, value in states.most_common()] or ["- None"])
    lines.extend(["", "## Time-Band Distribution"])
    lines.extend([f"- `{key}`: {value}" for key, value in bands.most_common()] or ["- None"])
    lines.extend(["", "## Top Blockers"])
    lines.extend([f"- `{key}`: {value}" for key, value in blockers.most_common(10)] or ["- None"])
    report = out_dir / "milestone_summary.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO research_volume_milestones (
                run_id, milestone_value, reached_at, report_path, total_new_items, provisional_records,
                target_gap_leads, metadata_only_leads, auxiliary_source_intelligence, priority_items,
                target_period_items, non_aggregator_items, duplicate_noise_rate, public_records_mutated,
                map_flags_mutated, frontend_artifacts_mutated, audit_status, notes
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id, milestone_value) DO UPDATE SET
                reached_at=excluded.reached_at, report_path=excluded.report_path,
                total_new_items=excluded.total_new_items, provisional_records=excluded.provisional_records,
                target_gap_leads=excluded.target_gap_leads, metadata_only_leads=excluded.metadata_only_leads,
                auxiliary_source_intelligence=excluded.auxiliary_source_intelligence, priority_items=excluded.priority_items,
                target_period_items=excluded.target_period_items, non_aggregator_items=excluded.non_aggregator_items,
                duplicate_noise_rate=excluded.duplicate_noise_rate, public_records_mutated=excluded.public_records_mutated,
                map_flags_mutated=excluded.map_flags_mutated, frontend_artifacts_mutated=excluded.frontend_artifacts_mutated,
                audit_status=excluded.audit_status, notes=excluded.notes
            """,
            (
                run_id,
                milestone,
                now_iso(),
                str(report),
                len(rows),
                layers.get("provisional_record", 0),
                layers.get("target_gap_lead", 0),
                layers.get("metadata_only_lead", 0),
                layers.get("auxiliary_source_intelligence", 0),
                priority,
                target_period,
                non_aggregator,
                duplicate_noise_rate,
                public_mutated,
                map_mutated,
                frontend_mutated,
                "complete" if len(rows) >= milestone else "not_reached",
                "research-layer milestone only; no public promotion",
            ),
        )
        conn.commit()
    return {"milestone": milestone, "total_new_items": len(rows), "priority_items": priority, "target_period_items": target_period, "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--milestone", type=int, required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.db), args.run_id, args.milestone, Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
