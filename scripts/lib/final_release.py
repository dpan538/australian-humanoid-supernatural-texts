from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from collection_expansion_common import now_iso, table_exists, write_csv


TIME_BANDS = [
    ("1926-1939", 1926, 1939),
    ("1940-1954", 1940, 1954),
    ("1955-1969", 1955, 1969),
    ("1970-1984", 1970, 1984),
    ("1985-1999", 1985, 1999),
    ("2000-2011", 2000, 2011),
]
DECADES = [
    ("1930s", 1930, 1939),
    ("1940s", 1940, 1949),
    ("1950s", 1950, 1959),
    ("1960s", 1960, 1969),
    ("1970s", 1970, 1979),
    ("1980s", 1980, 1989),
    ("1990s", 1990, 1999),
    ("2000s", 2000, 2009),
]
PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
PREFERRED_ROUTE_FAMILIES = {
    "local_history_serial",
    "council_local_studies",
    "state_library_catalogue",
    "state_archive_catalogue",
    "museum_heritage_page",
    "heritage_register",
    "historical_society",
    "public_history_site",
    "broadcast_catalogue",
}
RELEASE_ITEM_FIELDS = [
    "source_table",
    "source_row_id",
    "source_lead_id",
    "patch_layer",
    "title",
    "description",
    "url",
    "source_name",
    "source_tier",
    "source_family",
    "route_family",
    "inferred_year",
    "coverage_start_year",
    "coverage_end_year",
    "target_state",
    "target_locality",
    "temporal_signal",
    "term_signal",
    "place_signal",
    "evidence_gap",
    "blocker",
    "priority_score",
    "priority_bucket",
    "selection_reason",
]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def safe_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def band_for_year(year: Any, bands: list[tuple[str, int, int]] = TIME_BANDS) -> str:
    parsed = safe_int(year)
    if parsed is None:
        return "unknown"
    for label, start, end in bands:
        if start <= parsed <= end:
            return label
    return "outside"


def overlaps_1926_2011(row: dict[str, Any]) -> bool:
    years = [safe_int(row.get(key)) for key in ["inferred_year", "coverage_start_year", "coverage_end_year", "year"]]
    if any(year is not None and 1926 <= year <= 2011 for year in years):
        return True
    start = safe_int(row.get("coverage_start_year"))
    end = safe_int(row.get("coverage_end_year"))
    return bool(start is not None and end is not None and start <= 2011 and end >= 1926)


def canonical_url(url: Any) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    parsed = urlparse(text)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return text
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", "", ""))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def count_table(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(conn, table):
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] or 0)


def frontend_map_points(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    points = data.get("map_points") if isinstance(data, dict) else []
    return [row for row in points if isinstance(row, dict)]


def release_layer_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    conn.row_factory = sqlite3.Row
    if table_exists(conn, "release_metadata_gap_items"):
        rows.extend(dict(row, layer="metadata_only_gap_layer") for row in conn.execute("SELECT * FROM release_metadata_gap_items"))
    if table_exists(conn, "release_lead_overlay_items"):
        rows.extend(dict(row, layer="lead_coverage_layer") for row in conn.execute("SELECT * FROM release_lead_overlay_items"))
    if table_exists(conn, "release_source_intelligence_items"):
        rows.extend(dict(row, layer="source_intelligence_layer") for row in conn.execute("SELECT * FROM release_source_intelligence_items"))
    return rows


def source_is_concentrated(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "").lower() for key in ["source_name", "source_family", "route_family", "url"])
    return any(token in text for token in ["ayr", "wikipedia", "tourism", "hauntedplaces", "paranormal", "access_platform"])


def write_count_csv(path: Path, counter: Counter, key: str = "category") -> None:
    write_csv(path, [{key: label or "unknown", "count": count} for label, count in counter.most_common()], [key, "count"])


def now_row() -> tuple[str, str]:
    ts = now_iso()
    return ts, ts
