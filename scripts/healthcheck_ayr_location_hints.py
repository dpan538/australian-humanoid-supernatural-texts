#!/usr/bin/env python3
"""Attach conservative AYR source-visible place hints to existing records.

This script is a corpus-health pass, not a collector. It does not create
records. It only adds location rows and record-location links when a configured
place alias is visible in an existing record title/snippet/raw text.
Coordinates are intentionally left empty here; run geocode_location_queue.py to
upgrade only the rows that pass strict gazetteer checks.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso


DEFAULT_HINTS = PROJECT_ROOT / "config" / "ayr_location_health_hints.yml"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "ayr_location_health_report.md"
NEGATIVE_CONTEXT_PATTERNS = (
    "resides in",
    "now resides",
    "reporter",
    "newspaper",
    "magazine",
    "locals in",
    "publication",
    "source:",
)


def canonical_space(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def read_record_text(row: sqlite3.Row) -> str:
    parts = [
        row["title"] or "",
        row["publication"] or "",
        row["snippet"] or "",
    ]
    path_value = row["full_text_path"]
    if path_value:
        path = Path(path_value)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        try:
            parts.append(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
    return "\n".join(part for part in parts if part)


def load_hints(path: Path) -> list[dict[str, Any]]:
    data = read_yaml(path)
    output = []
    for row in data.get("places", []):
        aliases = [canonical_space(alias) for alias in row.get("aliases", []) if canonical_space(alias)]
        if not aliases:
            aliases = [canonical_space(row["place_name"])]
        output.append(
            {
                "place_name": canonical_space(row["place_name"]),
                "state_territory": canonical_space(row["state_territory"]),
                "aliases": aliases,
                "patterns": [alias_pattern(alias) for alias in aliases],
            }
        )
    return sorted(output, key=lambda item: max(len(alias) for alias in item["aliases"]), reverse=True)


def find_or_create_location(conn: sqlite3.Connection, hint: dict[str, Any]) -> int:
    row = conn.execute(
        "SELECT location_id FROM locations WHERE place_name = ?",
        (hint["place_name"],),
    ).fetchone()
    if row:
        return int(row["location_id"])
    cursor = conn.execute(
        """
        INSERT INTO locations (
            place_name, region, state_territory, country, latitude, longitude,
            location_type, geocode_source, verification_status, notes
        ) VALUES (?, NULL, ?, 'Australia', NULL, NULL,
                  'locality', 'ayr_source_visible_location_hint',
                  'source_named_place_needs_geocode',
                  'Configured AYR location-health hint; strict coordinates require separate gazetteer geocode.')
        """,
        (hint["place_name"], hint["state_territory"]),
    )
    return int(cursor.lastrowid)


def has_strict_point(conn: sqlite3.Connection, record_id: int) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE rl.record_id = ?
          AND l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
        LIMIT 1
        """,
        (record_id,),
    ).fetchone()
    return row is not None


def existing_state_codes(conn: sqlite3.Connection, record_id: int) -> set[str]:
    rows = conn.execute(
        """
        SELECT DISTINCT l.state_territory
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE rl.record_id = ?
          AND COALESCE(l.state_territory, '') != ''
        """,
        (record_id,),
    ).fetchall()
    return {str(row["state_territory"]) for row in rows if row["state_territory"]}


def attach_hint(conn: sqlite3.Connection, record_id: int, location_id: int, evidence: str) -> bool:
    existing = conn.execute(
        """
        SELECT 1 FROM record_locations
        WHERE record_id = ? AND location_id = ? AND relation_type = 'source_visible_place_hint'
        """,
        (record_id, location_id),
    ).fetchone()
    if existing:
        return False
    conn.execute(
        """
        INSERT OR REPLACE INTO record_locations (
            record_id, location_id, relation_type, evidence_text, confidence, notes
        ) VALUES (?, ?, 'source_visible_place_hint', ?, 'medium',
                  'Configured location-health pass; not analysis-ready without human review.')
        """,
        (record_id, location_id, evidence),
    )
    return True


def evidence_is_acceptable(evidence: str) -> bool:
    lowered = evidence.lower()
    return not any(pattern in lowered for pattern in NEGATIVE_CONTEXT_PATTERNS)


def run(db_path: str | Path, hints_path: Path, report_path: Path, apply: bool) -> dict[str, Any]:
    hints = load_hints(hints_path)
    stats = {
        "records_scanned": 0,
        "records_with_hint": 0,
        "links_added": 0,
        "strict_records_before": 0,
        "hint_counts": {},
        "examples": [],
    }
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT r.*
            FROM records r
            JOIN sources s ON s.source_id = r.source_id
            WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
              AND (
                s.source_name = 'Australian Yowie Research'
                OR COALESCE(r.external_id, '') LIKE 'ayr:%'
              )
            ORDER BY r.record_id
            """
        ).fetchall()
        stats["strict_records_before"] = conn.execute(
            """
            SELECT COUNT(DISTINCT r.record_id)
            FROM records r
            JOIN record_locations rl ON rl.record_id = r.record_id
            JOIN locations l ON l.location_id = rl.location_id
            WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
            """
        ).fetchone()[0]

        for row in rows:
            record_id = int(row["record_id"])
            if has_strict_point(conn, record_id):
                continue
            known_states = existing_state_codes(conn, record_id)
            stats["records_scanned"] += 1
            text = read_record_text(row)
            matched_this_record = False
            for hint in hints:
                if known_states and hint["state_territory"] not in known_states:
                    continue
                for pattern in hint["patterns"]:
                    found = pattern.search(text)
                    if not found:
                        continue
                    evidence = canonical_space(text[max(0, found.start() - 90) : min(len(text), found.end() + 90)])
                    if not evidence_is_acceptable(evidence):
                        continue
                    stats["hint_counts"][hint["place_name"]] = stats["hint_counts"].get(hint["place_name"], 0) + 1
                    matched_this_record = True
                    if apply:
                        location_id = find_or_create_location(conn, hint)
                        if attach_hint(conn, record_id, location_id, evidence):
                            stats["links_added"] += 1
                    if len(stats["examples"]) < 25:
                        stats["examples"].append(
                            {
                                "record_id": record_id,
                                "year": row["year"],
                                "title": row["title"],
                                "place": hint["place_name"],
                                "state": hint["state_territory"],
                                "evidence": evidence,
                            }
                        )
                    break
            if matched_this_record:
                stats["records_with_hint"] += 1
        if apply:
            conn.commit()

    write_report(stats, hints_path, report_path, apply)
    return stats


def write_report(stats: dict[str, Any], hints_path: Path, report_path: Path, apply: bool) -> None:
    lines = [
        "# AYR Location Health Report",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Mode: `{'apply' if apply else 'dry_run'}`",
        f"- Hints: `{hints_path}`",
        f"- Records scanned without strict point: `{stats['records_scanned']}`",
        f"- Records with source-visible place hint: `{stats['records_with_hint']}`",
        f"- Record-location links added: `{stats['links_added']}`",
        f"- Strict records before pass: `{stats['strict_records_before']}`",
        "",
        "## Policy",
        "",
        "This pass only attaches configured source-visible place aliases. It does not create records, does not infer coordinates, and does not promote publication mastheads or generic state names into event locations.",
        "",
        "## Top Hints",
    ]
    for place, count in sorted(stats["hint_counts"].items(), key=lambda item: (-item[1], item[0]))[:30]:
        lines.append(f"- {place}: {count}")
    lines.extend(["", "## Examples", ""])
    lines.append("| record_id | year | place | state | title | evidence |")
    lines.append("| --- | ---: | --- | --- | --- | --- |")
    for row in stats["examples"]:
        title = canonical_space(str(row["title"])).replace("|", "\\|")
        evidence = canonical_space(str(row["evidence"])).replace("|", "\\|")
        lines.append(
            f"| {row['record_id']} | {row['year'] or ''} | {row['place']} | {row['state']} | {title} | {evidence} |"
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--hints", default=str(DEFAULT_HINTS), help="YAML location hints")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Markdown report output")
    parser.add_argument("--apply", action="store_true", help="Write location links")
    args = parser.parse_args()
    stats = run(args.db, Path(args.hints), Path(args.report), args.apply)
    print(
        {
            "mode": "apply" if args.apply else "dry_run",
            "records_scanned": stats["records_scanned"],
            "records_with_hint": stats["records_with_hint"],
            "links_added": stats["links_added"],
        }
    )
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
