#!/usr/bin/env python3
"""Create compact human-review packets for collection candidates."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv


CANDIDATE_FIELDS = [
    "candidate_id",
    "target_state",
    "time_band",
    "source_name",
    "term_family",
    "title",
    "date_published",
    "publication",
    "url",
    "snippet",
    "query_string",
    "evidence_or_discovery",
    "source_tier",
    "mappability_hint",
    "duplicate_key",
    "review_status",
    "accepted_record_type",
    "accepted_evidence_source_name",
    "accepted_evidence_source_url",
    "accepted_original_source_name",
    "accepted_publication_date",
    "evidence_strength",
    "source_stated_place_text",
    "location_role",
    "jurisdiction_state",
    "ethics_review_status",
    "display_decision",
    "reviewer_notes",
]

SOURCE_CHAIN_FIELDS = [
    "candidate_id",
    "discovery_source_name",
    "access_source_name",
    "original_source_name",
    "evidence_source_name",
    "evidence_source_tier",
    "source_chain_review_status",
    "reviewer_corrected_original_source_name",
    "reviewer_corrected_evidence_source_name",
    "reviewer_corrected_evidence_source_url",
    "reviewer_notes",
]

GEOCODE_FIELDS = [
    "candidate_id",
    "source_stated_place_text",
    "jurisdiction_state",
    "location_role",
    "mappability_hint",
    "geocode_confidence",
    "display_allowed",
    "review_status",
    "reviewer_notes",
]


def rows_from_db(db_path: Path, run_id: str, max_items: int) -> list[dict[str, Any]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "collection_candidates"):
            return []
        rows = conn.execute(
            """
            SELECT * FROM collection_candidates
            WHERE run_id = ?
            ORDER BY target_state, time_band, source_name, term_family, title
            LIMIT ?
            """,
            (run_id, max_items),
        ).fetchall()
        return [dict(row) for row in rows]


def rows_from_review_csv(run_id: str, max_items: int) -> list[dict[str, Any]]:
    path = ROOT / "data" / "review" / "v2" / f"{run_id}_candidate_review.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))[:max_items]


def normalize_candidate(row: dict[str, Any]) -> dict[str, Any]:
    normalized = {field: row.get(field, "") for field in CANDIDATE_FIELDS}
    normalized["jurisdiction_state"] = row.get("jurisdiction_state") or row.get("target_state") or row.get("inferred_state") or ""
    normalized["review_status"] = row.get("review_status") or "needs_review"
    return normalized


def source_chain_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id", ""),
        "discovery_source_name": row.get("source_name", ""),
        "access_source_name": row.get("source_name", ""),
        "original_source_name": row.get("publication", ""),
        "evidence_source_name": row.get("publication") or row.get("source_name", ""),
        "evidence_source_tier": row.get("source_tier", ""),
        "source_chain_review_status": "needs_review",
        "reviewer_corrected_original_source_name": "",
        "reviewer_corrected_evidence_source_name": "",
        "reviewer_corrected_evidence_source_url": "",
        "reviewer_notes": "",
    }


def geocode_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": row.get("candidate_id", ""),
        "source_stated_place_text": row.get("source_stated_place_text") or row.get("target_locality") or "",
        "jurisdiction_state": row.get("target_state") or row.get("inferred_state") or "",
        "location_role": row.get("location_role", ""),
        "mappability_hint": row.get("mappability_hint", ""),
        "geocode_confidence": "needs_review",
        "display_allowed": 0,
        "review_status": "needs_review",
        "reviewer_notes": "",
    }


def write_candidate_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[
            (
                str(row.get("target_state") or "unknown"),
                str(row.get("time_band") or "unknown"),
                str(row.get("source_name") or "unknown"),
                str(row.get("term_family") or "unknown"),
            )
        ].append(row)
    lines = ["# Candidate Review", "", f"- Generated: `{now_iso()}`", f"- Candidates: `{len(rows)}`"]
    for key in sorted(grouped):
        state, time_band, source, term_family = key
        lines.extend(["", f"## {state} / {time_band} / {source} / {term_family}"])
        for row in grouped[key][:50]:
            lines.extend(
                [
                    "",
                    f"### {row.get('candidate_id')}",
                    f"- Title: {row.get('title') or ''}",
                    f"- Date: {row.get('date_published') or ''}",
                    f"- Publication: {row.get('publication') or ''}",
                    f"- URL: {row.get('url') or ''}",
                    f"- Query: {row.get('query_string') or ''}",
                    f"- Mappability: {row.get('mappability_hint') or ''}",
                    f"- Duplicate key: {row.get('duplicate_key') or ''}",
                    f"- Snippet: {row.get('snippet') or ''}",
                ]
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(path: Path, rows: list[dict[str, Any]], run_id: str) -> None:
    state_counts = Counter(row.get("target_state") or "unknown" for row in rows)
    time_counts = Counter(row.get("time_band") or "unknown" for row in rows)
    source_counts = Counter(row.get("source_name") or "unknown" for row in rows)
    lines = [
        "# Review Packet Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Candidate rows: `{len(rows)}`",
        "",
        "## States",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in state_counts.most_common()] or ["- None"])
    lines.extend(["", "## Time Bands"])
    lines.extend([f"- `{key}`: {count}" for key, count in time_counts.most_common()] or ["- None"])
    lines.extend(["", "## Sources"])
    lines.extend([f"- `{key}`: {count}" for key, count in source_counts.most_common(20)] or ["- None"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_packet(db_path: Path, run_id: str, out_dir: Path, max_items: int) -> dict[str, Any]:
    rows = rows_from_db(db_path, run_id, max_items)
    source = "sqlite"
    if not rows:
        rows = rows_from_review_csv(run_id, max_items)
        source = "review_csv"
    candidates = [normalize_candidate(row) for row in rows]
    source_chains = [source_chain_row(row) for row in candidates]
    geocodes = [geocode_row(row) for row in candidates if row.get("mappability_hint") in {"high", "medium"} or row.get("source_stated_place_text")]

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "candidate_review.csv", candidates, CANDIDATE_FIELDS)
    write_candidate_markdown(out_dir / "candidate_review.md", candidates)
    write_csv(out_dir / "source_chain_review.csv", source_chains, SOURCE_CHAIN_FIELDS)
    write_csv(out_dir / "geocode_review.csv", geocodes, GEOCODE_FIELDS)
    write_summary(out_dir / "summary.md", candidates, run_id)
    return {"candidates": len(candidates), "geocodes": len(geocodes), "source": source, "out_dir": out_dir}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--run-id", required=True, help="collection run id")
    parser.add_argument("--out-dir", required=True, help="review packet directory")
    parser.add_argument("--max-items", type=int, default=200, help="max candidate rows")
    args = parser.parse_args()

    summary = make_packet(Path(args.db), args.run_id, Path(args.out_dir), args.max_items)
    print(f"Wrote review packet with {summary['candidates']} candidates from {summary['source']}: {summary['out_dir']}")


if __name__ == "__main__":
    main()
