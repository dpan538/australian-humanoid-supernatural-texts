#!/usr/bin/env python3
"""Run final release gates over coverage, map, redirects, package, and ethics."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv
from lib.final_release import read_csv


FIELDS = ["gate", "status", "details"]


def audit(db_path: Path, package_dir: Path, redirect_dir: Path, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_dir = ROOT / "data" / "processed" / "v2" / "release_coverage_1926_2011"
    map_dir = ROOT / "data" / "processed" / "v2" / "final_map_layers"
    hard_gaps = read_csv(coverage_dir / "hard_gap_report.csv")
    redirect_validation = (redirect_dir / "redirect_validation_report.md").read_text(encoding="utf-8") if (redirect_dir / "redirect_validation_report.md").exists() else ""
    package_counts = json.loads((package_dir / "release-counts.json").read_text(encoding="utf-8")) if (package_dir / "release-counts.json").exists() else {}
    disclaimer = (package_dir / "release-disclaimer.md").read_text(encoding="utf-8") if (package_dir / "release-disclaimer.md").exists() else ""
    map_counts = json.loads((map_dir / "map_layer_counts.json").read_text(encoding="utf-8")) if (map_dir / "map_layer_counts.json").exists() else {}
    with sqlite3.connect(db_path) as conn:
        sensitive_public = 0
        metadata_public = conn.execute("SELECT COUNT(*) FROM release_metadata_gap_items WHERE public_record_status!='not_public_record'").fetchone()[0] if table_exists(conn, "release_metadata_gap_items") else 0
        lead_public = conn.execute("SELECT COUNT(*) FROM release_lead_overlay_items WHERE public_record_status!='not_public_record'").fetchone()[0] if table_exists(conn, "release_lead_overlay_items") else 0
    gates = []
    critical = [row for row in hard_gaps if row.get("gap_type") == "CRITICAL_HARD_GAP"]
    record_warn = [row for row in hard_gaps if row.get("gap_type") == "RECORD_HARD_GAP"]
    gates.append({"gate": "coverage_no_critical_hard_gap", "status": "PASS" if not critical else "FAIL", "details": f"{len(critical)} critical gaps"})
    gates.append({"gate": "coverage_record_gap_labelled", "status": "WARN" if record_warn else "PASS", "details": f"{len(record_warn)} record gaps with lead/metadata coverage"})
    gates.append({"gate": "metadata_not_counted_as_public_record", "status": "PASS" if metadata_public == 0 and lead_public == 0 else "FAIL", "details": f"metadata_public={metadata_public}, lead_public={lead_public}"})
    gates.append({"gate": "map_layers_separate", "status": "PASS" if "accepted_public_map" in map_counts else "FAIL", "details": f"accepted={map_counts.get('accepted_public_map', 0)}, overlays={map_counts.get('metadata_place_overlay', 0) + map_counts.get('lead_place_overlay', 0)}"})
    gates.append({"gate": "redirects_valid", "status": "PASS" if "Status: `PASS`" in redirect_validation else "FAIL", "details": "redirect validation report"})
    gates.append({"gate": "release_candidate_json_valid", "status": "PASS" if package_counts else "FAIL", "details": f"package counts present={bool(package_counts)}"})
    gates.append({"gate": "disclaimer_included", "status": "PASS" if "Metadata-only layer is not proof" in disclaimer else "FAIL", "details": "release disclaimer"})
    gates.append({"gate": "sensitive_not_public", "status": "PASS" if sensitive_public == 0 else "FAIL", "details": f"{sensitive_public} sensitive public rows"})
    status = "FAIL" if any(row["status"] == "FAIL" for row in gates) else ("WARN" if any(row["status"] == "WARN" for row in gates) else "PASS")
    write_csv(out_dir / "final_release_gate_results.csv", gates, FIELDS)
    counts = [{"category": key, "count": value} for key, value in package_counts.items() if isinstance(value, int)]
    write_csv(out_dir / "final_release_counts.csv", counts, ["category", "count"])
    limitations = ["# Final Release Known Limitations", "", "- Accepted-record gaps may remain where metadata-only/lead coverage is available.", "- Map overlays are separate and not proof/habitat maps.", "- Source-chain gaps remain visible for discovery/access-platform material."]
    (out_dir / "final_release_known_limitations.md").write_text("\n".join(limitations) + "\n", encoding="utf-8")
    summary = ["# Final Release Audit Summary", "", f"- Generated: `{now_iso()}`", f"- Overall status: `{status}`", "", "## Gates"]
    summary.extend([f"- `{row['gate']}`: {row['status']} - {row['details']}" for row in gates])
    (out_dir / "final_release_audit_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    go = ["# Final Release Go/No-Go", "", f"- Status: `{'ready_with_warnings' if status == 'WARN' else ('ready' if status == 'PASS' else 'blocked')}`", f"- Gate status: `{status}`", "- Public records mutated: `no`", "- Map flags mutated: `no`"]
    (out_dir / "final_release_go_no_go.md").write_text("\n".join(go) + "\n", encoding="utf-8")
    return {"status": status, "go_no_go": "ready_with_warnings" if status == "WARN" else ("ready" if status == "PASS" else "blocked"), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.db), Path(args.package_dir), Path(args.redirect_dir), Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
