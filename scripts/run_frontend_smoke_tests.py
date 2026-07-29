#!/usr/bin/env python3
"""Run available frontend build/smoke checks for the post-release site."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.post_release_site import EXPECTED_ACCEPTED_PUBLIC_MAP, read_json, run_command, write_json, write_markdown


CORE_ROUTES = ["/", "/map", "/density", "/source", "/about", "/dashboard"]
REQUIRED_PUBLIC_DATA = [
    "frontend-data.json",
    "release-count-contract.json",
    "release-cards.json",
    "release-charts.json",
    "frontend-map-overlays.release-candidate.json",
    "frontend-redirects.release-candidate.json",
    "release-coverage.release-candidate.json",
]


def smoke(repo_root: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    package = read_json(repo_root / "package.json", {}) or {}
    scripts = package.get("scripts", {})
    commands: list[list[str]] = []
    if execute and not (repo_root / "node_modules").exists() and (repo_root / "package-lock.json").exists():
        commands.append(["npm", "install"])
    if "lint" in scripts:
        commands.append(["npm", "run", "lint"])
    if "typecheck" in scripts:
        commands.append(["npm", "run", "typecheck"])
    if "test" in scripts:
        commands.append(["npm", "run", "test"])
    if "build" in scripts:
        commands.append(["npm", "run", "build"])

    command_results = [run_command(command, repo_root, timeout=300) for command in commands] if execute else []
    missing_data = [name for name in REQUIRED_PUBLIC_DATA if not (repo_root / "public" / "data" / name).exists()]
    contract = read_json(repo_root / "public" / "data" / "release-count-contract.json", {}) or {}
    map_count = contract.get("counts", {}).get("accepted_public_map_points")
    build_exists = (repo_root / ".next").exists() or (repo_root / "out").exists() or not execute
    route_rows = []
    for route in CORE_ROUTES:
        route_file = repo_root / "app" / route.strip("/") / "page.tsx" if route != "/" else repo_root / "app" / "page.tsx"
        route_rows.append({
            "route": route,
            "status": "PASS" if route_file.exists() else "WARN",
            "check": "source_route_exists" if route_file.exists() else "route_file_missing_or_dynamic",
        })
    artifact_rows = []
    for name in REQUIRED_PUBLIC_DATA:
        path = repo_root / "public" / "data" / name
        artifact_rows.append({"artifact": name, "exists": "yes" if path.exists() else "no", "size": path.stat().st_size if path.exists() else 0})

    failures = []
    if any(result["status"] == "FAIL" for result in command_results):
        failures.append("frontend command failed")
    if missing_data:
        failures.append(f"required public data missing: {', '.join(missing_data)}")
    if not build_exists:
        failures.append("build artifact missing")
    if map_count != EXPECTED_ACCEPTED_PUBLIC_MAP:
        failures.append(f"accepted public map count missing or incorrect: {map_count}")
    status = "FAIL" if failures else "PASS"

    write_json(out_dir / "frontend_command_results.json", command_results)
    write_csv(out_dir / "route_smoke_results.csv", route_rows, ["route", "status", "check"])
    write_csv(out_dir / "build_artifact_summary.csv", artifact_rows, ["artifact", "exists", "size"])
    write_markdown(
        out_dir / "frontend_smoke_test_report.md",
        [
            "# Frontend Smoke Test Report",
            "",
            f"- Generated: `{now_iso()}`",
            f"- Status: `{status}`",
            f"- Commands run: `{len(command_results)}`",
            f"- Build artifact detected: `{'yes' if build_exists else 'no'}`",
            f"- Missing public data files: `{len(missing_data)}`",
            f"- Accepted public map count: `{map_count}`",
            "",
            "## Command Results",
            *(f"- `{row['command']}`: `{row['status']}` ({row['returncode']})" for row in command_results),
            *(["", "## Failures", *[f"- {failure}" for failure in failures]] if failures else []),
        ],
    )
    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures}, indent=2))
    return {"status": status, "commands": len(command_results), "routes": len(route_rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = smoke(Path(args.repo_root), Path(args.out_dir), args.execute)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
