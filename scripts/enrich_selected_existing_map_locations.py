#!/usr/bin/env python3
"""Promote selected source-stated places on existing public records to map flags.

This is a review queue, not a crawler. Each row below was selected because the
accepted public record snippet itself names the place. The script still verifies
that source text is present, checks independent gazetteer coordinates, and skips
records that are already mapped or suppressed.
"""

from __future__ import annotations

import csv
import json
import math
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


EXPORT_CSV = ROOT / "data" / "exports" / "v2" / "selected_existing_map_enrichment.csv"
REPORT_MD = ROOT / "data" / "processed" / "v2" / "selected_existing_map_enrichment.md"
CACHE_PATH = ROOT / "data" / "interim" / "geocode_cache" / "selected_existing_map_enrichment_nominatim.json"
USER_AGENT = "AustralianHumanoidTexts/selected-map-enrichment contact: local research"

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
class ReviewedPlace:
    record_id: int
    place_name: str
    state: str
    source_text: str
    query: str
    location_type: str = "locality"
    relation_type: str = "reported_place"


REVIEWED_PLACES = [
    ReviewedPlace(646, "Braidwood, NSW", "NSW", "Braidwood, New South Wales", "Braidwood, New South Wales, Australia", "town"),
    ReviewedPlace(825, "Nanango, QLD", "QLD", "Nanango/ Queensland", "Nanango, Queensland, Australia", "town"),
    ReviewedPlace(827, "Dungay Creek, NSW", "NSW", "Dungay Creek, New South Wales", "Dungay Creek, New South Wales, Australia", "locality"),
    ReviewedPlace(828, "Kempsey, NSW", "NSW", "Kempsey, New South Wales", "Kempsey, New South Wales, Australia", "town"),
    ReviewedPlace(829, "Queanbeyan, ACT", "ACT", "Queanbeyan, A.C.T.", "Queanbeyan, Australian Capital Territory, Australia", "town"),
    ReviewedPlace(233, "Barclay's Island, NSW", "NSW", "Barclay's Island, New South Wales", "Barclays Island, New South Wales, Australia", "locality"),
    ReviewedPlace(613, "Wee Jasper, NSW", "NSW", "Between Wee Jasper and Yass", "Wee Jasper, New South Wales, Australia", "locality"),
    ReviewedPlace(301, "Mount Buffalo, VIC", "VIC", "Mt. Buffalo called Yarambulla", "Mount Buffalo, Victoria, Australia", "named_feature"),
    ReviewedPlace(836, "Mount Spurgeon, QLD", "QLD", "Mount Spurgeon, Queensland", "Mount Spurgeon, Queensland, Australia", "named_feature"),
    ReviewedPlace(249, "Blackbutt Ranges, QLD", "QLD", "Blackbutt Ranges, Queensland", "Blackbutt Range, Queensland, Australia", "named_feature"),
    ReviewedPlace(615, "Wellingrove, NSW", "NSW", "Wellingrove and Dundee, New South Wales", "Wellingrove, New South Wales, Australia", "locality"),
    ReviewedPlace(456, "Hornsby Heights, NSW", "NSW", "Hornsby Heights", "Hornsby Heights, New South Wales, Australia", "locality"),
    ReviewedPlace(138, "Parkes, NSW", "NSW", "Parkes and Central District, New South Wales", "Parkes, New South Wales, Australia", "town"),
    ReviewedPlace(381, "Miles, QLD", "QLD", "Between Chinchilla and Miles, Queensland", "Miles, Queensland, Australia", "town"),
    ReviewedPlace(429, "Atherton Tableland, QLD", "QLD", "Atherton tablelands", "Atherton Tableland, Queensland, Australia", "named_feature"),
    ReviewedPlace(3679, "Yarralumla House, ACT", "ACT", "Yarralumla House", "Yarralumla House, Canberra, Australian Capital Territory, Australia", "exact_site", "legend_associated_place"),
    ReviewedPlace(3680, "Washpen Creek, ACT", "ACT", "Washpen", "Washpen Creek, Australian Capital Territory, Australia", "named_feature", "legend_associated_place"),
    ReviewedPlace(2850, "Port Arthur Historic Site, TAS", "TAS", "Port Arthur", "Port Arthur Historic Site, Tasmania, Australia", "exact_site", "narrative_setting"),
    ReviewedPlace(647, "Mount Dryander, QLD", "QLD", "country around Mount Dryander", "Mount Dryander, Queensland, Australia", "named_feature"),
    ReviewedPlace(668, "Yorke Peninsula, SA", "SA", "Yorkes Peninsula", "Yorke Peninsula, South Australia, Australia", "named_feature"),
    ReviewedPlace(673, "Treachery Headland, NSW", "NSW", "Treachery Headland", "Treachery Headland, Seal Rocks, New South Wales, Australia", "named_feature"),
    ReviewedPlace(684, "Kanangra Falls, NSW", "NSW", "Kanangra Falls", "Kanangra Falls, New South Wales, Australia", "named_feature"),
    ReviewedPlace(700, "Blue Mountains, NSW", "NSW", "Blue Mountain district", "Blue Mountains, New South Wales, Australia", "named_feature"),
    ReviewedPlace(711, "Canberra, ACT", "ACT", "Canberra: History", "Canberra, Australian Capital Territory, Australia", "town", "legend_associated_place"),
    ReviewedPlace(841, "Adelaide River, NT", "NT", "Adelaide River", "Adelaide River, Northern Territory, Australia", "town"),
    ReviewedPlace(945, "Gold Coast, QLD", "QLD", "gold coast", "Gold Coast, Queensland, Australia", "locality"),
    ReviewedPlace(970, "Springwood, NSW", "NSW", "springwood, blue mountains", "Springwood, New South Wales, Australia", "locality"),
    ReviewedPlace(982, "Nanango, QLD", "QLD", "nanango yowie", "Nanango, Queensland, Australia", "town"),
    ReviewedPlace(1001, "Springbrook, QLD", "QLD", "springbrook yowie", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(1005, "Springbrook, QLD", "QLD", "springbrook yowie", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(1012, "Springbrook, QLD", "QLD", "springbrook yowie", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(1014, "Springbrook, QLD", "QLD", "springbrook yowie", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(1015, "Springbrook, QLD", "QLD", "springbrook yowie", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(1016, "Springbrook, QLD", "QLD", "springbrook", "Springbrook, Queensland, Australia", "locality"),
    ReviewedPlace(643, "Tooraweenah, NSW", "NSW", "Toowareenah NSW", "Tooraweenah, New South Wales, Australia", "locality"),
    ReviewedPlace(647, "Dryander National Park, QLD", "QLD", "Mount Dryander", "Dryander National Park, Queensland, Australia", "named_feature"),
    ReviewedPlace(673, "Seal Rocks, NSW", "NSW", "Treachery Headland, from Seal Rocks", "Seal Rocks, New South Wales, Australia", "locality"),
    ReviewedPlace(658, "Milburn Creek, NSW", "NSW", "Milburn Creek", "Milburn Creek, New South Wales, Australia", "named_feature"),
    ReviewedPlace(649, "Avondale, Illawarra, NSW", "NSW", "Avondale Ranges", "Avondale, Wollongong, New South Wales, Australia", "locality"),
    ReviewedPlace(1082, "Kilcoy, QLD", "QLD", "kilcoy yowie", "Kilcoy, Queensland, Australia", "town"),
    ReviewedPlace(1082, "Sandy Creek, Kilcoy, QLD", "QLD", "sandy creek", "Sandy Creek, Kilcoy, Queensland, Australia", "named_feature"),
]


def load_cache() -> dict[str, Any]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def write_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def geocode(spec: ReviewedPlace, cache: dict[str, Any], sleep_seconds: float) -> dict[str, Any] | None:
    if spec.query in cache:
        rows = cache[spec.query]
    else:
        url = "https://nominatim.openstreetmap.org/search?" + urlencode(
            {"q": spec.query, "format": "jsonv2", "limit": "5", "addressdetails": "1", "countrycodes": "au"}
        )
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=25) as response:
            rows = json.loads(response.read().decode("utf-8", "ignore"))
        cache[spec.query] = rows
        write_cache(cache)
        time.sleep(sleep_seconds)
    expected_state = STATE_NAMES[spec.state].lower()
    for row in rows:
        address = row.get("address") or {}
        display = canonicalise_whitespace(row.get("display_name") or "")
        state_values = {str(address.get(key) or "").lower() for key in ("state", "territory", "region", "ISO3166-2-lvl4")}
        if str(address.get("country_code") or "").lower() != "au":
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


def mapped_record_ids(conn) -> set[int]:
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


def upsert_link(conn, spec: ReviewedPlace, row: Any, geo: dict[str, Any]) -> dict[str, Any]:
    display = canonicalise_whitespace(geo.get("display_name") or "")
    note = (
        f"Selected existing-record map enrichment 2026-06-22; source excerpt names `{spec.source_text}`; "
        f"Nominatim display name: {display}"
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
            spec.place_name,
            spec.state,
            float(geo["lat"]),
            float(geo["lon"]),
            spec.location_type,
            "nominatim_openstreetmap_selected_existing_record_2026-06-22",
            note,
        ),
    )
    location_id = int(conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (spec.place_name,)).fetchone()["location_id"])
    evidence = canonicalise_whitespace(row["snippet"] or "")
    conn.execute(
        """
        INSERT OR REPLACE INTO record_locations (
            record_id, location_id, relation_type, evidence_text, confidence, notes
        )
        VALUES (?, ?, ?, ?, 'high', ?)
        """,
        (
            spec.record_id,
            location_id,
            spec.relation_type,
            evidence[:900],
            "Source-stated place from accepted public record snippet; state-matched independent gazetteer coordinate.",
        ),
    )
    return {
        "record_id": spec.record_id,
        "title": row["title"] or "",
        "source_name": row["source_name"] or "",
        "place_name": spec.place_name,
        "state_territory": spec.state,
        "latitude": geo["lat"],
        "longitude": geo["lon"],
        "geocode_display_name": display,
        "decision": "applied",
        "review_note": note,
    }


def main() -> None:
    cache = load_cache()
    rows_out: list[dict[str, Any]] = []
    with connect(DEFAULT_DB_PATH) as conn:
        mapped = mapped_record_ids(conn)
        for spec in REVIEWED_PLACES:
            row = conn.execute(
                """
                SELECT r.record_id, r.title, r.snippet, r.publicness_level, s.source_name,
                       c.relevance_code, c.publicness_code, c.ethics_flag
                FROM records r
                JOIN sources s ON s.source_id = r.source_id
                LEFT JOIN coding c ON c.record_id = r.record_id
                WHERE r.record_id = ?
                """,
                (spec.record_id,),
            ).fetchone()
            base = {
                "record_id": spec.record_id,
                "place_name": spec.place_name,
                "state_territory": spec.state,
                "decision": "",
                "review_note": "",
            }
            if not row:
                rows_out.append({**base, "decision": "missing_record", "review_note": "record not found"})
                continue
            if spec.record_id in mapped:
                rows_out.append({**base, "title": row["title"] or "", "source_name": row["source_name"] or "", "decision": "already_mapped", "review_note": "record already has eligible representative location"})
                continue
            if row["publicness_level"] == "restricted_excluded" or row["publicness_code"] == "restricted_excluded" or row["relevance_code"] == "scope_excluded":
                rows_out.append({**base, "title": row["title"] or "", "source_name": row["source_name"] or "", "decision": "not_public", "review_note": "record is not public eligible"})
                continue
            snippet = canonicalise_whitespace(row["snippet"] or "")
            if spec.source_text.lower() not in snippet.lower():
                rows_out.append({**base, "title": row["title"] or "", "source_name": row["source_name"] or "", "decision": "source_text_missing", "review_note": f"snippet did not contain {spec.source_text!r}"})
                continue
            geo = geocode(spec, cache, 1.5)
            if not geo:
                rows_out.append({**base, "title": row["title"] or "", "source_name": row["source_name"] or "", "decision": "geocode_rejected", "review_note": "no state-matched Australian gazetteer result"})
                continue
            rows_out.append(upsert_link(conn, spec, row, geo))
        conn.commit()

    EXPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "record_id",
        "title",
        "source_name",
        "place_name",
        "state_territory",
        "latitude",
        "longitude",
        "geocode_display_name",
        "decision",
        "review_note",
    ]
    with EXPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows_out:
            writer.writerow({field: row.get(field, "") for field in fields})

    counts: dict[str, int] = {}
    by_state: dict[str, int] = {}
    for row in rows_out:
        counts[row["decision"]] = counts.get(row["decision"], 0) + 1
        if row["decision"] == "applied":
            by_state[row["state_territory"]] = by_state.get(row["state_territory"], 0) + 1
    lines = [
        "# Selected Existing Map Enrichment",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Reviewed rows: `{len(rows_out)}`",
        f"- Applied map links: `{counts.get('applied', 0)}`",
        f"- Already mapped: `{counts.get('already_mapped', 0)}`",
        f"- Geocode rejected: `{counts.get('geocode_rejected', 0)}`",
        f"- CSV: `{EXPORT_CSV.relative_to(ROOT)}`",
        "",
        "## Applied by Jurisdiction",
    ]
    for state, count in sorted(by_state.items()):
        lines.append(f"- {state}: {count}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"reviewed": len(rows_out), **counts, "applied_by_state": by_state}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
