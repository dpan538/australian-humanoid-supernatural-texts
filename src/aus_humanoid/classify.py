"""Initial rule-based coding for imported public records.

This module provides triage only. Its output is a review queue, not final
interpretive coding.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from .normalise import canonicalise_whitespace
from .utils import PROJECT_ROOT, read_yaml, utc_now_iso


DEFAULT_NOISE_RULES_PATH = PROJECT_ROOT / "config" / "noise_rules.yml"


def _read_record_text(record: sqlite3.Row) -> str:
    path_value = record["full_text_path"]
    if not path_value:
        return ""
    path = Path(path_value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def load_noise_patterns(path: str | Path = DEFAULT_NOISE_RULES_PATH) -> list[str]:
    config = read_yaml(path)
    patterns: list[str] = []
    for item in config.get("noise_patterns", []):
        if isinstance(item, dict):
            patterns.extend(item.get("patterns", []))
        elif isinstance(item, str):
            patterns.append(item)
    return patterns


def contains_noise_pattern(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if re.search(re.escape(pattern), text, flags=re.IGNORECASE):
            return pattern
    return None


def load_alias_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            a.alias_id, a.alias, a.alias_type, a.search_priority,
            f.figure_id, f.canonical_name, f.ontology_default,
            f.humanoid_degree, f.involves_indigenous_knowledge
        FROM aliases a
        JOIN figures f ON f.figure_id = a.figure_id
        WHERE f.include_status IN ('include_v1', 'validate_before_include', 'control_only')
        ORDER BY a.search_priority DESC, LENGTH(a.alias) DESC, a.alias
        """
    ).fetchall()


def _alias_pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if re.match(r"^[A-Za-z0-9 -]+$", alias):
        escaped = escaped.replace(r"\ ", r"\s+")
        return re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _context(text: str, start: int, end: int, width: int = 90) -> str:
    left = max(0, start - width)
    right = min(len(text), end + width)
    return canonicalise_whitespace(text[left:right])


def match_aliases(conn: sqlite3.Connection, record_id: int, text: str) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for alias_row in load_alias_rows(conn):
        pattern = _alias_pattern(alias_row["alias"])
        found = pattern.search(text)
        if found is None:
            continue
        confidence = "high"
        if alias_row["alias_type"] in {"noise_sensitive", "historical_descriptor"}:
            confidence = "medium"
        if len(alias_row["alias"]) <= 4:
            confidence = "low"
        matches.append(
            {
                "record_id": record_id,
                "alias_id": alias_row["alias_id"],
                "matched_text": found.group(0),
                "match_context": _context(text, found.start(), found.end()),
                "confidence": confidence,
                "figure_id": alias_row["figure_id"],
                "canonical_name": alias_row["canonical_name"],
                "ontology_default": alias_row["ontology_default"],
                "humanoid_degree": alias_row["humanoid_degree"],
                "involves_indigenous_knowledge": alias_row["involves_indigenous_knowledge"],
            }
        )
    return matches


def publicness_code(publicness_level: str | None) -> str:
    mapping = {
        "open_full_text": "open_article",
        "public_metadata": "public_metadata",
        "public_page": "public_heritage_page",
        "restricted_excluded": "restricted_excluded",
    }
    return mapping.get(publicness_level or "", "open_article")


def classify_record(
    conn: sqlite3.Connection,
    record_id: int,
    noise_rules_path: str | Path = DEFAULT_NOISE_RULES_PATH,
) -> None:
    record = conn.execute("SELECT * FROM records WHERE record_id = ?", (record_id,)).fetchone()
    if record is None:
        raise ValueError(f"No record found for record_id {record_id}")
    record_figure = None
    if record["figure_id"]:
        record_figure = conn.execute(
            """
            SELECT canonical_name, ontology_default, humanoid_degree,
                   involves_indigenous_knowledge
            FROM figures
            WHERE figure_id = ?
            """,
            (record["figure_id"],),
        ).fetchone()

    text = "\n".join(
        part
        for part in [
            record["title"] or "",
            record["snippet"] or "",
            _read_record_text(record),
        ]
        if part
    )
    patterns = load_noise_patterns(noise_rules_path)
    noise_pattern = contains_noise_pattern(text, patterns)

    conn.execute("DELETE FROM record_alias_matches WHERE record_id = ?", (record_id,))
    matches = match_aliases(conn, record_id, text)
    for match in matches:
        conn.execute(
            """
            INSERT INTO record_alias_matches (
                record_id, alias_id, matched_text, match_context, confidence
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                match["record_id"],
                match["alias_id"],
                match["matched_text"],
                match["match_context"],
                match["confidence"],
            ),
        )

    primary = matches[0] if matches else {}
    if not primary and record_figure:
        primary = {
            "canonical_name": record_figure["canonical_name"],
            "matched_text": None,
            "ontology_default": record_figure["ontology_default"],
            "humanoid_degree": record_figure["humanoid_degree"],
            "involves_indigenous_knowledge": record_figure["involves_indigenous_knowledge"],
        }
    ethics_flag = "ok_public"
    if record["publicness_level"] == "restricted_excluded":
        ethics_flag = "restricted_exclude"
    elif primary.get("involves_indigenous_knowledge"):
        ethics_flag = "caution_indigenous_knowledge"

    relevance = "noise" if noise_pattern else "needs_review"
    notes = "Initial rule-based coding; requires human review."
    if noise_pattern:
        notes = f"Obvious noise pattern matched: {noise_pattern}. Requires confirmation."

    conn.execute(
        """
        INSERT INTO coding (
            record_id, canonical_figure_guess, figure_name_as_printed,
            variant_normalisation, ontology_code, humanoid_degree_code,
            source_voice, genre, publicness_code, relevance_code, ethics_flag,
            notes, coded_by, coded_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'unknown', 'unknown', ?, ?, ?, ?, 'system_seed', ?)
        ON CONFLICT(record_id) DO UPDATE SET
            canonical_figure_guess = excluded.canonical_figure_guess,
            figure_name_as_printed = excluded.figure_name_as_printed,
            variant_normalisation = excluded.variant_normalisation,
            ontology_code = excluded.ontology_code,
            humanoid_degree_code = excluded.humanoid_degree_code,
            publicness_code = excluded.publicness_code,
            relevance_code = excluded.relevance_code,
            ethics_flag = excluded.ethics_flag,
            notes = excluded.notes,
            coded_by = excluded.coded_by,
            coded_at = excluded.coded_at
        """,
        (
            record_id,
            primary.get("canonical_name"),
            primary.get("matched_text"),
            primary.get("matched_text"),
            primary.get("ontology_default"),
            primary.get("humanoid_degree"),
            publicness_code(record["publicness_level"]),
            relevance,
            ethics_flag,
            notes,
            utc_now_iso(),
        ),
    )


def classify_uncoded_records(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        SELECT r.record_id
        FROM records r
        LEFT JOIN coding c ON c.record_id = r.record_id
        WHERE c.record_id IS NULL
        ORDER BY r.record_id
        """
    ).fetchall()
    for row in rows:
        classify_record(conn, int(row["record_id"]))
    return len(rows)
