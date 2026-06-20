#!/usr/bin/env python3
"""Geocode existing source-named locations into strict map candidates.

This script upgrades only already-extracted source-named places. It does not
invent event locations from publication places or figure-associated regions.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "australian-humanoid-supernatural-texts/0.1 strict-geo-audit contact: dpan538"
CACHE_PATH = PROJECT_ROOT / "data" / "interim" / "geocode_cache" / "nominatim_location_geocodes.json"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "v2" / "strict_geocoding_report.md"

STATE_NAMES = {
    "ACT": {"australian capital territory", "act"},
    "NSW": {"new south wales", "nsw"},
    "NT": {"northern territory", "nt"},
    "QLD": {"queensland", "qld"},
    "SA": {"south australia", "sa"},
    "TAS": {"tasmania", "tas"},
    "VIC": {"victoria", "vic"},
    "WA": {"western australia", "wa"},
}

STRICT_LOCATION_TYPES = {"locality", "town", "named_feature"}
AU_BOUNDS = (-44.5, -9.0, 112.0, 154.5)


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def write_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def norm(value: Any) -> str:
    return str(value or "").strip()


def state_matches(expected: str, result: dict[str, Any]) -> bool:
    expected = norm(expected)
    if not expected:
        return True
    accepted = STATE_NAMES.get(expected, {expected.lower()})
    address = result.get("address") or {}
    values = {norm(address.get(key)).lower() for key in ("state", "state_code", "region")}
    display = norm(result.get("display_name")).lower()
    return bool(accepted & values) or any(f", {name.lower()}," in f", {display}," for name in accepted)


def in_au_bounds(latitude: float, longitude: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = AU_BOUNDS
    return min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon


def best_result(results: list[dict[str, Any]], expected_state: str) -> tuple[dict[str, Any] | None, str]:
    for result in results:
        try:
            latitude = float(result["lat"])
            longitude = float(result["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not in_au_bounds(latitude, longitude):
            continue
        if not state_matches(expected_state, result):
            continue
        result_type = norm(result.get("type")).lower()
        addresstype = norm(result.get("addresstype")).lower()
        if addresstype in {"country", "state"} or result_type in {"administrative"} and addresstype == "state":
            continue
        return result, "accepted"
    if results:
        return None, "no_result_matching_state_or_precision"
    return None, "no_result"


def geocode(query: str, cache: dict[str, Any], sleep_seconds: float) -> list[dict[str, Any]]:
    if query in cache:
        return cache[query]
    response = requests.get(
        NOMINATIM_URL,
        params={
            "q": query,
            "format": "jsonv2",
            "addressdetails": 1,
            "countrycodes": "au",
            "limit": 5,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json()
    cache[query] = results
    write_cache(cache)
    time.sleep(sleep_seconds)
    return results


def candidate_rows(conn, limit: int | None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            l.location_id,
            l.place_name,
            l.state_territory,
            l.location_type,
            l.verification_status,
            COUNT(rl.record_id) AS record_count,
            MIN(rl.record_id) AS sample_record_id
        FROM locations l
        JOIN record_locations rl ON rl.location_id = l.location_id
        WHERE COALESCE(l.latitude, '') = ''
          AND COALESCE(l.longitude, '') = ''
          AND l.verification_status = 'source_named_place_needs_geocode'
          AND l.location_type IN ('locality', 'town', 'named_feature')
        GROUP BY l.location_id
        ORDER BY record_count DESC, l.place_name
    """
    rows = [dict(row) for row in conn.execute(sql).fetchall()]
    return rows[:limit] if limit else rows


def apply_geocode(conn, row: dict[str, Any], result: dict[str, Any]) -> None:
    latitude = float(result["lat"])
    longitude = float(result["lon"])
    source_note = (
        "Nominatim/OpenStreetMap geocode; accepted only after Australia bounds "
        "and state/territory match. Human review still recommended before analysis-ready use."
    )
    conn.execute(
        """
        UPDATE locations
        SET latitude = ?,
            longitude = ?,
            location_type = CASE
                WHEN location_type IN ('locality', 'town', 'named_feature') THEN location_type
                ELSE 'locality'
            END,
            geocode_source = ?,
            verification_status = 'verified_gazetteer_point',
            notes = TRIM(COALESCE(notes, '') || CASE WHEN COALESCE(notes, '') = '' THEN '' ELSE ' | ' END || ?)
        WHERE location_id = ?
        """,
        (
            latitude,
            longitude,
            "nominatim_openstreetmap_state_matched",
            source_note,
            int(row["location_id"]),
        ),
    )


def write_report(stats: dict[str, Any], examples: list[dict[str, Any]], dry_run: bool) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Strict Geocoding Report",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Mode: `{'dry_run' if dry_run else 'apply'}`",
        f"- Queried locations: `{stats['queried']}`",
        f"- Accepted geocodes: `{stats['accepted']}`",
        f"- Rejected/no match: `{stats['rejected']}`",
        f"- Affected record-location links: `{stats['affected_records']}`",
        "",
        "## Policy",
        "",
        "Only pre-existing source-named localities are geocoded. Publication locations, country-only rows, state-only rows, broad regions, and figure-associated regions are not converted into map points.",
        "",
        "## Accepted Examples",
        "",
        "| location_id | place | state | records | latitude | longitude |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in examples[:40]:
        lines.append(
            f"| {item['location_id']} | {item['place_name']} | {item['state_territory']} | "
            f"{item['record_count']} | {item['latitude']:.6f} | {item['longitude']:.6f} |"
        )
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--limit", type=int, default=0, help="Maximum distinct locations to geocode")
    parser.add_argument("--sleep", type=float, default=1.05, help="Delay between uncached geocoding requests")
    parser.add_argument("--apply", action="store_true", help="Write accepted geocodes into locations")
    args = parser.parse_args()

    cache = load_cache()
    accepted_examples: list[dict[str, Any]] = []
    stats = {"queried": 0, "accepted": 0, "rejected": 0, "affected_records": 0}

    with connect(args.db) as conn:
        rows = candidate_rows(conn, args.limit or None)
        for row in rows:
            query = f"{row['place_name']}, Australia"
            stats["queried"] += 1
            results = geocode(query, cache, args.sleep)
            result, reason = best_result(results, norm(row["state_territory"]))
            if result is None:
                stats["rejected"] += 1
                continue
            latitude = float(result["lat"])
            longitude = float(result["lon"])
            stats["accepted"] += 1
            stats["affected_records"] += int(row["record_count"] or 0)
            accepted_examples.append(
                {
                    **row,
                    "latitude": latitude,
                    "longitude": longitude,
                    "reason": reason,
                }
            )
            if args.apply:
                apply_geocode(conn, row, result)
        if args.apply:
            conn.commit()

    write_report(stats, accepted_examples, dry_run=not args.apply)
    print(json.dumps(stats, indent=2, sort_keys=True))
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
