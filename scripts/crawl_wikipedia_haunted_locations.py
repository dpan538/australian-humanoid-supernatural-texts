#!/usr/bin/env python3
"""Stage-only crawl for Wikipedia's Australia haunted-locations list."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from crawl_public_books_metadata import FIELDNAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "wikipedia_haunted_locations"
DEFAULT_OUTPUT = OUT_DIR / "wikipedia_haunted_locations_round019_candidates.csv"
DEFAULT_RAW = OUT_DIR / "wikipedia_haunted_locations_round019_raw.json"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_wikipedia_haunted_locations_round019.md"
PAGE_TITLE = "List of reportedly haunted locations"
PAGE_URL = "https://en.wikipedia.org/wiki/List_of_reportedly_haunted_locations"
USER_AGENT = "AusFiguresGapCrawler/0.4 public Wikipedia metadata research"

ALIASES = {
    "Ararat Lunatic Asylum": ("Aradale", "Aradale Asylum", "Ararat Lunatic Asylum"),
    "Beechworth Lunatic Asylum": ("Beechworth Asylum", "Beechworth Lunatic Asylum"),
    "Dreamworld": ("Dreamworld",),
    "Hotel Kurrajong": ("Hotel Kurrajong",),
    "Monte Cristo Homestead": ("Monte Cristo Homestead", "Monte Cristo"),
    "North Head Quarantine Station": ("North Head Quarantine Station", "Quarantine Station"),
    "Port Arthur, Tasmania": ("Port Arthur Historic Site", "Port Arthur, Tasmania", "Port Arthur"),
    "Princess Alexandra Hospital": ("Princess Alexandra Hospital",),
    "Princess Theatre Melbourne": ("Princess Theatre Melbourne", "Princess Theatre"),
    "Willow Court Asylum": ("Willow Court Asylum", "Willow Court"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def fetch_json(url: str, timeout: int) -> dict[str, Any]:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "-A",
            USER_AGENT,
            "-H",
            "Accept: application/json",
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl_exit_{result.returncode}")
    return json.loads(result.stdout)


def api_url() -> str:
    params = {
        "action": "parse",
        "page": PAGE_TITLE,
        "prop": "wikitext|revid",
        "format": "json",
        "formatversion": "2",
    }
    return "https://en.wikipedia.org/w/api.php?" + urlencode(params)


def strip_markup(value: str) -> str:
    value = re.sub(r"<ref[^>/]*/>", "", value)
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.S)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)
    value = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", value)
    value = re.sub(r"'{2,5}", "", value)
    value = re.sub(r"\s+\[[^\]]+\]", "", value)
    return clean(value)


def australia_section(wikitext: str) -> str:
    match = re.search(r"^==\s*Australia\s*==\s*$", wikitext, re.M)
    if not match:
        return ""
    rest = wikitext[match.end() :]
    end = re.search(r"^==\s*[^=].*?==\s*$", rest, re.M)
    return rest[: end.start()] if end else rest


def parse_entries(section: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    current = ""
    for line in section.splitlines():
        if line.startswith("*"):
            if current:
                entries.append(entry_from_bullet(current))
            current = line[1:].strip()
        elif current and line.strip():
            current += " " + line.strip()
    if current:
        entries.append(entry_from_bullet(current))
    return [entry for entry in entries if entry.get("name")]


def entry_from_bullet(text: str) -> dict[str, str]:
    plain = strip_markup(text)
    name = ""
    for known_name, aliases in ALIASES.items():
        if any(re.search(r"\b" + re.escape(alias) + r"\b", plain, re.I) for alias in aliases):
            name = known_name
            break
    if not name:
        name = clean(plain.split(" in ", 1)[0].split(" is ", 1)[0].split(",", 1)[0])
    return {"name": name, "description": plain}


def coordinate_catalog(frontend: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    catalog: dict[str, dict[str, Any]] = {}
    for record in data.get("records", []):
        lat = record.get("map_latitude")
        lon = record.get("map_longitude")
        if lat in (None, "") or lon in (None, ""):
            continue
        place = clean(record.get("map_place_name") or record.get("location_summary"))
        if not place:
            continue
        for known_name, aliases in ALIASES.items():
            if any(re.search(r"\b" + re.escape(alias) + r"\b", place, re.I) for alias in aliases):
                catalog.setdefault(
                    known_name,
                    {
                        "location_text": place,
                        "latitude": lat,
                        "longitude": lon,
                        "location_precision": record.get("map_location_type") or record.get("location_precision_status") or "reviewed_place",
                    },
                )
    return catalog


def existing_url_places(frontend: Path) -> set[tuple[str, str]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    keys: set[tuple[str, str]] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        place = clean(record.get("map_place_name") or record.get("location_summary"))
        if url and place:
            keys.add((url, norm(place.split(",", 1)[0])))
    return keys


def make_row(entry: dict[str, str], coords: dict[str, dict[str, Any]], existing: set[tuple[str, str]], revid: str) -> dict[str, Any]:
    name = entry["name"]
    coord = coords.get(name, {})
    location_text = coord.get("location_text") or name
    external_slug = hashlib.sha1(f"{PAGE_URL}:{name}:{revid}".encode("utf-8")).hexdigest()[:16]
    duplicate = (PAGE_URL.lower(), norm(location_text.split(",", 1)[0])) in existing
    status = "duplicate_existing_record" if duplicate else "accepted"
    mapped = bool(coord)
    return {
        "candidate_status": status,
        "source_name": "Wikipedia",
        "source_type": "public_wikipedia_haunted_location_list",
        "source_tier": "public_directory",
        "query_family_id": "wikipedia_haunted_locations_australia",
        "query_string": PAGE_TITLE + " / Australia section",
        "abc_hit_id": "",
        "title": f"Wikipedia haunted-location list: {name}",
        "publication_or_organisation": "Wikipedia",
        "publication_date_text": f"Undated public page; accessed {date.today().isoformat()}",
        "year": "",
        "date_scope": "undated_directory_record",
        "access_date": date.today().isoformat(),
        "url": PAGE_URL,
        "canonical_url": PAGE_URL,
        "external_id": f"wikipedia-haunted-location:{external_slug}",
        "publicness_status": "public_wikipedia_page",
        "rights_access_status": "public_metadata_summary_only",
        "narrative_type": "ghost_legend",
        "secondary_role": "public_directory_cross_source_location_record",
        "australian_relation": "Australia section of a public Wikipedia haunted-location list.",
        "humanoid_basis": "reported_ghost_or_person_form_haunting_directory_entry",
        "source_label": "haunted_location",
        "matched_terms": "haunted;ghost",
        "matched_place": name,
        "location_text": location_text,
        "location_role": "public_directory_display_location",
        "latitude": coord.get("latitude", ""),
        "longitude": coord.get("longitude", ""),
        "location_precision": coord.get("location_precision", "") if mapped else "",
        "geocode_source": "existing_frontend_or_stage_place_catalog" if mapped else "",
        "geocode_verification_status": "reviewed_place_catalog_match" if mapped else "",
        "coordinate_evidence_note": "Coordinates reused from current stage overlay place catalog." if mapped else "",
        "duplicate_check_status": "checked_against_current_overlay_wikipedia_url_place",
        "quality_class": "B" if mapped else "C",
        "ethics_review_status": "public_directory_context_reviewed",
        "cultural_sensitivity": "low",
        "risk_flags": "",
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": "duplicate_against_current_overlay" if duplicate else "",
        "evidence_summary": entry["description"][:900],
        "raw_metadata_json": json.dumps({"page": PAGE_TITLE, "revid": revid, "entry_name": name}, ensure_ascii=False, sort_keys=True),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def write_report(path: Path, rows: list[dict[str, Any]], output: Path) -> None:
    accepted = [row for row in rows if row["candidate_status"] == "accepted"]
    mapped = [row for row in accepted if row.get("latitude") and row.get("longitude")]
    status_counts = Counter(row["candidate_status"] for row in rows)
    lines = [
        "# Wikipedia Haunted Locations Australia Crawl",
        "",
        "Stage-only crawl. These rows are public directory candidates, not production imports.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate CSV: `{output.resolve().relative_to(ROOT)}`",
        f"- Rows written: `{len(rows)}`",
        f"- Accepted candidates: `{len(accepted)}`",
        f"- Accepted with reused coordinates: `{len(mapped)}`",
        "",
        "## Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted Places"])
    for row in accepted:
        marker = "mapped" if row.get("latitude") and row.get("longitude") else "unmapped"
        lines.append(f"- {row['matched_place']}: {marker}")
    lines.extend(["", "## Notes"])
    lines.append("- Coordinates are reused only when the place already exists in the current stage overlay.")
    lines.append("- Rows are undated directory records and should not be used as annual trend evidence.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    payload = fetch_json(api_url(), args.timeout)
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    parse = payload.get("parse") if isinstance(payload.get("parse"), dict) else {}
    wikitext = ((parse.get("wikitext") or {}).get("*")) or ""
    revid = str(parse.get("revid") or "")
    entries = parse_entries(australia_section(wikitext))
    coords = coordinate_catalog(args.frontend)
    existing = existing_url_places(args.frontend)
    rows = [make_row(entry, coords, existing, revid) for entry in entries]
    write_csv(args.output, rows)
    write_report(args.report, rows, args.output)
    print(f"Wrote Wikipedia haunted locations: {args.output}")
    print(f"Rows: {len(rows)}")
    print(f"Accepted: {sum(1 for row in rows if row['candidate_status'] == 'accepted')}")
    print(f"Mapped accepted: {sum(1 for row in rows if row['candidate_status'] == 'accepted' and row.get('latitude') and row.get('longitude'))}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
