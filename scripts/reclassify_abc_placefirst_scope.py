#!/usr/bin/env python3
"""Suppress false-positive ABC place-first records from public export."""

from __future__ import annotations

import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import utc_now_iso

EXPORT_CSV = ROOT / "data" / "exports" / "v2" / "abc_placefirst_scope_reclassification.csv"
REPORT_MD = ROOT / "data" / "processed" / "v2" / "abc_placefirst_scope_reclassification.md"

SUPPRESS = {
    3964: "place not source-stated in retained excerpt; general hidden-object/evil-spirit discussion rather than distinct mapped ABC place narrative",
    3965: "ghost mushrooms/bioluminescence false positive; no supernatural humanoid narrative",
    3967: "fictional radio-play segment; no source-grounded local supernatural place record",
    3969: "book-title segment for The Ghost Theatre; non-Australian literary item, not local supernatural place evidence",
    3971: "BTN quiz item about a non-Australian dog-owned mansion; not Australian place narrative evidence",
    3972: "haunted by asthma attack is metaphorical usage",
    3973: "ghost reef is ecological metaphor, not humanoid supernatural evidence",
    3974: "ghost-like newt metaphor, not supernatural humanoid evidence",
    3977: "haunted by failure is metaphorical literary criticism",
    3979: "duplicate/lead segment for Fisher's Ghost; distinct scoped ABC item retained separately",
    3981: "religion/Jung discussion from Spirit of Things; no source-grounded supernatural humanoid place narrative",
    3982: "Science Show/Daleks segment; no source-grounded supernatural humanoid place narrative",
    3983: "political metaphor 'ghost of Workchoices'; no supernatural narrative evidence",
    3984: "unrelated Awaye biographical segment; no source-stated ghost/apparition place narrative",
    3987: "fictional radio-play episode; not a source-grounded local supernatural place record",
    4000: "mapped place appears only in generated coordinate note/metadata, not in retained source evidence excerpt",
    4001: "mapped place appears only in generated coordinate note/metadata, not in retained source evidence excerpt",
    4002: "biographical Territory interview; no explicit supernatural humanoid or apparition evidence in retained source excerpt",
    4003: "Ghost Songs program is culturally sensitive music-context material; Darwin map point is not the source-stated narrative place",
    4004: "Ghost Songs program names a Belyuen dream-song context rather than Darwin; high-sensitivity place evidence requires explicit review before public mapping",
    4005: "medical documentary false positive; no supernatural humanoid or apparition evidence in retained source excerpt",
    4006: "warbird recovery documentary false positive; lost planes/men context is not a supernatural humanoid narrative",
    4007: "BTN classroom episode false positive; no Australian supernatural humanoid narrative evidence",
    4008: "mining feature false positive; no supernatural humanoid or apparition evidence in retained source excerpt",
    4009: "duplicate Port Arthur ghost-tour narrative already represented by an earlier ABC canonical record",
    4011: "fishing segment false positive; mapped Woodman Point appears only in route metadata, not in source narrative evidence",
    4013: "music-program segment false positive; no source-grounded Fremantle supernatural humanoid narrative evidence",
}


def main() -> None:
    rows: list[dict[str, str]] = []
    now = utc_now_iso()
    with connect(DEFAULT_DB_PATH) as conn:
        for record_id, note in SUPPRESS.items():
            row = conn.execute(
                """
                SELECT r.record_id, r.title, r.url, s.source_name, c.relevance_code, c.notes
                FROM records r
                JOIN sources s ON s.source_id = r.source_id
                LEFT JOIN coding c ON c.record_id = r.record_id
                WHERE r.record_id = ?
                """,
                (record_id,),
            ).fetchone()
            if not row:
                rows.append({"record_id": str(record_id), "decision": "missing", "review_note": note})
                continue
            conn.execute(
                """
                UPDATE coding
                SET relevance_code = 'scope_excluded',
                    notes = TRIM(COALESCE(notes, '') || char(10) || ?),
                    coded_at = ?
                WHERE record_id = ?
                """,
                (f"ABC place-first scope reclassification 2026-06-22: {note}", now, record_id),
            )
            rows.append(
                {
                    "record_id": str(record_id),
                    "title": row["title"] or "",
                    "url": row["url"] or "",
                    "source_name": row["source_name"] or "",
                    "previous_relevance_code": row["relevance_code"] or "",
                    "decision": "scope_excluded",
                    "review_note": note,
                }
            )
        conn.commit()

    EXPORT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = ["record_id", "title", "url", "source_name", "previous_relevance_code", "decision", "review_note"]
    with EXPORT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    retained = []
    with sqlite3.connect(DEFAULT_DB_PATH) as raw:
        raw.row_factory = sqlite3.Row
        retained = raw.execute(
            """
            SELECT r.record_id, r.title
            FROM records r
            JOIN sources s ON s.source_id = r.source_id
            JOIN coding c ON c.record_id = r.record_id
            WHERE s.source_name = 'Australian Broadcasting Corporation'
              AND COALESCE(c.relevance_code, '') != 'scope_excluded'
            ORDER BY r.record_id
            """
        ).fetchall()

    lines = [
        "# ABC Place-First Scope Reclassification",
        "",
        f"- Generated: `{now}`",
        f"- Suppressed false positives: `{sum(1 for row in rows if row['decision'] == 'scope_excluded')}`",
        f"- Retained ABC records after review: `{len(retained)}`",
        f"- CSV: `{EXPORT_CSV.relative_to(ROOT)}`",
        "",
        "## Retained Records",
    ]
    for row in retained:
        lines.append(f"- `{row['record_id']}` {row['title']}")
    lines.extend(["", "## Suppressed Records"])
    for row in rows:
        lines.append(f"- `{row['record_id']}` {row.get('title', '')}: {row['review_note']}")
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"suppressed": sum(1 for row in rows if row["decision"] == "scope_excluded"), "retained": len(retained)})


if __name__ == "__main__":
    main()
