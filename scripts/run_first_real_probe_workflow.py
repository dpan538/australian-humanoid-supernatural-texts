#!/usr/bin/env python3
"""Run a Trove metadata-only probe workflow, dry-run by default."""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
import evaluate_route_yield
import make_nonexpert_dashboard
import make_review_packet
import probe_trove_metadata_batch
import score_probe_candidates


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def run_workflow(
    *,
    db_path: Path,
    query_plan: Path,
    run_id: str,
    limit: int,
    max_results_per_query: int,
    execute: bool,
    registry: Path = ROOT / "config" / "source_registry.yml",
) -> dict[str, Any]:
    if execute and not os.environ.get("TROVE_API_KEY"):
        raise RuntimeError("TROVE_API_KEY is required when --execute is passed")
    probe_summary = probe_trove_metadata_batch.run_batch(
        db_path=db_path,
        query_plan_path=query_plan,
        registry_path=registry,
        run_id=run_id,
        limit=limit,
        max_results_per_query=max_results_per_query,
        execute=execute,
    )
    review_csv = ROOT / "data" / "review" / "v2" / f"{run_id}_candidate_review.csv"
    packet_dir = ROOT / "data" / "review" / "v2" / "packets" / run_id
    make_review_packet.make_packet(db_path, run_id, packet_dir, limit)
    candidate_scores = ROOT / "data" / "review" / "v2" / f"probe_candidate_machine_scores_{run_id}.csv"
    candidate_report = ROOT / "data" / "processed" / "v2" / f"probe_candidate_score_report_{run_id}.md"
    scored = score_probe_candidates.score_file(db_path, review_csv, None, candidate_scores, candidate_report, limit)
    source_scores = ROOT / "data" / "review" / "v2" / "source_chain_machine_scores.csv"
    route_out = ROOT / "data" / "processed" / "v2" / f"route_yield_evaluation_{run_id}.csv"
    route_report = ROOT / "data" / "processed" / "v2" / f"route_yield_evaluation_{run_id}.md"
    route_rows = evaluate_route_yield.evaluate_files(candidate_scores, source_scores, route_out, route_report)
    make_nonexpert_dashboard.make_dashboard(ROOT / "data" / "processed" / "v2" / "nonexpert_machine_evaluation_dashboard.md", db_path)
    workflow_report = ROOT / "data" / "processed" / "v2" / "first_real_probe_workflow_report.md"
    buckets = Counter(row.get("machine_bucket") or "unknown" for row in scored)
    route_actions = Counter(row.get("recommended_action") or "unknown" for row in route_rows)
    lines = [
        "# First Real Probe Workflow Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Queries attempted: `{probe_summary.get('queries_attempted', 0)}`",
        f"- Metadata candidates staged/written: `{probe_summary.get('candidates', 0)}`",
        f"- Candidate review CSV rows: `{count_rows(review_csv)}`",
        f"- Priority review candidates: `{buckets.get('PRIORITY_REVIEW', 0)}`",
        f"- Context noise candidates: `{buckets.get('EXCLUDE_CONTEXT_NOISE', 0)}`",
        f"- Duplicate candidates skipped/excluded: `{buckets.get('EXCLUDE_DUPLICATE', 0)}`",
        f"- Route yield recommendation counts: `{dict(route_actions)}`",
        "- Candidates accepted: `0`",
        "- Map flags published: `0`",
        "- Warning: this workflow stages/reviews metadata only; it does not import reviewed candidates automatically.",
    ]
    workflow_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "execute": execute,
        "queries_attempted": probe_summary.get("queries_attempted", 0),
        "candidates": probe_summary.get("candidates", 0),
        "priority_review": buckets.get("PRIORITY_REVIEW", 0),
        "route_actions": dict(route_actions),
        "report": workflow_report,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--query-plan", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--max-results-per-query", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    summary = run_workflow(
        db_path=Path(args.db),
        query_plan=Path(args.query_plan),
        run_id=args.run_id,
        limit=args.limit,
        max_results_per_query=args.max_results_per_query,
        execute=bool(args.execute and not args.dry_run),
    )
    print(f"Workflow report: {summary['report']}")
    print(f"Candidates staged/written: {summary['candidates']}")


if __name__ == "__main__":
    main()
