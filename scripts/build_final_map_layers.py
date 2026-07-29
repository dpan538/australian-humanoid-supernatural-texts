#!/usr/bin/env python3
"""Build final public map and non-public overlay map layers."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.final_release import frontend_map_points, stable_id
from migrate_release_layers_v1 import migrate


ACCEPTED_FIELDS = ["record_id", "title", "latitude", "longitude", "place_name", "source"]
OVERLAY_FIELDS = ["overlay_id", "source_table", "source_row_id", "title", "target_state", "target_locality", "place_signal", "display_label", "map_display_status"]


def build(db_path: Path, frontend_map: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    accepted_points = frontend_map_points(frontend_map)
    accepted = [
        {
            "record_id": row.get("record_id") or row.get("id") or "",
            "title": row.get("title") or "",
            "latitude": row.get("lat") or row.get("latitude") or row.get("map_latitude") or "",
            "longitude": row.get("lng") or row.get("longitude") or row.get("map_longitude") or "",
            "place_name": row.get("place_name") or row.get("map_place_name") or "",
            "source": str(frontend_map),
        }
        for row in accepted_points
    ]
    metadata_overlay = []
    lead_overlay = []
    unmapped = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for row in conn.execute("SELECT * FROM release_metadata_gap_items"):
            item = dict(row)
            target = metadata_overlay if (item.get("target_locality") or item.get("place_signal")) else unmapped
            target.append({"overlay_id": stable_id("mapmeta_", item.get("release_item_id")), "source_table": "release_metadata_gap_items", "source_row_id": item.get("release_item_id"), "title": item.get("title"), "target_state": item.get("target_state"), "target_locality": item.get("target_locality"), "place_signal": item.get("place_signal"), "display_label": "Metadata-only lead overlay", "map_display_status": "overlay_not_public_map"})
        for row in conn.execute("SELECT * FROM release_lead_overlay_items"):
            item = dict(row)
            target = lead_overlay if item.get("target_locality") else unmapped
            target.append({"overlay_id": stable_id("maplead_", item.get("release_lead_id")), "source_table": "release_lead_overlay_items", "source_row_id": item.get("release_lead_id"), "title": item.get("title"), "target_state": item.get("target_state"), "target_locality": item.get("target_locality"), "place_signal": item.get("target_locality"), "display_label": "Research lead overlay", "map_display_status": "overlay_not_public_map"})
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "accepted_public_map.csv", accepted, ACCEPTED_FIELDS)
    write_csv(out_dir / "metadata_place_overlay.csv", metadata_overlay, OVERLAY_FIELDS)
    write_csv(out_dir / "lead_place_overlay.csv", lead_overlay, OVERLAY_FIELDS)
    write_csv(out_dir / "unmapped_gap_items.csv", unmapped, OVERLAY_FIELDS)
    counts = {"accepted_public_map": len(accepted), "metadata_place_overlay": len(metadata_overlay), "lead_place_overlay": len(lead_overlay), "unmapped_gap_items": len(unmapped)}
    (out_dir / "map_layer_counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    overlay_json = {"generated_at": now_iso(), "accepted_public_map_count": len(accepted), "metadata_place_overlay": metadata_overlay, "lead_place_overlay": lead_overlay, "unmapped_gap_items": unmapped}
    (out_dir / "map_overlay_frontend_data.json").write_text(json.dumps(overlay_json, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Final Map Layers Summary", "", f"- Generated: `{now_iso()}`", f"- Accepted public map count: `{len(accepted)}`", f"- Metadata overlay count: `{len(metadata_overlay)}`", f"- Lead overlay count: `{len(lead_overlay)}`", f"- Unmapped gap items: `{len(unmapped)}`", "- Public map flags mutated: `no`", "- Frontend map file replaced: `no`"]
    (out_dir / "final_map_layers_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--frontend-map", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), Path(args.frontend_map), Path(args.out_dir), args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
