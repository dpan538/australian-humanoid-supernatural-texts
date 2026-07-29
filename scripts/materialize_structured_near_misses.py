#!/usr/bin/env python3
"""Materialize structured endpoint near misses from endpoint records."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.structured_endpoint_recovery import build_near_miss, insert_near_miss, source_rows, write_near_miss_csv
from migrate_structured_near_miss_v1 import migrate


DEFAULT_CONFIG = ROOT / "config" / "noauth_structured_endpoints.yml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def materialize(db_path: Path, run_id: str, out: Path, report: Path, execute: bool, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    migrate(db_path)
    config = load_config(config_path)
    materialized: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        records = source_rows(conn, run_id)
        for record in records:
            near = build_near_miss(record, run_id, config)
            if not near:
                continue
            materialized.append(near)
            if execute:
                insert_near_miss(conn, near)
        if execute:
            conn.commit()

    out.parent.mkdir(parents=True, exist_ok=True)
    write_near_miss_csv(out, materialized)

    by_type = Counter(row["near_miss_type"] for row in materialized)
    by_route = Counter(f"{row.get('endpoint_type') or 'UNKNOWN'} / {row.get('source_name') or 'UNKNOWN'}" for row in materialized)
    recoverability = Counter(
        "80-100" if row["recoverability_score"] >= 80 else "50-79" if row["recoverability_score"] >= 50 else "1-49" if row["recoverability_score"] > 0 else "0"
        for row in materialized
    )
    previous_reported = sum(1 for row in materialized if row.get("inferred_year") or (row.get("controlled_term_hits") not in {"", "[]", None}))
    old_near_csv = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints" / f"{run_id}_structured_endpoint_near_misses.csv"
    old_rows = 0
    if old_near_csv.exists():
        old_rows = max(0, len(old_near_csv.read_text(encoding="utf-8", errors="replace").splitlines()) - 1)
    top = sorted(materialized, key=lambda row: (float(row.get("recoverability_score") or 0), row.get("source_tier") or ""), reverse=True)[:25]
    lines = [
        "# Structured Endpoint Near-Miss Materialization Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Total endpoint records: `{len(records)}`",
        f"- Near misses materialized: `{len(materialized)}`",
        f"- Previous reported near-miss-compatible rows: `{previous_reported}`",
        f"- Old near_misses CSV rows: `{old_rows}`",
        f"- Previous reported near-miss count reconciled: `{'yes' if previous_reported else 'no'}`",
        f"- Output CSV: `{out}`",
        "",
        "## Near Misses By Type",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in by_type.most_common()] or ["- None"])
    lines.extend(["", "## Recoverability Distribution"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(recoverability.items(), reverse=True)] or ["- None"])
    lines.extend(["", "## Top Source Routes"])
    lines.extend([f"- `{key}`: {value}" for key, value in by_route.most_common(20)] or ["- None"])
    lines.extend(["", "## Top 25 Recoverable Near Misses"])
    lines.extend(
        [
            f"- `{row['recoverability_score']}` `{row['near_miss_type']}` {row.get('endpoint_type') or 'UNKNOWN'} / {row.get('source_name') or 'UNKNOWN'}: {row.get('title') or row.get('item_url') or row['near_miss_id']}"
            for row in top
        ]
        or ["- None"]
    )
    lines.extend(
        [
            "",
            "## Reconciliation Note",
            "- The prior checkpoint near-miss count is a record-level derivation, not a materialized table.",
            "- The old CSV could be empty because it only exported controlled-term hits; date-only near misses were omitted.",
            "- This report makes `structured_endpoint_near_misses` and the materialized review CSV the durable recovery surface.",
        ]
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"endpoint_records": len(records), "materialized": len(materialized), "by_type": dict(by_type), "out": str(out), "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    summary = materialize(Path(args.db), args.run_id, Path(args.out), Path(args.report), execute=bool(args.execute and not args.dry_run), config_path=Path(args.config))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
