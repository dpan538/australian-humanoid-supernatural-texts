#!/usr/bin/env python3
"""Write a safe Trove query template CSV without making API calls."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, write_csv


OUTPUT_PATH = PROJECT_ROOT / "data" / "interim" / "trove_queries_to_run.csv"


def trove_search_url(query: str) -> str:
    return "https://trove.nla.gov.au/search/category/newspapers?keyword=" + quote_plus(query)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output CSV path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        rows = conn.execute(
            """
            SELECT q.query_id, q.query_string, q.date_start, q.date_end,
                   s.source_name, q.expected_noise_level, q.notes
            FROM queries q
            JOIN sources s ON s.source_id = q.source_id
            WHERE s.source_type IN ('trove_newspaper', 'trove_magazine')
              AND q.status = 'planned'
            ORDER BY q.query_id
            """
        ).fetchall()
    output_rows = [
        {
            "query_id": row["query_id"],
            "query_string": row["query_string"],
            "date_start": row["date_start"],
            "date_end": row["date_end"],
            "source_name": row["source_name"],
            "expected_noise_level": row["expected_noise_level"],
            "manual_search_url": trove_search_url(row["query_string"]),
            "notes": row["notes"],
        }
        for row in rows
    ]
    write_csv(
        args.output,
        output_rows,
        [
            "query_id",
            "query_string",
            "date_start",
            "date_end",
            "source_name",
            "expected_noise_level",
            "manual_search_url",
            "notes",
        ],
    )
    print(f"Wrote Trove query template: {args.output}")


if __name__ == "__main__":
    main()

