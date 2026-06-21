#!/usr/bin/env python3
"""Reject audited false-positive collection candidates without deleting rows."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "false_positive_rejections_20260621.md"


def reject_victorian_era_ghost_false_positives(db_path: str, dry_run: bool) -> list[dict[str, object]]:
    rejected: list[dict[str, object]] = []
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT candidate_id, run_id, source_label, source_type, title, location_text, url
            FROM collection_candidates_v2
            WHERE candidate_status = 'accepted'
              AND lower(source_label) = 'ghost'
              AND source_type LIKE 'internet_archive%'
              AND (
                    lower(title) LIKE '%victorian ghost%'
                 OR lower(title) LIKE '%victorian archives%'
                 OR lower(title) LIKE '%victorian %'
                 OR lower(title) LIKE '%angelica : a novel%'
                 OR lower(title) LIKE '%miss neville%'
                 OR lower(title) LIKE '%nineteenth-century literature criticism%'
              )
            ORDER BY candidate_id
            """
        ).fetchall()
        for row in rows:
            title = row["title"] or ""
            haystack = " ".join(str(row[key] or "") for key in ("title", "location_text"))
            australia_signal = re.search(
                r"\b(australia|australian|melbourne|gippsland|beechworth|ararat|ballarat|victoria,\s*australia)\b",
                haystack,
                re.I,
            )
            false_positive_signal = re.search(
                r"\b(victorian|novel|literature|wales|oxford|virago|phantom coach|miss neville|angelica)\b",
                title,
                re.I,
            )
            if not false_positive_signal:
                continue
            if australia_signal and not re.search(r"\b(novel|literature|wales|oxford|virago|phantom coach|miss neville|angelica)\b", title, re.I):
                continue
            rejected.append(dict(row))
            if dry_run:
                continue
            conn.execute(
                """
                UPDATE collection_candidates_v2
                SET candidate_status = 'rejected',
                    acceptance_decision = 'not_accepted',
                    rejection_reason = 'victorian_era_or_literary_false_positive_not_australia',
                    updated_at = ?
                WHERE candidate_id = ?
                """,
                (utc_now_iso(), row["candidate_id"]),
            )
        if not dry_run:
            conn.commit()
    return rejected


def write_report(path: Path, rows: list[dict[str, object]], dry_run: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# False-Positive Candidate Rejections",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Dry run: `{dry_run}`",
        f"- Rejected rows: {len(rows)}",
        "",
        "## Rules",
        "- Reject Internet Archive ghost candidates where `Victorian` means literary period or non-Australian archive context rather than Victoria, Australia.",
        "- No rows are deleted; candidates remain auditable with a rejection reason.",
        "",
        "## Rows",
    ]
    for row in rows:
        lines.append(f"- `{row['candidate_id']}` {row['title']} | {row['url']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = reject_victorian_era_ghost_false_positives(args.db, args.dry_run)
    write_report(Path(args.report), rows, args.dry_run)
    print(json.dumps({"dry_run": args.dry_run, "rejected_rows": len(rows)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
