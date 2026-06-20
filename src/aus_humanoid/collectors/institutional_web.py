"""Public institutional/community-controlled web collector placeholder."""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseCollector
from .models import CollectionCandidate


class InstitutionalWebCollector(BaseCollector):
    source_name = "Institutional public web"
    source_type = "institutional_web"
    source_tier = "B"

    def collect(self) -> Iterable[CollectionCandidate]:
        return []

