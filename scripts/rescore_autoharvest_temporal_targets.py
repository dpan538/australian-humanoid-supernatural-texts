#!/usr/bin/env python3
"""Reclassify existing autoharvest provisional records under target-gap rules."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.autoharvest_gap import classify_gap_candidate, insert_temporal_evidence, update_provisional_gap_fields
from migrate_autoharvest_gap_v2 import migrate


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def reclassify(db_path: Path, config_path: Path, run_id: str, out_path: Path, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = load_config(config_path)
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM provisional_records WHERE run_id=?", (run_id,)).fetchall()]
        for row in rows:
            candidate = {
                **row,
                "candidate_id": row.get("candidate_id"),
                "title": row.get("title"),
                "snippet": row.get("summary") or "",
                "url": row.get("source_url"),
                "source_name": row.get("source_name"),
                "source_tier": row.get("source_tier"),
                "route_family": row.get("route_family"),
                "target_state": row.get("target_state"),
                "date_published": row.get("date_published"),
                "inferred_year": row.get("inferred_year"),
                "evidence_source_name": row.get("evidence_source_name"),
                "evidence_source_url": row.get("evidence_source_url"),
                "ethics_status": row.get("ethics_status"),
                "duplicate_status": "unique",
                "evidence_or_discovery": "evidence_possible",
            }
            route = {
                "route_id": row.get("route_family") or "",
                "source_name": row.get("source_name"),
                "source_tier": row.get("source_tier"),
                "route_family": row.get("route_family"),
                "state": row.get("target_state"),
                "evidence_or_discovery": "evidence_possible",
            }
            decision = classify_gap_candidate(candidate, route, config, page_text=row.get("summary") or "")
            bucket = "TARGET_GAP_EFFECTIVE" if decision.target_gap_eligible else decision.auxiliary_status or "REJECTED_OR_HELD"
            counts[bucket] += 1
            examples.setdefault(bucket, [])
            if len(examples[bucket]) < 5:
                examples[bucket].append(f"{row.get('provisional_record_id')}: {row.get('title')} ({decision.reason})")
            if execute:
                update_provisional_gap_fields(conn, row["candidate_id"], decision, harvest_mode="legacy_reclassified")
                insert_temporal_evidence(conn, run_id, row["candidate_id"], row["provisional_record_id"], decision, row.get("source_url") or "")
        if execute:
            conn.commit()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    total = sum(counts.values())
    lines = [
        "# Autoharvest Temporal Reclassification",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Total previous provisional records: `{total}`",
        f"- TARGET_GAP_EFFECTIVE count: `{counts.get('TARGET_GAP_EFFECTIVE', 0)}`",
        f"- GENERAL_SAFE_PROVISIONAL count: `{counts.get('GENERAL_SAFE_PROVISIONAL', 0)}`",
        f"- UNDATED_AUXILIARY count: `{counts.get('UNDATED_AUXILIARY', 0)}`",
        f"- PLACE_ONLY_AUXILIARY count: `{counts.get('PLACE_ONLY_AUXILIARY', 0)}`",
        f"- ROUTE_DISCOVERY_ONLY count: `{counts.get('ROUTE_DISCOVERY_ONLY', 0)}`",
        f"- Rejected/noise/duplicate count: `{counts.get('REJECTED_OR_HELD', 0)}`",
        "",
        "## Examples",
    ]
    for bucket, bucket_examples in sorted(examples.items()):
        lines.append(f"### {bucket}")
        lines.extend(f"- {item}" for item in bucket_examples)
    lines.extend(["", "## Recommendation", "Start `noauth_gap_marathon_001`; do not count auxiliary rows toward target-gap effective growth."])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = reclassify(Path(args.db), Path(args.config), args.run_id, Path(args.out), execute=bool(args.execute and not args.dry_run))
    print(f"Wrote temporal reclassification report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
