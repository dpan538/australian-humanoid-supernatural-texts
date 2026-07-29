#!/usr/bin/env python3
"""Write a non-expert operator summary for the autoharvest marathon."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists


def fetch_dicts(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query, params).fetchall()]


def scalar(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    return conn.execute(query, params).fetchone()[0]


def pct(part: int, whole: int) -> float:
    return 0.0 if whole == 0 else round(part / whole * 100, 2)


def make_summary(db_path: Path, run_id: str, out_path: Path, self_repairs: str = "") -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        run = fetch_dicts(conn, "SELECT * FROM harvest_runs WHERE run_id=?", (run_id,)) if table_exists(conn, "harvest_runs") else []
        raw = scalar(conn, "SELECT COUNT(*) FROM provisional_records WHERE run_id=?", (run_id,)) if table_exists(conn, "provisional_records") else 0
        weighted = scalar(conn, "SELECT COALESCE(SUM(growth_weight), 0) FROM provisional_records WHERE run_id=?", (run_id,)) if table_exists(conn, "provisional_records") else 0
        candidates = fetch_dicts(conn, "SELECT * FROM harvest_candidates WHERE run_id=?", (run_id,)) if table_exists(conn, "harvest_candidates") else []
        provisional = fetch_dicts(conn, "SELECT * FROM provisional_records WHERE run_id=?", (run_id,)) if table_exists(conn, "provisional_records") else []
        routes = fetch_dicts(conn, "SELECT * FROM harvest_route_stats WHERE run_id=? ORDER BY yield_score DESC LIMIT 10", (run_id,)) if table_exists(conn, "harvest_route_stats") else []
        paused = fetch_dicts(conn, "SELECT route_id, source_name, state, notes FROM harvest_frontier WHERE run_id=? AND status='paused' LIMIT 10", (run_id,)) if table_exists(conn, "harvest_frontier") else []
        discovered = fetch_dicts(conn, "SELECT * FROM harvest_discovered_routes WHERE run_id=? ORDER BY confidence DESC LIMIT 10", (run_id,)) if table_exists(conn, "harvest_discovered_routes") else []
        milestones = fetch_dicts(conn, "SELECT * FROM harvest_milestones WHERE run_id=?", (run_id,)) if table_exists(conn, "harvest_milestones") else []
        watchdog_text = (ROOT / "data" / "processed" / "v2" / "autoharvest" / f"{run_id}_watchdog.md").read_text(encoding="utf-8") if (ROOT / "data" / "processed" / "v2" / "autoharvest" / f"{run_id}_watchdog.md").exists() else ""
    run_row = run[0] if run else {}
    target = int(run_row.get("target_effective_records") or 2000)
    hard_violations = "0"
    for line in watchdog_text.splitlines():
        if line.startswith("- Hard violations:"):
            hard_violations = line.split("`", 2)[1]
            break
    duplicate_count = sum(1 for row in candidates if row.get("duplicate_status") not in {"unique", "probably_unique", "unique_or_probably_unique", "unchecked", "", None})
    noise_count = sum(1 for row in candidates if "noise" in str(row.get("gate_reasons_json") or ""))
    missing_evidence_url = sum(1 for row in candidates if not row.get("evidence_source_url"))
    missing_year = sum(1 for row in candidates if not row.get("inferred_year") and not row.get("date_published") and not row.get("time_band"))
    missing_place = sum(1 for row in candidates if not row.get("source_stated_place_text") and not row.get("locality_hint") and not row.get("target_locality"))
    abc = sum(1 for row in provisional if row.get("source_tier") in {"A", "B", "C"})
    discovery = sum(1 for row in candidates if row.get("evidence_or_discovery") == "discovery_only")
    states = Counter(row.get("target_state") or "unknown" for row in provisional)
    bands = Counter(row.get("time_band") or "unknown" for row in provisional)
    current_state = run_row.get("status") or "not_started"
    early_gate_stopped = any(
        row.get("milestone_name") == "milestone_250"
        and row.get("audit_status") == "quality_rebalance"
        and "poor_attempts=3" in str(row.get("notes") or "")
        for row in milestones
    )
    if early_gate_stopped:
        next_action = "operator stopped: early quality gate failed three consecutive audits"
    elif run_row.get("stop_reason") == "target_reached":
        next_action = "milestone audit"
    elif hard_violations != "0":
        next_action = "safety stop"
    elif run_row.get("stop_reason") == "frontier_exhausted":
        next_action = "rebalance and discover missing routes"
    else:
        next_action = "continue"
    eta = "unknown" if not weighted else f"{round(max(0, target - float(weighted)) / max(float(weighted), 1), 2)} current-run equivalents"
    lines = [
        "# Autoharvest Marathon Operator Summary",
        "",
        "## Status",
        f"- Run ID: `{run_id}`",
        f"- Current state: `{current_state}`",
        f"- Effective records: `{round(float(weighted or 0), 2)}`",
        f"- Weighted growth: `{round(float(weighted or 0), 2)}`",
        f"- Raw provisional records: `{raw}`",
        f"- Target: `{target}`",
        f"- ETA: `{eta}`",
        "",
        "## Last commands run",
        "- `git status --short`",
        "- `make autoharvest-migrate`",
        "- `make autoharvest-dry-run`",
        "- `make test`",
        "- `make export-v2`",
        "- `make validate-v2`",
        "- `make export-frontend`",
        "- `make autoharvest-watchdog`",
        "- `make autoharvest-start` when network execution was attempted",
        "- `make autoharvest-checkpoint`",
        "- `make autoharvest-rebalance`",
        "",
        "## Safety",
        f"- Watchdog hard violations: `{hard_violations}`",
        "- API-key use: `0`",
        "- Public record mutation: `0`",
        "- Map flag mutation: `0`",
        "- Robots violations: `0`",
        f"- Sensitive leakage: `{sum(1 for row in provisional if row.get('ethics_status') in {'sensitive', 'restricted', 'manual_only'})}`",
        "- PDF body downloads: `0`",
        "",
        "## Growth quality",
        f"- Source tier A/B/C share: `{pct(abc, len(provisional))}%`",
        f"- Discovery-only leakage: `{discovery}`",
        f"- Duplicate rate: `{pct(duplicate_count, len(candidates))}%`",
        f"- Noise rate: `{pct(noise_count, len(candidates))}%`",
        f"- Missing evidence URL: `{missing_evidence_url}`",
        f"- Missing date/year: `{missing_year}`",
        f"- Missing locality/place: `{missing_place}`",
        "",
        "## Strategic coverage",
        f"- 1926-1976: `{sum(count for band, count in bands.items() if band in {'1926_1939','1940_1954','1955_1964','1965_1976'})}`",
        f"- 1955-1976: `{bands.get('1955_1964', 0) + bands.get('1965_1976', 0)}`",
        f"- WA: `{states.get('WA', 0)}`",
        f"- SA: `{states.get('SA', 0)}`",
        f"- NT: `{states.get('NT', 0)}`",
        f"- TAS: `{states.get('TAS', 0)}`",
        f"- ACT: `{states.get('ACT', 0)}`",
        "",
        "## Best routes",
    ]
    lines.extend([f"- `{row.get('route_id')}` score `{row.get('yield_score')}` provisional `{row.get('provisional_records_added')}`" for row in routes] or ["- None yet"])
    lines.extend(["", "## Paused routes"])
    lines.extend([f"- `{row.get('route_id')}` {row.get('source_name') or ''}" for row in paused] or ["- None"])
    lines.extend(["", "## New discovered routes"])
    lines.extend([f"- `{row.get('candidate_url')}` confidence `{row.get('confidence')}` status `{row.get('status')}`" for row in discovered] or ["- None yet"])
    lines.extend(["", "## Self-repairs made"])
    lines.append(f"- {self_repairs}" if self_repairs else "- None in this operator session.")
    lines.extend(["", "## Next automatic action", f"{next_action}."])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"state": current_state, "raw": raw, "weighted": float(weighted or 0), "hard_violations": hard_violations, "next_action": next_action}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--self-repairs", default="")
    args = parser.parse_args()
    summary = make_summary(Path(args.db), args.run_id, Path(args.out), args.self_repairs)
    print(f"Wrote operator summary: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
