#!/usr/bin/env python3
"""Build a local-only post-1926 gap projection frontend-data overlay.

This script does not ingest records into SQLite and does not overwrite
public/data/frontend-data.json. It creates explicitly labelled experimental
records so the Next.js app can be run locally against a larger projected corpus.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_INTERIM_OUTPUT = (
    ROOT / "data" / "interim" / "gap_probe_1926_2011" / "frontend-data.experimental-4000.json"
)
DEFAULT_PUBLIC_OUTPUT = ROOT / "public" / "data" / "frontend-data.experimental-4000.json"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_gap_localhost_overlay.md"

QUERY_FAMILIES = [
    {
        "id": "yowie_yahoo_named",
        "label": "Yowie / Yahoo named forms",
        "weight": 0.34,
        "figure": "Yowie",
        "printed": "Yowie",
        "ontology": "cryptid_style_apeman",
        "humanoid": "humanoid",
        "voice": "public_search_projection",
        "genre": "metadata_probe_projection",
        "ethics": "public_metadata_projection_review_required",
    },
    {
        "id": "hairy_humanoid_descriptors",
        "label": "Hairy humanoid descriptors",
        "weight": 0.19,
        "figure": "hairy man",
        "printed": "hairy man",
        "ontology": "cryptid_style_apeman",
        "humanoid": "humanoid",
        "voice": "public_search_projection",
        "genre": "metadata_probe_projection",
        "ethics": "public_metadata_projection_review_required",
    },
    {
        "id": "tracks_sightings_and_headlines",
        "label": "Tracks / sightings / headline language",
        "weight": 0.13,
        "figure": "reported_ghost_or_apparition",
        "printed": "sighting",
        "ontology": "rumour_account",
        "humanoid": "humanoid_adjacent",
        "voice": "public_search_projection",
        "genre": "metadata_probe_projection",
        "ethics": "public_metadata_projection_review_required",
    },
    {
        "id": "apparition_ghost_public_places",
        "label": "Ghost / apparition public-place records",
        "weight": 0.20,
        "figure": "ghost",
        "printed": "ghost",
        "ontology": "apparition_account",
        "humanoid": "humanoid",
        "voice": "public_search_projection",
        "genre": "metadata_probe_projection",
        "ethics": "public_metadata_projection_review_required",
    },
    {
        "id": "local_legend_source_voice",
        "label": "Local legend source-voice forms",
        "weight": 0.09,
        "figure": "local ghost stories",
        "printed": "local legend",
        "ontology": "local_legend",
        "humanoid": "humanoid_adjacent",
        "voice": "source_voice_projection",
        "genre": "metadata_probe_projection",
        "ethics": "public_local_history_projection_review_required",
    },
    {
        "id": "public_indigenous_named_figures",
        "label": "Public named figure records requiring sensitivity review",
        "weight": 0.05,
        "figure": "spirit-person",
        "printed": "public named figure",
        "ontology": "spirit_person_narrative",
        "humanoid": "humanoid",
        "voice": "public_source_representation_projection",
        "genre": "metadata_probe_projection",
        "ethics": "needs_human_ethics_review",
        "involves_indigenous_knowledge": True,
        "map_eligible_projection": False,
    },
]

SOURCE_FAMILIES = [
    {
        "id": "trove_newspaper_metadata",
        "label": "Trove newspaper and gazette metadata projection",
        "weight": 0.45,
        "access": "official_api_or_manual_export_projection",
    },
    {
        "id": "trove_magazine_metadata",
        "label": "Trove magazine and newsletter metadata projection",
        "weight": 0.10,
        "access": "official_api_or_manual_export_projection",
    },
    {
        "id": "archived_newspaper_metadata",
        "label": "Archived newspaper metadata projection",
        "weight": 0.12,
        "access": "public_metadata_projection",
    },
    {
        "id": "state_library_catalogue_metadata",
        "label": "State library / archive catalogue projection",
        "weight": 0.12,
        "access": "public_catalogue_projection",
    },
    {
        "id": "local_history_public_page",
        "label": "Local history public-page projection",
        "weight": 0.10,
        "access": "public_web_projection",
    },
    {
        "id": "public_indexed_book_metadata",
        "label": "Public indexed book metadata projection",
        "weight": 0.06,
        "access": "public_catalogue_or_public_domain_projection",
    },
    {
        "id": "museum_archive_catalogue_metadata",
        "label": "Museum / archive catalogue metadata projection",
        "weight": 0.05,
        "access": "public_catalogue_projection",
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def weighted_cycle(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    weights = [float(item["weight"]) for item in items]
    total = sum(weights)
    raw = [(weight / total) * count for weight in weights]
    floors = [math.floor(value) for value in raw]
    remainder = count - sum(floors)
    order = sorted(range(len(items)), key=lambda index: raw[index] - floors[index], reverse=True)
    for index in order[:remainder]:
        floors[index] += 1

    output: list[dict[str, Any]] = []
    for item, item_count in zip(items, floors, strict=True):
        output.extend([item] * item_count)
    return sorted(output, key=lambda item: item["id"])


def year_weight(year: int) -> int:
    if 1926 <= year <= 1929:
        return 35
    if 1930 <= year <= 1949:
        return 65
    if 1950 <= year <= 1969:
        return 60
    if 1970 <= year <= 1989:
        return 45
    return 35


def allocate_years(start_year: int, end_year: int, count: int) -> list[int]:
    years = list(range(start_year, end_year + 1))
    weights = [year_weight(year) for year in years]
    total = sum(weights)
    raw = [(weight / total) * count for weight in weights]
    floors = [math.floor(value) for value in raw]
    remainder = count - sum(floors)
    order = sorted(range(len(years)), key=lambda index: raw[index] - floors[index], reverse=True)
    for index in order[:remainder]:
        floors[index] += 1

    output: list[int] = []
    for year, year_count in zip(years, floors, strict=True):
        output.extend([year] * year_count)
    return output


def date_band_for_year(data: dict[str, Any], year: int) -> str:
    for band in data.get("date_bands", []):
        start = band.get("start")
        end = band.get("end")
        if start is None:
            continue
        if year >= int(start) and (end is None or year <= int(end)):
            return str(band["id"])
    return "unknown"


def max_int(rows: list[dict[str, Any]], key: str, fallback: int) -> int:
    values = [row.get(key) for row in rows if isinstance(row.get(key), int)]
    return max(values, default=fallback)


def figure_id_lookup(data: dict[str, Any]) -> dict[str, int]:
    lookup: dict[str, int] = {}
    for figure in data.get("figures", []):
        name = figure.get("canonical_name")
        figure_id = figure.get("figure_id")
        if isinstance(name, str) and isinstance(figure_id, int):
            lookup[name.lower()] = figure_id
    return lookup


def source_rows(data: dict[str, Any], start_source_id: int) -> dict[str, int]:
    source_ids: dict[str, int] = {}
    for index, source in enumerate(SOURCE_FAMILIES):
        source_id = start_source_id + index
        source_ids[source["id"]] = source_id
        data.setdefault("sources", []).append(
            {
                "source_id": source_id,
                "source_name": source["label"],
                "source_type": source["id"],
                "base_url": None,
                "access_method": source["access"],
                "publicness_level": "experimental_projection_not_a_source_record",
                "ethics_notes": (
                    "Localhost-only gap projection. This is not a public source item, "
                    "not a verified claim, and not eligible for production import."
                ),
            }
        )
    return source_ids


def query_rows(data: dict[str, Any], source_ids: dict[str, int], start_query_id: int) -> dict[tuple[str, str], int]:
    figures = figure_id_lookup(data)
    query_ids: dict[tuple[str, str], int] = {}
    query_id = start_query_id
    for source in SOURCE_FAMILIES:
        for family in QUERY_FAMILIES:
            query_ids[(source["id"], family["id"])] = query_id
            data.setdefault("queries", []).append(
                {
                    "query_id": query_id,
                    "figure_id": figures.get(str(family["figure"]).lower()),
                    "source_id": source_ids[source["id"]],
                    "query_string": f"experimental_projection::{family['id']}::{source['id']}",
                    "query_type": "localhost_gap_projection",
                    "date_start": "1926",
                    "date_end": "2011",
                    "expected_noise_level": "unknown_until_live_probe",
                    "status": "simulated_not_requested",
                    "notes": "Projection query row for localhost testing; not a live crawl result.",
                    "source_name": source["label"],
                    "source_type": source["id"],
                    "canonical_name": family["figure"],
                    "date_band": "post_1926_gap_window",
                }
            )
            query_id += 1
    return query_ids


def state_distribution(data: dict[str, Any]) -> list[str]:
    counts = data.get("summary", {}).get("corpus_state_counts") or data.get("summary", {}).get("state_record_counts") or {}
    states = [state for state in ("NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT") if counts.get(state)]
    if not states:
        states = ["NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT"]
        counts = {state: 1 for state in states}
    total = sum(int(counts[state]) for state in states)
    output: list[str] = []
    for state in states:
        quota = max(1, round((int(counts[state]) / total) * 4000))
        output.extend([state] * quota)
    return output


def map_anchors(data: dict[str, Any]) -> dict[str, tuple[float, float]]:
    anchors: dict[str, tuple[float, float]] = {}
    flags = data.get("map_flags", [])
    for state in ("NSW", "QLD", "VIC", "WA", "SA", "TAS", "NT", "ACT"):
        rows = [flag for flag in flags if flag.get("state_territory") == state]
        if not rows:
            continue
        anchors[state] = (
            float(statistics.median(float(row["x"]) for row in rows if row.get("x") is not None)),
            float(statistics.median(float(row["y"]) for row in rows if row.get("y") is not None)),
        )
    anchors.setdefault("NSW", (150.88, -33.49))
    anchors.setdefault("QLD", (152.85, -27.24))
    anchors.setdefault("VIC", (144.97, -37.81))
    anchors.setdefault("WA", (115.86, -31.96))
    anchors.setdefault("SA", (138.58, -34.92))
    anchors.setdefault("TAS", (147.33, -42.88))
    anchors.setdefault("NT", (131.14, -14.06))
    anchors.setdefault("ACT", (149.10, -35.30))
    return anchors


def jitter(anchor: tuple[float, float], index: int) -> tuple[float, float]:
    angle = (index * 137.507764) % 360
    radius = 0.04 + ((index % 17) * 0.018)
    radians = math.radians(angle)
    return (round(anchor[0] + math.cos(radians) * radius, 6), round(anchor[1] + math.sin(radians) * radius, 6))


def build_records(
    data: dict[str, Any],
    count: int,
    start_year: int,
    end_year: int,
    source_ids: dict[str, int],
    query_ids: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    start_record_id = max(9_260_000, max_int(data.get("records", []), "record_id", 0) + 1)
    years = allocate_years(start_year, end_year, count)
    families = weighted_cycle(QUERY_FAMILIES, count)
    sources = weighted_cycle(SOURCE_FAMILIES, count)
    states = state_distribution(data)

    records: list[dict[str, Any]] = []
    for index in range(count):
        year = years[index]
        family = families[(index * 7) % len(families)]
        source = sources[(index * 11) % len(sources)]
        state = states[(index * 13) % len(states)]
        record_id = start_record_id + index
        involves_indigenous = bool(family.get("involves_indigenous_knowledge", False))
        records.append(
            {
                "record_id": record_id,
                "source_id": source_ids[source["id"]],
                "query_id": query_ids[(source["id"], family["id"])],
                "figure_id": None,
                "external_id": f"experimental-gap-{record_id}",
                "title": f"Experimental gap projection: {family['label']} ({year})",
                "publication": source["label"],
                "author": None,
                "date_published": str(year),
                "year": year,
                "url": None,
                "snippet": (
                    "Localhost-only projection row for post-1926 gap testing. "
                    "This is not a source record, not a verified claim, and not production data."
                ),
                "publicness_level": "experimental_projection_not_a_public_record",
                "ingestion_status": "simulated_not_ingested",
                "source_name": source["label"],
                "source_type": source["id"],
                "canonical_figure": family["figure"],
                "cluster": "experimental_gap_projection",
                "tier": "simulation",
                "include_status": "experimental_localhost_only",
                "figure_humanoid_degree": family["humanoid"],
                "ontology_default": family["ontology"],
                "involves_indigenous_knowledge": involves_indigenous,
                "canonical_figure_guess": family["figure"],
                "figure_name_as_printed": family["printed"],
                "ontology_code": family["ontology"],
                "humanoid_degree_code": family["humanoid"],
                "source_voice": family["voice"],
                "genre": family["genre"],
                "publicness_code": "experimental_projection",
                "relevance_code": "needs_review_projection",
                "ethics_flag": family["ethics"],
                "coding_notes": (
                    "Experimental 4000-record post-1926 gap overlay. "
                    "Review live public source evidence before any candidate import."
                ),
                "date_band": date_band_for_year(data, year),
                "location_summary": f"Experimental {state} projection only; no place evidence.",
                "state_territory": state,
                "location_precision_status": "experimental_projection_only",
                "has_strict_map_point": False,
                "map_latitude": None,
                "map_longitude": None,
                "map_place_name": None,
                "map_location_role": "projection_not_record_location",
                "map_location_type": "state_projection",
                "map_geocode_source": "experimental_overlay",
                "map_verification_status": "simulation_only",
                "map_confidence": "simulation_only",
                "map_evidence_text": "No record-level map evidence; local projection only.",
            }
        )
    return records


def add_simulated_map_flags(data: dict[str, Any], records: list[dict[str, Any]], target_total_mapped: int) -> int:
    current_mapped = len({flag["record_id"] for flag in data.get("map_flags", []) if isinstance(flag.get("record_id"), int)})
    needed = max(0, target_total_mapped - current_mapped)
    eligible = [
        record
        for record in records
        if not record.get("involves_indigenous_knowledge") and record.get("state_territory")
    ]
    selected = eligible[: min(needed, len(eligible))]
    anchors = map_anchors(data)

    for index, record in enumerate(selected, start=1):
        state = str(record["state_territory"])
        lon, lat = jitter(anchors[state], index)
        record["map_longitude"] = lon
        record["map_latitude"] = lat
        record["map_place_name"] = f"{state} experimental projection"
        data.setdefault("map_flags", []).append(
            {
                "flag_id": f"exp-gap-{record['record_id']}",
                "record_id": record["record_id"],
                "state_territory": state,
                "x": lon,
                "y": lat,
                "stem_dx": round(((index % 9) - 4) * 0.18, 3),
                "stem_dy": round((((index // 9) % 9) - 4) * 0.18, 3),
                "display_precision": "experimental_state_projection",
                "source_location_type": "projection_not_record_location",
                "confidence": "simulation_only",
                "title": record["title"],
                "year": record["year"],
                "canonical_figure": record["canonical_figure"],
            }
        )
    return len(selected)


def count_by(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for record in records:
        value = record.get(key)
        if value not in (None, ""):
            counter[str(value)] += 1
    return dict(counter)


def recompute_summary(data: dict[str, Any]) -> None:
    records = data.get("records", [])
    flags = data.get("map_flags", [])
    mapped_ids = {flag.get("record_id") for flag in flags if isinstance(flag.get("record_id"), int)}
    years = [int(record["year"]) for record in records if isinstance(record.get("year"), int)]

    summary = data.setdefault("summary", {})
    summary["record_count"] = len(records)
    summary["source_count"] = len(data.get("sources", []))
    summary["query_count"] = len(data.get("queries", []))
    summary["mapped_record_count"] = len(mapped_ids)
    summary["map_flag_count"] = len(flags)
    summary["dated_record_count"] = len(years)
    summary["undated_record_count"] = len(records) - len(years)
    summary["unmapped_record_count"] = max(0, len(records) - len(mapped_ids))
    summary["earliest_year"] = min(years) if years else None
    summary["latest_year"] = max(years) if years else None
    summary["state_record_counts"] = count_by(records, "state_territory")
    summary["corpus_state_counts"] = count_by(records, "state_territory")
    summary["mapped_state_counts"] = count_by(flags, "state_territory")
    summary["records_by_figure"] = count_by(records, "canonical_figure_guess")
    summary["records_by_year"] = count_by(records, "year")
    summary["ontology_counts"] = count_by(records, "ontology_code")
    summary["ethics_counts"] = count_by(records, "ethics_flag")
    summary["source_type_counts"] = count_by(records, "source_type")

    source_rollup: dict[str, dict[str, int]] = {}
    query_counts = Counter(str(query.get("source_type")) for query in data.get("queries", []) if query.get("source_type"))
    for source_type, record_count in summary["source_type_counts"].items():
        source_rollup[source_type] = {"record_count": record_count, "query_count": query_counts.get(source_type, 0)}
    for source_type, query_count in query_counts.items():
        source_rollup.setdefault(source_type, {"record_count": 0, "query_count": query_count})
    summary["source_rollup"] = source_rollup

    record_band_counts = Counter(record.get("date_band") for record in records)
    mapped_record_lookup = {record["record_id"]: record for record in records if isinstance(record.get("record_id"), int)}
    mapped_band_counts = Counter(
        mapped_record_lookup[flag["record_id"]].get("date_band")
        for flag in flags
        if flag.get("record_id") in mapped_record_lookup
    )
    for band in data.get("date_bands", []):
        band_id = band.get("id")
        band["record_count"] = int(record_band_counts.get(band_id, 0))
        band["mapped_count"] = int(mapped_band_counts.get(band_id, 0))
        band["mapped_share"] = round((band["mapped_count"] / band["record_count"]) * 100, 1) if band["record_count"] else 0


def write_report(
    path: Path,
    data: dict[str, Any],
    added_records: int,
    added_mapped: int,
    public_output: Path,
    interim_output: Path,
) -> None:
    summary = data["summary"]
    records_by_year = {int(year): count for year, count in summary["records_by_year"].items() if str(year).isdigit()}
    sparse_1930_1969 = sum(records_by_year.get(year, 0) for year in range(1930, 1970))
    lines = [
        "# 1926-2011 Localhost Gap Overlay",
        "",
        "This file documents a local-only experimental overlay. It is not a crawl result, not a reviewed record import, and not production frontend data.",
        "",
        "## Outputs",
        "",
        f"- Public localhost file: `{public_output.relative_to(ROOT)}`",
        f"- Interim audit file: `{interim_output.relative_to(ROOT)}`",
        "- Default production file remains: `public/data/frontend-data.json`",
        "",
        "## Projection Counts",
        "",
        f"- Added projected records: {added_records:,}",
        f"- Added simulated mapped flags: {added_mapped:,}",
        f"- Experimental public records total: {summary['record_count']:,}",
        f"- Experimental mapped records total: {summary['mapped_record_count']:,}",
        f"- Experimental 1930-1969 public records after overlay: {sparse_1930_1969:,}",
        "",
        "## Safety Labels",
        "",
        "- `ingestion_status`: `simulated_not_ingested`",
        "- `publicness_code`: `experimental_projection`",
        "- `relevance_code`: `needs_review_projection`",
        "- simulated map flags use `confidence: simulation_only` and `display_precision: experimental_state_projection`",
        "",
        "## Localhost Use",
        "",
        "Run the app with:",
        "",
        "```bash",
        "NEXT_PUBLIC_FRONTEND_DATA_URL=/data/frontend-data.experimental-4000.json npm run dev",
        "```",
        "",
        "The default app still reads `/data/frontend-data.json` when the environment variable is absent.",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--interim-output", default=str(DEFAULT_INTERIM_OUTPUT))
    parser.add_argument("--public-output", default=str(DEFAULT_PUBLIC_OUTPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--target-additional-records", type=int, default=4000)
    parser.add_argument("--target-total-mapped", type=int, default=2500)
    parser.add_argument("--start-year", type=int, default=1926)
    parser.add_argument("--end-year", type=int, default=2011)
    parser.add_argument("--include-simulated-map-flags", action="store_true")
    args = parser.parse_args()

    source_data = load_json(Path(args.input))
    data = copy.deepcopy(source_data)
    data["schema_version"] = f"{data.get('schema_version', 'frontend-data/v1')}+experimental-gap-overlay"
    data["generated_at"] = utc_now_iso()
    data.setdefault("scope", {})["visual_mode"] = "localhost_experimental_gap_projection"
    data.setdefault("scope", {})["ethical_note"] = (
        data.get("scope", {}).get("ethical_note", "")
        + " Experimental overlay rows are simulation-only and not reviewed public records."
    ).strip()

    source_ids = source_rows(data, max_int(data.get("sources", []), "source_id", 0) + 1)
    query_ids = query_rows(data, source_ids, max_int(data.get("queries", []), "query_id", 0) + 1)
    records = build_records(
        data,
        args.target_additional_records,
        args.start_year,
        args.end_year,
        source_ids,
        query_ids,
    )
    data.setdefault("records", []).extend(records)
    added_mapped = 0
    if args.include_simulated_map_flags:
        added_mapped = add_simulated_map_flags(data, records, args.target_total_mapped)

    recompute_summary(data)

    interim_output = Path(args.interim_output)
    public_output = Path(args.public_output)
    write_json(interim_output, data)
    write_json(public_output, data)
    write_report(Path(args.report), data, len(records), added_mapped, public_output, interim_output)

    print(f"Wrote experimental interim data: {interim_output}")
    print(f"Wrote experimental public localhost data: {public_output}")
    print(f"Wrote report: {args.report}")
    print(f"Added projected records: {len(records)}")
    print(f"Added simulated mapped flags: {added_mapped}")
    print(f"Experimental totals: records={data['summary']['record_count']} mapped={data['summary']['mapped_record_count']}")


if __name__ == "__main__":
    main()
