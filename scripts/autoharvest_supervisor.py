#!/usr/bin/env python3
"""Supervisor wrapper for long-running no-auth autoharvest sessions."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoharvest_build_next_frontier import rebalance
from autoharvest_checkpoint_report import make_report
from autoharvest_milestone_audit import run_audit
from autoharvest_open_records import run_harvest
from autoharvest_watchdog import run_watchdog
from lib.autoharvest_engine import effective_growth, load_autoharvest_config
from migrate_autoharvest_v1 import migrate


def early_quality_status(db_path: Path, run_id: str) -> tuple[bool, dict[str, float]]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        provisional = [dict(row) for row in conn.execute("SELECT * FROM provisional_records WHERE run_id=?", (run_id,)).fetchall()]
        candidates = [dict(row) for row in conn.execute("SELECT * FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchall()]
    total = len(provisional)
    cand_total = len(candidates)
    abc_share = 0.0 if not total else sum(1 for row in provisional if row.get("source_tier") in {"A", "B", "C"}) / total * 100
    priority_share = 0.0 if not total else sum(1 for row in provisional if row.get("target_state") in {"WA", "SA", "NT", "TAS", "ACT"}) / total * 100
    gap_share = 0.0 if not total else sum(1 for row in provisional if row.get("time_band") in {"1926_1939", "1940_1954", "1955_1964", "1965_1976"}) / total * 100
    discovery = sum(1 for row in candidates if row.get("evidence_or_discovery") == "discovery_only")
    sensitive = sum(1 for row in provisional if row.get("ethics_status") in {"sensitive", "restricted", "manual_only"})
    duplicate_rate = 0.0 if not cand_total else sum(1 for row in candidates if row.get("duplicate_status") not in {"unique", "probably_unique", "unique_or_probably_unique", "unchecked", "", None}) / cand_total * 100
    noise_rate = 0.0 if not cand_total else sum(1 for row in candidates if "noise" in str(row.get("gate_reasons_json") or "")) / cand_total * 100
    missing_evidence = 0.0 if not cand_total else sum(1 for row in candidates if not row.get("evidence_source_url")) / cand_total * 100
    metrics = {
        "source_tier_abc_share": round(abc_share, 2),
        "priority_state_share": round(priority_share, 2),
        "gap_1926_1976_share": round(gap_share, 2),
        "discovery_only_leakage": discovery,
        "sensitive_leakage": sensitive,
        "duplicate_rate": round(duplicate_rate, 2),
        "noise_rate": round(noise_rate, 2),
        "missing_evidence_url_rate": round(missing_evidence, 2),
    }
    ok = (
        abc_share >= 85
        and discovery == 0
        and sensitive == 0
        and duplicate_rate <= 40
        and noise_rate <= 40
        and missing_evidence <= 10
        and priority_share >= 35
        and gap_share >= 20
    )
    return ok, metrics


def early_audit_attempts(db_path: Path, run_id: str) -> int:
    with sqlite3.connect(db_path) as conn:
        if not conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='harvest_milestones'").fetchone():
            return 0
        row = conn.execute("SELECT notes FROM harvest_milestones WHERE run_id=? AND milestone_name='milestone_250'", (run_id,)).fetchone()
    if not row or not row[0]:
        return 0
    for part in str(row[0]).split(";"):
        if part.startswith("poor_attempts="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return 0
    return 0


def record_early_audit(db_path: Path, run_id: str, status: str, metrics: dict[str, float], attempts: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO harvest_milestones(run_id, milestone_name, milestone_value, reached_at, report_path, audit_status, notes)
            VALUES (?, 'milestone_250', 250, ?, ?, ?, ?)
            ON CONFLICT(run_id, milestone_name) DO UPDATE SET
                reached_at=excluded.reached_at,
                report_path=excluded.report_path,
                audit_status=excluded.audit_status,
                notes=excluded.notes
            """,
            (
                run_id,
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "data/processed/v2/autoharvest/milestone_250/milestone_summary.md",
                status,
                "poor_attempts=" + str(attempts) + ";metrics=" + str(metrics),
            ),
        )
        conn.commit()


def supervise(db_path: Path, config_path: Path, seeds_path: Path, run_id: str, target: int, execute: bool, max_segments: int | None = None) -> dict[str, int | str]:
    if not execute:
        return run_harvest(db_path, config_path, seeds_path, run_id, target, execute=False)
    migrate(db_path)
    config = load_autoharvest_config(config_path)
    reports_dir = Path(config.data["outputs"]["reports_dir"])
    logs_dir = Path(config.data["outputs"]["logs_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    segment = 0
    stop_reason = ""
    while True:
        segment += 1
        summary = run_harvest(db_path, config_path, seeds_path, run_id, target, execute=True, segment_record_limit=100)
        make_report(db_path, run_id, reports_dir / f"{run_id}_checkpoint.md")
        watchdog = run_watchdog(db_path, run_id, reports_dir / f"{run_id}_watchdog.md")
        if watchdog["safety_stopped"]:
            stop_reason = "watchdog_safety_stop"
            break
        with sqlite3.connect(db_path) as conn:
            _raw, weighted = effective_growth(conn, run_id)
        if weighted >= 250:
            with sqlite3.connect(db_path) as conn:
                row = conn.execute("SELECT audit_status FROM harvest_milestones WHERE run_id=? AND milestone_name='milestone_250'", (run_id,)).fetchone()
                early_passed = bool(row and row[0] == "passed")
            if not early_passed:
                run_audit(db_path, run_id, 250, reports_dir / "milestone_250")
                ok, metrics = early_quality_status(db_path, run_id)
                attempts = early_audit_attempts(db_path, run_id)
                if ok and not watchdog["safety_stopped"]:
                    record_early_audit(db_path, run_id, "passed", metrics, attempts)
                else:
                    attempts += 1
                    record_early_audit(db_path, run_id, "quality_rebalance", metrics, attempts)
                    rebalance(db_path, run_id, config_path, reports_dir / f"{run_id}_frontier_rebalance.md")
                    if attempts >= 3:
                        stop_reason = "early_quality_gate_failed_three_times"
                        break
        if weighted >= target:
            run_audit(db_path, run_id, target, reports_dir / "milestone_2000")
            stop_reason = "target_reached_audit_written"
            break
        if max_segments is not None and segment >= max_segments:
            stop_reason = "max_segments_reached"
            break
        time.sleep(float(config.data.get("runtime", {}).get("default_loop_sleep_seconds", 30)))
    log_path = logs_dir / f"{run_id}_supervisor.log"
    log_path.write_text(f"segments={segment}\nstop_reason={stop_reason}\n", encoding="utf-8")
    return {"segments": segment, "stop_reason": stop_reason, "log": str(log_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--max-segments", type=int)
    args = parser.parse_args()
    summary = supervise(Path(args.db), Path(args.config), Path(args.seeds), args.run_id, args.target_effective_records, bool(args.execute), args.max_segments)
    print(f"Autoharvest supervisor stopped: {summary.get('stop_reason')}")
    print(summary)


if __name__ == "__main__":
    main()
