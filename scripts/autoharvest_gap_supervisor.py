#!/usr/bin/env python3
"""Gap-targeted no-auth autoharvest supervisor."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoharvest_gap_checkpoint_report import make_report as make_gap_checkpoint
from autoharvest_gap_milestone_audit import run_audit as run_gap_audit
from autoharvest_gap_rebalance import rebalance as gap_rebalance
from autoharvest_open_records import insert_page, seed_lookup
from autoharvest_watchdog import run_watchdog
from build_gap_targeted_noauth_frontier import build_frontier
from collection_expansion_common import now_iso
from lib.autoharvest_engine import (
    check_duplicate_against_existing,
    classify_noise,
    classify_route_safety,
    classify_sensitive,
    extract_candidates_from_page,
    extract_route_candidates,
    fetch_page_safe,
    insert_discovered_routes,
    insert_harvest_candidate,
    insert_provisional_record,
    load_autoharvest_config,
    load_noauth_seeds,
    make_duplicate_key,
    next_frontier_item,
    promote_discovered_routes_to_frontier,
    score_candidate,
    stable_id,
    update_route_stats,
)
from lib.autoharvest_gap import (
    classify_gap_candidate,
    gap_count,
    insert_temporal_evidence,
    provisional_id_for_candidate,
    update_candidate_gap_fields,
    update_provisional_gap_fields,
)
from migrate_autoharvest_gap_v2 import migrate
from validate_item_level_candidate import item_level_confidence


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def queue_candidate_item(conn: sqlite3.Connection, run_id: str, frontier: dict[str, Any], candidate: dict[str, Any], route: dict[str, Any]) -> bool:
    url = str(candidate.get("url") or "")
    if not url or url == frontier.get("url"):
        return False
    frontier_id = stable_id("frontier_", run_id, route.get("route_id"), url)
    before = conn.total_changes
    conn.execute(
        """
        INSERT INTO harvest_frontier (
            frontier_id, run_id, route_id, source_id, source_name, source_tier,
            route_family, state, url, url_type, parent_url, depth, priority_score,
            status, discovered_at, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gap_candidate_item', ?, ?, ?, 'queued', ?, ?)
        ON CONFLICT(frontier_id) DO NOTHING
        """,
        (
            frontier_id,
            run_id,
            route.get("route_id") or frontier.get("route_id"),
            route.get("source_id") or frontier.get("source_id"),
            route.get("source_name") or frontier.get("source_name"),
            route.get("source_tier") or frontier.get("source_tier"),
            route.get("route_family") or frontier.get("route_family"),
            route.get("state") or frontier.get("state"),
            url,
            frontier.get("url"),
            int(frontier.get("depth") or 0) + 1,
            float(frontier.get("priority_score") or 0) + 20,
            now_iso(),
            f"queued from directory candidate title={candidate.get('title') or ''}",
        ),
    )
    return conn.total_changes > before


def ordinary_safe_for_auxiliary(candidate: dict[str, Any], decision_reasons: list[str]) -> bool:
    hard = {"duplicate", "sensitive_or_restricted", "discovery_or_sensitive_route"}
    if any(reason in hard or reason.startswith("noise:") for reason in decision_reasons):
        return False
    for field in ["url", "title", "evidence_source_name", "evidence_source_url", "source_tier"]:
        if not candidate.get(field):
            return False
    return candidate.get("source_tier") in {"A", "B", "C"}


def process_gap_frontier_item(conn: sqlite3.Connection, run_id: str, frontier: dict[str, Any], route: dict[str, Any], config, session: requests.Session) -> dict[str, int]:
    stats = {"pages": 0, "candidates": 0, "target": 0, "auxiliary": 0, "queued_items": 0, "duplicates": 0, "noise": 0, "robots_blocked": 0, "errors": 0}
    fetch = fetch_page_safe(str(frontier["url"]), route, config, session)
    conn.execute(
        "UPDATE harvest_frontier SET status=?, last_attempted_at=?, robots_status=?, last_http_status=?, retry_count=retry_count+? WHERE frontier_id=?",
        (
            "fetched" if fetch.status == "fetched" else ("paused" if fetch.status in {"backoff", "paused"} else "blocked"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "allowed" if fetch.status == "fetched" else fetch.status,
            fetch.http_status,
            0 if fetch.status == "fetched" else 1,
            frontier["frontier_id"],
        ),
    )
    if fetch.status == "robots_blocked":
        stats["robots_blocked"] += 1
        return stats
    if fetch.status != "fetched" or not fetch.html:
        stats["errors"] += 1
        return stats
    stats["pages"] += 1
    page_id = insert_page(conn, run_id, frontier, fetch, fetch.html)
    page_candidate = {"title": frontier.get("source_name") or "", "url": frontier.get("url"), "snippet": ""}
    page_item_conf, page_reasons = item_level_confidence(page_candidate, "", {"link_count": fetch.html.count("<a "), "title": frontier.get("source_name")})
    directory_page = page_item_conf < 0.45 and frontier.get("url_type") in {"gap_search_query", "gap_seed_static", "seed", "discovered_route"}
    candidates = extract_candidates_from_page({"html": fetch.html, "url": frontier["url"]}, route, run_id, page_id)
    discovered = extract_route_candidates(fetch.html, frontier["url"], route, run_id)
    insert_discovered_routes(conn, discovered)
    promote_discovered_routes_to_frontier(conn, run_id, config)
    for candidate in candidates:
        stats["candidates"] += 1
        candidate["duplicate_key"] = candidate.get("duplicate_key") or make_duplicate_key(candidate)
        candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
        candidate["ethics_status"] = classify_sensitive(candidate, route)
        score, score_reasons = score_candidate(candidate, route, config)
        candidate["candidate_score"] = score
        candidate["noise_flags_json"] = json.dumps(classify_noise(" ".join([str(candidate.get("title") or ""), str(candidate.get("snippet") or "")]), config))
        decision = classify_gap_candidate(candidate, route, config.data, page_text="" if directory_page else fetch.html[:5000], metadata={"url": frontier["url"], "title": candidate.get("title"), "link_count": fetch.html.count("<a ")})
        if directory_page and not decision.target_gap_eligible:
            candidate["gate_status"] = "candidate_hold"
            candidate["gate_reasons_json"] = json.dumps(["directory_page_needs_item_fetch", *decision.reasons])
            insert_harvest_candidate(conn, candidate)
            update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
            if queue_candidate_item(conn, run_id, frontier, candidate, route):
                stats["queued_items"] += 1
            continue
        candidate["gate_status"] = "target_gap_accepted" if decision.target_gap_eligible else "auxiliary_accepted" if ordinary_safe_for_auxiliary(candidate, decision.reasons) and decision.auxiliary_status in {"GENERAL_SAFE_PROVISIONAL", "UNDATED_AUXILIARY", "PLACE_ONLY_AUXILIARY"} else "candidate_hold"
        candidate["gate_reasons_json"] = json.dumps(decision.reasons or score_reasons)
        insert_harvest_candidate(conn, candidate)
        update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
        if candidate["duplicate_status"] not in {"unique", "probably_unique"}:
            stats["duplicates"] += 1
        if any(reason.startswith("noise:") for reason in decision.reasons + score_reasons):
            stats["noise"] += 1
        if candidate["gate_status"] in {"target_gap_accepted", "auxiliary_accepted"} and insert_provisional_record(conn, candidate, max(score, 80 if decision.target_gap_eligible else 60)):
            conn.execute("UPDATE provisional_records SET route_id=? WHERE candidate_id=?", (candidate.get("route_id"), candidate["candidate_id"]))
            update_provisional_gap_fields(conn, candidate["candidate_id"], decision, harvest_mode="gap_targeted")
            insert_temporal_evidence(conn, run_id, candidate["candidate_id"], provisional_id_for_candidate(candidate), decision, candidate.get("url") or "")
            if decision.target_gap_eligible:
                stats["target"] += 1
            else:
                stats["auxiliary"] += 1
    update_route_stats(conn, run_id, route, pages=stats["pages"], candidates=stats["candidates"], provisional=stats["target"], duplicates=stats["duplicates"], noise=stats["noise"], robots_blocked=stats["robots_blocked"], errors=stats["errors"])
    return stats


def gap_should_stop(conn: sqlite3.Connection, run_id: str, target: int, started_at: float, max_runtime_hours: float, config_data: dict[str, Any]) -> tuple[bool, str]:
    _target_count, target_weight = gap_count(conn, run_id)
    if target_weight >= target:
        return True, "target_gap_reached"
    if (time.time() - started_at) / 3600 >= max_runtime_hours:
        return True, "max_runtime_hours_reached"
    pages = conn.execute("SELECT COUNT(*) FROM harvest_pages WHERE run_id=?", (run_id,)).fetchone()[0]
    brake = config_data.get("quality_brakes", {}).get("stop_if_target_gap_records_below_after_pages", {})
    if pages >= int(brake.get("pages", 500)) and target_weight < int(brake.get("min_target_records", 10)):
        return True, "target_gap_yield_nonviable_after_500_pages"
    queued = conn.execute("SELECT COUNT(*) FROM harvest_frontier WHERE run_id=? AND status='queued'", (run_id,)).fetchone()[0]
    if queued == 0:
        return True, "frontier_exhausted"
    return False, ""


def supervise(db_path: Path, config_path: Path, seeds_path: Path, run_id: str, target: int, execute: bool, max_segments: int | None = None) -> dict[str, Any]:
    migrate(db_path)
    config = load_autoharvest_config(config_path)
    config_data = load_config(config_path)
    reports_dir = Path(config.data.get("outputs", {}).get("reports_dir", "data/processed/v2/autoharvest"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    if not execute:
        return build_frontier(db_path, config_path, seeds_path, Path("data/interim/source_discovery/noauth_search_forms.csv"), run_id, reports_dir / "gap_targeted_frontier_plan.md", execute=False)
    build_frontier(db_path, config_path, seeds_path, Path("data/interim/source_discovery/noauth_search_forms.csv"), run_id, reports_dir / "gap_targeted_frontier_plan.md", execute=True)
    seeds = load_noauth_seeds(seeds_path)
    lookup = seed_lookup(seeds)
    started = time.time()
    session = requests.Session()
    segment = 0
    stop_reason = ""
    with sqlite3.connect(db_path) as conn:
        while True:
            stop, reason = gap_should_stop(conn, run_id, target, started, float(config.data.get("runtime", {}).get("max_runtime_hours", 168)), config_data)
            if stop:
                stop_reason = reason
                break
            frontier = next_frontier_item(conn, run_id)
            if not frontier:
                stop_reason = "frontier_exhausted"
                break
            route = lookup.get(str(frontier.get("route_id"))) or {
                "route_id": frontier.get("route_id"),
                "source_id": frontier.get("source_id"),
                "source_name": frontier.get("source_name"),
                "source_tier": frontier.get("source_tier"),
                "route_family": frontier.get("route_family"),
                "state": frontier.get("state"),
                "official_url": frontier.get("url"),
                "evidence_or_discovery": "evidence_possible",
            }
            ok, reasons = classify_route_safety(route, config)
            if not ok:
                conn.execute("UPDATE harvest_frontier SET status='blocked', notes=? WHERE frontier_id=?", (";".join(reasons), frontier["frontier_id"]))
                conn.commit()
                continue
            process_gap_frontier_item(conn, run_id, frontier, route, config, session)
            segment += 1
            conn.commit()
            target_count, target_weight = gap_count(conn, run_id)
            if target_weight >= 250:
                row = conn.execute("SELECT audit_status FROM harvest_milestones WHERE run_id=? AND milestone_name='gap_milestone_250'", (run_id,)).fetchone()
                if not row:
                    audit = run_gap_audit(db_path, run_id, 250, reports_dir / "gap_milestone_250")
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO harvest_milestones(run_id, milestone_name, milestone_value, reached_at, report_path, audit_status, notes)
                        VALUES (?, 'gap_milestone_250', 250, ?, ?, ?, ?)
                        """,
                        (run_id, now_iso(), str(reports_dir / "gap_milestone_250" / "milestone_summary.md"), "passed" if audit["quality_ok"] else "quality_rebalance", "gap target milestone audit"),
                    )
                    conn.commit()
            if segment % 10 == 0:
                make_gap_checkpoint(db_path, run_id, reports_dir / f"{run_id}_checkpoint.md", target)
                watchdog = run_watchdog(db_path, run_id, reports_dir / f"{run_id}_watchdog.md")
                if watchdog["safety_stopped"]:
                    stop_reason = "watchdog_safety_stop"
                    break
                gap_rebalance(db_path, config_path, run_id, reports_dir / f"{run_id}_rebalance.md")
            if max_segments is not None and segment >= max_segments:
                stop_reason = "max_segments_reached"
                break
        make_gap_checkpoint(db_path, run_id, reports_dir / f"{run_id}_checkpoint.md", target)
        watchdog = run_watchdog(db_path, run_id, reports_dir / f"{run_id}_watchdog.md")
        target_count, target_weight = gap_count(conn, run_id)
        status = "completed" if stop_reason == "target_gap_reached" else "paused"
        conn.execute(
            "UPDATE harvest_runs SET status=?, finished_at=?, stop_reason=?, effective_records_added=? WHERE run_id=?",
            (status, now_iso(), stop_reason, int(target_weight), run_id),
        )
        if stop_reason == "target_gap_reached":
            run_gap_audit(db_path, run_id, target, reports_dir / "gap_milestone_2000")
        conn.commit()
    log_path = Path(config.data.get("outputs", {}).get("logs_dir", "data/autoharvest/logs")) / f"{run_id}_gap_supervisor.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(f"segments={segment}\nstop_reason={stop_reason}\n", encoding="utf-8")
    return {"segments": segment, "stop_reason": stop_reason, "target_weight": target_weight, "watchdog": watchdog}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-segments", type=int)
    args = parser.parse_args()
    summary = supervise(Path(args.db), Path(args.config), Path(args.seeds), args.run_id, args.target_gap_effective_records, execute=bool(args.execute and not args.dry_run), max_segments=args.max_segments)
    print(f"Gap autoharvest supervisor stopped: {summary.get('stop_reason')}")
    print(summary)


if __name__ == "__main__":
    main()
