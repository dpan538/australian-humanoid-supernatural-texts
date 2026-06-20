#!/usr/bin/env python3
"""Export normalized V2 review CSVs and frontend-data/v2 JSON."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect, table_names
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso
from aus_humanoid.v2_schema import SCHEMA_VERSION


EXPORT_DIR = PROJECT_ROOT / "data" / "exports" / "v2"
FRONTEND_V2_PATH = PROJECT_ROOT / "public" / "data" / "frontend-data" / "v2.json"


def write_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def fetch_dicts(conn, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def date_band(value: str | None) -> str:
    if not value:
        return "undated / circulation period only"
    try:
        year = int(str(value)[:4])
    except ValueError:
        return "undated / circulation period only"
    if year < 1842:
        return "before 1842"
    if year <= 1875:
        return "1842-1875"
    if year <= 1918:
        return "1876-1918"
    if year <= 1945:
        return "1919-1945"
    if year <= 1969:
        return "1946-1969"
    if year <= 1999:
        return "1970-1999"
    return "2000-present"


def export_csvs(conn, export_dir: Path) -> dict[str, int]:
    source_items = fetch_dicts(
        conn,
        """
        SELECT
          ? AS schema_version, source_item_id, legacy_record_id, source_id,
          external_id, title, publication_or_organisation, author_or_creator,
          publication_date_text, publication_date_start, publication_date_end,
          publication_date_precision, access_date, url, canonical_url,
          persistent_identifier, source_type, source_tier, source_mediation,
          publicness_status, rights_access_status, reproduction_status,
          raw_snapshot_path, raw_snapshot_sha256, extracted_text_path,
          text_or_ocr_status, source_traceability_status, created_at, updated_at
        FROM source_items
        ORDER BY source_item_id
        """,
        (SCHEMA_VERSION,),
    )
    source_fields = list(source_items[0].keys()) if source_items else ["schema_version"]
    write_rows(export_dir / "source_items_review.csv", source_items, source_fields)

    narratives = fetch_dicts(
        conn,
        """
        SELECT
          ? AS schema_version, narrative_id, narrative_type, secondary_role,
          working_title, public_summary, narrative_status, analysis_status,
          humanoid_basis, australia_relation, earliest_attestation_start,
          earliest_attestation_end, earliest_attestation_precision,
          circulation_period_start, circulation_period_end, cultural_sensitivity,
          ethics_review_status, display_mode, normalized_entity_concept_id,
          classification_confidence, created_at, updated_at
        FROM narrative_units
        ORDER BY narrative_id
        """,
        (SCHEMA_VERSION,),
    )
    narrative_fields = list(narratives[0].keys()) if narratives else ["schema_version"]
    write_rows(export_dir / "narrative_units_review.csv", narratives, narrative_fields)

    exports = [
        (
            "encounter_events_review.csv",
            "SELECT ? AS schema_version, * FROM encounter_events ORDER BY encounter_event_id",
        ),
        (
            "narrative_source_links.csv",
            "SELECT ? AS schema_version, * FROM narrative_source_links ORDER BY narrative_source_link_id",
        ),
        (
            "narrative_relations.csv",
            "SELECT ? AS schema_version, * FROM narrative_relations ORDER BY narrative_relation_id",
        ),
        (
            "entity_labels_review.csv",
            "SELECT ? AS schema_version, * FROM entity_labels ORDER BY entity_label_id",
        ),
        (
            "entity_concepts.csv",
            "SELECT ? AS schema_version, * FROM entity_concepts ORDER BY entity_concept_id",
        ),
        (
            "narrative_locations_review.csv",
            """
            SELECT
              ? AS schema_version, nl.*, l.place_name, l.region, l.state_territory,
              l.country, l.latitude, l.longitude
            FROM narrative_locations nl
            JOIN locations l ON l.location_id = nl.location_id
            ORDER BY nl.narrative_location_id
            """,
        ),
        (
            "leads.csv",
            "SELECT ? AS schema_version, * FROM leads ORDER BY lead_id",
        ),
        (
            "exclusions.csv",
            "SELECT ? AS schema_version, * FROM exclusions ORDER BY exclusion_id",
        ),
    ]
    counts = {
        "source_items": len(source_items),
        "narrative_units": len(narratives),
    }
    for filename, sql in exports:
        rows = fetch_dicts(conn, sql, (SCHEMA_VERSION,))
        fields = list(rows[0].keys()) if rows else ["schema_version"]
        write_rows(export_dir / filename, rows, fields)
        counts[filename] = len(rows)

    review_queue = fetch_dicts(
        conn,
        """
        SELECT
          ? AS schema_version,
          m.legacy_record_id, m.source_item_id, m.narrative_id,
          m.primary_record_role, m.migration_confidence, m.review_flags,
          si.title, si.source_type, si.source_tier,
          nu.narrative_type, nu.secondary_role, nu.analysis_status,
          nu.ethics_review_status, nu.display_mode
        FROM legacy_record_mappings m
        JOIN source_items si ON si.source_item_id = m.source_item_id
        LEFT JOIN narrative_units nu ON nu.narrative_id = m.narrative_id
        WHERE COALESCE(nu.analysis_status, m.primary_record_role) IN
          ('display_ready_unreviewed', 'review_required', 'lead_only', 'exclusion', 'control')
           OR COALESCE(m.review_flags, '') != '[]'
        ORDER BY m.legacy_record_id
        """,
        (SCHEMA_VERSION,),
    )
    review_fields = list(review_queue[0].keys()) if review_queue else ["schema_version"]
    write_rows(export_dir / "review_queue.csv", review_queue, review_fields)
    counts["review_queue"] = len(review_queue)

    accepted_new = fetch_dicts(
        conn,
        """
        SELECT ? AS schema_version, *
        FROM collection_candidates_v2
        WHERE candidate_status = 'accepted'
        ORDER BY candidate_id
        """,
        (SCHEMA_VERSION,),
    )
    rejected_new = fetch_dicts(
        conn,
        """
        SELECT ? AS schema_version, *
        FROM collection_candidates_v2
        WHERE candidate_status IN ('rejected', 'duplicate', 'lead_only')
        ORDER BY candidate_id
        """,
        (SCHEMA_VERSION,),
    )
    write_rows(export_dir / "collection_500_accepted.csv", accepted_new, list(accepted_new[0].keys()) if accepted_new else ["schema_version"])
    write_rows(export_dir / "collection_500_rejected.csv", rejected_new, list(rejected_new[0].keys()) if rejected_new else ["schema_version"])
    counts["collection_500_accepted"] = len(accepted_new)
    counts["collection_500_rejected"] = len(rejected_new)
    return counts


def frontend_payload(conn) -> dict[str, Any]:
    source_items = fetch_dicts(conn, "SELECT * FROM source_items")
    narratives = fetch_dicts(conn, "SELECT * FROM narrative_units")
    locations = fetch_dicts(
        conn,
        """
        SELECT nl.*, l.place_name, l.region, l.state_territory, l.country,
               l.latitude, l.longitude, nu.narrative_type, nu.display_mode,
               nu.working_title
        FROM narrative_locations nl
        JOIN locations l ON l.location_id = nl.location_id
        JOIN narrative_units nu ON nu.narrative_id = nl.narrative_id
        WHERE nu.display_mode != 'suppressed'
        ORDER BY nl.narrative_location_id
        """,
    )
    labels = fetch_dicts(conn, "SELECT * FROM entity_labels")
    concepts = fetch_dicts(conn, "SELECT * FROM entity_concepts")
    links = fetch_dicts(conn, "SELECT * FROM narrative_source_links")
    candidates = fetch_dicts(conn, "SELECT * FROM collection_candidates_v2")

    narrative_type_counts = Counter(row.get("narrative_type") or row.get("secondary_role") or "untyped" for row in narratives)
    analysis_counts = Counter(row.get("analysis_status") or "unknown" for row in narratives)
    sensitivity_counts = Counter(row.get("cultural_sensitivity") or "unknown" for row in narratives)
    source_tier_counts = Counter(row.get("source_tier") or "unknown" for row in source_items)
    source_org_counts = Counter(row.get("publication_or_organisation") or "unknown" for row in source_items)
    location_role_counts = Counter(row.get("location_role") or "unknown" for row in locations)
    state_counts = Counter((row.get("state_territory") or "AU_UNSPECIFIED") for row in locations)
    date_counts = Counter(date_band(row.get("earliest_attestation_start")) for row in narratives)

    map_layers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in locations:
        layer = row.get("location_role") or "uncertain_or_broad_location"
        if layer == "publication_location":
            continue
        map_layers[layer].append(row)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "summary_counts": {
            "source_item_count": len(source_items),
            "narrative_unit_count": len(narratives),
            "encounter_account_count": narrative_type_counts.get("encounter_account", 0),
            "apparition_account_count": narrative_type_counts.get("apparition_account", 0),
            "ghost_legend_count": narrative_type_counts.get("ghost_legend", 0),
            "rumour_local_legend_count": narrative_type_counts.get("rumour_account", 0) + narrative_type_counts.get("local_legend", 0),
            "traditional_spirit_person_count": narrative_type_counts.get("traditional_narrative", 0)
            + narrative_type_counts.get("spirit_person_narrative", 0)
            + narrative_type_counts.get("giant_or_ogre_narrative", 0),
            "retelling_adaptation_count": narrative_type_counts.get("retelling_or_adaptation", 0),
            "discourse_context_count": sum(
                narrative_type_counts.get(key, 0)
                for key in ["heritage_discourse", "tourism_discourse", "media_commentary", "scholarly_commentary", "catalogue_metadata"]
            ),
            "unresolved_lead_count": analysis_counts.get("lead_only", 0),
            "analysis_ready_count": analysis_counts.get("analysis_ready", 0),
            "high_sensitivity_count": sensitivity_counts.get("high", 0) + sensitivity_counts.get("very_high", 0),
            "entity_concept_count": len(concepts),
            "source_label_count": len(labels),
        },
        "counts": {
            "narrative_types": dict(narrative_type_counts),
            "analysis_status": dict(analysis_counts),
            "source_tiers": dict(source_tier_counts),
            "source_organisations": dict(source_org_counts),
            "location_roles": dict(location_role_counts),
            "states": dict(state_counts),
            "date_bands": dict(date_counts),
            "collection_candidates": dict(Counter(row.get("candidate_status") or "unknown" for row in candidates)),
        },
        "map_layers": map_layers,
        "timeline_fields": [
            "event_date",
            "earliest_attestation",
            "publication_date",
            "retelling_date",
            "circulation_period",
        ],
        "narratives": narratives,
        "source_items": source_items,
        "entity_labels": labels,
        "entity_concepts": concepts,
        "narrative_source_links": links,
        "public_note": "Map data represents narrative geography, source geography, or alleged event geography, not verified supernatural distribution.",
    }


def export_all(db_path: str | Path, export_dir: Path, frontend_path: Path) -> dict[str, int]:
    with connect(db_path) as conn:
        required = {"source_items", "narrative_units", "legacy_record_mappings"}
        missing = required - table_names(conn)
        if missing:
            raise SystemExit(f"Missing V2 tables: {', '.join(sorted(missing))}. Run make migrate-v2 first.")
        counts = export_csvs(conn, export_dir)
        payload = frontend_payload(conn)
    frontend_path.parent.mkdir(parents=True, exist_ok=True)
    frontend_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "exports": counts,
        "frontend_data_v2": str(frontend_path.relative_to(PROJECT_ROOT)),
    }
    (export_dir / "MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--export-dir", default=str(EXPORT_DIR), help="V2 export directory")
    parser.add_argument("--frontend-output", default=str(FRONTEND_V2_PATH), help="frontend-data/v2 JSON path")
    args = parser.parse_args()
    counts = export_all(args.db, Path(args.export_dir), Path(args.frontend_output))
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
