#!/usr/bin/env python3
"""Create the SQLite database and all required tables."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, initialise_database
from aus_humanoid.utils import ensure_project_dirs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    ensure_project_dirs(ROOT)
    db_path = initialise_database(args.db)
    print(f"Initialised database: {db_path}")


if __name__ == "__main__":
    main()

