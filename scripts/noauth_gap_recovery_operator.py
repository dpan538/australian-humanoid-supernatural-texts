#!/usr/bin/env python3
"""Run the no-key no-auth target-gap recovery ladder."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from autoharvest_gap_supervisor import supervise
from build_target_acquisition_plan import build_plan
from cluster_and_repair_search_forms import repair as repair_forms
from collection_expansion_common import now_iso, write_csv
from deepen_viable_pdf_newsletter_routes import deepen as deepen_pdfs
from discover_targets_via_public_url_indexes import discover as discover_indexes
from expand_routes_from_source_atlas import expand as expand_atlas
from lib.gap_recovery import classify_recovery_status, read_csv, write_report
from mine_noauth_access_platforms_for_gap import mine as mine_access_platforms
from recover_gap_near_misses import recover as recover_near_misses
from run_target_acquisition_viability_test import run_viability


def count_rows(path: Path) -> int:
    return len(read_csv(path))


def summarize_watchdog() -> str:
    path = ROOT / "data" / "processed" / "v2" / "autoharvest" / "noauth_gap_marathon_001_watchdog.md"
    if not path.exists():
        return "not_run"
    text = path.read_text(encoding="utf-8")
    return "hard_0" if "Hard violations: `0`" in text else "see_watchdog_report"


def run_recovery(db_path: Path, config_path: Path, run_id: str, target: int, execute: bool, max_cycles: int = 3) -> dict:
    seeds = ROOT / "config" / "noauth_open_source_seeds.yml"
    registry = ROOT / "config" / "source_registry.yml"
    matrix = ROOT / "config" / "query_matrix_1926_1976.yml"
    forms_path = ROOT / "data" / "interim" / "source_discovery" / "noauth_search_forms.csv"
    viability_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_acquisition_viability"
    postmortem_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "zero_yield_postmortem"
    summary_path = ROOT / "data" / "processed" / "v2" / "autoharvest" / "noauth_gap_recovery_operator_summary.md"
    status = classify_recovery_status(
        count_rows(viability_dir / "viability_target_records.csv"),
        sum(1 for row in read_csv(viability_dir / "viability_candidates.csv") if row.get("gate_status") == "high_quality_near_miss"),
        2 if (viability_dir / "viability_candidates.csv").exists() else 0,
        search_forms=count_rows(forms_path),
    )
    cycle_summaries: list[dict] = []
    resumed = False
    resume_summary = {}
    final_viability = {}
    expanded_seeds = ROOT / "config" / "noauth_open_source_seeds_expanded.yml"
    for cycle in range(1, max_cycles + 1):
        near = recover_near_misses(db_path, "noauth_gap_viability_001", ROOT / "data" / "processed" / "v2" / "autoharvest" / "recovery_near_misses", execute)
        pdf = deepen_pdfs(db_path, viability_dir, "noauth_gap_pdf_deepening_001", 20, 100, execute)
        forms = repair_forms(forms_path, viability_dir, ROOT / "data" / "processed" / "v2" / "autoharvest" / "search_form_repair", execute)
        index = {"urls": 0, "archived": 0, "route_candidates": 0}
        access = {"candidates": 0, "decomposed": 0, "holds": 0}
        if cycle == 1 and status != "FAILED_EXHAUSTED":
            index = discover_indexes(db_path, seeds, registry, "noauth_gap_index_discovery_001", ROOT / "data" / "processed" / "v2" / "autoharvest" / "public_index_discovery", 8, 10, execute)
            access = mine_access_platforms(db_path, registry, "noauth_gap_access_platform_001", ROOT / "data" / "processed" / "v2" / "autoharvest" / "access_platform_gap_mining", execute)
        atlas = expand_atlas(ROOT / "docs" / "research" / "SOURCE_ROUTE_ATLAS_SEED.md", registry, seeds, expanded_seeds, ROOT / "data" / "processed" / "v2" / "autoharvest" / "source_atlas_expansion_report.md")
        plan_path = ROOT / "data" / "interim" / "collection_plans" / f"target_acquisition_recovery_cycle_{cycle}.csv"
        plan_report = ROOT / "data" / "processed" / "v2" / "autoharvest" / f"target_acquisition_recovery_cycle_{cycle}.md"
        plan = build_plan(db_path, postmortem_dir, expanded_seeds if expanded_seeds.exists() else seeds, registry, matrix, plan_path, plan_report, 1000)
        final_viability = run_viability(db_path, plan_path, f"{run_id}_viability_cycle_{cycle}", 500, execute)
        cycle_summary = {
            "cycle": cycle,
            "near_recovered": near.get("recovered", 0),
            "pdf_targets": pdf.get("targets", 0),
            "pdf_near_misses": pdf.get("near_misses", 0),
            "forms_repaired": forms.get("plan", 0),
            "index_urls": index.get("urls", 0),
            "access_decomposed": access.get("decomposed", 0),
            "atlas_added": atlas.get("added", 0),
            "plan_actions": len(plan),
            "viability_status": final_viability.get("viability_status"),
            "viability_targets": final_viability.get("target_records", 0),
            "viability_near_misses": final_viability.get("near_misses", 0),
        }
        cycle_summaries.append(cycle_summary)
        if final_viability.get("should_resume_gap_marathon"):
            resume_summary = supervise(db_path, config_path, expanded_seeds if expanded_seeds.exists() else seeds, "noauth_gap_marathon_001", target, execute=True, max_segments=100)
            resumed = True
            break
        status = classify_recovery_status(
            int(final_viability.get("target_records", 0)),
            int(final_viability.get("near_misses", 0)),
            int(final_viability.get("viable_pdf_routes", 0)),
            search_forms=forms.get("plan", 0),
            index_discoveries=index.get("urls", 0),
            route_expansion_candidates=atlas.get("added", 0),
        )
        if status == "FAILED_EXHAUSTED":
            break
        new_surfaces = int(near.get("recovered", 0)) + int(pdf.get("targets", 0)) + int(pdf.get("expand", 0)) + int(index.get("urls", 0)) + int(access.get("decomposed", 0)) + int(atlas.get("added", 0) if cycle == 1 else 0)
        if int(final_viability.get("target_records", 0)) == 0 and new_surfaces == 0:
            break
    write_cycle_csv(summary_path.with_suffix(".csv"), cycle_summaries)
    bullets = {
        "Run ID": run_id,
        "Execute": str(execute).lower(),
        "Initial recovery status": status,
        "Cycles completed": len(cycle_summaries),
        "Target-gap effective records found": final_viability.get("target_records", 0),
        "High-quality near misses remaining": final_viability.get("near_misses", 0),
        "Viable PDF/newsletter routes": final_viability.get("viable_pdf_routes", 0),
        "Search forms repaired/probed": cycle_summaries[-1].get("forms_repaired", 0) if cycle_summaries else 0,
        "Public-index URLs discovered": sum(int(row.get("index_urls", 0)) for row in cycle_summaries),
        "Access-platform decomposed candidates": sum(int(row.get("access_decomposed", 0)) for row in cycle_summaries),
        "Source-atlas routes added": cycle_summaries[-1].get("atlas_added", 0) if cycle_summaries else 0,
        "Gap marathon resumed": str(resumed).lower(),
        "Watchdog status": summarize_watchdog(),
        "Public records mutated": "no",
        "Map flags mutated": "no",
        "Frontend/public data promoted": "no",
        "Next automatic action": "resume gap marathon" if resumed else "no-key no-auth recovery exhausted or still non-target-yielding under current gates",
    }
    write_report(
        summary_path,
        "No-Auth Gap Recovery Operator Summary",
        bullets,
        {"Cycle Summaries": [f"- cycle {row['cycle']}: status `{row.get('viability_status')}`, targets `{row.get('viability_targets')}`, near misses `{row.get('viability_near_misses')}`, forms `{row.get('forms_repaired')}`, index URLs `{row.get('index_urls')}`" for row in cycle_summaries]},
    )
    return {"resumed": resumed, "cycles": len(cycle_summaries), "final_viability": final_viability, "summary": str(summary_path), "resume_summary": resume_summary}


def write_cycle_csv(path: Path, rows: list[dict]) -> None:
    write_csv(path, rows, list(rows[0].keys()) if rows else ["cycle"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_recovery(Path(args.db), Path(args.config), args.run_id, args.target_gap_effective_records, execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
