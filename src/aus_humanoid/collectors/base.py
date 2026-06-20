"""Shared collector base classes and staging helpers."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import utc_now_iso

from .models import CollectionCandidate


USER_AGENT = "AustralianHumanoidPublicTexts/0.4 public research archive; no credentialed access"


class BaseCollector(ABC):
    """Small interface every V2 collector should implement."""

    source_name: str = ""
    source_type: str = ""
    source_tier: str = ""

    def __init__(self, run_id: str, delay_seconds: float = 1.0, limit: int = 50) -> None:
        self.run_id = run_id
        self.delay_seconds = delay_seconds
        self.limit = limit

    @abstractmethod
    def collect(self) -> Iterable[CollectionCandidate]:
        """Yield staged candidates. Collectors do not insert accepted rows directly."""

    def wait(self) -> None:
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)


def neutral_summary(*parts: str, limit: int = 420) -> str:
    text = canonicalise_whitespace(" ".join(part for part in parts if part))
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def candidate_json(candidate: CollectionCandidate) -> str:
    return json.dumps(candidate.as_row(), ensure_ascii=False, sort_keys=True)


def write_jsonl(path: Path, candidates: Iterable[CollectionCandidate]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            payload = candidate.as_row()
            payload["generated_at"] = utc_now_iso()
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count

