#!/usr/bin/env python3
"""Detect no-auth autoharvest policy violations."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists


API_MARKERS = ["api.trove.nla.gov.au", "googleapis.com", "api.bing.microsoft.com", "bing.microsoft.com"]


def count(conn: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    return int(conn.execute(query, params).fetchone()[0] or 0)


def run_watchdog(db_path: Path, run_id: str, out_path: Path) -> dict[str, int | bool]:
    hard: list[str] = []
    warnings: list[str] = []
    with sqlite3.connect(db_path) as conn:
        if table_exists(conn, "harvest_frontier"):
            api_routes = count(conn, "SELECT COUNT(*) FROM harvest_frontier WHERE run_id=? AND (lower(url) LIKE '%api.trove.nla.gov.au%' OR lower(url) LIKE '%googleapis.com%' OR lower(url) LIKE '%bing.microsoft.com%')", (run_id,))
            if api_routes:
                hard.append(f"api_route_use:{api_routes}")
            robots = count(conn, "SELECT COUNT(*) FROM harvest_frontier WHERE run_id=? AND status='fetched' AND robots_status NOT IN ('allowed', 'fetched')", (run_id,))
            if robots:
                hard.append(f"robots_violation:{robots}")
        if table_exists(conn, "provisional_records"):
            sensitive = count(conn, "SELECT COUNT(*) FROM provisional_records WHERE run_id=? AND ethics_status IN ('sensitive','restricted','manual_only')", (run_id,))
            if sensitive:
                hard.append(f"sensitive_route_leakage:{sensitive}")
            restricted = count(conn, "SELECT COUNT(*) FROM provisional_records WHERE run_id=? AND rights_status IN ('restricted','paywalled','login_required')", (run_id,))
            if restricted:
                hard.append(f"restricted_rights_leakage:{restricted}")
        if table_exists(conn, "harvest_pages"):
            pdf_text = count(conn, "SELECT COUNT(*) FROM harvest_pages WHERE run_id=? AND lower(COALESCE(stored_body_path,'')) LIKE '%.pdf%'", (run_id,))
            if pdf_text:
                hard.append(f"pdf_body_stored:{pdf_text}")
        if table_exists(conn, "harvest_runs"):
            note_row = conn.execute("SELECT notes FROM harvest_runs WHERE run_id=?", (run_id,)).fetchone()
            notes = note_row[0] if note_row else ""
            marker = "baseline_public_records:"
            if marker in str(notes) and table_exists(conn, "records"):
                try:
                    baseline = int(str(notes).split(marker, 1)[1].split()[0])
                    current = count(conn, "SELECT COUNT(*) FROM records")
                    if current != baseline:
                        hard.append(f"public_records_count_changed:{baseline}->{current}")
                except ValueError:
                    warnings.append("baseline_public_records_unparseable")
        if hard and table_exists(conn, "harvest_runs"):
            conn.execute("UPDATE harvest_runs SET status='safety_stopped', stop_reason=? WHERE run_id=?", (";".join(hard), run_id))
            conn.commit()
    lines = [
        "# Autoharvest Watchdog",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Hard violations: `{len(hard)}`",
        f"- Safety stopped: `{str(bool(hard)).lower()}`",
        "",
        "## Hard Violations",
    ]
    lines.extend([f"- {item}" for item in hard] or ["- None"])
    lines.extend(["", "## Warnings"])
    lines.extend([f"- {item}" for item in warnings] or ["- None"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"hard": len(hard), "safety_stopped": bool(hard)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = run_watchdog(Path(args.db), args.run_id, Path(args.out))
    print(f"Wrote watchdog report: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
