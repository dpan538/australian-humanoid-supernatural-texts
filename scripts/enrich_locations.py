#!/usr/bin/env python3
"""Seed the location gazetteer and attach rule-based place matches to records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.geo import assign_locations_for_record, seed_locations
from aus_humanoid.utils import PROJECT_ROOT


def read_text(path_value: str | None) -> str:
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        seed_locations(conn)
        rows = conn.execute("SELECT * FROM records ORDER BY record_id").fetchall()
        matched = 0
        for row in rows:
            text = "\n".join(
                part
                for part in [
                    row["title"] or "",
                    row["publication"] or "",
                    row["snippet"] or "",
                    read_text(row["full_text_path"]),
                ]
                if part
            )
            matched += assign_locations_for_record(conn, int(row["record_id"]), text)
        conn.commit()
    print(f"Seeded location gazetteer and wrote {matched} record-location match(es)")


if __name__ == "__main__":
    main()

