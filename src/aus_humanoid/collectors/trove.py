"""Trove V2 collector placeholder.

Without a TROVE_API_KEY this collector stages reproducible public query leads
only. Leads are not counted as accepted source items until article-level content
is verified.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import quote_plus

from .base import BaseCollector, neutral_summary
from .models import CollectionCandidate


class TroveCollector(BaseCollector):
    source_name = "Trove"
    source_type = "trove_public_search"
    source_tier = "A"

    queries = [
        ('"Yahoo-devil devil"', "Yahoo"),
        ('"Hairy Man of the Wood"', "Hairy Man"),
        ('"Australian gorilla"', "Australian gorilla"),
        ('"Australian ape" yowie', "Australian ape"),
        ('"Yara-ma-yha-who"', "Yara-ma-yha-who"),
        ('Quinkan Queensland', "Quinkan"),
        ('Nargun Gippsland', "Nargun"),
        ('Mimih Arnhem', "Mimih"),
        ('Pangkarlangu Warlpiri', "Pangkarlangu"),
    ]

    def collect(self) -> Iterable[CollectionCandidate]:
        has_key = bool(os.environ.get("TROVE_API_KEY"))
        for query, label in self.queries[: self.limit]:
            url = "https://trove.nla.gov.au/search/category/newspapers?keyword=" + quote_plus(query)
            yield CollectionCandidate(
                run_id=self.run_id,
                candidate_status="lead_only",
                source_name=self.source_name,
                source_type=self.source_type,
                source_tier=self.source_tier,
                title=f"Trove public query: {query}",
                publication_or_organisation="National Library of Australia / Trove",
                publication_date_text="",
                url=url,
                canonical_url=url,
                external_id=f"trove-query:{quote_plus(query)}",
                narrative_type="",
                secondary_role="unresolved_lead",
                australian_relation="query_targets_australian_public_sources",
                humanoid_basis="query_label_requires_article_verification",
                source_label=label,
                location_text="",
                location_role="uncertain_or_broad_location",
                ethics_review_status="not_yet_reviewed",
                cultural_sensitivity="medium",
                acceptance_decision="not_accepted",
                rejection_reason="Trove API key not available; article-level content not verified" if not has_key else "API collection not implemented in this safe batch",
                evidence_summary=neutral_summary("Generated a reproducible Trove query URL.", "This remains a lead until a stable article item and text are inspected."),
                raw_metadata_json={"query": query, "has_trove_api_key": has_key},
            )

