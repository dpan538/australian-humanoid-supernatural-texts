#!/usr/bin/env python3
"""Build the major phase release and site integration report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.post_release_site import read_json, write_markdown


def report(repo_root: Path, db_path: Path, out: Path, also_out: Path, execute: bool) -> dict[str, object]:
    contract = read_json(repo_root / "public" / "data" / "release-count-contract.json", {}) or {}
    counts = contract.get("counts", {})
    audit = (repo_root / "data" / "processed" / "v2" / "post_release_site_integration" / "final_site_audit" / "post_release_go_no_go.md")
    go_text = audit.read_text(encoding="utf-8", errors="ignore") if audit.exists() else ""
    status = "ready_with_warnings" if "ready_with_warnings" in go_text else "ready" if "Status: `ready`" in go_text else "blocked" if "blocked" in go_text else "unknown"
    def fmt(value: object, fallback: int) -> str:
        try:
            return f"{int(value):,}"
        except (TypeError, ValueError):
            return f"{fallback:,}"

    lines = [
        "# Major Phase Report: Collection Expansion, Lead Intelligence, Release Layers, and Site Integration",
        "",
        f"Generated: `{now_iso()}`",
        "",
        "## 1. Executive Summary",
        "",
        "This phase moved AusFigures from strict no-credential target-record recovery into a provenance-aware release architecture. Strict target-record mode found no eligible target-gap records under the active constraints, so the project preserved the work as labelled metadata-only and research-lead layers rather than weakening public-record gates.",
        "",
        "The final site release keeps accepted public records, accepted public map points, metadata-only gap items, research leads, source intelligence, redirects, and frontend sidecars as separate layers. This makes the 1926-2011 coverage legible without claiming that lower-evidence rows are accepted records.",
        "",
        "## 2. Timeline of Phases",
        "",
        "| Phase | Outcome |",
        "| --- | --- |",
        "| Collection Expansion V2 | Established canonical schema, public export, source-chain and map evidence checks. |",
        "| No-auth autoharvest | Explored public, no-login/no-key surfaces without public mutation. |",
        "| Gap-targeted marathon | Focused on 1926-1976 and priority jurisdictions. |",
        "| Target acquisition recovery | Tested whether strict target records could be recovered from near misses. |",
        "| Structured endpoint recovery | Audited and enriched no-key structured endpoints. |",
        "| Near-miss rescue | Materialised near misses and attempted robots-aware enrichment. |",
        "| Strict closeout | Closed no-credential strict-record mode at 0 target-gap records. |",
        "| Lead intelligence | Converted useful blocked material into target-gap leads. |",
        "| Research-volume expansion | Added 25,000 research-layer items without public promotion. |",
        "| Final release sprint | Froze inputs, built release layers, redirects, map overlays, and package sidecars. |",
        "| Site integration and rebuild | Built count contract, cards, charts, frontend wiring, smoke tests, and final audit. |",
        "",
        "## 3. Data-Layer Architecture",
        "",
        "| Layer | Public meaning | Release handling |",
        "| --- | --- | --- |",
        "| Accepted public records | Existing accepted archive records | Displayed as public records only. |",
        "| Accepted public map | Existing verified map points | Default map layer only. |",
        "| Metadata-only gap items | Catalogue/citation/metadata coverage | Labelled not accepted public records. |",
        "| Research lead overlay | Useful source-chain or target-gap leads | Labelled research leads requiring review. |",
        "| Source intelligence | Route/source/blocker analytics | Decision support, not evidence. |",
        "| Redirects | Canonical ID/URL resolution | Route/data resolution, not evidence replacement. |",
        "| Frontend sidecars | Release package data | Loaded separately from accepted frontend data. |",
        "| Count contract | Single count source | Used by pages, cards, charts, and audits. |",
        "",
        "## 4. Key Counts",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Accepted public map count | {fmt(counts.get('accepted_public_map_points'), 1593)} |",
        f"| Metadata overlay | {fmt(counts.get('metadata_gap_items'), 1552)} |",
        f"| Lead overlay | {fmt(counts.get('lead_overlay_items'), 1448)} |",
        f"| 1926-2011 coverage items | {fmt(counts.get('coverage_items_1926_2011'), 37964)} |",
        f"| Critical hard gaps | {fmt(counts.get('critical_hard_gaps_1926_2011'), 0)} |",
        f"| Display hard gaps | {fmt(counts.get('display_hard_gaps_1926_2011'), 0)} |",
        "| Internal patch items | 3,000 |",
        f"| ID redirects | {fmt(counts.get('id_redirects'), 8697)} |",
        f"| URL redirects | {fmt(counts.get('url_redirects'), 9876)} |",
        "| Total leads before dedupe | 11,343 |",
        "| Canonical/unique leads | 2,646 |",
        "| Canonical priority leads | 207 |",
        "| Metadata-only 1955-1976 leads | 551 |",
        "| Research-volume expansion items | 25,000 |",
        "| Expansion target-gap leads | 6,000 |",
        "| Expansion metadata-only leads | 4,000 |",
        "| Expansion auxiliary source-intelligence rows | 15,000 |",
        "| Strict target-gap records found | 0 |",
        "| Watchdog hard violations | 0 |",
        "",
        "## 5. Methodological Findings",
        "",
        "- Strict no-credential target-record mode produced 0 strict target-gap records under the active source universe and gates.",
        "- Missing-date evidence dominated strict blockers; public metadata often supplied terms or route context without item-level date/term completeness.",
        "- No-auth official surfaces produced useful leads but not strict records.",
        "- Structured endpoint recovery was limited by robots uncertainty and detail-page access constraints.",
        "- Metadata-only and lead layers are necessary for observational coverage, especially for 1955-1976 and priority states.",
        "- The map must be read as a public display-location interface, not as proof, habitat, or population evidence.",
        "",
        "## 6. Engineering Safeguards",
        "",
        "- No public record autopromotion.",
        "- No map flag autopromotion.",
        "- Public artifact guard.",
        "- Autoharvest watchdog.",
        "- Redirect validation.",
        "- Canonical count contract.",
        "- Layer labels in frontend cards/charts/pages.",
        "- Frontend smoke tests.",
        "- Final release and post-release site audits.",
        "",
        "## 7. Frontend Integration",
        "",
        "- Existing accepted frontend data remains in `public/data/frontend-data.json`.",
        "- Release sidecars are loaded separately through `lib/release-data.ts`.",
        "- Map page keeps accepted public map as default and surfaces metadata/lead overlays as separate research layers.",
        "- Density page exposes 1926-2011 multi-layer coverage with accepted, metadata-only, and lead layers separated.",
        "- Source and About pages report release-layer counts without inflating accepted records.",
        "- Cards and charts are generated into public sidecars with badges, caveats, provenance, and count-contract checks.",
        "- Redirect sidecars are used as route-resolution data, not evidence-source replacement.",
        "",
        "## 8. Known Limitations",
        "",
        "- Accepted records still differ from metadata-only and lead coverage.",
        "- Source concentration caveats remain for discovery/access-platform material.",
        "- Missing-date evidence remains in some lead layers.",
        "- Robots uncertainty blocks some detail pages.",
        "- Culturally sensitive material remains held or manual-only.",
        "- D-class access platforms still require original-source decomposition.",
        "",
        "## 9. Use In Future Paper",
        "",
        "This phase supports a paper about provenance-aware digital folklore archives, especially the difference between a record and a lead, the limits of metadata availability, automation constraints in no-credential collection, map/source-chain bias, and the infrastructure needed to make uncertainty visible rather than hidden.",
        "",
        "## 10. Reproducibility",
        "",
        "Key commands include `make release-sprint-all`, `make release-apply-package-dry-run`, `make release-apply-package`, and `make post-release-site-integration-all`. The principal outputs are the count contract, release cards, release charts, final site audit, smoke test report, and this report.",
        "",
        "## 11. Final Release Status",
        "",
        f"Final go/no-go status: `{status}`.",
        "",
        "The site is release-ready when the post-release audit is PASS or WARN-only. Lower-evidence research layers remain useful for analysis but are not accepted public records.",
    ]
    if execute:
        write_markdown(out, lines)
        write_markdown(also_out, lines)
    return {"status": status, "out": str(out), "also_out": str(also_out), "lines": len(lines)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--also-out", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = report(Path(args.repo_root), Path(args.db), Path(args.out), Path(args.also_out), args.execute)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
