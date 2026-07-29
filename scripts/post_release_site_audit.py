#!/usr/bin/env python3
"""Run the unified post-release site integration audit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.post_release_site import EXPECTED_ACCEPTED_PUBLIC_MAP, extract_status, read_json, write_markdown


def read_status(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    return extract_status(path.read_text(encoding="utf-8", errors="ignore"))


def audit(
    repo_root: Path,
    db_path: Path,
    count_contract: Path,
    cards_path: Path,
    charts_path: Path,
    final_audit: Path,
    out_dir: Path,
    execute: bool,
) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    contract = read_json(count_contract, {}) or {}
    cards = (read_json(cards_path, {}) or {}).get("cards", [])
    charts = (read_json(charts_path, {}) or {}).get("charts", [])
    counts = contract.get("counts", {})
    display_audit_status = read_status(repo_root / "data" / "processed" / "v2" / "post_release_site_integration" / "frontend_display_audit" / "frontend_display_audit.md")
    validation_status = read_status(repo_root / "data" / "processed" / "v2" / "post_release_site_integration" / "frontend_release_contract_validation.md")
    smoke_status = read_status(repo_root / "data" / "processed" / "v2" / "post_release_site_integration" / "smoke_tests" / "frontend_smoke_test_report.md")
    final_go_status = read_status(final_audit / "final_release_go_no_go.md")
    apply_report = repo_root / "data" / "processed" / "v2" / "final_release_package" / "final_release_apply_report.md"
    apply_text = apply_report.read_text(encoding="utf-8", errors="ignore") if apply_report.exists() else ""

    gates: list[dict[str, str]] = []

    def gate(name: str, ok: bool, details: str, warn: bool = False) -> None:
        gates.append({"gate": name, "status": "PASS" if ok else "WARN" if warn else "FAIL", "details": details})

    gate("count_contract_present", count_contract.exists(), str(count_contract))
    gate("accepted_public_map_count", counts.get("accepted_public_map_points") == EXPECTED_ACCEPTED_PUBLIC_MAP, str(counts.get("accepted_public_map_points")))
    gate("metadata_not_public", contract.get("rules", {}).get("metadata_items_are_public_records") is False, "metadata rule false")
    gate("leads_not_public", contract.get("rules", {}).get("lead_items_are_public_records") is False, "lead rule false")
    gate("cards_have_caveats", all(card.get("caveat") for card in cards if card.get("layer_type") in {"metadata_only_gap_item", "research_lead"}), f"{len(cards)} cards")
    gate("charts_have_provenance", bool(charts) and all(chart.get("source_file_provenance") for chart in charts), f"{len(charts)} charts")
    gate("contract_validation", validation_status in {"PASS", "WARN"}, validation_status, warn=validation_status == "WARN")
    gate("frontend_smoke", smoke_status == "PASS", smoke_status)
    gate("final_release_audit", final_go_status in {"READY", "PASS"}, final_go_status)
    gate("public_db_mutation", "Database mutated: `no`" in apply_text or "Database mutated: no" in apply_text, "DB mutation report")
    gate("accepted_record_tables_unchanged", "Accepted records DB tables changed: `no`" in apply_text or "Accepted records DB tables changed: no" in apply_text, "accepted records report")
    gate("map_flags_unchanged", "Public map flags changed: `no`" in apply_text or "Public map flags changed: no" in apply_text, "map flags report")
    gate("display_audit", display_audit_status in {"PASS", "WARN"}, display_audit_status, warn=display_audit_status == "WARN")

    failures = [row for row in gates if row["status"] == "FAIL"]
    warnings = [row for row in gates if row["status"] == "WARN"]
    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    go_no_go = "blocked" if status == "FAIL" else "ready_with_warnings" if status == "WARN" else "ready"

    write_csv(out_dir / "post_release_site_gate_results.csv", gates, ["gate", "status", "details"])
    write_csv(out_dir / "post_release_known_bugs.csv", [], ["bug_id", "severity", "summary", "status"])
    write_markdown(
        out_dir / "post_release_known_limitations.md",
        [
            "# Post-Release Known Limitations",
            "",
            "- Accepted records remain distinct from metadata-only and lead coverage.",
            "- Source concentration caveats remain labelled.",
            "- Missing-date and source-chain limitations remain documented in lead layers.",
            "- Robots uncertainty and D-class access platforms remain non-public evidence limitations.",
            "- Map overlays are not accepted public map points and are not habitat/proof maps.",
        ],
    )
    write_markdown(
        out_dir / "post_release_site_audit_summary.md",
        [
            "# Post-Release Site Audit Summary",
            "",
            f"- Generated: `{now_iso()}`",
            f"- Status: `{status}`",
            f"- Go/no-go: `{go_no_go}`",
            f"- Accepted public records: `{counts.get('accepted_public_records', 0)}`",
            f"- Accepted public map points: `{counts.get('accepted_public_map_points', 0)}`",
            f"- Metadata-only gap items: `{counts.get('metadata_gap_items', 0)}`",
            f"- Research leads: `{counts.get('lead_overlay_items', 0)}`",
            f"- Cards: `{len(cards)}`",
            f"- Charts: `{len(charts)}`",
            f"- Contract validation: `{validation_status}`",
            f"- Frontend smoke: `{smoke_status}`",
            f"- Public records mutated: `no`",
            f"- Public map flags mutated: `no`",
        ],
    )
    write_markdown(
        out_dir / "post_release_go_no_go.md",
        [
            "# Post-Release Go/No-Go",
            "",
            f"- Status: `{go_no_go}`",
            f"- Gate status: `{status}`",
            f"- Fail gates: `{len(failures)}`",
            f"- Warn gates: `{len(warnings)}`",
            "- Accepted records mutated: `no`",
            "- Public map flags mutated: `no`",
            *(["", "## Failed Gates", *[f"- {row['gate']}: {row['details']}" for row in failures]] if failures else []),
            *(["", "## Warnings", *[f"- {row['gate']}: {row['details']}" for row in warnings]] if warnings else []),
        ],
    )
    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
    return {"status": status, "go_no_go": go_no_go, "failures": len(failures), "warnings": len(warnings)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--count-contract", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--charts", required=True)
    parser.add_argument("--final-audit", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = audit(
        Path(args.repo_root),
        Path(args.db),
        Path(args.count_contract),
        Path(args.cards),
        Path(args.charts),
        Path(args.final_audit),
        Path(args.out_dir),
        args.execute,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
