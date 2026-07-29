#!/usr/bin/env python3
"""Repair and diagnose AtoM/AtoM near misses using stored metadata first."""

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
    diagnose_robots,
    ensure_near_miss_tables,
    joined_near_misses,
    load_default_config,
    parse_existing_metadata,
    score_metadata_only,
    url_issue,
    write_enriched_csv,
)


def repair_atom(db_path: Path, run_id: str, out_dir: Path, execute: bool, config_path: Path | None = None) -> dict[str, Any]:
    ensure_near_miss_tables(db_path)
    config = load_default_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    enriched: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    remaining_rows: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        rows = joined_near_misses(conn, run_id, "n.endpoint_type='ATOM_AtoM'")
        for near in rows:
            metadata = parse_existing_metadata(near)
            detail_issue = url_issue(near)
            robots_status = ""
            if near.get("detail_url") and not detail_issue:
                robots_status = diagnose_robots(str(near.get("detail_url"))).robots_status
            result = score_metadata_only(conn, near, metadata, run_id, config, "structured_atom_atomm_repair_gap", execute)
            result["url_issue"] = detail_issue
            result["robots_status"] = robots_status
            result["adapter_diagnosis"] = "anchor_navigation_noise" if str(near.get("title") or "").lower().startswith("skip to") else "metadata_sparse_or_detail_required"
            enriched.append(result)
            if int(result.get("target_gap_eligible") or 0) == 1:
                target_rows.append(result)
            else:
                remaining_rows.append(result)
            diagnostics.append(result)
        if execute:
            conn.commit()
    write_enriched_csv(out_dir / "atom_atomm_enriched_records.csv", enriched)
    write_enriched_csv(out_dir / "atom_atomm_target_candidates.csv", target_rows)
    write_enriched_csv(out_dir / "atom_atomm_remaining_near_misses.csv", remaining_rows)
    diagnosis_counts = Counter(row["adapter_diagnosis"] for row in diagnostics)
    notes = [
        "# AtoM Adapter Patch Notes",
        "",
        "- Existing AtoM rows are dominated by broad browse/navigation anchors when titles such as `Skip to Navigation` appear.",
        "- Adapter repair should filter accessibility/navigation anchors and require item-like AtoM paths or stable identifiers before materializing records.",
        "- Detail fetch remains blocked unless robots is explicitly allowed and the URL is same-domain, non-auth, and item-like.",
    ]
    (out_dir / "atom_atomm_adapter_patch_notes.md").write_text("\n".join(notes) + "\n", encoding="utf-8")
    lines = [
        "# AtoM/AtoM Repair Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- AtoM near misses processed: `{len(enriched)}`",
        f"- Target candidates staged: `{len(target_rows)}`",
        f"- Remaining near misses: `{len(remaining_rows)}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Adapter Diagnosis",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(diagnosis_counts.items())] or ["- None"])
    (out_dir / "atom_atomm_repair_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "processed": len(enriched),
        "target_gap_records": len(target_rows),
        "remaining": len(remaining_rows),
        "diagnosis": dict(diagnosis_counts),
        "out_dir": str(out_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    args = parser.parse_args()
    print(json.dumps(repair_atom(Path(args.db), args.run_id, Path(args.out_dir), bool(args.execute and not args.dry_run), Path(args.config) if args.config else None), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
