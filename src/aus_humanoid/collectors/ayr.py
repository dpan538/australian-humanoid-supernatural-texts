"""AYR V2 collector placeholder.

AYR remains a limited-use discovery/witness-publication source. It is not an
ontology authority and is capped in the V2 +500 target.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseCollector
from .models import CollectionCandidate


class AYRCollector(BaseCollector):
    source_name = "Australian Yowie Research"
    source_type = "ayr_public_web"
    source_tier = "E"

    def collect(self) -> Iterable[CollectionCandidate]:
        return []

