from __future__ import annotations

import csv
import json
import re
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from collection_expansion_common import now_iso, table_exists, write_csv


ROOT = Path(__file__).resolve().parents[2]
POST_RELEASE_DIR = ROOT / "data" / "processed" / "v2" / "post_release_site_integration"
EXPECTED_ACCEPTED_PUBLIC_MAP = 1593

PROTECTED_LABELS = {
    "accepted_public_records": "Accepted public records",
    "accepted_public_map_points": "Accepted public map points",
    "metadata_gap_items": "Metadata-only gap items",
    "lead_overlay_items": "Research leads",
    "coverage_items_1926_2011": "Multi-layer coverage items",
}

LAYER_RULES = {
    "metadata_items_are_public_records": False,
    "lead_items_are_public_records": False,
    "map_overlays_are_accepted_map_points": False,
}

SIDECAR_FILES = [
    "frontend-data.release-candidate.json",
    "frontend-map-overlays.release-candidate.json",
    "frontend-redirects.release-candidate.json",
    "release-coverage.release-candidate.json",
    "source-intelligence.release-candidate.json",
    "release-counts.json",
    "release-disclaimer.md",
]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def safe_int(value: Any, default: int = 0) -> int:
    if value in {None, ""}:
        return default
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    if value in {None, ""}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def count_table(conn: sqlite3.Connection, table: str, where: str = "") -> int:
    if not table_exists(conn, table):
        return 0
    suffix = f" WHERE {where}" if where else ""
    return safe_int(conn.execute(f"SELECT COUNT(*) FROM {table}{suffix}").fetchone()[0])


def table_rows(conn: sqlite3.Connection, table: str, limit: int | None = None) -> list[dict[str, Any]]:
    if not table_exists(conn, table):
        return []
    conn.row_factory = sqlite3.Row
    query = f"SELECT * FROM {table}"
    if limit is not None:
        query += f" LIMIT {int(limit)}"
    return [dict(row) for row in conn.execute(query)]


def active_redirect_counts(db_path: Path, redirect_dir: Path) -> dict[str, int]:
    counts = {"id_redirects": 0, "url_redirects": 0}
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            counts["id_redirects"] = count_table(conn, "canonical_id_redirects", "active=1")
            counts["url_redirects"] = count_table(conn, "canonical_url_redirects", "active=1")
    if not counts["id_redirects"]:
        counts["id_redirects"] = len(read_csv_rows(redirect_dir / "canonical_id_redirects.csv"))
    if not counts["url_redirects"]:
        rows = read_csv_rows(redirect_dir / "canonical_url_redirects.csv")
        counts["url_redirects"] = len({(row.get("from_url"), row.get("to_url"), row.get("url_role")) for row in rows})
    return counts


def coverage_counts(coverage_dir: Path) -> dict[str, int]:
    coverage_rows = read_csv_rows(coverage_dir / "release_coverage_1926_2011.csv")
    hard_gap_rows = read_csv_rows(coverage_dir / "hard_gap_report.csv")
    return {
        "coverage_items_1926_2011": sum(safe_int(row.get("total_items")) for row in coverage_rows),
        "critical_hard_gaps_1926_2011": sum(1 for row in hard_gap_rows if row.get("gap_type") == "CRITICAL_HARD_GAP"),
        "display_hard_gaps_1926_2011": sum(1 for row in hard_gap_rows if row.get("gap_type") == "DISPLAY_HARD_GAP"),
    }


def current_count_sources(
    db_path: Path,
    frontend_data: Path,
    release_package: Path,
    coverage_dir: Path,
    map_dir: Path,
    redirect_dir: Path,
) -> dict[str, Any]:
    frontend = read_json(frontend_data, {}) or {}
    release_counts = read_json(release_package / "release-counts.json", {}) or {}
    map_counts = read_json(map_dir / "map_layer_counts.json", {}) or {}
    coverage = coverage_counts(coverage_dir)
    redirects = active_redirect_counts(db_path, redirect_dir)
    db_counts: dict[str, int] = {}
    if db_path.exists():
        with sqlite3.connect(db_path) as conn:
            db_counts = {
                "records_table": count_table(conn, "records"),
                "release_metadata_gap_items": count_table(conn, "release_metadata_gap_items"),
                "release_lead_overlay_items": count_table(conn, "release_lead_overlay_items"),
                "release_source_intelligence_items": count_table(conn, "release_source_intelligence_items"),
            }

    frontend_summary = frontend.get("summary", {}) if isinstance(frontend, dict) else {}
    frontend_counts = {
        "accepted_public_records": safe_int(frontend_summary.get("record_count"), len(frontend.get("records", []) if isinstance(frontend, dict) else [])),
        "accepted_public_map_points": safe_int(frontend_summary.get("mapped_record_count"), len(frontend.get("map_flags", []) if isinstance(frontend, dict) else [])),
    }
    canonical = {
        "accepted_public_records": safe_int(release_counts.get("accepted_public_records"), frontend_counts["accepted_public_records"]),
        "accepted_public_map_points": safe_int(map_counts.get("accepted_public_map"), frontend_counts["accepted_public_map_points"]),
        "metadata_gap_items": safe_int(release_counts.get("metadata_overlay"), map_counts.get("metadata_place_overlay", db_counts.get("release_metadata_gap_items", 0))),
        "lead_overlay_items": safe_int(release_counts.get("lead_overlay"), map_counts.get("lead_place_overlay", db_counts.get("release_lead_overlay_items", 0))),
        **coverage,
        **redirects,
    }
    return {
        "canonical": canonical,
        "frontend": frontend_counts,
        "release_package": release_counts,
        "map": map_counts,
        "coverage": coverage,
        "redirects": redirects,
        "db": db_counts,
    }


def summarize_source_family(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "unknown"
    return text.lower().replace(" ", "_")


def year_or_range(row: dict[str, Any]) -> str:
    year = row.get("inferred_year") or row.get("year")
    start = row.get("coverage_start_year")
    end = row.get("coverage_end_year")
    if year not in {None, ""}:
        return str(year)
    if start and end and str(start) != str(end):
        return f"{start}-{end}"
    if start or end:
        return str(start or end)
    return "undated"


def canonical_url_from_redirects(url: Any, redirects: dict[str, str]) -> str:
    text = str(url or "").strip()
    return redirects.get(text, text)


def read_url_redirect_map(redirect_dir: Path) -> dict[str, str]:
    rows = read_csv_rows(redirect_dir / "canonical_url_redirects.csv")
    mapping: dict[str, str] = {}
    for row in rows:
        from_url = row.get("from_url") or ""
        to_url = row.get("to_url") or ""
        if from_url and to_url:
            mapping[from_url] = to_url
    return mapping


def extract_status(text: str) -> str:
    match = re.search(r"Status:\s*`?([A-Z_a-z-]+)`?", text)
    return match.group(1).upper() if match else "UNKNOWN"


def run_command(command: list[str], cwd: Path, timeout: int = 180) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "status": "PASS" if completed.returncode == 0 else "FAIL",
        }
    except Exception as exc:  # pragma: no cover - defensive fallback for local tooling gaps
        return {
            "command": " ".join(command),
            "returncode": -1,
            "stdout_tail": "",
            "stderr_tail": str(exc),
            "status": "FAIL",
        }


def status_from_failures(failures: list[str], warnings: list[str] | None = None) -> str:
    if failures:
        return "FAIL"
    if warnings:
        return "WARN"
    return "PASS"


def counter_rows(counter: Counter[str], key_name: str = "category") -> list[dict[str, Any]]:
    return [{key_name: key or "unknown", "count": value} for key, value in counter.most_common()]
