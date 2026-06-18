#!/usr/bin/env python3
"""Write a Google Trends planning CSV without requiring pytrends."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT, write_csv


OUTPUT_PATH = PROJECT_ROOT / "data" / "interim" / "google_trends_terms.csv"


def main() -> None:
    rows = [
        {
            "term": term,
            "geo": "AU",
            "date_start": "2004",
            "date_end": "present",
            "metric_type": "google_trends_relative_interest",
            "notes": "Google Trends reports relative interest, not absolute search counts.",
        }
        for term in ["Yowie", "Bunyip", "Drop bear", "Wandjina", "Quinkan"]
    ]
    write_csv(
        OUTPUT_PATH,
        rows,
        ["term", "geo", "date_start", "date_end", "metric_type", "notes"],
    )
    print(f"Wrote Google Trends template: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

