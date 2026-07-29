#!/usr/bin/env python3
"""Dry-run or apply final release candidate files to public/data."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso


FILES = [
    "frontend-data.release-candidate.json",
    "frontend-map-overlays.release-candidate.json",
    "frontend-redirects.release-candidate.json",
    "release-coverage.release-candidate.json",
    "source-intelligence.release-candidate.json",
    "release-counts.json",
    "release-disclaimer.md",
]


def apply(package_dir: Path, execute: bool) -> dict[str, object]:
    public_dir = ROOT / "public" / "data"
    changed = []
    missing = [name for name in FILES if not (package_dir / name).exists()]
    backup_path = ""
    if execute and not missing:
        public_dir.mkdir(parents=True, exist_ok=True)
        existing = public_dir / "frontend-data.json"
        if existing.exists():
            backup = public_dir / f"frontend-data.backup-{now_iso().replace(':', '').replace('+', 'Z')}.json"
            shutil.copy2(existing, backup)
            backup_path = str(backup)
        for name in FILES:
            shutil.copy2(package_dir / name, public_dir / name)
            changed.append(str(public_dir / name))
    report = package_dir / "final_release_apply_report.md"
    lines = [
        "# Final Release Apply Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Mode: `{'execute' if execute else 'dry-run'}`",
        f"- Missing package files: `{len(missing)}`",
        f"- Backup path: `{backup_path or 'not_created'}`",
        f"- Changed files: `{len(changed)}`",
        "- Database mutated: `no`",
        "- Accepted records DB tables changed: `no`",
        "- Public map flags changed: `no`",
    ]
    if changed:
        lines.extend(["", "## Changed Files", *[f"- `{path}`" for path in changed]])
    if missing:
        lines.extend(["", "## Missing Files", *[f"- `{name}`" for name in missing]])
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"mode": "execute" if execute else "dry-run", "missing": missing, "backup_path": backup_path, "changed_files": changed, "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    execute = bool(args.execute and not args.dry_run)
    print(json.dumps(apply(Path(args.package_dir), execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
