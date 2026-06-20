"""NLA V2 collector placeholder for public digitized/catalogue items.

NLA catalogue metadata is staged as a pointer until a public source text is
verified. It must not count toward the accepted +500 target by itself.
"""

from __future__ import annotations

from collections.abc import Iterable

from .base import BaseCollector
from .models import CollectionCandidate


class NLACollector(BaseCollector):
    source_name = "National Library of Australia"
    source_type = "nla_public"
    source_tier = "A"

    def collect(self) -> Iterable[CollectionCandidate]:
        return []

