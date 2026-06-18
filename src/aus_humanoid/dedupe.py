"""Conservative duplicate marking helpers.

Duplicates are annotated in separate tables. Records are never deleted.
"""

from __future__ import annotations

import difflib
import itertools
import re
import sqlite3
from collections import defaultdict
from typing import Iterable

from .normalise import normalise_text


TOKEN_RE = re.compile(r"[a-z0-9]+")
STOPWORDS = {"a", "an", "and", "in", "of", "on", "the", "to"}


def title_tokens(title: str | None) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(normalise_text(title))
        if token not in STOPWORDS
    }


def token_overlap(left: str | None, right: str | None) -> float:
    left_tokens = title_tokens(left)
    right_tokens = title_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def title_similarity(left: str | None, right: str | None) -> float:
    left_norm = normalise_text(left)
    right_norm = normalise_text(right)
    if not left_norm or not right_norm:
        return 0.0
    return max(
        difflib.SequenceMatcher(None, left_norm, right_norm).ratio(),
        token_overlap(left_norm, right_norm),
    )


def _upsert_group(
    conn: sqlite3.Connection,
    group_key: str,
    record_ids: Iterable[int],
    notes: str,
) -> int:
    ids = sorted(set(int(record_id) for record_id in record_ids))
    canonical = ids[0] if ids else None
    conn.execute(
        """
        INSERT INTO dedupe_groups (group_key, canonical_record_id, notes)
        VALUES (?, ?, ?)
        ON CONFLICT(group_key) DO UPDATE SET
            canonical_record_id = excluded.canonical_record_id,
            notes = excluded.notes
        """,
        (group_key, canonical, notes),
    )
    row = conn.execute(
        "SELECT dedupe_group_id FROM dedupe_groups WHERE group_key = ?",
        (group_key,),
    ).fetchone()
    return int(row["dedupe_group_id"])


def _mark_records(
    conn: sqlite3.Connection,
    group_id: int,
    record_ids: Iterable[int],
    duplicate_type: str,
    score: float,
) -> None:
    for record_id in sorted(set(record_ids)):
        conn.execute(
            """
            INSERT OR REPLACE INTO record_dedupe (
                record_id, dedupe_group_id, duplicate_type, similarity_score
            ) VALUES (?, ?, ?, ?)
            """,
            (record_id, group_id, duplicate_type, score),
        )


def mark_duplicates(conn: sqlite3.Connection) -> int:
    """Find simple duplicates and populate dedupe tables."""

    rows = conn.execute(
        """
        SELECT record_id, url, title, year, publication
        FROM records
        ORDER BY record_id
        """
    ).fetchall()
    groups_created = 0

    by_url: dict[str, list[int]] = defaultdict(list)
    by_title_year_pub: dict[tuple[str, int | None, str], list[int]] = defaultdict(list)
    for row in rows:
        if row["url"]:
            by_url[normalise_text(row["url"])].append(int(row["record_id"]))
        key = (
            normalise_text(row["title"]),
            row["year"],
            normalise_text(row["publication"]),
        )
        if key[0] and key[1] and key[2]:
            by_title_year_pub[key].append(int(row["record_id"]))

    for url, record_ids in by_url.items():
        if len(record_ids) < 2:
            continue
        group_id = _upsert_group(conn, f"url:{url}", record_ids, "Exact URL duplicate.")
        _mark_records(conn, group_id, record_ids, "exact_duplicate", 1.0)
        groups_created += 1

    for key, record_ids in by_title_year_pub.items():
        if len(record_ids) < 2:
            continue
        group_key = "title_year_publication:" + "|".join(str(part) for part in key)
        group_id = _upsert_group(
            conn,
            group_key,
            record_ids,
            "Same normalised title, year, and publication.",
        )
        _mark_records(conn, group_id, record_ids, "same_title_different_issue", 1.0)
        groups_created += 1

    for left, right in itertools.combinations(rows, 2):
        if left["year"] != right["year"]:
            continue
        if not left["title"] or not right["title"]:
            continue
        similarity = title_similarity(left["title"], right["title"])
        if similarity < 0.9:
            continue
        record_ids = [int(left["record_id"]), int(right["record_id"])]
        group_key = f"similar_title:{left['year']}:{min(record_ids)}:{max(record_ids)}"
        group_id = _upsert_group(
            conn,
            group_key,
            record_ids,
            "High title similarity within the same year.",
        )
        _mark_records(conn, group_id, record_ids, "near_duplicate", similarity)
        groups_created += 1

    return groups_created
