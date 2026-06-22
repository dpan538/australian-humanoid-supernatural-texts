#!/usr/bin/env python3
"""Export a static JSON data contract for the Next.js frontend."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect, table_names
from aus_humanoid.geo import location_summary
from aus_humanoid.utils import PROJECT_ROOT


FRONTEND_DATA_PATH = PROJECT_ROOT / "public" / "data" / "frontend-data.json"

DATE_BANDS = [
    {
        "id": "backsearch_1803_1841",
        "label": "1803-1841",
        "start": 1803,
        "end": 1841,
        "role": "retrospective Trove backsearch / negative-control field",
    },
    {
        "id": "anchor_1842_1875",
        "label": "1842-1875",
        "start": 1842,
        "end": 1875,
        "role": "early semantic anchor period",
    },
    {
        "id": "expansion_1876_1969",
        "label": "1876-1969",
        "start": 1876,
        "end": 1969,
        "role": "pre-modern newspaper and publication expansion",
    },
    {
        "id": "modern_1970_1990",
        "label": "1970-1990",
        "start": 1970,
        "end": 1990,
        "role": "early modern witness, heritage, tourism, and media period",
    },
    {
        "id": "modern_1991_2010",
        "label": "1991-2010",
        "start": 1991,
        "end": 2010,
        "role": "late modern web, media, and public retelling period",
    },
    {
        "id": "contemporary_2011_present",
        "label": "2011-present",
        "start": 2011,
        "end": None,
        "role": "contemporary public web and platform circulation period",
    },
]

ATTENTION_DATE_WINDOWS = [
    {
        "id": "google_trends_2004_present",
        "label": "2004-present",
        "start": 2004,
        "end": None,
        "role": "Google Trends relative interest window",
    },
    {
        "id": "wikimedia_2015_present",
        "label": "2015-present",
        "start": 2015,
        "end": None,
        "role": "Wikimedia pageviews attention window",
    },
]

STATE_CODES = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"]
STATE_NAME_TO_CODE = {
    "western australia": "WA",
    "northern territory": "NT",
    "south australia": "SA",
    "queensland": "QLD",
    "new south wales": "NSW",
    "victoria": "VIC",
    "tasmania": "TAS",
    "australian capital territory": "ACT",
}
SITE_NAME_TO_CODE = {
    "mitchell river national park": "VIC",
    "den of nargun": "VIC",
    "port arthur": "TAS",
    "port arthur historic site": "TAS",
    "princess theatre": "VIC",
}
PUBLIC_MAP_LOCATION_ROLES = {
    "alleged_event_location",
    "apparition_location",
    "narrative_setting",
    "legend_associated_place",
    "rumour_circulation_place",
    "reported_place",
    "source_visible_place",
    "source_visible_place_hint",
    "mentioned_place",
}
PUBLIC_MAP_LOCATION_TYPES = {
    "exact_site",
    "road_segment",
    "named_feature",
    "town",
    "locality",
    "precise_point",
}
PUBLIC_MAP_VERIFICATION_STATUSES = {
    "verified_place",
    "verified_locality",
    "verified_gazetteer_point",
    "verified_institutional_coordinate",
}
PUBLIC_MAP_REJECTED_ROLES = {"publication_location", "source_collection_location"}
PUBLIC_MAP_TYPE_PRIORITY = {
    "exact_site": 0,
    "precise_point": 1,
    "road_segment": 2,
    "named_feature": 3,
    "locality": 4,
    "town": 5,
}

def row_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def year_to_band(year: int | None) -> str:
    if year is None:
        return "undated"
    for band in DATE_BANDS:
        end = band["end"] if band["end"] is not None else 9999
        if int(band["start"]) <= year <= int(end):
            return str(band["id"])
    return "outside_scope"


def query_band(date_start: str | None, date_end: str | None) -> str:
    start = str(date_start or "")
    end = str(date_end or "")
    for band in [*DATE_BANDS, *ATTENTION_DATE_WINDOWS]:
        if start == str(band["start"]) and (end == str(band["end"]) or (band["end"] is None and end == "present")):
            return str(band["id"])
    return f"{start}-{end}".strip("-") or "unspecified"


def year_from_date_text(value: str | None) -> int | None:
    if not value:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def query_overlaps_band(query: dict[str, Any], band: dict[str, Any]) -> bool:
    start = year_from_date_text(query.get("date_start"))
    end = year_from_date_text(query.get("date_end"))
    if str(query.get("date_end") or "").lower() == "present":
        end = 9999
    if start is None:
        return False
    if end is None:
        end = start
    band_start = int(band["start"])
    band_end = int(band["end"]) if band["end"] is not None else 9999
    return start <= band_end and end >= band_start


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def state_code_from_text(text: str | None) -> str | None:
    normalized = (text or "").lower()
    for site_name, code in SITE_NAME_TO_CODE.items():
        if site_name in normalized:
            return code
    for state_name, code in STATE_NAME_TO_CODE.items():
        if state_name in normalized:
            return code
    for code in STATE_CODES:
        if f" {code.lower()} " in f" {normalized} ":
            return code
    return None


def is_public_map_location(location: dict[str, Any]) -> bool:
    role = str(location.get("relation_type") or "")
    location_type = str(location.get("location_type") or "")
    verification = str(location.get("verification_status") or "")
    state = location.get("state_territory")
    country = str(location.get("country") or "Australia").lower()
    if role in PUBLIC_MAP_REJECTED_ROLES or role not in PUBLIC_MAP_LOCATION_ROLES:
        return False
    if location_type not in PUBLIC_MAP_LOCATION_TYPES:
        return False
    if verification not in PUBLIC_MAP_VERIFICATION_STATUSES:
        return False
    if location.get("latitude") is None or location.get("longitude") is None:
        return False
    if country != "australia" or state not in STATE_CODES:
        return False
    if not str(location.get("evidence_text") or "").strip():
        return False
    return True


def map_location_priority(location: dict[str, Any]) -> tuple[int, str]:
    return (
        PUBLIC_MAP_TYPE_PRIORITY.get(str(location.get("location_type") or ""), 99),
        str(location.get("place_name") or ""),
    )


def export_frontend_data(db_path: str | Path = DEFAULT_DB_PATH, output_path: Path = FRONTEND_DATA_PATH) -> Path:
    with connect(db_path) as conn:
        tables = table_names(conn)

        records_rows = conn.execute(
            """
            SELECT
                r.record_id, r.source_id, r.query_id, r.figure_id, r.external_id,
                r.title, r.publication, r.author, r.date_published, r.year,
                r.url, r.snippet, r.publicness_level, r.ingestion_status,
                s.source_name, s.source_type,
                f.canonical_name AS canonical_figure,
                f.cluster, f.tier, f.include_status,
                f.humanoid_degree AS figure_humanoid_degree,
                f.ontology_default, f.involves_indigenous_knowledge,
                c.canonical_figure_guess, c.figure_name_as_printed,
                c.ontology_code, c.humanoid_degree_code, c.source_voice,
                c.genre, c.publicness_code, c.relevance_code, c.ethics_flag,
                c.notes AS coding_notes
            FROM records r
            JOIN sources s ON s.source_id = r.source_id
            LEFT JOIN figures f ON f.figure_id = r.figure_id
            LEFT JOIN coding c ON c.record_id = r.record_id
            WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
              AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
              AND COALESCE(c.relevance_code, '') != 'scope_excluded'
            ORDER BY COALESCE(r.year, 9999), r.record_id
            """
        ).fetchall()

        records: list[dict[str, Any]] = []
        for row in records_rows:
            item = row_dict(row)
            item["year"] = safe_int(item.get("year"))
            item["date_band"] = year_to_band(item["year"])
            item["location_summary"] = location_summary(conn, int(item["record_id"])) if "record_locations" in tables else ""
            item["state_territory"] = None
            item["location_precision_status"] = "unmapped"
            item["has_strict_map_point"] = False
            item["map_latitude"] = None
            item["map_longitude"] = None
            item["map_place_name"] = None
            item["map_location_role"] = None
            item["map_location_type"] = None
            item["map_geocode_source"] = None
            item["map_verification_status"] = None
            item["map_confidence"] = None
            item["map_evidence_text"] = None
            records.append(item)

        locations: list[dict[str, Any]] = []
        if {"record_locations", "locations"}.issubset(tables):
            location_rows = conn.execute(
                """
                SELECT
                    rl.record_id, rl.relation_type, rl.evidence_text, rl.confidence, rl.notes,
                    l.place_name, l.region, l.state_territory, l.country,
                    l.latitude, l.longitude, l.location_type, l.geocode_source,
                    l.verification_status,
                    r.year, r.title,
                    COALESCE(c.canonical_figure_guess, f.canonical_name) AS canonical_figure
                FROM record_locations rl
                JOIN locations l ON l.location_id = rl.location_id
                JOIN records r ON r.record_id = rl.record_id
                LEFT JOIN figures f ON f.figure_id = r.figure_id
                LEFT JOIN coding c ON c.record_id = r.record_id
                WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
                  AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
                  AND COALESCE(c.relevance_code, '') != 'scope_excluded'
                ORDER BY COALESCE(r.year, 9999), rl.record_id, l.place_name
                """
            ).fetchall()
            for row in location_rows:
                item = row_dict(row)
                item["year"] = safe_int(item.get("year"))
                item["latitude"] = float(item["latitude"]) if item.get("latitude") not in (None, "") else None
                item["longitude"] = float(item["longitude"]) if item.get("longitude") not in (None, "") else None
                item["date_band"] = year_to_band(item["year"])
                locations.append(item)

        figure_rows = conn.execute(
            """
            SELECT
                f.figure_id, f.canonical_name, f.cluster, f.tier, f.include_status,
                f.humanoid_degree, f.ontology_default, f.involves_indigenous_knowledge,
                f.sensitivity_notes, f.description,
                a.alias_id, a.alias, a.alias_type, a.search_priority, a.notes AS alias_notes
            FROM figures f
            LEFT JOIN aliases a ON a.figure_id = f.figure_id
            ORDER BY f.cluster, f.canonical_name, a.search_priority DESC, a.alias
            """
        ).fetchall()

        figures_by_id: dict[int, dict[str, Any]] = {}
        for row in figure_rows:
            figure_id = int(row["figure_id"])
            if figure_id not in figures_by_id:
                figures_by_id[figure_id] = {
                    "figure_id": figure_id,
                    "canonical_name": row["canonical_name"],
                    "cluster": row["cluster"],
                    "tier": row["tier"],
                    "include_status": row["include_status"],
                    "humanoid_degree": row["humanoid_degree"],
                    "ontology_default": row["ontology_default"],
                    "involves_indigenous_knowledge": bool(row["involves_indigenous_knowledge"]),
                    "sensitivity_notes": row["sensitivity_notes"],
                    "description": row["description"],
                    "aliases": [],
                    "record_count": 0,
                    "earliest_year": None,
                    "latest_year": None,
                }
            if row["alias_id"] is not None:
                figures_by_id[figure_id]["aliases"].append(
                    {
                        "alias_id": row["alias_id"],
                        "alias": row["alias"],
                        "alias_type": row["alias_type"],
                        "search_priority": row["search_priority"],
                        "notes": row["alias_notes"],
                    }
                )

        for record in records:
            figure_id = record.get("figure_id")
            year = record.get("year")
            if figure_id in figures_by_id:
                figure = figures_by_id[figure_id]
                figure["record_count"] += 1
                if year is not None:
                    years = [existing for existing in (figure["earliest_year"], year) if existing is not None]
                    figure["earliest_year"] = min(years) if years else None
                    years = [existing for existing in (figure["latest_year"], year) if existing is not None]
                    figure["latest_year"] = max(years) if years else None

        query_rows = conn.execute(
            """
            SELECT
                q.query_id, q.figure_id, q.source_id, q.query_string, q.query_type,
                q.date_start, q.date_end, q.expected_noise_level, q.status, q.notes,
                s.source_name, s.source_type,
                f.canonical_name
            FROM queries q
            JOIN sources s ON s.source_id = q.source_id
            LEFT JOIN figures f ON f.figure_id = q.figure_id
            ORDER BY q.query_id
            """
        ).fetchall()
        queries = []
        for row in query_rows:
            item = row_dict(row)
            item["date_band"] = query_band(item.get("date_start"), item.get("date_end"))
            queries.append(item)

        source_rows = conn.execute(
            """
            SELECT source_id, source_name, source_type, base_url, access_method,
                   publicness_level, ethics_notes
            FROM sources
            ORDER BY source_type, source_name
            """
        ).fetchall()
        sources = [row_dict(row) for row in source_rows]

        attention_rows = conn.execute(
            """
            SELECT
                a.attention_id, a.figure_id, a.source_id, a.term, a.date,
                a.value, a.geo, a.metric_type, a.notes,
                f.canonical_name,
                s.source_name, s.source_type
            FROM attention_series a
            JOIN sources s ON s.source_id = a.source_id
            LEFT JOIN figures f ON f.figure_id = a.figure_id
            ORDER BY a.term, a.date
            """
        ).fetchall()
        attention = [row_dict(row) for row in attention_rows]

    record_band_counts = Counter(record["date_band"] for record in records)
    query_band_counts = Counter(query["date_band"] for query in queries)
    ontology_counts = Counter(record.get("ontology_code") or record.get("ontology_default") or "uncoded" for record in records)
    ethics_counts = Counter(record.get("ethics_flag") or "uncoded" for record in records)
    source_type_counts = Counter(record.get("source_type") or "unknown" for record in records)

    state_record_ids: dict[str, set[int]] = {code: set() for code in STATE_CODES}
    state_representative_records: dict[str, int] = {}
    first_location_by_record: dict[int, dict[str, Any]] = {}
    representative_map_location_by_record: dict[int, dict[str, Any]] = {}
    broad_locations = []
    records_by_id = {int(record["record_id"]): record for record in records}
    for location in locations:
        state = location.get("state_territory")
        record_id = int(location["record_id"])
        linked_record = records_by_id.get(record_id)
        if linked_record is None:
            continue
        location["source_name"] = linked_record.get("source_name")
        location["source_type"] = linked_record.get("source_type")
        location["publication"] = linked_record.get("publication")
        location["url"] = linked_record.get("url")
        location["ingestion_status"] = linked_record.get("ingestion_status")
        existing_location = first_location_by_record.get(record_id)
        if existing_location is None or (
            existing_location.get("state_territory") not in STATE_CODES and location.get("state_territory") in STATE_CODES
        ):
            first_location_by_record[record_id] = location
        if state in state_record_ids:
            state_record_ids[state].add(record_id)
            state_representative_records.setdefault(state, record_id)
        if is_public_map_location(location):
            existing = representative_map_location_by_record.get(record_id)
            if existing is None or map_location_priority(location) < map_location_priority(existing):
                representative_map_location_by_record[record_id] = location
        elif location.get("location_type") in {"broad_region", "state_or_territory", "country"}:
            broad_locations.append(location)

    # Frontend map policy: one explicit public flag per canonical record. All
    # location relationships stay exportable for audit/review, but public map
    # points are a derived subset selected from eligible representative rows.
    map_points = list(representative_map_location_by_record.values())
    mapped_record_ids = set(representative_map_location_by_record)
    for record_id, location in first_location_by_record.items():
        record = records_by_id.get(record_id)
        if not record:
            continue
        record["state_territory"] = location.get("state_territory")
        record["location_precision_status"] = location.get("location_type") or "mapped"
        record["has_strict_map_point"] = record_id in mapped_record_ids
        if record["has_strict_map_point"]:
            map_location = representative_map_location_by_record[record_id]
            record["state_territory"] = map_location.get("state_territory") or record.get("state_territory")
            record["location_precision_status"] = map_location.get("location_type") or record.get("location_precision_status")
            record["map_latitude"] = map_location.get("latitude")
            record["map_longitude"] = map_location.get("longitude")
            record["map_place_name"] = map_location.get("place_name")
            record["map_location_role"] = map_location.get("relation_type")
            record["map_location_type"] = map_location.get("location_type")
            record["map_geocode_source"] = map_location.get("geocode_source")
            record["map_verification_status"] = map_location.get("verification_status")
            record["map_confidence"] = map_location.get("confidence")
            record["map_evidence_text"] = map_location.get("evidence_text")

    corpus_state_record_ids: dict[str, set[int]] = {code: set() for code in STATE_CODES}
    unmapped_record_count = 0
    for record in records:
        state = record.get("state_territory")
        if state in corpus_state_record_ids:
            corpus_state_record_ids[state].add(int(record["record_id"]))
        else:
            unmapped_record_count += 1

    map_clusters = [
        {
            "cluster_id": f"state:{code}",
            "cluster_type": "state_or_territory_aggregate",
            "state_territory": code,
            "label": code,
            "record_count": len(record_ids),
            "representative_record_id": state_representative_records.get(code),
            "location_role": "uncertain_or_broad_location",
            "location_precision": "state_or_territory",
            "display_note": "Aggregated state/territory signal for records without precise public coordinates.",
        }
        for code, record_ids in state_record_ids.items()
        if record_ids
    ]

    # State-level or broad locations remain reviewable location data, but are not rendered as points.
    # Keep map_flags in lockstep with map_points so every displayed point remains auditable.
    map_flags: list[dict[str, Any]] = [
        {
            "flag_id": f"mapped:{point['record_id']}",
            "record_id": point["record_id"],
            "state_territory": point.get("state_territory"),
            "x": point.get("longitude"),
            "y": point.get("latitude"),
            "stem_dx": 0,
            "stem_dy": 0,
            "display_precision": "precise_point",
            "source_location_type": point.get("location_type"),
            "confidence": point.get("confidence"),
            "title": point.get("title"),
            "year": point.get("year"),
            "canonical_figure": point.get("canonical_figure"),
        }
        for point in map_points
    ]

    records_by_figure = Counter((record.get("canonical_figure_guess") or record.get("canonical_figure") or "uncoded") for record in records)
    records_by_year = Counter(str(record["year"]) for record in records if record.get("year") is not None)

    date_band_summaries = []
    for band in DATE_BANDS:
        planned_query_count = sum(1 for query in queries if query_overlaps_band(query, band))
        date_band_summaries.append(
            {
                **band,
                "record_count": int(record_band_counts.get(str(band["id"]), 0)),
                "planned_query_count": int(planned_query_count),
            }
        )
    if record_band_counts.get("undated"):
        date_band_summaries.append(
            {
                "id": "undated",
                "label": "Undated",
                "start": None,
                "end": None,
                "role": "public records with no defensible publication or event year in the source metadata",
                "record_count": int(record_band_counts.get("undated", 0)),
                "planned_query_count": 0,
            }
        )

    years = [record["year"] for record in records if record.get("year") is not None]
    source_rollup: dict[str, dict[str, Any]] = defaultdict(lambda: {"record_count": 0, "query_count": 0})
    for record in records:
        source_rollup[record.get("source_type") or "unknown"]["record_count"] += 1
    for query in queries:
        source_rollup[query.get("source_type") or "unknown"]["query_count"] += 1

    data = {
        "schema_version": "frontend-data/v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "scope": {
            "country": "Australia",
            "public_only": True,
            "visual_mode": "archive_terminal",
            "ethical_note": "Public metadata and public pages are display signals, not permission to extract restricted cultural knowledge.",
        },
        "summary": {
            "record_count": len(records),
            "figure_count": len(figures_by_id),
            "query_count": len(queries),
            "source_count": len(sources),
            "location_count": len(locations),
            "mapped_record_count": len(mapped_record_ids),
            "broad_location_count": len(broad_locations),
            "map_cluster_count": len(map_clusters),
            "map_flag_count": len(map_flags),
            "earliest_year": min(years) if years else None,
            "latest_year": max(years) if years else None,
            "state_record_counts": {code: len(ids) for code, ids in state_record_ids.items()},
            "corpus_state_counts": {code: len(ids) for code, ids in corpus_state_record_ids.items()},
            "mapped_state_counts": {code: sum(1 for point in map_points if point.get("state_territory") == code) for code in STATE_CODES},
            "unmapped_record_count": unmapped_record_count,
            "records_by_figure": dict(records_by_figure),
            "records_by_year": dict(sorted(records_by_year.items())),
            "ontology_counts": dict(ontology_counts),
            "ethics_counts": dict(ethics_counts),
            "source_type_counts": dict(source_type_counts),
            "source_rollup": dict(source_rollup),
        },
        "date_bands": date_band_summaries,
        "records": records,
        "locations": locations,
        "map_points": map_points,
        "map_flags": map_flags,
        "map_clusters": map_clusters,
        "broad_locations": broad_locations,
        "figures": list(figures_by_id.values()),
        "queries": queries,
        "sources": sources,
        "attention_series": attention,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--output", default=str(FRONTEND_DATA_PATH), help="JSON output path")
    args = parser.parse_args()

    path = export_frontend_data(args.db, Path(args.output))
    print(f"Wrote frontend data to: {path}")


if __name__ == "__main__":
    main()
