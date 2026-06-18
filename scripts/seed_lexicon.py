#!/usr/bin/env python3
"""Seed sources, figures, and aliases from YAML configuration."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.sources import seed_sources
from aus_humanoid.utils import PROJECT_ROOT, read_yaml


DEFAULT_LEXICON_PATH = PROJECT_ROOT / "config" / "lexicon.yml"
DEFAULT_SOURCES_PATH = PROJECT_ROOT / "config" / "sources.yml"


def upsert_figure(conn, figure: dict) -> int:
    existing = conn.execute(
        "SELECT figure_id FROM figures WHERE canonical_name = ?",
        (figure["canonical_name"],),
    ).fetchone()
    values = (
        figure["canonical_name"],
        figure["cluster"],
        figure["tier"],
        figure["include_status"],
        figure.get("humanoid_degree"),
        figure.get("ontology_default"),
        int(bool(figure.get("involves_indigenous_knowledge", False))),
        figure.get("sensitivity_notes"),
        figure.get("description"),
    )
    if existing:
        conn.execute(
            """
            UPDATE figures
            SET cluster = ?, tier = ?, include_status = ?, humanoid_degree = ?,
                ontology_default = ?, involves_indigenous_knowledge = ?,
                sensitivity_notes = ?, description = ?
            WHERE figure_id = ?
            """,
            values[1:] + (existing["figure_id"],),
        )
        return int(existing["figure_id"])

    cursor = conn.execute(
        """
        INSERT INTO figures (
            canonical_name, cluster, tier, include_status, humanoid_degree,
            ontology_default, involves_indigenous_knowledge, sensitivity_notes,
            description
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        values,
    )
    return int(cursor.lastrowid)


def upsert_alias(conn, figure_id: int, alias: dict) -> None:
    row = conn.execute(
        """
        SELECT alias_id FROM aliases
        WHERE figure_id = ? AND alias = ? AND alias_type = ?
        """,
        (figure_id, alias["alias"], alias["alias_type"]),
    ).fetchone()
    values = (
        alias["alias"],
        alias["alias_type"],
        int(alias.get("search_priority", 0)),
        alias.get("notes"),
    )
    if row:
        conn.execute(
            """
            UPDATE aliases
            SET search_priority = ?, notes = ?
            WHERE alias_id = ?
            """,
            (values[2], values[3], row["alias_id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO aliases (figure_id, alias, alias_type, search_priority, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (figure_id,) + values,
        )


def seed_lexicon(conn, lexicon_path: str | Path = DEFAULT_LEXICON_PATH) -> tuple[int, int]:
    config = read_yaml(lexicon_path)
    figure_count = 0
    alias_count = 0
    for figure in config.get("figures", []):
        figure_id = upsert_figure(conn, figure)
        figure_count += 1
        aliases = figure.get("aliases") or [
            {
                "alias": figure["canonical_name"],
                "alias_type": "exact",
                "search_priority": 100,
            }
        ]
        for alias in aliases:
            upsert_alias(conn, figure_id, alias)
            alias_count += 1
    return figure_count, alias_count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--lexicon", default=str(DEFAULT_LEXICON_PATH), help="Lexicon YAML path")
    parser.add_argument("--sources", default=str(DEFAULT_SOURCES_PATH), help="Sources YAML path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        seed_sources(conn, args.sources)
        figures, aliases = seed_lexicon(conn, args.lexicon)
        conn.commit()
    print(f"Seeded {figures} figures and {aliases} aliases")


if __name__ == "__main__":
    main()

