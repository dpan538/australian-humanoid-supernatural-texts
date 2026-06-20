"""Reputable media V2 collector placeholder."""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseCollector
from .models import CollectionCandidate


class ReputableMediaCollector(BaseCollector):
    source_name = "Reputable public media"
    source_type = "reputable_media"
    source_tier = "C"

    def collect(self) -> Iterable[CollectionCandidate]:
        return []

