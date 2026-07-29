#!/usr/bin/env python3
"""Decide whether autonomous target-gap lead mode should start now."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.target_gap_leads import load_config, read_leads
from migrate_target_gap_leads_v1 import migrate


def decide(db_path: Path, config_path: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    config = load_config(config_path)
    target = int(config.get("lead_mode", {}).get("target_leads") or 2000)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    total = len(leads)
    canonical = sum(1 for row in leads if row.get("duplicate_status") in {"canonical", "unique"})
    priority = sum(1 for row in leads if row.get("priority_bucket") == "PRIORITY_LEAD")
    unchecked = sum(1 for row in leads if row.get("duplicate_status") in {"", "unchecked", None})
    blockers = Counter(row.get("constraint_blocker") or "unknown" for row in leads)
    analysis_blockers = blockers.get("missing_date", 0) + blockers.get("missing_term", 0) + blockers.get("strict_record_gate_not_met", 0)
    metadata_done = (ROOT / "data" / "processed" / "v2" / "autoharvest" / "metadata_only_1955_1976" / "metadata_only_1955_1976_summary.md").exists()
    if total >= target and priority >= 250:
        recommendation = "do_not_start_lead_mode_yet"
        reason = "existing lead layer is already large; analyze and dedupe first."
    elif canonical and canonical < target:
        recommendation = "start_lead_mode_after_preflight"
        reason = "canonical leads remain below the configured target."
    elif priority < 100:
        recommendation = "start_lead_mode_after_preflight"
        reason = "priority leads remain below the useful threshold."
    elif unchecked:
        recommendation = "do_not_start_lead_mode_yet"
        reason = "duplicate/noise rate is not fully resolved."
    elif not metadata_done:
        recommendation = "do_not_start_lead_mode_yet"
        reason = "metadata-only layer has not been built."
    elif analysis_blockers >= max(1, total // 2):
        recommendation = "do_not_start_lead_mode_yet"
        reason = "top blockers are analysis problems rather than source-discovery problems."
    else:
        recommendation = "lead_mode_optional_later"
        reason = "lead acquisition may be useful only after a specific high-yield route is identified."
    lines = [
        "# Lead Mode Start Decision",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Configured target leads: `{target}`",
        f"- Total leads: `{total}`",
        f"- Canonical/unique leads: `{canonical or 'dedupe not run'}`",
        f"- Priority leads: `{priority}`",
        f"- Recommendation: `{recommendation}`",
        f"- Reason: {reason}",
        "",
        "## Rule Check",
        f"- Total leads >= target: `{str(total >= target).lower()}`",
        f"- Priority leads >= 250: `{str(priority >= 250).lower()}`",
        f"- Duplicate/noise rate unknown: `{str(bool(unchecked)).lower()}`",
        f"- Metadata-only layer built: `{str(metadata_done).lower()}`",
        f"- Analysis blockers dominate: `{str(analysis_blockers >= max(1, total // 2)).lower()}`",
        "",
        "## Action",
        "- Do not run `make lead-mode-start` automatically.",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"recommendation": recommendation, "reason": reason, "total_leads": total, "priority_leads": priority, "canonical_leads": canonical, "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(decide(Path(args.db), Path(args.config), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
