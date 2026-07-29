from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from collection_expansion_common import now_iso, table_exists, write_csv
from lib.structured_endpoint_recovery import configured_terms, safe_json, years_in_text


LEAD_FIELDS = [
    "lead_id",
    "source_run_id",
    "source_table",
    "source_row_id",
    "lead_type",
    "lead_status",
    "lead_score",
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

PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
ROUTE_FAMILY_BONUS = {"local_history_serial", "council_local_studies", "state_archive", "state_library", "state_archive_catalogue", "state_library_catalogue", "broadcast_catalogue"}
DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "constraint_decision.yml"


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = path or DEFAULT_CONFIG
    if not cfg.exists():
        return {}
    return yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}


def output_path(config: dict[str, Any], key: str, default: str) -> Path:
    return Path(config.get("outputs", {}).get(key) or default)


def text_blob(row: dict[str, Any]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in [
            "title",
            "description",
            "snippet",
            "date_text",
            "date_published",
            "term_signal",
            "source_stated_place_text",
            "target_locality",
            "place_text",
            "url",
        ]
    )


def term_signal(row: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    hits = safe_json(row.get("controlled_term_hits"), [])
    if isinstance(hits, list) and hits:
        return "; ".join(str(hit) for hit in hits if str(hit or "").strip())
    text = text_blob(row).lower()
    return "; ".join(term for term in configured_terms(config) if term in text)


def temporal_signal(row: dict[str, Any]) -> tuple[str, int | None]:
    for key in ["inferred_year", "source_publication_year", "narrative_year", "record_publication_year"]:
        value = row.get(key)
        try:
            year = int(value) if value not in {None, ""} else None
        except (TypeError, ValueError):
            year = None
        if year and 1926 <= year <= 1976:
            return str(year), year
    for year in years_in_text(text_blob(row)):
        if 1926 <= year <= 1976:
            return str(year), year
    start = row.get("coverage_start_year")
    end = row.get("coverage_end_year")
    try:
        if start not in {None, ""} and end not in {None, ""} and int(start) <= 1976 and int(end) >= 1926:
            return f"{start}-{end}", int(start)
    except (TypeError, ValueError):
        pass
    return "", None


def evidence_gap_for(term: str, temporal: str, url: str, row: dict[str, Any]) -> str:
    reasons = [str(item) for item in safe_json(row.get("gate_reasons_json"), [])]
    gaps: list[str] = []
    robots = str(row.get("robots_status") or "")
    if "UNKNOWN" in robots:
        gaps.append("robots_unknown")
    elif "DENIED" in robots:
        gaps.append("robots_denied")
    if not temporal:
        gaps.append("missing_date")
    if not term:
        gaps.append("missing_term")
    if not url:
        gaps.append("missing_item_url")
    if row.get("source_tier") == "D" or any("d_class" in reason for reason in reasons):
        gaps.append("d_class_needs_original")
    if "discovery_only" in " ".join(reasons).lower() or str(row.get("evidence_or_discovery") or "").lower() == "discovery_only":
        gaps.append("discovery_only_needs_evidence")
    if row.get("source_tier") in {None, "", "E"}:
        gaps.append("source_unknown")
    if any("not_item_level" in reason for reason in reasons):
        gaps.append("field_mapping_sparse")
    ethics = str(row.get("ethics_status") or "")
    if ethics in {"sensitive", "restricted", "manual_only"}:
        gaps.append("ethics_sensitive")
    rights = str(row.get("rights_status") or "")
    if rights in {"restricted", "paywalled", "login_required"}:
        gaps.append("rights_unclear")
    return ";".join(dict.fromkeys(gaps)) or "strict_gate_incomplete"


def blocker_for(gaps: str, row: dict[str, Any]) -> str:
    if "robots_denied" in gaps:
        return "robots_denied"
    if "robots_unknown" in gaps or "ROBOTS_UNKNOWN" in str(row.get("robots_status") or ""):
        return "robots_unknown"
    if "ethics_sensitive" in gaps:
        return "ethics_sensitive"
    if "rights_unclear" in gaps:
        return "rights_unclear"
    if "d_class_needs_original" in gaps:
        return "d_class_needs_original"
    if "discovery_only_needs_evidence" in gaps:
        return "discovery_only_needs_evidence"
    if "missing_date" in gaps:
        return "missing_date"
    if "missing_term" in gaps:
        return "missing_term"
    if "missing_item_url" in gaps:
        return "missing_item_url"
    return "strict_record_gate_not_met"


def action_for(lead_type: str, blocker: str, gaps: str) -> str:
    if lead_type == "MANUAL_SENSITIVE_HOLD" or blocker == "ethics_sensitive":
        return "pause_route"
    if blocker.startswith("robots"):
        return "request_robots_or_permission_clarification"
    if blocker == "d_class_needs_original":
        return "source_chain_replacement_search"
    if lead_type == "METADATA_ONLY_1955_1976_LEAD":
        return "metadata_only_1955_1976_layer"
    if "human_review_needed" in gaps:
        return "tiny_review_top_n"
    if lead_type in {"SEARCH_FORM_ROUTE_LEAD", "SOURCE_ATLAS_ROUTE_LEAD", "STRUCTURED_ENDPOINT_ROUTE_LEAD"}:
        return "route_research_needed"
    return "keep_as_lead"


def duplicate_key(row: dict[str, Any]) -> str:
    raw = "|".join(str(row.get(key) or "").strip().lower() for key in ["title", "url", "source_name", "temporal_signal"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_lead(source_table: str, source_row_id: str, lead_type: str, row: dict[str, Any], config: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    term = overrides.get("term_signal")
    if term is None:
        term = term_signal(row, config)
    temporal = overrides.get("temporal_signal")
    inferred = overrides.get("inferred_year")
    if temporal is None:
        temporal, inferred = temporal_signal(row)
    url = str(overrides.get("url") or row.get("url") or row.get("item_url") or row.get("detail_url") or row.get("evidence_source_url") or row.get("candidate_url") or "")
    gaps = overrides.get("evidence_gap") or evidence_gap_for(str(term or ""), str(temporal or ""), url, row)
    blocker = overrides.get("constraint_blocker") or blocker_for(str(gaps), row)
    action = overrides.get("recommended_next_action") or action_for(lead_type, blocker, str(gaps))
    ts = now_iso()
    lead = {
        "lead_id": stable_id("tgl_", source_table, source_row_id, lead_type, url, row.get("title") or row.get("candidate_source_name")),
        "source_run_id": row.get("run_id") or row.get("source_run_id"),
        "source_table": source_table,
        "source_row_id": source_row_id,
        "lead_type": lead_type,
        "lead_status": overrides.get("lead_status") or "open",
        "lead_score": float(overrides.get("lead_score") or 0),
        "priority_bucket": overrides.get("priority_bucket") or "",
        "title": overrides.get("title") or row.get("title") or row.get("candidate_source_name") or row.get("source_name") or "Untitled lead",
        "description": overrides.get("description") or row.get("description") or row.get("snippet") or row.get("reason_discovered") or "",
        "url": url,
        "source_name": overrides.get("source_name") or row.get("source_name") or row.get("evidence_source_name") or row.get("candidate_source_name") or "",
        "source_tier": overrides.get("source_tier") or row.get("source_tier") or row.get("source_tier_guess") or "",
        "source_family": overrides.get("source_family") or row.get("source_family") or row.get("endpoint_type") or row.get("term_family") or "",
        "route_family": overrides.get("route_family") or row.get("route_family") or row.get("route_family_guess") or "",
        "target_state": overrides.get("target_state") or row.get("target_state") or row.get("state") or row.get("state_guess") or "",
        "target_locality": overrides.get("target_locality") or row.get("target_locality") or row.get("locality_hint") or row.get("locality") or "",
        "inferred_year": inferred,
        "coverage_start_year": row.get("coverage_start_year"),
        "coverage_end_year": row.get("coverage_end_year"),
        "temporal_signal": temporal or "",
        "term_signal": term or "",
        "place_signal": overrides.get("place_signal") or row.get("place_text") or row.get("source_stated_place_text") or row.get("target_locality") or row.get("locality_hint") or "",
        "evidence_gap": gaps,
        "constraint_blocker": blocker,
        "recommended_next_action": action,
        "source_chain_json": overrides.get("source_chain_json") or json.dumps({k: row.get(k) for k in ["source_name", "source_tier", "route_family", "evidence_source_url", "access_source_url", "original_source_name"] if row.get(k)}, sort_keys=True),
        "robots_status": overrides.get("robots_status") or row.get("robots_status") or "",
        "rights_status": overrides.get("rights_status") or row.get("rights_status") or row.get("rights_text") or "",
        "ethics_status": overrides.get("ethics_status") or row.get("ethics_status") or "",
        "duplicate_key": overrides.get("duplicate_key") or "",
        "duplicate_status": overrides.get("duplicate_status") or row.get("duplicate_status") or "unchecked",
        "created_at": ts,
        "updated_at": ts,
    }
    lead["duplicate_key"] = lead["duplicate_key"] or duplicate_key(lead)
    return lead


def upsert_lead(conn: sqlite3.Connection, lead: dict[str, Any]) -> None:
    placeholders = ", ".join(["?"] * len(LEAD_FIELDS))
    updates = ", ".join(f"{field}=excluded.{field}" for field in LEAD_FIELDS if field not in {"lead_id", "created_at"})
    conn.execute(
        f"""
        INSERT INTO target_gap_leads ({", ".join(LEAD_FIELDS)})
        VALUES ({placeholders})
        ON CONFLICT(lead_id) DO UPDATE SET {updates}
        """,
        tuple(lead.get(field) for field in LEAD_FIELDS),
    )


def score_lead(row: dict[str, Any]) -> tuple[float, str]:
    score = 0.0
    term = bool(str(row.get("term_signal") or "").strip())
    temporal = bool(str(row.get("temporal_signal") or "").strip() or row.get("inferred_year"))
    url = bool(str(row.get("url") or "").strip())
    tier = str(row.get("source_tier") or "")
    route_family = str(row.get("route_family") or "")
    state = str(row.get("target_state") or "")
    blocker = str(row.get("constraint_blocker") or "")
    gaps = str(row.get("evidence_gap") or "")
    text = " ".join(str(row.get(key) or "").lower() for key in ["title", "description", "url", "lead_type"])
    if term:
        score += 30
    if temporal:
        score += 30
    if url:
        score += 20
    if tier in {"A", "B", "C"}:
        score += 20
    if state in PRIORITY_STATES:
        score += 20
    if route_family in ROUTE_FAMILY_BONUS:
        score += 15
    if row.get("source_chain_json") and row.get("source_chain_json") != "{}":
        score += 15
    if row.get("place_signal") or row.get("target_locality"):
        score += 10
    if row.get("source_name") or row.get("source_family"):
        score += 10
    ethics = str(row.get("ethics_status") or "")
    if ethics in {"sensitive", "restricted", "manual_only"} or row.get("lead_type") == "MANUAL_SENSITIVE_HOLD":
        score -= 50
        return max(0.0, min(100.0, score)), "SENSITIVE_HOLD"
    if any(token in text for token in ["tourism", "tour", "marketing", "gift shop"]):
        score -= 40
    if "discovery_only" in gaps:
        score -= 30
    if "d_class_needs_original" in gaps or tier == "D":
        score -= 30
    if "robots_denied" in gaps or blocker == "robots_denied":
        score -= 25
    if "robots_unknown" in gaps or blocker == "robots_unknown":
        score -= 15
    if "missing_date" in gaps:
        score -= 15
    if "missing_term" in gaps:
        score -= 15
    if "missing_item_url" in gaps:
        score -= 15
    score = max(0.0, min(100.0, score))
    if blocker in {"robots_denied", "robots_unknown"}:
        bucket = "BLOCKED_ROBOTS"
    elif blocker in {"d_class_needs_original", "discovery_only_needs_evidence", "rights_unclear"}:
        bucket = "BLOCKED_CONSTRAINT"
    elif score >= 80:
        bucket = "PRIORITY_LEAD"
    elif score >= 60:
        bucket = "GOOD_LEAD"
    elif score >= 40:
        bucket = "WEAK_LEAD"
    else:
        bucket = "HOLD"
    return score, bucket


def write_leads_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, LEAD_FIELDS)


def domain_for(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().removeprefix("www.")


def read_leads(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    if not table_exists(conn, "target_gap_leads"):
        return []
    return [dict(row) for row in conn.execute("SELECT * FROM target_gap_leads ORDER BY lead_score DESC, lead_id").fetchall()]
