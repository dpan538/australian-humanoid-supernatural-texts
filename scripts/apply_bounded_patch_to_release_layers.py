#!/usr/bin/env python3
"""Apply bounded patch rows into internal release layers only."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.final_release import read_csv, stable_id
from migrate_release_layers_v1 import migrate


INSERTED_FIELDS = ["release_id", "release_table", "source_table", "source_row_id", "patch_layer", "public_record_status", "map_display_status"]
REJECTED_FIELDS = ["source_table", "source_row_id", "patch_layer", "rejected_reason"]


def apply_patch_rows(db_path: Path, patch_plan: Path, run_id: str, execute: bool, out_dir: Path | None = None) -> dict[str, object]:
    migrate(db_path)
    rows = read_csv(patch_plan)
    inserted = []
    rejected = []
    with sqlite3.connect(db_path) as conn:
        for row in rows:
            if "ethics_sensitive" in str(row.get("evidence_gap") or ""):
                rejected.append({**row, "rejected_reason": "ethics_sensitive"})
                continue
            ts = now_iso()
            if row.get("patch_layer") == "metadata_only_gap":
                rid = stable_id("relmeta_", run_id, row.get("source_table"), row.get("source_row_id"))
                if execute:
                    conn.execute(
                        """
                        INSERT INTO release_metadata_gap_items (
                            release_item_id, source_lead_id, source_table, source_row_id, release_layer, title, description, url,
                            source_name, source_tier, source_family, route_family, inferred_year, coverage_start_year,
                            coverage_end_year, target_state, target_locality, temporal_signal, term_signal, place_signal,
                            evidence_gap, display_label, public_record_status, map_display_status, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(release_item_id) DO UPDATE SET updated_at=excluded.updated_at
                        """,
                        (
                            rid, row.get("source_lead_id"), row.get("source_table"), row.get("source_row_id"), "metadata_only_gap",
                            row.get("title"), row.get("description"), row.get("url"), row.get("source_name"), row.get("source_tier"),
                            row.get("source_family"), row.get("route_family"), row.get("inferred_year") or None, row.get("coverage_start_year") or None,
                            row.get("coverage_end_year") or None, row.get("target_state"), row.get("target_locality"), row.get("temporal_signal"),
                            row.get("term_signal"), row.get("place_signal"), row.get("evidence_gap"), "Metadata-only lead",
                            "not_public_record", "not_public_map", ts, ts,
                        ),
                    )
                inserted.append({"release_id": rid, "release_table": "release_metadata_gap_items", "source_table": row.get("source_table"), "source_row_id": row.get("source_row_id"), "patch_layer": row.get("patch_layer"), "public_record_status": "not_public_record", "map_display_status": "not_public_map"})
            elif row.get("patch_layer") == "lead_overlay":
                rid = stable_id("rellead_", run_id, row.get("source_table"), row.get("source_row_id"))
                if execute:
                    conn.execute(
                        """
                        INSERT INTO release_lead_overlay_items (
                            release_lead_id, source_lead_id, source_table, source_row_id, title, url, source_name,
                            source_family, route_family, inferred_year, coverage_start_year, coverage_end_year,
                            target_state, target_locality, lead_score, priority_bucket, evidence_gap, blocker,
                            display_label, public_record_status, map_display_status, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(release_lead_id) DO UPDATE SET updated_at=excluded.updated_at
                        """,
                        (
                            rid, row.get("source_lead_id"), row.get("source_table"), row.get("source_row_id"), row.get("title"),
                            row.get("url"), row.get("source_name"), row.get("source_family"), row.get("route_family"),
                            row.get("inferred_year") or None, row.get("coverage_start_year") or None, row.get("coverage_end_year") or None,
                            row.get("target_state"), row.get("target_locality"), row.get("priority_score") or 0, row.get("priority_bucket"),
                            row.get("evidence_gap"), row.get("blocker"), "Research lead", "not_public_record", "not_public_map", ts, ts,
                        ),
                    )
                inserted.append({"release_id": rid, "release_table": "release_lead_overlay_items", "source_table": row.get("source_table"), "source_row_id": row.get("source_row_id"), "patch_layer": row.get("patch_layer"), "public_record_status": "not_public_record", "map_display_status": "not_public_map"})
            elif row.get("patch_layer") == "source_intelligence":
                rid = stable_id("relsrc_", run_id, row.get("source_table"), row.get("source_row_id"))
                if execute:
                    conn.execute(
                        """
                        INSERT INTO release_source_intelligence_items (
                            source_intel_id, source_table, source_row_id, source_name, source_family, route_family,
                            state, blocker, opportunity_type, count_weight, notes, created_at, updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(source_intel_id) DO UPDATE SET updated_at=excluded.updated_at
                        """,
                        (rid, row.get("source_table"), row.get("source_row_id"), row.get("source_name"), row.get("source_family"), row.get("route_family"), row.get("target_state"), row.get("blocker"), "bounded_patch_source_intelligence", 1.0, row.get("selection_reason"), ts, ts),
                    )
                inserted.append({"release_id": rid, "release_table": "release_source_intelligence_items", "source_table": row.get("source_table"), "source_row_id": row.get("source_row_id"), "patch_layer": row.get("patch_layer"), "public_record_status": "not_public_record", "map_display_status": "not_public_map"})
        if execute:
            conn.commit()
    out_dir = out_dir or ROOT / "data" / "processed" / "v2" / "release_coverage_1926_2011"
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "final_patch_inserted_items.csv", inserted, INSERTED_FIELDS)
    write_csv(out_dir / "final_patch_rejected_items.csv", rejected, REJECTED_FIELDS)
    report = out_dir / "final_patch_apply_report.md"
    report.write_text("\n".join(["# Final Patch Apply Report", "", f"- Generated: `{now_iso()}`", f"- Run ID: `{run_id}`", f"- Inserted release-layer items: `{len(inserted)}`", f"- Rejected items: `{len(rejected)}`", "- Accepted public records created: `0`", "- Public map flags changed: `0`"]) + "\n", encoding="utf-8")
    return {"inserted": len(inserted), "rejected": len(rejected), "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--patch-plan", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", default=str(ROOT / "data" / "processed" / "v2" / "release_coverage_1926_2011"))
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(apply_patch_rows(Path(args.db), Path(args.patch_plan), args.run_id, args.execute, Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
