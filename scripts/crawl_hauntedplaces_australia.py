#!/usr/bin/env python3
"""Parse HauntedPlaces.org Australia directory into stage-only candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "html" / "hauntedplaces_australia_round015.html"
DEFAULT_OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "hauntedplaces"
DEFAULT_CANDIDATES = DEFAULT_OUT_DIR / "hauntedplaces_australia_round015_candidates.csv"
DEFAULT_RAW = DEFAULT_OUT_DIR / "hauntedplaces_australia_round015_raw.ndjson"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_hauntedplaces_australia_round015.md"

SOURCE_NAME = "HauntedPlaces.org Australia directory"
SOURCE_TYPE = "public_web_haunted_places_directory"
SOURCE_TIER = "public_directory_page"
SOURCE_PAGE = "https://www.hauntedplaces.org/Australia"

FIELDNAMES = [
    "candidate_status",
    "source_name",
    "source_type",
    "source_tier",
    "query_family_id",
    "query_string",
    "abc_hit_id",
    "title",
    "publication_or_organisation",
    "publication_date_text",
    "year",
    "date_scope",
    "access_date",
    "url",
    "canonical_url",
    "external_id",
    "publicness_status",
    "rights_access_status",
    "narrative_type",
    "secondary_role",
    "australian_relation",
    "humanoid_basis",
    "source_label",
    "matched_terms",
    "matched_place",
    "location_text",
    "location_role",
    "latitude",
    "longitude",
    "location_precision",
    "geocode_source",
    "geocode_verification_status",
    "coordinate_evidence_note",
    "duplicate_check_status",
    "quality_class",
    "ethics_review_status",
    "cultural_sensitivity",
    "risk_flags",
    "acceptance_decision",
    "rejection_reason",
    "evidence_summary",
    "raw_metadata_json",
]

MARKER_RE = re.compile(
    r"L\.marker\(\[(?P<lat>-?\d+(?:\.\d+)?),(?P<lon>-?\d+(?:\.\d+)?)\].*?"
    r"<a href='(?P<url>https://www\.hauntedplaces\.org/item/[^']+/)'>(?P<title>.*?)</a>",
    re.S | re.I,
)
LISTING_RE = re.compile(
    r"<h3><a href=\"(?P<url>https://www\.hauntedplaces\.org/item/[^\"]+/)\">(?P<title>.*?)</a></h3>\s*"
    r"<h5><b>(?P<location>.*?)</b></h5>\s*"
    r"<p>(?P<snippet>.*?)</p>",
    re.S | re.I,
)
TAG_RE = re.compile(r"<[^>]+>")

STATE_NAMES = {
    "Australian Capital Territory": "ACT",
    "New South Wales": "NSW",
    "Northern Territory": "NT",
    "Queensland": "QLD",
    "South Australia": "SA",
    "Tasmania": "TAS",
    "Victoria": "VIC",
    "Western Australia": "WA",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("\xa0", " ")).strip()


def strip_tags(value: str) -> str:
    return clean(TAG_RE.sub(" ", value))


def digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def state_from_location(location: str) -> str | None:
    for name, code in STATE_NAMES.items():
        if name.lower() in location.lower():
            return code
    return None


def state_from_coords(lat: float, lon: float) -> str | None:
    if 148.7 <= lon <= 149.5 and -35.95 <= lat <= -35.1:
        return "ACT"
    if 138.0 <= lon <= 154.1 and -29.2 <= lat <= -9.0:
        return "QLD"
    if 140.8 <= lon <= 154.1 and -37.8 <= lat <= -28.0:
        return "NSW"
    if 140.8 <= lon <= 150.2 and -39.3 <= lat <= -33.8:
        return "VIC"
    if 112.0 <= lon <= 129.1 and -36.5 <= lat <= -13.0:
        return "WA"
    if 129.0 <= lon <= 141.1 and -38.5 <= lat <= -25.0:
        return "SA"
    if 129.0 <= lon <= 138.2 and -26.2 <= lat <= -10.0:
        return "NT"
    if 143.5 <= lon <= 148.8 and -44.0 <= lat <= -39.0:
        return "TAS"
    return None


def parse(page: str) -> list[dict[str, object]]:
    listings: dict[str, dict[str, str]] = {}
    for match in LISTING_RE.finditer(page):
        url = clean(match.group("url"))
        listings[url] = {
            "title": strip_tags(match.group("title")),
            "location": strip_tags(match.group("location")),
            "snippet": strip_tags(match.group("snippet")),
        }
    rows = []
    seen: set[str] = set()
    for match in MARKER_RE.finditer(page):
        url = clean(match.group("url"))
        if url in seen:
            continue
        seen.add(url)
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        listing = listings.get(url, {})
        title = listing.get("title") or strip_tags(match.group("title"))
        location = listing.get("location") or ""
        state = state_from_location(location) or state_from_coords(lat, lon)
        location_text = clean(f"{location}, {state}" if state and state not in location else location)
        if not location_text:
            location_text = f"{title}, {state}" if state else title
        rows.append(
            {
                "url": url,
                "title": title,
                "location": location_text,
                "state": state,
                "snippet": listing.get("snippet") or "",
                "lat": lat,
                "lon": lon,
            }
        )
    return rows


def make_candidate(row: dict[str, object], access_date: str) -> dict[str, str]:
    url = str(row["url"])
    title = str(row["title"])
    location = str(row["location"])
    evidence = clean(
        f"Public HauntedPlaces.org Australia directory marker: {title}. "
        f"{row.get('snippet') or ''} This is a directory claim/legend entry, not a verified supernatural claim."
    )
    return {
        "candidate_status": "accepted",
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "source_tier": SOURCE_TIER,
        "query_family_id": "hauntedplaces_australia_directory",
        "query_string": "HauntedPlaces.org Australia directory markers",
        "abc_hit_id": "",
        "title": f"HauntedPlaces directory: {title}",
        "publication_or_organisation": SOURCE_NAME,
        "publication_date_text": "",
        "year": "",
        "date_scope": "undated_public_web_directory_candidate",
        "access_date": access_date,
        "url": url,
        "canonical_url": url,
        "external_id": f"hauntedplaces-australia:{digest(url)}",
        "publicness_status": "public_web_directory_page",
        "rights_access_status": "public_page_metadata_and_short_summary_only",
        "narrative_type": "haunting_or_apparition_report",
        "secondary_role": "public_haunted_place_directory_marker",
        "australian_relation": "australian_haunted_place_public_directory",
        "humanoid_basis": "person_form_or_ghost_context",
        "source_label": "ghost",
        "matched_terms": "ghost;haunted;apparition",
        "matched_place": location,
        "location_text": location,
        "location_role": "haunted_place_directory_display_location",
        "latitude": str(row["lat"]),
        "longitude": str(row["lon"]),
        "location_precision": "source_directory_marker",
        "geocode_source": "hauntedplaces_leaflet_marker",
        "geocode_verification_status": "source_provided_directory_marker_not_independently_verified",
        "coordinate_evidence_note": "Coordinate parsed from public HauntedPlaces.org Australia Leaflet marker.",
        "duplicate_check_status": "pending_overlay_dedupe",
        "quality_class": "stage_only_public_directory_marker",
        "ethics_review_status": "needs_human_review_before_production_import",
        "cultural_sensitivity": "public_haunted_place_directory_review",
        "risk_flags": "",
        "acceptance_decision": "accepted",
        "rejection_reason": "",
        "evidence_summary": evidence[:900],
        "raw_metadata_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
    }


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_report(path: Path, rows: list[dict[str, object]], candidates: Path, raw: Path) -> None:
    state_counts = Counter(str(row.get("state") or "unknown") for row in rows)
    lines = [
        "# 1926-2011 HauntedPlaces Australia Directory Crawl",
        "",
        "Stage-only parse of a public Australia haunted-place directory page. These rows are undated directory candidates.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Source page: `{SOURCE_PAGE}`",
        f"- Candidate output: `{rel(candidates)}`",
        f"- Raw output: `{rel(raw)}`",
        f"- Parsed markers: `{len(rows)}`",
        f"- Accepted mapped candidates: `{len(rows)}`",
        "",
        "## State Counts",
    ]
    for key, count in state_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(
        [
            "",
            "## Safety Notes",
            "- No detail pages or uploads were fetched in this round.",
            "- Rows are undated and should not be used to infer annual event trends.",
            "- Coordinates are source-provided directory markers and require human review before production import.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    access_date = utc_now_iso()
    page = args.input.read_text(encoding="utf-8", errors="replace")
    rows = parse(page)
    candidates = [make_candidate(row, access_date) for row in rows]

    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    with args.candidates.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(candidates)

    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    with args.raw_output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    write_report(args.report, rows, args.candidates, args.raw_output)
    print(f"Wrote HauntedPlaces candidates: {args.candidates}")
    print(f"Parsed markers: {len(rows)}")


if __name__ == "__main__":
    main()
