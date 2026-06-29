#!/usr/bin/env python3
"""Repair or suppress ABC known-site records after route-level sample review."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import utc_now_iso

EXPORT_CSV = ROOT / "data" / "exports" / "v2" / "abc_known_site_location_repair.csv"
REPORT_MD = ROOT / "data" / "processed" / "v2" / "abc_known_site_location_repair.md"

BEECHWORTH = {
    "place_name": "Beechworth Asylum, VIC",
    "state_territory": "VIC",
    "latitude": -36.35165,
    "longitude": 146.69093,
    "location_type": "exact_site",
    "geocode_source": "nominatim_openstreetmap_state_checked_abc_place_2026-06-22",
    "verification_status": "verified_gazetteer_point",
}

SUPPRESS = {
    3995: "duplicate full-program instance of the same Beechworth dark-tourism segment; segment record retained separately",
    3996: "duplicate full-program instance of the same Beechworth dark-tourism segment; segment record retained separately",
}


def upsert_beechworth(conn) -> int:
    conn.execute(
        """
        INSERT INTO locations(place_name, state_territory, country, latitude, longitude, location_type, geocode_source, verification_status, notes)
        VALUES (?, ?, 'Australia', ?, ?, ?, ?, ?, ?)
        ON CONFLICT(place_name) DO UPDATE SET
            state_territory=excluded.state_territory,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            location_type=excluded.location_type,
            geocode_source=excluded.geocode_source,
            verification_status=excluded.verification_status,
            notes=TRIM(COALESCE(locations.notes, '') || char(10) || excluded.notes)
        """,
        (
            BEECHWORTH["place_name"],
            BEECHWORTH["state_territory"],
            BEECHWORTH["latitude"],
            BEECHWORTH["longitude"],
            BEECHWORTH["location_type"],
            BEECHWORTH["geocode_source"],
            BEECHWORTH["verification_status"],
            "ABC known-site sample repair 2026-06-22; source excerpt names Beechworth and Mayday Hills/Asylum ghost tour segment.",
        ),
    )
    return int(conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (BEECHWORTH["place_name"],)).fetchone()[0])


def main() -> None:
    now = utc_now_iso()
    rows: list[dict[str, str]] = []
    with connect(DEFAULT_DB_PATH) as conn:
        beechworth_id = upsert_beechworth(conn)
        conn.execute("DELETE FROM record_locations WHERE record_id = ?", (3994,))
        conn.execute(
            """
            INSERT OR REPLACE INTO record_locations(record_id, location_id, relation_type, evidence_text, confidence, notes)
            VALUES (?, ?, 'legend_associated_place', ?, 'high', ?)
            """,
            (
                3994,
                beechworth_id,
                "ABC segment states a ghost tour operator in historic Beechworth and describes the Mayday Hills/Asylum site and reported ghosts.",
                "Repaired from broad Port Arthur transcript match to source-stated Beechworth site after route sample review.",
            ),
        )
        rows.append({"record_id": "3994", "decision": "location_repaired", "review_note": "Representative place changed to Beechworth Asylum, VIC."})
        for record_id, note in SUPPRESS.items():
            conn.execute(
                """
                UPDATE coding
                SET relevance_code = 'scope_excluded',
                    notes = TRIM(COALESCE(notes, '') || char(10) || ?),
                    coded_at = ?
                WHERE record_id = ?
                """,
                (f"ABC known-site location repair 2026-06-22: {note}", now, record_id),
            )
            rows.append({"record_id": str(record_id), "decision": "scope_excluded_duplicate", "review_note": note})
        conn.commit()

    EXPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with EXPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["record_id", "decision", "review_note"])
        writer.writeheader()
        writer.writerows(rows)

    REPORT_MD.write_text(
        "\n".join(
            [
                "# ABC Known-Site Location Repair",
                "",
                f"- Generated: `{now}`",
                "- Repaired record `3994` to Beechworth Asylum, VIC.",
                "- Suppressed duplicate full-program dark-tourism records `3995` and `3996`.",
                f"- CSV: `{EXPORT_CSV.relative_to(ROOT)}`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print({"rows": len(rows)})


if __name__ == "__main__":
    main()
