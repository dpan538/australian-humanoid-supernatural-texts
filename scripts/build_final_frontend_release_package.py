#!/usr/bin/env python3
"""Build final frontend release candidate package without overwriting public data."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.final_release import read_csv


DISCLAIMER = """# Release Disclaimer

- Accepted public records are distinct from metadata-only leads.
- Metadata-only layer is not proof and not an accepted public record.
- Map overlays are not habitat/proof maps.
- Source-chain gaps remain visible.
- 1926-2011 coverage includes multiple evidence layers.
"""


def load_json(path: Path) -> object:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def build(db_path: Path, map_layers: Path, redirect_dir: Path, coverage_dir: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    frontend_data = load_json(ROOT / "public" / "data" / "frontend-data.json")
    map_overlay = load_json(map_layers / "map_overlay_frontend_data.json")
    redirects = load_json(redirect_dir / "frontend_redirects.json")
    coverage_rows = read_csv(coverage_dir / "release_coverage_1926_2011.csv")
    source_counts = read_csv(coverage_dir / "release_coverage_by_layer.csv")
    counts = {
        "generated_at": now_iso(),
        "accepted_public_records": len(frontend_data.get("records", [])) if isinstance(frontend_data, dict) else 0,
        "accepted_public_map": len(frontend_data.get("map_points", [])) if isinstance(frontend_data, dict) else 0,
        "metadata_overlay": len(map_overlay.get("metadata_place_overlay", [])) if isinstance(map_overlay, dict) else 0,
        "lead_overlay": len(map_overlay.get("lead_place_overlay", [])) if isinstance(map_overlay, dict) else 0,
        "coverage_bands": len(coverage_rows),
    }
    package = {
        "schema": "final_release_candidate",
        "generated_at": now_iso(),
        "accepted_public_data": frontend_data,
        "release_layers": {
            "metadata_only_and_lead_layers_are_not_public_records": True,
            "coverage": coverage_rows,
        },
        "disclaimer": DISCLAIMER,
    }
    (out_dir / "frontend-data.release-candidate.json").write_text(json.dumps(package, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "frontend-map-overlays.release-candidate.json").write_text(json.dumps(map_overlay, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "frontend-redirects.release-candidate.json").write_text(json.dumps(redirects, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "release-coverage.release-candidate.json").write_text(json.dumps({"coverage": coverage_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "source-intelligence.release-candidate.json").write_text(json.dumps({"source_layer_counts": source_counts}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "release-counts.json").write_text(json.dumps(counts, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "release-disclaimer.md").write_text(DISCLAIMER, encoding="utf-8")
    summary = ["# Final Release Package Summary", "", f"- Generated: `{now_iso()}`", f"- Accepted public records: `{counts['accepted_public_records']}`", f"- Accepted public map points: `{counts['accepted_public_map']}`", f"- Metadata map overlay items: `{counts['metadata_overlay']}`", f"- Lead map overlay items: `{counts['lead_overlay']}`", "- Public data overwritten: `no`"]
    (out_dir / "final_release_package_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    return {"out_dir": str(out_dir), **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--map-layers", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--coverage-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), Path(args.map_layers), Path(args.redirect_dir), Path(args.coverage_dir), Path(args.out_dir), args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
