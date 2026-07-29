#!/usr/bin/env python3
"""Summarize whether no-credential target-gap collection is exhausted."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists
from migrate_structured_near_miss_v1 import migrate


def count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    return int((conn.execute(sql, params).fetchone() or [0])[0] or 0)


def read_metric(path: Path, label: str) -> str:
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(rf"{re.escape(label)}:\s*`?([^`\n]+)`?", text)
    return match.group(1).strip() if match else ""


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def count_csv_values(path: Path, field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in read_csv_rows(path):
        key = row.get(field) or ""
        counts[key] = counts.get(key, 0) + 1
    return counts


def report(db: Path, structured_run_id: str, recovery_summary: Path, structured_checkpoint: Path, out: Path) -> dict[str, Any]:
    migrate(db)
    structured_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
    review_dir = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"
    robots_csv = structured_dir / "robots_block_audit" / "robots_block_audit.csv"
    existing_csv = review_dir / "existing_metadata_enrichment_candidates.csv"
    atom_csv = structured_dir / "atom_atomm_repair" / "atom_atomm_enriched_records.csv"
    rss_csv = structured_dir / "rss_inline_enrichment" / "rss_inline_near_misses_remaining.csv"
    alternatives_csv = structured_dir / "allowed_detail_alternatives.csv"
    allowed_remaining_csv = review_dir / "allowed_detail_remaining_near_misses.csv"
    robots_counts = count_csv_values(robots_csv, "robots_status")
    robots_issue_counts = count_csv_values(robots_csv, "url_issue")
    safe_alternatives = sum(1 for row in read_csv_rows(alternatives_csv) if str(row.get("safe_to_fetch") or "").lower() == "true")
    alternatives_enriched = len(read_csv_rows(allowed_remaining_csv)) + len(read_csv_rows(review_dir / "allowed_detail_target_candidates.csv"))
    existing_metadata_rows = len(read_csv_rows(existing_csv))
    atom_rows = len(read_csv_rows(atom_csv))
    rss_rows = len(read_csv_rows(rss_csv))
    robots_rescue_attempted = robots_csv.exists() and existing_csv.exists() and atom_csv.exists() and rss_csv.exists() and alternatives_csv.exists()
    with sqlite3.connect(db) as conn:
        structured_targets = count(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=1", (structured_run_id,))
        structured_records = count(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=?", (structured_run_id,))
        structured_near = count(
            conn,
            "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND target_gap_eligible=0 AND ((controlled_term_hits IS NOT NULL AND controlled_term_hits NOT IN ('[]','')) OR inferred_year IS NOT NULL)",
            (structured_run_id,),
        )
        queued = (
            count(
                conn,
                """
                SELECT COUNT(*)
                FROM noauth_endpoint_queries q
                JOIN noauth_endpoint_inventory i ON i.endpoint_id=q.endpoint_id
                WHERE q.run_id=? AND q.status='queued' AND i.status='active'
                """,
                (structured_run_id,),
            )
            if table_exists(conn, "noauth_endpoint_queries")
            else 0
        )
        endpoints = count(conn, "SELECT COUNT(*) FROM noauth_endpoint_inventory") if table_exists(conn, "noauth_endpoint_inventory") else 0
        materialized_near = count(conn, "SELECT COUNT(*) FROM structured_endpoint_near_misses WHERE run_id=?", (structured_run_id,)) if table_exists(conn, "structured_endpoint_near_misses") else 0
        recoverable_near = (
            count(
                conn,
                """
                SELECT COUNT(*)
                FROM structured_endpoint_near_misses
                WHERE run_id=?
                  AND recoverability_score >= 50
                  AND recovery_status NOT IN (
                    'target_gap_eligible',
                    'HOLD_ROBOTS_DENIED',
                    'HOLD_MALFORMED_URL',
                    'HOLD_LOGIN_OR_AUTH',
                    'exhausted_unrecoverable',
                    'held_unrecoverable'
                  )
                """,
                (structured_run_id,),
            )
            if table_exists(conn, "structured_endpoint_near_misses")
            else 0
        )
        enrichment_attempted = (
            count(conn, "SELECT COUNT(*) FROM structured_endpoint_near_misses WHERE run_id=? AND enrichment_attempted=1", (structured_run_id,))
            if table_exists(conn, "structured_endpoint_near_misses")
            else 0
        )
        enriched_records = count(conn, "SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=?", (structured_run_id,)) if table_exists(conn, "structured_endpoint_enriched_records") else 0
        enriched_targets = count(conn, "SELECT COUNT(*) FROM structured_endpoint_enriched_records WHERE run_id=? AND target_gap_eligible=1", (structured_run_id,)) if table_exists(conn, "structured_endpoint_enriched_records") else 0
        adapter_rows = count(conn, "SELECT COUNT(*) FROM noauth_endpoint_records WHERE run_id=? AND (title IS NULL OR title='' OR item_url IS NULL OR item_url='')", (structured_run_id,))
        lead_count = count(conn, "SELECT COUNT(*) FROM target_gap_leads") if table_exists(conn, "target_gap_leads") else 0
        priority_leads = count(conn, "SELECT COUNT(*) FROM target_gap_leads WHERE priority_bucket='PRIORITY_LEAD'") if table_exists(conn, "target_gap_leads") else 0
    previous_target = read_metric(recovery_summary, "- Target-gap effective records found") or read_metric(recovery_summary, "- Target-gap effective records")
    observability_incomplete = structured_near > 0 and materialized_near == 0
    enrichment_incomplete = materialized_near > 0 and enrichment_attempted == 0
    near_remaining = materialized_near > 0 and recoverable_near > 0
    robots_unknown = sum(robots_counts.get(key, 0) for key in ["ROBOTS_UNKNOWN_TIMEOUT", "ROBOTS_UNKNOWN_HTTP_ERROR", "ROBOTS_UNKNOWN_MISSING_ROBOTS"])
    robots_diagnosed = sum(robots_counts.values())
    robots_unknown_dominates = robots_diagnosed > 0 and robots_unknown >= max(1, robots_diagnosed // 2)
    materialized_exhausted = structured_near == 0 or (materialized_near > 0 and recoverable_near == 0 and enrichment_attempted > 0)
    status = (
        "observability_incomplete"
        if observability_incomplete
        else "target_records_found"
        if structured_targets or enriched_targets
        else "robots_rescue_incomplete"
        if materialized_near > 0 and not robots_rescue_attempted
        else "enrichment_incomplete"
        if enrichment_incomplete
        else "strict_records_blocked_but_lead_mode_available"
        if lead_count > 0
        else "robots_uncertainty_blocked"
        if robots_unknown_dominates
        else "recoverable_near_misses_remain"
        if near_remaining or safe_alternatives > 0
        else "strict_no_credential_exhausted"
    )
    no_credential_strict_mode_exhausted = (
        status == "strict_no_credential_exhausted"
        and structured_targets == 0
        and enriched_targets == 0
        and queued == 0
        and materialized_exhausted
        and robots_rescue_attempted
        and not robots_unknown_dominates
        and safe_alternatives == 0
        and lead_count == 0
    )
    lines = [
        "# No-Credential Target-Gap Infeasibility Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Structured run ID: `{structured_run_id}`",
        f"- Previous recovery target result: `{previous_target or 'unknown'}`",
        f"- Status: `{status}`",
        f"- Structured endpoints discovered/known: `{endpoints}`",
        f"- Structured endpoint records seen: `{structured_records}`",
        f"- Structured target-gap records: `{structured_targets}`",
        f"- Structured near misses: `{structured_near}`",
        f"- Near misses materialized into rows: `{materialized_near}`",
        f"- Two-hop enrichment attempted rows: `{enrichment_attempted}`",
        f"- Enriched records: `{enriched_records}`",
        f"- Enriched target-gap records: `{enriched_targets}`",
        f"- Recoverable materialized near misses remaining: `{recoverable_near}`",
        f"- Structured queued queries remaining: `{queued}`",
        f"- Adapter field mapping missing title/url rows: `{adapter_rows}`",
        f"- Target-gap leads available: `{lead_count}`",
        f"- Priority target-gap leads: `{priority_leads}`",
        "",
        "## Robots-aware near-miss rescue",
        f"- Materialized near misses count: `{materialized_near}`",
        f"- Robots diagnosis rows: `{robots_diagnosed}`",
        f"- Robots diagnosis by category: `{json.dumps(robots_counts, sort_keys=True)}`",
        f"- URL issue diagnosis by category: `{json.dumps(robots_issue_counts, sort_keys=True)}`",
        f"- Existing metadata enrichment rows: `{existing_metadata_rows}`",
        f"- AtoM repair rows: `{atom_rows}`",
        f"- RSS inline enrichment remaining rows: `{rss_rows}`",
        f"- Safe alternative detail URLs discovered: `{safe_alternatives}`",
        f"- Detail alternatives enriched/remaining rows: `{alternatives_enriched}`",
        f"- Robots rescue attempted: `{str(robots_rescue_attempted).lower()}`",
        f"- Remaining recoverable near misses: `{recoverable_near}`",
        "",
        f"- no_credential_strict_mode_exhausted: `{str(no_credential_strict_mode_exhausted).lower()}`",
        f"- Declare no-credential target collection infeasible now: `{str(no_credential_strict_mode_exhausted).lower()}`",
        "- Public records changed: `no`",
        "- Map flags changed: `no`",
        "- Frontend/public data promoted: `no`",
        "- API keys used: `no`",
        "",
        "## Interpretation",
    ]
    if no_credential_strict_mode_exhausted:
        lines.append("- No-key/no-auth target collection is not viable under the current gates and current source universe after materialized near misses and two-hop enrichment were exhausted.")
    elif observability_incomplete:
        lines.append("- Status is observability_incomplete: reports show near misses, but durable near-miss rows are missing or unexplained.")
    elif status == "robots_rescue_incomplete":
        lines.append("- Status is robots_rescue_incomplete: materialized near misses exist, but robots-aware rescue artifacts are not complete, so infeasibility cannot be declared.")
    elif status == "robots_uncertainty_blocked":
        lines.append("- Status is robots_uncertainty_blocked: robots UNKNOWN categories dominate, and uncertainty is blocked closed rather than treated as permission.")
    elif status == "strict_records_blocked_but_lead_mode_available":
        lines.append("- Strict records mode remains blocked, but lead mode is available as a lower-evidence observational layer. Leads are not public records and do not publish map flags.")
    elif enrichment_incomplete:
        lines.append("- Do not declare infeasibility yet; materialized near misses exist but two-hop enrichment has not been attempted.")
    elif near_remaining:
        lines.append("- Do not declare infeasibility yet; recoverable materialized near misses remain.")
    else:
        lines.append("- Do not declare infeasibility yet; structured targets, near misses, or queued endpoint work remain.")
    lines.extend(
        [
            "",
            "## Exhaustion Requirements",
            "- HTML frontier exhausted: `not proven by this report`",
            "- Search forms exhausted: `not proven by this report`",
            "- PDF/newsletter deepening exhausted: `not proven by this report`",
            "- Public URL indexes exhausted or unavailable: `not proven by this report`",
            f"- Structured endpoints exhausted: `{str(queued == 0).lower()}`",
            f"- Materialized near misses exhausted: `{str(materialized_exhausted).lower()}`",
            f"- Two-hop enrichment exhausted: `{str(materialized_exhausted).lower()}`",
            f"- Robots-aware near-miss rescue exhausted: `{str(robots_rescue_attempted and not robots_unknown_dominates and safe_alternatives == 0 and recoverable_near == 0).lower()}`",
            f"- Adapter debug shows no recoverable parser issue: `{str(adapter_rows == 0).lower()}`",
            "- Access-platform decomposition failed or produced no eligible candidates: `not proven by this report`",
            "- Watchdog remains clean: `not proven by this report`",
            "",
            "## Failure Modes",
            f"- No date evidence rows: `{max(0, structured_near - materialized_near) if observability_incomplete else 0}`",
            "- No controlled term / date-only rows: see structured endpoint materialization report.",
            "- No item URL / parser failure rows: see adapter debug report.",
            "- D-class access candidates decomposable: see access platform endpoint reports.",
            "",
            "## Mode Distinctions",
            "- Strict records mode: requires all public-record gates and remains blocked.",
            "- Lead mode: observational planning layer; does not create public records.",
            "- Metadata-only layer: useful for 1955-1976 leads but not strict evidence records.",
            "- Access-platform layer: discovery/source-chain work only unless originals are decomposed.",
            "- Human-review-assisted mode: optional tiny top-N review, currently disabled.",
            "- API-key-assisted mode: optional Trove/API-key path, currently disabled.",
        ]
    )
    lines.extend(
        [
            "",
            "## Strategic Options",
            "- Keep gates intact and acquire credentials for sanctioned metadata APIs where allowed.",
            "- Add new A/B/C no-auth institutional routes to the source atlas.",
            "- Use human review for high-value near misses rather than broadening automated acceptance.",
            "- Treat D-class access platforms as discovery until original/evidence sources are decomposed.",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "structured_targets": structured_targets,
        "structured_near_misses": structured_near,
        "materialized_near_misses": materialized_near,
        "enrichment_attempted": enrichment_attempted,
        "recoverable_near_misses": recoverable_near,
        "target_gap_leads": lead_count,
        "priority_target_gap_leads": priority_leads,
        "robots_status_counts": robots_counts,
        "robots_issue_counts": robots_issue_counts,
        "robots_rescue_attempted": robots_rescue_attempted,
        "safe_alternative_detail_urls": safe_alternatives,
        "alternatives_enriched": alternatives_enriched,
        "queued": queued,
        "status": status,
        "declare_infeasible": no_credential_strict_mode_exhausted,
        "no_credential_strict_mode_exhausted": no_credential_strict_mode_exhausted,
        "out": str(out),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--structured-run-id", default="noauth_structured_endpoint_001")
    parser.add_argument("--recovery-summary", default="data/processed/v2/autoharvest/noauth_gap_recovery_operator_summary.md")
    parser.add_argument("--structured-checkpoint", default="data/processed/v2/autoharvest/structured_endpoints/noauth_structured_endpoint_001_checkpoint.md")
    parser.add_argument("--out", default="data/processed/v2/autoharvest/no_credential_infeasibility_report.md")
    args = parser.parse_args()
    print(json.dumps(report(Path(args.db), args.structured_run_id, Path(args.recovery_summary), Path(args.structured_checkpoint), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
