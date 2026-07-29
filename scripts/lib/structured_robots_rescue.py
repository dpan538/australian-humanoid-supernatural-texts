from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests

from collection_expansion_common import now_iso, stable_candidate_id, table_exists, write_csv
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, insert_provisional_record, make_duplicate_key
from lib.autoharvest_gap import insert_temporal_evidence, provisional_id_for_candidate, update_candidate_gap_fields, update_provisional_gap_fields
from lib.structured_endpoint_recovery import (
    ENRICHED_FIELDS,
    NEAR_MISS_FIELDS,
    USER_AGENT,
    configured_terms,
    enriched_record_row,
    has_target_date,
    insert_enriched_record,
    parse_html_metadata,
    parse_json_metadata,
    parse_oai_record,
    row_to_endpoint_record,
    safe_json,
    score_enriched,
    stable_id,
    strip_to_snippet,
    years_in_text,
)
from lib.structured_endpoints import clean_html


ROBOTS_STATUSES = {
    "ROBOTS_EXPLICITLY_DENIED",
    "ROBOTS_UNKNOWN_TIMEOUT",
    "ROBOTS_UNKNOWN_HTTP_ERROR",
    "ROBOTS_UNKNOWN_MISSING_ROBOTS",
    "ROBOTS_ALLOWED_BUT_FETCH_FAILED",
}
URL_ISSUES = {
    "DETAIL_URL_MISSING",
    "DETAIL_URL_MALFORMED",
    "DETAIL_URL_OFF_DOMAIN",
    "DETAIL_URL_ARCHIVED_OR_ACCESS_PLATFORM",
    "DETAIL_URL_LOGIN_OR_AUTH",
    "DETAIL_URL_DUPLICATE_OF_ENDPOINT",
    "DETAIL_URL_CANONICALIZATION_NEEDED",
}
FETCHABLE_ENDPOINT_TYPES = {"RSS_ATOM", "ATOM_AtoM", "OMEKA_API", "WORDPRESS_REST", "OAI_PMH", "IIIF"}
BLOCKED_HOST_TOKENS = {
    "api.trove.nla.gov.au",
    "googleapis.com",
    "api.bing.microsoft.com",
    "bing.microsoft.com",
}
LOGIN_TOKENS = ("/login", "signin", "sign-in", "auth", "sso", "captcha")
ARCHIVED_OR_ACCESS_TOKENS = ("webcache", "archive.org/web", "openlibrary.org", "gutenberg.org", "wikisource.org")
TARGET_START = 1926
TARGET_END = 1976


@dataclass
class RobotsDiagnosis:
    robots_status: str
    robots_url: str
    robots_error: str = ""
    http_status_if_known: str = ""
    allowed: bool = False


def sha_short(*parts: Any, prefix: str = "") -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fetch_robots_text(robots_url: str, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        response = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=(2.0, timeout), allow_redirects=True)
    except requests.Timeout:
        return 0, "", "timeout"
    except Exception as exc:
        return 0, "", exc.__class__.__name__
    return response.status_code, response.text or "", ""


def robots_url_for(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def diagnose_robots(url: str, user_agent: str = USER_AGENT) -> RobotsDiagnosis:
    robots_url = robots_url_for(url)
    if not robots_url:
        return RobotsDiagnosis("ROBOTS_UNKNOWN_HTTP_ERROR", "", "malformed_url", "", False)
    status, text, error = fetch_robots_text(robots_url)
    if error == "timeout":
        return RobotsDiagnosis("ROBOTS_UNKNOWN_TIMEOUT", robots_url, error, "", False)
    if status in {401, 403}:
        return RobotsDiagnosis("ROBOTS_EXPLICITLY_DENIED", robots_url, f"robots_http_{status}", str(status), False)
    if status == 404:
        return RobotsDiagnosis("ROBOTS_UNKNOWN_MISSING_ROBOTS", robots_url, "robots_missing", str(status), False)
    if status != 200 or not text:
        return RobotsDiagnosis("ROBOTS_UNKNOWN_HTTP_ERROR", robots_url, error or f"robots_http_{status}", str(status or ""), False)
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(text.splitlines())
    allowed = bool(parser.can_fetch(user_agent, url))
    return RobotsDiagnosis("ROBOTS_ALLOWED_BUT_FETCH_FAILED" if allowed else "ROBOTS_EXPLICITLY_DENIED", robots_url, "" if allowed else "disallow_rule", str(status), allowed)


def host(value: str) -> str:
    return urlparse(str(value or "")).netloc.lower().removeprefix("www.")


def same_domain(a: str, b: str) -> bool:
    ha = host(a)
    hb = host(b)
    return bool(ha and hb and (ha == hb or ha.endswith("." + hb) or hb.endswith("." + ha)))


def canonical_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme or not parsed.netloc:
        return ""
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    return parsed._replace(path=path, fragment="").geturl()


def url_issue(row: dict[str, Any]) -> str:
    detail_url = str(row.get("detail_url") or row.get("item_url") or "").strip()
    if not detail_url:
        return "DETAIL_URL_MISSING"
    parsed = urlparse(detail_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "DETAIL_URL_MALFORMED"
    lower = detail_url.lower()
    if any(token in lower for token in LOGIN_TOKENS):
        return "DETAIL_URL_LOGIN_OR_AUTH"
    if any(token in lower for token in ARCHIVED_OR_ACCESS_TOKENS) or any(token in parsed.netloc.lower() for token in BLOCKED_HOST_TOKENS):
        return "DETAIL_URL_ARCHIVED_OR_ACCESS_PLATFORM"
    endpoint_url = str(row.get("endpoint_url") or row.get("base_url") or "")
    domain = str(row.get("domain") or "").strip().lower()
    if endpoint_url and not same_domain(detail_url, endpoint_url):
        return "DETAIL_URL_OFF_DOMAIN"
    if domain and domain not in parsed.netloc.lower():
        return "DETAIL_URL_OFF_DOMAIN"
    if endpoint_url and canonical_url(detail_url).rstrip("/") == canonical_url(endpoint_url).rstrip("/"):
        return "DETAIL_URL_DUPLICATE_OF_ENDPOINT"
    if "informationobject/browse" in lower or (parsed.query and not re.search(r"/(items?|posts?|informationobject|collections?)/[^/?#]+", parsed.path, flags=re.I)):
        return "DETAIL_URL_DUPLICATE_OF_ENDPOINT"
    if canonical_url(detail_url) != detail_url:
        return "DETAIL_URL_CANONICALIZATION_NEEDED"
    return ""


def recommended_recovery_path(row: dict[str, Any], issue: str, robots_status: str) -> str:
    endpoint_type = str(row.get("endpoint_type") or "")
    if issue == "DETAIL_URL_LOGIN_OR_AUTH":
        return "HOLD_LOGIN_OR_AUTH"
    if issue in {"DETAIL_URL_MISSING", "DETAIL_URL_MALFORMED"}:
        return "HOLD_MALFORMED_URL"
    if robots_status == "ROBOTS_EXPLICITLY_DENIED":
        return "HOLD_ROBOTS_DENIED"
    if endpoint_type == "RSS_ATOM":
        return "USE_RSS_INLINE_CONTENT"
    if endpoint_type == "ATOM_AtoM":
        return "USE_ATOM_ATOM_FEED_ENTRY"
    if endpoint_type == "OAI_PMH":
        return "USE_OAI_GETRECORD_METADATA"
    if endpoint_type == "OMEKA_API":
        return "USE_OMEKA_ITEM_API"
    if endpoint_type == "WORDPRESS_REST":
        return "USE_WORDPRESS_REST_ITEM"
    if issue or robots_status.startswith("ROBOTS_UNKNOWN"):
        return "USE_EXISTING_ENDPOINT_METADATA"
    return "DISCOVER_ALLOWED_DETAIL_ALTERNATIVE"


def joined_near_misses(conn: sqlite3.Connection, run_id: str, where: str = "", params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    suffix = f" AND {where}" if where else ""
    rows = conn.execute(
        f"""
        SELECT
            n.*,
            r.metadata_json AS record_metadata_json,
            r.subject_terms AS subject_terms,
            r.creator AS creator,
            r.publisher AS publisher,
            r.format_text AS format_text,
            r.rights_text AS rights_text,
            r.item_level_confidence AS original_item_level_confidence,
            r.target_gap_score AS original_target_gap_score,
            r.duplicate_status AS duplicate_status,
            i.endpoint_url AS endpoint_url,
            i.base_url AS base_url,
            i.domain AS domain,
            i.state AS state,
            i.route_id AS route_id,
            i.source_id AS source_id,
            q.query_text AS query_text,
            q.controlled_term AS controlled_term,
            q.date_term AS date_term,
            q.locality AS locality,
            q.target_state AS target_state
        FROM structured_endpoint_near_misses n
        LEFT JOIN noauth_endpoint_records r ON r.endpoint_record_id=n.endpoint_record_id
        LEFT JOIN noauth_endpoint_inventory i ON i.endpoint_id=n.endpoint_id
        LEFT JOIN noauth_endpoint_queries q ON q.endpoint_query_id=n.endpoint_query_id
        WHERE n.run_id=?{suffix}
        ORDER BY n.recoverability_score DESC, n.created_at ASC, n.near_miss_id ASC
        """,
        (run_id, *params),
    ).fetchall()
    return [dict(row) for row in rows]


def flatten_json(value: Any, depth: int = 0) -> list[str]:
    if depth > 6:
        return []
    if value is None or value == "":
        return []
    if isinstance(value, dict):
        out: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                out.extend(flatten_json(item, depth + 1))
            else:
                out.append(f"{key}: {item}")
        return out
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(flatten_json(item, depth + 1))
        return out
    return [str(value)]


def first_text(elem: ET.Element, names: set[str]) -> str:
    values: list[str] = []
    for child in elem.iter():
        tag = child.tag.split("}", 1)[-1].lower()
        if tag in names and child.text:
            values.append(clean_html(child.text))
        if tag == "link" and "link" in names:
            href = child.attrib.get("href")
            if href:
                values.append(href)
    return strip_to_snippet("; ".join(dict.fromkeys(value for value in values if value)), 1500)


def parse_xml_excerpt(xml_text: str) -> dict[str, Any]:
    if not xml_text:
        return {}
    try:
        elem = ET.fromstring(xml_text)
    except ET.ParseError:
        wrapped = f"<root>{xml_text}</root>"
        try:
            elem = ET.fromstring(wrapped)
        except ET.ParseError:
            return {}
    return {
        "title": first_text(elem, {"title"}),
        "description": first_text(elem, {"description", "summary", "encoded", "content", "abstract"}),
        "date_text": first_text(elem, {"pubdate", "published", "updated", "date", "issued", "created"}),
        "subject_terms": first_text(elem, {"subject", "category", "keywords", "tag"}),
        "place_text": first_text(elem, {"coverage", "spatial", "place"}),
        "item_url": first_text(elem, {"link", "id"}),
        "metadata": {"xml_excerpt": xml_text[:5000]},
    }


def merge_metadata_fields(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for field in ["title", "description", "date_text", "subject_terms", "place_text", "item_url", "format_text", "rights_text"]:
        if extra.get(field):
            if merged.get(field) and field in {"description", "subject_terms", "place_text"} and str(extra[field]) not in str(merged[field]):
                merged[field] = strip_to_snippet(f"{merged[field]}; {extra[field]}", 2000)
            else:
                merged[field] = extra[field]
    meta = merged.get("metadata") if isinstance(merged.get("metadata"), dict) else {}
    if isinstance(extra.get("metadata"), dict):
        meta.update(extra["metadata"])
    merged["metadata"] = meta
    return merged


def parse_existing_metadata(row: dict[str, Any]) -> dict[str, Any]:
    raw = safe_json(row.get("record_metadata_json") or row.get("metadata_json"), {})
    base = {
        "title": row.get("title") or "",
        "description": row.get("description") or "",
        "date_text": row.get("date_text") or "",
        "subject_terms": row.get("subject_terms") or "",
        "place_text": row.get("place_text") or "",
        "item_url": row.get("item_url") or row.get("detail_url") or "",
        "format_text": row.get("format_text") or "",
        "rights_text": row.get("rights_text") or "",
        "metadata": {"source": "existing_endpoint_metadata", "raw": raw},
    }
    endpoint_type = str(row.get("endpoint_type") or "")
    if isinstance(raw, dict):
        if raw.get("xml_excerpt"):
            base = merge_metadata_fields(base, parse_xml_excerpt(str(raw.get("xml_excerpt") or "")))
        if raw.get("html_excerpt"):
            base = merge_metadata_fields(base, parse_html_metadata(str(raw.get("html_excerpt") or ""), base["item_url"]))
        json_like = parse_json_metadata(json.dumps(raw, ensure_ascii=False), endpoint_type)
        base = merge_metadata_fields(base, json_like)
        flattened = strip_to_snippet("; ".join(flatten_json(raw)), 2500)
        if flattened and flattened not in str(base.get("description")):
            base["description"] = strip_to_snippet(" ".join([str(base.get("description") or ""), flattened]), 2500)
    elif isinstance(raw, list):
        json_like = parse_json_metadata(json.dumps(raw, ensure_ascii=False), endpoint_type)
        base = merge_metadata_fields(base, json_like)
    base["metadata"]["parsed_at"] = now_iso()
    base["metadata"]["endpoint_type"] = endpoint_type
    return base


def strict_text(metadata: dict[str, Any]) -> str:
    return " ".join(
        str(metadata.get(field) or "")
        for field in ["title", "description", "date_text", "subject_terms", "place_text", "format_text"]
    )


def strict_term_hits(metadata: dict[str, Any], config: dict[str, Any] | None = None) -> list[str]:
    text = strict_text(metadata).lower()
    return [term for term in configured_terms(config) if term in text]


def target_date_hint(metadata: dict[str, Any]) -> bool:
    row = {
        "date_text": metadata.get("date_text") or strict_text(metadata),
        "inferred_year": metadata.get("inferred_year"),
        "coverage_start_year": metadata.get("coverage_start_year"),
        "coverage_end_year": metadata.get("coverage_end_year"),
    }
    return has_target_date(row) or any(TARGET_START <= year <= TARGET_END for year in years_in_text(strict_text(metadata)))


def remaining_gate_type(metadata: dict[str, Any], row: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    term = bool(strict_term_hits(metadata, config))
    date = target_date_hint(metadata)
    if term and not date:
        return "STILL_TERM_NO_DATE"
    if date and not term:
        return "STILL_DATE_NO_TERM"
    if row.get("near_miss_type") in {"FIELD_MAPPING_SUSPECT", "ITEM_LEVEL_LOW_CONFIDENCE"}:
        return "STILL_FIELD_MAPPING_SUSPECT"
    if row.get("detail_url") or row.get("item_url"):
        return "STILL_ITEM_URL_NEEDS_DETAIL"
    return "STILL_ROBOTS_DETAIL_REQUIRED"


def load_default_config(config_path: Path | None = None) -> dict[str, Any]:
    import yaml

    path = config_path or Path(__file__).resolve().parents[2] / "config" / "noauth_structured_endpoints.yml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def score_metadata_only(conn: sqlite3.Connection, near: dict[str, Any], metadata: dict[str, Any], run_id: str, config: dict[str, Any], harvest_mode: str, execute: bool) -> dict[str, Any]:
    merged = dict(near)
    for field in ["title", "description", "date_text", "place_text", "item_url", "format_text"]:
        if metadata.get(field):
            merged[field] = metadata[field]
    if metadata.get("subject_terms"):
        merged["subject_terms"] = metadata["subject_terms"]
    if metadata.get("item_url"):
        merged["item_url"] = metadata["item_url"]
    merged["detail_url"] = near.get("detail_url") or metadata.get("item_url") or near.get("item_url")
    scored, candidate = score_enriched(merged, metadata, config, run_id, conn)
    term_hits = strict_term_hits(metadata, config)
    has_date = target_date_hint(metadata)
    strict_reasons = list(scored["decision"].reasons)
    if not term_hits and "missing_controlled_term" not in strict_reasons:
        strict_reasons.append("missing_controlled_term")
    if not has_date and "missing_explicit_target_temporal_evidence" not in strict_reasons:
        strict_reasons.append("missing_explicit_target_temporal_evidence")
    if not term_hits or not has_date:
        scored["decision"].target_gap_eligible = False
        scored["decision"].reasons = strict_reasons
        scored["decision"].reason = ";".join(strict_reasons)
        scored["target_gap_score"] = min(float(scored.get("target_gap_score") or 0), 70.0)
    candidate["candidate_id"] = stable_candidate_id(
        near.get("endpoint_id") or "",
        near.get("near_miss_id"),
        merged.get("item_url") or merged.get("detail_url"),
        merged.get("title"),
        merged.get("date_text"),
        harvest_mode,
    )
    candidate["run_id"] = run_id
    candidate["evidence_source_url"] = merged.get("detail_url") or merged.get("item_url")
    candidate["access_source_url"] = near.get("item_url") or near.get("detail_url") or candidate.get("access_source_url")
    candidate["duplicate_key"] = make_duplicate_key(candidate)
    candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
    row = enriched_record_row(near, merged, metadata, scored, run_id)
    row["enriched_record_id"] = stable_id("seer_", run_id, harvest_mode, near.get("near_miss_id"), merged.get("title"), merged.get("date_text"))
    row["controlled_term_hits"] = json.dumps(term_hits)
    row["target_gap_eligible"] = 1 if scored["decision"].target_gap_eligible else 0
    row["target_gap_score"] = scored.get("target_gap_score", 0.0)
    row["gate_reasons_json"] = json.dumps(scored["decision"].reasons)
    row["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)[:5000]
    if execute:
        insert_enriched_record(conn, row)
        if row["target_gap_eligible"]:
            insert_harvest_candidate(conn, candidate)
            update_candidate_gap_fields(conn, candidate["candidate_id"], scored["decision"])
            if insert_provisional_record(conn, candidate, row["target_gap_score"]):
                update_provisional_gap_fields(conn, candidate["candidate_id"], scored["decision"], harvest_mode=harvest_mode)
                insert_temporal_evidence(conn, run_id, candidate["candidate_id"], provisional_id_for_candidate(candidate), scored["decision"], row.get("evidence_source_url") or "")
        status_value = "target_gap_eligible" if row["target_gap_eligible"] else remaining_gate_type(metadata, near, config)
        conn.execute(
            """
            UPDATE structured_endpoint_near_misses
            SET enrichment_attempted=1, recovery_status=?, enriched_record_id=?, updated_at=?
            WHERE near_miss_id=?
            """,
            (status_value, row["enriched_record_id"], now_iso(), near.get("near_miss_id")),
        )
    return {
        "near_miss_id": near.get("near_miss_id"),
        "enriched_record_id": row["enriched_record_id"],
        "target_gap_eligible": row["target_gap_eligible"],
        "target_gap_score": row["target_gap_score"],
        "remaining_gate": remaining_gate_type(metadata, near, config) if not row["target_gap_eligible"] else "",
        "controlled_term_hits": "; ".join(term_hits),
        "target_date_basis": scored["decision"].target_date_basis,
        "item_format": scored["decision"].item_format,
        "title": row.get("title") or "",
        "date_text": row.get("date_text") or "",
        "item_url": row.get("item_url") or "",
        "gate_reasons_json": row.get("gate_reasons_json") or "[]",
    }


def counts_by(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> dict[str, int]:
    return {str(row[0] or ""): int(row[1] or 0) for row in conn.execute(sql, params).fetchall()}


def ensure_near_miss_tables(db: Path) -> None:
    from migrate_structured_near_miss_v1 import migrate

    migrate(db)


def write_enriched_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "near_miss_id",
        "enriched_record_id",
        "target_gap_eligible",
        "target_gap_score",
        "remaining_gate",
        "controlled_term_hits",
        "target_date_basis",
        "item_format",
        "title",
        "date_text",
        "item_url",
        "gate_reasons_json",
    ]
    write_csv(path, rows, fields)


def load_alternatives(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def target_and_remaining_counts(conn: sqlite3.Connection, run_id: str) -> dict[str, int]:
    targets = 0
    if table_exists(conn, "structured_endpoint_enriched_records"):
        targets = int(conn.execute("SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=? AND target_gap_eligible=1", (run_id,)).fetchone()[0] or 0)
    remaining = int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM structured_endpoint_near_misses
            WHERE run_id=? AND recovery_status NOT IN ('target_gap_eligible','HOLD_ROBOTS_DENIED','HOLD_MALFORMED_URL','HOLD_LOGIN_OR_AUTH','exhausted_unrecoverable')
            """,
            (run_id,),
        ).fetchone()[0]
        or 0
    )
    return {"target_gap_records": targets, "recoverable_remaining": remaining}
