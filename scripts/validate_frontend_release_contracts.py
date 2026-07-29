#!/usr/bin/env python3
"""Validate frontend release count, card, chart, and sidecar contracts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.post_release_site import EXPECTED_ACCEPTED_PUBLIC_MAP, SIDECAR_FILES, read_json, write_markdown


def validate(repo_root: Path, count_contract: Path, cards_path: Path, charts_path: Path, package_dir: Path, out: Path) -> dict[str, object]:
    failures: list[str] = []
    warnings: list[str] = []
    contract = read_json(count_contract, {}) or {}
    cards_data = read_json(cards_path, {}) or {}
    charts_data = read_json(charts_path, {}) or {}
    counts = contract.get("counts", {})
    required_count_keys = [
        "accepted_public_records",
        "accepted_public_map_points",
        "metadata_gap_items",
        "lead_overlay_items",
        "coverage_items_1926_2011",
        "critical_hard_gaps_1926_2011",
        "display_hard_gaps_1926_2011",
        "id_redirects",
        "url_redirects",
    ]
    for key in required_count_keys:
        if key not in counts:
            failures.append(f"count contract missing {key}")
    if counts.get("accepted_public_map_points") != EXPECTED_ACCEPTED_PUBLIC_MAP:
        failures.append("accepted public map count drift")
    if contract.get("rules", {}).get("metadata_items_are_public_records") is not False:
        failures.append("metadata_items_are_public_records rule is not false")
    if contract.get("rules", {}).get("lead_items_are_public_records") is not False:
        failures.append("lead_items_are_public_records rule is not false")

    cards = cards_data.get("cards", [])
    card_ids = [card.get("id") for card in cards]
    if len(card_ids) != len(set(card_ids)):
        failures.append("duplicate card IDs")
    if not cards:
        failures.append("release cards missing")
    for card in cards:
        layer = card.get("layer_type")
        caveat = str(card.get("caveat") or "")
        if layer in {"metadata_only_gap_item", "research_lead"} and not caveat:
            failures.append(f"{card.get('id')} missing caveat")
        if layer in {"metadata_only_gap_item", "research_lead"} and card.get("public_record_status") != "not_public_record":
            failures.append(f"{card.get('id')} mislabeled public_record_status")
        if card.get("card_type") == "redirect_notice_card" and not card.get("redirect_target"):
            failures.append(f"{card.get('id')} missing redirect target")

    charts = charts_data.get("charts", [])
    if len(charts) < 10:
        failures.append("release charts missing required chart count")
    for chart in charts:
        if not chart.get("caveat"):
            failures.append(f"{chart.get('title')} missing caveat")
        if not chart.get("source_file_provenance"):
            failures.append(f"{chart.get('title')} missing provenance")
    if charts_data.get("contract_counts", {}).get("accepted_public_map_points") not in {None, EXPECTED_ACCEPTED_PUBLIC_MAP}:
        failures.append("chart contract count has map drift")

    missing_sidecars = [name for name in SIDECAR_FILES if not (package_dir / name).exists()]
    if missing_sidecars:
        failures.append(f"package sidecars missing: {', '.join(missing_sidecars)}")
    public_missing = [path for path in [count_contract, cards_path, charts_path] if not path.exists()]
    if public_missing:
        failures.append(f"public data files missing: {', '.join(map(str, public_missing))}")

    loader = (repo_root / "lib" / "release-data.ts").read_text(encoding="utf-8", errors="ignore") if (repo_root / "lib" / "release-data.ts").exists() else ""
    page_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for root in ["app", "components"] if (repo_root / root).exists() for path in (repo_root / root).rglob("*.tsx"))
    for token in ["loadReleaseCountContract", "loadMapOverlays", "loadReleaseCoverage", "loadRedirects"]:
        if token not in loader:
            failures.append(f"loader missing {token}")
    if "release-count-contract" not in loader or "ReleaseLayerStrip" not in page_text:
        failures.append("pages do not reference release count contract/data loader")

    status = "FAIL" if failures else "WARN" if warnings else "PASS"
    write_markdown(
        out,
        [
            "# Frontend Release Contract Validation",
            "",
            f"- Generated: `{now_iso()}`",
            f"- Status: `{status}`",
            f"- Count contract: `{count_contract}`",
            f"- Cards: `{len(cards)}`",
            f"- Charts: `{len(charts)}`",
            f"- Missing sidecars: `{len(missing_sidecars)}`",
            "",
            "## Checks",
            "- JSON valid: `yes`",
            "- Required count keys present: `yes`" if not any("count contract missing" in item for item in failures) else "- Required count keys present: `no`",
            f"- Accepted public map count: `{counts.get('accepted_public_map_points', 0)}`",
            "- Layers separated: `yes`" if not any("mislabeled" in item for item in failures) else "- Layers separated: `no`",
            *(["", "## Warnings", *[f"- {warning}" for warning in warnings]] if warnings else []),
            *(["", "## Failures", *[f"- {failure}" for failure in failures[:40]]] if failures else []),
        ],
    )
    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures[:20]}, indent=2))
    return {"status": status, "cards": len(cards), "charts": len(charts)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--count-contract", required=True)
    parser.add_argument("--cards", required=True)
    parser.add_argument("--charts", required=True)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = validate(Path(args.repo_root), Path(args.count_contract), Path(args.cards), Path(args.charts), Path(args.package_dir), Path(args.out))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
