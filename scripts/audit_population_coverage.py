#!/usr/bin/env python3
"""Audit corpus state coverage against ABS state/territory population."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT


DEFAULT_FRONTEND_DATA = PROJECT_ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_POPULATION = PROJECT_ROOT / "config" / "state_population_abs_2025_dec.yml"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "population_coverage_audit.md"
DEFAULT_CSV = PROJECT_ROOT / "data" / "exports" / "v2" / "population_coverage_audit.csv"
STATE_CODES = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"]


def per_million(count: int, population: int) -> float:
    if population <= 0:
        return 0.0
    return count / population * 1_000_000


def proportional_target(population: int, total_population: int, target_total: int) -> int:
    if total_population <= 0:
        return 0
    return round(target_total * population / total_population)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def build_rows(frontend_data: dict[str, Any], population_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    summary = frontend_data.get("summary", {})
    display_counts = summary.get("corpus_state_counts") or summary.get("state_record_counts") or {}
    mapped_counts = summary.get("mapped_state_counts") or {}
    populations = population_cfg["population"]
    targets = population_cfg.get("targets", {})
    min_per_state = int(targets.get("minimum_records_per_state", 100))
    mapped_target_total = int(targets.get("mapped_records_total", targets.get("strict_map_points_total", 1500)))
    display_target_total = int(targets.get("display_records_total", 3500))
    total_population = int(populations.get("AU") or sum(int(populations[code]) for code in STATE_CODES))

    rows: list[dict[str, Any]] = []
    for code in STATE_CODES:
        population = int(populations[code])
        display = int(display_counts.get(code, 0))
        mapped = int(mapped_counts.get(code, 0))
        display_prop_target = proportional_target(population, total_population, display_target_total)
        mapped_prop_target = proportional_target(population, total_population, mapped_target_total)
        rows.append(
            {
                "state": code,
                "population": population,
                "display_records": display,
                "mapped_records": mapped,
                "display_records_per_million": round(per_million(display, population), 2),
                "mapped_records_per_million": round(per_million(mapped, population), 2),
                "gap_to_minimum_display_100": max(0, min_per_state - display),
                "gap_to_minimum_mapped_100": max(0, min_per_state - mapped),
                "proportional_display_target_3500": display_prop_target,
                "gap_to_proportional_display_target": max(0, display_prop_target - display),
                "proportional_mapped_target_1500": mapped_prop_target,
                "gap_to_proportional_mapped_target": max(0, mapped_prop_target - mapped),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, rows: list[dict[str, Any]], frontend_data: dict[str, Any], population_cfg: dict[str, Any]) -> None:
    summary = frontend_data.get("summary", {})
    source = population_cfg.get("source", {})
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    totals = {
        "display_records": sum(int(row["display_records"]) for row in rows),
        "mapped_records": sum(int(row["mapped_records"]) for row in rows),
        "gap_min_display": sum(int(row["gap_to_minimum_display_100"]) for row in rows),
        "gap_min_mapped": sum(int(row["gap_to_minimum_mapped_100"]) for row in rows),
        "gap_prop_display": sum(int(row["gap_to_proportional_display_target"]) for row in rows),
        "gap_prop_mapped": sum(int(row["gap_to_proportional_mapped_target"]) for row in rows),
    }

    lines = [
        "# Population Coverage Audit",
        "",
        f"- Generated: `{generated_at}`",
        f"- Frontend data record count: `{summary.get('record_count')}`",
        f"- Mapped record count: `{summary.get('mapped_record_count')}`",
        f"- Population source: {source.get('organisation')} — {source.get('publication')}",
        f"- Population table: `{source.get('table')}`",
        f"- Reference date: `{source.get('reference_date')}`",
        f"- Source URL: {source.get('url')}",
        "",
        "## Interpretation Guardrail",
        "",
        "This audit measures public-record coverage against population distribution. It does not measure the prevalence of supernatural claims, traditions, beings, sightings, or beliefs.",
        "",
        "## Summary",
        "",
        f"- Display records assigned to a state/territory: `{totals['display_records']}`",
        f"- Mapped records assigned to a state/territory: `{totals['mapped_records']}`",
        f"- Additional display records needed for every state/territory to reach 100: `{totals['gap_min_display']}`",
        f"- Additional mapped records needed for every state/territory to reach 100: `{totals['gap_min_mapped']}`",
        f"- Additional display records needed to approach a 3,500-record population-proportional target: `{totals['gap_prop_display']}`",
        f"- Additional mapped records needed to approach a 1,500-record population-proportional target: `{totals['gap_prop_mapped']}`",
        "",
        "## State/Territory Coverage",
        "",
        "| State | Population | Display | Mapped | Display / 1m | Mapped / 1m | Gap to 100 display | Gap to 100 mapped | 3,500 display proportional target | Gap | 1,500 mapped proportional target | Gap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {state} | {population} | {display_records} | {mapped_records} | {display_records_per_million} | {mapped_records_per_million} | {gap_to_minimum_display_100} | {gap_to_minimum_mapped_100} | {proportional_display_target_3500} | {gap_to_proportional_display_target} | {proportional_mapped_target_1500} | {gap_to_proportional_mapped_target} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Collection Implication",
            "",
            "- WA, NT, SA, TAS, ACT, and VIC remain the priority states for mapped-record collection.",
            "- NSW and QLD are already overrepresented relative to the current corpus and should receive only high-quality non-duplicative additions in the next collection pass.",
            "- Broad or unresolved geography can still support dashboard and density views, but it should not be counted as a strict map point.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-data", default=str(DEFAULT_FRONTEND_DATA))
    parser.add_argument("--population", default=str(DEFAULT_POPULATION))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    args = parser.parse_args()

    frontend_data = load_json(Path(args.frontend_data))
    population_cfg = load_yaml(Path(args.population))
    rows = build_rows(frontend_data, population_cfg)
    write_csv(Path(args.csv), rows)
    write_report(Path(args.report), rows, frontend_data, population_cfg)
    print(json.dumps({"rows": len(rows), "report": args.report, "csv": args.csv}, indent=2))


if __name__ == "__main__":
    main()
