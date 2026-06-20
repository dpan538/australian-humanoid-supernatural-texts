"""Internet Archive V2 collector placeholder.

Accepted V2 use requires inspecting the actual public item/text. Metadata-only
matches remain source pointers.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseCollector
from .models import CollectionCandidate


class InternetArchiveCollector(BaseCollector):
    source_name = "Internet Archive"
    source_type = "internet_archive_public_text"
    source_tier = "A"

    def collect(self) -> Iterable[CollectionCandidate]:
        return []

