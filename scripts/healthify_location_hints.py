#!/usr/bin/env python3
"""Attach curated place hints to legacy records and resolve precise coordinates.

This script is intentionally conservative:
- it only uses manually curated place aliases from a YAML hint file;
- it never treats publication mastheads or state-only labels as strict map points;
- it rate-limits public geocoding and caches results for reproducibility;
- it can run in dry-run mode before writing any database rows.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_HINTS = PROJECT_ROOT / "config" / "ayr_location_health_hints.yml"
DEFAULT_CACHE = PROJECT_ROOT / "data" / "interim" / "location_geocode_cache.json"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "location_health_hints_20260621.md"

STATE_NAMES = {
    "WA": "Western Australia",
    "NT": "Northern Territory",
    "SA": "South Australia",
    "QLD": "Queensland",
    "NSW": "New South Wales",
    "VIC": "Victoria",
    "TAS": "Tasmania",
    "ACT": "Australian Capital Territory",
}

LOW_COVERAGE_STATES = {"WA", "NT", "SA", "TAS", "VIC", "ACT"}

USER_AGENT = (
    "AustralianHumanoidArchive/0.3 "
    "(public research; https://github.com/dpan538/australian-humanoid-supernatural-texts)"
)


@dataclass(frozen=True)
class PlaceHint:
    place_name: str
    state_territory: str
    aliases: tuple[str, ...]
    source: str = "curated_hint"


def load_hints(path: Path) -> list[PlaceHint]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    hints = []
    for row in data.get("places", []):
        place = canonicalise_whitespace(row.get("place_name"))
        state = canonicalise_whitespace(row.get("state_territory")).upper()
        aliases = tuple(canonicalise_whitespace(alias) for alias in row.get("aliases", []) if canonicalise_whitespace(alias))
        if place and state in STATE_NAMES and aliases:
            hints.append(PlaceHint(place, state, aliases))
    return hints


TITLE_PLACE_PATTERNS = (
    re.compile(
        r"^(?P<place>[A-Za-z][A-Za-z0-9'&./ -]{2,80}?),\s*"
        r"(?P<state>Victoria|Western Australia|South Australia|Northern Territory|Tasmania|Australian Capital Territory|New South Wales|Queensland)\s+"
        r"(?P<year>\d{4})$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?P<place>[A-Za-z][A-Za-z0-9'&./ -]{2,80}?),\s*"
        r"(?P<state>VIC|WA|SA|NT|TAS|ACT|NSW|QLD)\s+"
        r"(?P<year>\d{4})$",
        re.IGNORECASE,
    ),
)

STATE_VALUE_TO_CODE = {value.upper(): key for key, value in STATE_NAMES.items()}
STATE_VALUE_TO_CODE.update({key: key for key in STATE_NAMES})


def title_place_hint(title: str) -> PlaceHint | None:
    clean = canonicalise_whitespace(title)
    for pattern in TITLE_PLACE_PATTERNS:
        match = pattern.search(clean)
        if not match:
            continue
        place = canonicalise_whitespace(match.group("place"))
        state = STATE_VALUE_TO_CODE.get(match.group("state").upper())
        if not state:
            continue
        if any(token in place.lower() for token in ("article", "magazine", "news", "yowie article", "source unknown")):
            continue
        return PlaceHint(place, state, (place,), "title_place_pattern")
    return None


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def evidence_window(text: str, match: re.Match[str]) -> str:
    return canonicalise_whitespace(text[max(0, match.start() - 90) : min(len(text), match.end() + 90)])


def safe_text(row: Any) -> str:
    return "\n".join(
        part
        for part in [
            row["title"] or "",
            row["snippet"] or "",
            row["publication"] or "",
            row["url"] or "",
        ]
        if part
    )


def has_strict_location(conn, record_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE rl.record_id = ?
          AND l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
        LIMIT 1
        """,
        (record_id,),
    ).fetchone()
    return row is not None


def find_hint_matches(text: str, hints: list[PlaceHint], states: set[str] | None) -> list[tuple[PlaceHint, str]]:
    matches = []
    for hint in hints:
        if states and hint.state_territory not in states:
            continue
        for alias in hint.aliases:
            found = alias_pattern(alias).search(text)
            if found:
                matches.append((hint, evidence_window(text, found)))
                break
    return matches


def record_matches(
    row: Any,
    hints: list[PlaceHint],
    states: set[str] | None,
    infer_title_places: bool,
    title_place_only: bool,
) -> list[tuple[PlaceHint, str]]:
    text = safe_text(row)
    matches = [] if title_place_only else find_hint_matches(text, hints, states)
    if infer_title_places:
        title_hint = title_place_hint(row["title"] or "")
        if title_hint and (not states or title_hint.state_territory in states):
            evidence = canonicalise_whitespace(row["title"] or "")
            existing_keys = {(hint.place_name.lower(), hint.state_territory) for hint, _ in matches}
            if (title_hint.place_name.lower(), title_hint.state_territory) not in existing_keys:
                matches.insert(0, (title_hint, evidence))
    return matches


def geocode_hint(hint: PlaceHint, cache: dict[str, Any], no_network: bool, rate_limit: float) -> dict[str, Any] | None:
    key = f"{hint.place_name}|{hint.state_territory}"
    cached = cache.get(key)
    if cached:
        return cached if cached.get("ok") else None
    if no_network:
        return None

    query = f"{hint.place_name}, {STATE_NAMES[hint.state_territory]}, Australia"
    response = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "jsonv2", "limit": 5, "countrycodes": "au"},
        headers={"User-Agent": USER_AGENT},
        timeout=25,
    )
    response.raise_for_status()
    rows = response.json()
    state_name = STATE_NAMES[hint.state_territory].lower()
    selected = None
    for item in rows:
        display = str(item.get("display_name") or "").lower()
        if "australia" in display and state_name in display:
            selected = item
            break
    if selected is None and rows:
        selected = rows[0]

    if not selected:
        cache[key] = {"ok": False, "query": query, "generated_at": utc_now_iso()}
        time.sleep(rate_limit)
        return None

    result = {
        "ok": True,
        "query": query,
        "lat": float(selected["lat"]),
        "lon": float(selected["lon"]),
        "display_name": selected.get("display_name", ""),
        "class": selected.get("class", ""),
        "type": selected.get("type", ""),
        "generated_at": utc_now_iso(),
    }
    cache[key] = result
    time.sleep(rate_limit)
    return result


def upsert_location(conn, hint: PlaceHint, geocode: dict[str, Any]) -> int:
    conn.execute(
        """
        INSERT INTO locations (
            place_name, region, state_territory, country, latitude, longitude,
            location_type, geocode_source, verification_status, notes
        ) VALUES (?, ?, ?, 'Australia', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(place_name) DO UPDATE SET
            state_territory=excluded.state_territory,
            latitude=COALESCE(locations.latitude, excluded.latitude),
            longitude=COALESCE(locations.longitude, excluded.longitude),
            location_type=CASE
                WHEN locations.latitude IS NULL OR locations.longitude IS NULL THEN excluded.location_type
                ELSE locations.location_type
            END,
            geocode_source=CASE
                WHEN locations.latitude IS NULL OR locations.longitude IS NULL THEN excluded.geocode_source
                ELSE locations.geocode_source
            END,
            verification_status=CASE
                WHEN locations.latitude IS NULL OR locations.longitude IS NULL THEN excluded.verification_status
                ELSE locations.verification_status
            END,
            notes=CASE
                WHEN locations.notes IS NULL OR locations.notes = '' THEN excluded.notes
                ELSE locations.notes
            END
        """,
        (
            hint.place_name,
            STATE_NAMES[hint.state_territory],
            hint.state_territory,
            geocode["lat"],
            geocode["lon"],
            "locality",
            "nominatim_openstreetmap_from_curated_place_hint",
            "verified_gazetteer_point",
            f"Resolved from curated location-health hint. Nominatim display name: {geocode.get('display_name', '')}",
        ),
    )
    row = conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (hint.place_name,)).fetchone()
    if row is None:
        raise RuntimeError(f"Location insert failed for {hint.place_name}")
    return int(row["location_id"])


def attach_record_location(conn, record_id: int, location_id: int, evidence: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO record_locations (
            record_id, location_id, relation_type, evidence_text, confidence, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            record_id,
            location_id,
            "source_visible_place",
            evidence,
            "medium",
            "Curated place-hint health pass; source-visible place text matched record title/snippet/url. Not a publication-location inference.",
        ),
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    hints = load_hints(Path(args.hints))
    states = {state.strip().upper() for state in args.states.split(",") if state.strip()} if args.states else None
    cache = load_cache(Path(args.cache))
    stats = {
        "records_examined": 0,
        "records_with_hint_match": 0,
        "geocoded_places": 0,
        "attached_locations": 0,
        "skipped_existing_strict": 0,
        "skipped_ungeocoded": 0,
    }
    examples = []
    with connect(args.db) as conn:
        rows = conn.execute(
            """
            SELECT r.record_id, r.title, r.publication, r.snippet, r.url, r.year
            FROM records r
            ORDER BY r.record_id
            """
        ).fetchall()
        for row in rows:
            record_id = int(row["record_id"])
            stats["records_examined"] += 1
            if has_strict_location(conn, record_id):
                stats["skipped_existing_strict"] += 1
                continue
            matches = record_matches(row, hints, states, args.infer_title_places, args.title_place_only)
            if not matches:
                continue
            stats["records_with_hint_match"] += 1
            for hint, evidence in matches[: args.max_matches_per_record]:
                geocode = geocode_hint(hint, cache, args.no_network, args.rate_limit_seconds)
                if not geocode:
                    stats["skipped_ungeocoded"] += 1
                    continue
                stats["geocoded_places"] += 1
                if not args.dry_run:
                    location_id = upsert_location(conn, hint, geocode)
                    attach_record_location(conn, record_id, location_id, evidence)
                stats["attached_locations"] += 1
                if len(examples) < 16:
                    examples.append(
                        {
                            "record_id": record_id,
                            "year": row["year"],
                            "title": row["title"],
                            "place": hint.place_name,
                            "state": hint.state_territory,
                            "lat": geocode["lat"],
                            "lon": geocode["lon"],
                            "source": hint.source,
                        }
                    )
        if not args.dry_run:
            conn.commit()
    save_cache(Path(args.cache), cache)
    return {"stats": stats, "examples": examples, "states": sorted(states) if states else "all"}


def write_report(path: Path, result: dict[str, Any], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Location Health Hint Pass",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Hints: `{args.hints}`",
        f"- Dry run: `{args.dry_run}`",
        f"- Network geocoding disabled: `{args.no_network}`",
        f"- States: `{result['states']}`",
        "",
        "## Counts",
    ]
    for key, value in result["stats"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Example Attachments"])
    for item in result["examples"]:
        lines.append(
            f"- record `{item['record_id']}` ({item['year']}): {item['place']}, {item['state']} "
            f"({item['lat']:.5f}, {item['lon']:.5f}) [{item['source']}] -- {item['title']}"
        )
    lines.extend(
        [
            "",
            "## Policy",
            "- Only curated source-visible place aliases are used.",
            "- State-only, country-only, publication-location, and tourism-only signals are not promoted to strict map points by this script.",
            "- Coordinate resolution uses cached Nominatim/OpenStreetMap results with a project User-Agent and rate limit.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--hints", default=str(DEFAULT_HINTS))
    parser.add_argument("--cache", default=str(DEFAULT_CACHE))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--states", default="", help="Comma-separated state filter, e.g. WA,NT,SA,TAS,VIC,ACT")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--rate-limit-seconds", type=float, default=1.1)
    parser.add_argument("--max-matches-per-record", type=int, default=1)
    parser.add_argument("--infer-title-places", action="store_true", help="Also use strict 'Place, State YYYY' titles as source-visible place hints.")
    parser.add_argument("--title-place-only", action="store_true", help="Ignore curated aliases and only attach strict 'Place, State YYYY' title matches.")
    args = parser.parse_args()
    result = run(args)
    write_report(Path(args.report), result, args)
    print(json.dumps(result["stats"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
