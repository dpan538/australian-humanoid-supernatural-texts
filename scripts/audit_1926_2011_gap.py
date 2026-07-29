#!/usr/bin/env python3
"""Audit and simulate the 1926-2011 public-record gap without importing data."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH
from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso, write_csv


DEFAULT_FRONTEND_DATA = PROJECT_ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "gap_probe_1926_2011.yml"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "interim" / "gap_probe_1926_2011"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "1926_2011_gap_audit.md"


def load_frontend(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def percent(count: int, total: int) -> str:
    return f"{(count / total) * 100:.1f}%" if total else "0.0%"


def source_family(source_type: str | None) -> str:
    source = (source_type or "").lower()
    if "community" in source:
        return "community"
    if any(token in source for token in ("repository", "archive", "trove", "newspaper", "magazine")):
        return "repository/archive"
    if "modern_web" in source or "seeded_public_web" in source:
        return "modern_public_web"
    if any(token in source for token in ("public_domain", "gutenberg", "wikisource", "sacred_texts")):
        return "public_domain_text"
    if "institutional" in source or "municipal" in source:
        return "public_institution"
    if any(token in source for token in ("academic", "catalogue", "metadata", "andc")):
        return "academic/catalogue_metadata"
    return "other"


def narrative_label(record: dict[str, Any]) -> str:
    return (
        record.get("ontology_code")
        or record.get("genre")
        or record.get("canonical_figure_guess")
        or record.get("canonical_figure")
        or "uncoded"
    )


def figure_label(record: dict[str, Any]) -> str:
    return record.get("canonical_figure_guess") or record.get("canonical_figure") or "uncoded"


def safe_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        loaded = json.loads(value)
    except Exception:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def inner_raw_metadata(raw: dict[str, Any]) -> dict[str, Any]:
    nested = raw.get("raw_metadata_json")
    if not isinstance(nested, str):
        return {}
    return safe_json(nested)


def provenance(record_id: int, raw_by_record_id: dict[int, dict[str, Any]], source_type: str | None) -> str:
    raw = raw_by_record_id.get(record_id, {})
    inner = inner_raw_metadata(raw)
    for key in ("route_id", "source_family"):
        value = inner.get(key)
        if value:
            return str(value)
    for key in ("collector", "run_id", "promotion_source"):
        value = raw.get(key)
        if value:
            return str(value)
    return f"no_raw_provenance:{source_type or 'unknown'}"


def record_year(record: dict[str, Any]) -> int | None:
    year = record.get("year")
    return year if isinstance(year, int) else None


def records_in_window(records: list[dict[str, Any]], start: int, end: int) -> list[dict[str, Any]]:
    return [record for record in records if (year := record_year(record)) is not None and start <= year <= end]


def top_counter(counter: Counter[str], limit: int = 5) -> str:
    if not counter:
        return ""
    return "; ".join(f"{key}={count}" for key, count in counter.most_common(limit))


def bucket_rows(
    records: list[dict[str, Any]],
    mapped_ids: set[int],
    raw_by_record_id: dict[int, dict[str, Any]],
    buckets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for bucket in buckets:
        window_records = records_in_window(records, int(bucket["start_year"]), int(bucket["end_year"]))
        rows.append(
            {
                "bucket_id": bucket["id"],
                "label": bucket["label"],
                "start_year": bucket["start_year"],
                "end_year": bucket["end_year"],
                "public_records": len(window_records),
                "mapped_records": sum(1 for record in window_records if int(record["record_id"]) in mapped_ids),
                "mapped_share": f"{(sum(1 for record in window_records if int(record['record_id']) in mapped_ids) / len(window_records)):.3f}"
                if window_records
                else "0.000",
                "top_source_families": top_counter(Counter(source_family(record.get("source_type")) for record in window_records)),
                "top_source_types": top_counter(Counter(record.get("source_type") or "unknown" for record in window_records)),
                "top_narratives": top_counter(Counter(narrative_label(record) for record in window_records)),
                "top_figures": top_counter(Counter(figure_label(record) for record in window_records)),
                "top_provenance": top_counter(
                    Counter(
                        provenance(int(record["record_id"]), raw_by_record_id, record.get("source_type"))
                        for record in window_records
                    )
                ),
            }
        )
    return rows


def annual_rows(records: list[dict[str, Any]], mapped_ids: set[int], start: int = 1926, end: int = 2011) -> list[dict[str, Any]]:
    by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        year = record_year(record)
        if year is not None and start <= year <= end:
            by_year[year].append(record)
    rows: list[dict[str, Any]] = []
    for year in range(start, end + 1):
        year_records = by_year.get(year, [])
        rows.append(
            {
                "year": year,
                "public_records": len(year_records),
                "mapped_records": sum(1 for record in year_records if int(record["record_id"]) in mapped_ids),
                "top_source_type": top_counter(Counter(record.get("source_type") or "unknown" for record in year_records), 3),
                "top_narrative": top_counter(Counter(narrative_label(record) for record in year_records), 3),
                "top_figure": top_counter(Counter(figure_label(record) for record in year_records), 3),
            }
        )
    return rows


def query_plan_rows(config: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for date_window in config.get("date_windows", []):
        for query_family in config.get("query_families", []):
            for source_target in config.get("source_targets", []):
                for template in query_family.get("templates", []):
                    rows.append(
                        {
                            "date_window_id": date_window["id"],
                            "start_year": date_window["start_year"],
                            "end_year": date_window["end_year"],
                            "query_family_id": query_family["id"],
                            "query_family_label": query_family["label"],
                            "priority": query_family.get("priority", ""),
                            "query_template": template,
                            "expected_noise": query_family.get("expected_noise", ""),
                            "cultural_sensitivity_default": query_family.get("cultural_sensitivity_default", ""),
                            "source_target_id": source_target["id"],
                            "source_target_label": source_target["label"],
                            "source_tier": source_target.get("source_tier", ""),
                            "access_method": source_target.get("access_method", ""),
                            "requires_api_key": source_target.get("requires_api_key", False),
                            "rate_limit_seconds": source_target.get("rate_limit_seconds", ""),
                            "max_samples_per_query": source_target.get("max_samples_per_query", ""),
                            "publicness_check": source_target.get("publicness_check", ""),
                            "review_note": query_family.get("review_note", ""),
                            "status": "planned_probe_not_ingested",
                        }
                    )
    return rows


def allocate_simulated_additions(additional: int, source_mix: list[dict[str, Any]]) -> list[tuple[str, int]]:
    if additional <= 0:
        return []
    weighted: list[tuple[str, int, float]] = []
    allocated = 0
    for item in source_mix:
        exact = additional * float(item.get("share", 0))
        count = int(exact)
        allocated += count
        weighted.append((str(item["source_family"]), count, exact - count))
    remainder = additional - allocated
    weighted.sort(key=lambda item: item[2], reverse=True)
    output: list[tuple[str, int]] = []
    for index, (family, count, _fraction) in enumerate(weighted):
        if index < remainder:
            count += 1
        if count:
            output.append((family, count))
    return output


def simulation_rows(records: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    by_year = Counter(record_year(record) for record in records if record_year(record) is not None)
    simulation_config = config.get("simulation", {})
    source_mix = list(simulation_config.get("source_mix", []))
    mapped_share = float((simulation_config.get("mapping_assumption") or {}).get("mapped_share_for_simulation", 0.35))
    status_label = simulation_config.get("status_label", "simulated_not_ingested")
    rows: list[dict[str, Any]] = []
    for target in simulation_config.get("target_windows", []):
        target_per_year = int(target["target_public_records_per_year"])
        for year in range(int(target["start_year"]), int(target["end_year"]) + 1):
            current = int(by_year.get(year, 0))
            additional = max(0, target_per_year - current)
            if additional == 0:
                rows.append(
                    {
                        "simulation_status": status_label,
                        "window_id": target["id"],
                        "year": year,
                        "current_public_records": current,
                        "target_public_records": target_per_year,
                        "simulated_additional_public_records": 0,
                        "simulated_additional_mapped_records": 0,
                        "simulated_source_family": "",
                        "simulated_public_total_after_fill": current,
                        "note": "current count already meets or exceeds target",
                    }
                )
                continue
            for family, family_count in allocate_simulated_additions(additional, source_mix):
                rows.append(
                    {
                        "simulation_status": status_label,
                        "window_id": target["id"],
                        "year": year,
                        "current_public_records": current,
                        "target_public_records": target_per_year,
                        "simulated_additional_public_records": family_count,
                        "simulated_additional_mapped_records": round(family_count * mapped_share, 2),
                        "simulated_source_family": family,
                        "simulated_public_total_after_fill": current + additional,
                        "note": "aggregate planning row only; not a record and not production data",
                    }
                )
    return rows


def raw_metadata_by_record_id(db_path: Path) -> dict[int, dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT record_id, raw_metadata_json FROM records").fetchall()
    return {int(row["record_id"]): safe_json(row["raw_metadata_json"]) for row in rows}


def query_linkage_summary(records: list[dict[str, Any]]) -> tuple[int, int]:
    linked = sum(1 for record in records if record.get("query_id") is not None)
    return linked, len(records) - linked


def write_report(
    report_path: Path,
    data: dict[str, Any],
    config: dict[str, Any],
    bucket_data: list[dict[str, Any]],
    annual_data: list[dict[str, Any]],
    simulation_data: list[dict[str, Any]],
    output_dir: Path,
) -> None:
    records = data.get("records", [])
    linked_queries, unlinked_queries = query_linkage_summary(records)
    mid_row = next((row for row in bucket_data if row["bucket_id"] == "mid_century_gap"), None)
    full_gap_row = next((row for row in bucket_data if row["bucket_id"] == "full_gap_window"), None)
    early_row = next((row for row in bucket_data if row["bucket_id"] == "early_spike_reference"), None)
    simulated_total = sum(int(row["simulated_additional_public_records"]) for row in simulation_data)
    simulated_mapped = sum(float(row["simulated_additional_mapped_records"]) for row in simulation_data)
    sparse_years = [row for row in annual_data if int(row["public_records"]) <= 2]

    lines = [
        "# 1926-2011 Gap Audit and Probe Plan",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Frontend data: `{DEFAULT_FRONTEND_DATA}`",
        f"- Config: `{DEFAULT_CONFIG}`",
        f"- Output directory: `{output_dir}`",
        "",
        "## Guardrails",
        "",
        "- This report is an exploratory data audit and simulation.",
        "- Simulated additions are aggregate planning rows, not records.",
        "- No records were imported, promoted, geocoded, or written into production frontend data.",
        "- Public source existence is not treated as supernatural-claim verification.",
        "- Indigenous-related public-source rows require source-voice, publicness, terminology, and cultural-sensitivity review before any promotion.",
        "",
        "## Current Export Facts",
        "",
        f"- Public records: `{data.get('summary', {}).get('record_count')}`",
        f"- Mapped records: `{data.get('summary', {}).get('mapped_record_count')}`",
        f"- Dated records: `{data.get('summary', {}).get('dated_record_count')}`",
        f"- Records with linked `query_id`: `{linked_queries}`",
        f"- Records without linked `query_id`: `{unlinked_queries}`",
        "",
        "The zero linked-query count means current records cannot be attributed to exact query terms from the planned query table. Query-family reporting in this phase is therefore a planned-probe design, not retrospective provenance.",
        "",
        "## Bucket Evidence",
        "",
        "| Bucket | Public | Mapped | Top source families | Top narratives | Top figures | Top provenance |",
        "| --- | ---: | ---: | --- | --- | --- | --- |",
    ]
    for row in bucket_data:
        lines.append(
            "| {label} | {public_records} | {mapped_records} | {top_source_families} | {top_narratives} | {top_figures} | {top_provenance} |".format(
                **row
            )
        )

    lines.extend(
        [
            "",
            "## Gap Diagnosis",
            "",
            f"- The mid-century bucket has `{mid_row['public_records'] if mid_row else 'n/a'}` public records, compared with `{early_row['public_records'] if early_row else 'n/a'}` in the 1875-1926 reference bucket.",
            f"- The full 1926-2011 window has `{full_gap_row['public_records'] if full_gap_row else 'n/a'}` public records and is dominated by AYR-derived modern public web provenance.",
            "- The likely cause is not map filtering: public records are already low before map eligibility is applied.",
            "- The likely cause is not date parsing: the frontend export and database filter reconcile exactly in the local audit.",
            "- The main operational gap is source-route coverage after the public-domain/exact-text routes taper off and before modern web/institutional routes rise.",
            "",
            "## Sparse Years",
            "",
        ]
    )
    if sparse_years:
        sample = ", ".join(str(row["year"]) for row in sparse_years[:40])
        lines.append(f"- Years with two or fewer current public records in 1926-2011: {sample}")
        if len(sparse_years) > 40:
            lines.append(f"- Additional sparse years not shown: {len(sparse_years) - 40}")
    else:
        lines.append("- No sparse years under the current threshold.")

    lines.extend(
        [
            "",
            "## Planned Query Families",
            "",
            "| Family | Priority | Expected noise | Sensitivity | Templates | Review note |",
            "| --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for family in config.get("query_families", []):
        lines.append(
            f"| {family['label']} | {family.get('priority', '')} | {family.get('expected_noise', '')} | {family.get('cultural_sensitivity_default', '')} | {len(family.get('templates', []))} | {family.get('review_note', '')} |"
        )

    lines.extend(
        [
            "",
            "## Source Targets",
            "",
            "| Target | Tier | Access | API key | Rate limit | First-probe cap | Publicness check |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for target in config.get("source_targets", []):
        lines.append(
            f"| {target['label']} | {target.get('source_tier', '')} | {target.get('access_method', '')} | {target.get('requires_api_key', False)} | {target.get('rate_limit_seconds', '')}s | {target.get('max_queries_first_probe', '')} | {target.get('publicness_check', '')} |"
        )

    lines.extend(
        [
            "",
            "## Simulation Summary",
            "",
            f"- Simulated additional public-record aggregates: `{simulated_total}`",
            f"- Simulated additional mapped-record estimate: `{simulated_mapped:.1f}`",
            "- Simulation status label: `simulated_not_ingested`",
            "- Simulation rows are grouped by year and source family. They are placeholders for planning, not source records.",
            "",
            "## Output Files",
            "",
            f"- `{output_dir / 'year_bucket_evidence.csv'}`",
            f"- `{output_dir / 'annual_gap_evidence.csv'}`",
            f"- `{output_dir / 'planned_probe_queries.csv'}`",
            f"- `{output_dir / 'simulated_gap_fill_projection.csv'}`",
            f"- Optional Trove dry-run/live probe output: `{output_dir / 'trove_probe_requests.csv'}`",
            "",
            "## Next Implementation Notes",
            "",
            "- Add live hit-count probes only after network/API authorization.",
            "- For Trove, use the official API with `TROVE_API_KEY` or researcher-supplied manual exports.",
            "- Keep hit-count probes separate from candidate promotion.",
            "- Store publicness and risk flags with every probe result.",
            "- Promote nothing until source text/metadata, duplicate status, narrative type, source voice, cultural sensitivity, and location role have been reviewed.",
        ]
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-data", default=str(DEFAULT_FRONTEND_DATA))
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    args = parser.parse_args()

    frontend_path = Path(args.frontend_data)
    db_path = Path(args.db)
    config_path = Path(args.config)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report)

    data = load_frontend(frontend_path)
    config = read_yaml(config_path)
    records = list(data.get("records", []))
    mapped_ids = {int(row["record_id"]) for row in data.get("map_flags", data.get("map_points", []))}
    raw_by_record_id = raw_metadata_by_record_id(db_path)

    bucket_data = bucket_rows(records, mapped_ids, raw_by_record_id, list(config.get("audit_buckets", [])))
    annual_data = annual_rows(records, mapped_ids)
    planned_queries = query_plan_rows(config)
    simulated = simulation_rows(records, config)

    write_csv(
        output_dir / "year_bucket_evidence.csv",
        bucket_data,
        [
            "bucket_id",
            "label",
            "start_year",
            "end_year",
            "public_records",
            "mapped_records",
            "mapped_share",
            "top_source_families",
            "top_source_types",
            "top_narratives",
            "top_figures",
            "top_provenance",
        ],
    )
    write_csv(
        output_dir / "annual_gap_evidence.csv",
        annual_data,
        ["year", "public_records", "mapped_records", "top_source_type", "top_narrative", "top_figure"],
    )
    write_csv(
        output_dir / "planned_probe_queries.csv",
        planned_queries,
        [
            "date_window_id",
            "start_year",
            "end_year",
            "query_family_id",
            "query_family_label",
            "priority",
            "query_template",
            "expected_noise",
            "cultural_sensitivity_default",
            "source_target_id",
            "source_target_label",
            "source_tier",
            "access_method",
            "requires_api_key",
            "rate_limit_seconds",
            "max_samples_per_query",
            "publicness_check",
            "review_note",
            "status",
        ],
    )
    write_csv(
        output_dir / "simulated_gap_fill_projection.csv",
        simulated,
        [
            "simulation_status",
            "window_id",
            "year",
            "current_public_records",
            "target_public_records",
            "simulated_additional_public_records",
            "simulated_additional_mapped_records",
            "simulated_source_family",
            "simulated_public_total_after_fill",
            "note",
        ],
    )
    write_report(report_path, data, config, bucket_data, annual_data, simulated, output_dir)

    print(f"Wrote gap audit report: {report_path}")
    print(f"Wrote gap audit tables: {output_dir}")


if __name__ == "__main__":
    main()
