#!/usr/bin/env python3
"""Build a localhost frontend-data overlay from real live-crawl candidates."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_CANDIDATES = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "live_crawl" / "public_metadata_live_candidates.csv"
DEFAULT_PUBLIC_OUTPUT = ROOT / "public" / "data" / "frontend-data.live-crawl.json"
DEFAULT_INTERIM_OUTPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "live_crawl" / "frontend-data.live-crawl.json"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_live_candidate_overlay.md"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def max_int(rows: list[dict[str, Any]], key: str, fallback: int) -> int:
    values = [row.get(key) for row in rows if isinstance(row.get(key), int)]
    return max(values, default=fallback)


def date_band_for_year(data: dict[str, Any], year: int) -> str:
    for band in data.get("date_bands", []):
        start = band.get("start")
        end = band.get("end")
        if start is None:
            continue
        if year >= int(start) and (end is None or year <= int(end)):
            return str(band["id"])
    return "unknown"


def load_candidates(paths: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows.extend(row for row in csv.DictReader(handle) if row.get("candidate_status") == "public_metadata_candidate")
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = row.get("external_id") or row.get("url") or f"{row.get('title')}:{row.get('year')}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def source_key(row: dict[str, str]) -> str:
    return f"live_crawl_{row.get('source_api') or 'metadata'}"


def ensure_sources(data: dict[str, Any], candidates: list[dict[str, str]]) -> dict[str, int]:
    existing = {source.get("source_type"): int(source["source_id"]) for source in data.get("sources", []) if isinstance(source.get("source_id"), int)}
    next_id = max_int(data.get("sources", []), "source_id", 0) + 1
    source_ids: dict[str, int] = {}
    for key in sorted({source_key(row) for row in candidates}):
        if key in existing:
            source_ids[key] = existing[key]
            continue
        label = "OpenAlex live public metadata" if key.endswith("openalex") else "Crossref live public metadata"
        source_ids[key] = next_id
        data.setdefault("sources", []).append(
            {
                "source_id": next_id,
                "source_name": label,
                "source_type": key,
                "base_url": "https://api.openalex.org/works" if key.endswith("openalex") else "https://api.crossref.org/works",
                "access_method": "public_metadata_api_live_crawl",
                "publicness_level": "public_metadata_candidate",
                "ethics_notes": "Live crawl candidate source. Metadata only; full text and cultural sensitivity require human review before production import.",
            }
        )
        next_id += 1
    return source_ids


def ensure_queries(data: dict[str, Any], candidates: list[dict[str, str]], source_ids: dict[str, int]) -> dict[tuple[str, str], int]:
    next_id = max_int(data.get("queries", []), "query_id", 0) + 1
    query_ids: dict[tuple[str, str], int] = {}
    pairs = sorted({(source_key(row), row["query_family_id"]) for row in candidates})
    labels = {row["query_family_id"]: row["query_family_label"] for row in candidates}
    strings = {row["query_family_id"]: row["query_string"] for row in candidates}
    for source_type, family_id in pairs:
        query_ids[(source_type, family_id)] = next_id
        data.setdefault("queries", []).append(
            {
                "query_id": next_id,
                "figure_id": None,
                "source_id": source_ids[source_type],
                "query_string": strings.get(family_id) or family_id,
                "query_type": "live_gap_public_metadata_crawl",
                "date_start": "1926",
                "date_end": "2011",
                "expected_noise_level": "measured_in_live_crawl",
                "status": "candidate_overlay_not_production",
                "notes": f"Live public metadata query family: {labels.get(family_id, family_id)}.",
                "source_name": next((source["source_name"] for source in data["sources"] if source["source_id"] == source_ids[source_type]), source_type),
                "source_type": source_type,
                "canonical_name": None,
                "date_band": "post_1926_gap_window",
            }
        )
        next_id += 1
    return query_ids


def canonical_figure(row: dict[str, str]) -> str:
    family = row.get("query_family_id") or ""
    matched = (row.get("figure_terms_matched") or "").split(";")
    if family.startswith("yowie"):
        return "Yowie"
    if family.startswith("hairy"):
        return "hairy man"
    if "ghost" in family or "apparition" in family:
        return "ghost"
    if family == "public_indigenous_named_figures":
        return matched[0] if matched and matched[0] else "public named figure"
    if "bunyip" in ";".join(matched):
        return "bunyip"
    return matched[0] if matched and matched[0] else "uncoded"


def overlay_records(
    data: dict[str, Any],
    candidates: list[dict[str, str]],
    source_ids: dict[str, int],
    query_ids: dict[tuple[str, str], int],
) -> list[dict[str, Any]]:
    start_record_id = max(9_280_000, max_int(data.get("records", []), "record_id", 0) + 1)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(candidates):
        year = int(row["year"])
        source_type = source_key(row)
        figure = canonical_figure(row)
        risk_flags = row.get("risk_flags") or ""
        indigenous_related = "indigenous_related" in risk_flags
        record = {
            "record_id": start_record_id + index,
            "source_id": source_ids[source_type],
            "query_id": query_ids[(source_type, row["query_family_id"])],
            "figure_id": None,
            "external_id": row.get("external_id") or f"live-crawl-{start_record_id + index}",
            "title": row.get("title"),
            "publication": row.get("publication"),
            "author": row.get("author") or None,
            "date_published": str(year),
            "year": year,
            "url": row.get("url"),
            "snippet": row.get("evidence_summary"),
            "publicness_level": "public_metadata_candidate",
            "ingestion_status": "live_crawl_candidate_not_reviewed",
            "source_name": "OpenAlex live public metadata" if source_type.endswith("openalex") else "Crossref live public metadata",
            "source_type": source_type,
            "canonical_figure": figure,
            "cluster": "live_gap_public_metadata_candidate",
            "tier": "candidate",
            "include_status": "localhost_candidate_overlay_only",
            "figure_humanoid_degree": "needs_review",
            "ontology_default": row.get("narrative_type_guess"),
            "involves_indigenous_knowledge": indigenous_related,
            "canonical_figure_guess": figure,
            "figure_name_as_printed": row.get("figure_terms_matched") or figure,
            "ontology_code": row.get("narrative_type_guess"),
            "humanoid_degree_code": "needs_review",
            "source_voice": "public_metadata",
            "genre": "catalogue_metadata",
            "publicness_code": "public_metadata_candidate",
            "relevance_code": "needs_review",
            "ethics_flag": "needs_human_ethics_review" if indigenous_related else "public_metadata_review_required",
            "coding_notes": "Live public metadata candidate from 1926-2011 gap crawl; not production-reviewed.",
            "date_band": date_band_for_year(data, year),
            "location_summary": row.get("state_hint") or "No reviewed place evidence.",
            "state_territory": row.get("state_hint") or None,
            "location_precision_status": "not_reviewed",
            "has_strict_map_point": False,
            "map_latitude": None,
            "map_longitude": None,
            "map_place_name": None,
            "map_location_role": "not_map_eligible_without_place_review",
            "map_location_type": None,
            "map_geocode_source": None,
            "map_verification_status": "not_reviewed",
            "map_confidence": None,
            "map_evidence_text": None,
        }
        records.append(record)
    return records


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = row.get(key)
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
    query_counts = Counter(str(query.get("source_type")) for query in data.get("queries", []) if query.get("source_type"))
    summary["source_rollup"] = {
        source_type: {"record_count": count, "query_count": query_counts.get(source_type, 0)}
        for source_type, count in summary["source_type_counts"].items()
    }
    for source_type, count in query_counts.items():
        summary["source_rollup"].setdefault(source_type, {"record_count": 0, "query_count": count})
    band_counts = Counter(record.get("date_band") for record in records)
    mapped_lookup = {record["record_id"]: record for record in records if isinstance(record.get("record_id"), int)}
    mapped_band_counts = Counter(
        mapped_lookup[flag["record_id"]].get("date_band")
        for flag in flags
        if flag.get("record_id") in mapped_lookup
    )
    for band in data.get("date_bands", []):
        band_id = band.get("id")
        band["record_count"] = int(band_counts.get(band_id, 0))
        band["mapped_count"] = int(mapped_band_counts.get(band_id, 0))
        band["mapped_share"] = round((band["mapped_count"] / band["record_count"]) * 100, 1) if band["record_count"] else 0


def write_report(path: Path, candidates: list[dict[str, str]], records: list[dict[str, Any]], output: Path) -> None:
    lines = [
        "# 1926-2011 Live Candidate Localhost Overlay",
        "",
        "This overlay adds real public-metadata crawl candidates to localhost frontend data. It is not production data.",
        "",
        f"- Output: `{output.relative_to(ROOT)}`",
        f"- Added live crawl candidates: {len(records)}",
        "- Added mapped flags: 0",
        "- Map eligibility remains blocked until place-level review.",
        "",
        "## Candidate Sources",
    ]
    for source, count in Counter(row["source_api"] for row in candidates).most_common():
        lines.append(f"- {source}: {count}")
    lines.extend(["", "## Query Families"])
    for family, count in Counter(row["query_family_id"] for row in candidates).most_common():
        lines.append(f"- {family}: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--candidates", type=Path, nargs="+", default=[DEFAULT_CANDIDATES])
    parser.add_argument("--public-output", type=Path, default=DEFAULT_PUBLIC_OUTPUT)
    parser.add_argument("--interim-output", type=Path, default=DEFAULT_INTERIM_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    data = load_json(args.input)
    candidates = load_candidates(args.candidates)
    source_ids = ensure_sources(data, candidates)
    query_ids = ensure_queries(data, candidates, source_ids)
    records = overlay_records(data, candidates, source_ids, query_ids)
    data["schema_version"] = f"{data.get('schema_version', 'frontend-data/v1')}+live-crawl-candidate-overlay"
    data["generated_at"] = utc_now_iso()
    data.setdefault("scope", {})["visual_mode"] = "localhost_live_crawl_candidate_overlay"
    data.setdefault("records", []).extend(records)
    recompute_summary(data)
    write_json(args.public_output, data)
    write_json(args.interim_output, data)
    write_report(args.report, candidates, records, args.public_output)
    print(f"Wrote live-crawl frontend overlay: {args.public_output}")
    print(f"Added live candidates: {len(records)}")
    print(f"Totals: records={data['summary']['record_count']} mapped={data['summary']['mapped_record_count']}")


if __name__ == "__main__":
    main()
