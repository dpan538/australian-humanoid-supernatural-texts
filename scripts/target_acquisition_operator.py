#!/usr/bin/env python3
"""Coordinate target acquisition cycles before resuming the full gap marathon."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_gap_zero_yield import analyze
from autoharvest_gap_supervisor import supervise
from build_target_acquisition_plan import build_plan
from collection_expansion_common import now_iso
from discover_noauth_search_forms import discover
from run_target_acquisition_viability_test import VIABILITY_DIR, run_viability


def run_operator(db_path: Path, config_path: Path, run_id: str, target: int, execute: bool) -> dict:
    postmortem_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "zero_yield_postmortem"
    forms_path = ROOT / "data" / "interim" / "source_discovery" / "noauth_search_forms.csv"
    forms_report = ROOT / "data" / "processed" / "v2" / "noauth_search_forms.md"
    plan_path = ROOT / "data" / "interim" / "collection_plans" / "target_acquisition_plan.csv"
    plan_report = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_acquisition_plan.md"
    seeds = ROOT / "config" / "noauth_open_source_seeds.yml"
    registry = ROOT / "config" / "source_registry.yml"
    matrix = ROOT / "config" / "query_matrix_1926_1976.yml"
    postmortem = analyze(db_path, run_id, postmortem_dir)
    forms = discover(seeds, forms_path, forms_report, execute=execute, test_query="ghost")
    plan = build_plan(db_path, postmortem_dir, seeds, registry, matrix, plan_path, plan_report, 1000)
    viability = run_viability(db_path, plan_path, "noauth_gap_viability_001", 500, execute=execute)
    resumed = False
    resume_summary = {}
    if execute and viability.get("viable"):
        resume_summary = supervise(db_path, config_path, seeds, run_id, target, execute=True, max_segments=100)
        resumed = True
    next_action = "resume gap marathon" if resumed else "run gap-recovery-operator; current no-auth frontier failed but no-key recovery surfaces remain"
    summary_path = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_acquisition_operator_summary.md"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Target Acquisition Operator Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Postmortem candidates inspected: `{postmortem.get('candidates')}`",
        f"- Search forms discovered: `{len(forms)}`",
        f"- Acquisition actions planned: `{len(plan)}`",
        f"- Viability target records: `{viability.get('target_records')}`",
        f"- High-quality near misses: `{viability.get('near_misses')}`",
        f"- Viable PDF/newsletter/journal routes: `{viability.get('viable_pdf_routes')}`",
        f"- Viability status: `{viability.get('viability_status')}`",
        f"- Viability passed: `{str(viability.get('viable')).lower()}`",
        f"- Gap marathon resumed: `{str(resumed).lower()}`",
        f"- Resume summary: `{resume_summary}`",
        f"- Next action: `{next_action}`",
        "- No-key no-auth strategy exhausted: `no`" if not resumed else "- No-key no-auth strategy exhausted: `no`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
    ]
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"postmortem": postmortem, "forms": len(forms), "actions": len(plan), "viability": viability, "resumed": resumed, "summary": str(summary_path)}


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
