#!/usr/bin/env python3
"""Generate planned source queries from lexicon and noise rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_alias
from aus_humanoid.utils import PROJECT_ROOT, read_yaml


DEFAULT_QUERIES_PATH = PROJECT_ROOT / "config" / "queries.yml"
DEFAULT_NOISE_RULES_PATH = PROJECT_ROOT / "config" / "noise_rules.yml"
PREFERRED_SOURCE_NAMES = {
    "modern_web": "Modern Public Web",
}


def get_source_ids(conn, source_types: list[str]) -> dict[str, int]:
    found: dict[str, int] = {}
    for source_type in source_types:
        preferred_name = PREFERRED_SOURCE_NAMES.get(source_type)
        if preferred_name:
            row = conn.execute(
                """
                SELECT source_id, source_type
                FROM sources
                WHERE source_type = ? AND source_name = ?
                """,
                (source_type, preferred_name),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT source_id, source_type
                FROM sources
                WHERE source_type = ?
                ORDER BY source_id
                LIMIT 1
                """,
                (source_type,),
            ).fetchone()
        if row:
            found[source_type] = int(row["source_id"])
    missing = sorted(set(source_types) - set(found))
    if missing:
        raise ValueError(f"Missing source rows for source_type(s): {', '.join(missing)}")
    return found


def cleanup_noncanonical_planned_queries(conn) -> int:
    """Remove generated planned queries from non-canonical source rows.

    Collection-specific sources such as ABC News and English Wikipedia can share
    source_type = modern_web, but the query plan should remain attached to the
    canonical Modern Public Web source. Only unreferenced planned rows are
    cleaned up.
    """

    removed = 0
    for source_type, preferred_name in PREFERRED_SOURCE_NAMES.items():
        rows = conn.execute(
            """
            SELECT q.query_id
            FROM queries q
            JOIN sources s ON s.source_id = q.source_id
            LEFT JOIN records r ON r.query_id = q.query_id
            WHERE s.source_type = ?
              AND s.source_name != ?
              AND q.status = 'planned'
              AND r.record_id IS NULL
            """,
            (source_type, preferred_name),
        ).fetchall()
        for row in rows:
            conn.execute("DELETE FROM queries WHERE query_id = ?", (row["query_id"],))
            removed += 1
    return removed


def load_high_noise(noise_config: dict) -> dict[str, dict]:
    high_noise: dict[str, dict] = {}
    for item in noise_config.get("high_noise_terms", []):
        high_noise[normalise_alias(item["term"])] = item
    return high_noise


def expected_noise(alias: str, high_noise: dict[str, dict]) -> str:
    rule = high_noise.get(normalise_alias(alias))
    if rule:
        return rule.get("expected_noise_level", "high")
    return "medium" if len(alias) <= 5 else "low"


def query_strings_for_alias(alias: str, high_noise: dict[str, dict]) -> list[tuple[str, str]]:
    rule = high_noise.get(normalise_alias(alias))
    if rule:
        return [(query, "constrained_boolean") for query in rule.get("constraints", [])]
    return [(f'"{alias}"', "exact_phrase")]


def upsert_query(conn, row: dict) -> None:
    existing = conn.execute(
        """
        SELECT query_id FROM queries
        WHERE COALESCE(figure_id, -1) = COALESCE(?, -1)
          AND source_id = ?
          AND query_string = ?
          AND query_type = ?
          AND COALESCE(date_start, '') = COALESCE(?, '')
          AND COALESCE(date_end, '') = COALESCE(?, '')
        """,
        (
            row.get("figure_id"),
            row["source_id"],
            row["query_string"],
            row["query_type"],
            row.get("date_start"),
            row.get("date_end"),
        ),
    ).fetchone()
    values = (
        row.get("figure_id"),
        row["source_id"],
        row["query_string"],
        row["query_type"],
        row.get("date_start"),
        row.get("date_end"),
        row.get("expected_noise_level"),
        row.get("status", "planned"),
        row.get("notes"),
    )
    if existing:
        conn.execute(
            """
            UPDATE queries
            SET expected_noise_level = ?, status = ?, notes = ?
            WHERE query_id = ?
            """,
            (values[6], values[7], values[8], existing["query_id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO queries (
                figure_id, source_id, query_string, query_type, date_start,
                date_end, expected_noise_level, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values,
        )


def generate_queries(conn, queries_path: str | Path, noise_rules_path: str | Path) -> int:
    query_config = read_yaml(queries_path)
    noise_config = read_yaml(noise_rules_path)
    high_noise = load_high_noise(noise_config)
    cleanup_noncanonical_planned_queries(conn)

    historical_bands = query_config["date_bands"]["historical"]
    attention_bands = query_config["date_bands"]["attention"]
    historical_source_types = query_config["historical_source_types"]
    modern_source_types = query_config["modern_source_types"]
    attention_sources = query_config["attention_sources"]

    source_ids = get_source_ids(
        conn,
        sorted(set(historical_source_types + modern_source_types + list(attention_sources.values()))),
    )
    alias_rows = conn.execute(
        """
        SELECT
            f.figure_id, f.canonical_name, f.include_status, f.cluster,
            a.alias, a.alias_type, a.search_priority
        FROM figures f
        JOIN aliases a ON a.figure_id = f.figure_id
        WHERE f.include_status IN ('include_v1', 'control_only')
        ORDER BY f.figure_id, a.search_priority DESC, LENGTH(a.alias) DESC
        """
    ).fetchall()

    count = 0
    for row in alias_rows:
        if row["alias_type"] == "noise_class":
            continue
        for band in historical_bands:
            band_source_types = list(historical_source_types)
            if band["name"] == "modern_yowie_heritage_tourism_media":
                band_source_types = sorted(set(historical_source_types + modern_source_types))
            for query_string, query_type in query_strings_for_alias(row["alias"], high_noise):
                if not query_string:
                    continue
                for source_type in band_source_types:
                    upsert_query(
                        conn,
                        {
                            "figure_id": row["figure_id"],
                            "source_id": source_ids[source_type],
                            "query_string": query_string,
                            "query_type": "negative_control"
                            if band["name"] == "backsearch_negative_control"
                            else query_type,
                            "date_start": band["date_start"],
                            "date_end": band["date_end"],
                            "expected_noise_level": expected_noise(row["alias"], high_noise),
                            "status": "planned",
                            "notes": f"{band['label']}; generated from alias {row['alias']}.",
                        },
                    )
                    count += 1

    for item in query_config.get("attention_terms", []):
        for source_key, source_type in attention_sources.items():
            band = attention_bands[source_key]
            upsert_query(
                conn,
                {
                    "figure_id": None,
                    "source_id": source_ids[source_type],
                    "query_string": item["term"],
                    "query_type": "attention_series",
                    "date_start": band["date_start"],
                    "date_end": band["date_end"],
                    "expected_noise_level": item.get("expected_noise_level", "medium"),
                    "status": "planned",
                    "notes": f"{band['label']}; attention-series planning term.",
                },
            )
            count += 1

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES_PATH), help="Queries YAML path")
    parser.add_argument("--noise-rules", default=str(DEFAULT_NOISE_RULES_PATH), help="Noise YAML path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        generate_queries(conn, args.queries, args.noise_rules)
        count = conn.execute("SELECT COUNT(*) AS n FROM queries").fetchone()["n"]
        conn.commit()
    print(f"Generated or updated query plan: {count} total planned query rows")


if __name__ == "__main__":
    main()
