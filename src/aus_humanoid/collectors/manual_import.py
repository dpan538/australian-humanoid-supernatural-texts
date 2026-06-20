"""Manual-import V2 collector helpers.

This module documents the accepted candidate shape for manually verified public
items. The actual CSV import is handled by scripts/collect_v2_batch.py.
"""

from __future__ import annotations

REQUIRED_MANUAL_COLUMNS = [
    "source_name",
    "source_type",
    "source_tier",
    "title",
    "publication_or_organisation",
    "publication_date_text",
    "url",
    "external_id",
    "narrative_type",
    "secondary_role",
    "australian_relation",
    "humanoid_basis",
    "source_label",
    "location_text",
    "location_role",
    "ethics_review_status",
    "cultural_sensitivity",
    "evidence_summary",
]

