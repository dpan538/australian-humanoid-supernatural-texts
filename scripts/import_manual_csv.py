#!/usr/bin/env python3
"""Import manually collected public records from a CSV file."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.classify import classify_record
from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import parse_year, slugify
from aus_humanoid.sources import get_or_create_manual_source
from aus_humanoid.utils import PROJECT_ROOT, json_dumps, utc_now_iso


REQUIRED_COLUMNS = [
    "source_name",
    "query_string",
    "external_id",
    "title",
    "publication",
    "author",
    "date_published",
    "url",
    "snippet",
    "raw_text",
]


def get_query_id(conn, source_id: int, query_string: str) -> int | None:
    row = conn.execute(
        """
        SELECT query_id FROM queries
        WHERE source_id = ? AND query_string = ?
        ORDER BY query_id
        LIMIT 1
        """,
        (source_id, query_string),
    ).fetchone()
    return int(row["query_id"]) if row else None


def import_rows(conn, csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(set(REQUIRED_COLUMNS) - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"CSV is missing required column(s): {', '.join(missing)}")
        count = 0
        for row in reader:
            source_id = get_or_create_manual_source(conn, row["source_name"])
            query_id = get_query_id(conn, source_id, row["query_string"])
            year = parse_year(row["date_published"])
            now = utc_now_iso()
            cursor = conn.execute(
                """
                INSERT INTO records (
                    source_id, query_id, external_id, title, publication, author,
                    date_published, year, url, snippet, raw_metadata_json,
                    access_status, publicness_level, ingestion_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'public_imported',
                          'open_full_text', 'raw', ?, ?)
                """,
                (
                    source_id,
                    query_id,
                    row["external_id"],
                    row["title"],
                    row["publication"],
                    row["author"],
                    row["date_published"],
                    year,
                    row["url"],
                    row["snippet"],
                    json_dumps({key: value for key, value in row.items() if key != "raw_text"}),
                    now,
                    now,
                ),
            )
            record_id = int(cursor.lastrowid)
            text_dir = PROJECT_ROOT / "data" / "raw" / "text"
            text_dir.mkdir(parents=True, exist_ok=True)
            text_path = text_dir / f"record_{record_id}_{slugify(row['title'])}.txt"
            text_path.write_text(row.get("raw_text") or "", encoding="utf-8")
            conn.execute(
                "UPDATE records SET full_text_path = ? WHERE record_id = ?",
                (str(text_path.relative_to(PROJECT_ROOT)), record_id),
            )
            classify_record(conn, record_id)
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", help="Manual record CSV to import")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        count = import_rows(conn, Path(args.csv_path))
        conn.commit()
    print(f"Imported {count} manual records")


if __name__ == "__main__":
    main()

