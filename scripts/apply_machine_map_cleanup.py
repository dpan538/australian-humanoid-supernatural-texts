#!/usr/bin/env python3
"""Apply machine-suggested map cleanup only when safety checks pass."""

from __future__ import annotations

import argparse
import csv
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import column_exists, now_iso, table_exists, write_csv


APPLIED_FIELDS = [
    "record_id",
    "narrative_unit_id",
    "legacy_map_id",
    "machine_bucket",
    "machine_confidence",
    "hard_fail_reasons",
    "cleanup_action",
    "status",
    "details",
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def has_count_conflict(reconciliation_path: Path) -> bool:
    if not reconciliation_path.exists():
        return True
    text = reconciliation_path.read_text(encoding="utf-8")
    return "count_conflict_resolved: `true`" not in text


def manifest_missing(reconciliation_path: Path) -> bool:
    manifest = reconciliation_path.with_name("frontend_map_manifest.json")
    return not manifest.exists()


def auto_apply_eligible(row: dict[str, Any], min_confidence: float) -> tuple[bool, str]:
    try:
        confidence = float(row.get("machine_confidence") or 0)
    except ValueError:
        confidence = 0.0
    bucket = str(row.get("machine_bucket") or "")
    reasons = str(row.get("hard_fail_reasons") or "").lower()
    ethics = str(row.get("ethics_flags_json") or "").lower()
    if confidence < min_confidence:
        return False, "below_min_confidence"
    if any(token in ethics for token in ["indigenous", "aboriginal", "torres", "sensitive", "restricted"]):
        return False, "sensitive_rows_require_human_review"
    if bucket in {"RED_DEMOTE_ELIGIBLE", "RED_SUPPRESS_ELIGIBLE"}:
        return False, "refuse_legacy_red_bucket_requires_public_prefixed_rescore"
    if bucket in {"NONPUBLIC_IGNORE", "HOLD_UNKNOWN_POPULATION"}:
        return False, "refuse_nonpublic_or_unknown_population"
    if bucket == "RED_PUBLIC_SUPPRESS_ELIGIBLE" and (
        "sensitive_without_display_decision" in reasons or "display_allowed_zero_or_suppressed" in reasons
        or "display_suppressed" in reasons
    ):
        return True, "suppress_public_map"
    deterministic_demote = any(
        token in reasons
        for token in [
            "invalid_location_role",
            "missing_or_outside_australia_coordinates",
            "coordinates_outside_australia",
        ]
    )
    if bucket == "RED_PUBLIC_DEMOTE_ELIGIBLE" and deterministic_demote:
        return True, "demote_to_unmapped"
    return False, "not_red_deterministic_cleanup"


def make_backup(db_path: Path, backup_dir: Path, run_id: str) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{db_path.stem}_{run_id}_{now_iso().replace(':', '').replace('+', 'Z')}.sqlite"
    shutil.copy2(db_path, backup)
    return backup


def apply_row(conn: sqlite3.Connection, row: dict[str, Any], action: str) -> tuple[str, str]:
    narrative_location_id = str(row.get("legacy_map_id") or "").strip()
    narrative_id = str(row.get("narrative_unit_id") or "").strip()
    if action == "demote_to_unmapped":
        if narrative_location_id and table_exists(conn, "narrative_locations") and column_exists(conn, "narrative_locations", "review_status"):
            conn.execute(
                "UPDATE narrative_locations SET review_status = ? WHERE narrative_location_id = ?",
                ("machine_demoted_unmapped", narrative_location_id),
            )
            return "applied", "narrative_locations.review_status set to machine_demoted_unmapped"
        return "manual_action_required", "No safe narrative_locations key available."
    if action == "suppress_public_map":
        if narrative_id and table_exists(conn, "narrative_units") and column_exists(conn, "narrative_units", "display_mode"):
            conn.execute(
                "UPDATE narrative_units SET display_mode = ? WHERE narrative_id = ?",
                ("suppressed", narrative_id),
            )
            return "applied", "narrative_units.display_mode set to suppressed"
        return "manual_action_required", "No safe narrative_units key available."
    return "manual_action_required", f"Unsupported action {action}"


def write_report(path: Path, run_id: str, blocked: bool, dry_run: bool, rows: list[dict[str, Any]], backup: Path | None) -> None:
    lines = [
        "# Machine Map Cleanup Apply Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'dry-run' if dry_run else 'execute'}`",
        f"- Blocked: `{blocked}`",
        f"- Rows considered/applied: `{len(rows)}`",
        f"- Backup DB: `{backup or ''}`",
        "",
        "## Results",
    ]
    lines.extend([f"- `{row.get('status')}`: {row.get('cleanup_action')} {row.get('record_id') or row.get('narrative_unit_id')}" for row in rows] or ["- No rows eligible."])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_cleanup(
    db_path: Path,
    scores_path: Path,
    reconciliation_path: Path,
    run_id: str,
    out_csv: Path,
    report_path: Path,
    execute: bool,
    backup_dir: Path | None,
    min_confidence: float,
) -> dict[str, Any]:
    rows = read_rows(scores_path)
    blocked = has_count_conflict(reconciliation_path) or manifest_missing(reconciliation_path)
    block_reason = "frontend_manifest_missing" if manifest_missing(reconciliation_path) else "count_conflict_unresolved"
    results: list[dict[str, Any]] = []
    for row in rows:
        eligible, action_or_reason = auto_apply_eligible(row, min_confidence)
        if not eligible:
            continue
        result = {field: row.get(field, "") for field in APPLIED_FIELDS}
        result["cleanup_action"] = action_or_reason
        result["status"] = "blocked" if blocked else ("would_apply" if not execute else "pending")
        result["details"] = block_reason if blocked else ""
        results.append(result)

    backup: Path | None = None
    if execute and not blocked:
        if not backup_dir:
            blocked = True
            for result in results:
                result["status"] = "blocked"
                result["details"] = "execute_requires_backup_db"
        else:
            backup = make_backup(db_path, backup_dir, run_id)
            with sqlite3.connect(db_path) as conn:
                for result in results:
                    status, details = apply_row(conn, result, str(result.get("cleanup_action") or ""))
                    result["status"] = status
                    result["details"] = details
                conn.commit()
    elif execute and blocked:
        for result in results:
            result["status"] = "blocked"
            result["details"] = block_reason

    write_csv(out_csv, results, APPLIED_FIELDS)
    write_report(report_path, run_id, blocked, not execute, results, backup)
    return {"blocked": blocked, "rows": len(results), "backup": backup}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--scores", required=True, help="map evidence score CSV")
    parser.add_argument("--reconciliation", required=True, help="canonical count reconciliation report")
    parser.add_argument("--run-id", required=True, help="cleanup run id")
    parser.add_argument("--out", required=True, help="applied-row CSV output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="preview only")
    mode.add_argument("--execute", action="store_true", help="execute safe cleanup")
    parser.add_argument("--backup-db", help="backup directory required for execute")
    parser.add_argument("--min-confidence", type=float, default=0.95)
    args = parser.parse_args()
    summary = run_cleanup(
        Path(args.db),
        Path(args.scores),
        Path(args.reconciliation),
        args.run_id,
        Path(args.out),
        Path(args.report),
        bool(args.execute),
        Path(args.backup_db) if args.backup_db else None,
        args.min_confidence,
    )
    print(f"Machine map cleanup rows: {summary['rows']}")
    print(f"Blocked: {summary['blocked']}")


if __name__ == "__main__":
    main()
