#!/usr/bin/env python3
"""Shared helpers for Humanities and Social Sciences Communications paper tooling."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "config" / "paper_hss_freeze.yaml"
SCRIPT_VERSION = "2026-07-06.1"

PUBLIC_DISPLAY_MODES = {"full", "summary_only", "metadata_only"}
SENSITIVE_VALUES = {
    "sensitive",
    "restricted",
    "manual_only",
    "secret",
    "sacred",
    "high",
    "very_high",
    "high_public_source_summary_only",
    "suppressed",
}
SENSITIVE_TERMS = {
    "aboriginal",
    "indigenous",
    "torres strait",
    "first nations",
    "secret/sacred",
    "secret sacred",
    "restricted cultural",
    "wandjina",
    "quinkan",
    "mamu",
    "pangkarlangu",
    "yara-ma-yha-who",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG
    if not path.exists():
        raise SystemExit(f"Missing paper config: {rel_path(path)}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Paper config must be a mapping: {rel_path(path)}")
    return data


def rel_path(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.resolve().relative_to(ROOT))
    except Exception:
        return str(path)


def resolve_repo_path(path: str | Path | None, default: str | Path | None = None) -> Path:
    raw = path if path not in {None, ""} else default
    if raw is None:
        raise ValueError("No path configured")
    candidate = Path(str(raw))
    return candidate if candidate.is_absolute() else ROOT / candidate


def configured_path(config: dict[str, Any], section: str, key: str, default: str | None = None) -> Path:
    return resolve_repo_path(config.get(section, {}).get(key), default)


def release_dir(config: dict[str, Any]) -> Path:
    return configured_path(config, "freeze", "release_dir")


def docs_dir(config: dict[str, Any]) -> Path:
    return configured_path(config, "freeze", "docs_dir")


def sqlite_db_path(config: dict[str, Any]) -> Path:
    configured = configured_path(config, "inputs", "sqlite_db")
    if configured.exists():
        return configured
    candidates = sorted((ROOT / "data" / "processed").glob("*.sqlite"))
    if not candidates:
        raise SystemExit("No SQLite database found under data/processed.")
    return candidates[0]


def git_commit(short: bool = False) -> str:
    args = ["git", "rev-parse", "--short" if short else "HEAD"]
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def git_dirty_summary() -> dict[str, Any]:
    try:
        output = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True)
    except Exception:
        return {"status_available": False, "dirty_file_count": None, "is_dirty": None}
    paths = [line for line in output.splitlines() if line.strip()]
    return {"status_available": True, "dirty_file_count": len(paths), "is_dirty": bool(paths)}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(path: Path, role: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "role": role,
            "path": rel_path(path),
            "exists": False,
            "bytes": "",
            "sha256": "",
            "mtime_utc": "",
        }
    stat = path.stat()
    return {
        "role": role,
        "path": rel_path(path),
        "exists": True,
        "bytes": stat.st_size,
        "sha256": sha256_file(path),
        "mtime_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).replace(microsecond=0).isoformat(),
    }


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    if not table_exists(conn, table):
        return set()
    return {str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def count_table(conn: sqlite3.Connection, table: str, where: str = "1=1") -> int | None:
    if not table_exists(conn, table):
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0] or 0)


def count_by(conn: sqlite3.Connection, table: str, column: str, where: str = "1=1") -> list[dict[str, Any]]:
    if not table_exists(conn, table) or column not in table_columns(conn, table):
        return []
    rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF(TRIM(CAST({column} AS TEXT)), ''), '(missing)') AS value,
               COUNT(*) AS count
        FROM {table}
        WHERE {where}
        GROUP BY value
        ORDER BY count DESC, value
        """
    ).fetchall()
    return [{"value": row["value"], "count": int(row["count"])} for row in rows]


def load_json(path: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return {}, [f"missing JSON file: {rel_path(path)}"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, [f"could not parse JSON {rel_path(path)}: {exc}"]
    if not isinstance(data, dict):
        warnings.append(f"JSON root is not an object: {rel_path(path)}")
        return {}, warnings
    return data, warnings


def read_csv_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], [f"missing CSV file: {rel_path(path)}"]
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle)), []
    except Exception as exc:
        return [], [f"could not parse CSV {rel_path(path)}: {exc}"]


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def pct(part: int | float, whole: int | float) -> float:
    return 0.0 if not whole else round(float(part) / float(whole) * 100, 2)


def count_csv_rows(path: Path) -> int | None:
    rows, _ = read_csv_rows(path)
    return len(rows) if path.exists() else None


def add_count(
    rows: list[dict[str, Any]],
    count_family: str,
    metric: str,
    value: Any,
    unit: str,
    source: str,
    status: str = "ok",
    notes: str = "",
) -> None:
    rows.append(
        {
            "count_family": count_family,
            "metric": metric,
            "value": "" if value is None else value,
            "unit": unit,
            "source": source,
            "status": status,
            "notes": notes,
        }
    )


def add_unavailable(rows: list[dict[str, Any]], count_family: str, metric: str, unit: str, notes: str) -> None:
    add_count(rows, count_family, metric, "", unit, "not available in current local data", "not_available", notes)


def counter_rows(counter: Counter[str], total: int, key_name: str) -> list[dict[str, Any]]:
    result = []
    for key, count in counter.most_common():
        result.append({key_name: key or "(missing)", "count": count, "share_pct": pct(count, total)})
    return result


def domain_only(url: Any) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    return parsed.netloc.lower().removeprefix("www.")


def redacted_text(value: Any, limit: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def has_sensitive_term(text: Any) -> bool:
    folded = str(text or "").casefold()
    return any(term in folded for term in SENSITIVE_TERMS)


def row_is_sensitive(row: dict[str, Any]) -> bool:
    for key, value in row.items():
        if key in {"source_chain_json", "raw_metadata_json"}:
            continue
        folded = str(value or "").strip().casefold()
        if folded in SENSITIVE_VALUES:
            return True
        if key in {
            "ethics_status",
            "ethics_review_status",
            "cultural_sensitivity",
            "display_mode",
            "constraint_blocker",
            "evidence_gap",
            "title",
            "source_name",
            "source_family",
            "route_family",
        } and has_sensitive_term(folded):
            return True
    return False


def markdown_count_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| count_family | metric | value | unit | source | status | notes |",
        "| --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {count_family} | {metric} | {value} | {unit} | {source} | {status} | {notes} |".format(
                count_family=row.get("count_family", ""),
                metric=row.get("metric", ""),
                value=row.get("value", ""),
                unit=row.get("unit", ""),
                source=row.get("source", ""),
                status=row.get("status", ""),
                notes=str(row.get("notes", "")).replace("|", "/"),
            )
        )
    return lines


def write_manifest(path: Path, script_name: str, outputs: list[Path], inputs: list[Path], warnings: list[str]) -> dict[str, Any]:
    payload = {
        "script": script_name,
        "script_version": SCRIPT_VERSION,
        "generated_at": now_iso(),
        "git_commit": git_commit(),
        "git_dirty_summary": git_dirty_summary(),
        "inputs": [file_record(path, "input") for path in inputs],
        "outputs": [file_record(path, "output") for path in outputs if path.exists()],
        "warnings": warnings,
    }
    write_json(path, payload)
    return payload
