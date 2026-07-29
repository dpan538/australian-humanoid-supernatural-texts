#!/usr/bin/env python3
"""Audit temporal gaps, map balance, source chains, and release gates."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import gate, now_iso, pct, table_exists, write_csv


PUBLIC_BANDS = [
    ("1825-1850", 1825, 1850),
    ("1851-1889", 1851, 1889),
    ("1890-1929", 1890, 1929),
    ("1930-1969", 1930, 1969),
    ("1970-1999", 1970, 1999),
    ("2000-2026", 2000, 2026),
]
GAP_BANDS = [
    ("1926-1939", 1926, 1939),
    ("1940-1954", 1940, 1954),
    ("1955-1964", 1955, 1964),
    ("1965-1976", 1965, 1976),
]


def safe_year(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    try:
        return int(text)
    except ValueError:
        return None


def count_bands(years: list[int | None], bands: list[tuple[str, int, int]]) -> list[dict[str, Any]]:
    total_dated = sum(1 for year in years if year is not None)
    rows = []
    for label, start, end in bands:
        count = sum(1 for year in years if year is not None and start <= year <= end)
        rows.append({"band": label, "start_year": start, "end_year": end, "count": count, "share_pct": pct(count, total_dated)})
    return rows


def fetch_years(conn: sqlite3.Connection) -> list[int | None]:
    if table_exists(conn, "narrative_units"):
        rows = conn.execute("SELECT earliest_attestation_start FROM narrative_units").fetchall()
        years = [safe_year(row["earliest_attestation_start"]) for row in rows]
        if years:
            return years
    if table_exists(conn, "records"):
        rows = conn.execute("SELECT year, date_published FROM records").fetchall()
        return [safe_year(row["year"]) or safe_year(row["date_published"]) for row in rows]
    return []


def fetch_map_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if table_exists(conn, "narrative_locations") and table_exists(conn, "locations"):
        rows = conn.execute(
            """
            SELECT
                COALESCE(l.state_territory, 'AU_UNSPECIFIED') AS state,
                nl.location_text_as_printed AS source_stated_place_text,
                nl.location_role AS location_role,
                nl.review_status AS review_status,
                l.latitude AS lat,
                l.longitude AS lng
            FROM narrative_locations nl
            JOIN locations l ON l.location_id = nl.location_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if table_exists(conn, "record_locations") and table_exists(conn, "locations"):
        rows = conn.execute(
            """
            SELECT
                COALESCE(l.state_territory, 'AU_UNSPECIFIED') AS state,
                rl.location_text AS source_stated_place_text,
                rl.relation_type AS location_role,
                rl.verification_status AS review_status,
                l.latitude AS lat,
                l.longitude AS lng
            FROM record_locations rl
            JOIN locations l ON l.location_id = rl.location_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    return []


def map_balance_rows(map_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(row.get("state") or "AU_UNSPECIFIED") for row in map_rows)
    total = sum(counts.values())
    return [
        {"state": state, "mapped_count": count, "share_pct": pct(count, total)}
        for state, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def mapped_missing_required(map_rows: list[dict[str, Any]]) -> int:
    missing = 0
    for row in map_rows:
        if not row.get("source_stated_place_text"):
            missing += 1
            continue
        if not row.get("location_role"):
            missing += 1
            continue
        if row.get("lat") is None or row.get("lng") is None:
            missing += 1
            continue
        if not row.get("review_status"):
            missing += 1
    return missing


def concentration_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if table_exists(conn, "source_chains"):
        source_rows = conn.execute(
            """
            SELECT
                COALESCE(access_source_name, 'unknown') AS access_source_name,
                COALESCE(original_source_name, '') AS original_source_name,
                COALESCE(evidence_source_name, 'unknown') AS evidence_source_name,
                COALESCE(evidence_source_tier, 'unknown') AS evidence_source_tier,
                COALESCE(evidence_source_family, 'unknown') AS source_family
            FROM source_chains
            """
        ).fetchall()
        rows.extend(dict(row) for row in source_rows)
    if rows:
        return rows
    if table_exists(conn, "source_items"):
        source_rows = conn.execute(
            """
            SELECT
                COALESCE(source_mediation, 'unknown') AS access_source_name,
                COALESCE(publication_or_organisation, '') AS original_source_name,
                COALESCE(publication_or_organisation, 'unknown') AS evidence_source_name,
                COALESCE(source_tier, 'unknown') AS evidence_source_tier,
                COALESCE(source_type, 'unknown') AS source_family
            FROM source_items
            """
        ).fetchall()
        rows.extend(dict(row) for row in source_rows)
    return rows


def count_dimension(rows: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(str(row.get(field) or "unknown") for row in rows)
    total = sum(counts.values())
    return [
        {"dimension": field, "value": value, "count": count, "share_pct": pct(count, total)}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def source_chain_audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    missing_original = sum(1 for row in rows if not row.get("original_source_name"))
    discovery_like = sum(1 for row in rows if str(row.get("evidence_source_tier")).upper() == "E")
    return [
        {"metric": "source_chain_rows", "value": total},
        {"metric": "missing_original_source_name", "value": missing_original},
        {"metric": "missing_original_source_name_share_pct", "value": pct(missing_original, total)},
        {"metric": "tier_e_or_discovery_like_rows", "value": discovery_like},
    ]


def discovery_only_accepted(conn: sqlite3.Connection) -> int:
    total = 0
    if table_exists(conn, "collection_candidates"):
        total += conn.execute(
            """
            SELECT COUNT(*) FROM collection_candidates
            WHERE review_status = 'accepted' AND evidence_or_discovery = 'discovery_only'
            """
        ).fetchone()[0]
    if table_exists(conn, "source_chains"):
        total += conn.execute(
            """
            SELECT COUNT(*) FROM source_chains
            WHERE source_chain_review_status IN ('accepted', 'display_ready_reviewed')
              AND evidence_source_tier = 'E'
            """
        ).fetchone()[0]
    return int(total)


def non_ayr_gap_accepted(conn: sqlite3.Connection) -> int:
    total = 0
    if table_exists(conn, "source_items"):
        total += conn.execute(
            """
            SELECT COUNT(*) FROM source_items
            WHERE CAST(SUBSTR(COALESCE(publication_date_start, publication_date_text, ''), 1, 4) AS INTEGER) BETWEEN 1926 AND 1976
              AND LOWER(COALESCE(publication_or_organisation, '')) NOT LIKE '%australian yowie research%'
              AND LOWER(COALESCE(url, '')) NOT LIKE '%yowiehunters%'
            """
        ).fetchone()[0]
    if table_exists(conn, "collection_candidates"):
        total += conn.execute(
            """
            SELECT COUNT(*) FROM collection_candidates
            WHERE review_status = 'accepted'
              AND inferred_year BETWEEN 1926 AND 1976
              AND LOWER(COALESCE(source_name, '')) NOT LIKE '%australian yowie research%'
              AND LOWER(COALESCE(url, '')) NOT LIKE '%yowiehunters%'
            """
        ).fetchone()[0]
    return int(total)


def state_new_mapped_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    if table_exists(conn, "collection_candidates"):
        rows = conn.execute(
            """
            SELECT target_state, COUNT(*) AS count
            FROM collection_candidates
            WHERE review_status IN ('accepted', 'needs_review')
              AND mappability_hint IN ('high', 'medium')
            GROUP BY target_state
            """
        ).fetchall()
        counts.update({row["target_state"]: int(row["count"]) for row in rows if row["target_state"]})
    return counts


def top_share(rows: list[dict[str, Any]], field: str, top_n: int = 1) -> float:
    counts = Counter(str(row.get(field) or "unknown") for row in rows)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    top = sum(count for _, count in counts.most_common(top_n))
    return round(top / total, 4)


def evaluate_release_gates(metrics: dict[str, Any], targets: dict[str, Any]) -> list[dict[str, str]]:
    caps = targets.get("source_caps", {})
    state_targets = targets.get("state_targets", {})
    gates = [
        gate(
            "WARN" if metrics.get("share_1930_1969", 0.0) < 5.0 else "PASS",
            "temporal_1930_1969_share",
            metrics.get("share_1930_1969", 0.0),
            ">=5%",
            "1930-1969 share should not remain near-empty.",
        ),
        gate(
            "WARN" if metrics.get("non_ayr_1926_1976_accepted", 0) < 300 else "PASS",
            "non_ayr_gap_accepted_records",
            metrics.get("non_ayr_1926_1976_accepted", 0),
            ">=300",
            "Gap records should not rely on AYR or access platforms alone.",
        ),
        gate(
            "FAIL" if metrics.get("discovery_only_accepted", 0) > int(caps.get("max_discovery_only_accepted_records", 0)) else "PASS",
            "discovery_only_accepted_leakage",
            metrics.get("discovery_only_accepted", 0),
            caps.get("max_discovery_only_accepted_records", 0),
            "Discovery-only sources must not be accepted as evidence.",
        ),
        gate(
            "FAIL" if metrics.get("mapped_missing_required", 0) > 0 else "PASS",
            "mapped_records_missing_required_place_evidence",
            metrics.get("mapped_missing_required", 0),
            "0",
            "Mapped public flags need place text, role, coordinates, and review status.",
        ),
        gate(
            "WARN"
            if metrics.get("top_evidence_source_share", 0.0) > float(caps.get("max_single_evidence_source_org_share", 0.20))
            else "PASS",
            "single_evidence_source_org_share",
            metrics.get("top_evidence_source_share", 0.0),
            caps.get("max_single_evidence_source_org_share", 0.20),
            "One evidence source organisation should not dominate the corpus.",
        ),
        gate(
            "WARN"
            if metrics.get("top_access_platform_share", 0.0) > float(caps.get("max_single_access_platform_share", 0.35))
            and metrics.get("access_original_missing_share", 0.0) > 0.5
            else "PASS",
            "single_access_platform_share_without_originals",
            metrics.get("top_access_platform_share", 0.0),
            caps.get("max_single_access_platform_share", 0.35),
            "Access-platform dominance is risky when original source names are missing.",
        ),
        gate(
            "WARN" if metrics.get("nsw_qld_vic_mapped_share", 0.0) > 80.0 else "PASS",
            "nsw_qld_vic_mapped_share",
            metrics.get("nsw_qld_vic_mapped_share", 0.0),
            "<=80%",
            "Map balance should improve outside NSW/QLD/VIC.",
        ),
    ]
    state_counts = metrics.get("state_new_mapped_counts", {})
    for state in sorted(state_targets):
        floor = int(state_targets[state].get("min_new_mapped_candidates", 0))
        observed = int(state_counts.get(state, 0))
        gates.append(
            gate(
                "WARN" if observed < floor else "PASS",
                f"{state.lower()}_new_mapped_candidate_floor",
                observed,
                floor,
                "State-first target floor after collection run.",
            )
        )
    return gates


def markdown_table(rows: list[dict[str, Any]], fields: list[str]) -> list[str]:
    if not rows:
        return ["No rows."]
    lines = ["| " + " | ".join(fields) + " |", "| " + " | ".join(["---"] * len(fields)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    return lines


def write_md(path: Path, title: str, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {title}", "", f"- Generated: `{now_iso()}`", ""]
    lines.extend(markdown_table(rows, fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def audit(db_path: Path, targets_path: Path, out_dir: Path) -> dict[str, Any]:
    targets = yaml.safe_load(targets_path.read_text(encoding="utf-8")) or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        years = fetch_years(conn)
        public_rows = count_bands(years, PUBLIC_BANDS)
        gap_rows = count_bands(years, GAP_BANDS)
        temporal_rows = public_rows + gap_rows

        map_rows_raw = fetch_map_rows(conn)
        map_rows = map_balance_rows(map_rows_raw)

        source_rows_raw = concentration_rows(conn)
        concentration = (
            count_dimension(source_rows_raw, "access_source_name")
            + count_dimension(source_rows_raw, "original_source_name")
            + count_dimension(source_rows_raw, "evidence_source_name")
            + count_dimension(source_rows_raw, "evidence_source_tier")
            + count_dimension(source_rows_raw, "source_family")
        )
        chain_rows = source_chain_audit_rows(source_rows_raw)

        total_dated = sum(1 for year in years if year is not None)
        count_1930_1969 = sum(1 for year in years if year is not None and 1930 <= year <= 1969)
        nsw_qld_vic = sum(1 for row in map_rows_raw if row.get("state") in {"NSW", "QLD", "VIC"})
        missing_original = sum(1 for row in source_rows_raw if not row.get("original_source_name"))
        metrics = {
            "share_1930_1969": pct(count_1930_1969, total_dated),
            "non_ayr_1926_1976_accepted": non_ayr_gap_accepted(conn),
            "discovery_only_accepted": discovery_only_accepted(conn),
            "mapped_missing_required": mapped_missing_required(map_rows_raw),
            "top_evidence_source_share": top_share(source_rows_raw, "evidence_source_name"),
            "top_access_platform_share": top_share(source_rows_raw, "access_source_name"),
            "access_original_missing_share": 0.0 if not source_rows_raw else round(missing_original / len(source_rows_raw), 4),
            "nsw_qld_vic_mapped_share": pct(nsw_qld_vic, len(map_rows_raw)),
            "state_new_mapped_counts": state_new_mapped_counts(conn),
        }
        gates = evaluate_release_gates(metrics, targets)
        gate_run_id = "collection_balance_" + now_iso().replace(":", "").replace("+", "Z")
        ensure_release_gate_table(conn)
        for result in gates:
            conn.execute(
                """
                INSERT OR REPLACE INTO release_gate_results (
                    gate_run_id, gate_name, gate_status, observed_value,
                    threshold_value, details, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gate_run_id,
                    result["gate_name"],
                    result["gate_status"],
                    result["observed_value"],
                    result["threshold_value"],
                    result["details"],
                    now_iso(),
                ),
            )
        conn.commit()

    write_csv(out_dir / "temporal_gap_audit.csv", temporal_rows, ["band", "start_year", "end_year", "count", "share_pct"])
    write_md(out_dir / "temporal_gap_audit.md", "Temporal Gap Audit", temporal_rows, ["band", "count", "share_pct"])
    write_csv(out_dir / "map_balance_audit.csv", map_rows, ["state", "mapped_count", "share_pct"])
    write_md(out_dir / "map_balance_audit.md", "Map Balance Audit", map_rows, ["state", "mapped_count", "share_pct"])
    write_csv(out_dir / "source_concentration_audit.csv", concentration, ["dimension", "value", "count", "share_pct"])
    write_md(out_dir / "source_concentration_audit.md", "Source Concentration Audit", concentration, ["dimension", "value", "count", "share_pct"])
    write_csv(out_dir / "source_chain_audit.csv", chain_rows, ["metric", "value"])
    write_md(out_dir / "source_chain_audit.md", "Source Chain Audit", chain_rows, ["metric", "value"])
    write_md(out_dir / "release_gate_audit.md", "Release Gate Audit", gates, ["gate_name", "gate_status", "observed_value", "threshold_value", "details"])
    return {"gate_run_id": gate_run_id, "gates": gates, "metrics": metrics}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--targets", required=True, help="collection_targets.yml path")
    parser.add_argument("--out-dir", required=True, help="audit output directory")
    args = parser.parse_args()

    summary = audit(Path(args.db), Path(args.targets), Path(args.out_dir))
    statuses = Counter(result["gate_status"] for result in summary["gates"])
    print(f"Collection balance audit complete: gate_run_id={summary['gate_run_id']}")
    print("Gate statuses: " + ", ".join(f"{key}={statuses[key]}" for key in sorted(statuses)))


if __name__ == "__main__":
    main()
