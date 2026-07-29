#!/usr/bin/env python3
"""Run the no-credential structured endpoint target-gap operator."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_structured_endpoint_queries import build as build_queries
from collection_expansion_common import now_iso
from discover_noauth_structured_endpoints import discover as discover_endpoints
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, insert_provisional_record, make_duplicate_key
from lib.autoharvest_gap import insert_temporal_evidence, provisional_id_for_candidate, update_candidate_gap_fields, update_provisional_gap_fields
from lib.structured_endpoints import EndpointConfig, EndpointRecord, client_for, score_endpoint_record, stable_endpoint_record_id
from migrate_structured_endpoint_harvest_v1 import migrate


def target_count(conn: sqlite3.Connection, run_id: str) -> tuple[int, float]:
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(target_effective_weight), 0) FROM provisional_records WHERE run_id=? AND target_gap_eligible=1 AND harvest_mode='structured_endpoint_gap'",
        (run_id,),
    ).fetchone()
    return int(row[0] or 0), float(row[1] or 0.0)


def endpoint_config(config: dict) -> EndpointConfig:
    limits = config.get("endpoint_probe_limits", {})
    return EndpointConfig(
        timeout_seconds=min(float(limits.get("timeout_seconds", 25)), 3.0),
        rate_limit_seconds=min(float(limits.get("rate_limit_seconds", 2.5)), 0.25),
        max_pages=min(int(limits.get("max_pages_per_endpoint", 25)), 5),
        max_records=min(int(limits.get("max_records_per_endpoint", 500)), 20),
    )


def load_query_batch(conn: sqlite3.Connection, run_id: str, limit: int) -> list[dict]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT q.*, i.*
        FROM noauth_endpoint_queries q
        JOIN noauth_endpoint_inventory i ON i.endpoint_id=q.endpoint_id
        WHERE q.run_id=? AND q.status='queued' AND i.status='active'
        ORDER BY q.priority_score DESC, q.created_at ASC
        LIMIT ?
        """,
        (run_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


def active_endpoint_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM noauth_endpoint_inventory WHERE status='active' AND noauth_verified=1").fetchone()[0] or 0)


def queued_query_count(conn: sqlite3.Connection, run_id: str) -> int:
    return int(
        conn.execute(
            """
            SELECT COUNT(*)
            FROM noauth_endpoint_queries q
            JOIN noauth_endpoint_inventory i ON i.endpoint_id=q.endpoint_id
            WHERE q.run_id=? AND q.status='queued' AND i.status='active'
            """,
            (run_id,),
        ).fetchone()[0]
        or 0
    )


def insert_endpoint_record(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO noauth_endpoint_records (
            endpoint_record_id, run_id, endpoint_id, endpoint_query_id, route_id, source_name,
            source_tier, endpoint_type, item_url, item_id, title, description, creator,
            publisher, date_text, inferred_year, coverage_start_year, coverage_end_year,
            subject_terms, place_text, format_text, rights_text, metadata_json,
            controlled_term_hits, temporal_evidence_json, item_level_confidence,
            target_gap_score, target_gap_eligible, gate_reasons_json, duplicate_key,
            duplicate_status, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(
            row.get(field)
            for field in [
                "endpoint_record_id",
                "run_id",
                "endpoint_id",
                "endpoint_query_id",
                "route_id",
                "source_name",
                "source_tier",
                "endpoint_type",
                "item_url",
                "item_id",
                "title",
                "description",
                "creator",
                "publisher",
                "date_text",
                "inferred_year",
                "coverage_start_year",
                "coverage_end_year",
                "subject_terms",
                "place_text",
                "format_text",
                "rights_text",
                "metadata_json",
                "controlled_term_hits",
                "temporal_evidence_json",
                "item_level_confidence",
                "target_gap_score",
                "target_gap_eligible",
                "gate_reasons_json",
                "duplicate_key",
                "duplicate_status",
                "created_at",
            ]
        ),
    )


def update_stats(conn: sqlite3.Connection, run_id: str, endpoint: dict, stats: Counter) -> None:
    attempted = int(stats.get("queries_attempted", 0))
    records = int(stats.get("records_seen", 0))
    targets = int(stats.get("target_gap_records", 0))
    near = int(stats.get("near_misses", 0))
    errors = int(stats.get("errors", 0))
    dup = int(stats.get("duplicates", 0))
    score = (targets * 10.0 + near * 2.0) / max(1, attempted)
    action = "boost" if targets else "continue_small" if near else "pause_zero_yield" if attempted and not records else "monitor"
    conn.execute(
        """
        INSERT INTO noauth_endpoint_route_stats (
            run_id, endpoint_id, endpoint_type, source_name, queries_attempted,
            records_seen, target_gap_records, near_misses, duplicates, noise,
            errors, yield_score, recommended_action, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, endpoint_id) DO UPDATE SET
            queries_attempted=noauth_endpoint_route_stats.queries_attempted + excluded.queries_attempted,
            records_seen=noauth_endpoint_route_stats.records_seen + excluded.records_seen,
            target_gap_records=noauth_endpoint_route_stats.target_gap_records + excluded.target_gap_records,
            near_misses=noauth_endpoint_route_stats.near_misses + excluded.near_misses,
            duplicates=noauth_endpoint_route_stats.duplicates + excluded.duplicates,
            errors=noauth_endpoint_route_stats.errors + excluded.errors,
            yield_score=excluded.yield_score,
            recommended_action=excluded.recommended_action,
            updated_at=excluded.updated_at
        """,
        (run_id, endpoint["endpoint_id"], endpoint.get("endpoint_type"), endpoint.get("source_name"), attempted, records, targets, near, dup, 0, errors, score, action, now_iso()),
    )
    if action == "pause_zero_yield":
        reason = "paused after repeated structured endpoint errors" if errors >= 3 else "paused after zero-yield structured endpoint batch"
        conn.execute("UPDATE noauth_endpoint_inventory SET status='paused', notes=? WHERE endpoint_id=?", (reason, endpoint["endpoint_id"]))


def process_query(conn: sqlite3.Connection, row: dict, config: dict, run_id: str, session: requests.Session, execute: bool) -> Counter:
    stats: Counter = Counter()
    stats["queries_attempted"] += 1
    endpoint = dict(row)
    query = dict(row)
    cfg = endpoint_config(config)
    client = client_for(endpoint.get("endpoint_type") or "", cfg, session)
    try:
        records = client.fetch_records(endpoint, query) if execute else []
    except Exception:
        records = []
        stats["errors"] += 1
    stats["records_seen"] += len(records)
    for record in records:
        candidate_score = score_endpoint_record(record, endpoint, query, config, run_id)
        candidate = candidate_score["candidate"]
        candidate["run_id"] = run_id
        candidate["duplicate_key"] = make_duplicate_key(candidate)
        candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
        if candidate["duplicate_status"] not in {"unique", "probably_unique", "unique_or_probably_unique"}:
            stats["duplicates"] += 1
        # Re-score after duplicate status is known.
        candidate_score = score_endpoint_record(record, endpoint, query, config, run_id, candidate["duplicate_status"])
        candidate = candidate_score["candidate"]
        decision = candidate_score["decision"]
        endpoint_record = {
            "endpoint_record_id": stable_endpoint_record_id(run_id, endpoint["endpoint_id"], record.item_url, record.title, record.date_text),
            "run_id": run_id,
            "endpoint_id": endpoint["endpoint_id"],
            "endpoint_query_id": row["endpoint_query_id"],
            "route_id": endpoint.get("route_id"),
            "source_name": endpoint.get("source_name"),
            "source_tier": endpoint.get("source_tier"),
            "endpoint_type": endpoint.get("endpoint_type"),
            "item_url": record.item_url,
            "item_id": record.item_id,
            "title": record.title,
            "description": record.description,
            "creator": record.creator,
            "publisher": record.publisher,
            "date_text": record.date_text,
            "inferred_year": decision.temporal.extracted_year,
            "coverage_start_year": decision.temporal.coverage_start_year,
            "coverage_end_year": decision.temporal.coverage_end_year,
            "subject_terms": ";".join(record.subjects),
            "place_text": record.place_text,
            "format_text": record.format_text,
            "rights_text": record.rights_text,
            "metadata_json": record.raw_metadata_json,
            "controlled_term_hits": json.dumps(candidate_score["controlled_term_hits"]),
            "temporal_evidence_json": json.dumps(decision.temporal.as_dict()),
            "item_level_confidence": decision.item_level_confidence,
            "target_gap_score": candidate_score["target_gap_score"],
            "target_gap_eligible": 1 if decision.target_gap_eligible else 0,
            "gate_reasons_json": json.dumps(decision.reasons),
            "duplicate_key": candidate.get("duplicate_key"),
            "duplicate_status": candidate.get("duplicate_status"),
            "created_at": now_iso(),
        }
        if execute:
            insert_endpoint_record(conn, endpoint_record)
            insert_harvest_candidate(conn, candidate)
            update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
            if decision.target_gap_eligible and insert_provisional_record(conn, candidate, candidate_score["target_gap_score"]):
                update_provisional_gap_fields(conn, candidate["candidate_id"], decision, harvest_mode="structured_endpoint_gap")
                insert_temporal_evidence(conn, run_id, candidate["candidate_id"], provisional_id_for_candidate(candidate), decision, record.item_url)
        if decision.target_gap_eligible:
            stats["target_gap_records"] += 1
        elif decision.temporal.confidence >= 0.7 or decision.term_hit_confidence >= 0.7:
            stats["near_misses"] += 1
    if execute:
        conn.execute("UPDATE noauth_endpoint_queries SET status='attempted', attempted_at=? WHERE endpoint_query_id=?", (now_iso(), row["endpoint_query_id"]))
    return stats


def run_operator(db_path: Path, config_path: Path, run_id: str, target: int, execute: bool, max_segments: int = 3) -> dict[str, object]:
    migrate(db_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    out_dir = ROOT / config.get("outputs", {}).get("out_dir", "data/processed/v2/autoharvest/structured_endpoints")
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = ROOT / "config" / "noauth_open_source_seeds.yml"
    registry = ROOT / "config" / "source_registry.yml"
    expanded = ROOT / "config" / "noauth_open_source_seeds_expanded.yml"
    with sqlite3.connect(db_path) as conn:
        existing_endpoints = active_endpoint_count(conn)
        existing_queued = queued_query_count(conn, run_id)
    if existing_endpoints:
        discover_summary = {"endpoints": existing_endpoints, "reused": True}
    else:
        discover_summary = discover_endpoints(db_path, config_path, seeds, registry, expanded, out_dir / "endpoint_discovery_report.md", execute)
    if existing_queued:
        build_summary = {"queries": existing_queued, "reused": True}
    else:
        build_summary = build_queries(db_path, config_path, run_id, out_dir / "structured_endpoint_query_plan.md", execute)
    segment_summaries: list[dict[str, object]] = []
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        for segment in range(1, max_segments + 1):
            count, weight = target_count(conn, run_id)
            if weight >= target:
                break
            batch = load_query_batch(conn, run_id, 20)
            if not batch:
                break
            per_endpoint: dict[str, Counter] = defaultdict(Counter)
            for row in batch:
                stats = process_query(conn, row, config, run_id, session, execute)
                per_endpoint[row["endpoint_id"]].update(stats)
            for endpoint_id, stats in per_endpoint.items():
                endpoint = next(row for row in batch if row["endpoint_id"] == endpoint_id)
                update_stats(conn, run_id, endpoint, stats)
            if execute:
                conn.commit()
            target_raw, target_weight = target_count(conn, run_id)
            segment_summaries.append({"segment": segment, "queries": len(batch), "target_raw": target_raw, "target_weight": target_weight, "endpoints": len(per_endpoint)})
            if sum(int(stats.get("target_gap_records", 0)) + int(stats.get("near_misses", 0)) for stats in per_endpoint.values()) == 0 and segment >= 1:
                break
    summary_path = out_dir / f"{run_id}_operator_summary.md"
    with sqlite3.connect(db_path) as conn:
        target_raw, target_weight = target_count(conn, run_id)
        records_seen = conn.execute("SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=?", (run_id,)).fetchone()[0]
        near = conn.execute(
            "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=0 AND ((controlled_term_hits IS NOT NULL AND controlled_term_hits NOT IN ('[]','')) OR inferred_year IS NOT NULL)",
            (run_id,),
        ).fetchone()[0]
        queued = queued_query_count(conn, run_id)
    segment_lines = [f"- segment {row['segment']}: queries `{row['queries']}`, target `{row['target_weight']}`, endpoints `{row['endpoints']}`" for row in segment_summaries] or ["- None"]
    lines = [
        "# Structured Endpoint Gap Operator Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Endpoints discovered this run: `{discover_summary.get('endpoints')}`",
        f"- Endpoint queries generated: `{build_summary.get('queries')}`",
        f"- Endpoint records seen: `{records_seen}`",
        f"- Target-gap effective records: `{target_weight} / {target}`",
        f"- Target-gap raw records: `{target_raw}`",
        f"- High-quality near misses: `{near}`",
        f"- Queued endpoint queries remaining: `{queued}`",
        f"- Marathon status: `{'target_reached' if target_weight >= target else 'paused_or_exhausted' if queued == 0 else 'paused_after_segment'}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Segments",
        *segment_lines,
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"target_records": target_raw, "target_weight": target_weight, "records_seen": records_seen, "near_misses": near, "queued": queued, "summary": str(summary_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_operator(Path(args.db), Path(args.config), args.run_id, args.target_gap_effective_records, execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
