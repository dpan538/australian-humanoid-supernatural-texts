from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import yaml

from collection_expansion_common import now_iso, stable_candidate_id, write_csv
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, insert_provisional_record, make_duplicate_key
from lib.autoharvest_gap import classify_gap_candidate, insert_temporal_evidence, provisional_id_for_candidate, update_candidate_gap_fields, update_provisional_gap_fields

PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
TARGET_TERMS = [
    "ghost",
    "haunted",
    "apparition",
    "phantom",
    "yowie",
    "bunyip",
    "min-min",
    "minmin",
    "hairy-man",
    "wild-man",
    "local-history",
    "newsletter",
    "journal",
    "bulletin",
    "historical-society",
    "gaol",
    "hotel",
    "station",
    "folklore",
    "legend",
    "1930",
    "1940",
    "1950",
    "1960",
    "1970",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_yaml_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [row for row in data if isinstance(row, dict)]


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def stable_action_id(*parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return "act_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def route_id_for_url(url: str, prefix: str = "index") -> str:
    host = urlparse(str(url or "")).netloc.lower().replace("www.", "")
    safe = re.sub(r"[^a-z0-9]+", "_", host).strip("_")[:48] or "unknown"
    return f"{prefix}_{safe}"


def domain_of(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().replace("www.", "")


def trusted_domains_from_sources(*paths: Path) -> set[str]:
    domains: set[str] = set()
    for path in paths:
        for row in read_yaml_rows(path):
            for key in ["official_url", "url", "search_url", "homepage", "access_url"]:
                value = str(row.get(key) or "")
                if value.startswith(("http://", "https://")):
                    domains.add(domain_of(value))
    return {domain for domain in domains if domain and "trove" not in domain}


def classify_recovery_status(
    target_records: int,
    near_misses: int,
    viable_pdf_routes: int,
    search_forms: int = 0,
    index_discoveries: int = 0,
    route_expansion_candidates: int = 0,
) -> str:
    if target_records >= 10:
        return "PASSED_TARGET"
    if near_misses >= 50:
        return "PASSED_NEAR_MISS"
    if viable_pdf_routes >= 20:
        return "PASSED_ROUTE_SURFACE"
    if target_records == 0 and (near_misses >= 10 or viable_pdf_routes >= 1 or search_forms >= 50 or index_discoveries > 0 or route_expansion_candidates > 0):
        return "CONTINUE_RECOVERY"
    return "FAILED_EXHAUSTED"


def write_report(path: Path, title: str, bullets: dict[str, Any], sections: dict[str, list[str]] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", f"- Generated: `{now_iso()}`"]
    lines.extend(f"- {label}: `{value}`" for label, value in bullets.items())
    for heading, rows in (sections or {}).items():
        lines.extend(["", f"## {heading}"])
        lines.extend(rows or ["- None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def candidate_from_seed(base: dict[str, Any], run_id: str, title: str, url: str, snippet: str, date_text: str = "", item_format: str = "ARTICLE_PAGE") -> dict[str, Any]:
    route_id = base.get("route_id") or route_id_for_url(url)
    source_name = base.get("source_name") or base.get("evidence_source_name") or domain_of(url)
    source_tier = base.get("source_tier") or "B"
    route_family = base.get("route_family") or "public_history_site"
    candidate = {
        "candidate_id": stable_candidate_id(str(route_id), url, url, title, date_text, snippet[:120]),
        "run_id": run_id,
        "page_id": "",
        "route_id": route_id,
        "source_id": base.get("source_id") or route_id,
        "source_name": source_name,
        "source_tier": source_tier,
        "route_family": route_family,
        "target_state": base.get("target_state") or base.get("state") or "",
        "target_locality": base.get("target_locality") or base.get("locality_hint") or base.get("state") or "",
        "time_band": base.get("time_band") or base.get("target_time_band") or "",
        "term_family": base.get("term_family") or "controlled_supernatural",
        "term": base.get("term") or "",
        "title": (title or source_name or "Gap recovery candidate")[:500],
        "snippet": (snippet or "")[:1000],
        "url": url,
        "stable_id": url,
        "date_published": date_text or base.get("date_published") or "",
        "inferred_year": None,
        "source_stated_place_text": base.get("source_stated_place_text") or "",
        "locality_hint": base.get("locality_hint") or base.get("state") or "",
        "mappability_hint": base.get("mappability_hint") or "low",
        "evidence_source_name": source_name,
        "evidence_source_url": url,
        "access_source_name": base.get("access_source_name") or source_name,
        "access_source_url": base.get("access_source_url") or url,
        "original_source_name": base.get("original_source_name") or "",
        "rights_status": base.get("rights_status") or "metadata_only",
        "ethics_status": base.get("ethics_status") or "not_sensitive",
        "metadata_only": 1,
        "candidate_score": 80,
        "duplicate_key": "",
        "duplicate_status": "unchecked",
        "noise_flags_json": "[]",
        "gate_status": "candidate",
        "gate_reasons_json": "[]",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "evidence_or_discovery": base.get("evidence_or_discovery") or "evidence_possible",
        "item_format": item_format,
        "record_publication_date_text": date_text,
    }
    return candidate


def classify_and_optionally_stage(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
    route: dict[str, Any],
    config_data: dict[str, Any],
    page_text: str,
    execute: bool,
    provisional: bool = True,
):
    candidate["duplicate_key"] = make_duplicate_key(candidate)
    candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
    decision = classify_gap_candidate(
        candidate,
        route,
        config_data,
        page_text=page_text,
        metadata={
            "record_publication_date": candidate.get("record_publication_date_text") or candidate.get("date_published"),
            "date_is_record_publication": True,
            "title": candidate.get("title"),
            "description": candidate.get("snippet"),
            "item_format": candidate.get("item_format"),
        },
    )
    candidate["gate_status"] = "target_gap_accepted" if decision.target_gap_eligible else "high_quality_near_miss" if decision.term_hit_confidence >= 0.7 or decision.temporal.confidence >= 0.7 else "candidate_hold"
    candidate["gate_reasons_json"] = json.dumps(decision.reasons)
    candidate["target_gap_eligible"] = int(decision.target_gap_eligible)
    candidate["target_gap_reason"] = decision.reason
    candidate["target_date_basis"] = decision.target_date_basis
    candidate["item_format"] = decision.item_format or candidate.get("item_format")
    if execute:
        insert_harvest_candidate(conn, candidate)
        update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
        if provisional and decision.target_gap_eligible and insert_provisional_record(conn, candidate, 90):
            update_provisional_gap_fields(conn, candidate["candidate_id"], decision)
            insert_temporal_evidence(conn, candidate["run_id"], candidate["candidate_id"], provisional_id_for_candidate(candidate), decision, candidate.get("url") or "")
    return decision, candidate


def top_counts(rows: list[dict[str, Any]], key: str, limit: int = 10) -> list[str]:
    return [f"- `{name}`: {count}" for name, count in Counter(str(row.get(key) or "") for row in rows).most_common(limit)]


def url_pattern_priority(url: str, state: str = "", route_family: str = "") -> tuple[int, list[str]]:
    hay = url.lower()
    score = 0
    reasons: list[str] = []
    matched = [term for term in TARGET_TERMS if term in hay]
    if matched:
        score += 40
        reasons.append("url_term")
    if ".pdf" in hay:
        score += 30
        reasons.append("pdf")
    if any(token in hay for token in ["newsletter", "journal", "bulletin"]):
        score += 30
        reasons.append("serial")
    if re.search(r"19[2-7]\d|1930|1940|1950|1960|1970", hay):
        score += 25
        reasons.append("year_signal")
    if state in PRIORITY_STATES:
        score += 25
        reasons.append("priority_state")
    if route_family in {"local_history_serial", "council_local_studies", "state_library_catalogue", "state_archive_catalogue"}:
        score += 15
        reasons.append("strong_route_family")
    return score, reasons


def command_block(command: str) -> str:
    return f"`{command}`"
