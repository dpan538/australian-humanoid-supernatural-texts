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

STATE_FLAG_FIELDS = {
    "WA": (168, 394, 326, 488, 18),
    "NT": (428, 552, 218, 338, 13),
    "SA": (438, 578, 378, 456, 12),
    "QLD": (610, 766, 258, 454, 16),
    "NSW": (650, 766, 454, 522, 22),
    "VIC": (610, 704, 542, 586, 13),
    "TAS": (696, 738, 642, 676, 7),
    "ACT": (762, 792, 492, 522, 5),
    "UNMAPPED": (828, 908, 220, 286, 8),
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


def display_flag_position(state: str, index: int, total: int) -> tuple[float, float, float, float]:
    x0, x1, y0, y1, columns = STATE_FLAG_FIELDS.get(state, STATE_FLAG_FIELDS["UNMAPPED"])
    rows = max(1, (total + columns - 1) // columns)
    col = index % columns
    row = index // columns
    x_step = (x1 - x0) / max(columns - 1, 1)
    y_step = (y1 - y0) / max(rows - 1, 1)
    # Tiny deterministic jitter keeps dense fields from looking mechanically sorted.
    jitter_x = ((index * 37) % 7 - 3) * 0.55
    jitter_y = ((index * 53) % 5 - 2) * 0.45
    x = x0 + col * x_step + jitter_x
    y = y0 + row * y_step + jitter_y
    stem_dx = 8 if (index + row) % 2 else -8
    stem_dy = -10 if index % 3 else 10
    return (round(x, 3), round(y, 3), stem_dx, stem_dy)
    try:
        return int(value)
    except (TypeError, ValueError):
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
    for location in locations:
        state = location.get("state_territory")
        record_id = int(location["record_id"])
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

    records_by_id = {int(record["record_id"]): record for record in records}
    record_ids_by_display_state: dict[str, list[int]] = {code: [] for code in [*STATE_CODES, "UNMAPPED"]}
    for record in records:
        record_id = int(record["record_id"])
        location = first_location_by_record.get(record_id)
        state = location.get("state_territory") if location else None
        display_state = state if state in STATE_CODES else "UNMAPPED"
        record_ids_by_display_state[display_state].append(record_id)

    map_flags: list[dict[str, Any]] = []
    for display_state, record_ids in record_ids_by_display_state.items():
        for index, record_id in enumerate(record_ids):
            record = records_by_id[record_id]
            location = first_location_by_record.get(record_id)
            x, y, stem_dx, stem_dy = display_flag_position(display_state, index, len(record_ids))
            if display_state == "UNMAPPED":
                display_precision = "no_public_location"
            elif location and location.get("latitude") is not None and location.get("longitude") is not None:
                display_precision = "precise_public_coordinate"
            else:
                display_precision = "state_or_broad_display_placement"
            map_flags.append(
                {
                    "flag_id": f"record:{record_id}",
                    "record_id": record_id,
                    "state_territory": display_state,
                    "x": x,
                    "y": y,
                    "stem_dx": stem_dx,
                    "stem_dy": stem_dy,
                    "display_precision": display_precision,
                    "source_location_type": location.get("location_type") if location else None,
                    "confidence": location.get("confidence") if location else None,
                    "title": record.get("title"),
                    "year": record.get("year"),
                    "canonical_figure": record.get("canonical_figure_guess")
                    or record.get("canonical_figure")
                    or record.get("figure_name_as_printed"),
                }
            )

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
            "broad_location_count": len(broad_locations),
            "map_cluster_count": len(map_clusters),
            "map_flag_count": len(map_flags),
            "earliest_year": min(years) if years else None,
            "latest_year": max(years) if years else None,
            "state_record_counts": {code: len(ids) for code, ids in state_record_ids.items()},
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
        "map_clusters": map_clusters,
        "map_flags": map_flags,
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
