#!/usr/bin/env python3
"""Suppress recent public-domain fiction rows that fail the strict scope gate."""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "australian_humanoid_figures.sqlite"
REPORT_MD = ROOT / "data" / "processed" / "v2" / "recent_fiction_scope_reclassification.md"
REPORT_CSV = ROOT / "data" / "exports" / "v2" / "recent_fiction_scope_reclassification.csv"

START_RECORD_ID = 2644


def has_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def label_from_title(title: str) -> str:
    return title.split(" in ", 1)[0].strip().lower()


def strict_decision(title: str, snippet: str) -> tuple[bool, str]:
    label = label_from_title(title)
    text = re.sub(r"\s+", " ", snippet.lower())
    strong = {
        "apparition",
        "devil-devil",
        "evil spirit",
        "fairies",
        "fairy",
        "ghost",
        "ghosts",
        "haunted house",
        "magician",
        "phantom",
        "spectral",
        "spectre",
        "spirit being",
        "spirit person",
        "supernatural",
        "witch",
        "wizard",
    }
    mythic = strong | {"legend", "myth", "ogre", "giant man"}
    if label in {"little man", "little woman", "little old man", "little old woman"}:
        return (has_any(text, strong), "ordinary_human_little_person_description")
    if label in {"spirit", "spirits"}:
        return (has_any(text, strong | {"dead", "medicine man"}), "idiomatic_mood_or_alcohol_spirit")
    if label == "devil":
        return (has_any(text, {"devil-devil", "evil spirit", "ghost", "phantom", "supernatural", "witch", "wizard"}), "idiomatic_or_expletive_devil")
    if label == "giant":
        return (has_any(text, mythic), "ordinary_or_metaphorical_giant")
    if label in {"apparition", "phantom", "haunted"}:
        return (has_any(text, strong | {"haunted house"}), "non_supernatural_appearance_term")
    if label in {"ghost", "ghosts"}:
        if "ghost of a chance" in text or re.search(r"ghost of (all )?(his|her|their|my|your|our|past)", text):
            return (False, "metaphorical_ghost_phrase")
        return (True, "")
    return (True, "")


def main() -> None:
    REPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT r.record_id, r.title, r.snippet, s.source_name, s.source_type,
               c.relevance_code, c.notes, m.candidate_id
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN coding c ON c.record_id = r.record_id
        LEFT JOIN collection_candidate_record_mappings m ON m.record_id = r.record_id
        WHERE r.record_id >= ?
          AND s.source_type = 'public_domain_ebook'
          AND COALESCE(c.relevance_code, '') != 'scope_excluded'
        ORDER BY r.record_id
        """,
        (START_RECORD_ID,),
    ).fetchall()
    report_rows: list[dict[str, str]] = []
    suppressed = 0
    retained = 0
    for row in rows:
        keep, reason = strict_decision(row["title"] or "", row["snippet"] or "")
        decision = "retain" if keep else "scope_exclude"
        if keep:
            retained += 1
        else:
            suppressed += 1
            note = f"strict_fiction_scope_reclassification:{reason}"
            conn.execute(
                """
                UPDATE coding
                SET relevance_code = 'scope_excluded',
                    notes = TRIM(COALESCE(notes, '') || char(10) || ?)
                WHERE record_id = ?
                """,
                (note, row["record_id"]),
            )
            if row["candidate_id"]:
                conn.execute(
                    """
                    UPDATE collection_candidates_v2
                    SET rejection_reason = ?,
                        updated_at = datetime('now')
                    WHERE candidate_id = ?
                    """,
                    (note, row["candidate_id"]),
                )
        report_rows.append(
            {
                "record_id": str(row["record_id"]),
                "candidate_id": str(row["candidate_id"] or ""),
                "source_name": row["source_name"] or "",
                "title": row["title"] or "",
                "source_label": label_from_title(row["title"] or ""),
                "decision": decision,
                "reason": reason,
                "evidence_excerpt": row["snippet"] or "",
            }
        )
    conn.commit()
    with REPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "record_id",
            "candidate_id",
            "source_name",
            "title",
            "source_label",
            "decision",
            "reason",
            "evidence_excerpt",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)
    lines = [
        "# Recent Fiction Scope Reclassification",
        "",
        f"- Start record_id: `{START_RECORD_ID}`",
        f"- Reviewed recent public-domain ebook records: `{len(report_rows)}`",
        f"- Retained: `{retained}`",
        f"- Scope-excluded: `{suppressed}`",
        "",
        "Rows were not deleted. Out-of-scope rows were marked `scope_excluded` in `coding`; linked staging candidates remain accepted so the promotion mapping invariant stays auditable.",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"reviewed": len(report_rows), "retained": retained, "scope_excluded": suppressed})


if __name__ == "__main__":
    main()
