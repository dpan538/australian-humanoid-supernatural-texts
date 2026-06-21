#!/usr/bin/env python3
"""Downgrade tourism-only accepted candidates to discovery leads.

Tourism pages can be useful discovery routes, but they should not be counted as
accepted public-source evidence unless a stronger archival, institutional,
newspaper, book, or community-controlled source backs the record.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "tourism_candidate_downgrade_20260621.md"

TOURISM_SOURCE_NAME_FRAGMENTS = (
    "ghost tours",
    "haunted horizons",
    "tourism",
)

TOURISM_HOST_FRAGMENTS = (
    "asylumghosttours.com",
    "adelaidehauntedhorizons.com",
    "visitvictoria.com",
    "westernaustralia.com",
    "southaustralia.com",
    "northernterritory.com",
    "discovertasmania.com",
    "visitcanberra.com",
    "tripadvisor.",
    "timeout.",
)


def host_for(url: str) -> str:
    return urlsplit(url or "").netloc.lower().removeprefix("www.")


def is_tourism_only(row: sqlite3.Row) -> bool:
    secondary = (row["secondary_role"] or "").lower()
    source = (row["source_name"] or "").lower()
    host = host_for(row["url"] or row["canonical_url"] or "")
    return (
        "tourism" in secondary
        or any(fragment in source for fragment in TOURISM_SOURCE_NAME_FRAGMENTS)
        or any(fragment in host for fragment in TOURISM_HOST_FRAGMENTS)
    )


def downgrade(db_path: str, dry_run: bool) -> dict[str, object]:
    rows_changed: list[dict[str, object]] = []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT candidate_id, run_id, source_name, source_type, source_tier,
                   quality_class, title, secondary_role, url, canonical_url
            FROM collection_candidates_v2
            WHERE candidate_status = 'accepted'
            ORDER BY candidate_id
            """
        ).fetchall()
        for row in rows:
            if not is_tourism_only(row):
                continue
            rows_changed.append(dict(row))
            if dry_run:
                continue
            conn.execute(
                """
                UPDATE collection_candidates_v2
                SET candidate_status = 'lead_only',
                    source_type = CASE
                        WHEN source_type = 'seeded_public_web' THEN 'tourism_discovery'
                        ELSE source_type
                    END,
                    source_tier = 'E',
                    quality_class = 'D',
                    acceptance_decision = 'not_accepted',
                    rejection_reason = 'tourism_discovery_only_requires_stronger_source',
                    secondary_role = 'source_pointer',
                    updated_at = ?
                WHERE candidate_id = ?
                """,
                (utc_now_iso(), row["candidate_id"]),
            )
        if not dry_run:
            conn.commit()
    return {"dry_run": dry_run, "downgraded_count": len(rows_changed), "rows": rows_changed}


def write_report(path: Path, result: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Tourism Candidate Downgrade",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Dry run: `{result['dry_run']}`",
        f"- Downgraded candidates: {result['downgraded_count']}",
        "",
        "## Policy",
        "- Tourism-only pages remain useful discovery/source-pointer leads.",
        "- They are not counted as accepted display records without stronger archival, institutional, newspaper, book, or community-controlled corroborating sources.",
        "- No rows are deleted; candidate provenance remains auditable.",
        "",
        "## Rows",
    ]
    for row in result["rows"]:  # type: ignore[index]
        lines.append(
            f"- `{row['candidate_id']}` {row['source_name']} | {row['title']} | {row['url']}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = downgrade(args.db, args.dry_run)
    write_report(Path(args.report), result)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
