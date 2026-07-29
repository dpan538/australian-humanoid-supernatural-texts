#!/usr/bin/env python3
"""Freeze final release inputs and block further open-ended crawling."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from lib.final_release import count_table, frontend_map_points
from migrate_research_volume_expansion_v1 import migrate as migrate_volume


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def freeze(db_path: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    migrate_volume(db_path)
    with sqlite3.connect(db_path) as conn:
        accepted = count_table(conn, "records")
        target_gap = count_table(conn, "target_gap_leads")
        research_volume = count_table(conn, "research_volume_items")
        metadata_only = conn.execute("SELECT COUNT(*) FROM target_gap_leads WHERE lead_type='METADATA_ONLY_1955_1976_LEAD'").fetchone()[0] if table_exists(conn, "target_gap_leads") else 0
        canonical = conn.execute("SELECT COUNT(*) FROM target_gap_leads WHERE duplicate_status IN ('canonical','unique')").fetchone()[0] if table_exists(conn, "target_gap_leads") else 0
    map_rows = len(frontend_map_points(ROOT / "public" / "data" / "frontend-data.json"))
    payload = {
        "freeze_id": "release_freeze_001",
        "created_at": now_iso(),
        "git_commit": git_commit(),
        "accepted_records_count": accepted,
        "public_map_rows_count": map_rows,
        "target_gap_leads_count": target_gap,
        "canonical_leads_count": canonical,
        "metadata_only_leads_count": metadata_only,
        "research_volume_items_count": research_volume,
        "crawler_status": "frozen",
        "allowed_post_freeze_actions": ["bounded_patch_import", "dedupe", "map_reconciliation", "redirect_generation", "export_rebuild", "audit"],
        "disallowed_post_freeze_actions": ["long_marathon", "unrestricted_crawl", "new_source_discovery_without_cap", "public_record_autopromotion", "map_flag_autopromotion"],
    }
    if execute:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "freeze_state.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(freeze(Path(args.db), Path(args.out_dir), args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
