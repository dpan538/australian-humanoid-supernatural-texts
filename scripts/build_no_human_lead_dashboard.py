#!/usr/bin/env python3
"""Build a no-row-review dashboard for target-gap lead mode."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from lib.target_gap_leads import load_config, read_leads
from migrate_target_gap_leads_v1 import migrate


def dashboard(db_path: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
        strict_records = int(conn.execute("SELECT COUNT(*) FROM provisional_records WHERE COALESCE(target_gap_eligible,0)=1 AND COALESCE(harvest_mode,'') LIKE 'structured%'").fetchone()[0] or 0) if table_exists(conn, "provisional_records") else 0
    bucket_counts = Counter(row.get("priority_bucket") or "" for row in leads)
    blocker_counts = Counter(row.get("constraint_blocker") or "" for row in leads)
    route_counts = Counter(row.get("route_family") or row.get("source_name") or "unknown" for row in leads)
    years = [int(row["inferred_year"]) for row in leads if str(row.get("inferred_year") or "").isdigit()]
    states = Counter(row.get("target_state") or "unknown" for row in leads)
    target_leads = int(load_config().get("lead_mode", {}).get("target_leads") or 2000)
    lead_pool_populated = len(leads) >= target_leads
    lines = [
        "# No-Human Target-Gap Lead Dashboard",
        "",
        f"- Generated: `{now_iso()}`",
        "",
        "## 1. Strict Mode Result",
        f"- Strict target-gap records: `{strict_records}`",
        "- Continue strict records mode: `no`",
        "",
        "## 2. Why Strict Records Mode Produced 0 Records",
        "- Current no-credential surfaces do not combine explicit 1926-1976 temporal evidence, controlled terms, item-level evidence URLs, and safe source chains under robots-safe constraints.",
        "",
        "## 3. Target-Gap Leads",
        f"- Total target-gap leads: `{len(leads)}`",
        f"- Configured lead target: `{target_leads}`",
        f"- Existing leads exceed target: `{str(lead_pool_populated).lower()}`",
        "",
        "## 4. Priority Leads",
        f"- Priority leads: `{bucket_counts.get('PRIORITY_LEAD', 0)}`",
        f"- Good leads: `{bucket_counts.get('GOOD_LEAD', 0)}`",
        "",
        "## 5. Main Blockers",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in blocker_counts.most_common(10)] or ["- None"])
    lines.extend(["", "## 6. Best Source Clusters"])
    lines.extend([f"- `{key}`: {value} leads" for key, value in route_counts.most_common(10)] or ["- None"])
    lines.extend(
        [
            "",
            "## 7. 1926-1976 Lead Coverage",
            f"- Earliest lead year: `{min(years) if years else 'unknown'}`",
            f"- Latest lead year: `{max(years) if years else 'unknown'}`",
            f"- Dated leads: `{len(years)}`",
            "",
            "## 8. Priority-State Coverage",
        ]
    )
    for state in ["WA", "SA", "NT", "TAS", "ACT"]:
        lines.append(f"- `{state}`: {states.get(state, 0)} leads")
    lines.extend(
        [
            "",
            "## 9. Recommended Next Operating Mode",
            "- Continue strict mode? `no`",
            "- Lead mode? `available later`",
            "- Start lead mode immediately? `no`",
            "- Existing leads exceed the target, so analyze/dedupe them before collecting more.",
            "- Metadata-only 1955-1976 layer? `yes`",
            "- Top-N human review? `optional`",
            "- Trove API? `optional but not default`",
            "",
            "## 10. Exact Next Command",
            "- `make lead-intelligence-all`",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads": len(leads), "priority_leads": bucket_counts.get("PRIORITY_LEAD", 0), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(dashboard(Path(args.db), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
