#!/usr/bin/env python3
"""Export human-review datasets from the SQLite database."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.geo import location_summary
from aus_humanoid.utils import PROJECT_ROOT


EXPORT_DIR = PROJECT_ROOT / "data" / "exports"


def write_query(conn, path: Path, sql: str, fieldnames: list[str]) -> None:
    rows = conn.execute(sql).fetchall()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fieldnames})


def export_all(conn, export_dir: Path = EXPORT_DIR) -> None:
    records_rows = conn.execute(
        """
        SELECT
            r.record_id, r.year, r.date_published, r.title, r.publication, r.url,
            c.canonical_figure_guess, c.figure_name_as_printed, r.snippet,
            c.relevance_code, c.ontology_code, c.humanoid_degree_code,
            c.source_voice, c.genre, c.publicness_code, c.ethics_flag, c.notes
        FROM records r
        LEFT JOIN coding c ON c.record_id = r.record_id
        WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
          AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
          AND COALESCE(c.relevance_code, '') != 'scope_excluded'
        ORDER BY r.year, r.record_id
        """
    ).fetchall()
    records_fields = [
            "record_id",
            "year",
            "date_published",
            "title",
            "publication",
            "url",
            "location_summary",
            "canonical_figure_guess",
            "figure_name_as_printed",
            "snippet",
            "relevance_code",
            "ontology_code",
            "humanoid_degree_code",
            "source_voice",
            "genre",
            "publicness_code",
            "ethics_flag",
            "notes",
    ]
    records_path = export_dir / "records_review.csv"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    with records_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=records_fields)
        writer.writeheader()
        for row in records_rows:
            out = {field: row[field] for field in records_fields if field != "location_summary"}
            out["location_summary"] = location_summary(conn, int(row["record_id"]))
            writer.writerow(out)
    write_query(
        conn,
        export_dir / "figures_aliases.csv",
        """
        SELECT
            f.figure_id, f.canonical_name, f.cluster, f.tier, f.include_status,
            f.humanoid_degree, f.ontology_default, f.involves_indigenous_knowledge,
            f.sensitivity_notes, a.alias_id, a.alias, a.alias_type,
            a.search_priority, a.notes
        FROM figures f
        LEFT JOIN aliases a ON a.figure_id = f.figure_id
        ORDER BY f.cluster, f.canonical_name, a.search_priority DESC, a.alias
        """,
        [
            "figure_id",
            "canonical_name",
            "cluster",
            "tier",
            "include_status",
            "humanoid_degree",
            "ontology_default",
            "involves_indigenous_knowledge",
            "sensitivity_notes",
            "alias_id",
            "alias",
            "alias_type",
            "search_priority",
            "notes",
        ],
    )
    write_query(
        conn,
        export_dir / "query_plan.csv",
        """
        SELECT
            q.query_id, s.source_name, s.source_type, f.canonical_name,
            q.query_string, q.query_type, q.date_start, q.date_end,
            q.expected_noise_level, q.status, q.notes
        FROM queries q
        JOIN sources s ON s.source_id = q.source_id
        LEFT JOIN figures f ON f.figure_id = q.figure_id
        ORDER BY s.source_type, f.canonical_name, q.date_start, q.query_string
        """,
        [
            "query_id",
            "source_name",
            "source_type",
            "canonical_name",
            "query_string",
            "query_type",
            "date_start",
            "date_end",
            "expected_noise_level",
            "status",
            "notes",
        ],
    )
    write_query(
        conn,
        export_dir / "attention_series.csv",
        """
        SELECT
            a.attention_id, f.canonical_name, s.source_name, s.source_type,
            a.term, a.date, a.value, a.geo, a.metric_type, a.notes
        FROM attention_series a
        JOIN sources s ON s.source_id = a.source_id
        LEFT JOIN figures f ON f.figure_id = a.figure_id
        ORDER BY a.term, a.date
        """,
        [
            "attention_id",
            "canonical_name",
            "source_name",
            "source_type",
            "term",
            "date",
            "value",
            "geo",
            "metric_type",
            "notes",
        ],
    )
    write_query(
        conn,
        export_dir / "record_locations.csv",
        """
        SELECT
            rl.record_id, r.year, r.title, l.place_name, l.region,
            l.state_territory, l.country, l.latitude, l.longitude,
            l.location_type, l.verification_status, rl.relation_type,
            rl.evidence_text, rl.confidence, rl.notes
        FROM record_locations rl
        JOIN records r ON r.record_id = rl.record_id
        JOIN locations l ON l.location_id = rl.location_id
        ORDER BY r.year, r.record_id, l.place_name
        """,
        [
            "record_id",
            "year",
            "title",
            "place_name",
            "region",
            "state_territory",
            "country",
            "latitude",
            "longitude",
            "location_type",
            "verification_status",
            "relation_type",
            "evidence_text",
            "confidence",
            "notes",
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--export-dir", default=str(EXPORT_DIR), help="Export directory")
    args = parser.parse_args()

    with connect(args.db) as conn:
        export_all(conn, Path(args.export_dir))
    print(f"Wrote exports to: {args.export_dir}")


if __name__ == "__main__":
    main()
