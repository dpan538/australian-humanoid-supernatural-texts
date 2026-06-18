#!/usr/bin/env python3
"""Run conservative duplicate marking without deleting records."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.dedupe import mark_duplicates


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        groups = mark_duplicates(conn)
        conn.commit()
    print(f"Marked {groups} duplicate group(s)")


if __name__ == "__main__":
    main()

