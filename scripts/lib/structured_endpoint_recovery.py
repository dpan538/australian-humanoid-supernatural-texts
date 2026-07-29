from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from collection_expansion_common import now_iso, stable_candidate_id, write_csv
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, insert_provisional_record, is_api_url, make_duplicate_key
from lib.autoharvest_gap import classify_gap_candidate, insert_temporal_evidence, provisional_id_for_candidate, update_candidate_gap_fields, update_provisional_gap_fields
from lib.noauth_web import allowed_by_robots, extract_jsonld, extract_links, normalize_url
from lib.structured_endpoints import EndpointRecord, clean_html, score_endpoint_record


USER_AGENT = "AusFiguresStructuredEndpointRecoveryBot/0.1 metadata-first no-login no-api"
TARGET_START = 1926
TARGET_END = 1976
PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
DETAIL_ENDPOINT_TYPES = {"ATOM_AtoM", "OMEKA_API", "WORDPRESS_REST", "RSS_ATOM", "OAI_PMH", "IIIF"}
DEFAULT_TERMS = [
    "ghost",
    "apparition",
    "haunted",
    "phantom",
    "yowie",
    "yahoo",
    "hairy man",
    "wild man",
    "ape man",
    "giant man",
    "bunyip",
    "min min",
    "fisher's ghost",
    "white lady",
    "haunted gaol",
    "haunted jail",
    "haunted hotel",
    "haunted station",
    "local legend",
]
NEAR_MISS_FIELDS = [
    "near_miss_id",
    "run_id",
    "endpoint_record_id",
    "endpoint_id",
    "endpoint_query_id",
    "source_name",
    "source_tier",
    "endpoint_type",
    "route_family",
    "item_url",
    "item_id",
    "title",
    "description",
    "date_text",
    "inferred_year",
    "coverage_start_year",
    "coverage_end_year",
    "place_text",
    "controlled_term_hits",
    "temporal_evidence_json",
    "gate_reasons_json",
    "near_miss_type",
    "recoverability_score",
    "recovery_action",
    "recovery_status",
    "detail_url",
    "enrichment_attempted",
    "enriched_record_id",
    "created_at",
    "updated_at",
]
ENRICHED_FIELDS = [
    "enriched_record_id",
    "run_id",
    "near_miss_id",
    "endpoint_record_id",
    "source_name",
    "source_tier",
    "endpoint_type",
    "detail_url",
    "item_url",
    "title",
    "description",
    "date_text",
    "inferred_year",
    "coverage_start_year",
    "coverage_end_year",
    "place_text",
    "controlled_term_hits",
    "temporal_evidence_json",
    "item_level_confidence",
    "target_gap_score",
    "target_gap_eligible",
    "gate_reasons_json",
    "evidence_source_name",
    "evidence_source_url",
    "access_source_name",
    "access_source_url",
    "metadata_json",
    "created_at",
]


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def safe_json(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def text_blob(row: dict[str, Any], include_query: bool = False) -> str:
    parts = [
        row.get("title"),
        row.get("description"),
        row.get("date_text"),
        row.get("subject_terms"),
        row.get("place_text"),
        row.get("format_text"),
    ]
    if include_query:
        parts.extend([row.get("item_url"), row.get("query_text"), row.get("controlled_term"), row.get("date_term"), row.get("locality")])
    return " ".join(str(part or "") for part in parts)


def configured_terms(config: dict[str, Any] | None = None) -> list[str]:
    config = config or {}
    terms = config.get("target_queries", {}).get("controlled_terms") or config.get("term_gate", {}).get("controlled_terms") or DEFAULT_TERMS
    return [str(term).lower() for term in terms if str(term or "").strip()]


def stored_controlled_hits(row: dict[str, Any]) -> list[str]:
    hits = safe_json(row.get("controlled_term_hits"), [])
    if isinstance(hits, list):
        return [str(hit) for hit in hits if str(hit or "").strip()]
    return []


def has_record_term(row: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    if stored_controlled_hits(row):
        return True
    haystack = text_blob(row, include_query=False).lower()
    return any(term in haystack for term in configured_terms(config))


def has_query_term_hint(row: dict[str, Any], config: dict[str, Any] | None = None) -> bool:
    haystack = " ".join(str(row.get(key) or "") for key in ["query_text", "controlled_term", "item_url"]).lower()
    return any(term in haystack for term in configured_terms(config))


def year_in_target(value: Any) -> bool:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return False
    return TARGET_START <= year <= TARGET_END


def years_in_text(value: str) -> list[int]:
    years: list[int] = []
    for match in re.finditer(r"\b(18\d{2}|19\d{2}|20\d{2})\b", value or ""):
        year = int(match.group(1))
        if 1800 <= year <= 2030 and year not in years:
            years.append(year)
    return years


def has_target_date(row: dict[str, Any]) -> bool:
    if year_in_target(row.get("inferred_year")):
        return True
    start = row.get("coverage_start_year")
    end = row.get("coverage_end_year")
    try:
        if start not in {None, ""} and end not in {None, ""} and int(start) <= TARGET_END and int(end) >= TARGET_START:
            return True
    except (TypeError, ValueError):
        pass
    return any(TARGET_START <= year <= TARGET_END for year in years_in_text(str(row.get("date_text") or "")))


def has_any_date_hint(row: dict[str, Any]) -> bool:
    if row.get("inferred_year") not in {None, ""} or row.get("coverage_start_year") not in {None, ""} or row.get("coverage_end_year") not in {None, ""}:
        return True
    return bool(years_in_text(text_blob(row, include_query=True)))


def is_duplicate_or_noise(row: dict[str, Any]) -> bool:
    reasons = [str(reason) for reason in safe_json(row.get("gate_reasons_json"), [])]
    dup = str(row.get("duplicate_status") or "").lower()
    return dup not in {"", "unchecked", "unique", "probably_unique", "unique_or_probably_unique"} or "duplicate" in reasons or any(reason.startswith("noise:") for reason in reasons)


def is_disallowed_detail_url(url: str) -> bool:
    lower = str(url or "").lower()
    blocked = ["api.trove.nla.gov.au", "googleapis.com", "api.bing.microsoft.com", "bing.microsoft.com", "login", "captcha"]
    return not lower.startswith(("http://", "https://")) or any(token in lower for token in blocked) or is_api_url(url)


def looks_truncated(row: dict[str, Any]) -> bool:
    title = str(row.get("title") or "").strip().lower()
    desc = str(row.get("description") or "").strip()
    if title in {"skip to navigation", "skip to content", "search", "home"}:
        return True
    return bool(row.get("item_url")) and len(desc) < 80


def endpoint_detail_type(endpoint_type: str) -> str:
    return {
        "ATOM_AtoM": "AtoM_DETAIL_REQUIRED",
        "OMEKA_API": "OMEKA_ITEM_DETAIL_REQUIRED",
        "WORDPRESS_REST": "WORDPRESS_POST_DETAIL_REQUIRED",
        "RSS_ATOM": "RSS_ITEM_DETAIL_REQUIRED",
        "OAI_PMH": "OAI_RECORD_DETAIL_REQUIRED",
    }.get(endpoint_type, "")


def classify_near_miss(row: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    reasons = [str(reason) for reason in safe_json(row.get("gate_reasons_json"), [])]
    endpoint_type = str(row.get("endpoint_type") or "")
    item_url = str(row.get("item_url") or "")
    term = has_record_term(row, config)
    date = has_target_date(row)
    if any("d_class_requires_original_source_decomposition" in reason for reason in reasons) or row.get("source_tier") == "D":
        return "D_CLASS_NEEDS_ORIGINAL"
    if endpoint_type in {"ATOM_AtoM", "OMEKA_API", "WORDPRESS_REST", "RSS_ATOM", "OAI_PMH"} and item_url:
        return endpoint_detail_type(endpoint_type)
    if term and not date:
        return "TERM_NO_DATE"
    if date and not term:
        return "DATE_NO_TERM"
    if item_url and looks_truncated(row):
        return "DESCRIPTION_TRUNCATED"
    if item_url:
        return "ITEM_URL_NEEDS_DETAIL"
    if row.get("coverage_start_year") or row.get("coverage_end_year"):
        return "COVERAGE_DATE_AMBIGUOUS"
    if any(str(reason).startswith("not_item_level") for reason in reasons):
        return "ITEM_LEVEL_LOW_CONFIDENCE"
    if has_query_term_hint(row, config) or has_any_date_hint(row):
        return "FIELD_MAPPING_SUSPECT"
    if float(row.get("target_gap_score") or 0) >= 65:
        return "TARGET_SCORE_BORDERLINE"
    metadata = safe_json(row.get("metadata_json"), {})
    metadata_values = metadata.values() if isinstance(metadata, dict) else metadata if isinstance(metadata, list) else []
    if ".pdf" in item_url.lower() or any(".pdf" in str(link).lower() for link in metadata_values):
        return "PDF_OR_MEDIA_LINK_NEEDS_SNIPPET"
    return ""


def recovery_action(near_miss_type: str, endpoint_type: str, item_url: str) -> str:
    if not item_url:
        return "HOLD_UNRECOVERABLE"
    if ".pdf" in item_url.lower().split("?", 1)[0]:
        return "PROBE_LINKED_PDF_SNIPPET"
    if near_miss_type == "AtoM_DETAIL_REQUIRED" or endpoint_type == "ATOM_AtoM":
        return "FETCH_ATOM_DETAIL"
    if near_miss_type == "OMEKA_ITEM_DETAIL_REQUIRED" or endpoint_type == "OMEKA_API":
        return "FETCH_OMEKA_ITEM"
    if near_miss_type == "WORDPRESS_POST_DETAIL_REQUIRED" or endpoint_type == "WORDPRESS_REST":
        return "FETCH_WORDPRESS_POST"
    if near_miss_type == "RSS_ITEM_DETAIL_REQUIRED" or endpoint_type == "RSS_ATOM":
        return "FETCH_RSS_ITEM_LINK"
    if near_miss_type == "OAI_RECORD_DETAIL_REQUIRED" or endpoint_type == "OAI_PMH":
        return "FETCH_OAI_RECORD"
    if near_miss_type == "PDF_OR_MEDIA_LINK_NEEDS_SNIPPET":
        return "PROBE_LINKED_PDF_SNIPPET"
    if near_miss_type == "ITEM_URL_NEEDS_DETAIL":
        return "FETCH_DETAIL_PAGE"
    return "FETCH_DETAIL_PAGE" if item_url else "HOLD_UNRECOVERABLE"


def recoverability_score(row: dict[str, Any], near_miss_type: str, config: dict[str, Any] | None = None) -> float:
    score = 0.0
    item_url = str(row.get("item_url") or "")
    if item_url:
        score += 30
    if has_record_term(row, config) or has_query_term_hint(row, config):
        score += 25
    if has_any_date_hint(row):
        score += 25
    if row.get("source_tier") in {"A", "B", "C"}:
        score += 20
    if row.get("endpoint_type") in DETAIL_ENDPOINT_TYPES:
        score += 15
    if (row.get("state") or row.get("target_state")) in PRIORITY_STATES:
        score += 10
    if not item_url:
        score -= 50
    if is_disallowed_detail_url(item_url):
        score -= 50
    if is_duplicate_or_noise(row):
        score -= 30
    if near_miss_type == "FIELD_MAPPING_SUSPECT":
        score = max(score, 40)
    return max(0.0, min(100.0, score))


def detail_url_for(row: dict[str, Any]) -> str:
    item_url = str(row.get("item_url") or "").strip()
    endpoint_type = str(row.get("endpoint_type") or "")
    if endpoint_type == "OMEKA_API" and item_url:
        return item_url
    if endpoint_type == "OAI_PMH" and row.get("endpoint_url") and row.get("item_id"):
        sep = "&" if "?" in str(row["endpoint_url"]) else "?"
        return f"{row['endpoint_url']}{sep}{urlencode({'verb': 'GetRecord', 'metadataPrefix': 'oai_dc', 'identifier': row['item_id']})}"
    return normalize_url(item_url)


def source_rows(conn: sqlite3.Connection, run_id: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT
            r.*,
            i.route_family AS route_family,
            i.state AS state,
            i.endpoint_url AS endpoint_url,
            i.base_url AS base_url,
            i.domain AS domain,
            q.query_text AS query_text,
            q.controlled_term AS controlled_term,
            q.date_term AS date_term,
            q.locality AS locality,
            q.target_state AS target_state
        FROM noauth_endpoint_records r
        LEFT JOIN noauth_endpoint_inventory i ON i.endpoint_id=r.endpoint_id
        LEFT JOIN noauth_endpoint_queries q ON q.endpoint_query_id=r.endpoint_query_id
        WHERE r.run_id=? AND COALESCE(r.target_gap_eligible, 0)=0
        ORDER BY r.created_at ASC, r.endpoint_record_id ASC
        """,
        (run_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def build_near_miss(row: dict[str, Any], run_id: str, config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    near_type = classify_near_miss(row, config)
    if not near_type:
        return None
    detail_url = detail_url_for(row)
    score = recoverability_score(row, near_type, config)
    action = recovery_action(near_type, str(row.get("endpoint_type") or ""), detail_url)
    ts = now_iso()
    near_id = stable_id("senm_", run_id, row.get("endpoint_record_id"), detail_url, near_type)
    status = "queued" if score > 0 and action != "HOLD_UNRECOVERABLE" else "held_unrecoverable"
    return {
        "near_miss_id": near_id,
        "run_id": run_id,
        "endpoint_record_id": row.get("endpoint_record_id"),
        "endpoint_id": row.get("endpoint_id"),
        "endpoint_query_id": row.get("endpoint_query_id"),
        "source_name": row.get("source_name"),
        "source_tier": row.get("source_tier"),
        "endpoint_type": row.get("endpoint_type"),
        "route_family": row.get("route_family"),
        "item_url": row.get("item_url"),
        "item_id": row.get("item_id"),
        "title": row.get("title"),
        "description": row.get("description"),
        "date_text": row.get("date_text"),
        "inferred_year": row.get("inferred_year"),
        "coverage_start_year": row.get("coverage_start_year"),
        "coverage_end_year": row.get("coverage_end_year"),
        "place_text": row.get("place_text"),
        "controlled_term_hits": row.get("controlled_term_hits"),
        "temporal_evidence_json": row.get("temporal_evidence_json"),
        "gate_reasons_json": row.get("gate_reasons_json"),
        "near_miss_type": near_type,
        "recoverability_score": score,
        "recovery_action": action,
        "recovery_status": status,
        "detail_url": detail_url,
        "enrichment_attempted": 0,
        "enriched_record_id": "",
        "created_at": ts,
        "updated_at": ts,
    }


def insert_near_miss(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    placeholders = ", ".join(["?"] * len(NEAR_MISS_FIELDS))
    updates = ", ".join(f"{field}=excluded.{field}" for field in NEAR_MISS_FIELDS if field not in {"near_miss_id", "created_at"})
    conn.execute(
        f"""
        INSERT INTO structured_endpoint_near_misses ({", ".join(NEAR_MISS_FIELDS)})
        VALUES ({placeholders})
        ON CONFLICT(near_miss_id) DO UPDATE SET {updates}
        """,
        tuple(row.get(field) for field in NEAR_MISS_FIELDS),
    )


def insert_enriched_record(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    placeholders = ", ".join(["?"] * len(ENRICHED_FIELDS))
    conn.execute(
        f"""
        INSERT OR REPLACE INTO structured_endpoint_enriched_records ({", ".join(ENRICHED_FIELDS)})
        VALUES ({placeholders})
        """,
        tuple(row.get(field) for field in ENRICHED_FIELDS),
    )


def strip_to_snippet(text: str, limit: int = 1500) -> str:
    cleaned = re.sub(r"\s+", " ", clean_html(text or "")).strip()
    return cleaned[:limit]


def html_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.I | re.S)
    return strip_to_snippet(match.group(1), 300) if match else ""


def meta_content(html: str, names: list[str]) -> str:
    for name in names:
        pattern = rf"<meta\b[^>]*(?:name|property)=[\"']{re.escape(name)}[\"'][^>]*content=[\"']([^\"']+)[\"'][^>]*>"
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if match:
            return strip_to_snippet(unescape(match.group(1)), 1000)
        pattern = rf"<meta\b[^>]*content=[\"']([^\"']+)[\"'][^>]*(?:name|property)=[\"']{re.escape(name)}[\"'][^>]*>"
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if match:
            return strip_to_snippet(unescape(match.group(1)), 1000)
    return ""


def heading_text(html: str) -> str:
    values: list[str] = []
    for match in re.finditer(r"<h[1-3]\b[^>]*>(.*?)</h[1-3]>", html or "", flags=re.I | re.S):
        value = strip_to_snippet(match.group(1), 250)
        if value:
            values.append(value)
    return "; ".join(dict.fromkeys(values))[:1000]


def visible_text_sample(html: str, limit: int = 2000) -> str:
    text = re.sub(r"<(script|style|nav|footer|header)\b.*?</\1>", " ", html or "", flags=re.I | re.S)
    return strip_to_snippet(text, limit)


def jsonld_value(data: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str):
            return strip_to_snippet(value, 1200)
        if isinstance(value, list):
            values = [jsonld_value(item, ["name", "headline", "title", "@value"]) if isinstance(item, dict) else str(item) for item in value]
            joined = "; ".join(value for value in values if value)
            if joined:
                return strip_to_snippet(joined, 1200)
        if isinstance(value, dict):
            nested = jsonld_value(value, ["name", "headline", "title", "@value"])
            if nested:
                return nested
    return ""


def parse_jsonld_metadata(html: str) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for data in extract_jsonld(html):
        title = jsonld_value(data, ["name", "headline", "title"])
        desc = jsonld_value(data, ["description", "articleBody", "abstract"])
        date = jsonld_value(data, ["datePublished", "dateCreated", "dateModified", "temporalCoverage"])
        subjects = jsonld_value(data, ["keywords", "about", "genre"])
        place = jsonld_value(data, ["spatialCoverage", "contentLocation", "location"])
        url = jsonld_value(data, ["url", "@id", "mainEntityOfPage"])
        if title and not merged.get("title"):
            merged["title"] = title
        if desc and not merged.get("description"):
            merged["description"] = desc
        if date and not merged.get("date_text"):
            merged["date_text"] = date
        if subjects and not merged.get("subject_terms"):
            merged["subject_terms"] = subjects
        if place and not merged.get("place_text"):
            merged["place_text"] = place
        if url and not merged.get("item_url"):
            merged["item_url"] = url
    return merged


def parse_labelled_html_metadata(html: str) -> dict[str, str]:
    text = html or ""
    pairs: dict[str, str] = {}
    for match in re.finditer(r"<(?:dt|th)\b[^>]*>(.*?)</(?:dt|th)>\s*<(?:dd|td)\b[^>]*>(.*?)</(?:dd|td)>", text, flags=re.I | re.S):
        key = strip_to_snippet(match.group(1), 100).lower()
        value = strip_to_snippet(match.group(2), 1000)
        if key and value:
            pairs[key] = value
    out: dict[str, str] = {}
    label_map = {
        "title": ["title", "name"],
        "date_text": ["date", "dates", "created", "publication date"],
        "description": ["description", "scope and content", "scope/content", "abstract", "summary"],
        "subject_terms": ["subject", "subjects", "tags"],
        "place_text": ["place", "places", "coverage", "spatial coverage", "location"],
        "identifier": ["identifier", "reference code"],
        "source": ["source"],
    }
    for field, labels in label_map.items():
        for key, value in pairs.items():
            if any(label in key for label in labels):
                out[field] = value
                break
    return out


def dc_values(data: dict[str, Any], keys: list[str]) -> str:
    values: list[str] = []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    values.append(str(item.get("@value") or item.get("value") or item.get("display_title") or item.get("o:label") or ""))
                else:
                    values.append(str(item or ""))
        elif isinstance(value, dict):
            values.append(str(value.get("@value") or value.get("value") or value.get("display_title") or ""))
        elif value:
            values.append(str(value))
    return strip_to_snippet("; ".join(value for value in values if value), 1500)


def parse_json_metadata(text: str, endpoint_type: str) -> dict[str, Any]:
    try:
        data = json.loads(text or "")
    except Exception:
        return {}
    if isinstance(data, list):
        data = data[0] if data and isinstance(data[0], dict) else {}
    if not isinstance(data, dict):
        return {}
    if endpoint_type == "IIIF" or "metadata" in data and ("@context" in data or "items" in data):
        metadata = data.get("metadata") or []
        meta_text = "; ".join(f"{dc_values(item, ['label'])}: {dc_values(item, ['value'])}" for item in metadata if isinstance(item, dict))
        return {
            "title": dc_values(data, ["label", "title", "name"]),
            "description": strip_to_snippet(meta_text or dc_values(data, ["summary", "description"]), 1500),
            "date_text": strip_to_snippet(meta_text, 1000),
            "subject_terms": strip_to_snippet(meta_text, 1000),
            "metadata": data,
        }
    return {
        "title": dc_values(data, ["title", "o:title", "dcterms:title"]),
        "description": dc_values(data, ["description", "dcterms:description", "content"]),
        "date_text": dc_values(data, ["date", "dcterms:date", "created", "modified"]),
        "subject_terms": dc_values(data, ["subjects", "subject", "dcterms:subject", "tags"]),
        "place_text": dc_values(data, ["coverage", "dcterms:coverage", "spatial", "spatial_coverage"]),
        "source": dc_values(data, ["source", "dcterms:source"]),
        "item_url": dc_values(data, ["url", "o:url", "@id", "link"]),
        "metadata": data,
    }


def parse_oai_record(text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(text or "")
    except ET.ParseError:
        return {}

    def collect(names: list[str]) -> str:
        out: list[str] = []
        for child in root.iter():
            tag = child.tag.split("}", 1)[-1].lower()
            if tag in names and child.text:
                out.append(child.text.strip())
        return strip_to_snippet("; ".join(dict.fromkeys(out)), 1500)

    return {
        "title": collect(["title"]),
        "description": collect(["description"]),
        "date_text": collect(["date"]),
        "subject_terms": collect(["subject"]),
        "place_text": collect(["coverage"]),
        "item_url": collect(["identifier"]),
    }


def parse_html_metadata(html: str, url: str) -> dict[str, Any]:
    jsonld = parse_jsonld_metadata(html)
    labelled = parse_labelled_html_metadata(html)
    title = jsonld.get("title") or labelled.get("title") or meta_content(html, ["og:title", "twitter:title"]) or heading_text(html) or html_title(html)
    desc = jsonld.get("description") or labelled.get("description") or meta_content(html, ["description", "og:description", "twitter:description"]) or visible_text_sample(html)
    date = jsonld.get("date_text") or labelled.get("date_text") or meta_content(html, ["article:published_time", "date", "dc.date", "dcterms.date"])
    subjects = jsonld.get("subject_terms") or labelled.get("subject_terms") or meta_content(html, ["keywords", "dc.subject", "dcterms.subject"])
    place = jsonld.get("place_text") or labelled.get("place_text") or meta_content(html, ["dc.coverage", "dcterms.coverage"])
    links = extract_links(html, url)
    iiif = next((link["url"] for link in links if "iiif" in link["url"].lower() and "manifest" in link["url"].lower()), "")
    pdf = next((link["url"] for link in links if ".pdf" in link["url"].lower().split("?", 1)[0]), "")
    return {
        "title": strip_to_snippet(title, 500),
        "description": strip_to_snippet(desc, 1500),
        "date_text": strip_to_snippet(date, 500),
        "subject_terms": strip_to_snippet(subjects, 1000),
        "place_text": strip_to_snippet(place, 500),
        "item_url": jsonld.get("item_url") or url,
        "iiif_manifest_url": iiif,
        "linked_pdf_url": pdf,
        "metadata": {"jsonld": extract_jsonld(html), "labelled": labelled, "links_sample": links[:20]},
    }


def fetch_url(url: str, session: requests.Session, timeout: float = 12.0, rate_limit: float = 0.25) -> tuple[int, str, str]:
    if is_disallowed_detail_url(url):
        return 0, "", "blocked_policy"
    if not allowed_by_robots(url, USER_AGENT):
        return 0, "", "robots_denied_or_unknown"
    time.sleep(max(0.0, rate_limit))
    try:
        response = session.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, text/html;q=0.8"},
            timeout=(3.0, timeout),
            allow_redirects=True,
        )
    except Exception:
        return 0, "", "fetch_exception"
    return response.status_code, response.text[:2_000_000] if response.text else "", response.headers.get("content-type", "")


def fetch_detail_metadata(near: dict[str, Any], session: requests.Session) -> tuple[dict[str, Any], str]:
    url = str(near.get("detail_url") or near.get("item_url") or "")
    if not url:
        return {}, "missing_detail_url"
    status, text, content_type = fetch_url(url, session)
    if status != 200 or not text:
        return {}, f"fetch_failed:{status}:{content_type}"
    endpoint_type = str(near.get("endpoint_type") or "")
    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        metadata = parse_json_metadata(text, endpoint_type)
    elif "xml" in content_type.lower() or text.lstrip().startswith("<OAI") or "<OAI-PMH" in text[:500]:
        metadata = parse_oai_record(text)
    else:
        metadata = parse_html_metadata(text, url)
    metadata.setdefault("metadata", {})
    metadata["fetched_url"] = url
    metadata["content_type"] = content_type
    return metadata, "ok"


def merge_enriched_metadata(near: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    merged = dict(near)
    for field in ["title", "description", "date_text", "place_text", "item_url"]:
        if metadata.get(field):
            merged[field] = metadata[field]
    if metadata.get("subject_terms"):
        merged["subject_terms"] = metadata["subject_terms"]
    if metadata.get("item_url"):
        merged["item_url"] = metadata["item_url"]
    return merged


def row_to_endpoint_record(row: dict[str, Any], metadata: dict[str, Any]) -> EndpointRecord:
    subjects = []
    subject_text = row.get("subject_terms") or metadata.get("subject_terms") or ""
    if isinstance(subject_text, str):
        subjects = [part.strip() for part in re.split(r"[;,\n]", subject_text) if part.strip()]
    return EndpointRecord(
        item_url=str(row.get("item_url") or row.get("detail_url") or ""),
        item_id=str(row.get("item_id") or row.get("item_url") or row.get("detail_url") or ""),
        title=str(row.get("title") or ""),
        description=str(row.get("description") or ""),
        date_text=str(row.get("date_text") or ""),
        coverage_start_year=row.get("coverage_start_year"),
        coverage_end_year=row.get("coverage_end_year"),
        subjects=subjects,
        place_text=str(row.get("place_text") or ""),
        source_name=str(row.get("source_name") or ""),
        source_tier=str(row.get("source_tier") or ""),
        endpoint_type=str(row.get("endpoint_type") or ""),
        raw_metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True)[:5000],
    )


def endpoint_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "endpoint_id": row.get("endpoint_id") or row.get("near_miss_id"),
        "route_id": row.get("route_id") or row.get("endpoint_id"),
        "source_name": row.get("source_name"),
        "source_tier": row.get("source_tier"),
        "route_family": row.get("route_family"),
        "state": row.get("target_state") or row.get("state"),
        "endpoint_type": row.get("endpoint_type"),
        "endpoint_url": row.get("detail_url") or row.get("item_url"),
    }


def query_context(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_text": row.get("query_text") or row.get("controlled_term") or "",
        "controlled_term": row.get("controlled_term") or "",
        "target_state": row.get("target_state") or row.get("state") or "",
        "locality": row.get("locality") or "",
    }


def score_enriched(row: dict[str, Any], metadata: dict[str, Any], config: dict[str, Any], run_id: str, conn: sqlite3.Connection) -> tuple[dict[str, Any], dict[str, Any]]:
    record = row_to_endpoint_record(row, metadata)
    endpoint = endpoint_context(row)
    query = query_context(row)
    preliminary = score_endpoint_record(record, endpoint, query, config, run_id)
    candidate = preliminary["candidate"]
    candidate["run_id"] = run_id
    candidate["evidence_source_url"] = row.get("detail_url") or row.get("item_url")
    candidate["access_source_url"] = row.get("item_url") or row.get("detail_url")
    candidate["date_published"] = row.get("date_text") or ""
    candidate["duplicate_key"] = make_duplicate_key(candidate)
    candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
    scored = score_endpoint_record(record, endpoint, query, config, run_id, candidate["duplicate_status"])
    scored["candidate"]["candidate_id"] = stable_candidate_id(
        endpoint.get("endpoint_id") or "",
        row.get("near_miss_id"),
        row.get("detail_url") or row.get("item_url"),
        row.get("title"),
        row.get("date_text"),
        run_id,
    )
    scored["candidate"]["run_id"] = run_id
    scored["candidate"]["duplicate_key"] = make_duplicate_key(scored["candidate"])
    scored["candidate"]["duplicate_status"] = candidate["duplicate_status"]
    return scored, scored["candidate"]


def enriched_record_row(near: dict[str, Any], merged: dict[str, Any], metadata: dict[str, Any], scored: dict[str, Any], run_id: str) -> dict[str, Any]:
    decision = scored["decision"]
    enriched_id = stable_id("seer_", run_id, near.get("near_miss_id"), merged.get("detail_url") or merged.get("item_url"), merged.get("title"))
    return {
        "enriched_record_id": enriched_id,
        "run_id": run_id,
        "near_miss_id": near.get("near_miss_id"),
        "endpoint_record_id": near.get("endpoint_record_id"),
        "source_name": near.get("source_name"),
        "source_tier": near.get("source_tier"),
        "endpoint_type": near.get("endpoint_type"),
        "detail_url": near.get("detail_url"),
        "item_url": merged.get("item_url") or near.get("item_url"),
        "title": merged.get("title"),
        "description": merged.get("description"),
        "date_text": merged.get("date_text"),
        "inferred_year": decision.temporal.extracted_year,
        "coverage_start_year": decision.temporal.coverage_start_year,
        "coverage_end_year": decision.temporal.coverage_end_year,
        "place_text": merged.get("place_text"),
        "controlled_term_hits": json.dumps(scored.get("controlled_term_hits", [])),
        "temporal_evidence_json": json.dumps(decision.temporal.as_dict()),
        "item_level_confidence": decision.item_level_confidence,
        "target_gap_score": scored.get("target_gap_score", 0.0),
        "target_gap_eligible": 1 if decision.target_gap_eligible else 0,
        "gate_reasons_json": json.dumps(decision.reasons),
        "evidence_source_name": near.get("source_name"),
        "evidence_source_url": near.get("detail_url") or near.get("item_url"),
        "access_source_name": near.get("source_name"),
        "access_source_url": near.get("item_url") or near.get("detail_url"),
        "metadata_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True)[:5000],
        "created_at": now_iso(),
    }


def process_near_miss(conn: sqlite3.Connection, near: dict[str, Any], config: dict[str, Any], run_id: str, session: requests.Session, execute: bool) -> dict[str, Any]:
    if near.get("recovery_action") == "HOLD_UNRECOVERABLE" or float(near.get("recoverability_score") or 0) <= 0:
        return {"near_miss_id": near.get("near_miss_id"), "status": "held_unrecoverable", "target_gap_eligible": 0}
    metadata, status = fetch_detail_metadata(near, session)
    if status != "ok":
        if execute:
            conn.execute(
                "UPDATE structured_endpoint_near_misses SET enrichment_attempted=1, recovery_status=?, updated_at=? WHERE near_miss_id=?",
                ("paused_fetch_failed", now_iso(), near.get("near_miss_id")),
            )
        return {"near_miss_id": near.get("near_miss_id"), "status": status, "target_gap_eligible": 0}
    merged = merge_enriched_metadata(near, metadata)
    scored, candidate = score_enriched(merged, metadata, config, run_id, conn)
    row = enriched_record_row(near, merged, metadata, scored, run_id)
    if execute:
        insert_enriched_record(conn, row)
        insert_harvest_candidate(conn, candidate)
        update_candidate_gap_fields(conn, candidate["candidate_id"], scored["decision"])
        if scored["decision"].target_gap_eligible and insert_provisional_record(conn, candidate, scored.get("target_gap_score", 90)):
            update_provisional_gap_fields(conn, candidate["candidate_id"], scored["decision"], harvest_mode="structured_endpoint_enriched_gap")
            insert_temporal_evidence(conn, run_id, candidate["candidate_id"], provisional_id_for_candidate(candidate), scored["decision"], row.get("evidence_source_url") or "")
        status_value = "target_gap_eligible" if row["target_gap_eligible"] else "enriched_near_miss"
        conn.execute(
            """
            UPDATE structured_endpoint_near_misses
            SET enrichment_attempted=1, recovery_status=?, enriched_record_id=?, updated_at=?
            WHERE near_miss_id=?
            """,
            (status_value, row["enriched_record_id"], now_iso(), near.get("near_miss_id")),
        )
    return {"near_miss_id": near.get("near_miss_id"), "status": "ok", "target_gap_eligible": row["target_gap_eligible"], "enriched_record_id": row["enriched_record_id"]}


def write_near_miss_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, NEAR_MISS_FIELDS)


def write_enriched_outputs(conn: sqlite3.Connection, run_id: str, review_dir: Path) -> dict[str, int]:
    conn.row_factory = sqlite3.Row
    targets = [dict(row) for row in conn.execute("SELECT * FROM structured_endpoint_enriched_records WHERE run_id=? AND target_gap_eligible=1 ORDER BY target_gap_score DESC", (run_id,)).fetchall()]
    remaining = [dict(row) for row in conn.execute("SELECT * FROM structured_endpoint_near_misses WHERE run_id=? AND recovery_status IN ('queued','paused_fetch_failed','enriched_near_miss') ORDER BY recoverability_score DESC", (run_id,)).fetchall()]
    write_csv(review_dir / "enriched_target_gap_candidates.csv", targets, ENRICHED_FIELDS)
    write_csv(review_dir / "enriched_near_misses_remaining.csv", remaining, NEAR_MISS_FIELDS)
    return {"targets": len(targets), "remaining": len(remaining)}
