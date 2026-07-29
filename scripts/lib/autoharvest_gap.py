from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from collection_expansion_common import now_iso
from lib.autoharvest_engine import PRIORITY_STATES, TARGET_BANDS, classify_noise, classify_sensitive, stable_id
from lib.temporal_evidence import TemporalEvidence, best_temporal_evidence, year_in_target_range
from validate_item_level_candidate import classify_item_format, item_level_confidence


DEFAULT_TERMS = [
    "ghost",
    "apparition",
    "haunted",
    "phantom",
    "yowie",
    "yahoo",
    "hairy man",
    "wild man",
    "ape man",
    "giant man",
    "bunyip",
    "min min",
    "fisher's ghost",
    "white lady",
    "haunted gaol",
    "haunted jail",
    "haunted hotel",
    "haunted station",
    "local legend",
]


@dataclass
class GapDecision:
    target_gap_eligible: bool
    reason: str
    auxiliary_status: str
    temporal: TemporalEvidence
    term_hit_confidence: float
    item_level_confidence: float
    target_effective_weight: float
    reasons: list[str]
    item_format: str = ""
    item_format_confidence: float = 0.0
    target_date_basis: str = "none"


def controlled_terms(config: dict[str, Any] | None = None) -> list[str]:
    config = config or {}
    terms = config.get("term_gate", {}).get("controlled_terms") or config.get("target_queries", {}).get("controlled_terms") or DEFAULT_TERMS
    return [str(term) for term in terms if str(term or "").strip()]


def target_localities(candidate: dict[str, Any], route: dict[str, Any] | None = None) -> list[str]:
    route = route or {}
    values = [
        candidate.get("target_locality"),
        candidate.get("locality_hint"),
        candidate.get("source_stated_place_text"),
        candidate.get("target_state"),
        route.get("state"),
    ]
    return [str(value) for value in values if str(value or "").strip()]


def term_hit(text: str, terms: list[str]) -> tuple[bool, float, str]:
    lower = (text or "").lower()
    for term in terms:
        if str(term).lower() in lower:
            return True, 1.0, term
    return False, 0.0, ""


def target_year_from_candidate(candidate: dict[str, Any]) -> int | None:
    for key in ["source_publication_year", "narrative_year", "inferred_year"]:
        value = candidate.get(key)
        try:
            year = int(value) if value not in {None, ""} else None
        except (TypeError, ValueError):
            year = None
        if year and year_in_target_range(year):
            return year
    return None


def classify_gap_candidate(
    candidate: dict[str, Any],
    route: dict[str, Any] | None,
    config: dict[str, Any] | None,
    page_text: str = "",
    metadata: dict[str, Any] | None = None,
) -> GapDecision:
    route = route or {}
    config = config or {}
    terms = controlled_terms(config)
    localities = target_localities(candidate, route)
    combined_text = " ".join(
        [
            str(candidate.get("title") or ""),
            str(candidate.get("snippet") or ""),
            str(candidate.get("date_published") or ""),
            str(candidate.get("url") or ""),
            page_text or "",
        ]
    )
    hit, term_conf, _term = term_hit(combined_text, terms)
    item_format, item_format_conf, format_reasons = classify_item_format(candidate, page_text, metadata)
    metadata_for_date = {
        **(metadata or {}),
        "title": candidate.get("title"),
        "description": candidate.get("snippet"),
        "item_format": item_format,
        "record_publication_year": candidate.get("record_publication_year"),
        "record_publication_date": candidate.get("record_publication_date_text"),
        "source_publication_year": candidate.get("source_publication_year"),
        "narrative_date_text": candidate.get("narrative_date_text"),
        "collection_coverage_date_text": candidate.get("collection_coverage_date_text"),
    }
    if item_format in {"SERIAL_ISSUE_ITEM", "PDF_ISSUE", "CATALOGUE_ITEM", "BROADCAST_ITEM", "ARCHIVE_FINDING_AID_ITEM", "ARTICLE_PAGE"}:
        metadata_for_date["date_is_record_publication"] = True
        metadata_for_date["date_published"] = candidate.get("date_published")
    temporal = best_temporal_evidence(
        combined_text,
        metadata_for_date,
        terms,
        localities,
    )
    item_conf, item_reasons = item_level_confidence(candidate, page_text, metadata)
    reasons: list[str] = []
    if candidate.get("source_tier") not in {"A", "B", "C"}:
        reasons.append("source_tier_not_abc")
    if candidate.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"} or route.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"}:
        reasons.append("discovery_or_sensitive_route")
    if not candidate.get("evidence_source_name"):
        reasons.append("missing_evidence_source_name")
    if not candidate.get("evidence_source_url"):
        reasons.append("missing_evidence_source_url")
    if not hit:
        reasons.append("missing_controlled_term")
    if temporal.confidence < float(config.get("temporal_gate", {}).get("min_date_confidence", 0.7)):
        reasons.append("missing_explicit_target_temporal_evidence")
    item_level_formats = {"CATALOGUE_ITEM", "SERIAL_ISSUE_ITEM", "ARTICLE_PAGE", "PDF_ISSUE", "BROADCAST_ITEM", "ARCHIVE_FINDING_AID_ITEM"}
    if item_conf < 0.7 and item_format not in item_level_formats:
        reasons.append("not_item_level:" + ",".join((item_reasons + format_reasons)[:3]))
    if candidate.get("ethics_status") in {"sensitive", "restricted", "manual_only"} or classify_sensitive(candidate, route) in {"sensitive", "restricted", "manual_only"}:
        reasons.append("sensitive_or_restricted")
    if candidate.get("duplicate_status") not in {"unique", "probably_unique", "unique_or_probably_unique", "unchecked", "", None}:
        reasons.append("duplicate")
    noise = classify_noise(combined_text, config)
    if noise:
        reasons.append("noise:" + ",".join(noise))
    target_ok = not reasons
    if target_ok:
        weight = 1.0
        if candidate.get("target_state") in PRIORITY_STATES or route.get("state") in PRIORITY_STATES:
            weight += 0.25
        if candidate.get("time_band") in {"1955_1964", "1965_1976"}:
            weight += 0.25
        return GapDecision(True, "TARGET_GAP_EFFECTIVE", "", temporal, term_conf, item_conf, min(weight, 1.5), [], item_format, item_format_conf, temporal.target_date_basis)
    if "duplicate" in reasons or any(reason.startswith("noise:") for reason in reasons) or "sensitive_or_restricted" in reasons or "discovery_or_sensitive_route" in reasons:
        aux = "REJECTED_OR_HELD"
    elif "missing_explicit_target_temporal_evidence" in reasons:
        aux = "UNDATED_AUXILIARY"
    elif "missing_controlled_term" in reasons:
        aux = "GENERAL_SAFE_PROVISIONAL"
    elif any(reason.startswith("not_item_level") for reason in reasons):
        aux = "ROUTE_DISCOVERY_ONLY"
    else:
        aux = "PLACE_ONLY_AUXILIARY"
    return GapDecision(False, ";".join(reasons), aux, temporal, term_conf, item_conf, 0.0, reasons, item_format, item_format_conf, temporal.target_date_basis)


def gap_count(conn: sqlite3.Connection, run_id: str) -> tuple[int, float]:
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(target_effective_weight), 0) FROM provisional_records WHERE run_id=? AND target_gap_eligible=1",
        (run_id,),
    ).fetchone()
    return int(row[0] or 0), float(row[1] or 0.0)


def update_candidate_gap_fields(conn: sqlite3.Connection, candidate_id: str, decision: GapDecision) -> None:
    conn.execute(
        """
        UPDATE harvest_candidates
        SET temporal_evidence_type=?, source_publication_year=?, narrative_year=?,
            coverage_start_year=?, coverage_end_year=?, date_confidence=?,
            term_hit_confidence=?, item_level_confidence=?, target_gap_candidate=?,
            item_format=?, item_format_confidence=?, record_publication_year=?,
            record_publication_date_text=?, narrative_date_text=?,
            collection_coverage_date_text=?, target_date_basis=?
        WHERE candidate_id=?
        """,
        (
            decision.temporal.evidence_type,
            decision.temporal.extracted_year if decision.temporal.evidence_type == "source_publication_year" else None,
            decision.temporal.extracted_year if decision.temporal.evidence_type in {"narrative_year", "decade_near_term"} else None,
            decision.temporal.coverage_start_year,
            decision.temporal.coverage_end_year,
            decision.temporal.confidence,
            decision.term_hit_confidence,
            decision.item_level_confidence,
            1 if decision.target_gap_eligible else 0,
            decision.item_format,
            decision.item_format_confidence,
            decision.temporal.extracted_year if decision.target_date_basis == "record_publication_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "record_publication_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "narrative_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "collection_coverage_date" else None,
            decision.target_date_basis,
            candidate_id,
        ),
    )


def update_provisional_gap_fields(conn: sqlite3.Connection, candidate_id: str, decision: GapDecision, harvest_mode: str = "gap_targeted") -> None:
    conn.execute(
        """
        UPDATE provisional_records
        SET harvest_mode=?, target_gap_eligible=?, target_gap_reason=?, temporal_evidence_type=?,
            source_publication_year=?, narrative_year=?, coverage_start_year=?, coverage_end_year=?,
            date_confidence=?, term_hit_confidence=?, item_level_confidence=?,
            auxiliary_status=?, target_effective_weight=?,
            item_format=?, item_format_confidence=?, record_publication_year=?,
            record_publication_date_text=?, narrative_date_text=?,
            collection_coverage_date_text=?, target_date_basis=?
        WHERE candidate_id=?
        """,
        (
            harvest_mode,
            1 if decision.target_gap_eligible else 0,
            decision.reason,
            decision.temporal.evidence_type,
            decision.temporal.extracted_year if decision.temporal.evidence_type == "source_publication_year" else None,
            decision.temporal.extracted_year if decision.temporal.evidence_type in {"narrative_year", "decade_near_term"} else None,
            decision.temporal.coverage_start_year,
            decision.temporal.coverage_end_year,
            decision.temporal.confidence,
            decision.term_hit_confidence,
            decision.item_level_confidence,
            decision.auxiliary_status,
            decision.target_effective_weight,
            decision.item_format,
            decision.item_format_confidence,
            decision.temporal.extracted_year if decision.target_date_basis == "record_publication_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "record_publication_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "narrative_date" else None,
            decision.temporal.evidence_text if decision.target_date_basis == "collection_coverage_date" else None,
            decision.target_date_basis,
            candidate_id,
        ),
    )


def insert_temporal_evidence(conn: sqlite3.Connection, run_id: str, candidate_id: str, provisional_record_id: str | None, decision: GapDecision, source_url: str) -> None:
    if not decision.temporal.evidence_type:
        return
    raw = "|".join([run_id, candidate_id, decision.temporal.evidence_type, decision.temporal.evidence_text, source_url])
    temporal_id = "te_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    conn.execute(
        """
        INSERT OR REPLACE INTO harvest_temporal_evidence (
            temporal_evidence_id, run_id, candidate_id, provisional_record_id, evidence_type,
            evidence_text, extracted_year, coverage_start_year, coverage_end_year,
            term_nearby, locality_nearby, source_url, confidence, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            temporal_id,
            run_id,
            candidate_id,
            provisional_record_id,
            decision.temporal.evidence_type,
            decision.temporal.evidence_text,
            decision.temporal.extracted_year,
            decision.temporal.coverage_start_year,
            decision.temporal.coverage_end_year,
            decision.temporal.term_nearby,
            decision.temporal.locality_nearby,
            source_url,
            decision.temporal.confidence,
            now_iso(),
        ),
    )


def provisional_id_for_candidate(candidate: dict[str, Any]) -> str:
    return stable_id("prov_", candidate.get("candidate_id"), candidate.get("url"))


def decision_json(decision: GapDecision) -> str:
    return json.dumps(
        {
            "target_gap_eligible": decision.target_gap_eligible,
            "reason": decision.reason,
            "auxiliary_status": decision.auxiliary_status,
            "temporal": decision.temporal.as_dict(),
            "term_hit_confidence": decision.term_hit_confidence,
            "item_level_confidence": decision.item_level_confidence,
            "target_effective_weight": decision.target_effective_weight,
            "reasons": decision.reasons,
            "item_format": decision.item_format,
            "item_format_confidence": decision.item_format_confidence,
            "target_date_basis": decision.target_date_basis,
        },
        sort_keys=True,
    )
