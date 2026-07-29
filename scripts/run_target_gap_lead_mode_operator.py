#!/usr/bin/env python3
"""Optional autonomous target-gap lead-mode operator."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from convert_failures_to_target_gap_leads import convert
from lib.target_gap_leads import load_config, output_path
from migrate_target_gap_leads_v1 import migrate
from score_target_gap_leads import score


def lead_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM target_gap_leads").fetchone()[0] or 0) if table_exists(conn, "target_gap_leads") else 0


def run_operator(db_path: Path, config_path: Path, target_leads: int, execute: bool) -> dict[str, object]:
    migrate(db_path)
    config = load_config(config_path)
    lead_dir = output_path(config, "lead_dir", "data/processed/v2/autoharvest/target_gap_leads")
    lead_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        before = lead_count(conn)
    phases = {}
    if before < target_leads:
        phases["convert"] = convert(db_path, config_path, lead_dir / "target_gap_leads_created.md", execute)
        phases["score"] = score(db_path, lead_dir / "lead_score_report.md", execute)
    with sqlite3.connect(db_path) as conn:
        after = lead_count(conn)
    status = "target_leads_reached" if after >= target_leads else "lead_surfaces_exhausted"
    report = lead_dir / "lead_mode_operator_report.md"
    lines = [
        "# Target-Gap Lead Mode Operator",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Stop status: `{status}`",
        f"- Lead count before: `{before}`",
        f"- Lead count after: `{after}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
    ]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": status, "lead_count_before": before, "lead_count_after": after, "phases": phases, "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--target-leads", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run_operator(Path(args.db), Path(args.config), args.target_leads, bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
