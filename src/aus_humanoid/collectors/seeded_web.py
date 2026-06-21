"""Seeded public-web collector for strict-geography V2 candidates.

This collector is intentionally conservative. It is for public URLs that have
already been selected as plausible research sources, not broad web crawling.
Rows are accepted only when they provide all card fields, locality coordinates,
and enough fetched or pre-reviewed public text to verify the source label and
place relationship.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import requests
import yaml
from bs4 import BeautifulSoup

from aus_humanoid.normalise import canonicalise_whitespace, normalise_alias
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso

from .base import BaseCollector, USER_AGENT, neutral_summary
from .models import CollectionCandidate


TEXT_MINIMUM_CHARS = 240


def load_seed_rows(path: Path) -> list[dict[str, Any]]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("seeds", [])
    if not isinstance(rows, list):
        raise ValueError(f"Seed file must contain a list under `seeds`: {path}")
    return [dict(row) for row in rows]


def host_key(url: str) -> str:
    parts = urlsplit(url)
    host = parts.netloc.lower().replace("www.", "") or "unknown-host"
    path_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return f"{host}-{path_hash}"


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    return canonicalise_whitespace(soup.get_text(" "))


def fetch_public_text(url: str, cache_path: Path) -> tuple[str, str]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        text = cache_path.read_text(encoding="utf-8", errors="replace")
        return text, "cache"
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/plain;q=0.9,*/*;q=0.2"},
        timeout=35,
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" in content_type.lower():
        text = html_to_text(response.text)
    else:
        text = canonicalise_whitespace(response.text)
    cache_path.write_text(text, encoding="utf-8")
    return text, "network"


def term_present(term: str, text: str) -> bool:
    normalized_term = normalise_alias(term)
    normalized_text = normalise_alias(text)
    if not normalized_term:
        return False
    return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text) is not None


def any_term_present(terms: list[str], text: str) -> bool:
    return any(term_present(term, text) for term in terms if term)


def source_tier(row: dict[str, Any]) -> str:
    return canonicalise_whitespace(row.get("source_tier") or row.get("quality_class") or "C")


class SeededWebCollector(BaseCollector):
    """Collect a small, auditable seed list of public web sources."""

    source_name = "Seeded Public Web"
    source_type = "seeded_public_web"
    source_tier = "C"

    def __init__(self, run_id: str, seed_path: Path, delay_seconds: float = 1.0, limit: int = 50) -> None:
        super().__init__(run_id=run_id, delay_seconds=delay_seconds, limit=limit)
        self.seed_path = seed_path

    def collect(self) -> Iterable[CollectionCandidate]:
        cache_root = PROJECT_ROOT / "data" / "interim" / "collection_cache" / "seeded_web_v2"
        emitted = 0
        for row in load_seed_rows(self.seed_path):
            if emitted >= self.limit:
                break
            yield self._candidate_from_seed(row, cache_root)
            emitted += 1
            self.wait()

    def _candidate_from_seed(self, row: dict[str, Any], cache_root: Path) -> CollectionCandidate:
        url = canonicalise_whitespace(row.get("url"))
        title = canonicalise_whitespace(row.get("title") or row.get("title_hint") or url)
        if not url:
            return self._candidate(row, "rejected", "seed_missing_url", "")

        text = ""
        fetch_status = "not_attempted"
        if row.get("manual_public_text_excerpt"):
            text = canonicalise_whitespace(row["manual_public_text_excerpt"])
            fetch_status = "manual_public_excerpt"
        else:
            try:
                text, fetch_status = fetch_public_text(url, cache_root / f"{host_key(url)}.txt")
            except Exception as exc:
                return self._candidate(row, "lead_only", f"public_text_fetch_failed:{exc}", "")

        if len(text) < TEXT_MINIMUM_CHARS and not row.get("allow_short_public_text"):
            return self._candidate(row, "lead_only", "public_text_too_short_for_acceptance", text)

        expected_terms = list(row.get("expected_terms") or [])
        source_label = canonicalise_whitespace(row.get("source_label"))
        if source_label and source_label not in expected_terms:
            expected_terms.append(source_label)
        if expected_terms and not any_term_present(expected_terms, text):
            return self._candidate(row, "lead_only", "expected_source_label_not_found_in_public_text", text)

        place_terms = [canonicalise_whitespace(row.get("location_text"))]
        place_terms.extend(row.get("location_aliases") or [])
        if place_terms and not any_term_present(place_terms, text):
            return self._candidate(row, "lead_only", "expected_place_not_found_in_public_text", text)

        evidence_summary = canonicalise_whitespace(row.get("evidence_summary")) or neutral_summary(
            "The public source describes or promotes a place-linked supernatural humanoid narrative.",
            text[:520],
            limit=520,
        )
        row = {**row, "evidence_summary": evidence_summary, "fetch_status": fetch_status}
        return self._candidate(row, "accepted", "", text)

    def _candidate(self, row: dict[str, Any], status: str, reason: str, text: str) -> CollectionCandidate:
        now = utc_now_iso()
        source_name = canonicalise_whitespace(row.get("source_name") or row.get("publication_or_organisation") or self.source_name)
        source_type = canonicalise_whitespace(row.get("source_type") or self.source_type)
        title = canonicalise_whitespace(row.get("title") or row.get("title_hint") or row.get("url") or "Seeded public web lead")
        url = canonicalise_whitespace(row.get("url"))
        quality_class = canonicalise_whitespace(row.get("quality_class") or source_tier(row))
        raw = {
            "seed": row,
            "seed_file": str(self.seed_path),
            "collector": "SeededWebCollector",
            "fetch_status": row.get("fetch_status") or "not_fetched",
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest() if text else "",
            "generated_at": now,
        }
        return CollectionCandidate(
            run_id=self.run_id,
            candidate_status=status,
            source_name=source_name,
            source_type=source_type,
            source_tier=canonicalise_whitespace(row.get("source_tier") or quality_class or self.source_tier),
            title=title,
            publication_or_organisation=canonicalise_whitespace(row.get("publication_or_organisation") or source_name),
            publication_date_text=canonicalise_whitespace(row.get("publication_date_text") or "undated public page"),
            url=url,
            canonical_url=url,
            external_id=canonicalise_whitespace(row.get("external_id") or ""),
            narrative_type=canonicalise_whitespace(row.get("narrative_type") or "local_legend"),
            secondary_role=canonicalise_whitespace(row.get("secondary_role") or "heritage_discourse"),
            australian_relation=canonicalise_whitespace(row.get("australian_relation") or "Australian public source and place association"),
            humanoid_basis=canonicalise_whitespace(row.get("humanoid_basis") or "human-like apparition or humanoid narrative"),
            source_label=canonicalise_whitespace(row.get("source_label") or row.get("label") or "unclassified public humanoid narrative"),
            location_text=canonicalise_whitespace(row.get("location_text") or ""),
            location_role=canonicalise_whitespace(row.get("location_role") or "legend_associated_place"),
            ethics_review_status=canonicalise_whitespace(row.get("ethics_review_status") or "ok_public"),
            cultural_sensitivity=canonicalise_whitespace(row.get("cultural_sensitivity") or "low"),
            acceptance_decision="accepted" if status == "accepted" else "not_accepted",
            rejection_reason=reason,
            evidence_summary=canonicalise_whitespace(row.get("evidence_summary")) or neutral_summary(text[:520], limit=520),
            access_date=canonicalise_whitespace(row.get("access_date") or now[:10]),
            publicness_status=canonicalise_whitespace(row.get("publicness_status") or "public_page"),
            rights_access_status=canonicalise_whitespace(row.get("rights_access_status") or "public web page; no full reproduction asserted"),
            latitude=float(row["latitude"]) if row.get("latitude") not in (None, "") else None,
            longitude=float(row["longitude"]) if row.get("longitude") not in (None, "") else None,
            location_precision=canonicalise_whitespace(row.get("location_precision") or "named_feature"),
            geocode_source=canonicalise_whitespace(row.get("geocode_source") or "seeded_manual_public_source_coordinate"),
            geocode_verification_status=canonicalise_whitespace(row.get("geocode_verification_status") or "verified_gazetteer_point"),
            coordinate_evidence_note=canonicalise_whitespace(row.get("coordinate_evidence_note") or ""),
            duplicate_check_status=canonicalise_whitespace(row.get("duplicate_check_status") or "canonical_url_checked"),
            quality_class=quality_class,
            raw_metadata_json=raw,
        )
