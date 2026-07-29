#!/usr/bin/env python3
"""Long-running no-auth open-records harvester for provisional growth records."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.autoharvest_engine import (
    HarvestConfig,
    check_duplicate_against_existing,
    checkpoint_run,
    classify_noise,
    classify_route_safety,
    classify_sensitive,
    effective_growth,
    extract_candidates_from_page,
    extract_page_metadata,
    extract_route_candidates,
    fetch_page_safe,
    initialize_run,
    insert_discovered_routes,
    insert_harvest_candidate,
    insert_provisional_record,
    load_autoharvest_config,
    load_noauth_seeds,
    next_frontier_item,
    provisional_gate,
    promote_discovered_routes_to_frontier,
    score_candidate,
    seed_frontier,
    should_stop,
    stable_id,
    update_route_stats,
    write_run_report,
)
from migrate_autoharvest_v1 import migrate


def seed_lookup(seeds: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(seed.get("route_id") or seed.get("source_id")): seed for seed in seeds}


def dry_run_report(db_path: Path, config: HarvestConfig, seeds: list[dict[str, Any]], run_id: str, target: int) -> dict[str, Any]:
    accepted = 0
    rejected = 0
    reasons: dict[str, int] = {}
    for seed in seeds:
        ok, why = classify_route_safety(seed, config)
        if ok:
            accepted += 1
        else:
            rejected += 1
            for reason in why:
                reasons[reason] = reasons.get(reason, 0) + 1
    out_path = Path(config.data["outputs"]["reports_dir"]) / f"{run_id}_dry_run.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Autoharvest Dry Run",
        "",
        f"- Run ID: `{run_id}`",
        f"- Target effective records: `{target}`",
        f"- Safe seed routes eligible for frontier: `{accepted}`",
        f"- Seed routes rejected by policy: `{rejected}`",
        "- API keys required: `no`",
        "- Trove API used: `no`",
        "- Google/Bing APIs used: `no`",
        "- Public records mutated: `no`",
        "- Public map flags mutated: `no`",
        "- Pages fetched: `0`",
        "- Provisional records inserted: `0`",
        "",
        "## Rejection Reasons",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(reasons.items())] or ["- None"])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"eligible_routes": accepted, "rejected_routes": rejected, "report": out_path}


def insert_page(conn: sqlite3.Connection, run_id: str, frontier: dict[str, Any], fetch: Any, html: str) -> str:
    page_id = stable_id("hpage_", run_id, frontier.get("frontier_id"), frontier.get("url"))
    meta = extract_page_metadata(html, frontier.get("url") or "")
    conn.execute(
        """
        INSERT OR REPLACE INTO harvest_pages (
            page_id, run_id, frontier_id, route_id, url, fetched_at, http_status, content_type,
            content_length, title, canonical_url, text_sample, link_count, pdf_link_count,
            relevance_score, stored_body_path, metadata_json, robots_allowed, fetch_status, error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            page_id,
            run_id,
            frontier.get("frontier_id"),
            frontier.get("route_id"),
            frontier.get("url"),
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            fetch.http_status,
            fetch.content_type,
            len(html.encode("utf-8")),
            meta["title"],
            frontier.get("url"),
            meta["text_sample"],
            len(meta["links"]),
            len(meta["pdf_links"]),
            0,
            "",
            json.dumps({"rss_links": meta["rss_links"][:20]}),
            1,
            "fetched",
            "",
        ),
    )
    return page_id


def process_frontier_item(conn: sqlite3.Connection, run_id: str, frontier: dict[str, Any], route: dict[str, Any], config: HarvestConfig, session: requests.Session) -> dict[str, int]:
    stats = {"pages": 0, "candidates": 0, "provisional": 0, "duplicates": 0, "noise": 0, "robots_blocked": 0, "errors": 0}
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
    candidates = extract_candidates_from_page({"html": fetch.html, "url": frontier["url"]}, route, run_id, page_id)
    discovered = extract_route_candidates(fetch.html, frontier["url"], route, run_id)
    insert_discovered_routes(conn, discovered)
    promote_discovered_routes_to_frontier(conn, run_id, config)
    for candidate in candidates:
        stats["candidates"] += 1
        candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
        candidate["ethics_status"] = classify_sensitive(candidate, route)
        score, reasons = score_candidate(candidate, route, config)
        candidate["candidate_score"] = score
        candidate["noise_flags_json"] = json.dumps(classify_noise(" ".join([str(candidate.get("title") or ""), str(candidate.get("snippet") or "")]), config))
        ok, gate_reasons = provisional_gate(candidate, score, reasons, config)
        candidate["gate_status"] = "provisional_accepted" if ok else "candidate_hold"
        candidate["gate_reasons_json"] = json.dumps(gate_reasons or reasons)
        insert_harvest_candidate(conn, candidate)
        if candidate["duplicate_status"] not in {"unique", "probably_unique"}:
            stats["duplicates"] += 1
        if any(reason.startswith("noise:") for reason in reasons):
            stats["noise"] += 1
        if ok and insert_provisional_record(conn, candidate, score):
            stats["provisional"] += 1
    update_route_stats(conn, run_id, route, **stats)
    return stats


def run_harvest(db_path: Path, config_path: Path, seeds_path: Path, run_id: str, target: int, execute: bool, segment_record_limit: int | None = None) -> dict[str, Any]:
    migrate(db_path)
    config = load_autoharvest_config(config_path)
    if target:
        config.data.setdefault("target", {})["effective_new_records"] = target
    seeds = load_noauth_seeds(seeds_path)
    if not execute:
        return dry_run_report(db_path, config, seeds, run_id, config.target_effective_records)

    started = time.time()
    lookup = seed_lookup(seeds)
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        initialize_run(conn, run_id, config.data.get("run_name", "noauth_autoharvest_marathon"), config.target_effective_records, execute=True)
        seed_frontier(conn, run_id, seeds, config, dry_run=False)
        conn.commit()
        segment_start_raw, _segment_start_weighted = effective_growth(conn, run_id)
        stop_reason = ""
        while True:
            stop, reason = should_stop(conn, run_id, config.target_effective_records, started, float(config.data.get("runtime", {}).get("max_runtime_hours", 168)))
            if stop:
                stop_reason = reason
                break
            if segment_record_limit is not None:
                raw, _weighted = effective_growth(conn, run_id)
                if raw - segment_start_raw >= segment_record_limit:
                    stop_reason = "segment_record_limit_reached"
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
                update_route_stats(conn, run_id, route, errors=1)
                conn.commit()
                continue
            process_frontier_item(conn, run_id, frontier, route, config, session)
            checkpoint_every = int(config.data.get("runtime", {}).get("checkpoint_every_records", 100))
            raw, weighted = effective_growth(conn, run_id)
            if raw and raw % checkpoint_every == 0:
                checkpoint_run(conn, run_id, config)
            conn.commit()
        report = write_run_report(conn, run_id, config, Path(config.data["outputs"]["reports_dir"]) / f"{run_id}_report.md", stop_reason)
        checkpoint_run(conn, run_id, config)
        conn.execute("UPDATE harvest_runs SET status=?, finished_at=?, stop_reason=?, effective_records_added=? WHERE run_id=?", ("completed" if stop_reason == "target_reached" else "paused", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), stop_reason, int(report["weighted"]), run_id))
        conn.commit()
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-effective-records", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--segment-record-limit", type=int)
    args = parser.parse_args()
    execute = bool(args.execute and not args.dry_run)
    summary = run_harvest(Path(args.db), Path(args.config), Path(args.seeds), args.run_id, args.target_effective_records, execute, args.segment_record_limit)
    print(f"Autoharvest {'execute' if execute else 'dry-run'} complete.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
