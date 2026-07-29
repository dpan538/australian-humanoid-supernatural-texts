#!/usr/bin/env python3
"""Safely enrich materialized structured endpoint near misses."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from lib.structured_endpoint_recovery import process_near_miss, write_enriched_outputs
from migrate_structured_near_miss_v1 import migrate


DEFAULT_CONFIG = ROOT / "config" / "noauth_structured_endpoints.yml"
REPORT = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints" / "enrichment_report.md"
REVIEW_DIR = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def queued_near_misses(conn: sqlite3.Connection, run_id: str, limit: int) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [
        dict(row)
        for row in conn.execute(
            """
            SELECT *
            FROM structured_endpoint_near_misses
            WHERE run_id=? AND recovery_status='queued'
            ORDER BY recoverability_score DESC, created_at ASC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
    ]


def enrich(db_path: Path, run_id: str, limit: int, execute: bool, config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    migrate(db_path)
    config = load_config(config_path)
    session = requests.Session()
    processed: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        if not table_exists(conn, "structured_endpoint_near_misses"):
            raise RuntimeError("structured_endpoint_near_misses table missing; run migration/materialization first")
        rows = queued_near_misses(conn, run_id, limit)
        for near in rows:
            result = process_near_miss(conn, near, config, run_id, session, execute)
            processed.append(result)
        if execute:
            conn.commit()
        outputs = write_enriched_outputs(conn, run_id, REVIEW_DIR)
        total_enriched = int(conn.execute("SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=?", (run_id,)).fetchone()[0] or 0)
        target_gap = int(conn.execute("SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=? AND target_gap_eligible=1", (run_id,)).fetchone()[0] or 0)
        remaining_recoverable = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM structured_endpoint_near_misses
                WHERE run_id=? AND recovery_status IN ('queued','paused_fetch_failed','enriched_near_miss') AND recoverability_score >= 50
                """,
                (run_id,),
            ).fetchone()[0]
            or 0
        )
    statuses = Counter(row.get("status") for row in processed)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Structured Endpoint Near-Miss Enrichment Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Limit: `{limit}`",
        f"- Near misses processed: `{len(processed)}`",
        f"- Enriched records total: `{total_enriched}`",
        f"- Target-gap enriched records: `{target_gap}`",
        f"- Recoverable near misses remaining: `{remaining_recoverable}`",
        f"- Target candidate CSV: `{REVIEW_DIR / 'enriched_target_gap_candidates.csv'}`",
        f"- Remaining near-miss CSV: `{REVIEW_DIR / 'enriched_near_misses_remaining.csv'}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Statuses",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in statuses.most_common()] or ["- None"])
    lines.extend(
        [
            "",
            "## Safety",
            "- Robots are checked before public detail fetches.",
            "- No login, paywall, API-key, Trove API, Google API, or Bing API endpoints are used.",
            "- Detail bodies are not stored; metadata and snippets are capped.",
            "- Target-gap rows, if any, are staged only in provisional_records with harvest_mode `structured_endpoint_enriched_gap`.",
        ]
    )
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "processed": len(processed),
        "enriched_records": total_enriched,
        "target_gap_records": target_gap,
        "recoverable_remaining": remaining_recoverable,
        "statuses": dict(statuses),
        "outputs": outputs,
        "report": str(REPORT),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    summary = enrich(Path(args.db), args.run_id, args.limit, execute=bool(args.execute and not args.dry_run), config_path=Path(args.config))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
