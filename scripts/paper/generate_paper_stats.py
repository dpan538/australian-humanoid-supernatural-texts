#!/usr/bin/env python3
"""Generate reproducible descriptive statistics for the HSS paper package."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from paper_common import (
    DEFAULT_CONFIG,
    PUBLIC_DISPLAY_MODES,
    ROOT,
    add_count,
    add_unavailable,
    configured_path,
    connect,
    count_by,
    count_table,
    docs_dir,
    load_config,
    load_json,
    markdown_count_table,
    now_iso,
    pct,
    read_csv_rows,
    rel_path,
    release_dir,
    sqlite_db_path,
    table_columns,
    table_exists,
    write_csv,
    write_json,
    write_manifest,
)


SCRIPT_NAME = "generate_paper_stats.py"
COUNT_FIELDS = ["count_family", "metric", "value", "unit", "source", "status", "notes"]
DETAIL_FIELDS = ["dimension", "value", "count", "share_pct", "source", "notes"]

ELIGIBLE_MAP_ROLES = {
    "alleged_event_location",
    "apparition_location",
    "legend_associated_place",
    "narrative_setting",
    "rumour_circulation_place",
}


def _json_array_len(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    return len(value) if isinstance(value, list) else None


def _write_detail(path: Path, rows: list[dict[str, Any]]) -> None:
    write_csv(path, rows, DETAIL_FIELDS)


def _counter_detail(counter_rows: list[dict[str, Any]], dimension: str, total: int, source: str, notes: str = "") -> list[dict[str, Any]]:
    return [
        {
            "dimension": dimension,
            "value": row.get("value", "(missing)"),
            "count": row.get("count", 0),
            "share_pct": pct(int(row.get("count") or 0), total),
            "source": source,
            "notes": notes,
        }
        for row in counter_rows
    ]


def _csv_group_sum(rows: list[dict[str, Any]], key: str, count_key: str = "row_count") -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        label = str(row.get(key) or "(missing)").strip() or "(missing)"
        try:
            count = int(float(row.get(count_key) or 0))
        except (TypeError, ValueError):
            count = 0
        counter[label] += count
    return counter


def _source_chain_audit_metrics(path: Path) -> dict[str, str]:
    rows, _ = read_csv_rows(path)
    return {str(row.get("metric")): str(row.get("value")) for row in rows if row.get("metric")}


def _constraint_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _missingness_rows(conn: sqlite3.Connection, table: str, fields: list[str], source: str) -> list[dict[str, Any]]:
    if not table_exists(conn, table):
        return []
    columns = table_columns(conn, table)
    total = count_table(conn, table) or 0
    rows = []
    for field in fields:
        if field not in columns:
            rows.append(
                {
                    "dimension": f"{table}_missingness",
                    "value": field,
                    "count": "",
                    "share_pct": "",
                    "source": source,
                    "notes": "field not available in current local data",
                }
            )
            continue
        count = int(
            conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {field} IS NULL OR TRIM(CAST({field} AS TEXT))=''"
            ).fetchone()[0]
            or 0
        )
        rows.append(
            {
                "dimension": f"{table}_missingness",
                "value": field,
                "count": count,
                "share_pct": pct(count, total),
                "source": source,
                "notes": f"denominator={total}",
            }
        )
    return rows


def _map_eligibility(conn: sqlite3.Connection) -> tuple[int | None, int | None]:
    if not table_exists(conn, "narrative_locations") or not table_exists(conn, "locations"):
        return None, None
    has_units = table_exists(conn, "narrative_units")
    total_sql = """
        SELECT COUNT(*)
        FROM narrative_locations nl
        JOIN locations l ON l.location_id = nl.location_id
    """
    eligible_sql = """
        SELECT COUNT(*)
        FROM narrative_locations nl
        JOIN locations l ON l.location_id = nl.location_id
    """
    where = """
        WHERE lower(COALESCE(nl.location_role,'')) IN ({roles})
          AND l.latitude IS NOT NULL
          AND l.longitude IS NOT NULL
    """.format(
        roles=",".join("?" for _ in ELIGIBLE_MAP_ROLES)
    )
    params: list[Any] = sorted(ELIGIBLE_MAP_ROLES)
    if has_units:
        eligible_sql += " JOIN narrative_units nu ON nu.narrative_id = nl.narrative_id "
        where += " AND COALESCE(nu.display_mode,'') IN ({modes}) AND COALESCE(nu.analysis_status,'') != 'excluded'".format(
            modes=",".join("?" for _ in PUBLIC_DISPLAY_MODES)
        )
        params.extend(sorted(PUBLIC_DISPLAY_MODES))
    total = int(conn.execute(total_sql).fetchone()[0] or 0)
    eligible = int(conn.execute(eligible_sql + where, params).fetchone()[0] or 0)
    return eligible, total


def compute_stats(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    counts: list[dict[str, Any]] = []
    detail_outputs: dict[str, str] = {}
    tables_dir = out_dir / "tables"
    db_path = sqlite_db_path(config)

    frontend_path = configured_path(config, "inputs", "frontend_public_json")
    frontend_v2_path = configured_path(config, "inputs", "frontend_v2_json")
    release_counts_path = configured_path(config, "inputs", "frontend_release_counts_json")
    canonical_counts_path = configured_path(config, "inputs", "canonical_count_reconciliation_csv")
    frontend_concentration_path = configured_path(config, "inputs", "frontend_source_concentration_audit_csv")
    source_concentration_path = configured_path(config, "inputs", "source_concentration_audit_csv")
    source_chain_audit_path = configured_path(config, "inputs", "source_chain_audit_csv")
    constraint_path = configured_path(config, "inputs", "constraint_decision_yaml")

    frontend, w = load_json(frontend_path)
    warnings.extend(w)
    frontend_v2, w = load_json(frontend_v2_path)
    warnings.extend(w)
    release_counts, w = load_json(release_counts_path)
    warnings.extend(w)
    constraint_config = _constraint_config(constraint_path)

    add_unavailable(
        counts,
        "live_public_website_display_counts",
        "live_public_records",
        "records",
        "Requires explicit capture from deployed website/runtime; local frontend exports are reported separately.",
    )
    add_unavailable(
        counts,
        "live_public_website_display_counts",
        "live_public_mapped_records",
        "records",
        "Requires explicit capture from deployed website/runtime; local frontend exports are reported separately.",
    )

    frontend_records = _json_array_len(frontend, "records")
    frontend_map_points = _json_array_len(frontend, "map_points")
    frontend_map_flags = _json_array_len(frontend, "map_flags")
    if frontend_records is None:
        add_unavailable(counts, "local_frontend_export_display_counts", "frontend_records", "records", "`records` array missing.")
    else:
        add_count(counts, "local_frontend_export_display_counts", "frontend_records", frontend_records, "records", rel_path(frontend_path))
    if frontend_map_points is None:
        add_unavailable(counts, "local_frontend_export_display_counts", "frontend_map_points", "rows", "`map_points` array missing.")
    else:
        add_count(counts, "local_frontend_export_display_counts", "frontend_map_points", frontend_map_points, "rows", rel_path(frontend_path))
    if frontend_map_flags is None:
        add_unavailable(counts, "local_frontend_export_display_counts", "frontend_map_flags", "rows", "`map_flags` array missing.")
    else:
        add_count(counts, "local_frontend_export_display_counts", "frontend_map_flags", frontend_map_flags, "rows", rel_path(frontend_path))
    if frontend_map_points is not None and frontend_map_flags is not None:
        add_count(
            counts,
            "local_frontend_export_display_counts",
            "map_points_equal_map_flags",
            int(frontend_map_points == frontend_map_flags),
            "boolean_as_int",
            rel_path(frontend_path),
            notes="1 means local export satisfies map_points.length == map_flags.length.",
        )

    if release_counts:
        for key in ["accepted_public_records", "accepted_public_map", "metadata_overlay", "lead_overlay"]:
            if isinstance(release_counts.get(key), int):
                add_count(counts, "frontend_release_package_counts", key, release_counts[key], "rows", rel_path(release_counts_path))

    with connect(db_path) as conn:
        records_total = count_table(conn, "records")
        if records_total is None:
            add_unavailable(counts, "legacy_flat_record_corpus_counts", "records_total", "records", "`records` table missing.")
        else:
            add_count(counts, "legacy_flat_record_corpus_counts", "records_total", records_total, "records", "records")
            if "full_text_path" in table_columns(conn, "records"):
                with_text = count_table(conn, "records", "full_text_path IS NOT NULL AND TRIM(full_text_path)!=''")
                add_count(counts, "legacy_flat_record_corpus_counts", "records_with_full_text_path", with_text, "records", "records")
            publicness_rows = _counter_detail(count_by(conn, "records", "publicness_level"), "records.publicness_level", records_total, "records")
            _write_detail(tables_dir / "legacy_record_publicness_counts.csv", publicness_rows)
            detail_outputs["legacy_record_publicness_counts"] = rel_path(tables_dir / "legacy_record_publicness_counts.csv")

        source_items_total = count_table(conn, "source_items")
        narrative_total = count_table(conn, "narrative_units")
        if source_items_total is None:
            add_unavailable(counts, "v2_normalized_public_corpus_counts", "source_items_total", "rows", "`source_items` table missing.")
        else:
            add_count(counts, "v2_normalized_public_corpus_counts", "source_items_total", source_items_total, "source_items", "source_items")
        if narrative_total is None:
            add_unavailable(counts, "v2_normalized_public_corpus_counts", "narrative_units_total", "rows", "`narrative_units` table missing.")
        else:
            add_count(counts, "v2_normalized_public_corpus_counts", "narrative_units_total", narrative_total, "narrative_units", "narrative_units")
            modes = ",".join("?" for _ in PUBLIC_DISPLAY_MODES)
            public_narratives = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) FROM narrative_units
                    WHERE COALESCE(display_mode,'') IN ({modes})
                      AND COALESCE(analysis_status,'') != 'excluded'
                    """,
                    sorted(PUBLIC_DISPLAY_MODES),
                ).fetchone()[0]
                or 0
            )
            add_count(
                counts,
                "v2_normalized_public_corpus_counts",
                "public_display_eligible_narrative_units",
                public_narratives,
                "narrative_units",
                "narrative_units",
                notes="display_mode in full/summary_only/metadata_only and analysis_status not excluded.",
            )
            display_rows = _counter_detail(count_by(conn, "narrative_units", "display_mode"), "narrative_units.display_mode", narrative_total, "narrative_units")
            analysis_rows = _counter_detail(count_by(conn, "narrative_units", "analysis_status"), "narrative_units.analysis_status", narrative_total, "narrative_units")
            ethics_rows = _counter_detail(count_by(conn, "narrative_units", "ethics_review_status"), "narrative_units.ethics_review_status", narrative_total, "narrative_units")
            sensitivity_rows = _counter_detail(count_by(conn, "narrative_units", "cultural_sensitivity"), "narrative_units.cultural_sensitivity", narrative_total, "narrative_units")
            _write_detail(tables_dir / "v2_display_mode_counts.csv", display_rows)
            _write_detail(tables_dir / "v2_analysis_status_counts.csv", analysis_rows)
            _write_detail(tables_dir / "v2_ethics_counts.csv", ethics_rows + sensitivity_rows)
            detail_outputs["v2_display_mode_counts"] = rel_path(tables_dir / "v2_display_mode_counts.csv")
            detail_outputs["v2_analysis_status_counts"] = rel_path(tables_dir / "v2_analysis_status_counts.csv")
            detail_outputs["v2_ethics_counts"] = rel_path(tables_dir / "v2_ethics_counts.csv")

        source_link_total = count_table(conn, "narrative_source_links")
        add_count(
            counts,
            "source_chain_model_counts",
            "narrative_source_links_total",
            source_link_total,
            "links",
            "narrative_source_links" if source_link_total is not None else "not available in current local data",
            "ok" if source_link_total is not None else "not_available",
            "Normalized link table count; not a proof-strength count.",
        )
        source_chain_table_total = count_table(conn, "source_chains")
        add_count(
            counts,
            "source_chain_model_counts",
            "source_chains_table_rows",
            source_chain_table_total,
            "rows",
            "source_chains" if source_chain_table_total is not None else "not available in current local data",
            "ok" if source_chain_table_total is not None else "not_available",
            "The local source_chains table may be empty even when source-chain audit files exist.",
        )
        source_chain_audit = _source_chain_audit_metrics(source_chain_audit_path)
        for key in ["source_chain_rows", "missing_original_source_name", "tier_e_or_discovery_like_rows"]:
            if key in source_chain_audit:
                add_count(counts, "source_chain_model_counts", f"audit_{key}", source_chain_audit[key], "rows", rel_path(source_chain_audit_path))

        if table_exists(conn, "collection_candidates_v2"):
            candidate_total = count_table(conn, "collection_candidates_v2") or 0
            add_count(counts, "v2_normalized_public_corpus_counts", "collection_candidates_v2_total", candidate_total, "candidates", "collection_candidates_v2")
            candidate_rows = _counter_detail(count_by(conn, "collection_candidates_v2", "candidate_status"), "collection_candidates_v2.candidate_status", candidate_total, "collection_candidates_v2")
            _write_detail(tables_dir / "collection_candidate_status_counts.csv", candidate_rows)
            detail_outputs["collection_candidate_status_counts"] = rel_path(tables_dir / "collection_candidate_status_counts.csv")

        provisional_total = count_table(conn, "provisional_records")
        if provisional_total is None:
            add_unavailable(counts, "strict_no_credential_record_gate_experiment_counts", "provisional_records_total", "rows", "`provisional_records` table missing.")
        else:
            add_count(counts, "strict_no_credential_record_gate_experiment_counts", "provisional_records_total", provisional_total, "rows", "provisional_records")
            columns = table_columns(conn, "provisional_records")
            if {"target_gap_eligible", "harvest_mode"}.issubset(columns):
                strict_targets = int(
                    conn.execute(
                        """
                        SELECT COUNT(*) FROM provisional_records
                        WHERE COALESCE(target_gap_eligible,0)=1
                          AND COALESCE(harvest_mode,'') LIKE 'structured%'
                        """
                    ).fetchone()[0]
                    or 0
                )
                add_count(
                    counts,
                    "strict_no_credential_record_gate_experiment_counts",
                    "strict_target_gap_records",
                    strict_targets,
                    "records",
                    "provisional_records",
                    notes="Strict no-credential structured target-gap gate.",
                )
            else:
                add_unavailable(
                    counts,
                    "strict_no_credential_record_gate_experiment_counts",
                    "strict_target_gap_records",
                    "records",
                    "`target_gap_eligible` and `harvest_mode` fields missing.",
                )
        for table, metric in [
            ("harvest_pages", "harvest_pages_seen"),
            ("harvest_candidates", "harvest_candidates_seen"),
            ("noauth_endpoint_inventory", "structured_endpoints_seen"),
            ("noauth_endpoint_records", "structured_endpoint_records_seen"),
            ("structured_endpoint_near_misses", "structured_near_misses_materialized"),
            ("structured_endpoint_enriched_records", "structured_enriched_records"),
        ]:
            value = count_table(conn, table)
            if value is None:
                add_unavailable(counts, "strict_no_credential_record_gate_experiment_counts", metric, "rows", f"`{table}` table missing.")
            else:
                add_count(counts, "strict_no_credential_record_gate_experiment_counts", metric, value, "rows", table)

        target = constraint_config.get("strict_mode_status", {}).get("target")
        if target not in {None, ""}:
            add_count(counts, "strict_no_credential_record_gate_experiment_counts", "strict_target_goal", target, "records", rel_path(constraint_path), notes="Configuration target, not achieved count.")

        leads_total = count_table(conn, "target_gap_leads")
        if leads_total is None:
            add_unavailable(counts, "lead_mode_conversion_counts", "target_gap_leads_total", "leads", "`target_gap_leads` table missing.")
        else:
            add_count(counts, "lead_mode_conversion_counts", "target_gap_leads_total", leads_total, "leads", "target_gap_leads")
            add_count(
                counts,
                "lead_mode_conversion_counts",
                "lead_mode_enabled_config",
                int(bool(constraint_config.get("lead_mode", {}).get("enabled"))),
                "boolean_as_int",
                rel_path(constraint_path),
            )
            for column, filename, family in [
                ("lead_type", "lead_type_counts.csv", "lead_mode_conversion_counts"),
                ("source_table", "lead_source_table_counts.csv", "lead_mode_conversion_counts"),
                ("priority_bucket", "priority_lead_bucket_counts.csv", "priority_lead_counts"),
                ("constraint_blocker", "lead_blocker_counts.csv", "blocker_counts"),
                ("evidence_gap", "lead_evidence_gap_counts.csv", "blocker_counts"),
                ("source_family", "lead_source_family_counts.csv", "source_family_concentration_counts"),
                ("route_family", "lead_route_family_counts.csv", "source_family_concentration_counts"),
            ]:
                rows = _counter_detail(count_by(conn, "target_gap_leads", column), f"target_gap_leads.{column}", leads_total, "target_gap_leads")
                _write_detail(tables_dir / filename, rows)
                detail_outputs[filename.removesuffix(".csv")] = rel_path(tables_dir / filename)
                if rows and family == "blocker_counts" and column == "constraint_blocker":
                    top = rows[0]
                    add_count(counts, "blocker_counts", "top_constraint_blocker", top["count"], "leads", "target_gap_leads", notes=f"{top['value']} ({top['share_pct']}%).")
                    add_count(counts, "blocker_counts", "distinct_constraint_blockers", len(rows), "blockers", "target_gap_leads")
                if rows and column == "source_family":
                    top = rows[0]
                    add_count(counts, "source_family_concentration_counts", "top_lead_source_family_count", top["count"], "leads", "target_gap_leads", notes=f"{top['value']} ({top['share_pct']}%).")
                    add_count(counts, "source_family_concentration_counts", "distinct_lead_source_families", len(rows), "families", "target_gap_leads")
            threshold = int(constraint_config.get("lead_mode", {}).get("priority_lead_score_threshold") or 80)
            if "lead_score" in table_columns(conn, "target_gap_leads"):
                score_priority = int(conn.execute("SELECT COUNT(*) FROM target_gap_leads WHERE COALESCE(lead_score,0) >= ?", (threshold,)).fetchone()[0] or 0)
                add_count(counts, "priority_lead_counts", f"lead_score_gte_{threshold}", score_priority, "leads", "target_gap_leads")

        eligible, map_denominator = _map_eligibility(conn)
        if eligible is None or map_denominator is None:
            add_unavailable(counts, "mapped_public_record_counts", "local_rule_map_eligible_narrative_locations", "rows", "narrative location/location tables missing.")
        else:
            add_count(
                counts,
                "mapped_public_record_counts",
                "local_rule_map_eligible_narrative_locations",
                eligible,
                "rows",
                "narrative_locations JOIN locations JOIN narrative_units",
                notes=f"Local rule denominator={map_denominator}; do not substitute for frontend map count.",
            )
            add_count(
                counts,
                "mapped_public_record_counts",
                "local_rule_map_eligibility_share_pct",
                pct(eligible, map_denominator),
                "percent",
                "narrative_locations JOIN locations JOIN narrative_units",
            )

        for table, column, filename, dimension in [
            ("source_items", "publication_or_organisation", "source_organisation_counts.csv", "source_items.publication_or_organisation"),
            ("source_items", "source_type", "source_type_counts.csv", "source_items.source_type"),
            ("source_items", "publicness_status", "source_publicness_counts.csv", "source_items.publicness_status"),
        ]:
            total = count_table(conn, table) or 0
            rows = _counter_detail(count_by(conn, table, column), dimension, total, table)
            _write_detail(tables_dir / filename, rows)
            detail_outputs[filename.removesuffix(".csv")] = rel_path(tables_dir / filename)
            if rows and column == "publication_or_organisation":
                add_count(counts, "source_organisation_source_type_counts", "distinct_source_organisations", len(rows), "organisations", table)
                add_count(counts, "source_organisation_source_type_counts", "top_source_organisation_count", rows[0]["count"], "source_items", table, notes=f"{rows[0]['value']} ({rows[0]['share_pct']}%).")
            if rows and column == "source_type":
                add_count(counts, "source_organisation_source_type_counts", "distinct_source_types", len(rows), "source_types", table)
                add_count(counts, "source_organisation_source_type_counts", "top_source_type_count", rows[0]["count"], "source_items", table, notes=f"{rows[0]['value']} ({rows[0]['share_pct']}%).")

        missingness = []
        missingness.extend(_missingness_rows(conn, "target_gap_leads", ["temporal_signal", "term_signal", "place_signal", "source_family", "source_chain_json"], "target_gap_leads"))
        missingness.extend(_missingness_rows(conn, "narrative_units", ["earliest_attestation_start", "public_summary", "cultural_sensitivity", "ethics_review_status"], "narrative_units"))
        missingness.extend(_missingness_rows(conn, "source_items", ["publication_or_organisation", "source_type", "source_traceability_status", "publicness_status"], "source_items"))
        _write_detail(tables_dir / "missingness_counts.csv", missingness)
        detail_outputs["missingness_counts"] = rel_path(tables_dir / "missingness_counts.csv")
        for row in missingness:
            if row.get("value") in {"temporal_signal", "term_signal", "place_signal", "source_family"} and row.get("count") != "":
                add_count(
                    counts,
                    "missingness_counts",
                    f"target_gap_leads_missing_{row['value']}",
                    row["count"],
                    "leads",
                    "target_gap_leads",
                    notes=f"{row['share_pct']}% missing.",
                )

    canonical_rows, w = read_csv_rows(canonical_counts_path)
    warnings.extend(w)
    for row in canonical_rows:
        name = str(row.get("population_name") or "")
        if name == "canonical_frontend_public_records":
            add_count(counts, "mapped_public_record_counts", "canonical_frontend_public_records", row.get("total_rows"), "records", rel_path(canonical_counts_path))
        elif name == "canonical_frontend_public_map_rows":
            add_count(counts, "mapped_public_record_counts", "canonical_frontend_public_map_rows", row.get("total_rows"), "rows", rel_path(canonical_counts_path))

    frontend_concentration_rows, w = read_csv_rows(frontend_concentration_path)
    warnings.extend(w)
    if frontend_concentration_rows:
        family_counter = _csv_group_sum(frontend_concentration_rows, "source_family", "row_count")
        total = sum(family_counter.values())
        detail_rows = [
            {
                "dimension": "frontend_map.source_family",
                "value": key,
                "count": count,
                "share_pct": pct(count, total),
                "source": rel_path(frontend_concentration_path),
                "notes": "frontend map source-family audit",
            }
            for key, count in family_counter.most_common()
        ]
        _write_detail(tables_dir / "frontend_map_source_family_counts.csv", detail_rows)
        detail_outputs["frontend_map_source_family_counts"] = rel_path(tables_dir / "frontend_map_source_family_counts.csv")
        if detail_rows:
            add_count(
                counts,
                "source_family_concentration_counts",
                "top_frontend_map_source_family_count",
                detail_rows[0]["count"],
                "map_rows",
                rel_path(frontend_concentration_path),
                notes=f"{detail_rows[0]['value']} ({detail_rows[0]['share_pct']}%).",
            )

    source_concentration_rows, w = read_csv_rows(source_concentration_path)
    warnings.extend(w)
    if source_concentration_rows:
        _write_detail(
            tables_dir / "source_chain_original_source_counts.csv",
            [
                {
                    "dimension": row.get("dimension", ""),
                    "value": row.get("value", ""),
                    "count": row.get("count", ""),
                    "share_pct": row.get("share_pct", ""),
                    "source": rel_path(source_concentration_path),
                    "notes": "existing source concentration audit",
                }
                for row in source_concentration_rows
                if row.get("dimension") in {"original_source_name", "access_source_name"}
            ],
        )
        detail_outputs["source_chain_original_source_counts"] = rel_path(tables_dir / "source_chain_original_source_counts.csv")

    summary = {
        "generated_at": now_iso(),
        "script": SCRIPT_NAME,
        "release_dir": rel_path(out_dir),
        "counts": counts,
        "detail_tables": detail_outputs,
        "warnings": warnings,
    }
    return summary


def write_stats_markdown(path: Path, stats: dict[str, Any], title: str = "Paper Count Reconciliation") -> None:
    rows = stats["counts"]
    unavailable = [row for row in rows if row.get("status") == "not_available"]
    lines = [
        f"# {title}",
        "",
        f"- Generated: `{stats['generated_at']}`",
        f"- Source stats JSON: `{rel_path(release_dir(load_config()) / 'paper_stats.json')}`",
        "",
        "## Count Family Definitions",
        "",
        "- `live_public_website_display_counts`: counts read from the deployed public website/runtime. These are not inferred from local files.",
        "- `local_frontend_export_display_counts`: counts read from the local static frontend export.",
        "- `legacy_flat_record_corpus_counts`: counts from the legacy `records` table.",
        "- `v2_normalized_public_corpus_counts`: counts from normalized V2 tables and exports.",
        "- `strict_no_credential_record_gate_experiment_counts`: counts from strict no-login/no-credential experiment tables and closeout configuration.",
        "- `lead_mode_conversion_counts`: lead rows retained after strict record gates failed or were unsuitable.",
        "- `priority_lead_counts`: lead rows with priority buckets or scores; these are not public records.",
        "- `mapped_public_record_counts`: public-map and map-eligibility populations. Frontend map rows are not interchangeable with internal location rows.",
        "- `source_organisation_source_type_counts`: source organisation and source type distributions.",
        "- `source_family_concentration_counts`: source-family concentration for map rows and leads where fields exist.",
        "- `blocker_counts`: blocker and evidence-gap counts for leads.",
        "- `missingness_counts`: missing-field diagnostics for leads, narratives, and source items.",
        "",
        "## Current Local Counts",
        "",
    ]
    lines.extend(markdown_count_table(rows))
    lines.extend(
        [
            "",
            "## Not Available In Current Local Data",
            "",
        ]
    )
    if unavailable:
        lines.extend([f"- `{row['count_family']}.{row['metric']}`: {row['notes']}" for row in unavailable])
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Non-Mixing Rule",
            "",
            "Do not combine live site display counts, local frontend export counts, legacy records, V2 normalized rows, strict-record experiment rows, lead-mode rows, or mapped rows unless a generated provenance table explicitly links the units.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--write-docs", action="store_true")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    out_dir = Path(args.out_dir) if args.out_dir else release_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = compute_stats(config, out_dir)

    stats_json = out_dir / "paper_stats.json"
    stats_csv = out_dir / "paper_counts.csv"
    stats_md = out_dir / "paper_stats.md"
    write_json(stats_json, stats)
    write_csv(stats_csv, stats["counts"], COUNT_FIELDS)
    write_stats_markdown(stats_md, stats)

    outputs = [stats_json, stats_csv, stats_md]
    if args.write_docs:
        count_doc = docs_dir(config) / "COUNT_RECONCILIATION.md"
        write_stats_markdown(count_doc, stats)
        outputs.append(count_doc)
    manifest = out_dir / "stats_script_manifest.json"
    write_manifest(
        manifest,
        SCRIPT_NAME,
        outputs + [Path(path) for path in stats["detail_tables"].values()],
        [
            sqlite_db_path(config),
            configured_path(config, "inputs", "frontend_public_json"),
            configured_path(config, "inputs", "frontend_v2_json"),
            configured_path(config, "inputs", "canonical_count_reconciliation_csv"),
            configured_path(config, "inputs", "frontend_source_concentration_audit_csv"),
            configured_path(config, "inputs", "source_concentration_audit_csv"),
            configured_path(config, "inputs", "source_chain_audit_csv"),
            configured_path(config, "inputs", "constraint_decision_yaml"),
        ],
        stats["warnings"],
    )
    print(json.dumps({"counts": len(stats["counts"]), "out": rel_path(stats_json), "warnings": stats["warnings"]}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
