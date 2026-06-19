#!/usr/bin/env python3
"""Plan a second public-source collection round without fetching content.

The default mode is deliberately conservative: no network requests, no record
inserts, and no scraping. The script writes a public-source lead plan and a
location-review queue so the next live collection round can be checked before
it touches external services or the records table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import re
import sqlite3
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_alias, slugify
from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso, write_csv


DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "round_002.yml"
DEFAULT_LEADS_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_leads.csv"
DEFAULT_LOCATION_REVIEW_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_location_review.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "public_round_002_plan.md"
DEFAULT_NOISE_RULES_PATH = PROJECT_ROOT / "config" / "noise_rules.yml"
DEFAULT_METADATA_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_metadata.json"
DEFAULT_MANIFEST_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_manifest.json"

LOGGER = logging.getLogger("collect_public_round_002")

LeadRow = dict[str, Any]
LocationRow = dict[str, Any]
MissingFigureRow = dict[str, Any]

LEAD_FIELDS = [
    "round_id",
    "lead_id",
    "related_lead_ids",
    "collection_action",
    "execution_priority",
    "source_name",
    "source_type",
    "source_publicness_level",
    "source_publicness_guard",
    "source_health_status",
    "last_source_health_check",
    "figure",
    "include_status",
    "tier",
    "involves_indigenous_knowledge",
    "existing_records_summary",
    "query_id",
    "query_string",
    "query_type",
    "date_start",
    "date_end",
    "date_band",
    "expected_noise_level",
    "manual_search_url",
    "api_request_template",
    "estimated_hits",
    "alternative_query_suggestions",
    "high_noise_guard",
    "location_state_hint",
    "location_region_hint",
    "location_precision_target",
    "ethics_gate",
    "ethics_review_passed",
    "ethics_reviewed_by",
    "ethics_reviewed_date",
    "notes",
]

LOCATION_FIELDS = [
    "round_id",
    "record_id",
    "year",
    "title",
    "source_name",
    "figure",
    "url",
    "verified_places",
    "state_territories",
    "broad_regions",
    "location_precision",
    "has_uncertain_locations",
    "locations_json",
    "location_evidence",
    "needs_location_review",
    "notes",
]

LEAD_FIELD_SCHEMA = {
    "round_id": (str,),
    "lead_id": (str,),
    "related_lead_ids": (str,),
    "collection_action": (str,),
    "execution_priority": (int,),
    "source_name": (str,),
    "source_type": (str,),
    "involves_indigenous_knowledge": (int,),
    "query_string": (str,),
    "date_band": (str,),
    "high_noise_guard": (str,),
}

LOCATION_FIELD_SCHEMA = {
    "round_id": (str,),
    "record_id": (int,),
    "title": (str, type(None)),
    "location_precision": (str,),
    "has_uncertain_locations": (str,),
    "needs_location_review": (str,),
}

BLOCKING_HIGH_NOISE_GUARDS = {"BLOCKED_BARE_QUERY"}


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def load_round_config(path: str | Path) -> dict[str, Any]:
    config = read_yaml(path)
    required = [
        "round_id",
        "public_source_types",
        "validation_source_types",
        "allowed_publicness_levels",
        "planned_include_statuses",
        "historical_bands",
        "search_url_templates",
        "location_hints",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing round config key(s): {', '.join(missing)}")
    return config


def clean_query_for_bare_check(query: str) -> str:
    text = query.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return normalise_alias(text)


def forbidden_bare_terms(noise_rules_path: Path) -> set[str]:
    rules = read_yaml(noise_rules_path)
    forbidden = rules.get("bare_query_policy", {}).get("forbidden", [])
    return {normalise_alias(term) for term in forbidden}


def _normalised_policy_terms(values: list[Any]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        if isinstance(value, dict):
            value = value.get("term", "")
        if value:
            terms.add(normalise_alias(str(value)))
    return terms


def bare_query_policy(config: dict[str, Any], noise_rules_path: Path) -> dict[str, set[str]]:
    rules = read_yaml(noise_rules_path)
    noise_policy = rules.get("bare_query_policy", {})
    round_policy = config.get("bare_query_policy", {})
    return {
        "forbidden": _normalised_policy_terms(noise_policy.get("forbidden", []))
        | _normalised_policy_terms(round_policy.get("forbidden", [])),
        "manual_review": _normalised_policy_terms(round_policy.get("manual_review", [])),
        "context_sensitive": _normalised_policy_terms(round_policy.get("context_sensitive", [])),
    }


def high_noise_guard_for_query(query: str, policy: dict[str, set[str]]) -> str:
    cleaned = clean_query_for_bare_check(query)
    if cleaned in policy.get("forbidden", set()):
        return "BLOCKED_BARE_QUERY"
    if cleaned in policy.get("context_sensitive", set()):
        return "CONTEXT_SENSITIVE_REVIEW"
    if cleaned in policy.get("manual_review", set()):
        return "MANUAL_REVIEW_RECOMMENDED"
    return "ok"


def date_band_name(config: dict[str, Any], date_start: str | None, date_end: str | None) -> str:
    start = date_start or ""
    end = date_end or ""
    for band in config["historical_bands"]:
        if str(band["date_start"]) == start and str(band["date_end"]) == end:
            return band["band_name"]
    special = config.get("special_date_bands", {})
    if start in special:
        return special[start]
    return "custom_or_unbanded"


def source_enabled_for_band(config: dict[str, Any], source_type: str, band_name: str) -> bool:
    source_rules = config.get("source_band_support", {}).get(source_type, {})
    enabled = source_rules.get("enabled_bands")
    if not enabled:
        return True
    return band_name in enabled


def source_publicness_guard(config: dict[str, Any], publicness_level: str | None) -> str:
    allowed = set(config.get("allowed_publicness_levels", []))
    if publicness_level in allowed:
        return "ok_public_source"
    return "BLOCKED_NONPUBLIC_SOURCE"


def manual_search_url(
    config: dict[str, Any],
    source_type: str,
    base_url: str | None,
    query: str,
    date_start: str | None = None,
    date_end: str | None = None,
) -> str:
    encoded = quote_plus(query)
    template = base_url if base_url and "{query}" in base_url else None
    template = template or config.get("search_url_templates", {}).get(source_type)
    if not template:
        return base_url or ""
    url = template.format(
        query=encoded,
        date_start=quote_plus(date_start or ""),
        date_end=quote_plus(date_end or ""),
    )
    return url


def source_health(config: dict[str, Any], source_type: str) -> tuple[str, str]:
    health = config.get("source_health", {})
    default = health.get("default", {})
    source_health_row = health.get(source_type, default)
    return (
        source_health_row.get("status", default.get("status", "unknown")),
        source_health_row.get("last_checked", default.get("last_checked", "not yet checked")),
    )


def api_request_template(
    config: dict[str, Any],
    source_type: str,
    query: str,
    date_start: str | None,
    date_end: str | None,
) -> str:
    template = config.get("api_request_templates", {}).get(source_type, "")
    if not template:
        return ""
    return template.format(
        query=quote_plus(query),
        date_start=quote_plus(date_start or ""),
        date_end=quote_plus(date_end or ""),
    )


def estimate_hits(query: str, expected_noise_level: str | None, query_type: str, high_noise_guard: str) -> str:
    if query_type == "attention_series":
        return "not_applicable_attention_series"
    if high_noise_guard in BLOCKING_HIGH_NOISE_GUARDS:
        return "blocked_until_constrained"
    if high_noise_guard != "ok":
        return "review_first_unknown"
    noise = (expected_noise_level or "").lower()
    if noise in {"extreme", "high"}:
        return "high_review_first"
    if noise == "medium":
        return "medium_unknown"
    words = [word for word in re.split(r"\W+", clean_query_for_bare_check(query)) if word]
    if len(words) <= 1:
        return "high_unknown"
    if len(words) == 2:
        return "medium_unknown"
    return "low_medium_unknown"


def alternative_query_suggestions(query: str) -> str:
    cleaned = clean_query_for_bare_check(query)
    suggestions: list[str] = []
    stripped = unicodedata.normalize("NFKD", cleaned).encode("ASCII", "ignore").decode("ASCII")
    if stripped and stripped != cleaned:
        suggestions.append(stripped)
    hyphenless = re.sub(r"[-‐‑‒–—]+", " ", cleaned).strip()
    if hyphenless and hyphenless != cleaned:
        suggestions.append(f'"{hyphenless}"')
        words = [word for word in re.split(r"\s+", hyphenless) if word]
        if len(words) > 2:
            suggestions.append(" AND ".join(words))
    return json.dumps(list(dict.fromkeys(suggestions))[:4], ensure_ascii=False)


def ethics_gate(row: dict[str, Any]) -> str:
    if int(row.get("involves_indigenous_knowledge") or 0):
        return (
            "public_metadata_or_public_page_only; exclude restricted, secret/sacred, "
            "community-controlled, unpublished, or non-public material"
        )
    return "public_published_only; verify Australia scope and humanoid relevance"


def location_hint_for(config: dict[str, Any], row: dict[str, Any]) -> tuple[str, str, str]:
    figure = row.get("canonical_name") or row.get("figure")
    hint = config.get("location_hints", {}).get(figure or "")
    if hint:
        return (hint.get("state", ""), hint.get("region", ""), hint.get("precision", ""))
    if row.get("tier") == "tier_1_core" or int(row.get("involves_indigenous_knowledge") or 0):
        return ("AU", "", "Australia scope only; source must provide place or region")
    return ("", "", "location evidence must come from source")


def existing_record_summaries(conn) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT
            f.canonical_name,
            COUNT(r.record_id) AS record_count,
            MIN(r.year) AS earliest_year,
            MAX(r.year) AS latest_year,
            MAX(r.updated_at) AS last_updated
        FROM figures f
        LEFT JOIN records r ON r.figure_id = f.figure_id
        GROUP BY f.figure_id, f.canonical_name
        """
    ).fetchall()
    summaries: dict[str, str] = {}
    for row in rows:
        count = int(row["record_count"] or 0)
        if not count:
            summaries[row["canonical_name"]] = "existing_records=0"
            continue
        years = ""
        if row["earliest_year"] or row["latest_year"]:
            years = f"; years={row['earliest_year'] or '?'}-{row['latest_year'] or '?'}"
        updated = f"; last_updated={row['last_updated']}" if row["last_updated"] else ""
        summaries[row["canonical_name"]] = f"existing_records={count}{years}{updated}"
    return summaries


def compute_priority(lead: LeadRow) -> int:
    score = 3
    tier = str(lead.get("tier", ""))
    noise = str(lead.get("expected_noise_level", "")).lower()
    if "tier_1" in tier:
        score += 1
    if lead.get("include_status") == "include_v1":
        score += 1
    if noise == "low":
        score += 1
    elif noise == "high":
        score -= 1
    elif noise == "extreme":
        score -= 2
    if "validation" in str(lead.get("collection_action", "")):
        score -= 1
    if lead.get("high_noise_guard") in BLOCKING_HIGH_NOISE_GUARDS:
        score = 1
    elif lead.get("high_noise_guard") != "ok":
        score -= 1
    if lead.get("source_publicness_guard") != "ok_public_source":
        score = 1
    return max(1, min(5, score))


def enrich_lead(config: dict[str, Any], lead: LeadRow, record_summaries: dict[str, str]) -> LeadRow:
    health_status, health_checked = source_health(config, lead["source_type"])
    lead["source_health_status"] = health_status
    lead["last_source_health_check"] = health_checked
    lead["api_request_template"] = api_request_template(
        config,
        lead["source_type"],
        lead["query_string"],
        lead.get("date_start"),
        lead.get("date_end"),
    )
    lead["estimated_hits"] = estimate_hits(
        lead["query_string"],
        lead.get("expected_noise_level"),
        lead.get("query_type", ""),
        lead.get("high_noise_guard", "ok"),
    )
    lead["alternative_query_suggestions"] = alternative_query_suggestions(lead["query_string"])
    lead["existing_records_summary"] = record_summaries.get(lead.get("figure", ""), "existing_records=unknown")
    lead["ethics_review_passed"] = ""
    lead["ethics_reviewed_by"] = ""
    lead["ethics_reviewed_date"] = ""
    lead["related_lead_ids"] = []
    lead["execution_priority"] = compute_priority(lead)
    return lead


def sources_by_type(conn) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT source_id, source_name, source_type, base_url, publicness_level
        FROM sources
        ORDER BY source_type, source_name, source_id
        """
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_type"]].append(dict(row))
    duplicates = {source_type: rows for source_type, rows in grouped.items() if len(rows) > 1}
    for source_type, rows_for_type in sorted(duplicates.items()):
        names = ", ".join(row["source_name"] for row in rows_for_type)
        LOGGER.warning("Multiple sources share source_type=%s: %s", source_type, names)
    return dict(grouped)


def append_note(note: str | None, extra: str) -> str:
    if note:
        return f"{note} | {extra}"
    return extra


def build_lead_id(*parts: str, max_alias_length: int = 24) -> str:
    cleaned = []
    for index, part in enumerate(parts):
        value = slugify(normalise_alias(part)) if part else "none"
        if index == 3:
            value = value[:max_alias_length]
        cleaned.append(value)
    return ":".join(cleaned)


def planned_query_leads(
    conn,
    config: dict[str, Any],
    policy: dict[str, set[str]],
    record_summaries: dict[str, str],
) -> list[LeadRow]:
    public_source_types = tuple(config["public_source_types"])
    include_statuses = tuple(config.get("planned_include_statuses", ["include_v1", "control_only"]))
    rows = conn.execute(
        """
        SELECT
            q.query_id, q.query_string, q.query_type, q.date_start, q.date_end,
            q.expected_noise_level, q.notes,
            s.source_name, s.source_type, s.base_url, s.publicness_level,
            f.canonical_name, f.include_status, f.tier,
            f.involves_indigenous_knowledge
        FROM queries q
        JOIN sources s ON s.source_id = q.source_id
        LEFT JOIN figures f ON f.figure_id = q.figure_id
        WHERE q.status = 'planned'
          AND s.source_type IN (%s)
          AND (f.include_status IS NULL OR f.include_status IN (%s))
        ORDER BY s.source_type, q.date_start, q.query_id
        """
        % (
            ",".join("?" for _ in public_source_types),
            ",".join("?" for _ in include_statuses),
        ),
        public_source_types + include_statuses,
    ).fetchall()
    leads: list[LeadRow] = []
    round_id = config["round_id"]
    for row in rows:
        row_dict = dict(row)
        query = row["query_string"]
        band_name = date_band_name(config, row["date_start"], row["date_end"])
        if not source_enabled_for_band(config, row["source_type"], band_name):
            continue
        state_hint, region_hint, precision = location_hint_for(config, row_dict)
        high_noise_guard = high_noise_guard_for_query(query, policy)
        publicness_guard = source_publicness_guard(config, row["publicness_level"])
        notes = row["notes"] or ""
        if publicness_guard != "ok_public_source":
            notes = append_note(notes, "WARNING: source is not marked as public; filtered unless --keep-blocked is used.")
        leads.append(
            enrich_lead(
                config,
                {
                "round_id": round_id,
                "lead_id": f"{round_id}:query:{row['query_id']}",
                "collection_action": "planned_public_query",
                "source_name": row["source_name"],
                "source_type": row["source_type"],
                "source_publicness_level": row["publicness_level"],
                "source_publicness_guard": publicness_guard,
                "figure": row["canonical_name"] or "",
                "include_status": row["include_status"] or "",
                "tier": row["tier"] or "",
                "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                "query_id": row["query_id"],
                "query_string": query,
                "query_type": row["query_type"],
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "date_band": band_name,
                "expected_noise_level": row["expected_noise_level"],
                "manual_search_url": manual_search_url(
                    config, row["source_type"], row["base_url"], query, row["date_start"], row["date_end"]
                ),
                "high_noise_guard": high_noise_guard,
                "location_state_hint": state_hint,
                "location_region_hint": region_hint,
                "location_precision_target": precision,
                "ethics_gate": ethics_gate(row_dict),
                "notes": notes,
                },
                record_summaries,
            )
        )
    return leads


def validation_queue_leads(
    conn,
    config: dict[str, Any],
    policy: dict[str, set[str]],
    record_summaries: dict[str, str],
) -> list[LeadRow]:
    sources = sources_by_type(conn)
    rows = conn.execute(
        """
        SELECT
            f.canonical_name, f.include_status, f.tier,
            f.involves_indigenous_knowledge, a.alias
        FROM figures f
        JOIN aliases a ON a.figure_id = f.figure_id
        WHERE f.include_status = 'validate_before_include'
        ORDER BY f.canonical_name, a.search_priority DESC, a.alias
        """
    ).fetchall()
    leads: list[LeadRow] = []
    round_id = config["round_id"]
    for row in rows:
        row_dict = dict(row)
        query = f'"{row["alias"]}"'
        state_hint, region_hint, precision = location_hint_for(config, row_dict)
        for band in config["historical_bands"]:
            band_name = band["band_name"]
            for source_type in config["validation_source_types"]:
                if not source_enabled_for_band(config, source_type, band_name):
                    continue
                for source in sources.get(source_type, []):
                    publicness_guard = source_publicness_guard(config, source.get("publicness_level"))
                    lead_id = build_lead_id(
                        round_id,
                        "validation",
                        row["canonical_name"],
                        row["alias"],
                        source_type,
                        band_name,
                    )
                    high_noise_guard = high_noise_guard_for_query(query, policy)
                    notes = (
                        "Validation queue lead only. Do not ingest as include_v1 unless "
                        "manually promoted after public-source and ethics review."
                    )
                    if publicness_guard != "ok_public_source":
                        notes = append_note(notes, "WARNING: source is not marked as public; filtered unless --keep-blocked is used.")
                    leads.append(
                        enrich_lead(
                            config,
                            {
                            "round_id": round_id,
                            "lead_id": lead_id,
                            "collection_action": "validation_queue_only",
                            "source_name": source["source_name"],
                            "source_type": source["source_type"],
                            "source_publicness_level": source["publicness_level"],
                            "source_publicness_guard": publicness_guard,
                            "figure": row["canonical_name"],
                            "include_status": row["include_status"],
                            "tier": row["tier"],
                            "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                            "query_id": "",
                            "query_string": query,
                            "query_type": "validation_exact_phrase",
                            "date_start": str(band["date_start"]),
                            "date_end": str(band["date_end"]),
                            "date_band": band_name,
                            "expected_noise_level": "high",
                            "manual_search_url": manual_search_url(
                                config,
                                source["source_type"],
                                source["base_url"],
                                query,
                                str(band["date_start"]),
                                str(band["date_end"]),
                            ),
                            "high_noise_guard": high_noise_guard,
                            "location_state_hint": state_hint,
                            "location_region_hint": region_hint,
                            "location_precision_target": precision,
                            "ethics_gate": ethics_gate(row_dict),
                            "notes": notes,
                            },
                            record_summaries,
                        )
                    )
    return leads


def has_uncertain_locations(location_rows: list[dict[str, Any]]) -> bool:
    if not location_rows:
        return True
    statuses = {row["verification_status"] or "" for row in location_rows}
    types = {row["location_type"] or "" for row in location_rows}
    uncertain_statuses = {"needs_review", "broad_region_only", "verified_country_scope"}
    uncertain_types = {"broad_region", "state_or_territory", "country", "locality_or_article_title"}
    return bool(statuses & uncertain_statuses or types & uncertain_types)


def location_precision(location_rows: list[dict[str, Any]]) -> str:
    statuses = {row["verification_status"] or "" for row in location_rows}
    types = {row["location_type"] or "" for row in location_rows}
    if not location_rows:
        return "unknown"
    if "needs_review" in statuses:
        return "needs_review"
    if "town" in types or "locality" in types:
        best = "verified_place"
    elif "state_or_territory" in types:
        best = "verified_region"
    elif "broad_region" in types:
        best = "broad_region"
    else:
        best = "country_or_unclear"
    if has_uncertain_locations(location_rows) and best not in {"needs_review", "unknown", "country_or_unclear"}:
        return f"mixed_{best}"
    return best


def location_review_rows(conn, round_id: str) -> list[LocationRow]:
    records = conn.execute(
        """
        SELECT r.record_id, r.year, r.title, r.url, s.source_name,
               f.canonical_name AS figure
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN figures f ON f.figure_id = r.figure_id
        ORDER BY COALESCE(r.year, 9999), r.record_id
        """
    ).fetchall()
    output: list[LocationRow] = []
    for record in records:
        locations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT l.place_name, l.region, l.state_territory, l.location_type,
                       l.verification_status, rl.evidence_text, rl.confidence, rl.notes
                FROM record_locations rl
                JOIN locations l ON l.location_id = rl.location_id
                WHERE rl.record_id = ?
                ORDER BY l.location_type, l.place_name
                """,
                (record["record_id"],),
            ).fetchall()
        ]
        places = sorted(
            row["place_name"]
            for row in locations
            if row["location_type"] in {"town", "locality", "locality_or_article_title"}
        )
        states = sorted({row["state_territory"] for row in locations if row["state_territory"]})
        broad_regions = sorted(
            {
                row["region"] or row["place_name"]
                for row in locations
                if row["location_type"] in {"broad_region", "state_or_territory", "country"}
            }
        )
        evidence = " | ".join(
            sorted(
                {
                    f"{row['place_name']}: {row['evidence_text']}"
                    for row in locations
                    if row.get("evidence_text")
                }
            )
        )
        locations_json = json.dumps(
            [
                {
                    "place_name": row["place_name"],
                    "region": row["region"],
                    "state_territory": row["state_territory"],
                    "location_type": row["location_type"],
                    "verification_status": row["verification_status"],
                    "evidence_text": row["evidence_text"],
                    "confidence": row["confidence"],
                    "notes": row["notes"],
                }
                for row in locations
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        precision = location_precision(locations)
        uncertain = has_uncertain_locations(locations)
        output.append(
            {
                "round_id": round_id,
                "record_id": record["record_id"],
                "year": record["year"],
                "title": record["title"],
                "source_name": record["source_name"],
                "figure": record["figure"] or "",
                "url": record["url"] or "",
                "verified_places": "; ".join(places),
                "state_territories": "; ".join(states),
                "broad_regions": "; ".join(broad_regions),
                "location_precision": precision,
                "has_uncertain_locations": "yes" if uncertain else "no",
                "locations_json": locations_json,
                "location_evidence": evidence,
                "needs_location_review": "yes"
                if uncertain or precision.startswith("mixed_") or precision in {"unknown", "needs_review", "country_or_unclear"}
                else "no",
                "notes": "Human review should confirm whether place is setting, publication place, sighting location, or broad discourse region.",
            }
        )
    return output


def blocked_rows(leads: list[LeadRow]) -> list[LeadRow]:
    return [
        row
        for row in leads
        if row["high_noise_guard"] in BLOCKING_HIGH_NOISE_GUARDS
        or row["source_publicness_guard"] != "ok_public_source"
    ]


def duplicate_lead_ids(leads: list[LeadRow]) -> dict[str, int]:
    counts = Counter(row["lead_id"] for row in leads)
    return {lead_id: count for lead_id, count in counts.items() if count > 1}


def deduplicate_leads(leads: list[LeadRow]) -> tuple[list[LeadRow], int]:
    seen: dict[tuple[str, str, str, str], LeadRow] = {}
    dropped = 0
    for lead in leads:
        key = (
            lead["query_string"],
            lead["source_type"],
            str(lead.get("date_start") or ""),
            str(lead.get("date_end") or ""),
        )
        if key in seen:
            seen[key]["related_lead_ids"].append(lead["lead_id"])
            dropped += 1
            continue
        lead["related_lead_ids"] = []
        seen[key] = lead
    for lead in seen.values():
        related = lead.get("related_lead_ids") or []
        lead["related_lead_ids"] = json.dumps(related, ensure_ascii=False)
    return list(seen.values()), dropped


def missing_figure_report(conn, leads: list[LeadRow]) -> list[MissingFigureRow]:
    planned_figures = {row["figure"] for row in leads if row.get("figure")}
    rows = conn.execute(
        """
        SELECT canonical_name, include_status, tier
        FROM figures
        WHERE include_status NOT LIKE 'exclude%'
        ORDER BY tier, canonical_name
        """
    ).fetchall()
    return [
        {
            "canonical_name": row["canonical_name"],
            "include_status": row["include_status"],
            "tier": row["tier"],
        }
        for row in rows
        if row["canonical_name"] not in planned_figures
    ]


def validate_rows(rows: list[dict[str, Any]], schema: dict[str, tuple[type, ...]], label: str) -> None:
    for index, row in enumerate(rows, start=1):
        for field, expected_types in schema.items():
            value = row.get(field)
            if value == "":
                continue
            if value is not None and not isinstance(value, expected_types):
                raise TypeError(
                    f"{label} row {index} field {field}: expected {expected_types}, got {type(value)}"
                )


def apply_sampling(leads: list[LeadRow], limit: int | None, sample: float | None, seed: int) -> list[LeadRow]:
    selected = list(leads)
    if sample is not None:
        if sample <= 0 or sample > 1:
            raise ValueError("--sample must be greater than 0 and less than or equal to 1")
        if sample < 1:
            rng = random.Random(seed)
            sample_size = max(1, round(len(selected) * sample))
            selected = rng.sample(selected, sample_size)
    if limit is not None:
        if limit < 0:
            raise ValueError("--limit must be zero or greater")
        selected = selected[:limit]
    return selected


def apply_output_suffix(args: argparse.Namespace) -> None:
    suffix = args.output_suffix
    if not suffix:
        return
    for attr in ["leads_output", "location_output", "report", "metadata_output", "manifest_output"]:
        path = Path(getattr(args, attr))
        setattr(args, attr, str(path.with_name(f"{path.stem}_{suffix}{path.suffix}")))


def git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def build_metadata(
    config: dict[str, Any],
    args: argparse.Namespace,
    all_leads: list[LeadRow],
    written_leads: list[LeadRow],
    locations: list[LocationRow],
    blocked: list[LeadRow],
    dedupe_dropped: int,
) -> dict[str, Any]:
    return {
        "script": str(Path(__file__).relative_to(PROJECT_ROOT)),
        "round_id": config["round_id"],
        "generated_at": utc_now_iso(),
        "git_commit": git_commit(),
        "arguments": vars(args),
        "db_path": str(Path(args.db).resolve()),
        "config_path": str(Path(args.config).resolve()),
        "noise_rules_path": str(Path(args.noise_rules).resolve()),
        "counts": {
            "candidate_leads": len(all_leads),
            "written_leads": len(written_leads),
            "blocked_leads": len(blocked),
            "deduplicated_leads": dedupe_dropped,
            "location_review_rows": len(locations),
        },
    }


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(path: Path, output_paths: list[Path]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for output_path in output_paths:
        if output_path.exists():
            rows.append(
                {
                    "path": str(output_path.resolve()),
                    "sha256": sha256_file(output_path),
                    "bytes": output_path.stat().st_size,
                }
            )
    path.write_text(json.dumps({"files": rows}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_report(
    path: Path,
    config: dict[str, Any],
    all_leads: list[LeadRow],
    written_leads: list[LeadRow],
    locations: list[LocationRow],
    blocked: list[LeadRow],
    duplicate_ids: dict[str, int],
    missing_figures: list[MissingFigureRow],
    dedupe_dropped: int,
    args: argparse.Namespace,
) -> None:
    by_action = Counter(row["collection_action"] for row in written_leads)
    by_source = Counter(row["source_type"] for row in written_leads)
    by_band = Counter(row["date_band"] for row in written_leads)
    by_priority = Counter(row["execution_priority"] for row in written_leads)
    by_review_guard = Counter(row["high_noise_guard"] for row in written_leads if row["high_noise_guard"] != "ok")
    location_needs_review = sum(1 for row in locations if row["needs_location_review"] == "yes")
    blocked_by_guard = Counter(
        "publicness" if row["source_publicness_guard"] != "ok_public_source" else "high_noise"
        for row in blocked
    )

    lines = [
        "# Public Collection Round 002 Plan",
        "",
        f"Run id: `{config['round_id']}`",
        f"Created at: `{utc_now_iso()}`",
        "Mode: plan only; no network requests; no records inserted.",
        "",
        "## Execution Context",
        "",
        f"- Script: `{Path(__file__).relative_to(PROJECT_ROOT)}`",
        f"- Config: `{Path(args.config).resolve()}`",
        f"- Noise rules: `{Path(args.noise_rules).resolve()}`",
        f"- DB path: `{Path(args.db).resolve()}`",
        f"- Leads output: `{Path(args.leads_output).resolve()}`",
        f"- Location output: `{Path(args.location_output).resolve()}`",
        f"- Report output: `{Path(args.report).resolve()}`",
        f"- Validation queue included: `{not args.without_validation_queue}`",
        f"- Keep blocked rows: `{args.keep_blocked}`",
        f"- Limit: `{args.limit}`",
        f"- Sample: `{args.sample}`",
        f"- Output suffix: `{args.output_suffix or ''}`",
        "",
        "## Purpose",
        "",
        "Prepare a broader but still conservative public-source collection round before live fetching starts.",
        "The plan prioritises earlier source discovery, public metadata review, and explicit location-evidence tracking.",
        "",
        "## Safety Gates",
        "",
        "- Australia-only scope.",
        "- Public, published, openly discoverable sources only.",
        "- No restricted, secret/sacred, unpublished, community-controlled, or non-public materials.",
        "- Public catalogue metadata is treated as a lead, not permission to extract restricted cultural knowledge.",
        "- Validation-queue terms are written as validation leads only and are not promoted to `include_v1`.",
        "- High-noise bare queries and non-public source rows are blocked by the plan validator.",
        "",
        "## Lead Counts",
        "",
        f"- Candidate lead rows before filtering: {len(all_leads)}",
        f"- Written lead rows: {len(written_leads)}",
        f"- Filtered or blocked rows: {len(blocked)}",
        f"- Duplicate query/source/date rows merged: {dedupe_dropped}",
        f"- Duplicate lead IDs detected: {len(duplicate_ids)}",
    ]
    for key, count in sorted(blocked_by_guard.items()):
        lines.append(f"- Blocked by `{key}`: {count}")

    for label, counter in [
        ("By action", by_action),
        ("By source type", by_source),
        ("By date band", by_band),
        ("By execution priority", by_priority),
    ]:
        lines.extend(["", f"### {label}", ""])
        for key, count in sorted(counter.items()):
            lines.append(f"- `{key}`: {count}")

    lines.extend(["", "### Non-Blocking Review Guards", ""])
    if by_review_guard:
        for key, count in sorted(by_review_guard.items()):
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- None")

    lines.extend(["", "## Blocked Row Sample", ""])
    if blocked:
        for row in blocked[:25]:
            lines.append(
                f"- `{row['lead_id']}` | guard={row['high_noise_guard']}/{row['source_publicness_guard']} | "
                f"source={row['source_type']} | query={row['query_string']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Figures Without Planned Queries", ""])
    if missing_figures:
        for row in missing_figures[:50]:
            lines.append(f"- `{row['canonical_name']}` | tier={row['tier']} | status={row['include_status']}")
    else:
        lines.append("- None")

    lines.extend(["", "## Duplicate Lead IDs", ""])
    if duplicate_ids:
        for lead_id, count in sorted(duplicate_ids.items())[:25]:
            lines.append(f"- `{lead_id}`: {count}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Location Review",
            "",
            f"- Records in location queue: {len(locations)}",
            f"- Records needing location review: {location_needs_review}",
            "",
            "Location fields are evidence fields, not final geocoding truth. The `locations_json` column preserves per-place evidence, confidence, type, and notes for review.",
            "",
            "## Outputs",
            "",
            f"- `{Path(args.leads_output).resolve()}`",
            f"- `{Path(args.location_output).resolve()}`",
            f"- `{Path(args.metadata_output).resolve()}`",
            f"- `{Path(args.manifest_output).resolve()}`",
            "",
            "## Next Live-Collection Step",
            "",
            "After reviewing this plan, implement source-specific collectors one at a time. Start with manual Trove/NLA metadata verification, then add API-backed retrieval only where credentials, publicness, and rate limits are clear.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Round configuration YAML path")
    parser.add_argument("--noise-rules", default=str(DEFAULT_NOISE_RULES_PATH), help="Noise rules YAML path")
    parser.add_argument("--leads-output", default=str(DEFAULT_LEADS_PATH), help="Lead-plan CSV output path")
    parser.add_argument(
        "--location-output",
        default=str(DEFAULT_LOCATION_REVIEW_PATH),
        help="Location-review CSV output path",
    )
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Markdown report output path")
    parser.add_argument("--metadata-output", default=str(DEFAULT_METADATA_PATH), help="Run metadata JSON output path")
    parser.add_argument("--manifest-output", default=str(DEFAULT_MANIFEST_PATH), help="SHA256 manifest JSON output path")
    parser.add_argument(
        "--without-validation-queue",
        action="store_true",
        help="Omit validation-queue-only leads from the plan",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Exit non-zero before writing files if blocked rows are generated",
    )
    parser.add_argument(
        "--keep-blocked",
        action="store_true",
        help="Write blocked rows for audit instead of filtering them from lead CSV output",
    )
    parser.add_argument("--only-planned-queries", action="store_true", help="Generate only planned query leads")
    parser.add_argument("--only-validation", action="store_true", help="Generate only validation-queue leads")
    parser.add_argument("--only-locations", action="store_true", help="Generate only the location-review queue")
    parser.add_argument("--limit", type=int, help="Maximum number of lead rows to write after filtering")
    parser.add_argument("--sample", type=float, help="Fraction of lead rows to sample after filtering, from 0 to 1")
    parser.add_argument("--sample-seed", type=int, default=42, help="Deterministic seed for --sample")
    parser.add_argument("--output-suffix", help="Append a suffix to output filenames for versioned plans")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    setup_logging(args.verbose)
    apply_output_suffix(args)

    only_flags = [args.only_planned_queries, args.only_validation, args.only_locations]
    if sum(1 for flag in only_flags if flag) > 1:
        LOGGER.error("Use only one of --only-planned-queries, --only-validation, or --only-locations.")
        raise SystemExit(1)

    db_path = Path(args.db)
    if not db_path.exists():
        LOGGER.error("Database not found: %s. Run `make init seed queries` first.", db_path)
        raise SystemExit(1)

    config = load_round_config(args.config)
    policy = bare_query_policy(config, Path(args.noise_rules))
    try:
        with connect(db_path) as conn:
            record_summaries = existing_record_summaries(conn)
            leads: list[LeadRow] = []
            if not args.only_locations:
                if not args.only_validation:
                    leads.extend(planned_query_leads(conn, config, policy, record_summaries))
                if not args.without_validation_queue and not args.only_planned_queries:
                    leads.extend(validation_queue_leads(conn, config, policy, record_summaries))
            locations = location_review_rows(conn, config["round_id"]) if not args.only_planned_queries and not args.only_validation else []
            missing_figures = missing_figure_report(conn, leads)
    except sqlite3.OperationalError:
        LOGGER.exception("Database error while generating round 002 plan")
        raise SystemExit(1)

    blocked = blocked_rows(leads)
    duplicate_ids = duplicate_lead_ids(leads)
    if duplicate_ids:
        LOGGER.warning("Detected %d duplicate lead_id value(s)", len(duplicate_ids))
    if blocked:
        LOGGER.warning("Generated %d blocked row(s)", len(blocked))
    if args.fail_on_blocked and blocked:
        LOGGER.error("Blocked rows found; exiting without writing output files.")
        raise SystemExit(1)

    lead_candidates = leads if args.keep_blocked else [row for row in leads if row not in blocked]
    deduped_leads, dedupe_dropped = deduplicate_leads(lead_candidates)
    leads_to_write = apply_sampling(deduped_leads, args.limit, args.sample, args.sample_seed)

    validate_rows(leads_to_write, LEAD_FIELD_SCHEMA, "lead")
    validate_rows(locations, LOCATION_FIELD_SCHEMA, "location")
    Path(args.leads_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.location_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metadata_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.manifest_output).parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.leads_output, leads_to_write, LEAD_FIELDS)
    write_csv(args.location_output, locations, LOCATION_FIELDS)
    write_report(
        Path(args.report),
        config,
        leads,
        leads_to_write,
        locations,
        blocked,
        duplicate_ids,
        missing_figures,
        dedupe_dropped,
        args,
    )
    metadata = build_metadata(config, args, leads, leads_to_write, locations, blocked, dedupe_dropped)
    write_metadata(Path(args.metadata_output), metadata)
    write_manifest(
        Path(args.manifest_output),
        [
            Path(args.leads_output),
            Path(args.location_output),
            Path(args.report),
            Path(args.metadata_output),
        ],
    )

    LOGGER.info("Wrote round 002 lead plan: %s", args.leads_output)
    LOGGER.info("Wrote round 002 location review: %s", args.location_output)
    LOGGER.info("Wrote round 002 report: %s", args.report)
    LOGGER.info("Wrote round 002 metadata: %s", args.metadata_output)
    LOGGER.info("Wrote round 002 manifest: %s", args.manifest_output)


if __name__ == "__main__":
    main()
