"""Internet Archive V2 collector.

Search hits are not accepted as records by themselves. A candidate must expose
public OCR/text and contain a relevant source label in that text. Candidates
with a verified gazetteer place are eligible for the strict map layer; candidates
with public text but incomplete geography are accepted only for dashboard/density
review surfaces, not for the map.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

from aus_humanoid.geo import GAZETTEER
from aus_humanoid.normalise import canonicalise_whitespace, normalise_alias
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso

from .base import BaseCollector, USER_AGENT, neutral_summary
from .models import CollectionCandidate


SEARCH_SPECS: tuple[dict[str, str], ...] = (
    # Non-Yowie and low-coverage regions first. These are public-text probes,
    # not ontology assertions or claims of supernatural truth.
    {"label": "Nargun", "query": '"Nargun" AND (Gippsland OR Victoria OR Australia)', "sensitivity": "high", "fallback_place": "Gippsland", "fallback_state": "VIC"},
    {"label": "Puttikan", "query": '"Puttikan" AND (Victoria OR Australia)', "sensitivity": "high", "fallback_place": "Victoria", "fallback_state": "VIC"},
    {"label": "Mimih", "query": '("Mimih" OR "Mimi spirits") AND ("Northern Territory" OR Arnhem OR Australia)', "sensitivity": "high", "fallback_place": "Northern Territory", "fallback_state": "NT"},
    {"label": "Garkain", "query": '"Garkain" AND (Arnhem OR "Northern Territory" OR Australia)', "sensitivity": "high", "fallback_place": "Arnhem Land", "fallback_state": "NT"},
    {"label": "Mokoi", "query": '"Mokoi" AND (Arnhem OR "Northern Territory" OR Australia)', "sensitivity": "high", "fallback_place": "Northern Territory", "fallback_state": "NT"},
    {"label": "Pangkarlangu", "query": '"Pangkarlangu" AND (Warlpiri OR "Northern Territory" OR Australia)', "sensitivity": "high", "fallback_place": "Northern Territory", "fallback_state": "NT"},
    {"label": "Mamu", "query": '"Mamu" AND (Anangu OR Pitjantjatjara OR spirit OR Australia)', "sensitivity": "high", "fallback_place": "Central Australia", "fallback_state": "AU"},
    {"label": "Wandjina", "query": '("Wandjina" OR "Wanjina") AND ("Western Australia" OR Kimberley OR Australia)', "sensitivity": "high", "fallback_place": "Kimberley", "fallback_state": "WA"},
    {"label": "Quinkan", "query": '("Quinkan" OR "Quinkin") AND (Laura OR "Cape York" OR Queensland OR Australia)', "sensitivity": "high", "fallback_place": "Laura", "fallback_state": "QLD"},
    {"label": "Yaroma", "query": '"Yaroma" AND (Queensland OR Australia)', "sensitivity": "high", "fallback_place": "Queensland", "fallback_state": "QLD"},
    {"label": "Yara-ma-yha-who", "query": '("Yara-ma-yha-who" OR "Yara ma yha who") AND Australia', "sensitivity": "high", "fallback_place": "Australia", "fallback_state": "AU"},
    {"label": "Tjangara", "query": '"Tjangara" AND (giant OR spirit OR Australia)', "sensitivity": "high", "fallback_place": "Australia", "fallback_state": "AU"},
    # Hairy-humanoid operational cluster remains, but it is no longer first.
    {"label": "Australian gorilla", "query": '"Australian gorilla"', "sensitivity": "low", "fallback_place": "Australia", "fallback_state": "AU"},
    {"label": "Hairy Man", "query": '"Hairy Man" AND Australia', "sensitivity": "medium", "fallback_place": "Australia", "fallback_state": "AU"},
    {"label": "Yahoo", "query": '"Yahoo" AND Australia AND Aboriginal', "sensitivity": "low", "fallback_place": "Australia", "fallback_state": "AU"},
    {"label": "Yowie", "query": '"Yowie" AND Australia', "sensitivity": "low", "fallback_place": "Australia", "fallback_state": "AU"},
)

NOISE_PATTERNS = (
    "cadbury",
    "chocolate",
    "toy",
    "yowie bay",
    "yahoo mail",
    "yahoo news",
    "mamu corporation",
    "hiv",
    "macaque",
    "anime",
    "fanfiction",
    "video game",
    "playstation",
    "ps2",
    "xbox",
    "nintendo",
    "tasmanian tiger 3",
    "witcher",
    "alien gods",
    "ufo",
    "extraterrestrial",
    "palenque",
    "church committee",
    "foreign leaders",
    "dublin core",
    "accessibility",
    "virtual museum",
    "museum on the web",
    "china mail",
)

NARRATIVE_BY_LABEL = {
    "yowie": "encounter_account",
    "yahoo": "descriptive_belief_record",
    "australian gorilla": "encounter_account",
    "hairy man": "local_legend",
    "quinkan": "traditional_narrative",
    "nargun": "traditional_narrative",
    "mimih": "spirit_person_narrative",
    "wandjina": "spirit_person_narrative",
    "pangkarlangu": "giant_or_ogre_narrative",
    "yara-ma-yha-who": "traditional_narrative",
    "garkain": "spirit_person_narrative",
    "mokoi": "spirit_person_narrative",
    "mamu": "spirit_person_narrative",
    "puttikan": "traditional_narrative",
    "yaroma": "giant_or_ogre_narrative",
    "tjangara": "giant_or_ogre_narrative",
}

BROAD_LOCATION_HINTS = {
    "arnhem land": ("Arnhem Land", "NT"),
    "northern territory": ("Northern Territory", "NT"),
    "central australia": ("Central Australia", "AU"),
    "kimberley": ("Kimberley", "WA"),
    "western australia": ("Western Australia", "WA"),
    "gippsland": ("Gippsland", "VIC"),
    "victoria": ("Victoria", "VIC"),
    "south australia": ("South Australia", "SA"),
    "tasmania": ("Tasmania", "TAS"),
    "cape york": ("Cape York Peninsula", "QLD"),
    "laura": ("Laura", "QLD"),
    "queensland": ("Queensland", "QLD"),
    "australia": ("Australia", "AU"),
}


def curl_json(url: str, cache_path: Path) -> dict[str, Any]:
    """Fetch JSON through curl and cache the response for reproducibility."""

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    result = subprocess.run(
        ["curl", "-L", "-sS", "-A", USER_AGENT, "--max-time", "35", url],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl failed for {url}")
    payload = json.loads(result.stdout)
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def curl_text(url: str, cache_path: Path) -> str:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="replace")
    result = subprocess.run(
        ["curl", "-L", "-sS", "-A", USER_AGENT, "--max-time", "45", url],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl failed for {url}")
    cache_path.write_text(result.stdout, encoding="utf-8")
    return result.stdout


def first_text_file(metadata: dict[str, Any]) -> dict[str, Any] | None:
    for item in metadata.get("files", []):
        name = str(item.get("name") or "")
        if not name.endswith(".txt"):
            continue
        if str(item.get("private") or "").lower() == "true":
            continue
        if name.endswith(("_meta.txt", "_files.xml")):
            continue
        return item
    return None


def has_noise(text: str) -> str:
    lowered = text.lower()
    for pattern in NOISE_PATTERNS:
        if re.search(rf"\b{re.escape(pattern)}\b", lowered):
            return pattern
    return ""


def source_label_present(label: str, text: str) -> bool:
    norm = normalise_alias(text)
    label_norm = normalise_alias(label)
    if label_norm in norm:
        return True
    if label_norm == "yara-ma-yha-who" and "yara ma yha who" in norm:
        return True
    if label_norm == "quinkan" and "quinkin" in norm:
        return True
    if label_norm == "wandjina" and "wanjina" in norm:
        return True
    return False


def sentence_evidence(label: str, text: str) -> str:
    compact = canonicalise_whitespace(text)
    pattern = re.compile(r"[^.?!]{0,180}" + re.escape(label.split()[0]) + r"[^.?!]{0,240}[.?!]?", re.I)
    match = pattern.search(compact)
    if match:
        return canonicalise_whitespace(match.group(0))[:520]
    return compact[:520]


def gazetteer_places() -> list[dict[str, Any]]:
    places: list[dict[str, Any]] = []
    for entry in GAZETTEER:
        if entry.latitude is None or entry.longitude is None:
            continue
        if entry.location_type not in {"town", "locality", "named_feature"}:
            continue
        for name in (entry.place_name, *entry.aliases):
            if not name:
                continue
            places.append(
                {
                    "name": name,
                    "place_name": entry.place_name,
                    "state": entry.state_territory or "",
                    "latitude": entry.latitude,
                    "longitude": entry.longitude,
                    "location_type": entry.location_type,
                    "source": entry.geocode_source,
                }
            )
    places.sort(key=lambda item: len(item["name"]), reverse=True)
    return places


def find_strict_place(text: str) -> dict[str, Any] | None:
    norm = normalise_alias(text)
    for place in gazetteer_places():
        name = normalise_alias(place["name"])
        if len(name) < 4:
            continue
        if re.search(rf"\b{re.escape(name)}\b", norm):
            return place
    return None


def find_broad_place(spec: dict[str, str], text: str) -> tuple[str, str]:
    norm = normalise_alias(text)
    for term, (place, state) in BROAD_LOCATION_HINTS.items():
        if re.search(rf"\b{re.escape(term)}\b", norm):
            return place, state
    return spec.get("fallback_place") or "Australia", spec.get("fallback_state") or "AU"


def metadata_value(metadata: dict[str, Any], doc: dict[str, Any], key: str) -> str:
    value = metadata.get("metadata", {}).get(key) or doc.get(key) or ""
    if isinstance(value, list):
        return canonicalise_whitespace(", ".join(str(v) for v in value))
    return canonicalise_whitespace(value)


class InternetArchiveCollector(BaseCollector):
    source_name = "Internet Archive"
    source_type = "internet_archive_public_text"
    source_tier = "A"

    def collect(self) -> Iterable[CollectionCandidate]:
        emitted = 0
        cache_root = PROJECT_ROOT / "data" / "interim" / "collection_cache" / "internet_archive_v2"
        for spec in SEARCH_SPECS:
            if emitted >= self.limit:
                break
            try:
                search = self._search(spec, cache_root)
            except Exception as exc:
                yield self._lead(spec, "", "", f"archive_search_failed:{exc}", {"query": spec["query"]})
                emitted += 1
                continue
            docs = search.get("response", {}).get("docs", []) if isinstance(search, dict) else []
            for doc in docs:
                if emitted >= self.limit:
                    break
                candidate = self._candidate_from_doc(spec, doc, cache_root)
                yield candidate
                emitted += 1
                self.wait()

    def _search(self, spec: dict[str, str], cache_root: Path) -> dict[str, Any]:
        search_url = (
            "https://archive.org/advancedsearch.php?"
            + "&".join(
                [
                    "q=" + quote_plus(f"({spec['query']}) AND mediatype:texts"),
                    "fl[]=identifier",
                    "fl[]=title",
                    "fl[]=date",
                    "fl[]=creator",
                    "fl[]=description",
                    "fl[]=publicdate",
                    "rows=25",
                    "output=json",
                ]
            )
        )
        cache_name = normalise_alias(spec["label"]).replace(" ", "_").replace("/", "_")
        return curl_json(search_url, cache_root / "search" / f"{cache_name}.json")

    def _candidate_from_doc(self, spec: dict[str, str], doc: dict[str, Any], cache_root: Path) -> CollectionCandidate:
        identifier = canonicalise_whitespace(doc.get("identifier"))
        title = canonicalise_whitespace(doc.get("title")) or identifier or f"Internet Archive lead: {spec['label']}"
        item_url = f"https://archive.org/details/{identifier}" if identifier else ""
        if not identifier:
            return self._lead(spec, title, item_url, "archive_identifier_missing", {"doc": doc})

        metadata_url = f"https://archive.org/metadata/{quote_plus(identifier)}"
        try:
            metadata = curl_json(metadata_url, cache_root / "metadata" / f"{identifier}.json")
        except Exception as exc:
            return self._lead(spec, title, item_url, f"archive_metadata_failed:{exc}", {"doc": doc})

        combined_meta = canonicalise_whitespace(
            " ".join(
                str(value)
                for value in [
                    title,
                    doc.get("description"),
                    metadata.get("metadata", {}).get("description"),
                    metadata.get("metadata", {}).get("subject"),
                ]
                if value
            )
        )
        noise = has_noise(combined_meta)
        if noise:
            return self._rejected(spec, title, item_url, f"noise:{noise}", {"doc": doc, "metadata_url": metadata_url})

        text_file = first_text_file(metadata)
        if text_file is None:
            return self._lead(spec, title, item_url, "public_text_or_ocr_not_available", {"doc": doc, "metadata_url": metadata_url})
        text_url = f"https://archive.org/download/{quote_plus(identifier)}/{quote_plus(str(text_file['name']))}"
        try:
            text = curl_text(text_url, cache_root / "text" / identifier / str(text_file["name"]))
        except Exception as exc:
            return self._lead(spec, title, item_url, f"archive_text_failed:{exc}", {"doc": doc, "text_file": text_file})

        evidence_blob = "\n".join([combined_meta, text[:300000]])
        if not source_label_present(spec["label"], evidence_blob):
            return self._rejected(spec, title, item_url, "source_label_not_found_in_public_text", {"doc": doc, "text_file": text_file})

        place = find_strict_place(evidence_blob)
        sensitivity = spec["sensitivity"]
        evidence = sentence_evidence(spec["label"], evidence_blob)
        label_key = normalise_alias(spec["label"])
        has_strict_place = place is not None
        broad_place, broad_state = find_broad_place(spec, evidence_blob)
        location_text = str(place["place_name"]) if has_strict_place else broad_place
        location_role = "narrative_setting" if has_strict_place else "uncertain_or_broad_location"
        location_precision = str(place["location_type"]) if has_strict_place else "broad_region"
        geocode_source = str(place["source"]) if has_strict_place else "internet_archive_public_text_broad_location_signal"
        verification_status = "verified_gazetteer_point" if has_strict_place else "needs_review"
        coordinate_note = (
            f"Matched gazetteer place `{place['place_name']}` in public text/metadata."
            if has_strict_place
            else f"Public text matched `{spec['label']}` but only broad location signal `{location_text}`; excluded from map until human geocoding review."
        )
        quality_class = "A" if has_strict_place else "D"
        ethics_status = "needs_human_ethics_review" if sensitivity == "high" else "ok_public"
        summary_intro = (
            f"The public Internet Archive text contains the source label `{spec['label']}` and the mapped place `{location_text}`."
            if has_strict_place
            else f"The public Internet Archive text contains the source label `{spec['label']}` and a broad Australian location signal `{location_text}`."
        )
        return CollectionCandidate(
            run_id=self.run_id,
            candidate_status="accepted",
            source_name=self.source_name,
            source_type=self.source_type,
            source_tier=self.source_tier,
            title=title,
            publication_or_organisation=metadata_value(metadata, doc, "creator") or "Internet Archive public text",
            publication_date_text=metadata_value(metadata, doc, "date") or metadata_value(metadata, doc, "publicdate") or "undated public item",
            access_date=utc_now_iso()[:10],
            url=item_url,
            canonical_url=item_url,
            external_id=f"internet_archive:{identifier}",
            publicness_status="public_full_text",
            rights_access_status="Internet Archive public item; short excerpt/neutral summary only in project export.",
            narrative_type=NARRATIVE_BY_LABEL.get(label_key, "descriptive_belief_record"),
            secondary_role="",
            australian_relation="source_text_contains_australian_place_signal",
            humanoid_basis="source_label_matched_public_text",
            source_label=spec["label"],
            location_text=location_text,
            location_role=location_role,
            latitude=float(place["latitude"]) if has_strict_place else None,
            longitude=float(place["longitude"]) if has_strict_place else None,
            location_precision=location_precision,
            geocode_source=geocode_source,
            geocode_verification_status=verification_status,
            coordinate_evidence_note=coordinate_note,
            duplicate_check_status="canonical_url_checked",
            quality_class=quality_class,
            ethics_review_status=ethics_status,
            cultural_sensitivity=sensitivity,
            acceptance_decision="accepted",
            rejection_reason="",
            evidence_summary=neutral_summary(
                summary_intro,
                evidence,
            ),
            raw_metadata_json={"doc": doc, "metadata_url": metadata_url, "text_file": text_file},
        )

    def _lead(self, spec: dict[str, str], title: str, url: str, reason: str, raw: dict[str, Any]) -> CollectionCandidate:
        return CollectionCandidate(
            run_id=self.run_id,
            candidate_status="lead_only",
            source_name=self.source_name,
            source_type=self.source_type,
            source_tier=self.source_tier,
            title=title or f"Internet Archive lead: {spec['label']}",
            publication_or_organisation="Internet Archive",
            publication_date_text="",
            url=url,
            canonical_url=url,
            external_id=f"ia-lead:{normalise_alias(title or spec['label']).replace(' ', '-')[:80]}",
            narrative_type="",
            secondary_role="unresolved_lead",
            australian_relation="requires_text_and_location_verification",
            humanoid_basis="source_label_search_hit_requires_verification",
            source_label=spec["label"],
            location_text="",
            location_role="uncertain_or_broad_location",
            ethics_review_status="not_yet_reviewed",
            cultural_sensitivity=spec.get("sensitivity", "medium"),
            acceptance_decision="not_accepted",
            rejection_reason=reason,
            evidence_summary=neutral_summary("Internet Archive item requires further review.", reason),
            raw_metadata_json=raw,
        )

    def _rejected(self, spec: dict[str, str], title: str, url: str, reason: str, raw: dict[str, Any]) -> CollectionCandidate:
        candidate = self._lead(spec, title, url, reason, raw)
        candidate.candidate_status = "rejected"
        candidate.secondary_role = "exclusion"
        return candidate
