#!/usr/bin/env python3
"""Add verified representative map locations from source-stated record excerpts.

This is a map-enrichment lane, not a general geocoder. It only links an existing
public record to a place when the place name appears in that record's evidence
excerpt and the place resolves to the expected Australian jurisdiction.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import utc_now_iso


EXPORT_CSV = ROOT / "data" / "exports" / "v2" / "record_location_enrichment_20260622.csv"
REPORT_MD = ROOT / "data" / "processed" / "v2" / "record_location_enrichment_20260622.md"
CACHE_PATH = ROOT / "data" / "interim" / "geocode_cache" / "record_location_enrichment_nominatim.json"
USER_AGENT = "AustralianHumanoidTexts/map-enrichment contact: local research"

STATE_NAMES = {
    "ACT": "Australian Capital Territory",
    "NSW": "New South Wales",
    "NT": "Northern Territory",
    "QLD": "Queensland",
    "SA": "South Australia",
    "TAS": "Tasmania",
    "VIC": "Victoria",
    "WA": "Western Australia",
}


@dataclass(frozen=True)
class PlaceSpec:
    name: str
    state: str
    location_type: str
    query: str | None = None

    @property
    def display_name(self) -> str:
        return f"{self.name}, {self.state}"

    @property
    def geocode_query(self) -> str:
        return self.query or f"{self.name}, {STATE_NAMES[self.state]}, Australia"


PLACE_CATALOG = [
    PlaceSpec("Moreton Bay", "QLD", "named_feature"),
    PlaceSpec("Blue Mountains", "NSW", "named_feature"),
    PlaceSpec("Newcastle", "NSW", "town"),
    PlaceSpec("Wollongong", "NSW", "town"),
    PlaceSpec("Illawarra", "NSW", "locality"),
    PlaceSpec("Bathurst", "NSW", "town"),
    PlaceSpec("Goulburn", "NSW", "town"),
    PlaceSpec("Bendigo", "VIC", "town"),
    PlaceSpec("Ballarat", "VIC", "town"),
    PlaceSpec("Port Phillip", "VIC", "named_feature"),
    PlaceSpec("Mount Gambier", "SA", "town"),
    PlaceSpec("Port Lincoln", "SA", "town"),
    PlaceSpec("Lake Eyre", "SA", "named_feature", "Kati Thanda-Lake Eyre, South Australia, Australia"),
    PlaceSpec("Swan River", "WA", "named_feature"),
    PlaceSpec("Perth", "WA", "town"),
    PlaceSpec("Fremantle", "WA", "town"),
    PlaceSpec("Alice Springs", "NT", "town"),
    PlaceSpec("Finke River", "NT", "named_feature"),
    PlaceSpec("Roper River", "NT", "named_feature"),
    PlaceSpec("Hobart", "TAS", "town"),
    PlaceSpec("Launceston", "TAS", "town"),
    PlaceSpec("Derwent River", "TAS", "named_feature"),
]

SUPERNATURAL_RE = re.compile(
    r"\b(ghosts?|spirits?|devil|devil-devil|supernatural|witch|wizard|magic man|medicine man|"
    r"apparition|phantom|giants?|baiame|byamee|daramulun|bunjil|mura-mura|iruntarinia|"
    r"oruncha|turramullun|evil spirit|demon)\b",
    re.I,
)
SKIP_EXCERPT_RE = re.compile(
    r"(\*\*\* start|ebook|printed by|published by|st\. james|gazette|preface|index|"
    r"public internet archive item metadata/title|public openalex|public crossref|location cue|"
    r"publication/source)",
    re.I,
)
SKIP_ETHICS_RE = re.compile(r"(caution|sensitive|restricted|suppress)", re.I)


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def write_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def http_json(url: str) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def geocode_place(spec: PlaceSpec, cache: dict[str, Any], sleep: float) -> dict[str, Any] | None:
    if spec.geocode_query in cache:
        rows = cache[spec.geocode_query]
    else:
        url = "https://nominatim.openstreetmap.org/search?" + urlencode(
            {
                "q": spec.geocode_query,
                "format": "jsonv2",
                "addressdetails": "1",
                "countrycodes": "au",
                "limit": "5",
            }
        )
        rows = http_json(url)
        cache[spec.geocode_query] = rows
        write_cache(cache)
        time.sleep(sleep)
    expected_state = STATE_NAMES[spec.state].lower()
    for row in rows:
        address = row.get("address") or {}
        display = canonicalise_whitespace(row.get("display_name") or "")
        state_values = {
            str(address.get(key) or "").lower()
            for key in ("state", "territory", "region", "ISO3166-2-lvl4")
        }
        if address.get("country_code", "").lower() != "au":
            continue
        if expected_state not in state_values and expected_state not in display.lower() and f"au-{spec.state.lower()}" not in state_values:
            continue
        try:
            float(row["lat"])
            float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        return row
    return None


def existing_mapped_record_ids(conn) -> set[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT rl.record_id
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
          AND l.location_type IN ('exact_site', 'precise_point', 'road_segment', 'named_feature', 'locality', 'town')
          AND l.verification_status IN ('verified_place', 'verified_locality', 'verified_gazetteer_point', 'verified_institutional_coordinate')
          AND rl.relation_type NOT IN ('publication_location', 'source_collection_location')
        """
    ).fetchall()
    return {int(row["record_id"]) for row in rows}


def evidence_window(text: str, place: str, radius: int = 360) -> str:
    match = re.search(r"\b" + re.escape(place) + r"\b", text, re.I)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return canonicalise_whitespace(text[start:end])


def candidate_rows(conn) -> list[dict[str, Any]]:
    mapped = existing_mapped_record_ids(conn)
    rows = conn.execute(
        """
        SELECT r.record_id, r.title, r.snippet, r.url, s.source_name, s.source_type,
               c.ontology_code, c.ethics_flag
        FROM records r
        JOIN coding c ON c.record_id = r.record_id
        JOIN sources s ON s.source_id = r.source_id
        WHERE COALESCE(c.relevance_code, '') != 'scope_excluded'
          AND COALESCE(r.publicness_level, '') != 'restricted_excluded'
          AND s.source_name IN ('Internet Archive', 'Project Gutenberg Australia', 'Project Gutenberg', 'Internet Sacred Text Archive')
        ORDER BY r.record_id
        """
    ).fetchall()
    output: list[dict[str, Any]] = []
    seen_records: set[int] = set()
    for row in rows:
        record_id = int(row["record_id"])
        if record_id in mapped or record_id in seen_records:
            continue
        excerpt = canonicalise_whitespace(row["snippet"] or "")
        if not excerpt or SKIP_EXCERPT_RE.search(excerpt) or SKIP_ETHICS_RE.search(row["ethics_flag"] or ""):
            continue
        for spec in PLACE_CATALOG:
            if not re.search(r"\b" + re.escape(spec.name) + r"\b", excerpt, re.I):
                continue
            window = evidence_window(excerpt, spec.name)
            if not SUPERNATURAL_RE.search(window):
                continue
            output.append(
                {
                    "record_id": record_id,
                    "title": row["title"],
                    "source_name": row["source_name"],
                    "source_type": row["source_type"],
                    "ontology_code": row["ontology_code"],
                    "place_name": spec.display_name,
                    "source_place_text": spec.name,
                    "state_territory": spec.state,
                    "location_type": spec.location_type,
                    "evidence_text": window,
                    "url": row["url"],
                }
            )
            seen_records.add(record_id)
            break
    return output


def upsert_location(conn, row: dict[str, Any], geocode: dict[str, Any]) -> int:
    note = (
        f"Record-location enrichment 2026-06-22; source excerpt names `{row['source_place_text']}`; "
        f"Nominatim display name: {canonicalise_whitespace(geocode.get('display_name') or '')}"
    )
    conn.execute(
        """
        INSERT INTO locations (
            place_name, state_territory, country, latitude, longitude, location_type,
            geocode_source, verification_status, notes
        )
        VALUES (?, ?, 'Australia', ?, ?, ?, ?, 'verified_gazetteer_point', ?)
        ON CONFLICT(place_name) DO UPDATE SET
            state_territory = excluded.state_territory,
            country = 'Australia',
            latitude = excluded.latitude,
            longitude = excluded.longitude,
            location_type = excluded.location_type,
            geocode_source = excluded.geocode_source,
            verification_status = excluded.verification_status,
            notes = TRIM(COALESCE(locations.notes, '') || char(10) || excluded.notes)
        """,
        (
            row["place_name"],
            row["state_territory"],
            float(geocode["lat"]),
            float(geocode["lon"]),
            row["location_type"],
            "nominatim_openstreetmap_record_evidence_2026-06-22",
            note,
        ),
    )
    location = conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (row["place_name"],)).fetchone()
    return int(location["location_id"])


def apply_links(conn, rows: list[dict[str, Any]], geocodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    applied: list[dict[str, Any]] = []
    for row in rows:
        geocode = geocodes.get(row["place_name"])
        if not geocode:
            row["decision"] = "geocode_rejected"
            applied.append(row)
            continue
        location_id = upsert_location(conn, row, geocode)
        conn.execute(
            """
            INSERT OR REPLACE INTO record_locations (
                record_id, location_id, relation_type, evidence_text, confidence, notes
            )
            VALUES (?, ?, 'narrative_setting', ?, 'high', ?)
            """,
            (
                row["record_id"],
                location_id,
                row["evidence_text"],
                "Source-stated place extracted from accepted public record excerpt; state-matched independent gazetteer coordinate.",
            ),
        )
        row["latitude"] = geocode["lat"]
        row["longitude"] = geocode["lon"]
        row["geocode_display_name"] = canonicalise_whitespace(geocode.get("display_name") or "")
        row["decision"] = "applied"
        applied.append(row)
    conn.commit()
    return applied


def write_outputs(rows: list[dict[str, Any]], dry_run: bool) -> None:
    EXPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "record_id",
        "title",
        "source_name",
        "source_type",
        "ontology_code",
        "place_name",
        "source_place_text",
        "state_territory",
        "location_type",
        "latitude",
        "longitude",
        "decision",
        "geocode_display_name",
        "url",
        "evidence_text",
    ]
    with EXPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.get("decision", "candidate")] = counts.get(row.get("decision", "candidate"), 0) + 1
    by_state: dict[str, int] = {}
    for row in rows:
        if row.get("decision") == "applied":
            by_state[row["state_territory"]] = by_state.get(row["state_territory"], 0) + 1
    lines = [
        "# Record Location Enrichment",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Mode: `{'dry_run' if dry_run else 'apply'}`",
        f"- Rows reviewed: `{len(rows)}`",
        f"- Applied map links: `{counts.get('applied', 0)}`",
        f"- Geocode rejected: `{counts.get('geocode_rejected', 0)}`",
        f"- CSV: `{EXPORT_CSV.relative_to(ROOT)}`",
        "",
        "## Applied by Jurisdiction",
    ]
    for state, count in sorted(by_state.items()):
        lines.append(f"- {state}: {count}")
    lines.extend(["", "## Policy", "", "Rows are linked only when the accepted record evidence excerpt itself names the place and the independent gazetteer result matches the expected Australian jurisdiction. Caution or sensitive ethics rows are excluded from automatic mapping."])
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply verified links to the canonical database")
    parser.add_argument("--limit", type=int, default=0, help="Limit candidate records")
    parser.add_argument("--sleep", type=float, default=1.0, help="Delay between uncached geocoding requests")
    args = parser.parse_args()

    cache = load_cache()
    with connect(DEFAULT_DB_PATH) as conn:
        rows = candidate_rows(conn)
        if args.limit:
            rows = rows[: args.limit]
        geocodes: dict[str, dict[str, Any]] = {}
        for row in rows:
            spec = next(spec for spec in PLACE_CATALOG if spec.display_name == row["place_name"])
            geocode = geocode_place(spec, cache, args.sleep)
            if geocode:
                geocodes[row["place_name"]] = geocode
        if args.apply:
            rows = apply_links(conn, rows, geocodes)
        else:
            for row in rows:
                geocode = geocodes.get(row["place_name"])
                row["decision"] = "would_apply" if geocode else "geocode_rejected"
                if geocode:
                    row["latitude"] = geocode["lat"]
                    row["longitude"] = geocode["lon"]
                    row["geocode_display_name"] = canonicalise_whitespace(geocode.get("display_name") or "")
    write_outputs(rows, dry_run=not args.apply)
    print(json.dumps({"rows": len(rows), "applied": sum(1 for row in rows if row.get("decision") == "applied"), "would_apply": sum(1 for row in rows if row.get("decision") == "would_apply"), "geocode_rejected": sum(1 for row in rows if row.get("decision") == "geocode_rejected")}, indent=2, sort_keys=True))
    print(f"CSV: {EXPORT_CSV}")
    print(f"Report: {REPORT_MD}")


if __name__ == "__main__":
    main()
