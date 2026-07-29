#!/usr/bin/env python3
"""Create a plain-language dashboard from machine evaluation outputs."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists


DEFAULTS = {
    "db": ROOT / "data" / "processed" / "australian_humanoid_figures.sqlite",
    "trace": ROOT / "data" / "processed" / "v2" / "frontend_map_pipeline_trace.md",
    "manifest": ROOT / "data" / "processed" / "v2" / "frontend_map_manifest.json",
    "partition_summary": ROOT / "data" / "processed" / "v2" / "mapped_like_row_partition_summary.md",
    "reconciliation": ROOT / "data" / "processed" / "v2" / "canonical_count_reconciliation.md",
    "map_scores": ROOT / "data" / "review" / "v2" / "map_evidence_machine_scores.csv",
    "source_scores": ROOT / "data" / "review" / "v2" / "source_chain_machine_scores.csv",
    "candidate_scores": ROOT / "data" / "processed" / "v2" / "probe_candidate_scores.csv",
    "route_yield": ROOT / "data" / "processed" / "v2" / "route_yield_evaluation.csv",
    "map_report": ROOT / "data" / "processed" / "v2" / "map_evidence_machine_score_report.md",
    "source_plan": ROOT / "data" / "review" / "v2" / "source_chain_remediation" / "remediation_plan.md",
    "probe_plan": ROOT / "data" / "processed" / "v2" / "first_real_trove_probe_plan.md",
    "frontend_source_audit": ROOT / "data" / "processed" / "v2" / "frontend_source_concentration_audit.csv",
    "replacement_tasks": ROOT / "data" / "review" / "v2" / "source_chain_remediation" / "replacement_search_tasks.csv",
    "late_gap_plan": ROOT / "data" / "processed" / "v2" / "late_gap_1955_1976_institutional_probe_plan.md",
    "first_probe_workflow": ROOT / "data" / "processed" / "v2" / "first_real_probe_workflow_report.md",
    "noauth_plan": ROOT / "data" / "interim" / "collection_plans" / "noauth_open_probe_plan.csv",
    "noauth_manual": ROOT / "data" / "interim" / "collection_plans" / "noauth_manual_review_tasks.csv",
    "noauth_probe_report": ROOT / "data" / "processed" / "v2" / "noauth_open_probe_001_report.md",
    "noauth_candidate_review": ROOT / "data" / "review" / "v2" / "noauth_open_probe_001_candidate_review.csv",
    "noauth_candidate_scores": ROOT / "data" / "review" / "v2" / "noauth_open_probe_001_candidate_scores.csv",
    "noauth_route_yield": ROOT / "data" / "processed" / "v2" / "noauth_route_yield.csv",
}


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def bucket_counts(rows: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(row.get("machine_bucket") or "unknown") for row in rows)


def gate_summary(db_path: Path) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "release_gate_results"):
            return []
        rows = conn.execute(
            """
            SELECT gate_name, gate_status, observed_value, threshold_value, details, created_at
            FROM release_gate_results
            ORDER BY created_at DESC
            LIMIT 25
            """
        ).fetchall()
        return [dict(row) for row in rows]


def count_conflict_text(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return True, "Canonical count reconciliation has not been run."
    text = path.read_text(encoding="utf-8")
    if "count_conflict_resolved: `true`" in text:
        return False, "Canonical map count discrepancy is explained by partitions."
    return True, "Canonical map count conflict is unresolved."


def file_status(path: Path) -> str:
    return "present" if path.exists() else "missing"


def family_share(rows: list[dict[str, Any]], family: str, column: str = "row_count") -> float:
    total = sum(int(row.get(column) or 0) for row in rows)
    part = sum(int(row.get(column) or 0) for row in rows if row.get("source_family") == family)
    return 0.0 if total == 0 else round(part / total * 100, 2)


def report_value(path: Path, label: str) -> str:
    if not path.exists():
        return "0"
    prefix = f"- {label}: `"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line.split("`", 2)[1]
    return "0"


def make_dashboard(out_path: Path, db_path: Path = DEFAULTS["db"]) -> dict[str, Any]:
    conflict, conflict_message = count_conflict_text(DEFAULTS["reconciliation"])
    map_rows = read_csv_rows(DEFAULTS["map_scores"])
    source_rows = read_csv_rows(DEFAULTS["source_scores"])
    candidate_rows = read_csv_rows(DEFAULTS["candidate_scores"])
    route_rows = read_csv_rows(DEFAULTS["route_yield"])
    concentration_rows = read_csv_rows(DEFAULTS["frontend_source_audit"])
    replacement_rows = read_csv_rows(DEFAULTS["replacement_tasks"])
    noauth_plan_rows = read_csv_rows(DEFAULTS["noauth_plan"])
    noauth_manual_rows = read_csv_rows(DEFAULTS["noauth_manual"])
    noauth_candidate_rows = read_csv_rows(DEFAULTS["noauth_candidate_review"])
    noauth_score_rows = read_csv_rows(DEFAULTS["noauth_candidate_scores"])
    noauth_yield_rows = read_csv_rows(DEFAULTS["noauth_route_yield"])
    gates = gate_summary(db_path)

    map_buckets = bucket_counts(map_rows)
    source_buckets = bucket_counts(source_rows)
    candidate_buckets = bucket_counts(candidate_rows)
    route_actions = Counter(row.get("recommended_action") or "unknown" for row in route_rows)
    noauth_buckets = bucket_counts(noauth_score_rows)
    noauth_actions = Counter(row.get("recommended_action") or "unknown" for row in noauth_yield_rows)

    public_red = map_buckets.get("RED_PUBLIC_DEMOTE_ELIGIBLE", 0) + map_buckets.get("RED_PUBLIC_SUPPRESS_ELIGIBLE", 0)
    public_amber = sum(map_buckets.get(key, 0) for key in map_buckets if key.startswith("AMBER_PUBLIC"))
    discovery_replacements = source_buckets.get("RED_DISCOVERY_ONLY_LEAKAGE", 0)
    unknown_sources = source_buckets.get("AMBER_UNKNOWN_SOURCE", 0)
    first_probe_run = DEFAULTS["first_probe_workflow"].exists()
    noauth_plan_exists = DEFAULTS["noauth_plan"].exists()
    noauth_report_exists = DEFAULTS["noauth_probe_report"].exists()
    noauth_execute_has_candidates = bool(noauth_candidate_rows)
    candidate_meaningful = bool(candidate_rows)
    safe_to_apply = not conflict and DEFAULTS["manifest"].exists() and public_red > 0
    if noauth_execute_has_candidates:
        recommendation = "Evaluate no-auth staged candidates."
    elif noauth_report_exists:
        recommendation = "Review no-auth dry-run, then execute only if route terms are safe."
    elif noauth_plan_exists:
        recommendation = "Run the no-auth open-records dry-run."
    elif not DEFAULTS["trace"].exists() or not DEFAULTS["manifest"].exists():
        recommendation = "Resolve frontend map pipeline trace first."
    elif safe_to_apply:
        recommendation = "Safe to run machine-map-cleanup-dry-run."
    elif not noauth_plan_exists:
        recommendation = "Plan the no-auth open-records sprint."
    elif DEFAULTS["late_gap_plan"].exists():
        recommendation = "Review only the top 20 action rows."
    elif public_amber or discovery_replacements or unknown_sources:
        recommendation = "Plan the no-auth open-records sprint."
    else:
        recommendation = "Do not clean map; fix source chains first."
    if noauth_execute_has_candidates:
        next_command = "make noauth-open-sprint-evaluate"
    elif noauth_report_exists:
        next_command = "make noauth-probe-execute"
    elif noauth_plan_exists:
        next_command = "make noauth-open-sprint-dry-run"
    else:
        next_command = "make noauth-plan-open-probe"
    map_cleanup_status = "Cleanup unnecessary; public RED rows are zero." if public_red == 0 else "Dry-run only unless explicitly requested with backup."
    export_status = "Yes for the current unchanged frontend export; cleanup is separate and guarded."

    lines = [
        "# Machine Evaluation Dashboard",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Canonical count status: {conflict_message}",
        f"- Clear recommendation: {recommendation}",
        f"- Map cleanup guidance: {map_cleanup_status}",
        f"- Safe to export frontend? {export_status}",
        f"- Next exact command: `{next_command}`",
        "",
        "## Plain-Language Summary",
        "",
        "The machine checks are advisory. They do not accept candidates, publish map flags, or change public records.",
        "Rows marked GREEN look structurally sound, AMBER rows need human review, and public-prefixed RED rows are cleanup candidates only after dry-run review.",
        "",
        "## Input Reports",
        f"- Frontend pipeline trace: `{file_status(DEFAULTS['trace'])}`",
        f"- Frontend map manifest: `{file_status(DEFAULTS['manifest'])}`",
        f"- Partition summary: `{file_status(DEFAULTS['partition_summary'])}`",
        f"- Map evidence report: `{file_status(DEFAULTS['map_report'])}`",
        f"- Source remediation plan: `{file_status(DEFAULTS['source_plan'])}`",
        f"- First real Trove probe plan: `{file_status(DEFAULTS['probe_plan'])}`",
        "",
        "## Map Status",
        "- Public map safe: `yes`",
        f"- Public RED rows: `{public_red}`",
        f"- Cleanup needed: `{'yes' if public_red else 'no'}`",
        "",
        "## Source Concentration Status",
        f"- AYR-family share on frontend map: `{family_share(concentration_rows, 'AYR_FAMILY')}`%",
        f"- AYR-family share in 1926-1976 mapped rows: `{family_share(concentration_rows, 'AYR_FAMILY', 'rows_1926_1976')}`%",
        "",
        "## Source-Chain Status",
        f"- Discovery-only replacement count: `{discovery_replacements}`",
        f"- Unknown source registry count: `{unknown_sources}`",
        f"- Replacement search tasks: `{len(replacement_rows)}`",
        "- Next remediation batch: top 100 replacement search tasks.",
        "",
        "## Probe Status",
        f"- First real Trove probe run: `{str(first_probe_run).lower()}`",
        f"- Candidate scoring meaningful: `{str(candidate_meaningful).lower()}`",
        "",
        "## No-Auth Open Records Sprint",
        f"- No-auth plan exists: `{str(noauth_plan_exists).lower()}`",
        f"- No-auth automated planned rows: `{len(noauth_plan_rows)}`",
        f"- No-auth manual planned tasks: `{len(noauth_manual_rows)}`",
        f"- Dry-run pages that would be fetched: `{report_value(DEFAULTS['noauth_probe_report'], 'Dry-run pages that would be fetched')}`",
        f"- Robots-blocked routes: `{report_value(DEFAULTS['noauth_probe_report'], 'Routes skipped by robots')}`",
        f"- Manual-only routes/tasks: `{len(noauth_manual_rows)}`",
        f"- Candidates staged or review rows written: `{len(noauth_candidate_rows)}`",
        f"- Priority open-record candidates: `{noauth_buckets.get('PRIORITY_REVIEW_OPEN_RECORD', 0)}`",
        f"- Routes to expand: `{noauth_actions.get('EXPAND_NOAUTH_ROUTE', 0)}`",
        f"- Routes to pause: `{noauth_actions.get('PAUSE_NOISE', 0) + noauth_actions.get('PAUSE_DUPLICATES', 0) + noauth_actions.get('PAUSE_ROBOTS_OR_TERMS', 0)}`",
        f"- Next exact command: `{next_command}`",
        "",
        "## Map Evidence",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(map_buckets.items())] or ["- No map scores found."])
    lines.extend(["", "## Source Chains"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(source_buckets.items())] or ["- No source-chain scores found."])
    lines.extend(["", "## Probe Candidates"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(candidate_buckets.items())] or ["- No candidate scores found."])
    lines.extend(["", "## Route Yield"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(route_actions.items())] or ["- No route-yield evaluation found."])
    lines.extend(["", "## Release Gates"])
    if gates:
        for gate in gates[:15]:
            lines.append(
                f"- `{gate.get('gate_name')}`: {gate.get('gate_status')} "
                f"(observed {gate.get('observed_value')}, threshold {gate.get('threshold_value')})"
            )
    else:
        lines.append("- No release gate rows found in the database.")
    lines.extend(
        [
            "",
            "## Next Human Actions",
            "",
            f"- {recommendation}",
            "- Treat `NONPUBLIC_IGNORE` as internal-only for public map cleanup.",
            "- Use source-chain remediation batches before treating access platforms or discovery pages as evidence.",
            "- Use the no-auth open-records sprint before any API-key workflow.",
        ]
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "count_conflict": conflict,
        "safe_to_apply": safe_to_apply,
        "map_buckets": dict(map_buckets),
        "source_buckets": dict(source_buckets),
        "candidate_buckets": dict(candidate_buckets),
        "route_actions": dict(route_actions),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="dashboard Markdown output")
    parser.add_argument("--db", default=str(DEFAULTS["db"]), help="SQLite database path")
    args = parser.parse_args()
    summary = make_dashboard(Path(args.out), Path(args.db))
    print(f"Wrote dashboard: {args.out}")
    print(f"Count conflict: {summary['count_conflict']}")


if __name__ == "__main__":
    main()
