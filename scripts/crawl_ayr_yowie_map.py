#!/usr/bin/env python3
"""Parse the public AYR Yowie map into stage-only gap candidates.

This script intentionally reads a saved public HTML page rather than repeatedly
requesting every report page. The source page exposes Leaflet markers with
report category, link, title, and coordinates. Rows remain localhost-only
candidates and are not promoted to the production database.
"""

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
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "raw" / "html" / "ayr_yowiemap_round013.html"
DEFAULT_OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_yowie_map"
DEFAULT_CANDIDATES = DEFAULT_OUT_DIR / "ayr_yowie_map_round013_candidates.csv"
DEFAULT_RAW = DEFAULT_OUT_DIR / "ayr_yowie_map_round013_raw.ndjson"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_ayr_yowie_map_round013.md"

SOURCE_NAME = "Australian Yowie Research / AYR Yowie Reports Map"
SOURCE_TYPE = "public_web_yowie_report_map"
SOURCE_TIER = "public_claim_report_index"
MAP_URL = "https://yowiemap.sennaswdev.com/yowiemap.php"

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

STATE_BY_PATH = {
    "new-south-wales": "NSW",
    "queensland": "QLD",
    "victoria": "VIC",
    "western-australia": "WA",
    "south-australia": "SA",
    "northern-territory": "NT",
    "tasmania": "TAS",
    "media-clips": None,
}

STATE_PATTERNS = [
    ("NSW", r"\b(?:New South Wales|NSW)\b"),
    ("QLD", r"\b(?:Queensland|QLD|South East Queensland)\b"),
    ("VIC", r"\b(?:Victoria|VIC)\b"),
    ("WA", r"\b(?:Western Australia|WA)\b"),
    ("SA", r"\b(?:South Australia|SA)\b"),
    ("NT", r"\b(?:Northern Territory|NT)\b"),
    ("TAS", r"\b(?:Tasmania|TAS)\b"),
    ("ACT", r"\b(?:Australian Capital Territory|A\.C\.T\.|ACT)\b"),
]

CATEGORY_BY_PREFIX = {
    "youtube reports, interviews": "youtube_audio_report",
    "written reports": "written_report",
    "photographs of footprints and handprints": "print_or_track_photo",
    "videos": "video_report",
    "reports from newspapers": "newspaper_clip",
    "sound recordings of calls, etc": "audio_recording",
    "photographs associated with the location": "photo_report",
    "witness sketches": "witness_sketch",
}

MARKER_RE = re.compile(
    r"var marker_info = '(?P<popup>.*?)';\s*L\.marker\(\s*\[\s*"
    r"(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*(?P<lon>-?\d+(?:\.\d+)?)\s*\]",
    re.S,
)
ANCHOR_RE = re.compile(r"<a\s+href=\"(?P<href>[^\"]+)\"[^>]*>(?P<text>.*?)</a>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
YEAR_RE = re.compile(r"\b(17\d{2}|18\d{2}|19\d{2}|20[0-2]\d)\b")
DECADE_RE = re.compile(r"\b(19\d0|20[0-2]0)s\b")
INDIGENOUS_TITLE_RE = re.compile(r"\b(aboriginal|indigenous|first nations|dreaming|dreamtime)\b", re.I)
LOCATION_RE = re.compile(
    r"\b(?:at|near|around|between|in|from|by)\s+(.+?)(?:\s+\((?:c\.?\s*)?\d{4}|"
    r"\s+\d{4}\b|,\s*(?:New South Wales|Queensland|Victoria|Western Australia|"
    r"South Australia|Northern Territory|Tasmania|A\.C\.T\.|ACT|NSW|QLD|VIC|WA|SA|NT|TAS)|$)",
    re.I,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("\xa0", " ")).strip()


def strip_tags(value: str) -> str:
    return clean(TAG_RE.sub(" ", value))


def digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def extract_year(title: str, url: str) -> int | None:
    for source in (title, url):
        years = [int(match.group(1)) for match in YEAR_RE.finditer(source)]
        years = [year for year in years if 1700 <= year <= 2026]
        if years:
            return years[-1]
        decades = [int(match.group(1)) for match in DECADE_RE.finditer(source)]
        decades = [year for year in decades if 1920 <= year <= 2020]
        if decades:
            return decades[-1]
    return None


def date_scope(year: int | None) -> str:
    if year is None:
        return "undated_lead"
    if year < 1926:
        return "pre_1926_out_of_scope"
    if year <= 2011:
        return "1926_2011_gap_candidate"
    return "post_2011_context_candidate"


def state_from_title_or_url(title: str, url: str) -> str | None:
    for state, pattern in STATE_PATTERNS:
        if re.search(pattern, title, flags=re.I):
            return state
    parts = [part for part in urlparse(url).path.strip("/").split("/") if part]
    if parts:
        first = parts[0].lower()
        if first in STATE_BY_PATH:
            return STATE_BY_PATH[first]
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


def location_from_title(title: str, state: str | None) -> str:
    text = re.sub(r"^(?:YouTube reports, interviews|Written reports|Reports from newspapers|Videos|Witness sketches):\s*", "", title, flags=re.I)
    text = re.sub(r"^Yowie\s+(?:Sighting|Sightings|Attack|Footage|Report|Reports?|Article|Encounter|Possible Yowie Sighting)\s*", "", text, flags=re.I)
    match = LOCATION_RE.search(text)
    if match:
        place = clean(match.group(1))
    else:
        place = clean(text)
    place = re.sub(r"\s*\((?:c\.?\s*)?(?:17|18|19|20)\d{2}[^)]*\)\s*$", "", place)
    place = re.sub(r"\s+(?:17|18|19|20)\d{2}(?:\s*\(\d+\))?\s*$", "", place)
    place = clean(place.strip(" -.,"))
    if not place:
        place = clean(text)
    return f"{place}, {state}" if state and state not in place else place


def category_from_text(prefix: str, url: str) -> tuple[str, str]:
    key = clean(prefix).lower()
    category = CATEGORY_BY_PREFIX.get(key)
    if not category:
        if "youtube.com" in url:
            category = "youtube_audio_report"
        elif "/media-clips/" in url:
            category = "newspaper_clip"
        else:
            category = "public_map_report"
    return category, clean(prefix) or category


def parse_markers(page: str) -> list[dict[str, str | int | float | None]]:
    markers = []
    for index, match in enumerate(MARKER_RE.finditer(page), start=1):
        popup = match.group("popup")
        anchor = ANCHOR_RE.search(popup)
        if not anchor:
            continue
        url = clean(anchor.group("href")).strip()
        if url.startswith("ttps://"):
            url = "h" + url
        title_text = strip_tags(anchor.group("text"))
        prefix = title_text.split(":", 1)[0] if ":" in title_text else ""
        title = clean(title_text)
        category, category_label = category_from_text(prefix, url)
        lat = float(match.group("lat"))
        lon = float(match.group("lon"))
        year = extract_year(title, url)
        state = state_from_title_or_url(title, url) or state_from_coords(lat, lon)
        location = location_from_title(title, state)
        markers.append(
            {
                "index": index,
                "url": url,
                "title": title,
                "year": year,
                "date_scope": date_scope(year),
                "state": state,
                "location": location,
                "lat": lat,
                "lon": lon,
                "category": category,
                "category_label": category_label,
                "popup_html": clean(popup),
            }
        )
    return markers


def make_candidate(marker: dict[str, str | int | float | None], access_date: str) -> dict[str, str]:
    year = marker["year"]
    scope = str(marker["date_scope"])
    title = str(marker["title"])
    sensitive_title = bool(INDIGENOUS_TITLE_RE.search(title))
    accepted = isinstance(year, int) and year >= 1926 and not sensitive_title
    if sensitive_title:
        status = "lead_only"
        decision = "not_accepted"
        rejection = "indigenous_related_context_requires_manual_review"
    elif not accepted and scope == "pre_1926_out_of_scope":
        status = "lead_only"
        decision = "not_accepted"
        rejection = "pre_1926_out_of_gap_scope"
    elif not accepted:
        status = "lead_only"
        decision = "not_accepted"
        rejection = "missing_year_for_post_1926_gap_overlay"
    else:
        status = "accepted"
        decision = "accepted"
        rejection = ""
    url = str(marker["url"])
    category = str(marker["category"])
    location = str(marker["location"])
    external_id = f"ayr-yowie-map:{digest(url + '|' + str(marker['lat']) + '|' + str(marker['lon']) + '|' + title)}"
    evidence = (
        f"Public AYR Yowie map marker: {title}. "
        f"Coordinates and link are displayed in the public map page; not a verified supernatural claim."
    )
    return {
        "candidate_status": status,
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "source_tier": SOURCE_TIER,
        "query_family_id": f"ayr_yowie_map_{category}",
        "query_string": "AYR public Yowie map marker extraction",
        "abc_hit_id": "",
        "title": title,
        "publication_or_organisation": SOURCE_NAME,
        "publication_date_text": str(year or ""),
        "year": str(year or ""),
        "date_scope": scope,
        "access_date": access_date,
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_web_map_marker_metadata",
        "rights_access_status": "public_page_metadata_only_full_text_not_reused",
        "narrative_type": "reported_encounter",
        "secondary_role": "public_claim_report_index_marker",
        "australian_relation": "australian_yowie_report_public_map",
        "humanoid_basis": "explicit_humanoid",
        "source_label": "Yowie",
        "matched_terms": "Yowie;Yowie Sighting",
        "matched_place": location,
        "location_text": location,
        "location_role": "reported_place_or_public_display_location",
        "latitude": str(marker["lat"]),
        "longitude": str(marker["lon"]),
        "location_precision": "source_map_marker",
        "geocode_source": "ayr_public_yowie_map_marker",
        "geocode_verification_status": "source_provided_map_marker_not_independently_verified",
        "coordinate_evidence_note": "Coordinate parsed from public Leaflet marker in AYR-linked Yowie map.",
        "duplicate_check_status": "pending_overlay_dedupe",
        "quality_class": "stage_only_public_report_marker",
        "ethics_review_status": "needs_human_review_before_production_import",
        "cultural_sensitivity": "public_claim_report_context_review",
        "risk_flags": "indigenous_related_title_human_review_required" if sensitive_title else "",
        "acceptance_decision": decision,
        "rejection_reason": rejection,
        "evidence_summary": evidence,
        "raw_metadata_json": json.dumps(marker, ensure_ascii=False, sort_keys=True),
    }


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_report(
    path: Path,
    candidates_path: Path,
    raw_path: Path,
    markers: list[dict[str, str | int | float | None]],
    rows: list[dict[str, str]],
    access_date: str,
) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    scope_counts = Counter(row["date_scope"] for row in rows)
    category_counts = Counter(marker["category"] for marker in markers)
    accepted = [row for row in rows if row["candidate_status"] == "accepted"]
    accepted_1926_2011 = [row for row in accepted if row["date_scope"] == "1926_2011_gap_candidate"]
    accepted_post_2011 = [row for row in accepted if row["date_scope"] == "post_2011_context_candidate"]
    lines = [
        "# 1926-2011 AYR Yowie Map Crawl",
        "",
        "Stage-only parse of one public AYR-linked Yowie map page. This is a public-report index, not a proof dataset.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Source page: `{MAP_URL}`",
        f"- Saved input: `{rel(DEFAULT_INPUT)}`",
        f"- Candidate output: `{rel(candidates_path)}`",
        f"- Raw marker output: `{rel(raw_path)}`",
        f"- Access date: `{access_date}`",
        f"- Parsed markers: `{len(markers)}`",
        f"- Accepted post-1926 candidates: `{len(accepted)}`",
        f"- Accepted 1926-2011 gap candidates: `{len(accepted_1926_2011)}`",
        f"- Accepted post-2011 context candidates: `{len(accepted_post_2011)}`",
        "",
        "## Candidate Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Date Scope Counts"])
    for key, count in scope_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Marker Categories"])
    for key, count in category_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(
        [
            "",
            "## Publicness And Risk Notes",
            "- One public HTML page was downloaded and parsed offline; linked report pages were not bulk-fetched.",
            "- Coordinates are source-provided map marker coordinates and are not independently geocoded here.",
            "- Rows are marked `stage_only_public_report_marker` and require human review before production import.",
            "- This source should be displayed as public report metadata, never as verified habitat, population, or proof.",
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
    markers = parse_markers(page)
    rows = [make_candidate(marker, access_date) for marker in markers]

    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    with args.candidates.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    with args.raw_output.open("w", encoding="utf-8") as handle:
        for marker in markers:
            handle.write(json.dumps(marker, ensure_ascii=False, sort_keys=True) + "\n")

    write_report(args.report, args.candidates, args.raw_output, markers, rows, access_date)
    accepted = [row for row in rows if row["candidate_status"] == "accepted"]
    print(f"Wrote AYR Yowie map candidates: {args.candidates}")
    print(f"Parsed markers: {len(markers)}")
    print(f"Accepted post-1926 candidates: {len(accepted)}")


if __name__ == "__main__":
    main()
