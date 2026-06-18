#!/usr/bin/env python3
"""Write a Wikimedia Pageviews target CSV from July 2015 onward."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT, write_csv


OUTPUT_PATH = PROJECT_ROOT / "data" / "interim" / "wikimedia_pageview_targets.csv"


def main() -> None:
    rows = [
        {
            "article_title": title,
            "project": "en.wikipedia.org",
            "date_start": "2015-07-01",
            "date_end": "present",
            "metric_type": "wikimedia_pageviews",
            "notes": "Stable article-title candidate; verify title redirects before collection.",
        }
        for title in ["Yowie", "Bunyip", "Drop bear", "Wandjina", "Quinkan"]
    ]
    write_csv(
        OUTPUT_PATH,
        rows,
        ["article_title", "project", "date_start", "date_end", "metric_type", "notes"],
    )
    print(f"Wrote Wikimedia Pageviews template: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

