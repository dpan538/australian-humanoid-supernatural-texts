from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml

from collection_expansion_common import now_iso, write_csv
from lib.target_gap_leads import LEAD_FIELDS, score_lead, upsert_lead


ROOT = Path(__file__).resolve().parents[2]
PRIORITY_STATES = ["WA", "SA", "NT", "TAS", "ACT"]
PREFERRED_FAMILIES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "national_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "museum_heritage_page",
    "museum_collection",
    "heritage_register",
    "historical_society",
    "public_history_site",
    "broadcast_catalogue",
    "public_broadcast_metadata",
    "public_domain_texts",
    "national_library_catalogue",
    "archive_finding_aid",
    "newsletter_archive",
    "journal_index",
    "public_pdf_index",
}
SAFE_ACCESS = {"public_html", "catalogue_manual_or_html", "public_web", "semi_automated_metadata", "manual_search_task", "metadata_first"}
DISALLOWED_TEXT = ["trove api", "google", "bing", "paywall", "login", "captcha", "token", "tourism", "paranormal aggregator", "wikipedia", "yowie map", "hauntedplaces"]
AGGREGATOR_TEXT = ["ayr", "wikipedia", "tourism", "hauntedplaces", "paranormal", "yowie map"]
TERMS = ["ghost", "haunted", "apparition", "phantom", "yowie", "bunyip", "min min", "local legend", "haunted hotel", "haunted gaol"]
LOCALITIES = {
    "WA": ["Fremantle", "Kalgoorlie", "Albany", "Perth", "Broome", "Geraldton"],
    "SA": ["Adelaide", "Kapunda", "Burra", "Moonta", "Port Adelaide", "Mount Gambier"],
    "NT": ["Darwin", "Katherine", "Alice Springs", "Tennant Creek", "Pine Creek"],
    "TAS": ["Hobart", "Launceston", "Port Arthur", "Queenstown", "Zeehan"],
    "ACT": ["Canberra", "Acton", "Kingston", "Yarralumla", "Hall"],
}
YEARS = list(range(1926, 1977))
METADATA_YEARS = list(range(1955, 1977))
TIME_BANDS = [(1926, 1934), (1935, 1944), (1945, 1954), (1955, 1964), (1965, 1976)]

SCHEDULE_FIELDS = [
    "task_id",
    "run_id",
    "planned_layer",
    "task_type",
    "source_id",
    "source_name",
    "source_tier",
    "source_family",
    "route_family",
    "target_state",
    "target_locality",
    "inferred_year",
    "time_band",
    "term",
    "title",
    "description",
    "url",
    "source_chain_json",
    "evidence_gap",
    "constraint_blocker",
    "recommended_next_action",
    "priority_score",
    "priority_bucket",
    "robots_status",
    "rights_status",
    "ethics_status",
    "is_priority_item",
    "is_target_period",
    "is_non_aggregator",
]

AUX_FIELDS = [
    "intelligence_id",
    "run_id",
    "source_table",
    "source_row_id",
    "intelligence_type",
    "intelligence_status",
    "intelligence_score",
    "priority_bucket",
    "title",
    "description",
    "url",
    "source_name",
    "source_tier",
    "source_family",
    "route_family",
    "target_state",
    "target_locality",
    "inferred_year",
    "coverage_start_year",
    "coverage_end_year",
    "time_band",
    "temporal_signal",
    "term_signal",
    "place_signal",
    "evidence_gap",
    "constraint_blocker",
    "recommended_next_action",
    "source_chain_json",
    "robots_status",
    "rights_status",
    "ethics_status",
    "duplicate_key",
    "duplicate_status",
    "created_at",
    "updated_at",
]

ITEM_FIELDS = [
    "item_id",
    "run_id",
    "layer",
    "linked_table",
    "linked_row_id",
    "source_name",
    "source_tier",
    "source_family",
    "route_family",
    "target_state",
    "target_locality",
    "inferred_year",
    "time_band",
    "temporal_signal",
    "term_signal",
    "priority_score",
    "priority_bucket",
    "evidence_gap",
    "constraint_blocker",
    "is_priority_item",
    "is_target_period",
    "is_non_aggregator",
    "duplicate_key",
    "duplicate_status",
    "created_at",
    "updated_at",
]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def read_yaml_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []


def source_id(row: dict[str, Any]) -> str:
    return str(row.get("route_id") or row.get("source_id") or row.get("candidate_source_name") or row.get("source_name") or "")


def source_states(row: dict[str, Any]) -> list[str]:
    states = row.get("states")
    if isinstance(states, list) and states:
        return [state for state in states if state in PRIORITY_STATES] or PRIORITY_STATES
    state = row.get("state") or row.get("state_guess")
    return [state] if state in PRIORITY_STATES else PRIORITY_STATES


def normalize_source(row: dict[str, Any]) -> dict[str, Any]:
    rid = source_id(row)
    return {
        "source_id": rid,
        "source_name": row.get("source_name") or row.get("candidate_source_name") or row.get("institution") or rid or "Unknown source",
        "source_tier": row.get("source_tier") or row.get("source_tier_guess") or "B",
        "source_family": row.get("source_family") or row.get("route_family") or row.get("route_family_guess") or "source_atlas_route",
        "route_family": row.get("route_family") or row.get("route_family_guess") or "public_history_site",
        "states": source_states(row),
        "url": row.get("official_url") or row.get("base_url") or row.get("candidate_url") or row.get("url") or row.get("search_url") or "",
        "search_url_template": row.get("search_url_template") or row.get("candidate_url") or row.get("official_url") or row.get("base_url") or "",
        "access_method": row.get("access_method") or row.get("collection_mode") or "",
        "evidence_or_discovery": row.get("evidence_or_discovery") or row.get("evidence_or_discovery_guess") or "evidence_possible",
        "allowed_content_mode": row.get("allowed_content_mode") or row.get("collection_mode") or "metadata_only",
        "noauth_allowed": row.get("noauth_allowed", True),
        "api_key_required": row.get("api_key_required") or bool(row.get("api_key_env")),
        "login_required": row.get("login_required", False),
        "paywall_required": row.get("paywall_required", False),
        "respect_robots": row.get("respect_robots", row.get("robots_check_required", True)),
        "notes": row.get("notes") or row.get("reason_discovered") or "",
    }


def safe_source(row: dict[str, Any]) -> bool:
    text = " ".join(str(row.get(key) or "").lower() for key in ["source_id", "source_name", "route_family", "url", "search_url_template", "notes", "access_method"])
    if row.get("api_key_required") or row.get("login_required") or row.get("paywall_required"):
        return False
    if "trove" in text and "api" in text:
        return False
    if any(token in text for token in DISALLOWED_TEXT):
        return False
    if row.get("evidence_or_discovery") == "manual_only_sensitive":
        return False
    if row.get("source_tier") not in {"A", "B", "C", "D"}:
        return False
    if row.get("source_tier") == "D" and row.get("evidence_or_discovery") not in {"evidence_only_if_original_source_identified", "discovery_only"}:
        return False
    if row.get("route_family") not in PREFERRED_FAMILIES:
        return False
    return True


def is_non_aggregator(row: dict[str, Any]) -> int:
    text = " ".join(str(row.get(key) or "").lower() for key in ["source_name", "source_family", "route_family", "url"])
    return 0 if any(token in text for token in AGGREGATOR_TEXT) else 1


def build_url(template: str, term: str, state: str, year: int, locality: str) -> str:
    if not template:
        return ""
    query = f"{term} {locality or state} {year}".strip()
    if "{query}" in template:
        return template.replace("{query}", quote_plus(query))
    separator = "&" if "?" in template else "?"
    return f"{template}{separator}q={quote_plus(query)}"


def time_band(year: int) -> str:
    for start, end in TIME_BANDS:
        if start <= year <= end:
            return f"{start}-{end}"
    return "unknown"


def task_priority(row: dict[str, Any], state: str, year: int, term: str, layer: str) -> tuple[float, str]:
    score = 0.0
    if row.get("source_tier") in {"A", "B", "C"}:
        score += 20
    if state in PRIORITY_STATES:
        score += 20
    if row.get("route_family") in PREFERRED_FAMILIES:
        score += 15
    if 1926 <= year <= 1976:
        score += 30
    if term:
        score += 30
    if layer == "auxiliary_source_intelligence":
        score -= 20
    score = max(0.0, min(100.0, score))
    if score >= 80:
        return score, "PRIORITY_LEAD"
    if score >= 60:
        return score, "GOOD_LEAD"
    if score >= 40:
        return score, "WEAK_LEAD"
    return score, "HOLD"


def load_safe_sources() -> list[dict[str, Any]]:
    paths = [
        ROOT / "config" / "noauth_open_source_seeds_expanded.yml",
        ROOT / "config" / "noauth_open_source_seeds.yml",
        ROOT / "config" / "source_registry.yml",
    ]
    rows: dict[str, dict[str, Any]] = {}
    for path in paths:
        for raw in read_yaml_rows(path):
            source = normalize_source(raw)
            if safe_source(source):
                rows[source["source_id"] or source["source_name"]] = source
    return sorted(rows.values(), key=lambda row: (row["route_family"], row["source_name"]))


def make_schedule(run_id: str, target_new_items: int) -> list[dict[str, Any]]:
    sources = load_safe_sources()
    if not sources:
        sources = [
            {
                "source_id": "fallback_state_library_catalogue",
                "source_name": "Fallback State Library Catalogue",
                "source_tier": "B",
                "source_family": "state_library_catalogue",
                "route_family": "state_library_catalogue",
                "states": PRIORITY_STATES,
                "url": "",
                "search_url_template": "",
                "evidence_or_discovery": "evidence_possible",
            }
        ]
    rows: list[dict[str, Any]] = []

    def add(layer: str, task_type: str, source: dict[str, Any], state: str, year: int, term: str, locality: str) -> None:
        if len(rows) >= target_new_items:
            return
        score, bucket = task_priority(source, state, year, term, layer)
        if layer == "target_gap_lead":
            evidence_gap = "missing_item_url;source_route_task"
            blocker = "missing_item_url"
            action = "route_research_needed"
        elif layer == "metadata_only_lead":
            evidence_gap = "metadata_only_layer;missing_term" if not term else "metadata_only_layer;strict_record_gate_not_met"
            blocker = "missing_term" if not term else "strict_record_gate_not_met"
            action = "metadata_only_1955_1976_layer"
        else:
            evidence_gap = "auxiliary_source_intelligence;source_route_task"
            blocker = "source_route_intelligence"
            action = "keep_as_lead"
        url = build_url(str(source.get("search_url_template") or source.get("url") or ""), term, state, year, locality)
        source_chain = {
            "source_name": source.get("source_name"),
            "source_tier": source.get("source_tier"),
            "route_family": source.get("route_family"),
            "access_method": source.get("access_method"),
            "allowed_content_mode": source.get("allowed_content_mode"),
            "evidence_or_discovery": source.get("evidence_or_discovery"),
        }
        task_id = stable_id("rvts_", run_id, layer, task_type, source.get("source_id"), state, year, term, locality)
        rows.append(
            {
                "task_id": task_id,
                "run_id": run_id,
                "planned_layer": layer,
                "task_type": task_type,
                "source_id": source.get("source_id") or "",
                "source_name": source.get("source_name") or "",
                "source_tier": source.get("source_tier") or "",
                "source_family": source.get("source_family") or source.get("route_family") or "",
                "route_family": source.get("route_family") or "",
                "target_state": state,
                "target_locality": locality,
                "inferred_year": year,
                "time_band": time_band(year),
                "term": term,
                "title": f"{source.get('source_name')} {state} {year} {term or 'metadata'} expansion lead",
                "description": f"Volume expansion task for {source.get('route_family')} in {state}, {year}. This is a research-layer item, not a public record.",
                "url": url,
                "source_chain_json": json.dumps(source_chain, sort_keys=True),
                "evidence_gap": evidence_gap,
                "constraint_blocker": blocker,
                "recommended_next_action": action,
                "priority_score": score,
                "priority_bucket": bucket,
                "robots_status": "robots_check_required_before_fetch" if source.get("respect_robots", True) else "",
                "rights_status": "metadata_only",
                "ethics_status": "safe_noauth_metadata_route",
                "is_priority_item": 1 if bucket == "PRIORITY_LEAD" else 0,
                "is_target_period": 1 if 1926 <= year <= 1976 else 0,
                "is_non_aggregator": is_non_aggregator(source),
            }
        )

    target_gap_target = min(6000, max(1, round(target_new_items * 0.24))) if target_new_items else 0
    metadata_target = min(4000, max(1, round(target_new_items * 0.16))) if target_new_items > 1 else 0
    auxiliary_target = max(0, target_new_items - target_gap_target - metadata_target)
    layer_counts = Counter(row["planned_layer"] for row in rows)
    for layer, target_count in [("target_gap_lead", target_gap_target), ("metadata_only_lead", metadata_target), ("auxiliary_source_intelligence", auxiliary_target)]:
        source_index = 0
        year_pool = METADATA_YEARS if layer == "metadata_only_lead" else YEARS
        term_pool = TERMS if layer != "metadata_only_lead" else ["", "ghost", "haunted", "local legend"]
        while layer_counts[layer] < target_count and len(rows) < target_new_items:
            source = sources[source_index % len(sources)]
            states = source.get("states") or PRIORITY_STATES
            state = states[(source_index // len(sources)) % len(states)]
            year = year_pool[(source_index // max(1, len(sources) * len(states))) % len(year_pool)]
            term = term_pool[(source_index // max(1, len(sources) * len(states) * len(year_pool))) % len(term_pool)]
            locality = LOCALITIES.get(state, [state])[(source_index // 7) % len(LOCALITIES.get(state, [state]))]
            task_type = {
                "target_gap_lead": "high_yield_route_expansion",
                "metadata_only_lead": "metadata_only_1955_1976_expansion",
                "auxiliary_source_intelligence": "source_intelligence_route_task",
            }[layer]
            before = len(rows)
            add(layer, task_type, source, state, year, term, locality)
            if len(rows) > before:
                layer_counts[layer] += 1
            source_index += 1
            if source_index > target_new_items * max(2, len(sources)):
                break
    return rows[:target_new_items]


def duplicate_key(row: dict[str, Any]) -> str:
    raw = "|".join(str(row.get(key) or "").lower() for key in ["planned_layer", "source_name", "target_state", "target_locality", "inferred_year", "term", "url"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def materialize_target_lead(conn: sqlite3.Connection, row: dict[str, Any]) -> str:
    lead_type = "METADATA_ONLY_1955_1976_LEAD" if row["planned_layer"] == "metadata_only_lead" else "SOURCE_ATLAS_ROUTE_LEAD"
    lead_id = stable_id("tgl_", "research_volume_schedule", row["task_id"], row["planned_layer"])
    lead = {
        "lead_id": lead_id,
        "source_run_id": row["run_id"],
        "source_table": "research_volume_schedule",
        "source_row_id": row["task_id"],
        "lead_type": lead_type,
        "lead_status": "open",
        "lead_score": float(row["priority_score"] or 0),
        "priority_bucket": row["priority_bucket"],
        "title": row["title"],
        "description": row["description"],
        "url": row["url"],
        "source_name": row["source_name"],
        "source_tier": row["source_tier"],
        "source_family": row["source_family"],
        "route_family": row["route_family"],
        "target_state": row["target_state"],
        "target_locality": row["target_locality"],
        "inferred_year": int(row["inferred_year"]),
        "coverage_start_year": int(row["inferred_year"]),
        "coverage_end_year": int(row["inferred_year"]),
        "temporal_signal": str(row["inferred_year"]),
        "term_signal": row["term"],
        "place_signal": row["target_locality"] or row["target_state"],
        "evidence_gap": row["evidence_gap"],
        "constraint_blocker": row["constraint_blocker"],
        "recommended_next_action": row["recommended_next_action"],
        "source_chain_json": row["source_chain_json"],
        "robots_status": row["robots_status"],
        "rights_status": row["rights_status"],
        "ethics_status": row["ethics_status"],
        "duplicate_key": duplicate_key(row),
        "duplicate_status": "unchecked",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    score, bucket = score_lead(lead)
    lead["lead_score"] = max(float(row["priority_score"] or 0), score)
    lead["priority_bucket"] = "PRIORITY_LEAD" if lead["lead_score"] >= 80 else bucket
    upsert_lead(conn, lead)
    return lead_id


def materialize_auxiliary(conn: sqlite3.Connection, row: dict[str, Any]) -> str:
    intelligence_id = stable_id("auxsi_", "research_volume_schedule", row["task_id"])
    ts = now_iso()
    aux = {
        "intelligence_id": intelligence_id,
        "run_id": row["run_id"],
        "source_table": "research_volume_schedule",
        "source_row_id": row["task_id"],
        "intelligence_type": row["task_type"],
        "intelligence_status": "open",
        "intelligence_score": row["priority_score"],
        "priority_bucket": row["priority_bucket"],
        "title": row["title"],
        "description": row["description"],
        "url": row["url"],
        "source_name": row["source_name"],
        "source_tier": row["source_tier"],
        "source_family": row["source_family"],
        "route_family": row["route_family"],
        "target_state": row["target_state"],
        "target_locality": row["target_locality"],
        "inferred_year": row["inferred_year"],
        "coverage_start_year": row["inferred_year"],
        "coverage_end_year": row["inferred_year"],
        "time_band": row["time_band"],
        "temporal_signal": str(row["inferred_year"]),
        "term_signal": row["term"],
        "place_signal": row["target_locality"] or row["target_state"],
        "evidence_gap": row["evidence_gap"],
        "constraint_blocker": row["constraint_blocker"],
        "recommended_next_action": row["recommended_next_action"],
        "source_chain_json": row["source_chain_json"],
        "robots_status": row["robots_status"],
        "rights_status": row["rights_status"],
        "ethics_status": row["ethics_status"],
        "duplicate_key": duplicate_key(row),
        "duplicate_status": "unchecked",
        "created_at": ts,
        "updated_at": ts,
    }
    placeholders = ", ".join(["?"] * len(AUX_FIELDS))
    updates = ", ".join(f"{field}=excluded.{field}" for field in AUX_FIELDS if field not in {"intelligence_id", "created_at"})
    conn.execute(
        f"INSERT INTO auxiliary_source_intelligence ({', '.join(AUX_FIELDS)}) VALUES ({placeholders}) ON CONFLICT(intelligence_id) DO UPDATE SET {updates}",
        tuple(aux.get(field) for field in AUX_FIELDS),
    )
    return intelligence_id


def insert_volume_item(conn: sqlite3.Connection, row: dict[str, Any], linked_table: str, linked_row_id: str) -> None:
    ts = now_iso()
    item = {
        "item_id": stable_id("rvi_", row["run_id"], row["task_id"], linked_table, linked_row_id),
        "run_id": row["run_id"],
        "layer": row["planned_layer"],
        "linked_table": linked_table,
        "linked_row_id": linked_row_id,
        "source_name": row["source_name"],
        "source_tier": row["source_tier"],
        "source_family": row["source_family"],
        "route_family": row["route_family"],
        "target_state": row["target_state"],
        "target_locality": row["target_locality"],
        "inferred_year": row["inferred_year"],
        "time_band": row["time_band"],
        "temporal_signal": str(row["inferred_year"]),
        "term_signal": row["term"],
        "priority_score": row["priority_score"],
        "priority_bucket": row["priority_bucket"],
        "evidence_gap": row["evidence_gap"],
        "constraint_blocker": row["constraint_blocker"],
        "is_priority_item": row["is_priority_item"],
        "is_target_period": row["is_target_period"],
        "is_non_aggregator": row["is_non_aggregator"],
        "duplicate_key": duplicate_key(row),
        "duplicate_status": "unchecked",
        "created_at": ts,
        "updated_at": ts,
    }
    placeholders = ", ".join(["?"] * len(ITEM_FIELDS))
    updates = ", ".join(f"{field}=excluded.{field}" for field in ITEM_FIELDS if field not in {"item_id", "created_at"})
    conn.execute(
        f"INSERT INTO research_volume_items ({', '.join(ITEM_FIELDS)}) VALUES ({placeholders}) ON CONFLICT(item_id) DO UPDATE SET {updates}",
        tuple(item.get(field) for field in ITEM_FIELDS),
    )


def write_schedule(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, SCHEDULE_FIELDS)


def summarize_items(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    rows = [dict(row) for row in conn.execute("SELECT * FROM research_volume_items WHERE run_id=?", (run_id,)).fetchall()]
    layers = Counter(row["layer"] for row in rows)
    return {
        "total_new_items": len(rows),
        "provisional_records": layers.get("provisional_record", 0),
        "target_gap_leads": layers.get("target_gap_lead", 0),
        "metadata_only_leads": layers.get("metadata_only_lead", 0),
        "auxiliary_source_intelligence": layers.get("auxiliary_source_intelligence", 0),
        "priority_items": sum(1 for row in rows if int(row.get("is_priority_item") or 0)),
        "target_period_items": sum(1 for row in rows if int(row.get("is_target_period") or 0)),
        "non_aggregator_items": sum(1 for row in rows if int(row.get("is_non_aggregator") or 0)),
    }
