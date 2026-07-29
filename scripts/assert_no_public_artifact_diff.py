#!/usr/bin/env python3
"""Create or check hashes for public/frontend artifacts that operators must not mutate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_PATHS = [
    "public/data/frontend-data.json",
    "public/data/frontend-data/v2.json",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_artifacts(repo_root: Path) -> list[Path]:
    paths = [repo_root / item for item in DEFAULT_PATHS]
    exports = repo_root / "data" / "exports" / "v2"
    if exports.exists():
        paths.extend(path for path in exports.rglob("*") if path.is_file())
    return sorted(dict.fromkeys(path for path in paths if path.exists()))


def snapshot(repo_root: Path) -> dict[str, Any]:
    files = {}
    for path in iter_artifacts(repo_root):
        files[str(path.relative_to(repo_root))] = {"sha256": sha256(path), "size": path.stat().st_size}
    return {"repo_root": str(repo_root), "files": files}


def create_baseline(repo_root: Path, baseline_file: Path) -> dict[str, Any]:
    data = snapshot(repo_root)
    baseline_file.parent.mkdir(parents=True, exist_ok=True)
    baseline_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"baseline_file": str(baseline_file), "files": len(data["files"])}


def check_baseline(repo_root: Path, baseline_file: Path, allow_changed: bool = False) -> dict[str, Any]:
    old = json.loads(baseline_file.read_text(encoding="utf-8")) if baseline_file.exists() else {"files": {}}
    new = snapshot(repo_root)
    old_files = old.get("files", {})
    new_files = new.get("files", {})
    added = sorted(set(new_files) - set(old_files))
    removed = sorted(set(old_files) - set(new_files))
    changed = sorted(path for path in set(old_files) & set(new_files) if old_files[path].get("sha256") != new_files[path].get("sha256"))
    ok = not (added or removed or changed)
    result = {"ok": ok, "added": added, "removed": removed, "changed": changed, "baseline_file": str(baseline_file)}
    if not ok and not allow_changed:
        raise SystemExit(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--baseline-file", required=True)
    parser.add_argument("--create-baseline", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--allow-changed", action="store_true")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    baseline = Path(args.baseline_file)
    if not baseline.is_absolute():
        baseline = repo_root / baseline
    if args.create_baseline:
        print(json.dumps(create_baseline(repo_root, baseline), indent=2, sort_keys=True))
    elif args.check:
        print(json.dumps(check_baseline(repo_root, baseline, args.allow_changed), indent=2, sort_keys=True))
    else:
        raise SystemExit("use --create-baseline or --check")


if __name__ == "__main__":
    main()
