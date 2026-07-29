#!/usr/bin/env python3
"""Crawl AYR state report indexes into stage-only gap candidates.

The AYR public map is coordinate-rich but not necessarily exhaustive. The state
index pages list public report links with place and year in the anchor text.
This crawler fetches only those seven public index pages, reuses AYR map
coordinates when available, and clearly marks when a coordinate is derived from
another AYR marker for the same place rather than the exact report URL.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "html"
DEFAULT_OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_state_indexes"
DEFAULT_CANDIDATES = DEFAULT_OUT_DIR / "ayr_state_indexes_round014_candidates.csv"
DEFAULT_RAW = DEFAULT_OUT_DIR / "ayr_state_indexes_round014_raw.ndjson"
DEFAULT_REQUESTS = DEFAULT_OUT_DIR / "ayr_state_indexes_round014_requests.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_ayr_state_indexes_round014.md"
DEFAULT_MAP_RAW = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_yowie_map" / "ayr_yowie_map_round013_raw.ndjson"

BASE_URL = "https://www.yowiehunters.com.au"
SOURCE_NAME = "Australian Yowie Research state report indexes"
SOURCE_TYPE = "public_web_yowie_state_report_index"
SOURCE_TIER = "public_claim_report_index"
USER_AGENT = "AusFiguresGapCrawler/0.4 public metadata research"

STATE_PAGES = {
    "NSW": ("new-south-wales", "New South Wales"),
    "QLD": ("queensland", "Queensland"),
    "VIC": ("victoria", "Victoria"),
    "WA": ("western-australia", "Western Australia"),
    "SA": ("south-australia", "South Australia"),
    "NT": ("northern-territory", "Northern Territory"),
    "TAS": ("tasmania", "Tasmania"),
}

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

ANCHOR_RE = re.compile(r"<a\s+href=\"(?P<href>[^\"]+)\"[^>]*>(?P<text>.*?)</a>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
YEAR_RE = re.compile(r"\b(17\d{2}|18\d{2}|19\d{2}|20[0-2]\d)\b")
DECADE_RE = re.compile(r"\b(19\d0|20[0-2]0)s\b")
INDIGENOUS_TITLE_RE = re.compile(r"\b(aboriginal|indigenous|first nations|dreaming|dreamtime)\b", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or "")).replace("\xa0", " ")).strip()


def strip_tags(value: str) -> str:
    return clean(TAG_RE.sub(" ", value))


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def digest(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def fetch(url: str, timeout: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.2"})
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def raw_path_for_state(state: str) -> Path:
    return RAW_DIR / f"ayr_state_{state.lower()}_round014.html"


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


def location_from_title(title: str, state_name: str, state: str) -> str:
    place = clean(title)
    place = re.sub(r"\s*(?:,|\b)\s*" + re.escape(state_name) + r"\b", "", place, flags=re.I)
    place = re.sub(r"\s*\b(?:NSW|QLD|VIC|WA|SA|NT|TAS|ACT)\b", "", place, flags=re.I)
    place = re.sub(r"\s*\b(?:17|18|19|20)\d{2}(?:\s*(?:&|-|to)\s*(?:17|18|19|20)?\d{2})?.*$", "", place)
    place = re.sub(r"\s*\bunknown\b.*$", "", place, flags=re.I)
    place = clean(place.strip(" -,."))
    if not place:
        place = clean(title)
    return f"{place}, {state}"


def load_map_coordinates(path: Path) -> tuple[dict[str, dict[str, object]], dict[tuple[str, str], list[dict[str, object]]]]:
    by_url: dict[str, dict[str, object]] = {}
    by_place: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    if not path.exists():
        return by_url, by_place
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            marker = json.loads(line)
            url = clean(str(marker.get("url") or "")).lower()
            location = clean(str(marker.get("location") or ""))
            state = clean(str(marker.get("state") or ""))
            if url:
                by_url[url] = marker
            if location and state:
                place_key = norm(location.split(",", 1)[0])
                by_place[(place_key, state)].append(marker)
    return by_url, by_place


def coordinate_for_link(
    url: str,
    location_text: str,
    state: str,
    by_url: dict[str, dict[str, object]],
    by_place: dict[tuple[str, str], list[dict[str, object]]],
) -> tuple[str, str, str, str, str]:
    marker = by_url.get(url.lower())
    if marker:
        return (
            str(marker.get("lat") or ""),
            str(marker.get("lon") or ""),
            "source_map_marker_exact_url",
            "ayr_public_yowie_map_marker_exact_url",
            "AYR public map contains a marker for the same report URL.",
        )
    place_key = norm(location_text.split(",", 1)[0])
    place_markers = by_place.get((place_key, state)) or []
    if place_markers:
        marker = place_markers[0]
        return (
            str(marker.get("lat") or ""),
            str(marker.get("lon") or ""),
            "derived_same_source_place_coordinate",
            "ayr_public_yowie_map_marker_same_place",
            "Coordinate derived from another AYR public map marker for the same place/state, not from this exact report URL.",
        )
    return "", "", "", "", ""


def parse_state_page(page: str, state: str, slug: str, state_name: str) -> list[dict[str, str | int | None]]:
    rows = []
    seen: set[str] = set()
    prefix = f"/{slug}/"
    for match in ANCHOR_RE.finditer(page):
        href = clean(match.group("href"))
        if not href.startswith(prefix):
            continue
        title = strip_tags(match.group("text"))
        if not title or title.lower() in {"next", "previous"}:
            continue
        url = urljoin(BASE_URL, href)
        parsed = urlparse(url)
        url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        year = extract_year(title, url)
        location = location_from_title(title, state_name, state)
        rows.append(
            {
                "state": state,
                "state_name": state_name,
                "url": url,
                "title": title,
                "year": year,
                "date_scope": date_scope(year),
                "location": location,
            }
        )
    return rows


def make_candidate(row: dict[str, str | int | None], coords: tuple[str, str, str, str, str], access_date: str) -> dict[str, str]:
    lat, lon, precision, geocode_source, coord_note = coords
    year = row["year"]
    scope = str(row["date_scope"])
    title = str(row["title"])
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
    url = str(row["url"])
    state = str(row["state"])
    location = str(row["location"])
    external_id = f"ayr-state-index:{digest(url + '|' + title)}"
    evidence = (
        f"Public AYR {state} report index link: {title}. "
        "The state index supplies the public report URL, place text, and year; not a verified supernatural claim."
    )
    return {
        "candidate_status": status,
        "source_name": SOURCE_NAME,
        "source_type": SOURCE_TYPE,
        "source_tier": SOURCE_TIER,
        "query_family_id": f"ayr_state_index_{state.lower()}",
        "query_string": f"AYR public {state} state report index",
        "abc_hit_id": "",
        "title": f"AYR report index: {title}",
        "publication_or_organisation": SOURCE_NAME,
        "publication_date_text": str(year or ""),
        "year": str(year or ""),
        "date_scope": scope,
        "access_date": access_date,
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_web_index_link_metadata",
        "rights_access_status": "public_page_metadata_only_full_text_not_reused",
        "narrative_type": "reported_encounter",
        "secondary_role": "public_claim_report_index_link",
        "australian_relation": "australian_yowie_report_public_state_index",
        "humanoid_basis": "explicit_humanoid",
        "source_label": "Yowie",
        "matched_terms": "Yowie;Yowie report index",
        "matched_place": location,
        "location_text": location,
        "location_role": "reported_place_from_state_report_index",
        "latitude": lat,
        "longitude": lon,
        "location_precision": precision,
        "geocode_source": geocode_source,
        "geocode_verification_status": (
            "source_provided_or_same_source_marker_coordinate_not_independently_verified" if lat and lon else ""
        ),
        "coordinate_evidence_note": coord_note,
        "duplicate_check_status": "pending_overlay_dedupe",
        "quality_class": "stage_only_public_report_index_link",
        "ethics_review_status": "needs_human_review_before_production_import",
        "cultural_sensitivity": "public_claim_report_context_review",
        "risk_flags": "indigenous_related_title_human_review_required" if sensitive_title else "",
        "acceptance_decision": decision,
        "rejection_reason": rejection,
        "evidence_summary": evidence,
        "raw_metadata_json": json.dumps(row, ensure_ascii=False, sort_keys=True),
    }


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def write_report(
    path: Path,
    rows: list[dict[str, str]],
    request_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str | int | None]],
    candidates: Path,
    raw_output: Path,
) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    scope_counts = Counter(row["date_scope"] for row in rows)
    state_counts = Counter(str(row.get("state")) for row in raw_rows)
    coord_counts = Counter(row["location_precision"] or "no_coordinate" for row in rows if row["candidate_status"] == "accepted")
    accepted = [row for row in rows if row["candidate_status"] == "accepted"]
    mapped = [row for row in accepted if row["latitude"] and row["longitude"]]
    lines = [
        "# 1926-2011 AYR State Index Crawl",
        "",
        "Stage-only crawl of seven public AYR state report index pages. This is public report metadata, not proof.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate output: `{rel(candidates)}`",
        f"- Raw link output: `{rel(raw_output)}`",
        f"- Requests: `{len(request_rows)}`",
        f"- Parsed index links: `{len(raw_rows)}`",
        f"- Accepted post-1926 candidates: `{len(accepted)}`",
        f"- Accepted candidates with coordinates: `{len(mapped)}`",
        "",
        "## Candidate Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Date Scope Counts"])
    for key, count in scope_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## State Counts"])
    for key, count in state_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted Coordinate Sources"])
    for key, count in coord_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(
        [
            "",
            "## Safety Notes",
            "- Only seven public index pages are fetched, with a delay between requests.",
            "- Linked report pages are not bulk-fetched in this round.",
            "- Same-place coordinates are marked as derived and require human review before production use.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--requests-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--map-raw", type=Path, default=DEFAULT_MAP_RAW)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=2.0)
    parser.add_argument("--use-cache", action="store_true", help="Read saved raw state pages when present.")
    args = parser.parse_args()

    access_date = utc_now_iso()
    by_url, by_place = load_map_coordinates(args.map_raw)
    raw_rows: list[dict[str, str | int | None]] = []
    request_rows: list[dict[str, str]] = []
    for state, (slug, state_name) in STATE_PAGES.items():
        url = f"{BASE_URL}/{slug}"
        raw_path = raw_path_for_state(state)
        started = time.time()
        status = "ok"
        error = ""
        try:
            if args.use_cache and raw_path.exists():
                page = raw_path.read_text(encoding="utf-8", errors="replace")
                status = "cache"
            else:
                page = fetch(url, args.timeout)
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                raw_path.write_text(page, encoding="utf-8")
                time.sleep(args.sleep)
            page_rows = parse_state_page(page, state, slug, state_name)
            raw_rows.extend(page_rows)
        except Exception as exc:  # noqa: BLE001 - request summary should preserve probe failures.
            status = "error"
            error = str(exc)
            page_rows = []
        request_rows.append(
            {
                "state": state,
                "url": url,
                "status": status,
                "error": error,
                "parsed_links": str(len(page_rows)),
                "elapsed_seconds": f"{time.time() - started:.2f}",
            }
        )

    candidates = [
        make_candidate(
            row,
            coordinate_for_link(str(row["url"]), str(row["location"]), str(row["state"]), by_url, by_place),
            access_date,
        )
        for row in raw_rows
    ]

    args.candidates.parent.mkdir(parents=True, exist_ok=True)
    with args.candidates.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(candidates)

    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    with args.raw_output.open("w", encoding="utf-8") as handle:
        for row in raw_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    args.requests_output.parent.mkdir(parents=True, exist_ok=True)
    with args.requests_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["state", "url", "status", "error", "parsed_links", "elapsed_seconds"])
        writer.writeheader()
        writer.writerows(request_rows)

    write_report(args.report, candidates, request_rows, raw_rows, args.candidates, args.raw_output)
    accepted = [row for row in candidates if row["candidate_status"] == "accepted"]
    mapped = [row for row in accepted if row["latitude"] and row["longitude"]]
    print(f"Wrote AYR state index candidates: {args.candidates}")
    print(f"Parsed links: {len(raw_rows)}")
    print(f"Accepted post-1926 candidates: {len(accepted)}")
    print(f"Accepted with coordinates: {len(mapped)}")


if __name__ == "__main__":
    main()
