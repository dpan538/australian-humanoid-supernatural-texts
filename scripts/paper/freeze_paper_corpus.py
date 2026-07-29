#!/usr/bin/env python3
"""Create a non-destructive paper corpus freeze manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paper_common import (
    DEFAULT_CONFIG,
    ROOT,
    configured_path,
    docs_dir,
    file_record,
    git_commit,
    git_dirty_summary,
    load_config,
    now_iso,
    read_csv_rows,
    rel_path,
    release_dir,
    sqlite_db_path,
    write_csv,
    write_json,
    write_manifest,
)


SCRIPT_NAME = "freeze_paper_corpus.py"


def configured_inputs(config: dict[str, Any]) -> list[tuple[str, Path]]:
    inputs = config.get("inputs", {})
    records: list[tuple[str, Path]] = []
    for key, value in sorted(inputs.items()):
        if value in {None, ""}:
            continue
        path = configured_path(config, "inputs", key)
        if path.is_dir():
            for child in sorted(path.glob("*")):
                if child.is_file() and child.suffix.lower() in {".csv", ".json", ".md", ".yml", ".yaml"}:
                    records.append((f"{key}:{child.name}", child))
        else:
            records.append((key, path))
    records.append(("active_sqlite_db", sqlite_db_path(config)))
    return records


def table_inventory(db_path: Path) -> list[dict[str, Any]]:
    import sqlite3

    rows: list[dict[str, Any]] = []
    if not db_path.exists():
        return rows
    with sqlite3.connect(db_path) as conn:
        names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        for name in names:
            try:
                count = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] or 0)
            except Exception:
                count = ""
            rows.append({"table": name, "row_count": count})
    return rows


def write_snapshot_doc(path: Path, payload: dict[str, Any], inventory_rows: list[dict[str, Any]]) -> None:
    lines = [
        "# Corpus Snapshot",
        "",
        "This file records the local paper freeze used for the working article.",
        "It is a manifest of reproducible inputs, not a copy of source texts or restricted material.",
        "",
        "## Freeze",
        "",
        f"- Freeze id: `{payload['freeze_id']}`",
        f"- Generated: `{payload['generated_at']}`",
        f"- Git commit: `{payload['git_commit']}`",
        f"- Git dirty file count: `{payload['git_dirty_summary'].get('dirty_file_count')}`",
        f"- Release directory: `{payload['release_dir']}`",
        "",
        "## Input Manifest",
        "",
        "| role | path | exists | bytes | sha256 |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in payload["inputs"]:
        lines.append(
            f"| {row['role']} | `{row['path']}` | {row['exists']} | {row['bytes']} | `{row['sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## SQLite Table Inventory",
            "",
            "| table | row_count |",
            "| --- | ---: |",
        ]
    )
    for row in inventory_rows:
        lines.append(f"| `{row['table']}` | {row['row_count']} |")
    lines.extend(
        [
            "",
            "## Safety Boundary",
            "",
            "- No raw source text, HTML, XML, PDFs, Word files, cookies, credentials, or SQLite database copies are placed in the paper release.",
            "- Counts for the manuscript should be regenerated from `paper_stats.json` rather than typed by hand.",
            "- Live public website counts are not inferred from local exports; they must be explicitly captured if needed.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def freeze(config_path: Path, out_dir: Path | None, execute: bool) -> dict[str, Any]:
    config = load_config(config_path)
    target_release_dir = out_dir or release_dir(config)
    target_docs_dir = docs_dir(config)
    target_release_dir.mkdir(parents=True, exist_ok=True) if execute else None
    target_docs_dir.mkdir(parents=True, exist_ok=True) if execute else None

    input_pairs = configured_inputs(config)
    inventory = []
    seen: set[Path] = set()
    for role, path in input_pairs:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        inventory.append(file_record(path, role))

    db_path = sqlite_db_path(config)
    table_rows = table_inventory(db_path)
    freeze_id = str(config.get("freeze", {}).get("freeze_id") or target_release_dir.name)
    payload = {
        "freeze_id": freeze_id,
        "generated_at": now_iso(),
        "paper": config.get("paper", {}),
        "release_dir": rel_path(target_release_dir),
        "docs_dir": rel_path(target_docs_dir),
        "git_commit": git_commit(),
        "git_dirty_summary": git_dirty_summary(),
        "inputs": inventory,
        "sqlite_tables": table_rows,
        "safety": {
            "copied_raw_text": False,
            "copied_sqlite_database": False,
            "copied_frontend_artifacts": False,
            "read_only_against_source_data": True,
        },
    }

    outputs: list[Path] = []
    if execute:
        freeze_json = target_release_dir / "paper_freeze_manifest.json"
        inventory_csv = target_release_dir / "paper_input_inventory.csv"
        table_csv = target_release_dir / "sqlite_table_inventory.csv"
        snapshot_md = target_docs_dir / "CORPUS_SNAPSHOT.md"
        write_json(freeze_json, payload)
        write_csv(inventory_csv, inventory, ["role", "path", "exists", "bytes", "sha256", "mtime_utc"])
        write_csv(table_csv, table_rows, ["table", "row_count"])
        write_snapshot_doc(snapshot_md, payload, table_rows)
        outputs.extend([freeze_json, inventory_csv, table_csv, snapshot_md])
        manifest_path = target_release_dir / "freeze_script_manifest.json"
        write_manifest(
            manifest_path,
            SCRIPT_NAME,
            outputs,
            [path for _, path in input_pairs if path.exists()],
            [],
        )
        outputs.append(manifest_path)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    payload = freeze(
        Path(args.config),
        Path(args.out_dir) if args.out_dir else None,
        args.execute,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
