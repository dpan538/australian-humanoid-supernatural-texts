#!/usr/bin/env python3
"""Score target-gap leads and write prioritized lead queues."""

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
from lib.target_gap_leads import LEAD_FIELDS, read_leads, score_lead, write_leads_csv
from migrate_target_gap_leads_v1 import migrate


def score(db_path: Path, out: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
        scored = []
        for row in leads:
            lead_score, bucket = score_lead(row)
            row["lead_score"] = lead_score
            row["priority_bucket"] = bucket
            scored.append(row)
            if execute:
                conn.execute("UPDATE target_gap_leads SET lead_score=?, priority_bucket=?, updated_at=? WHERE lead_id=?", (lead_score, bucket, now_iso(), row["lead_id"]))
        if execute:
            conn.commit()
    scored.sort(key=lambda row: (-float(row.get("lead_score") or 0), str(row.get("lead_id") or "")))
    lead_dir = out.parent
    write_leads_csv(lead_dir / "target_gap_leads_scored.csv", scored)
    write_leads_csv(lead_dir / "priority_leads_top_100.csv", [row for row in scored if row.get("priority_bucket") == "PRIORITY_LEAD"][:100])
    write_leads_csv(lead_dir / "blocked_by_constraint.csv", [row for row in scored if row.get("priority_bucket") == "BLOCKED_CONSTRAINT"])
    write_leads_csv(lead_dir / "robots_clarification_queue.csv", [row for row in scored if row.get("priority_bucket") == "BLOCKED_ROBOTS"])
    write_leads_csv(lead_dir / "d_class_decomposition_queue.csv", [row for row in scored if "d_class" in str(row.get("evidence_gap") or "")])
    write_leads_csv(lead_dir / "metadata_only_1955_1976_leads.csv", [row for row in scored if row.get("lead_type") == "METADATA_ONLY_1955_1976_LEAD"])
    bucket_counts = Counter(row.get("priority_bucket") or "" for row in scored)
    blocker_counts = Counter(row.get("constraint_blocker") or "" for row in scored)
    lines = [
        "# Target-Gap Lead Score Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Leads scored: `{len(scored)}`",
        f"- Priority leads: `{bucket_counts.get('PRIORITY_LEAD', 0)}`",
        f"- Good leads: `{bucket_counts.get('GOOD_LEAD', 0)}`",
        f"- Blocked robots leads: `{bucket_counts.get('BLOCKED_ROBOTS', 0)}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Priority Buckets",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(bucket_counts.items())] or ["- None"])
    lines.extend(["", "## Top Blockers"])
    lines.extend([f"- `{key}`: {value}" for key, value in blocker_counts.most_common(12)] or ["- None"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads_scored": len(scored), "priority_leads": bucket_counts.get("PRIORITY_LEAD", 0), "bucket_counts": dict(bucket_counts), "blocker_counts": dict(blocker_counts), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(score(Path(args.db), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
