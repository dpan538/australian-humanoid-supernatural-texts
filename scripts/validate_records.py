#!/usr/bin/env python3
"""Run database integrity checks and write a validation report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_text
from aus_humanoid.utils import PROJECT_ROOT


REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "validation_report.md"
BARE_FORBIDDEN = {"yahoo", "mimi", "mamu", "hairy man"}


def is_bare_forbidden(query: str) -> bool:
    stripped = normalise_text(query).strip('"').strip("'").strip()
    return stripped in BARE_FORBIDDEN


def run_checks(conn) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    warnings: list[str] = []

    rows = conn.execute("SELECT query_id, query_string FROM queries").fetchall()
    bare = [row for row in rows if is_bare_forbidden(row["query_string"])]
    if bare:
        failures.append(
            "Bare high-noise query generated: "
            + ", ".join(f"#{row['query_id']} {row['query_string']}" for row in bare)
        )

    restricted = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM records r
        LEFT JOIN coding c ON c.record_id = r.record_id
        WHERE COALESCE(r.publicness_level, '') = 'restricted_excluded'
           OR COALESCE(c.publicness_code, '') = 'restricted_excluded'
        """
    ).fetchone()["n"]
    if restricted:
        warnings.append(
            f"{restricted} restricted_excluded record(s) exist; export filters must exclude them."
        )

    missing_source = conn.execute(
        "SELECT COUNT(*) AS n FROM records WHERE source_id IS NULL"
    ).fetchone()["n"]
    if missing_source:
        failures.append(f"{missing_source} record(s) have no source_id.")

    missing_year = conn.execute(
        """
        SELECT COUNT(*) AS n
        FROM records
        WHERE date_published IS NOT NULL
          AND TRIM(date_published) != ''
          AND year IS NULL
        """
    ).fetchone()["n"]
    if missing_year:
        warnings.append(
            f"{missing_year} record(s) have date_published but no parsed year."
        )

    promoted_validation = conn.execute(
        """
        SELECT canonical_name
        FROM figures
        WHERE (cluster = 'validation_queue' OR tier = 'validation_queue')
          AND include_status = 'include_v1'
        ORDER BY canonical_name
        """
    ).fetchall()
    if promoted_validation:
        failures.append(
            "Validation-queue term(s) marked include_v1 without manual promotion notes: "
            + ", ".join(row["canonical_name"] for row in promoted_validation)
        )

    fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk_errors:
        failures.append(f"Foreign key check reported {len(fk_errors)} issue(s).")

    return failures, warnings


def write_report(failures: list[str], warnings: list[str], path: Path = REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Validation Report",
        "",
        f"Status: {'FAIL' if failures else 'PASS'}",
        "",
        "## Failures",
        "",
    ]
    lines.extend([f"- {item}" for item in failures] or ["- None"])
    lines.extend(["", "## Warnings", ""])
    lines.extend([f"- {item}" for item in warnings] or ["- None"])
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "- No bare Yahoo-only queries.",
            "- No bare Mimi-only queries.",
            "- No bare Mamu-only queries.",
            "- No bare Hairy Man-only queries.",
            "- Restricted publicness is flagged and filtered from exports.",
            "- Records retain source identifiers.",
            "- Dated records are checked for parseable years.",
            "- Validation queue terms are not silently promoted to include_v1.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--report", default=str(REPORT_PATH), help="Validation report path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        failures, warnings = run_checks(conn)
    write_report(failures, warnings, Path(args.report))
    print(f"Wrote validation report: {args.report}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

