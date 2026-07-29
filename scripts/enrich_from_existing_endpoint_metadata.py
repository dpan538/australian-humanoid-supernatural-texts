#!/usr/bin/env python3
"""Re-score materialized near misses using already-fetched endpoint metadata only."""

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
from lib.structured_robots_rescue import (
    ensure_near_miss_tables,
    joined_near_misses,
    load_default_config,
    parse_existing_metadata,
    score_metadata_only,
    write_enriched_csv,
)


def enrich_existing_metadata(db_path: Path, run_id: str, out: Path, report: Path, execute: bool, config_path: Path | None = None) -> dict[str, Any]:
    ensure_near_miss_tables(db_path)
    config = load_default_config(config_path)
    processed: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = joined_near_misses(conn, run_id)
        for near in rows:
            metadata = parse_existing_metadata(near)
            result = score_metadata_only(conn, near, metadata, run_id, config, "structured_existing_metadata_gap", execute)
            processed.append(result)
        if execute:
            conn.commit()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_enriched_csv(out, processed)
    targets = [row for row in processed if int(row.get("target_gap_eligible") or 0) == 1]
    remaining = Counter(str(row.get("remaining_gate") or "TARGET_GAP_ELIGIBLE") for row in processed)
    lines = [
        "# Existing Endpoint Metadata Enrichment Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Near misses processed: `{len(processed)}`",
        f"- Enriched records written: `{len(processed) if execute else 0}`",
        f"- Target-gap records staged: `{len(targets)}`",
        f"- Output CSV: `{out}`",
        "- Network fetches performed: `0`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Remaining Near Misses By Missing Gate",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(remaining.items()) if key != "TARGET_GAP_ELIGIBLE"] or ["- None"])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "processed": len(processed),
        "enriched_records": len(processed) if execute else 0,
        "target_gap_records": len(targets),
        "remaining_by_gate": dict(remaining),
        "out": str(out),
        "report": str(report),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    args = parser.parse_args()
    print(
        json.dumps(
            enrich_existing_metadata(Path(args.db), args.run_id, Path(args.out), Path(args.report), bool(args.execute and not args.dry_run), Path(args.config) if args.config else None),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
