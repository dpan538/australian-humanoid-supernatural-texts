#!/usr/bin/env python3
"""Build a localhost overlay from stage-only public web gap candidates."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "public" / "data" / "frontend-data.live-crawl.json"
DEFAULT_FALLBACK_INPUT = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_CANDIDATES = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search" / "abc_public_search_round001_candidates.csv"
DEFAULT_PUBLIC_OUTPUT = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
DEFAULT_INTERIM_OUTPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "frontend-data.gap-public-web.json"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_gap_public_web_overlay.md"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def max_int(rows: list[dict[str, Any]], key: str, fallback: int) -> int:
    values = [row.get(key) for row in rows if isinstance(row.get(key), int)]
    return max(values, default=fallback)


def year_from_text(value: str) -> int | None:
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", value or "")
    if not match:
        return None
    return int(match.group(1))


def date_band_for_year(data: dict[str, Any], year: int | None) -> str:
    if year is None:
        return "unknown"
    for band in data.get("date_bands", []):
        start = band.get("start")
        end = band.get("end")
        if start is None:
            continue
        if year >= int(start) and (end is None or year <= int(end)):
            return str(band["id"])
    return "unknown"


def state_from_location(value: str) -> str | None:
    for token in ("NSW", "QLD", "VIC", "TAS", "SA", "WA", "NT", "ACT"):
        if re.search(rf"\b{token}\b", value or ""):
            return token
    return None


def canonical_figure(row: dict[str, str]) -> str:
    label = (row.get("source_label") or row.get("matched_terms") or "").lower()
    if "yowie" in label:
        return "Yowie"
    if "yahoo" in label:
        return "Yahoo"
    if "hairy" in label:
        return "hairy man"
    if "mimih" in label:
        return "Mimih"
    if "mimi" in label:
        return "Mimi"
    if "spirit_people" in label or "spirit people" in label:
        return "Spirit People"
    if "apparition" in label:
        return "apparition"
    if "phantom" in label:
        return "phantom"
    if "haunted" in label:
        return "haunted"
    if "ghost" in label or "spook" in label:
        return "ghost"
    return row.get("source_label") or "reported_supernatural_figure"


def humanoid_degree(row: dict[str, str]) -> str:
    label = (row.get("source_label") or row.get("matched_terms") or "").lower()
    if any(term in label for term in ("yowie", "yahoo", "hairy", "wild man", "spirit people", "mimih", "mimi")):
        return "explicit_humanoid"
    if any(term in label for term in ("ghost", "apparition", "phantom", "spook", "lady")):
        return "person_form"
    return "needs_review"


def source_voice(row: dict[str, str]) -> str:
    source_type = row.get("source_type") or ""
    if "media" in source_type:
        return "public_media"
    if "education" in source_type:
        return "public_education"
    return "public_web"


def load_candidates(paths: list[Path]) -> tuple[list[dict[str, str]], Counter[str]]:
    rows: list[dict[str, str]] = []
    statuses: Counter[str] = Counter()
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                statuses[row.get("candidate_status") or ""] += 1
                if row.get("candidate_status") == "accepted" and row.get("acceptance_decision") == "accepted":
                    rows.append(row)
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        key = (row.get("canonical_url") or row.get("url") or "", norm(row.get("location_text") or row.get("source_label") or row.get("title") or ""))
        if key in seen:
            statuses["overlay_duplicate_within_candidates"] += 1
            continue
        seen.add(key)
        unique.append(row)
    return unique, statuses


def base_duplicate_keys(data: dict[str, Any]) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    urls: set[str] = set()
    url_places: set[tuple[str, str]] = set()
    external_ids: set[str] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(url)
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
        place = clean(record.get("map_place_name") or record.get("location_summary") or "")
        if url and place:
            url_places.add((url, norm(place.split(",", 1)[0].split("(", 1)[0])))
    return urls, url_places, external_ids


def filter_new_candidates(data: dict[str, Any], rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], Counter[str]]:
    urls, url_places, external_ids = base_duplicate_keys(data)
    kept: list[dict[str, str]] = []
    stats: Counter[str] = Counter()
    for row in rows:
        url = clean(row.get("canonical_url") or row.get("url")).lower()
        place = norm(clean(row.get("location_text")).split(",", 1)[0])
        external_id = clean(row.get("external_id"))
        if external_id and external_id in external_ids:
            stats["duplicate_external_id_against_base"] += 1
            continue
        if url and place and (url, place) in url_places:
            stats["duplicate_url_place_against_base"] += 1
            continue
        if url and not place and url in urls:
            stats["duplicate_url_against_base"] += 1
            continue
        kept.append(row)
    return kept, stats


def ensure_source(data: dict[str, Any], row: dict[str, str]) -> int:
    source_name = row.get("source_name") or "Public web gap candidate"
    source_type = row.get("source_type") or "public_web_gap_candidate"
    for source in data.get("sources", []):
        if source.get("source_name") == source_name and source.get("source_type") == source_type:
            return int(source["source_id"])
    next_id = max_int(data.get("sources", []), "source_id", 0) + 1
    data.setdefault("sources", []).append(
        {
            "source_id": next_id,
            "source_name": source_name,
            "source_type": source_type,
            "base_url": "https://www.abc.net.au/" if "ABC" in source_name or "Broadcasting" in source_name else None,
            "access_method": "stage_only_public_web_gap_crawl",
            "publicness_level": row.get("publicness_status") or "public_web_page",
            "ethics_notes": "Localhost gap candidate overlay only; human review required before production import.",
        }
    )
    return next_id


def ensure_query(data: dict[str, Any], row: dict[str, str], source_id: int, cache: dict[tuple[int, str, str], int]) -> int:
    family = row.get("query_family_id") or "public_web_gap_candidate"
    query = row.get("query_string") or family
    key = (source_id, family, query)
    if key in cache:
        return cache[key]
    next_id = max_int(data.get("queries", []), "query_id", 0) + 1
    cache[key] = next_id
    data.setdefault("queries", []).append(
        {
            "query_id": next_id,
            "figure_id": None,
            "source_id": source_id,
            "query_string": query,
            "query_type": "stage_only_public_web_gap_crawl",
            "date_start": "1926",
            "date_end": "2026",
            "expected_noise_level": "measured_in_probe",
            "status": "localhost_candidate_overlay_not_production",
            "notes": f"Stage-only gap query family: {family}.",
            "source_name": row.get("source_name"),
            "source_type": row.get("source_type"),
            "canonical_name": None,
            "date_band": row.get("date_scope") or "post_1926_gap_probe",
        }
    )
    return next_id


def map_ready(row: dict[str, str]) -> bool:
    if not row.get("latitude") or not row.get("longitude"):
        return False
    if not row.get("geocode_verification_status"):
        return False
    try:
        float(row["latitude"])
        float(row["longitude"])
    except ValueError:
        return False
    return True


def make_record(data: dict[str, Any], row: dict[str, str], record_id: int, source_id: int, query_id: int) -> dict[str, Any]:
    year = year_from_text(row.get("publication_date_text") or row.get("year") or "")
    figure = canonical_figure(row)
    mapped = map_ready(row)
    state = state_from_location(row.get("location_text") or "")
    risk_flags = row.get("risk_flags") or ""
    ethics = row.get("ethics_review_status") or ("needs_human_ethics_review" if risk_flags else "public_media_context_reviewed")
    return {
        "record_id": record_id,
        "source_id": source_id,
        "query_id": query_id,
        "figure_id": None,
        "external_id": row.get("external_id") or f"gap-public-web-{record_id}",
        "title": row.get("title"),
        "publication": row.get("publication_or_organisation") or row.get("source_name"),
        "author": None,
        "date_published": row.get("publication_date_text") or (str(year) if year else ""),
        "year": year,
        "url": row.get("canonical_url") or row.get("url"),
        "snippet": row.get("evidence_summary"),
        "publicness_level": row.get("publicness_status") or "public_web_page",
        "ingestion_status": "stage_only_gap_public_web_candidate_not_production",
        "source_name": row.get("source_name"),
        "source_type": row.get("source_type"),
        "canonical_figure": figure,
        "cluster": "gap_public_web_candidate",
        "tier": "candidate",
        "include_status": "localhost_candidate_overlay_only",
        "figure_humanoid_degree": humanoid_degree(row),
        "ontology_default": row.get("narrative_type") or "needs_review",
        "involves_indigenous_knowledge": bool(risk_flags),
        "canonical_figure_guess": figure,
        "figure_name_as_printed": (row.get("matched_terms") or row.get("source_label") or figure),
        "ontology_code": row.get("narrative_type") or "needs_review",
        "humanoid_degree_code": humanoid_degree(row),
        "source_voice": source_voice(row),
        "genre": "public_media_or_web_candidate",
        "publicness_code": row.get("publicness_status") or "public_web_page",
        "relevance_code": "needs_review",
        "ethics_flag": ethics,
        "coding_notes": "Stage-only public web gap crawl candidate; not production-reviewed.",
        "date_band": date_band_for_year(data, year),
        "location_summary": row.get("location_text") or "No reviewed place evidence.",
        "state_territory": state,
        "location_precision_status": row.get("location_precision") or ("not_reviewed" if not mapped else "reviewed_place_catalog_match"),
        "has_strict_map_point": mapped,
        "map_latitude": float(row["latitude"]) if mapped else None,
        "map_longitude": float(row["longitude"]) if mapped else None,
        "map_place_name": row.get("location_text") if mapped else None,
        "map_location_role": row.get("location_role") if mapped else "not_map_eligible_without_place_review",
        "map_location_type": row.get("location_precision") if mapped else None,
        "map_geocode_source": row.get("geocode_source") if mapped else None,
        "map_verification_status": row.get("geocode_verification_status") if mapped else "not_reviewed",
        "map_confidence": "medium" if mapped else None,
        "map_evidence_text": row.get("coordinate_evidence_note") if mapped else None,
    }


def make_map_flag(record: dict[str, Any], next_flag_id: int) -> dict[str, Any]:
    return {
        "flag_id": f"gap-public-web:{next_flag_id}",
        "record_id": record["record_id"],
        "state_territory": record.get("state_territory"),
        "x": record["map_longitude"],
        "y": record["map_latitude"],
        "stem_dx": 0,
        "stem_dy": 0,
        "display_precision": "precise_point" if record.get("map_location_type") == "exact_site" else "approximate_point",
        "source_location_type": record.get("map_location_type"),
        "confidence": record.get("map_confidence") or "medium",
        "title": record.get("title"),
        "year": record.get("year"),
        "canonical_figure": record.get("canonical_figure_guess"),
    }


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


def year_bucket(year: int | None) -> str:
    if year is None:
        return "undated"
    if 1926 <= year <= 1945:
        return "1926-1945"
    if 1946 <= year <= 1969:
        return "1946-1969"
    if 1970 <= year <= 1990:
        return "1970-1990"
    if 1991 <= year <= 2011:
        return "1991-2011"
    if year >= 2012:
        return "2012-2026"
    return "pre-1926"


def write_report(
    path: Path,
    candidates: list[dict[str, str]],
    kept: list[dict[str, str]],
    records: list[dict[str, Any]],
    status_counts: Counter[str],
    overlay_dupes: Counter[str],
    output: Path,
    data: dict[str, Any],
) -> None:
    try:
        output_label = str(output.resolve().relative_to(ROOT))
    except ValueError:
        output_label = str(output)
    mapped = [record for record in records if record.get("has_strict_map_point")]
    bucket_counts = Counter(year_bucket(record.get("year")) for record in records)
    mapped_bucket_counts = Counter(year_bucket(record.get("year")) for record in mapped)
    source_counts = Counter(record.get("source_type") for record in records)
    query_counts = Counter(row.get("query_family_id") for row in kept)
    lines = [
        "# 1926-2011 Gap Public Web Localhost Overlay",
        "",
        "This overlay adds stage-only public web/ABC candidates to localhost frontend data. It is not production data.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Output: `{output_label}`",
        f"- Accepted candidate rows loaded: `{len(candidates)}`",
        f"- New rows after base dedupe: `{len(kept)}`",
        f"- Added records: `{len(records)}`",
        f"- Added map flags: `{len(mapped)}`",
        f"- Localhost totals: `{data['summary']['record_count']}` records / `{data['summary']['mapped_record_count']}` mapped",
        "",
        "## Candidate Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key or 'blank'}: {count}")
    lines.extend(["", "## Overlay Duplicate Filters"])
    for key, count in overlay_dupes.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Evidence Table By Year Bucket"])
    lines.append("| bucket | added_records | added_mapped |")
    lines.append("|---|---:|---:|")
    for bucket in ["1926-1945", "1946-1969", "1970-1990", "1991-2011", "2012-2026", "undated"]:
        lines.append(f"| {bucket} | {bucket_counts.get(bucket, 0)} | {mapped_bucket_counts.get(bucket, 0)} |")
    lines.extend(["", "## Source Families"])
    for key, count in source_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Query Families"])
    for key, count in query_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes"])
    lines.append("- Map flags use reviewed coordinates already present in frontend or prior stage files; new unreviewed geocoding is not performed here.")
    lines.append("- All rows remain localhost-only until human review approves production import.")
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

    input_path = args.input if args.input.exists() else DEFAULT_FALLBACK_INPUT
    data = load_json(input_path)
    candidates, status_counts = load_candidates(args.candidates)
    kept, overlay_dupes = filter_new_candidates(data, candidates)
    query_cache: dict[tuple[int, str, str], int] = {}
    start_record_id = max(9_380_000, max_int(data.get("records", []), "record_id", 0) + 1)
    start_flag_id = len(data.get("map_flags", [])) + 1
    records: list[dict[str, Any]] = []
    flags: list[dict[str, Any]] = []
    for index, row in enumerate(kept):
        source_id = ensure_source(data, row)
        query_id = ensure_query(data, row, source_id, query_cache)
        record = make_record(data, row, start_record_id + index, source_id, query_id)
        records.append(record)
        if record["has_strict_map_point"]:
            flags.append(make_map_flag(record, start_flag_id + len(flags)))
    data["schema_version"] = f"{data.get('schema_version', 'frontend-data/v1')}+gap-public-web-overlay"
    data["generated_at"] = utc_now_iso()
    data.setdefault("scope", {})["visual_mode"] = "localhost_gap_public_web_candidate_overlay"
    data.setdefault("records", []).extend(records)
    data.setdefault("map_flags", []).extend(flags)
    recompute_summary(data)
    write_json(args.public_output, data)
    write_json(args.interim_output, data)
    write_report(args.report, candidates, kept, records, status_counts, overlay_dupes, args.public_output, data)
    print(f"Wrote gap public web overlay: {args.public_output}")
    print(f"Added records: {len(records)}")
    print(f"Added mapped flags: {len(flags)}")
    print(f"Totals: records={data['summary']['record_count']} mapped={data['summary']['mapped_record_count']}")


if __name__ == "__main__":
    main()
