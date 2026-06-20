#!/usr/bin/env python3
"""Create V2 normalized tables and migrate legacy flat records.

The migration is intentionally conservative: every legacy record becomes a
source_item and a legacy_record_mapping, while narrative_units are only created
when the source item has enough public substance to display as a narrative or
context record. Automated migration never assigns analysis_ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_alias, parse_year
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso
from aus_humanoid.v2_schema import (
    SCHEMA_VERSION,
    V2_INDEX_STATEMENTS,
    V2_SCHEMA_STATEMENTS,
    V2_TABLES,
)


MIGRATION_VERSION = "002_normalized_narrative_archive"
MIGRATION_NAME = "Create normalized narrative/source model and map legacy records"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "migration_report.md"
DEFAULT_RECLASS_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "legacy_985_reclassification_report.md"

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}

CONTROL_TERMS = {"bunyip", "drop bear", "min min lights"}
EXCLUSION_TERMS = {"rainbow serpent", "ngatyi", "bula"}
TRADITIONAL_TERMS = {
    "yaroma",
    "yara-ma-yha-who",
    "yara-ma-tha-who",
    "mimih",
    "mimi",
    "quinkan",
    "quinkin",
    "wandjina",
    "wanjina",
    "nargun",
    "garkain",
    "mokoi",
    "mamu",
    "pangkarlangu",
    "puttikan",
    "tjangara",
}
HIGH_SENSITIVITY_TERMS = {"wandjina", "wanjina", "mamu", "quinkan", "quinkin"}
HAIRY_HUMANOID_TERMS = {
    "yowie",
    "yahoo",
    "hairy man",
    "hairy man of the wood",
    "australian ape",
    "australian gorilla",
    "wild man",
    "ape-like man",
    "unknown humanoid",
}


@dataclass(frozen=True)
class Classification:
    primary_role: str
    narrative_type: str | None
    secondary_role: str | None
    relationship_type: str | None
    source_tier: str
    source_mediation: str
    narrative_status: str
    analysis_status: str
    humanoid_basis: str
    australia_relation: str
    cultural_sensitivity: str
    ethics_review_status: str
    display_mode: str
    classification_confidence: str
    source_traceability_status: str
    rights_access_status: str
    reproduction_status: str
    text_or_ocr_status: str
    label_type: str
    entity_concept_key: str | None
    review_flags: list[str]
    notes: str


def canonicalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS],
        doseq=True,
    )
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((scheme, netloc, path, query, ""))


def checksum_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def migration_checksum() -> str:
    payload = "\n".join(V2_SCHEMA_STATEMENTS + V2_INDEX_STATEMENTS)
    return checksum_text(payload)


def apply_v2_schema(conn: sqlite3.Connection) -> None:
    now = utc_now_iso()
    for statement in V2_SCHEMA_STATEMENTS:
        conn.execute(statement)
    for statement in V2_INDEX_STATEMENTS:
        conn.execute(statement)
    conn.execute(
        """
        INSERT INTO schema_migrations(version, name, applied_at, checksum, reversible, notes)
        VALUES (?, ?, ?, ?, 0, ?)
        ON CONFLICT(version) DO UPDATE SET
            name=excluded.name,
            checksum=excluded.checksum,
            notes=excluded.notes
        """,
        (
            MIGRATION_VERSION,
            MIGRATION_NAME,
            now,
            migration_checksum(),
            f"Schema version {SCHEMA_VERSION}. Additive migration; legacy tables remain intact.",
        ),
    )


def ensure_entity_concepts(conn: sqlite3.Connection) -> dict[str, int]:
    now = utc_now_iso()
    concepts = [
        (
            "hairy_humanoid_operational_cluster",
            "Hairy / upright anomalous humanoid narratives",
            "operational_cluster",
            "Operational grouping for Yowie, Yahoo, Hairy Man, Australian ape/gorilla, wild man, and similar source labels.",
            "medium",
        ),
        (
            "traditional_spirit_person_cluster",
            "Traditional and spirit-person public narratives",
            "contextual_cluster",
            "Public narratives and heritage/discourse records using source/community terminology; not a cryptid category.",
            "high",
        ),
        (
            "control_or_excluded_terms",
            "Controls and exclusions",
            "control_cluster",
            "Terms retained for contrast or explicit exclusion from humanoid-core counts.",
            "medium",
        ),
        (
            "unresolved_or_validation_label",
            "Unresolved validation label",
            "validation_cluster",
            "Source labels requiring stronger public provenance before normalization.",
            "medium",
        ),
    ]
    for row in concepts:
        conn.execute(
            """
            INSERT INTO entity_concepts(
                concept_key, display_name, concept_scope, description,
                sensitivity_level, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(concept_key) DO UPDATE SET
                display_name=excluded.display_name,
                concept_scope=excluded.concept_scope,
                description=excluded.description,
                sensitivity_level=excluded.sensitivity_level,
                updated_at=excluded.updated_at
            """,
            (*row, now, now),
        )
    return {
        row["concept_key"]: int(row["entity_concept_id"])
        for row in conn.execute("SELECT entity_concept_id, concept_key FROM entity_concepts")
    }


def source_tier_for(source_type: str, source_name: str) -> tuple[str, str, str]:
    st = source_type or ""
    name = (source_name or "").lower()
    if st in {"trove_newspaper", "trove_magazine", "nla_catalogue"}:
        return "A", "original_or_near_primary", "stable_public_identifier"
    if st in {"aiatsis_public_catalogue", "andc"}:
        return "B", "public_institutional_metadata", "public_metadata_only"
    if st in {"academic_metadata"}:
        return "B", "bibliographic_metadata", "metadata_only_pointer"
    if st in {"internet_archive_metadata"}:
        return "A", "digitized_public_item_or_metadata", "metadata_requires_item_inspection"
    if "yowie research" in name:
        return "E", "specialist_aggregator_or_witness_publication", "public_page_traceable"
    if st in {"modern_web"}:
        return "C", "public_web_or_media", "public_page_traceable"
    if st in {"wikimedia_pageviews", "google_trends"}:
        return "attention", "attention_series", "not_source_item_evidence"
    return "C", "public_source", "public_page_traceable"


def label_for(row: sqlite3.Row) -> str:
    for field in ("figure_name_as_printed", "canonical_figure_guess", "canonical_name"):
        value = row[field] if field in row.keys() else None
        if value:
            return str(value)
    return "unknown humanoid"


def classify(row: sqlite3.Row) -> Classification:
    source_type = row["source_type"] or ""
    source_name = row["source_name"] or ""
    source_tier, source_mediation, traceability = source_tier_for(source_type, source_name)
    label = normalise_alias(label_for(row))
    title = normalise_alias(row["title"] or "")
    snippet = normalise_alias(row["snippet"] or "")
    text = " ".join([label, title, snippet])
    flags: list[str] = []

    if label in CONTROL_TERMS or row["include_status"] == "control_only":
        return Classification(
            "control",
            None,
            "control",
            None,
            source_tier,
            source_mediation,
            "control",
            "excluded",
            "non_core_control",
            "australia_public_text",
            "medium",
            "not_required_control",
            "metadata_only",
            "medium",
            traceability,
            "public_review_required",
            "metadata_or_short_excerpt_only",
            "metadata_or_excerpt",
            "compiler_supplied_label",
            "control_or_excluded_terms",
            ["control"],
            "Control term retained outside humanoid-core counts.",
        )
    if label in EXCLUSION_TERMS or row["include_status"] == "exclude_core":
        return Classification(
            "exclusion",
            None,
            "exclusion",
            None,
            source_tier,
            source_mediation,
            "excluded",
            "excluded",
            "outside_v2_core",
            "australia_public_text",
            "very_high",
            "excluded_by_scope",
            "suppressed",
            "medium",
            traceability,
            "public_review_required",
            "metadata_or_short_excerpt_only",
            "metadata_or_excerpt",
            "compiler_supplied_label",
            "control_or_excluded_terms",
            ["exclusion"],
            "Excluded/control material kept auditable but outside public core.",
        )

    indigenous = bool(row["involves_indigenous_knowledge"])
    high_sensitivity = label in HIGH_SENSITIVITY_TERMS or "wandjina" in text or "wanjina" in text
    if high_sensitivity:
        sensitivity = "high"
        display_mode = "summary_only"
        ethics = "requires_ethics_review"
        flags.append("high_sensitivity")
    elif indigenous:
        sensitivity = "medium"
        display_mode = "summary_only"
        ethics = "caution_indigenous_related"
        flags.append("indigenous_related")
    else:
        sensitivity = "low"
        display_mode = "full"
        ethics = "ok_public"

    if source_type in {"academic_metadata"}:
        return Classification(
            "catalogue_metadata",
            None,
            "catalogue_metadata",
            "catalogue_pointer",
            source_tier,
            source_mediation,
            "metadata_pointer",
            "lead_only",
            "public_metadata_mentions_project_label",
            "australia_relation_requires_review",
            sensitivity,
            ethics,
            "metadata_only",
            "medium",
            traceability,
            "metadata_public_reuse_unclear",
            "metadata_only",
            "metadata_only",
            "compiler_supplied_label",
            "traditional_spirit_person_cluster" if indigenous else "unresolved_or_validation_label",
            flags + ["metadata_only_not_accepted"],
            "Bibliographic metadata is a source pointer unless accessible content is reviewed.",
        )
    if source_type in {"internet_archive_metadata"} and not row["full_text_path"]:
        flags.append("item_text_requires_inspection")

    if label in TRADITIONAL_TERMS or indigenous:
        if "giant" in text or label in {"pangkarlangu", "tjangara"}:
            narrative_type = "giant_or_ogre_narrative"
        elif "spirit" in text or label in {"mimih", "mimi", "quinkan", "quinkin", "wandjina", "wanjina", "mokoi", "mamu", "garkain"}:
            narrative_type = "spirit_person_narrative"
        else:
            narrative_type = "traditional_narrative"
        return Classification(
            "first-class narrative source",
            narrative_type,
            "heritage_discourse" if source_type in {"modern_web", "internet_archive_metadata"} else None,
            "original_publication" if source_tier == "A" else "derivative_web_summary",
            source_tier,
            source_mediation,
            "legacy_migrated_public_narrative",
            "display_ready_unreviewed",
            "public_source_describes_humanoid_or_spirit_person_basis",
            "australia_public_text_or_association",
            sensitivity,
            ethics,
            display_mode,
            "medium",
            traceability,
            "public_review_required",
            "short_excerpt_or_summary_only",
            "metadata_or_excerpt",
            "exact_name",
            "traditional_spirit_person_cluster",
            flags,
            "Traditional/spirit-person material preserved as public narrative/context, not cryptid taxonomy.",
        )

    if label in HAIRY_HUMANOID_TERMS or row["canonical_name"] == "Yowie":
        relationship = "witness_account_publication"
        role = "first-class narrative source"
        if "Australian Yowie Research" in source_name:
            relationship = "retrospective_summary"
            if "historical" in text or "newspaper" in text or (row["year"] and int(row["year"]) < 1970):
                relationship = "archive_reproduction"
                flags.append("original_article_verification_required")
        return Classification(
            role,
            "encounter_account",
            None,
            relationship,
            source_tier,
            source_mediation,
            "legacy_migrated_encounter_candidate",
            "display_ready_unreviewed",
            "source_reports_humanoid_or_hairy_upright_figure",
            "australian_event_or_public_text_relation",
            sensitivity,
            ethics,
            display_mode,
            "medium",
            traceability,
            "public_review_required",
            "short_excerpt_or_summary_only",
            "metadata_or_excerpt",
            "exact_name" if label == "yowie" else "historical_descriptor",
            "hairy_humanoid_operational_cluster",
            flags,
            "Migrated as encounter-account candidate; source verification does not verify supernatural claim.",
        )

    return Classification(
        "source pointer",
        None,
        "source_pointer",
        "derivative_web_summary",
        source_tier,
        source_mediation,
        "requires_review",
        "lead_only",
        "humanoid_basis_requires_review",
        "australia_relation_requires_review",
        sensitivity,
        ethics,
        "metadata_only",
        "low",
        traceability,
        "public_review_required",
        "metadata_or_short_excerpt_only",
        "metadata_or_excerpt",
        "uncertain_label",
        "unresolved_or_validation_label",
        flags + ["requires_manual_classification"],
        "Legacy row could not be safely promoted by deterministic rules.",
    )


def date_precision(date_text: str | None, year: int | None) -> str:
    text = str(date_text or "").strip()
    if not text and year:
        return "year"
    if not text:
        return "unknown"
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return "exact_day"
    if len(text) >= 7 and text[4:5] == "-":
        return "month"
    if parse_year(text):
        return "year"
    return "unknown"


def concise_summary(row: sqlite3.Row, classification: Classification) -> str:
    title = row["title"] or "Untitled public source"
    label = label_for(row)
    source = row["source_name"] or row["publication"] or "public source"
    snippet = (row["snippet"] or "").strip()
    if snippet:
        evidence = snippet[:360]
    else:
        evidence = "The migrated legacy source contains enough public metadata for review, but needs manual excerpt verification."
    return f"The source reports or discusses {label} in '{title}' ({source}). {evidence}"


def get_or_create_source_item(conn: sqlite3.Connection, row: sqlite3.Row, classification: Classification) -> int:
    now = utc_now_iso()
    canonical_url = canonicalize_url(row["url"])
    year = row["year"]
    date_text = row["date_published"] or (str(year) if year else "")
    pub_start = str(year) if year else ""
    extracted_text_path = row["full_text_path"] or ""
    raw_sha = ""
    if extracted_text_path:
        path = PROJECT_ROOT / extracted_text_path
        if path.exists():
            raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()

    conn.execute(
        """
        INSERT INTO source_items(
            legacy_record_id, source_id, external_id, title, publication_or_organisation,
            author_or_creator, publication_date_text, publication_date_start,
            publication_date_end, publication_date_precision, access_date, url,
            canonical_url, persistent_identifier, source_type, source_tier,
            source_mediation, publicness_status, rights_access_status,
            reproduction_status, raw_snapshot_path, raw_snapshot_sha256,
            extracted_text_path, text_or_ocr_status, source_traceability_status,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(legacy_record_id) DO UPDATE SET
            source_id=excluded.source_id,
            external_id=excluded.external_id,
            title=excluded.title,
            publication_or_organisation=excluded.publication_or_organisation,
            author_or_creator=excluded.author_or_creator,
            publication_date_text=excluded.publication_date_text,
            publication_date_start=excluded.publication_date_start,
            publication_date_end=excluded.publication_date_end,
            publication_date_precision=excluded.publication_date_precision,
            access_date=excluded.access_date,
            url=excluded.url,
            canonical_url=excluded.canonical_url,
            persistent_identifier=excluded.persistent_identifier,
            source_type=excluded.source_type,
            source_tier=excluded.source_tier,
            source_mediation=excluded.source_mediation,
            publicness_status=excluded.publicness_status,
            rights_access_status=excluded.rights_access_status,
            reproduction_status=excluded.reproduction_status,
            raw_snapshot_path=excluded.raw_snapshot_path,
            raw_snapshot_sha256=excluded.raw_snapshot_sha256,
            extracted_text_path=excluded.extracted_text_path,
            text_or_ocr_status=excluded.text_or_ocr_status,
            source_traceability_status=excluded.source_traceability_status,
            updated_at=excluded.updated_at
        """,
        (
            row["record_id"],
            row["source_id"],
            row["external_id"],
            row["title"],
            row["publication"] or row["source_name"],
            row["author"],
            date_text,
            pub_start,
            pub_start,
            date_precision(date_text, year),
            now[:10],
            row["url"],
            canonical_url,
            row["external_id"],
            row["source_type"],
            classification.source_tier,
            classification.source_mediation,
            row["publicness_level"] or row["publicness_code"] or "public_page",
            classification.rights_access_status,
            classification.reproduction_status,
            row["raw_metadata_json"] or "",
            raw_sha,
            extracted_text_path,
            classification.text_or_ocr_status,
            classification.source_traceability_status,
            now,
            now,
        ),
    )
    return int(conn.execute("SELECT source_item_id FROM source_items WHERE legacy_record_id = ?", (row["record_id"],)).fetchone()[0])


def get_or_create_narrative(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    classification: Classification,
    concept_ids: dict[str, int],
) -> int | None:
    if classification.analysis_status in {"lead_only", "excluded"} and classification.narrative_type is None:
        return None
    now = utc_now_iso()
    key = f"legacy:{row['record_id']}"
    year = row["year"]
    concept_id = concept_ids.get(classification.entity_concept_key or "")
    summary = concise_summary(row, classification)
    conn.execute(
        """
        INSERT INTO narrative_units(
            migration_key, narrative_type, secondary_role, working_title, public_summary,
            narrative_status, analysis_status, humanoid_basis, australia_relation,
            earliest_attestation_start, earliest_attestation_end,
            earliest_attestation_precision, circulation_period_start,
            circulation_period_end, cultural_sensitivity, ethics_review_status,
            display_mode, normalized_entity_concept_id, classification_confidence,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(migration_key) DO UPDATE SET
            narrative_type=excluded.narrative_type,
            secondary_role=excluded.secondary_role,
            working_title=excluded.working_title,
            public_summary=excluded.public_summary,
            narrative_status=excluded.narrative_status,
            analysis_status=excluded.analysis_status,
            humanoid_basis=excluded.humanoid_basis,
            australia_relation=excluded.australia_relation,
            earliest_attestation_start=excluded.earliest_attestation_start,
            earliest_attestation_end=excluded.earliest_attestation_end,
            earliest_attestation_precision=excluded.earliest_attestation_precision,
            circulation_period_start=excluded.circulation_period_start,
            circulation_period_end=excluded.circulation_period_end,
            cultural_sensitivity=excluded.cultural_sensitivity,
            ethics_review_status=excluded.ethics_review_status,
            display_mode=excluded.display_mode,
            normalized_entity_concept_id=excluded.normalized_entity_concept_id,
            classification_confidence=excluded.classification_confidence,
            updated_at=excluded.updated_at
        """,
        (
            key,
            classification.narrative_type,
            classification.secondary_role,
            row["title"] or label_for(row),
            summary,
            classification.narrative_status,
            classification.analysis_status,
            classification.humanoid_basis,
            classification.australia_relation,
            str(year) if year else "",
            str(year) if year else "",
            "year" if year else "unknown",
            str(year) if year else "",
            str(year) if year else "",
            classification.cultural_sensitivity,
            classification.ethics_review_status,
            classification.display_mode,
            concept_id,
            classification.classification_confidence,
            now,
            now,
        ),
    )
    return int(conn.execute("SELECT narrative_id FROM narrative_units WHERE migration_key = ?", (key,)).fetchone()[0])


def upsert_link(conn: sqlite3.Connection, narrative_id: int | None, source_item_id: int, classification: Classification) -> None:
    if narrative_id is None or classification.relationship_type is None:
        return
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO narrative_source_links(
            narrative_id, source_item_id, relationship_type, confidence,
            evidence_note, human_review_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(narrative_id, source_item_id, relationship_type) DO UPDATE SET
            confidence=excluded.confidence,
            evidence_note=excluded.evidence_note,
            human_review_status=excluded.human_review_status,
            updated_at=excluded.updated_at
        """,
        (
            narrative_id,
            source_item_id,
            classification.relationship_type,
            classification.classification_confidence,
            classification.notes,
            "pending",
            now,
            now,
        ),
    )


def upsert_encounter_event(conn: sqlite3.Connection, row: sqlite3.Row, narrative_id: int | None, classification: Classification) -> None:
    if narrative_id is None or classification.narrative_type != "encounter_account":
        return
    year = row["year"]
    date_text = row["date_published"] or (str(year) if year else "")
    summary = concise_summary(row, classification)
    conn.execute(
        """
        INSERT INTO encounter_events(
            narrative_id, event_date_start, event_date_end, event_date_precision,
            witness_count, witness_type, encounter_context, morphology_evidence,
            behaviour_evidence, anomaly_evidence, event_summary, event_review_status
        )
        VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(narrative_id) DO UPDATE SET
            event_date_start=excluded.event_date_start,
            event_date_end=excluded.event_date_end,
            event_date_precision=excluded.event_date_precision,
            witness_type=excluded.witness_type,
            encounter_context=excluded.encounter_context,
            morphology_evidence=excluded.morphology_evidence,
            behaviour_evidence=excluded.behaviour_evidence,
            anomaly_evidence=excluded.anomaly_evidence,
            event_summary=excluded.event_summary,
            event_review_status=excluded.event_review_status
        """,
        (
            narrative_id,
            str(year) if year else "",
            str(year) if year else "",
            date_precision(date_text, year),
            "unknown",
            classification.source_mediation,
            row["snippet"] or row["title"] or "",
            "",
            classification.humanoid_basis,
            summary,
            "pending_human_review",
        ),
    )


def upsert_label(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    source_item_id: int,
    narrative_id: int | None,
    classification: Classification,
    concept_ids: dict[str, int],
) -> None:
    label = label_for(row)
    concept_id = concept_ids.get(classification.entity_concept_key or "")
    if narrative_id is None:
        conn.execute(
            """
            DELETE FROM entity_labels
            WHERE source_item_id = ?
              AND narrative_id IS NULL
              AND label_text = ?
              AND label_type = ?
            """,
            (source_item_id, label, classification.label_type),
        )
    conn.execute(
        """
        INSERT INTO entity_labels(
            source_item_id, narrative_id, label_text, normalized_text,
            language_or_dialect, label_type, supplied_by, source_context,
            entity_concept_id, normalization_status, review_status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_item_id, narrative_id, label_text, label_type) DO UPDATE SET
            normalized_text=excluded.normalized_text,
            supplied_by=excluded.supplied_by,
            source_context=excluded.source_context,
            entity_concept_id=excluded.entity_concept_id,
            normalization_status=excluded.normalization_status,
            review_status=excluded.review_status
        """,
        (
            source_item_id,
            narrative_id,
            label,
            normalise_alias(label),
            "",
            classification.label_type,
            "source_or_legacy_coding",
            row["snippet"] or row["title"] or "",
            concept_id,
            "preserved_source_label",
            "pending",
        ),
    )


def map_location_role(classification: Classification, relation_type: str | None, location_type: str | None) -> str:
    rel = relation_type or ""
    loc = location_type or ""
    if classification.narrative_type == "encounter_account" and rel == "reported_place":
        return "alleged_event_location"
    if classification.narrative_type == "apparition_account" and rel == "reported_place":
        return "apparition_location"
    if classification.narrative_type in {"ghost_legend", "local_legend"}:
        return "legend_associated_place"
    if classification.narrative_type in {"traditional_narrative", "spirit_person_narrative", "giant_or_ogre_narrative"}:
        return "cultural_association_region" if loc in {"figure_associated_region", "state_or_territory"} else "narrative_setting"
    if rel == "mentioned_place":
        return "narrative_setting"
    if loc in {"country_or_unclear", "broad_region"}:
        return "uncertain_or_broad_location"
    return "uncertain_or_broad_location"


def migrate_locations(conn: sqlite3.Connection, legacy_record_id: int, source_item_id: int, narrative_id: int | None, classification: Classification) -> int:
    if narrative_id is None:
        return 0
    now = utc_now_iso()
    rows = conn.execute(
        """
        SELECT rl.*, l.location_type, l.place_name
        FROM record_locations rl
        JOIN locations l ON l.location_id = rl.location_id
        WHERE rl.record_id = ?
        """,
        (legacy_record_id,),
    ).fetchall()
    count = 0
    for loc in rows:
        role = map_location_role(classification, loc["relation_type"], loc["location_type"])
        conn.execute(
            """
            INSERT INTO narrative_locations(
                narrative_id, location_id, source_item_id, location_role,
                location_text_as_printed, location_precision, verification_status,
                confidence, evidence_excerpt, review_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(narrative_id, location_id, source_item_id, location_role) DO UPDATE SET
                location_text_as_printed=excluded.location_text_as_printed,
                location_precision=excluded.location_precision,
                verification_status=excluded.verification_status,
                confidence=excluded.confidence,
                evidence_excerpt=excluded.evidence_excerpt,
                review_status=excluded.review_status
            """,
            (
                narrative_id,
                loc["location_id"],
                source_item_id,
                role,
                loc["place_name"],
                loc["location_type"] or "unknown",
                loc["notes"] or "legacy_location_needs_review",
                loc["confidence"] or "low",
                loc["evidence_text"] or "",
                "pending",
                now,
            ),
        )
        count += 1
    return count


def upsert_mapping(
    conn: sqlite3.Connection,
    legacy_record_id: int,
    source_item_id: int,
    narrative_id: int | None,
    classification: Classification,
) -> None:
    now = utc_now_iso()
    conn.execute(
        """
        INSERT INTO legacy_record_mappings(
            legacy_record_id, source_item_id, narrative_id, primary_record_role,
            migration_status, migration_confidence, review_flags,
            migration_notes, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(legacy_record_id) DO UPDATE SET
            source_item_id=excluded.source_item_id,
            narrative_id=excluded.narrative_id,
            primary_record_role=excluded.primary_record_role,
            migration_status=excluded.migration_status,
            migration_confidence=excluded.migration_confidence,
            review_flags=excluded.review_flags,
            migration_notes=excluded.migration_notes,
            updated_at=excluded.updated_at
        """,
        (
            legacy_record_id,
            source_item_id,
            narrative_id,
            classification.primary_role,
            "mapped",
            classification.classification_confidence,
            json.dumps(classification.review_flags, ensure_ascii=False),
            classification.notes,
            now,
            now,
        ),
    )


def upsert_exclusion(conn: sqlite3.Connection, row: sqlite3.Row, source_item_id: int, narrative_id: int | None, classification: Classification) -> None:
    if classification.primary_role not in {"control", "exclusion"}:
        return
    now = utc_now_iso()
    existing = conn.execute(
        "SELECT exclusion_id FROM exclusions WHERE legacy_record_id = ? AND exclusion_type = ?",
        (row["record_id"], classification.primary_role),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE exclusions SET reason = ?, evidence_note = ? WHERE exclusion_id = ?",
            (classification.notes, row["snippet"] or row["title"] or "", existing["exclusion_id"]),
        )
    else:
        conn.execute(
            """
            INSERT INTO exclusions(
                legacy_record_id, source_item_id, narrative_id, exclusion_type,
                reason, evidence_note, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (row["record_id"], source_item_id, narrative_id, classification.primary_role, classification.notes, row["snippet"] or "", now),
        )


def legacy_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            r.*, s.source_name, s.source_type,
            f.canonical_name, f.cluster, f.tier, f.include_status,
            f.involves_indigenous_knowledge,
            c.canonical_figure_guess, c.figure_name_as_printed,
            c.ontology_code, c.humanoid_degree_code, c.publicness_code,
            c.relevance_code, c.ethics_flag, c.genre
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN figures f ON f.figure_id = r.figure_id
        LEFT JOIN coding c ON c.record_id = r.record_id
        ORDER BY r.record_id
        """
    ).fetchall()


def migrate(db_path: str | Path) -> dict[str, Any]:
    with connect(db_path) as conn:
        apply_v2_schema(conn)
        concept_ids = ensure_entity_concepts(conn)
        counters: Counter[str] = Counter()
        source_counter: Counter[str] = Counter()
        type_counter: Counter[str] = Counter()
        location_count = 0
        for row in legacy_rows(conn):
            classification = classify(row)
            source_item_id = get_or_create_source_item(conn, row, classification)
            narrative_id = get_or_create_narrative(conn, row, classification, concept_ids)
            upsert_link(conn, narrative_id, source_item_id, classification)
            upsert_encounter_event(conn, row, narrative_id, classification)
            upsert_label(conn, row, source_item_id, narrative_id, classification, concept_ids)
            location_count += migrate_locations(conn, int(row["record_id"]), source_item_id, narrative_id, classification)
            upsert_mapping(conn, int(row["record_id"]), source_item_id, narrative_id, classification)
            upsert_exclusion(conn, row, source_item_id, narrative_id, classification)
            counters[classification.primary_role] += 1
            counters[classification.analysis_status] += 1
            source_counter[row["source_name"] or "unknown"] += 1
            if classification.narrative_type:
                type_counter[classification.narrative_type] += 1
            elif classification.secondary_role:
                type_counter[classification.secondary_role] += 1
        conn.commit()
        totals = {
            "legacy_rows": conn.execute("SELECT COUNT(*) FROM records").fetchone()[0],
            "source_items": conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0],
            "narrative_units": conn.execute("SELECT COUNT(*) FROM narrative_units").fetchone()[0],
            "encounter_events": conn.execute("SELECT COUNT(*) FROM encounter_events").fetchone()[0],
            "mappings": conn.execute("SELECT COUNT(*) FROM legacy_record_mappings").fetchone()[0],
            "unmapped": conn.execute(
                "SELECT COUNT(*) FROM records r LEFT JOIN legacy_record_mappings m ON m.legacy_record_id = r.record_id WHERE m.legacy_record_id IS NULL"
            ).fetchone()[0],
            "narrative_locations": conn.execute("SELECT COUNT(*) FROM narrative_locations").fetchone()[0],
            "entity_labels": conn.execute("SELECT COUNT(*) FROM entity_labels").fetchone()[0],
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "totals": totals,
        "roles": dict(counters),
        "sources": dict(source_counter),
        "types": dict(type_counter),
        "location_links_migrated": location_count,
    }


def write_reports(result: dict[str, Any], report_path: Path, reclass_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    totals = result["totals"]
    lines = [
        "# V2 Migration Report",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Schema version: `{result['schema_version']}`",
        f"- Legacy rows: {totals['legacy_rows']}",
        f"- Migrated source items: {totals['source_items']}",
        f"- Migrated narrative units: {totals['narrative_units']}",
        f"- Legacy mappings: {totals['mappings']}",
        f"- Unmapped legacy rows: {totals['unmapped']}",
        f"- Entity labels: {totals['entity_labels']}",
        f"- Narrative locations: {totals['narrative_locations']}",
        "",
        "## Notes",
        "- The legacy `records` table is intact.",
        "- Automated migration never assigns `analysis_ready`.",
        "- Academic metadata is migrated as catalogue/source-pointer material unless manually reviewed later.",
        "- Source labels are preserved separately from entity concepts.",
        "- Publication/source geography is not silently converted into event geography.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    reclass_lines = [
        "# Legacy Reclassification Report",
        "",
        f"- Generated: `{utc_now_iso()}`",
        "",
        "## Primary Roles and Statuses",
    ]
    for key, value in sorted(result["roles"].items()):
        reclass_lines.append(f"- {key}: {value}")
    reclass_lines.extend(["", "## Narrative Types and Secondary Roles"])
    for key, value in sorted(result["types"].items()):
        reclass_lines.append(f"- {key}: {value}")
    reclass_lines.extend(["", "## Legacy Source Families"])
    for key, value in sorted(result["sources"].items(), key=lambda item: (-item[1], item[0])):
        reclass_lines.append(f"- {key}: {value}")
    reclass_lines.extend(
        [
            "",
            "## Interpretation",
            "- These classifications are deterministic first-pass review states, not final scholarly coding.",
            "- `display_ready_unreviewed` means suitable for interface review cards, not analysis-ready evidence.",
            "- `lead_only` records remain useful but do not count as accepted source items for the V2 +500 target.",
        ]
    )
    reclass_path.parent.mkdir(parents=True, exist_ok=True)
    reclass_path.write_text("\n".join(reclass_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Migration report path")
    parser.add_argument("--reclassification-report", default=str(DEFAULT_RECLASS_REPORT), help="Legacy reclassification report path")
    args = parser.parse_args()
    result = migrate(args.db)
    write_reports(result, Path(args.report), Path(args.reclassification_report))
    print(json.dumps(result["totals"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
