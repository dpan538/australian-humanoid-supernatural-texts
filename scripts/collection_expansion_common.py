#!/usr/bin/env python3
"""Shared helpers for the collection expansion V2 tooling."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse
from urllib.robotparser import RobotFileParser

import yaml


SOURCE_TIERS = {"A", "B", "C", "D", "E"}
EVIDENCE_MODES = {
    "evidence_possible",
    "evidence_only_if_original_source_identified",
    "discovery_only",
    "manual_only_sensitive",
}
REQUIRED_REGISTRY_FIELDS = {
    "source_id",
    "source_name",
    "institution",
    "route_family",
    "source_tier",
    "evidence_or_discovery",
    "scope",
    "states",
    "access_method",
    "allowed_content_mode",
}

STATE_NAMES = {
    "ACT": "Australian Capital Territory",
    "NSW": "New South Wales",
    "NT": "Northern Territory",
    "QLD": "Queensland",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "VIC": "Victoria",
    "WA": "Western Australia",
}

_ROBOT_CACHE: dict[str, RobotFileParser] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def bool_int(value: Any, default: bool = False) -> int:
    if value is None:
        return 1 if default else 0
    return 1 if bool(value) else 0


def quote_term(term: str) -> str:
    return f'"{term}"' if " " in term else term


def make_query(term: str, locality: str | None, state: str, start_year: int, end_year: int, trove: bool) -> str:
    parts = [quote_term(term)]
    parts.append(quote_term(locality or STATE_NAMES.get(state, state)))
    if trove:
        parts.append(f"date:[{start_year}-01-01T00:00:00Z TO {end_year}-12-31T23:59:59Z]")
    else:
        parts.extend([str(start_year), str(end_year)])
    return " AND ".join(parts)


def make_site_search_query(term: str, locality: str | None, state: str, start_year: int, end_year: int, source: dict[str, Any]) -> str:
    base = make_query(term, locality, state, start_year, end_year, trove=False)
    template = str(source.get("search_url_template") or "")
    if not template:
        return base
    return template.replace("{query}", quote_plus(base))


def stable_query_id(*parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def stable_candidate_id(
    source_id: str,
    stable_id: str | None,
    url: str | None,
    title: str | None,
    date_published: str | None,
    query: str | None,
) -> str:
    raw = "|".join(
        [
            normalize_space(source_id),
            normalize_space(stable_id or url),
            normalize_space(title),
            normalize_space(date_published),
            normalize_space(query),
        ]
    )
    return "cand_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def duplicate_key(
    title: str | None,
    publication: str | None,
    date_published: str | None,
    url: str | None,
    stable_id: str | None,
) -> str:
    raw = "|".join(
        [
            normalize_space(title),
            normalize_space(publication),
            normalize_space(date_published),
            normalize_space(stable_id or url),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def stable_review_id(*parts: Any) -> str:
    raw = "|".join(normalize_space(part) for part in parts)
    return "geo_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def index_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def validate_registry_item(item: dict[str, Any], index: int = 0) -> None:
    missing = REQUIRED_REGISTRY_FIELDS - set(item)
    if missing:
        raise ValueError(f"registry item {index} missing required fields: {sorted(missing)}")
    tier = str(item.get("source_tier") or "")
    mode = str(item.get("evidence_or_discovery") or "")
    if tier not in SOURCE_TIERS:
        raise ValueError(f"{item.get('source_id', index)} has invalid source_tier: {tier}")
    if mode not in EVIDENCE_MODES:
        raise ValueError(f"{item.get('source_id', index)} has invalid evidence_or_discovery: {mode}")
    if mode == "evidence_possible" and tier == "E":
        raise ValueError(f"{item.get('source_id', index)}: discovery tier E cannot be evidence_possible")
    states = item.get("states")
    if not isinstance(states, list) or not states:
        raise ValueError(f"{item.get('source_id', index)} must provide a non-empty states list")


def load_registry(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    if not isinstance(data, list):
        raise ValueError("source_registry.yml must be a list of route objects")
    seen: set[str] = set()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"registry item {index} must be a mapping")
        validate_registry_item(item, index)
        source_id = str(item["source_id"])
        if source_id in seen:
            raise ValueError(f"duplicate source_id: {source_id}")
        seen.add(source_id)
    return data


def routes_by_family_and_state(registry: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in registry:
        family = str(item.get("route_family") or "")
        for state in item.get("states", []):
            result.setdefault((family, str(state)), []).append(item)
        if item.get("scope") == "national":
            for state in STATE_NAMES:
                result.setdefault((family, state), []).append(item)
    for key in result:
        result[key].sort(key=lambda row: (str(row.get("source_tier") or "Z"), str(row.get("source_id") or "")))
    return result


def source_lookup(registry: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item["source_id"]): item for item in registry}


def route_is_manual_only(route: dict[str, Any]) -> bool:
    mode = str(route.get("evidence_or_discovery") or "")
    access = str(route.get("access_method") or "")
    content = str(route.get("allowed_content_mode") or "")
    return mode == "manual_only_sensitive" or "manual" in access or "manual" in content


def allowed_by_robots(url: str, user_agent: str = "AusFiguresResearchBot/0.1") -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _ROBOT_CACHE:
        rp = RobotFileParser()
        rp.set_url(root + "/robots.txt")
        try:
            rp.read()
        except Exception:
            return False
        _ROBOT_CACHE[root] = rp
    return _ROBOT_CACHE[root].can_fetch(user_agent, url)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def pct(part: int, whole: int) -> float:
    return 0.0 if whole == 0 else round(part / whole * 100, 2)


def gate(status: str, name: str, observed: Any, threshold: Any, details: str) -> dict[str, str]:
    return {
        "gate_name": name,
        "gate_status": status,
        "observed_value": str(observed),
        "threshold_value": str(threshold),
        "details": details,
    }
