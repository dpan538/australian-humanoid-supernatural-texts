#!/usr/bin/env python3
"""Audit the target-gap lead population without promoting records."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.lead_intelligence import counter_rows, group_counter, ignored_as_auxiliary, lead_kind, useful_for_observation, write_count_csv
from lib.target_gap_leads import read_leads
from migrate_target_gap_leads_v1 import migrate


AUDIT_FIELDS = ["metric", "count"]


def audit(db_path: Path, out_dir: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
    kind_counts = Counter(lead_kind(row) for row in leads)
    unique_keys = {row.get("duplicate_key") or row.get("lead_id") for row in leads}
    priority = sum(1 for row in leads if row.get("priority_bucket") == "PRIORITY_LEAD")
    rows = [
        {"metric": "total_leads", "count": len(leads)},
        {"metric": "unique_duplicate_keys", "count": len(unique_keys)},
        {"metric": "priority_leads", "count": priority},
        {"metric": "good_leads", "count": sum(1 for row in leads if row.get("priority_bucket") == "GOOD_LEAD")},
        {"metric": "weak_leads", "count": sum(1 for row in leads if row.get("priority_bucket") == "WEAK_LEAD")},
        {"metric": "hold_leads", "count": sum(1 for row in leads if row.get("priority_bucket") == "HOLD")},
        {"metric": "sensitive_holds", "count": sum(1 for row in leads if row.get("priority_bucket") == "SENSITIVE_HOLD")},
        {"metric": "blocked_robots", "count": sum(1 for row in leads if row.get("priority_bucket") == "BLOCKED_ROBOTS")},
        {"metric": "useful_for_1926_1976_observation", "count": sum(1 for row in leads if useful_for_observation(row))},
        {"metric": "term_signal_no_date", "count": sum(1 for row in leads if row.get("term_signal") and not row.get("temporal_signal") and not row.get("inferred_year"))},
        {"metric": "date_signal_no_term", "count": sum(1 for row in leads if (row.get("temporal_signal") or row.get("inferred_year")) and not row.get("term_signal"))},
        {"metric": "route_family_only_relevance", "count": sum(1 for row in leads if lead_kind(row) == "source_route_lead")},
        {"metric": "source_route_leads", "count": kind_counts.get("source_route_lead", 0)},
        {"metric": "source_chain_remediation_leads", "count": kind_counts.get("source_chain_remediation_lead", 0)},
        {"metric": "robots_permission_leads", "count": kind_counts.get("robots_permission_lead", 0)},
        {"metric": "auxiliary_noise_or_hold", "count": sum(1 for row in leads if ignored_as_auxiliary(row))},
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "lead_population_audit.csv", rows, AUDIT_FIELDS)
    write_count_csv(out_dir / "lead_population_by_type.csv", counter_rows(group_counter(leads, "lead_type")))
    write_count_csv(out_dir / "lead_population_by_blocker.csv", counter_rows(group_counter(leads, "constraint_blocker")))
    write_count_csv(out_dir / "lead_population_by_route_family.csv", counter_rows(group_counter(leads, "route_family")))
    write_count_csv(out_dir / "lead_population_by_source_family.csv", counter_rows(group_counter(leads, "source_family")))
    write_count_csv(out_dir / "lead_population_by_state.csv", counter_rows(group_counter(leads, "target_state")))
    write_count_csv(out_dir / "lead_population_by_term_signal.csv", counter_rows(group_counter(leads, "term_signal")))
    write_count_csv(out_dir / "lead_population_by_temporal_signal.csv", counter_rows(group_counter(leads, "temporal_signal")))
    lines = [
        "# Target-Gap Lead Population Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total leads: `{len(leads)}`",
        f"- Unique duplicate-key clusters: `{len(unique_keys)}`",
        f"- Priority leads: `{priority}`",
        f"- Useful for 1926-1976 observation: `{rows[8]['count']}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Lead Kind Census",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in kind_counts.most_common()] or ["- None"])
    lines.extend(["", "## Key Answers"])
    lines.extend([f"- `{row['metric']}`: {row['count']}" for row in rows])
    (out_dir / "lead_population_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"total_leads": len(leads), "unique_duplicate_keys": len(unique_keys), "priority_leads": priority, "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.db), Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
