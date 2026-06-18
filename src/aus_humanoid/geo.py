"""Conservative location extraction and storage helpers."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable

from .normalise import normalise_text


@dataclass(frozen=True)
class GazetteerEntry:
    place_name: str
    region: str | None
    state_territory: str | None
    country: str
    latitude: float | None
    longitude: float | None
    location_type: str
    geocode_source: str
    verification_status: str
    aliases: tuple[str, ...]
    notes: str = ""


GAZETTEER: tuple[GazetteerEntry, ...] = (
    GazetteerEntry(
        place_name="Australia",
        region=None,
        state_territory=None,
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="country",
        geocode_source="manual_project_scope",
        verification_status="verified_country_scope",
        aliases=("Australia", "Australian"),
    ),
    GazetteerEntry(
        place_name="Outback",
        region="Outback",
        state_territory=None,
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="broad_region",
        geocode_source="manual_region_label",
        verification_status="broad_region_only",
        aliases=("Outback",),
    ),
    GazetteerEntry(
        place_name="Southeastern Australia",
        region="Southeastern Australia",
        state_territory=None,
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="broad_region",
        geocode_source="manual_region_label",
        verification_status="broad_region_only",
        aliases=("Southeastern Australia", "South-eastern Australia", "South eastern Australia"),
    ),
    GazetteerEntry(
        place_name="Great Dividing Range",
        region="Great Dividing Range",
        state_territory=None,
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="broad_region",
        geocode_source="manual_region_label",
        verification_status="broad_region_only",
        aliases=("Great Dividing Range",),
    ),
    GazetteerEntry(
        place_name="Northern Territory",
        region="Northern Territory",
        state_territory="NT",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Northern Territory",),
    ),
    GazetteerEntry(
        place_name="Australian Capital Territory",
        region="Australian Capital Territory",
        state_territory="ACT",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Australian Capital Territory", "ACT"),
    ),
    GazetteerEntry(
        place_name="South Australia",
        region="South Australia",
        state_territory="SA",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("South Australia",),
    ),
    GazetteerEntry(
        place_name="Western Australia",
        region="Western Australia",
        state_territory="WA",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Western Australia",),
    ),
    GazetteerEntry(
        place_name="New South Wales",
        region="New South Wales",
        state_territory="NSW",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("New South Wales", "NSW"),
    ),
    GazetteerEntry(
        place_name="Queensland",
        region="Queensland",
        state_territory="QLD",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Queensland", "QLD"),
    ),
    GazetteerEntry(
        place_name="Victoria",
        region="Victoria",
        state_territory="VIC",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Victoria",),
    ),
    GazetteerEntry(
        place_name="Kilcoy",
        region="Somerset Region",
        state_territory="QLD",
        country="Australia",
        latitude=-26.943,
        longitude=152.565,
        location_type="town",
        geocode_source="manual_gazetteer_wikipedia_crosscheck",
        verification_status="verified_place",
        aliases=("Kilcoy", "Kilcoy, Queensland"),
    ),
    GazetteerEntry(
        place_name="Batemans Bay",
        region="South Coast",
        state_territory="NSW",
        country="Australia",
        latitude=-35.708,
        longitude=150.175,
        location_type="town",
        geocode_source="manual_gazetteer_wikipedia_crosscheck",
        verification_status="verified_place",
        aliases=("Batemans Bay",),
    ),
    GazetteerEntry(
        place_name="Ulladulla",
        region="South Coast",
        state_territory="NSW",
        country="Australia",
        latitude=-35.356,
        longitude=150.472,
        location_type="town",
        geocode_source="manual_gazetteer_wikipedia_crosscheck",
        verification_status="verified_place",
        aliases=("Ulladulla",),
    ),
    GazetteerEntry(
        place_name="Springbrook",
        region="Gold Coast hinterland",
        state_territory="QLD",
        country="Australia",
        latitude=-28.191,
        longitude=153.266,
        location_type="locality",
        geocode_source="manual_gazetteer_wikipedia_crosscheck",
        verification_status="verified_place",
        aliases=("Springbrook", "Springbrook, Queensland"),
    ),
    GazetteerEntry(
        place_name="Mulgowie",
        region="Lockyer Valley",
        state_territory="QLD",
        country="Australia",
        latitude=-27.735,
        longitude=152.374,
        location_type="locality",
        geocode_source="manual_gazetteer_wikipedia_crosscheck",
        verification_status="verified_place",
        aliases=("Mulgowie",),
    ),
    GazetteerEntry(
        place_name="Cape York Peninsula",
        region="Far North Queensland",
        state_territory="QLD",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="broad_region",
        geocode_source="manual_region_label",
        verification_status="broad_region_only",
        aliases=("Cape York", "Cape York Peninsula"),
    ),
    GazetteerEntry(
        place_name="Tasmania",
        region="Tasmania",
        state_territory="TAS",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="state_or_territory",
        geocode_source="manual_state_label",
        verification_status="verified_region",
        aliases=("Tasmania",),
    ),
    GazetteerEntry(
        place_name="Milburn Creek",
        region=None,
        state_territory="NSW",
        country="Australia",
        latitude=None,
        longitude=None,
        location_type="locality_or_article_title",
        geocode_source="manual_uncertain",
        verification_status="needs_review",
        aliases=("Milburn Creek",),
        notes="Article title/source lead; coordinates not asserted in V1.",
    ),
)


def seed_locations(conn: sqlite3.Connection) -> int:
    count = 0
    for entry in GAZETTEER:
        conn.execute(
            """
            INSERT INTO locations (
                place_name, region, state_territory, country, latitude, longitude,
                location_type, geocode_source, verification_status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (
                entry.place_name,
                entry.region,
                entry.state_territory,
                entry.country,
                entry.latitude,
                entry.longitude,
                entry.location_type,
                entry.geocode_source,
                entry.verification_status,
                entry.notes,
            ),
        )
        count += 1
    return count


def find_location_id(conn: sqlite3.Connection, place_name: str) -> int:
    row = conn.execute(
        "SELECT location_id FROM locations WHERE place_name = ?",
        (place_name,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Location not seeded: {place_name}")
    return int(row["location_id"])


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)


def location_matches(text: str) -> list[tuple[GazetteerEntry, str]]:
    matches: list[tuple[GazetteerEntry, str]] = []
    seen: set[str] = set()
    for entry in sorted(GAZETTEER, key=lambda item: max(len(a) for a in item.aliases), reverse=True):
        for alias in entry.aliases:
            found = _alias_pattern(alias).search(text)
            if found and entry.place_name not in seen:
                evidence = text[max(0, found.start() - 90) : min(len(text), found.end() + 90)]
                matches.append((entry, " ".join(evidence.split())))
                seen.add(entry.place_name)
                break
    return matches


def assign_locations_for_record(
    conn: sqlite3.Connection,
    record_id: int,
    text: str,
    relation_type: str = "mentioned_place",
    confidence: str = "medium",
) -> int:
    seed_locations(conn)
    count = 0
    for entry, evidence in location_matches(text):
        location_id = find_location_id(conn, entry.place_name)
        conn.execute(
            """
            INSERT OR REPLACE INTO record_locations (
                record_id, location_id, relation_type, evidence_text, confidence, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record_id,
                location_id,
                relation_type,
                evidence,
                confidence if entry.verification_status != "needs_review" else "low",
                "Rule-based place extraction; human review recommended.",
            ),
        )
        count += 1
    return count


def location_summary(conn: sqlite3.Connection, record_id: int) -> str:
    rows = conn.execute(
        """
        SELECT l.place_name, l.state_territory, l.region, rl.confidence
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE rl.record_id = ?
        ORDER BY l.place_name
        """,
        (record_id,),
    ).fetchall()
    parts = []
    for row in rows:
        qualifier = row["state_territory"] or row["region"] or ""
        label = row["place_name"] + (f" ({qualifier})" if qualifier else "")
        parts.append(f"{label}: {row['confidence']}")
    return "; ".join(parts)

