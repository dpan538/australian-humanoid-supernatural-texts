#!/usr/bin/env python3
"""Freeze the current legacy database and exports with SHA256 checksums."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_RELEASE = PROJECT_ROOT / "data" / "releases" / "legacy_985"
EXPORT_NAMES = [
    "records_review.csv",
    "figures_aliases.csv",
    "query_plan.csv",
    "attention_series.csv",
    "record_locations.csv",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip()


def count_records(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0])


def copy_if_changed(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and sha256_file(src) == sha256_file(dst):
        return
    shutil.copy2(src, dst)


def snapshot(db_path: Path, release_dir: Path) -> Path:
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")

    database_dir = release_dir / "database"
    exports_dir = release_dir / "exports"
    database_dir.mkdir(parents=True, exist_ok=True)
    exports_dir.mkdir(parents=True, exist_ok=True)

    db_dst = database_dir / db_path.name
    copy_if_changed(db_path, db_dst)

    copied_exports: list[Path] = []
    for name in EXPORT_NAMES:
        src = PROJECT_ROOT / "data" / "exports" / name
        if src.exists():
            dst = exports_dir / name
            copy_if_changed(src, dst)
            copied_exports.append(dst)

    manifest_items = [db_dst, *copied_exports]
    manifest_lines = [f"{sha256_file(path)}  {path.relative_to(release_dir)}" for path in manifest_items]
    manifest_path = release_dir / "MANIFEST.sha256"
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    db_checksum = sha256_file(db_dst)
    record_count = count_records(db_dst)
    generated = utc_now_iso()
    readme = [
        "# Legacy 985 Corpus Freeze",
        "",
        f"- Generation date: `{generated}`",
        f"- Commit SHA: `{git_commit()}`",
        "- Schema version: `legacy-flat-v1`",
        f"- Exact record count: `{record_count}`",
        f"- Database checksum: `{db_checksum}`",
        f"- Database file: `database/{db_path.name}`",
        f"- Export files: `{len(copied_exports)}`",
        "",
        "## Limitations",
        "- This release preserves the legacy flat-record model.",
        "- A legacy row may represent a source page, a retelling, catalogue metadata, a control, or a source pointer.",
        "- Legacy record counts should not be interpreted as unique narratives, unique encounter events, or balanced geographic prevalence.",
        "- Source labels were not fully separated from analytical entity concepts in the legacy model.",
        "- Location rows may represent reported places, broad associations, or review signals rather than verified event locations.",
        "",
        "## Checksums",
        "Checksums are recorded in `MANIFEST.sha256`.",
    ]
    (release_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return release_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--release-dir", default=str(DEFAULT_RELEASE), help="Release output directory")
    args = parser.parse_args()
    path = snapshot(Path(args.db), Path(args.release_dir))
    print(f"Wrote legacy snapshot: {path}")


if __name__ == "__main__":
    main()
