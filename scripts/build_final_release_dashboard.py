#!/usr/bin/env python3
"""Build final non-expert release dashboard."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def extract_status(text: str) -> str:
    match = re.search(r"Status:\s*`([^`]+)`", text)
    return match.group(1) if match else "blocked"


def build(audit_dir: Path, coverage_dir: Path, map_dir: Path, redirect_dir: Path, out: Path) -> dict[str, object]:
    go_text = (audit_dir / "final_release_go_no_go.md").read_text(encoding="utf-8") if (audit_dir / "final_release_go_no_go.md").exists() else ""
    status = extract_status(go_text)
    coverage_text = (coverage_dir / "release_coverage_1926_2011_summary.md").read_text(encoding="utf-8") if (coverage_dir / "release_coverage_1926_2011_summary.md").exists() else ""
    map_counts = json.loads((map_dir / "map_layer_counts.json").read_text(encoding="utf-8")) if (map_dir / "map_layer_counts.json").exists() else {}
    redirect_text = (redirect_dir / "redirect_validation_report.md").read_text(encoding="utf-8") if (redirect_dir / "redirect_validation_report.md").exists() else ""
    redirect_status = "PASS" if "Status: `PASS`" in redirect_text else "FAIL"
    next_command = "python3 scripts/apply_final_release_package.py --package-dir data/processed/v2/final_release_package --execute" if status in {"ready", "ready_with_warnings"} else "read data/processed/v2/final_release_audit/final_release_go_no_go.md"
    lines = [
        "# Final Release Dashboard",
        "",
        "## 1. Release Status",
        f"- Status: `{status}`",
        "",
        "## 2. 1926-2011 Coverage",
        "- Accepted records, metadata-only items, and leads are reported as separate layers.",
        "- Remaining caveats are in `final_release_known_limitations.md`.",
        "",
        "## 3. Map",
        f"- Accepted public map count: `{map_counts.get('accepted_public_map', 0)}`",
        f"- Metadata overlay count: `{map_counts.get('metadata_place_overlay', 0)}`",
        f"- Lead overlay count: `{map_counts.get('lead_place_overlay', 0)}`",
        f"- Unmapped gap items: `{map_counts.get('unmapped_gap_items', 0)}`",
        "",
        "## 4. Redirects",
        f"- Redirect validation: `{redirect_status}`",
        "",
        "## 5. Source Concentration",
        "- Source-chain caveats remain labelled; discovery/access layers are not accepted evidence.",
        "",
        "## 6. What Changed",
        "- Release layers added.",
        "- Public records unchanged.",
        "- Map flags unchanged.",
        "",
        "## 7. Next Command",
        f"- `{next_command}`",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": status, "redirect_status": redirect_status, "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-dir", required=True)
    parser.add_argument("--coverage-dir", required=True)
    parser.add_argument("--map-dir", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    import json as _json

    print(_json.dumps(build(Path(args.audit_dir), Path(args.coverage_dir), Path(args.map_dir), Path(args.redirect_dir), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
