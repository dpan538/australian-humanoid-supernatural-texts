#!/usr/bin/env python3
"""Apply human-reviewed legacy map flag triage decisions."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import normalize_space, now_iso, table_exists


ALLOWED_DECISIONS = {
    "keep_public_map_flag",
    "demote_to_unmapped",
    "suppress_public_map",
    "update_place_evidence",
    "update_geocode_review",
    "manual_sensitive_review",
}


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Review CSV is missing a header")
        required = {"legacy_map_id", "reviewer_decision"}
        missing = sorted(required - set(reader.fieldnames))
        if missing:
            raise ValueError(f"Review CSV missing required columns: {missing}")
        return [dict(row) for row in reader]


def ensure_release_gate_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS release_gate_results (
            gate_run_id TEXT,
            gate_name TEXT,
            gate_status TEXT,
            observed_value TEXT,
            threshold_value TEXT,
            details TEXT,
            created_at TEXT NOT NULL,
            PRIMARY KEY (gate_run_id, gate_name)
        )
        """
    )


def numeric_or_none(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def update_if_value(conn: sqlite3.Connection, sql: str, value: Any, row_id: str) -> int:
    if str(value or "").strip() == "":
        return 0
    conn.execute(sql, (value, row_id))
    return 1


def apply_v2_decision(conn: sqlite3.Connection, row: dict[str, str], run_id: str) -> tuple[str, str]:
    legacy_map_id = str(row.get("legacy_map_id") or "").strip()
    if not legacy_map_id.isdigit():
        return "manual_action_required", "legacy_map_id is not a V2 narrative_location_id"
    existing = conn.execute(
        "SELECT narrative_location_id, narrative_id, location_id FROM narrative_locations WHERE narrative_location_id = ?",
        (legacy_map_id,),
    ).fetchone()
    if not existing:
        return "manual_action_required", "narrative_location_id not found"

    decision = normalize_space(row.get("reviewer_decision"))
    note = f"{run_id}: {decision}"
    if row.get("reviewer_notes"):
        note += f" - {row['reviewer_notes']}"

    if decision == "keep_public_map_flag":
        conn.execute(
            "UPDATE narrative_locations SET review_status = COALESCE(NULLIF(review_status, ''), 'reviewed_keep_public_map_flag') WHERE narrative_location_id = ?",
            (legacy_map_id,),
        )
        return "updated", "kept public map flag"

    if decision == "manual_sensitive_review":
        conn.execute(
            "UPDATE narrative_locations SET review_status = ? WHERE narrative_location_id = ?",
            ("manual_sensitive_review_required", legacy_map_id),
        )
        return "updated", "marked manual sensitive review"

    if decision == "demote_to_unmapped":
        conn.execute(
            """
            UPDATE narrative_locations
            SET review_status = ?, confidence = COALESCE(NULLIF(confidence, ''), 'not_public_map_eligible')
            WHERE narrative_location_id = ?
            """,
            ("demoted_unmapped_by_legacy_map_triage", legacy_map_id),
        )
        return "updated", "demoted by review status; public exporter must respect review gate"

    if decision == "suppress_public_map":
        conn.execute(
            "UPDATE narrative_locations SET review_status = ?, confidence = ? WHERE narrative_location_id = ?",
            ("suppressed_public_map_by_legacy_map_triage", "not_public_map_eligible", legacy_map_id),
        )
        if table_exists(conn, "narrative_units"):
            conn.execute(
                "UPDATE narrative_units SET display_mode = 'suppressed', updated_at = COALESCE(updated_at, ?) WHERE narrative_id = ?",
                (now_iso(), existing["narrative_id"]),
            )
        return "updated", "suppressed public map flag by review status/display mode"

    if decision in {"update_place_evidence", "update_geocode_review"}:
        updates = 0
        updates += update_if_value(
            conn,
            "UPDATE narrative_locations SET location_text_as_printed = ? WHERE narrative_location_id = ?",
            row.get("corrected_source_stated_place_text"),
            legacy_map_id,
        )
        updates += update_if_value(
            conn,
            "UPDATE narrative_locations SET location_role = ? WHERE narrative_location_id = ?",
            row.get("corrected_location_role"),
            legacy_map_id,
        )
        updates += update_if_value(
            conn,
            "UPDATE narrative_locations SET location_precision = ? WHERE narrative_location_id = ?",
            row.get("corrected_coordinate_precision"),
            legacy_map_id,
        )
        updates += update_if_value(
            conn,
            "UPDATE narrative_locations SET confidence = ? WHERE narrative_location_id = ?",
            row.get("corrected_geocode_confidence"),
            legacy_map_id,
        )
        lat = numeric_or_none(row.get("corrected_lat"))
        lng = numeric_or_none(row.get("corrected_lng"))
        state = str(row.get("corrected_jurisdiction_state") or "").strip()
        if lat is not None:
            conn.execute("UPDATE locations SET latitude = ? WHERE location_id = ?", (lat, existing["location_id"]))
            updates += 1
        if lng is not None:
            conn.execute("UPDATE locations SET longitude = ? WHERE location_id = ?", (lng, existing["location_id"]))
            updates += 1
        if state:
            conn.execute("UPDATE locations SET state_territory = ? WHERE location_id = ?", (state, existing["location_id"]))
            updates += 1
        conn.execute(
            "UPDATE narrative_locations SET review_status = ? WHERE narrative_location_id = ?",
            ("reviewed_after_legacy_map_triage", legacy_map_id),
        )
        return "updated", f"updated {updates} evidence/geocode fields"

    return "manual_action_required", f"unsupported decision: {decision}"


def apply_decisions(db_path: Path, review_csv: Path, run_id: str, execute: bool) -> dict[str, Any]:
    rows = read_review_csv(review_csv)
    considered = [row for row in rows if normalize_space(row.get("reviewer_decision"))]
    invalid = [row for row in considered if normalize_space(row.get("reviewer_decision")) not in ALLOWED_DECISIONS]
    actions: list[dict[str, str]] = []

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        has_v2 = table_exists(conn, "narrative_locations") and table_exists(conn, "locations")
        for row in considered:
            decision = normalize_space(row.get("reviewer_decision"))
            if decision not in ALLOWED_DECISIONS:
                actions.append({"legacy_map_id": row.get("legacy_map_id", ""), "status": "invalid_decision", "detail": decision})
                continue
            if not has_v2:
                actions.append({"legacy_map_id": row.get("legacy_map_id", ""), "status": "manual_action_required", "detail": "V2 map tables missing"})
                continue
            if execute:
                status, detail = apply_v2_decision(conn, row, run_id)
            else:
                status, detail = "dry_run", f"would apply {decision}"
            actions.append({"legacy_map_id": row.get("legacy_map_id", ""), "status": status, "detail": detail})
        if execute:
            ensure_release_gate_table(conn)
            counts: dict[str, int] = {}
            for action in actions:
                counts[action["status"]] = counts.get(action["status"], 0) + 1
            for name, value in counts.items():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO release_gate_results (
                        gate_run_id, gate_name, gate_status, observed_value,
                        threshold_value, details, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        f"legacy_map_triage_{name}",
                        "WARN" if name == "manual_action_required" else "PASS",
                        str(value),
                        "reviewed decisions",
                        "Legacy map triage application summary",
                        now_iso(),
                    ),
                )
            conn.commit()

    report_path = ROOT / "data" / "processed" / "v2" / f"{run_id}_legacy_map_apply_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Legacy Map Triage Apply Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Review rows: `{len(rows)}`",
        f"- Rows with reviewer decisions: `{len(considered)}`",
        f"- Invalid decisions: `{len(invalid)}`",
        "",
        "## Actions",
    ]
    if actions:
        for action in actions[:200]:
            lines.append(f"- `{action['legacy_map_id']}`: {action['status']} - {action['detail']}")
    else:
        lines.append("- No reviewer decisions supplied.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {"rows": len(rows), "considered": len(considered), "invalid": len(invalid), "actions": actions, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--review-csv", required=True, help="legacy map triage review CSV")
    parser.add_argument("--run-id", required=True, help="apply run id")
    parser.add_argument("--dry-run", action="store_true", help="validate decisions without writing")
    parser.add_argument("--execute", action="store_true", help="apply reviewer decisions")
    args = parser.parse_args()

    execute = bool(args.execute and not args.dry_run)
    summary = apply_decisions(Path(args.db), Path(args.review_csv), args.run_id, execute)
    print(f"Legacy map triage {'executed' if execute else 'dry run'}: {summary['considered']} decisions considered.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
