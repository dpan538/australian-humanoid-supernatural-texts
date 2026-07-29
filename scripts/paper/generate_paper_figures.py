#!/usr/bin/env python3
"""Generate paper figure data tables and simple SVG charts."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from paper_common import (
    DEFAULT_CONFIG,
    docs_dir,
    load_config,
    load_json,
    read_csv_rows,
    rel_path,
    release_dir,
    write_csv,
    write_json,
    write_manifest,
)


SCRIPT_NAME = "generate_paper_figures.py"


def numeric(value: Any) -> float | None:
    try:
        if value in {None, ""}:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def top_rows(rows: list[dict[str, Any]], n: int = 10) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: numeric(row.get("count")) or 0, reverse=True)[:n]


def bar_svg(path: Path, title: str, rows: list[dict[str, Any]], label_key: str = "label", value_key: str = "count") -> None:
    width = 960
    row_h = 34
    top = 58
    left = 260
    chart_w = 620
    height = max(180, top + row_h * len(rows) + 36)
    max_value = max([numeric(row.get(value_key)) or 0 for row in rows] or [0])
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="24" y="34" font-family="Arial, sans-serif" font-size="22" font-weight="700" fill="#111111">{html.escape(title)}</text>',
    ]
    for index, row in enumerate(rows):
        y = top + index * row_h
        value = numeric(row.get(value_key)) or 0
        bar_w = 0 if max_value == 0 else int(value / max_value * chart_w)
        label = str(row.get(label_key) or row.get("value") or "")
        parts.extend(
            [
                f'<text x="24" y="{y + 20}" font-family="Arial, sans-serif" font-size="14" fill="#222222">{html.escape(label[:42])}</text>',
                f'<rect x="{left}" y="{y}" width="{bar_w}" height="22" fill="#2f6f73"/>',
                f'<text x="{left + bar_w + 8}" y="{y + 17}" font-family="Arial, sans-serif" font-size="13" fill="#222222">{value:g}</text>',
            ]
        )
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def count_reconciliation_rows(stats: dict[str, Any]) -> list[dict[str, Any]]:
    wanted = {
        ("local_frontend_export_display_counts", "frontend_records"): "Local frontend records",
        ("local_frontend_export_display_counts", "frontend_map_points"): "Local frontend map rows",
        ("legacy_flat_record_corpus_counts", "records_total"): "Legacy records table",
        ("v2_normalized_public_corpus_counts", "source_items_total"): "V2 source items",
        ("v2_normalized_public_corpus_counts", "narrative_units_total"): "V2 narrative units",
        ("lead_mode_conversion_counts", "target_gap_leads_total"): "Lead-mode rows",
        ("strict_no_credential_record_gate_experiment_counts", "strict_target_gap_records"): "Strict-gate records",
    }
    result = []
    for row in stats.get("counts", []):
        key = (row.get("count_family"), row.get("metric"))
        if key not in wanted:
            continue
        value = numeric(row.get("value"))
        if value is None:
            continue
        result.append(
            {
                "label": wanted[key],
                "count_family": key[0],
                "metric": key[1],
                "count": int(value) if value.is_integer() else value,
                "source": row.get("source", ""),
                "notes": row.get("notes", ""),
            }
        )
    return result


def write_inventory(path: Path, generated: list[dict[str, str]]) -> None:
    lines = [
        "# Figure And Table Inventory",
        "",
        "This inventory lists reproducible figure/table assets for the manuscript. The SVG files are convenience renderings; CSV files are the source of truth.",
        "",
        "| id | role | path | manuscript use |",
        "| --- | --- | --- | --- |",
    ]
    for row in generated:
        lines.append(f"| {row['id']} | {row['role']} | `{row['path']}` | {row['use']} |")
    lines.extend(
        [
            "",
            "## Planned Manuscript Tables",
            "",
            "- Table 1: Count-family reconciliation and non-mixing rules.",
            "- Table 2: Source-chain fields, blocker classes, and record/lead outcomes.",
            "- Table 3: Manual audit coding frame and inter-review notes.",
            "",
            "## Planned Manuscript Figures",
            "",
            "- Figure 1: Count-family separation.",
            "- Figure 2: Lead blocker distribution.",
            "- Figure 3: Source-family concentration.",
            "- Figure 4: Map/display eligibility separation.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    stats_path = out_dir / "paper_stats.json"
    stats, warnings = load_json(stats_path)
    if not stats:
        raise SystemExit(f"Missing paper stats. Run generate_paper_stats.py first: {rel_path(stats_path)}")
    figures_dir = out_dir / "figures"
    tables_dir = out_dir / "tables"
    generated: list[dict[str, str]] = []

    recon_rows = count_reconciliation_rows(stats)
    recon_csv = figures_dir / "figure_1_count_family_reconciliation.csv"
    recon_svg = figures_dir / "figure_1_count_family_reconciliation.svg"
    write_csv(recon_csv, recon_rows, ["label", "count_family", "metric", "count", "source", "notes"])
    bar_svg(recon_svg, "Count-family separation", recon_rows)
    generated.extend(
        [
            {"id": "figure_1_data", "role": "csv", "path": rel_path(recon_csv), "use": "Count-family separation data."},
            {"id": "figure_1_svg", "role": "svg", "path": rel_path(recon_svg), "use": "Convenience rendering of count-family separation."},
        ]
    )

    blocker_rows, w = read_csv_rows(tables_dir / "lead_blocker_counts.csv")
    warnings.extend(w)
    blocker_top = top_rows(blocker_rows, 10)
    blocker_csv = figures_dir / "figure_2_lead_blockers_top10.csv"
    blocker_svg = figures_dir / "figure_2_lead_blockers_top10.svg"
    write_csv(blocker_csv, blocker_top, ["dimension", "value", "count", "share_pct", "source", "notes"])
    bar_svg(blocker_svg, "Lead blockers, top 10", blocker_top, label_key="value")
    generated.extend(
        [
            {"id": "figure_2_data", "role": "csv", "path": rel_path(blocker_csv), "use": "Top lead blocker counts."},
            {"id": "figure_2_svg", "role": "svg", "path": rel_path(blocker_svg), "use": "Convenience rendering of blocker distribution."},
        ]
    )

    family_rows, w = read_csv_rows(tables_dir / "frontend_map_source_family_counts.csv")
    warnings.extend(w)
    if not family_rows:
        family_rows, w = read_csv_rows(tables_dir / "lead_source_family_counts.csv")
        warnings.extend(w)
    family_top = top_rows(family_rows, 10)
    family_csv = figures_dir / "figure_3_source_family_top10.csv"
    family_svg = figures_dir / "figure_3_source_family_top10.svg"
    write_csv(family_csv, family_top, ["dimension", "value", "count", "share_pct", "source", "notes"])
    bar_svg(family_svg, "Source-family concentration, top 10", family_top, label_key="value")
    generated.extend(
        [
            {"id": "figure_3_data", "role": "csv", "path": rel_path(family_csv), "use": "Top source-family concentration rows."},
            {"id": "figure_3_svg", "role": "svg", "path": rel_path(family_svg), "use": "Convenience rendering of source-family concentration."},
        ]
    )

    map_rows = [
        {
            "label": row.get("metric", ""),
            "count_family": row.get("count_family", ""),
            "metric": row.get("metric", ""),
            "count": row.get("value", ""),
            "source": row.get("source", ""),
            "notes": row.get("notes", ""),
        }
        for row in stats.get("counts", [])
        if row.get("count_family") == "mapped_public_record_counts" and numeric(row.get("value")) is not None
    ]
    map_csv = figures_dir / "figure_4_map_display_separation.csv"
    map_svg = figures_dir / "figure_4_map_display_separation.svg"
    write_csv(map_csv, map_rows, ["label", "count_family", "metric", "count", "source", "notes"])
    bar_svg(map_svg, "Map/display eligibility separation", map_rows)
    generated.extend(
        [
            {"id": "figure_4_data", "role": "csv", "path": rel_path(map_csv), "use": "Map and eligibility count separation."},
            {"id": "figure_4_svg", "role": "svg", "path": rel_path(map_svg), "use": "Convenience rendering of map/display separation."},
        ]
    )

    inventory_md = out_dir / "FIGURE_TABLE_INVENTORY.md"
    docs_inventory = docs_dir(config) / "FIGURE_TABLE_INVENTORY.md"
    write_inventory(inventory_md, generated)
    write_inventory(docs_inventory, generated)
    generated.extend(
        [
            {"id": "inventory_release", "role": "markdown", "path": rel_path(inventory_md), "use": "Release inventory."},
            {"id": "inventory_docs", "role": "markdown", "path": rel_path(docs_inventory), "use": "Documentation inventory."},
        ]
    )

    manifest = {
        "generated": generated,
        "warnings": warnings,
    }
    manifest_path = out_dir / "figure_script_manifest.json"
    write_json(manifest_path, manifest)
    write_manifest(
        out_dir / "figure_outputs_manifest.json",
        SCRIPT_NAME,
        [Path(row["path"]) for row in generated] + [manifest_path],
        [stats_path, tables_dir / "lead_blocker_counts.csv", tables_dir / "frontend_map_source_family_counts.csv"],
        warnings,
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    out_dir = Path(args.out_dir) if args.out_dir else release_dir(config)
    payload = generate(config, out_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
