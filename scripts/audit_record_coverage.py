#!/usr/bin/env python3
"""Write a reproducible coverage/confidence audit for display records."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "processed" / "record_coverage_audit.md"


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def pct(count: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def rows(conn: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return list(conn.execute(sql).fetchall())


def card_ready_count(conn: sqlite3.Connection, where: str = "1=1") -> int:
    return scalar(
        conn,
        f"""
        SELECT COUNT(*)
        FROM records r
        WHERE {where}
          AND r.year IS NOT NULL
          AND r.title IS NOT NULL
          AND r.url IS NOT NULL
          AND r.snippet IS NOT NULL
          AND r.source_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM coding c WHERE c.record_id = r.record_id)
          AND EXISTS (SELECT 1 FROM record_locations rl WHERE rl.record_id = r.record_id)
        """,
    )


def record_confidence(conn: sqlite3.Connection) -> Counter[str]:
    priority = {"high": 3, "medium": 2, "low": 1}
    output: Counter[str] = Counter()
    record_ids = [row["record_id"] for row in rows(conn, "SELECT record_id FROM records")]
    for record_id in record_ids:
        confidences = [
            row["confidence"] or "unknown"
            for row in conn.execute(
                "SELECT confidence FROM record_locations WHERE record_id = ?",
                (record_id,),
            ).fetchall()
        ]
        if not confidences:
            output["unknown"] += 1
            continue
        best = max(confidences, key=lambda item: priority.get(item, 0))
        output[best] += 1
    return output


def write_audit(db_path: str | Path, output_path: Path = DEFAULT_OUTPUT) -> Path:
    with connect(db_path) as conn:
        total = scalar(conn, "SELECT COUNT(*) FROM records")
        ayr_total = scalar(conn, "SELECT COUNT(*) FROM records WHERE external_id LIKE 'ayr:%'")
        ready_total = card_ready_count(conn)
        ready_ayr = card_ready_count(conn, "r.external_id LIKE 'ayr:%'")

        state_rows = rows(
            conn,
            """
            SELECT
              CASE
                WHEN l.state_territory IS NULL THEN 'UNKNOWN'
                WHEN TRIM(l.state_territory) = '' THEN 'AU_UNSPECIFIED'
                ELSE l.state_territory
              END AS state,
                   COUNT(DISTINCT r.record_id) AS count
            FROM records r
            LEFT JOIN record_locations rl ON rl.record_id = r.record_id
            LEFT JOIN locations l ON l.location_id = rl.location_id
            GROUP BY state
            ORDER BY state
            """,
        )
        band_rows = rows(
            conn,
            """
            SELECT
              CASE
                WHEN year BETWEEN 1803 AND 1841 THEN '1803-1841 backsearch'
                WHEN year BETWEEN 1842 AND 1875 THEN '1842-1875 anchor'
                WHEN year BETWEEN 1876 AND 1969 THEN '1876-1969 expansion'
                WHEN year >= 1970 THEN '1970-present modern'
                ELSE 'unknown'
              END AS band,
              COUNT(*) AS count
            FROM records
            GROUP BY band
            ORDER BY
              CASE band
                WHEN '1803-1841 backsearch' THEN 1
                WHEN '1842-1875 anchor' THEN 2
                WHEN '1876-1969 expansion' THEN 3
                WHEN '1970-present modern' THEN 4
                ELSE 5
              END
            """,
        )
        source_rows = rows(
            conn,
            """
            SELECT s.source_name, s.source_type, COUNT(*) AS count
            FROM records r
            JOIN sources s ON s.source_id = r.source_id
            GROUP BY s.source_id, s.source_name, s.source_type
            ORDER BY count DESC, s.source_name
            """,
        )
        relevance_rows = rows(
            conn,
            """
            SELECT COALESCE(c.relevance_code, 'uncoded') AS relevance_code, COUNT(*) AS count
            FROM records r
            LEFT JOIN coding c ON c.record_id = r.record_id
            GROUP BY relevance_code
            ORDER BY count DESC
            """,
        )
        ethics_rows = rows(
            conn,
            """
            SELECT COALESCE(c.ethics_flag, 'uncoded') AS ethics_flag, COUNT(*) AS count
            FROM records r
            LEFT JOIN coding c ON c.record_id = r.record_id
            GROUP BY ethics_flag
            ORDER BY count DESC
            """,
        )
        confidence = record_confidence(conn)
        earliest = conn.execute("SELECT MIN(year), MAX(year) FROM records").fetchone()

    lines = [
        "# Record Coverage and Confidence Audit",
        "",
        "## Execution Context",
        f"- Generated: `{utc_now_iso()}`",
        f"- Database: `{Path(db_path)}`",
        f"- Total display records: {total}",
        f"- AYR public records: {ayr_total}",
        f"- Year span: {earliest[0]}-{earliest[1]}",
        "",
        "## Card Readiness",
        f"- All records card-ready: {ready_total}/{total} ({pct(ready_total, total)})",
        f"- AYR records card-ready: {ready_ayr}/{ayr_total} ({pct(ready_ayr, ayr_total)})",
        "- Card-ready means year, title, URL, snippet, source, coding row, and at least one location link.",
        "",
        "## Date Coverage",
    ]
    for row in band_rows:
        lines.append(f"- {row['band']}: {row['count']} ({pct(int(row['count']), total)})")

    lines.extend(["", "## Region Coverage"])
    for row in state_rows:
        lines.append(f"- {row['state']}: {row['count']} ({pct(int(row['count']), total)})")

    lines.extend(
        [
            "",
            "## Location Confidence",
            f"- high: {confidence.get('high', 0)} ({pct(confidence.get('high', 0), total)})",
            f"- medium: {confidence.get('medium', 0)} ({pct(confidence.get('medium', 0), total)})",
            f"- low: {confidence.get('low', 0)} ({pct(confidence.get('low', 0), total)})",
            f"- unknown: {confidence.get('unknown', 0)} ({pct(confidence.get('unknown', 0), total)})",
            "",
            "## Source Coverage",
        ]
    )
    for row in source_rows:
        lines.append(f"- {row['source_name']} ({row['source_type']}): {row['count']} ({pct(int(row['count']), total)})")

    lines.extend(["", "## Relevance Coding"])
    for row in relevance_rows:
        lines.append(f"- {row['relevance_code']}: {row['count']} ({pct(int(row['count']), total)})")

    lines.extend(["", "## Ethics Flags"])
    for row in ethics_rows:
        lines.append(f"- {row['ethics_flag']}: {row['count']} ({pct(int(row['count']), total)})")

    lines.extend(
        [
            "",
            "## Audit Notes",
            "- AYR records are card-ready display records, not search leads.",
            "- Regional coverage is not even: NSW and QLD dominate because the public AYR archive is heavily weighted toward those states.",
            "- AU_UNSPECIFIED records have Australia-level or broad-region location signals rather than a state/territory.",
            "- UNKNOWN records have display fields but no reliable state/territory location.",
            "- Early-period coverage improved through public historical/media pages, but the corpus remains modern-heavy.",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Markdown audit output path")
    args = parser.parse_args()
    path = write_audit(args.db, Path(args.output))
    print(f"Wrote record coverage audit: {path}")


if __name__ == "__main__":
    main()
