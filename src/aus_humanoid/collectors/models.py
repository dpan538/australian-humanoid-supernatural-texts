"""Typed candidate models for V2 collectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CollectionCandidate:
    run_id: str
    candidate_status: str
    source_name: str
    source_type: str
    source_tier: str
    title: str
    publication_or_organisation: str
    publication_date_text: str
    url: str
    canonical_url: str
    external_id: str
    narrative_type: str
    secondary_role: str
    australian_relation: str
    humanoid_basis: str
    source_label: str
    location_text: str
    location_role: str
    ethics_review_status: str
    cultural_sensitivity: str
    acceptance_decision: str
    rejection_reason: str
    evidence_summary: str
    latitude: float | None = None
    longitude: float | None = None
    location_precision: str = ""
    geocode_source: str = ""
    geocode_verification_status: str = ""
    coordinate_evidence_note: str = ""
    duplicate_check_status: str = ""
    quality_class: str = ""
    raw_metadata_json: dict[str, Any] = field(default_factory=dict)

    def as_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["raw_metadata_json"] = self.raw_metadata_json
        return row
