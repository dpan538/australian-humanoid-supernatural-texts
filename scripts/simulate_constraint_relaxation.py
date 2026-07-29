#!/usr/bin/env python3
"""Simulate constraint relaxation scenarios without executing them."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.target_gap_leads import stable_id
from migrate_target_gap_leads_v1 import migrate


SCENARIOS = [
    ("strict_unchanged", "Strict no-credential remains unchanged", "none", 0, 0, "low", "low", "low", "none", "none", "Do not continue equivalent crawlers."),
    ("lead_mode", "Allow target-gap leads as observational layer", "count leads not records", 0, 2000, "low", "low", "low", "low", "none", "Recommended default next mode."),
    ("d_class", "Allow D-class access-platform provisional layer", "D-class evidence constraint", 0, 300, "medium", "high", "low", "medium", "none", "Optional only with clear labeling."),
    ("metadata_1955_1976", "Allow metadata-only 1955-1976 layer", "strict item evidence layer", 0, 800, "medium", "medium", "low", "low", "none", "Recommended as lead layer, not records."),
    ("review_25", "Allow top-25 machine-selected human review", "no human row review", 10, 25, "low", "low", "low", "low", "low", "Optional."),
    ("review_50", "Allow top-50 machine-selected human review", "no human row review", 20, 50, "low", "low", "low", "low", "low", "Optional."),
    ("trove_api", "Allow Trove API key for 1926-1954 only", "no Trove API key", 500, 1000, "low", "low", "low", "medium", "none", "Optional and requires key; not default."),
    ("robots_clarification", "Allow robots/permission clarification campaign", "permission workflow", 0, 120, "low", "low", "low", "medium", "medium", "Useful if permission work is acceptable."),
    ("lower_to_leads", "Lower target from 2000 records to 2000 leads", "target definition", 0, 2000, "low", "low", "low", "low", "none", "Recommended if observational layer is acceptable."),
    ("hybrid", "Hybrid: leads + metadata-only + top-25 review", "mixed lead/review layer", 10, 2500, "medium", "medium", "low", "medium", "low", "Best optional upgrade without broad crawling."),
]


def simulate(db_path: Path, config: Path, out: Path, execute: bool) -> dict[str, object]:
    del config
    migrate(db_path)
    rows = []
    ts = now_iso()
    for scenario_id, name, changed, records, leads, qrisk, srisk, erisk, cost, effort, rec in SCENARIOS:
        rows.append(
            {
                "scenario_id": stable_id("scn_", scenario_id),
                "scenario_name": name,
                "constraint_changed": changed,
                "expected_new_records": records,
                "expected_new_leads": leads,
                "quality_risk": qrisk,
                "source_chain_risk": srisk,
                "ethics_risk": erisk,
                "implementation_cost": cost,
                "owner_effort": effort,
                "recommendation": rec,
                "created_at": ts,
            }
        )
    if execute:
        with sqlite3.connect(db_path) as conn:
            for row in rows:
                fields = list(row)
                placeholders = ", ".join(["?"] * len(fields))
                conn.execute(f"INSERT OR REPLACE INTO constraint_relaxation_scenarios ({', '.join(fields)}) VALUES ({placeholders})", tuple(row[field] for field in fields))
            conn.commit()
    lines = [
        "# Constraint Relaxation Simulation",
        "",
        f"- Generated: `{ts}`",
        "- This is decision support only. No scenario was executed.",
        "",
        "## Scenarios",
    ]
    for row in rows:
        lines.append(f"- `{row['scenario_name']}`: expected records `{row['expected_new_records']}`, expected leads `{row['expected_new_leads']}`, recommendation `{row['recommendation']}`")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"scenarios": len(rows), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(simulate(Path(args.db), Path(args.config), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
