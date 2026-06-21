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
        "id": "modern_1970_present",
        "label": "1970-present",
        "start": 1970,
        "end": None,
        "role": "modern Yowie / heritage / tourism / media period",
    },
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

def row_dict(row: Any) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def year_to_band(year: int | None) -> str:
    if year is None:
        return "undated"
    for band in DATE_BANDS[:4]:
        end = band["end"] if band["end"] is not None else 9999
        if int(band["start"]) <= year <= int(end):
            return str(band["id"])
    return "outside_scope"


def query_band(date_start: str | None, date_end: str | None) -> str:
    start = str(date_start or "")
    end = str(date_end or "")
    for band in DATE_BANDS:
        if start == str(band["start"]) and (end == str(band["end"]) or (band["end"] is None and end == "present")):
            return str(band["id"])
    return f"{start}-{end}".strip("-") or "unspecified"


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def state_code_from_text(text: str | None) -> str | None:
    normalized = (text or "").lower()
    for state_name, code in STATE_NAME_TO_CODE.items():
        if state_name in normalized:
            return code
    for code in STATE_CODES:
        if f" {code.lower()} " in f" {normalized} ":
            return code
    return None


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

        accepted_candidate_rows = []
        if "collection_candidates_v2" in tables:
            accepted_candidate_rows = conn.execute(
                """
                SELECT *
                FROM collection_candidates_v2
                WHERE candidate_status = 'accepted'
                  AND COALESCE(publicness_status, '') != 'restricted_excluded'
                ORDER BY candidate_id
                """
            ).fetchall()
            for row in accepted_candidate_rows:
                candidate = row_dict(row)
                candidate_id = int(candidate["candidate_id"])
                record_id = 900000000 + candidate_id
                year = safe_int(str(candidate.get("publication_date_text") or "")[:4])
                state_code = state_code_from_text(candidate.get("location_text"))
                latitude = float(candidate["latitude"]) if candidate.get("latitude") not in (None, "") else None
                longitude = float(candidate["longitude"]) if candidate.get("longitude") not in (None, "") else None
                has_strict_point = latitude is not None and longitude is not None
                record = {
                    "record_id": record_id,
                    "source_id": 0,
                    "query_id": None,
                    "figure_id": None,
                    "external_id": candidate.get("external_id"),
                    "title": candidate.get("title"),
                    "publication": candidate.get("publication_or_organisation"),
                    "author": None,
                    "date_published": candidate.get("publication_date_text"),
                    "year": year,
                    "url": candidate.get("url"),
                    "snippet": candidate.get("evidence_summary"),
                    "publicness_level": candidate.get("publicness_status"),
                    "ingestion_status": "v2_accepted_candidate" if not has_strict_point else "strict_geo_candidate",
                    "source_name": candidate.get("source_name"),
                    "source_type": candidate.get("source_type"),
                    "canonical_figure": candidate.get("source_label"),
                    "cluster": "strict_geo_collection",
                    "tier": candidate.get("source_tier"),
                    "include_status": "include_v2_candidate",
                    "figure_humanoid_degree": candidate.get("humanoid_basis"),
                    "ontology_default": candidate.get("narrative_type"),
                    "involves_indigenous_knowledge": candidate.get("ethics_review_status") == "caution_indigenous_knowledge",
                    "canonical_figure_guess": candidate.get("source_label"),
                    "figure_name_as_printed": candidate.get("source_label"),
                    "ontology_code": candidate.get("narrative_type"),
                    "humanoid_degree_code": candidate.get("humanoid_basis"),
                    "source_voice": candidate.get("secondary_role"),
                    "genre": candidate.get("source_type"),
                    "publicness_code": candidate.get("publicness_status"),
                    "relevance_code": "relevant",
                    "ethics_flag": candidate.get("ethics_review_status"),
                    "coding_notes": f"V2 accepted candidate {candidate_id}; map point {'verified' if has_strict_point else 'pending strict geocode'}; quality {candidate.get('quality_class') or 'ungraded'}.",
                    "date_band": year_to_band(year),
                    "location_summary": candidate.get("location_text") or "",
                    "state_territory": state_code,
                    "location_precision_status": candidate.get("location_precision") or ("precise_point" if has_strict_point else "unmapped"),
                    "has_strict_map_point": has_strict_point,
                }
                records.append(record)
                if has_strict_point:
                    location = {
                        "record_id": record_id,
                        "relation_type": candidate.get("location_role"),
                        "evidence_text": candidate.get("coordinate_evidence_note") or candidate.get("evidence_summary"),
                        "confidence": candidate.get("quality_class"),
                        "notes": "Accepted V2 strict-geography candidate.",
                        "place_name": candidate.get("location_text") or candidate.get("title") or "Strict geocoded candidate",
                        "region": None,
                        "state_territory": state_code,
                        "country": "Australia",
                        "latitude": latitude,
                        "longitude": longitude,
                        "location_type": candidate.get("location_precision"),
                        "geocode_source": candidate.get("geocode_source"),
                        "verification_status": candidate.get("geocode_verification_status"),
                        "year": year,
                        "title": candidate.get("title"),
                        "canonical_figure": candidate.get("source_label"),
                        "date_band": year_to_band(year),
                    }
                    locations.append(location)

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
    precise_points = []
    broad_locations = []
    records_by_id = {int(record["record_id"]): record for record in records}
    for location in locations:
        state = location.get("state_territory")
        record_id = int(location["record_id"])
        linked_record = records_by_id.get(record_id, {})
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
        if location.get("latitude") is not None and location.get("longitude") is not None:
            precise_points.append(location)
        elif location.get("location_type") in {"broad_region", "state_or_territory", "country"}:
            broad_locations.append(location)

    precise_record_ids = {int(point["record_id"]) for point in precise_points}
    for record_id, location in first_location_by_record.items():
        record = records_by_id.get(record_id)
        if not record:
            continue
        record["state_territory"] = location.get("state_territory")
        record["location_precision_status"] = location.get("location_type") or "mapped"
        record["has_strict_map_point"] = record_id in precise_record_ids

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

    # Strict map policy: only verified records with public latitude/longitude become map flags.
    # State-level or broad locations remain reviewable location data, but are not rendered as points.
    # Keep map_flags in lockstep with map_points so every displayed strict point remains auditable.
    map_flags: list[dict[str, Any]] = [
        {
            "flag_id": f"strict:{point['record_id']}:{index}",
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
        for index, point in enumerate(precise_points)
    ]

    records_by_figure = Counter((record.get("canonical_figure_guess") or record.get("canonical_figure") or "uncoded") for record in records)
    records_by_year = Counter(str(record["year"]) for record in records if record.get("year") is not None)

    date_band_summaries = []
    for band in DATE_BANDS:
        date_band_summaries.append(
            {
                **band,
                "record_count": int(record_band_counts.get(str(band["id"]), 0)),
                "planned_query_count": int(query_band_counts.get(str(band["id"]), 0)),
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
            "precise_point_count": len(precise_points),
            "map_point_count": len(precise_points),
            "broad_location_count": len(broad_locations),
            "map_cluster_count": len(map_clusters),
            "map_flag_count": len(precise_points),
            "earliest_year": min(years) if years else None,
            "latest_year": max(years) if years else None,
            "state_record_counts": {code: len(ids) for code, ids in state_record_ids.items()},
            "corpus_state_counts": {code: len(ids) for code, ids in corpus_state_record_ids.items()},
            "strict_state_counts": {code: sum(1 for point in precise_points if point.get("state_territory") == code) for code in STATE_CODES},
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
        "map_points": precise_points,
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
