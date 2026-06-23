#!/usr/bin/env python3
"""Run a production-scale multi-route collection sprint.

Workers retrieve and classify into route-local staging files only. The main
process then deduplicates, stages through collection_candidates_v2, promotes
accepted candidates, updates verified map-queue locations, exports frontend
JSON, validates, and writes one sprint status report.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import utc_now_iso
from collect_v2_batch import insert_candidate
from promote_accepted_candidates import promote_candidates


CONFIG_PATH = ROOT / "config" / "collection_sprint.yml"
ROUTES_PATH = ROOT / "config" / "collection_routes.yml"
STATUS_MD = ROOT / "data" / "processed" / "v2" / "collection_sprint_status.md"
STATUS_JSON = ROOT / "data" / "processed" / "v2" / "collection_sprint_status.json"
STATE_JSON = ROOT / "data" / "processed" / "v2" / "collection_sprint_state.json"
FINAL_STATUS_MD = ROOT / "data" / "processed" / "v2" / "launch_collection_final_status.md"
FINAL_STATUS_JSON = ROOT / "data" / "processed" / "v2" / "launch_collection_final_status.json"
FRONTEND_DATA = ROOT / "public" / "data" / "frontend-data.json"
USER_AGENT = "AustralianHumanoidTexts/collection-sprint contact: local research"

CSV_FIELDS = [
    "candidate_status",
    "source_name",
    "source_type",
    "source_tier",
    "title",
    "publication_or_organisation",
    "publication_date_text",
    "access_date",
    "url",
    "canonical_url",
    "external_id",
    "publicness_status",
    "rights_access_status",
    "narrative_type",
    "secondary_role",
    "australian_relation",
    "humanoid_basis",
    "source_label",
    "location_text",
    "location_role",
    "latitude",
    "longitude",
    "location_precision",
    "geocode_source",
    "geocode_verification_status",
    "coordinate_evidence_note",
    "duplicate_check_status",
    "quality_class",
    "ethics_review_status",
    "cultural_sensitivity",
    "acceptance_decision",
    "rejection_reason",
    "evidence_summary",
]

PERSON_FORM_WORDS = {
    "spirit",
    "ghost",
    "being",
    "man",
    "men",
    "woman",
    "women",
    "person",
    "individual",
    "ancestor",
    "all-father",
    "giant",
    "fairy",
    "fairies",
    "witch",
    "wizard",
    "magician",
    "enchanter",
    "devil",
    "sprite",
}

CONTEXT_ONLY_WORDS = {
    "animal",
    "bird",
    "tree",
    "plant",
    "sun",
    "moon",
    "star",
    "flood",
    "waterhole",
    "ceremony",
    "totem",
}

IDIOMATIC_NON_SCOPE_PATTERNS = {
    "ghost of a chance",
    "white as a ghost",
    "spirit of adventure",
    "spirit of enterprise",
    "spirit of the age",
    "spirit of improvement",
    "spirit of inquiry",
    "devil of a",
    "poor devil",
}

FICTION_STRICT_SOURCE_TYPES = {"public_domain_ebook"}
FICTION_STRONG_PERSON_FORM_TERMS = {
    "apparition",
    "fairies",
    "fairy",
    "ghost",
    "ghosts",
    "haunted",
    "magician",
    "phantom",
    "spectral",
    "spectre",
    "supernatural",
    "witch",
    "wizard",
}
FICTION_SUPERNATURAL_SIGNALS = {
    "apparition",
    "dead",
    "evil spirit",
    "fairies",
    "fairy",
    "ghost",
    "ghosts",
    "haunted",
    "legend",
    "myth",
    "phantom",
    "spectral",
    "spectre",
    "spirit being",
    "supernatural",
    "witch",
    "wizard",
}

STATE_ALIASES = {
    "NSW": "New South Wales",
    "QLD": "Queensland",
    "VIC": "Victoria",
    "TAS": "Tasmania",
    "SA": "South Australia",
    "WA": "Western Australia",
    "NT": "Northern Territory",
    "ACT": "Australian Capital Territory",
}

ABC_SUPERNATURAL_RE = re.compile(
    r"\b(ghosts?|haunted|apparitions?|phantoms?|spectral|spectres?|spirits?|spooks?|"
    r"blue lady|white lady|grey lady|yowie|devil|supernatural|paranormal|ghostly|lost souls?|enraged spirits?)\b",
    re.I,
)

ABC_STRONG_NARRATIVE_RE = re.compile(
    r"\b(ghosts?|ghost stories?|ghost tours?|apparitions?|phantoms?|spectral|spectres?|spooks?|"
    r"resident ghost|blue lady|white lady|grey lady|yowie|most haunted|ghostly|lost souls?|enraged spirits?|"
    r"haunted by (?:a |an |the )?(?:notorious )?ex-convict|"
    r"haunted (?:house|houses|homestead|place|places|site|sites|gaol|jail|asylum|hospital|"
    r"hotel|theatre|cemetery|property|building|town|mansion))\b",
    re.I,
)

ABC_SKIP_RE = re.compile(
    r"\b(ghost writer|ghostwriter|ghost net|ghost nets|ghost gum|ghost gear|ghost town only|"
    r"ghost bat|ghost shark|ghost mushrooms?|ghost reef|ghost-like|ghost theatre|"
    r"ghost of workchoices|ghost of rudd|ghosts of social media|political parties|federal election|"
    r"qantas|science show|daleks|ghosts? of (?:the )?past|"
    r"snapchat|video game|film review|book review|passwords?|woodfires?|asthma|bioluminescence)\b",
    re.I,
)

GEOCODE_CACHE_PATH = ROOT / "data" / "interim" / "geocode_cache" / "collection_sprint_places_nominatim.json"
GEOCODE_LOCK = Lock()


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.block_tag = ""
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "sup", "table", "nav", "footer"}:
            self.skip_depth += 1
        if tag in {"p", "div", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "sup", "table", "nav", "footer"} and self.skip_depth:
            self.skip_depth -= 1
        if tag in {"p", "div", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        lines = []
        for raw in "".join(self.parts).splitlines():
            line = canonicalise_whitespace(raw)
            if line:
                lines.append(line)
        return "\n".join(lines)


@dataclass
class RouteResult:
    route_id: str
    family: str
    organisation: str
    source_name: str
    retrieval_method: str
    stage_csv: str
    stage_ndjson: str
    processed: int = 0
    fetched: int = 0
    accepted_provisional: int = 0
    context_provisional: int = 0
    suppressed: int = 0
    duplicates: int = 0
    rejected: int = 0
    lead_only: int = 0
    errors: int = 0
    map_candidates: int = 0
    runtime_seconds: float = 0.0
    stop_reason: str = ""
    route_phase: str = "probe"
    candidates: list[dict[str, Any]] = field(default_factory=list)
    map_updates: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    resume_cursor: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id,
            "family": self.family,
            "organisation": self.organisation,
            "source_name": self.source_name,
            "retrieval_method": self.retrieval_method,
            "stage_csv": self.stage_csv,
            "stage_ndjson": self.stage_ndjson,
            "processed": self.processed,
            "fetched": self.fetched,
            "accepted_provisional": self.accepted_provisional,
            "context_provisional": self.context_provisional,
            "suppressed": self.suppressed,
            "duplicates": self.duplicates,
            "rejected": self.rejected,
            "lead_only": self.lead_only,
            "errors": self.errors,
            "map_candidates": self.map_candidates,
            "runtime_seconds": round(self.runtime_seconds, 1),
            "acceptance_rate": round(self.accepted_provisional / self.processed, 4) if self.processed else 0,
            "stop_reason": self.stop_reason,
            "route_phase": self.route_phase,
            "notes": self.notes,
            "resume_cursor": self.resume_cursor,
        }


def http_get(url: str, timeout: int = 30) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_text(url: str) -> str:
    raw = http_get(url)
    if url.endswith(".gz"):
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "ignore")
    if "<html" in text[:2000].lower() or "</" in text[:5000]:
        parser = VisibleTextParser()
        parser.feed(text)
        return parser.text()
    return text


def load_geocode_cache() -> dict[str, Any]:
    if GEOCODE_CACHE_PATH.exists():
        try:
            return json.loads(GEOCODE_CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def write_geocode_cache(cache: dict[str, Any]) -> None:
    GEOCODE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def split_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for raw in re.split(r"\n{1,}|\r{1,}", text):
        block = canonicalise_whitespace(raw)
        if len(block) < 90:
            continue
        if len(block) > 1100:
            for sentence_group in re.split(r"(?<=[.!?])\s+", block):
                sentence_group = canonicalise_whitespace(sentence_group)
                if len(sentence_group) >= 90:
                    blocks.append(sentence_group)
        else:
            blocks.append(block)
    return blocks


def term_windows(text: str, terms: list[str], window: int = 360) -> list[str]:
    compact = canonicalise_whitespace(text)
    windows: list[str] = []
    used_spans: list[tuple[int, int]] = []
    for term in terms:
        for match in re.finditer(re.escape(term), compact, flags=re.IGNORECASE):
            start = max(0, match.start() - window)
            end = min(len(compact), match.end() + window)
            if any(abs(start - old_start) < 120 and abs(end - old_end) < 120 for old_start, old_end in used_spans):
                continue
            used_spans.append((start, end))
            snippet = compact[start:end]
            if len(snippet) >= 90:
                windows.append(snippet)
    return windows


def contains_term(text: str, term: str) -> bool:
    term = canonicalise_whitespace(term)
    if not term:
        return False
    escaped = re.escape(term)
    if term[0].isalnum() and term[-1].isalnum():
        escaped = rf"\b{escaped}\b"
    return re.search(escaped, text, flags=re.IGNORECASE) is not None


def slug(value: str, max_len: int = 60) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", canonicalise_whitespace(value).lower()).strip("-")
    return cleaned[:max_len].strip("-") or "item"


def short_excerpt(text: str, limit: int = 640) -> str:
    text = canonicalise_whitespace(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "."


def apply_text_boundaries(text: str, page: dict[str, Any]) -> str:
    start_marker = page.get("start_marker")
    end_marker = page.get("end_marker")
    if start_marker:
        start = text.lower().find(str(start_marker).lower())
        if start >= 0:
            text = text[start:]
    if end_marker:
        end = text.lower().find(str(end_marker).lower())
        if end > 0:
            text = text[:end]
    return text


def classify_block(term: str, block: str, route: dict[str, Any]) -> tuple[str, str, str, str]:
    lower = block.lower()
    term_lower = term.lower()
    is_strict_fiction = route.get("source_type") in FICTION_STRICT_SOURCE_TYPES or route.get("ethics_review_status") == "public_fiction_reviewed"
    if any(pattern in lower for pattern in IDIOMATIC_NON_SCOPE_PATTERNS) and not any(
        signal in lower for signal in {"apparition", "haunted", "supernatural", "spook", "spectral"}
    ):
        return "rejected", "descriptive_belief_record", "idiomatic_or_non_scope_term_use", "insufficient_evidence"
    if is_strict_fiction:
        has_signal = any(signal in lower for signal in FICTION_SUPERNATURAL_SIGNALS)
        if term_lower in {"little man", "little woman", "little old man", "little old woman"} and not has_signal:
            return "rejected", "descriptive_belief_record", "ordinary_human_description_in_fiction", "insufficient_evidence"
        if term_lower in {"spirit", "spirits"} and not any(
            signal in lower
            for signal in {
                "apparition",
                "dead",
                "evil spirit",
                "ghost",
                "haunted",
                "spirit being",
                "spirit person",
                "supernatural",
                "witch",
                "wizard",
            }
        ):
            return "rejected", "descriptive_belief_record", "idiomatic_or_mood_spirit_in_fiction", "insufficient_evidence"
        if term_lower == "devil" and not any(
            signal in lower for signal in {"devil-devil", "evil spirit", "ghost", "phantom", "supernatural", "witch", "wizard"}
        ):
            return "rejected", "descriptive_belief_record", "idiomatic_or_expletive_devil_in_fiction", "insufficient_evidence"
        if term_lower == "giant" and not any(
            signal in lower for signal in {"fairy", "giant man", "giant-person", "legend", "myth", "ogre", "supernatural"}
        ):
            return "rejected", "descriptive_belief_record", "ordinary_or_metaphorical_giant_in_fiction", "insufficient_evidence"
        if term_lower in {"apparition", "phantom", "haunted"} and not any(
            signal in lower for signal in {"apparition", "ghost", "haunted house", "phantom", "spectral", "spectre", "supernatural"}
        ):
            return "rejected", "descriptive_belief_record", "non_supernatural_appearance_term_in_fiction", "insufficient_evidence"
    person_form = contains_term(block, term) and any(contains_term(block, word) for word in PERSON_FORM_WORDS)
    route_person_terms = {str(item).lower() for item in route.get("person_form_terms", [])}
    if term_lower in route_person_terms:
        person_form = True
    if term_lower in {"medicine man", "medicine-man", "magic man", "little old man", "little old woman"}:
        person_form = True
    if term_lower in {"fairy", "fairies", "witch", "wizard", "magician", "enchanter", "giant", "ghost", "ghosts", "apparition", "phantom", "water-sprite"}:
        person_form = True
    if is_strict_fiction and term_lower in {"little man", "little woman", "little old man", "little old woman"}:
        person_form = person_form and any(signal in lower for signal in FICTION_STRONG_PERSON_FORM_TERMS)
    if term_lower in {"spirit", "spirits", "devil"} and any(
        signal in lower for signal in {"dead", "ghost", "apparition", "supernatural", "being", "beings", "ancestor", "ancestral", "medicine", "wizard", "witch", "evil spirit", "devil-devil"}
    ):
        person_form = True
    if term_lower in {"byamee", "baiame", "wirreenun", "daramulun", "mullyan", "wurrunnah", "yhi"}:
        person_form = True
    if not person_form:
        if any(word in lower for word in CONTEXT_ONLY_WORDS):
            return "context", "descriptive_belief_record", "humanoid_adjacent_context", "context_only"
        return "rejected", "descriptive_belief_record", "insufficient_person_form_evidence", "insufficient_evidence"
    if "ghost" in lower:
        return "first_class", "apparition_account", "explicit_supernatural_or_anomalous_person_form_agent", "accepted"
    if "giant" in lower:
        return "first_class", "giant_or_ogre_narrative", "explicit_supernatural_or_anomalous_person_form_agent", "accepted"
    if any(word in lower for word in {"fairy", "fairies", "witch", "wizard", "magician", "enchanter"}):
        return "first_class", "retelling_or_adaptation", "explicit_supernatural_or_anomalous_person_form_agent", "accepted"
    if any(word in lower for word in {"medicine man", "medicine-man", "magic man"}):
        return "first_class", "descriptive_belief_record", "explicit_supernatural_or_anomalous_person_form_agent", "accepted"
    return "first_class", "spirit_person_narrative", "explicit_supernatural_or_anomalous_person_form_agent", "accepted"


def make_candidate(
    route: dict[str, Any],
    page: dict[str, Any],
    term: str,
    block: str,
    index: int,
    digest: str = "",
) -> dict[str, Any]:
    outcome, narrative_type, humanoid_basis, candidate_status = classify_block(term, block, route)
    if outcome == "first_class" and route.get("narrative_type_override"):
        narrative_type = str(route["narrative_type_override"])
    chapter = canonicalise_whitespace(page.get("chapter") or page.get("section_id") or "section")
    title = f"{canonicalise_whitespace(term)} in {chapter}"
    source_title = canonicalise_whitespace(route.get("source_title") or route.get("source_name"))
    if route.get("external_id_strategy") == "evidence_hash" and digest:
        external_suffix = digest[:16]
    else:
        external_suffix = f"{index:03d}"
    external_id = f"{slug(route['route_id'], 28)}:{slug(page.get('section_id') or page.get('url'), 28)}:{slug(term, 28)}:{external_suffix}"
    evidence = short_excerpt(block)
    return {
        "candidate_status": candidate_status if outcome == "first_class" else ("lead_only" if outcome == "context" else "rejected"),
        "source_name": route["source_name"],
        "source_type": route["source_type"],
        "source_tier": route["source_tier"],
        "title": title,
        "publication_or_organisation": f"{source_title}; {route.get('source_author', route['organisation'])}",
        "publication_date_text": str(route.get("publication_date_text") or ""),
        "access_date": date.today().isoformat(),
        "url": page["url"],
        "canonical_url": page["url"],
        "external_id": external_id,
        "publicness_status": "public_domain_public_web" if "public_domain" in route.get("source_type", "") else "public_text_item",
        "rights_access_status": "public_access_text_available",
        "narrative_type": narrative_type,
        "secondary_role": "source_grounded_section_record" if outcome == "first_class" else "context_only",
        "australian_relation": route.get("australian_relation", ""),
        "humanoid_basis": humanoid_basis,
        "source_label": canonicalise_whitespace(term),
        "location_text": page.get("location_text") or route.get("default_location_text", ""),
        "location_role": page.get("location_role") or route.get("default_location_role", "cultural_association_region"),
        "latitude": page.get("latitude", route.get("default_latitude", "")),
        "longitude": page.get("longitude", route.get("default_longitude", "")),
        "location_precision": page.get("location_precision") or route.get("default_location_precision") or ("region" if route.get("default_location_text") else ""),
        "geocode_source": page.get("geocode_source", route.get("default_geocode_source", "")),
        "geocode_verification_status": page.get("geocode_verification_status", route.get("default_geocode_verification_status", "")),
        "coordinate_evidence_note": page.get("coordinate_evidence_note", route.get("default_coordinate_evidence_note", "")),
        "duplicate_check_status": "source_url_external_id_and_excerpt_hash_checked",
        "quality_class": "B" if outcome == "first_class" else "reviewed_context",
        "ethics_review_status": route.get("ethics_review_status", "public_context_reviewed"),
        "cultural_sensitivity": route.get("cultural_sensitivity", "moderate"),
        "acceptance_decision": "accepted" if outcome == "first_class" else "not_accepted",
        "rejection_reason": "" if outcome == "first_class" else outcome,
        "evidence_summary": evidence,
    }


def existing_evidence_hashes_for_urls(urls: set[str]) -> set[str]:
    if not urls:
        return set()
    placeholders = ",".join("?" for _ in urls)
    hashes: set[str] = set()
    with connect(DEFAULT_DB_PATH) as conn:
        rows = conn.execute(
            f"""
            SELECT raw_metadata_json
            FROM collection_candidates_v2
            WHERE canonical_url IN ({placeholders})
            """,
            tuple(sorted(urls)),
        ).fetchall()
    for row in rows:
        raw = row["raw_metadata_json"]
        if not raw:
            continue
        try:
            metadata = json.loads(raw)
        except json.JSONDecodeError:
            continue
        digest = metadata.get("evidence_sha256")
        if digest:
            hashes.add(str(digest))
    return hashes


def print_route_progress(result: RouteResult, started_at: float) -> None:
    elapsed = time.monotonic() - started_at
    rate = result.accepted_provisional / result.processed if result.processed else 0
    print(
        "[collection-sprint] "
        f"route_id={result.route_id} processed={result.processed} fetched={result.fetched} "
        f"accepted_provisional={result.accepted_provisional} context_provisional={result.context_provisional} "
        f"suppressed={result.suppressed} duplicates={result.duplicates} rejected={result.rejected} "
        f"errors={result.errors} elapsed={elapsed:.1f}s acceptance_rate={rate:.3f} "
        f"map_candidates={result.map_candidates}",
        flush=True,
    )


def fetch_archive_text(route: dict[str, Any]) -> tuple[str, str]:
    identifier = route["archive_identifier"]
    metadata_url = f"https://archive.org/metadata/{quote(identifier)}"
    metadata = json.loads(http_get(metadata_url).decode("utf-8", "ignore"))
    text_names: list[str] = []
    for file_row in metadata.get("files", []):
        name = str(file_row.get("name") or "")
        if name.endswith("_djvu.txt") and name not in text_names:
            text_names.append(name)
    for file_row in metadata.get("files", []):
        name = str(file_row.get("name") or "")
        if name.endswith("_hocr_searchtext.txt.gz") and name not in text_names:
            text_names.append(name)
    for file_row in metadata.get("files", []):
        name = str(file_row.get("name") or "")
        if name.endswith(".txt") and name not in text_names:
            text_names.append(name)
    if not text_names:
        raise RuntimeError(f"No public OCR text file found for {identifier}")
    errors: list[str] = []
    for text_name in text_names:
        text_url = f"https://archive.org/download/{quote(identifier)}/{quote(text_name)}"
        try:
            return text_url, fetch_text(text_url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{text_name}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"No readable public OCR text file found for {identifier}; attempts={'; '.join(errors[:4])}")


def collect_text_route(
    route: dict[str, Any],
    stage_dir: Path,
    scaled: bool,
    cursor: dict[str, Any] | None = None,
) -> RouteResult:
    started_at = time.monotonic()
    cursor = cursor or {}
    route_id = route["route_id"]
    max_candidates = int(route.get("max_candidates_scaled" if scaled else "max_candidates_probe") or 30)
    accepted_target = int(route.get("accepted_target") or 0)
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="scaled" if scaled else "probe",
    )
    pages = list(route.get("pages") or [])
    if route.get("archive_identifier"):
        if cursor.get("exhausted") and route.get("resume_strategy") != "rescan_new_evidence":
            result.stop_reason = "route_cursor_exhausted"
            result.resume_cursor = cursor
            write_route_stage(result)
            print_route_progress(result, started_at)
            return result
        text_url, text = fetch_archive_text(route)
        pages = [{"section_id": route["archive_identifier"], "url": text_url, "chapter": route.get("source_title", "full text"), "text": text}]
    existing_hashes: set[str] = set()
    if route.get("resume_strategy") == "rescan_new_evidence":
        existing_hashes = existing_evidence_hashes_for_urls({str(page.get("url") or "") for page in pages})
    seen_hashes: set[str] = set()
    term_hits: Counter[str] = Counter()
    term_hit_limit = int(route.get("term_hit_limit") or 4)
    required_place_terms = [str(term) for term in route.get("required_place_terms") or []]
    start_page_index = 0 if route.get("resume_strategy") == "rescan_new_evidence" else int(cursor.get("page_index") or 0)
    next_page_index = start_page_index
    try:
        for page_index, page in enumerate(pages[start_page_index:], start=start_page_index):
            if result.processed >= max_candidates:
                break
            next_page_index = page_index
            try:
                text = page.get("text") or fetch_text(page["url"])
                text = apply_text_boundaries(text, page)
                result.fetched += 1
            except Exception as exc:  # noqa: BLE001
                result.errors += 1
                result.notes.append(f"{page.get('url')}: {type(exc).__name__}: {exc}")
                continue
            blocks = split_blocks(text)
            blocks.extend(term_windows(text, list(route.get("entity_terms", []))))
            for block in blocks:
                lower = block.lower()
                matching_terms = [term for term in route.get("entity_terms", []) if contains_term(block, term)]
                if not matching_terms:
                    continue
                for term in matching_terms:
                    if result.processed >= max_candidates:
                        break
                    if accepted_target and result.accepted_provisional >= accepted_target:
                        break
                    if route.get("require_place_match_for_acceptance") and required_place_terms and not any(
                        contains_term(block, place_term) for place_term in required_place_terms
                    ):
                        continue
                    if term_hits[term.lower()] >= term_hit_limit:
                        continue
                    digest = hashlib.sha256(canonicalise_whitespace(block).lower().encode("utf-8")).hexdigest()
                    if digest in existing_hashes:
                        result.duplicates += 1
                        continue
                    if digest in seen_hashes:
                        result.duplicates += 1
                        continue
                    seen_hashes.add(digest)
                    term_hits[term.lower()] += 1
                    result.processed += 1
                    candidate = make_candidate(route, page, term, block, result.processed, digest)
                    candidate["raw_metadata_json"] = {
                        "route_id": route_id,
                        "source_family": route.get("family"),
                        "chapter": page.get("chapter"),
                        "section_id": page.get("section_id"),
                        "scope_classifier": "term_and_person_form_gate_v1",
                        "evidence_sha256": digest,
                    }
                    result.candidates.append(candidate)
                    if candidate["candidate_status"] == "accepted":
                        result.accepted_provisional += 1
                    elif candidate["candidate_status"] == "lead_only":
                        result.context_provisional += 1
                        result.lead_only += 1
                    else:
                        result.rejected += 1
                    if result.processed % 25 == 0:
                        print_route_progress(result, started_at)
                if accepted_target and result.accepted_provisional >= accepted_target:
                    break
            next_page_index = page_index + 1
        exhausted = next_page_index >= len(pages)
        result.resume_cursor = {
            "page_index": next_page_index,
            "total_pages": len(pages),
            "exhausted": exhausted,
            "updated_at": utc_now_iso(),
        }
        if route.get("archive_identifier"):
            result.resume_cursor["exhausted"] = True
        result.stop_reason = "accepted_target_reached" if accepted_target and result.accepted_provisional >= accepted_target else "route_candidate_limit_or_source_exhausted"
        if result.resume_cursor.get("exhausted") and not result.accepted_provisional:
            result.stop_reason = "route_cursor_exhausted"
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def html_to_visible_text(fragment: str) -> str:
    parser = VisibleTextParser()
    parser.feed(html.unescape(fragment))
    return parser.text()


def recollect_search_urls(route: dict[str, Any]) -> list[str]:
    base_url = route["base_url"].rstrip("/") + "/"
    urls: list[str] = []
    seen: set[str] = set()
    for url in route.get("item_urls") or []:
        absolute = urljoin(base_url, str(url))
        if absolute not in seen:
            seen.add(absolute)
            urls.append(absolute)
    search_path = str(route.get("search_path") or "nodes/search")
    max_items = int(route.get("max_search_items") or 80)
    for term in route.get("search_terms") or route.get("entity_terms") or []:
        if len(urls) >= max_items:
            break
        search_url = urljoin(base_url, search_path) + "?" + urlencode({"keywords": term})
        try:
            search_html = http_get(search_url).decode("utf-8", "ignore")
        except Exception:
            continue
        for href in re.findall(r'href=["\']([^"\']*?/nodes/view/\d+[^"\']*)["\']', search_html):
            absolute = urljoin(base_url, href.split("#", 1)[0])
            absolute = absolute.split("?", 1)[0]
            if absolute not in seen:
                seen.add(absolute)
                urls.append(absolute)
                if len(urls) >= max_items:
                    break
    return urls


def fetch_recollect_item_ocr(route: dict[str, Any], item_url: str) -> tuple[str, str, list[str]]:
    raw_html = http_get(item_url).decode("utf-8", "ignore")
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.IGNORECASE | re.DOTALL)
    title = canonicalise_whitespace(html.unescape(title_match.group(1))) if title_match else item_url.rsplit("/", 1)[-1]
    title = re.sub(r"\s*\|\s*.*$", "", title).strip() or item_url.rsplit("/", 1)[-1]
    asset_ids: list[str] = []
    for tag in re.findall(r"<img\b[^>]*>", raw_html, flags=re.IGNORECASE):
        if not re.search(r"\bhasOCR=[\"']?1[\"']?", tag, flags=re.IGNORECASE):
            continue
        match = re.search(r"\bidx=[\"']?(\d+)[\"']?", tag, flags=re.IGNORECASE)
        if match and match.group(1) not in asset_ids:
            asset_ids.append(match.group(1))
    max_assets = int(route.get("max_assets_per_item") or 12)
    texts: list[str] = []
    for asset_id in asset_ids[:max_assets]:
        text_url = urljoin(item_url, f"/nodes/gettxt/OCR/{asset_id}")
        try:
            fragment = http_get(text_url).decode("utf-8", "ignore")
        except Exception:
            continue
        text = html_to_visible_text(fragment)
        if text:
            texts.append(text)
        sleep_seconds = float(route.get("asset_rate_limit_seconds") or 0)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return title, "\n".join(texts), asset_ids


def collect_recollect_ocr_route(
    route: dict[str, Any],
    stage_dir: Path,
    scaled: bool,
    cursor: dict[str, Any] | None = None,
) -> RouteResult:
    started_at = time.monotonic()
    cursor = cursor or {}
    route_id = route["route_id"]
    max_candidates = int(route.get("max_candidates_scaled" if scaled else "max_candidates_probe") or 30)
    accepted_target = int(route.get("accepted_target") or 0)
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="scaled" if scaled else "probe",
    )
    try:
        if cursor.get("exhausted") and route.get("resume_strategy") != "rescan_new_evidence":
            result.stop_reason = "route_cursor_exhausted"
            result.resume_cursor = cursor
            return result
        item_urls = recollect_search_urls(route)
        max_runtime = float(route.get("max_runtime_seconds") or 600)
        print(
            "[collection-sprint] "
            f"route_id={route_id} recollect_discovered_items={len(item_urls)} "
            f"elapsed={time.monotonic() - started_at:.1f}s",
            flush=True,
        )
        start_item_index = 0 if route.get("resume_strategy") == "rescan_new_evidence" else int(cursor.get("item_index") or 0)
        existing_hashes = existing_evidence_hashes_for_urls(set(item_urls)) if route.get("resume_strategy") == "rescan_new_evidence" else set()
        seen_hashes: set[str] = set()
        next_item_index = start_item_index
        required_place_terms = [str(term) for term in route.get("required_place_terms") or []]
        for item_index, item_url in enumerate(item_urls[start_item_index:], start=start_item_index):
            if time.monotonic() - started_at > max_runtime:
                result.stop_reason = "route_runtime_limit_reached"
                break
            if result.processed >= max_candidates:
                break
            if accepted_target and result.accepted_provisional >= accepted_target:
                break
            next_item_index = item_index
            try:
                item_title, item_text, asset_ids = fetch_recollect_item_ocr(route, item_url)
                result.fetched += 1
            except Exception as exc:  # noqa: BLE001
                result.errors += 1
                result.notes.append(f"{item_url}: {type(exc).__name__}: {exc}")
                continue
            next_item_index = item_index + 1
            print(
                "[collection-sprint] "
                f"route_id={route_id} recollect_item_index={item_index + 1}/{len(item_urls)} "
                f"fetched={result.fetched} processed={result.processed} accepted_provisional={result.accepted_provisional} "
                f"map_candidates={result.map_candidates} elapsed={time.monotonic() - started_at:.1f}s",
                flush=True,
            )
            if not item_text or len(canonicalise_whitespace(item_text)) < 120:
                result.rejected += 1
                continue
            searchable_place_text = f"{item_title}\n{item_text}"
            place_matched = not required_place_terms or any(contains_term(searchable_place_text, term) for term in required_place_terms)
            if route.get("require_place_match_for_acceptance") and not place_matched:
                result.lead_only += 1
                continue
            page = {
                "section_id": item_url.rstrip("/").rsplit("/", 1)[-1],
                "url": item_url,
                "chapter": item_title,
            }
            if place_matched and route.get("default_location_text"):
                page.update(
                    {
                        "location_text": route.get("default_location_text"),
                        "location_role": route.get("default_location_role", "legend_associated_place"),
                        "latitude": route.get("default_latitude", ""),
                        "longitude": route.get("default_longitude", ""),
                        "location_precision": route.get("default_location_precision", "locality"),
                        "geocode_source": route.get("default_geocode_source", ""),
                        "geocode_verification_status": route.get("default_geocode_verification_status", ""),
                        "coordinate_evidence_note": route.get("default_coordinate_evidence_note", ""),
                    }
                )
            blocks = split_blocks(item_text)
            blocks.extend(term_windows(item_text, list(route.get("entity_terms", []))))
            for block in blocks:
                if result.processed >= max_candidates:
                    break
                if accepted_target and result.accepted_provisional >= accepted_target:
                    break
                matching_terms = [term for term in route.get("entity_terms", []) if contains_term(block, term)]
                if not matching_terms:
                    continue
                digest = hashlib.sha256(canonicalise_whitespace(f"{item_url}:{block}").lower().encode("utf-8")).hexdigest()
                if digest in existing_hashes or digest in seen_hashes:
                    result.duplicates += 1
                    continue
                seen_hashes.add(digest)
                term = matching_terms[0]
                result.processed += 1
                candidate = make_candidate(route, page, term, block, result.processed, digest)
                candidate["raw_metadata_json"] = {
                    "route_id": route_id,
                    "source_family": route.get("family"),
                    "item_title": item_title,
                    "item_url": item_url,
                    "asset_ids": asset_ids,
                    "scope_classifier": "recollect_ocr_term_and_person_form_gate_v1",
                    "evidence_sha256": digest,
                }
                result.candidates.append(candidate)
                if candidate["candidate_status"] == "accepted":
                    result.accepted_provisional += 1
                    if candidate.get("latitude") and candidate.get("longitude"):
                        result.map_candidates += 1
                elif candidate["candidate_status"] == "lead_only":
                    result.context_provisional += 1
                    result.lead_only += 1
                else:
                    result.rejected += 1
                if result.processed % 25 == 0:
                    print_route_progress(result, started_at)
        result.resume_cursor = {
            "item_index": next_item_index,
            "total_items": len(item_urls),
            "exhausted": next_item_index >= len(item_urls),
            "updated_at": utc_now_iso(),
        }
        if not result.stop_reason:
            result.stop_reason = "accepted_target_reached" if accepted_target and result.accepted_provisional >= accepted_target else "route_candidate_limit_or_source_exhausted"
        if result.resume_cursor.get("exhausted") and not result.accepted_provisional:
            result.stop_reason = "metadata_only_or_no_scope_ocr"
    except Exception as exc:  # noqa: BLE001
        result.errors += 1
        result.stop_reason = f"recollect_route_error:{type(exc).__name__}"
        result.notes.append(str(exc))
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def collect_probe_only(route: dict[str, Any], stage_dir: Path, cursor: dict[str, Any] | None = None) -> RouteResult:
    started_at = time.monotonic()
    route_id = route["route_id"]
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="probe",
    )
    try:
        if (cursor or {}).get("exhausted"):
            result.stop_reason = "route_cursor_exhausted"
            result.resume_cursor = cursor or {}
            return result
        url = route.get("search_url")
        if url:
            text = fetch_text(url)
            result.fetched = 1
            # Directory/search pages are discovery only unless item text is retrieved.
            for idx, block in enumerate(split_blocks(text)[: int(route.get("max_candidates_probe") or 30)], start=1):
                result.processed += 1
                if any(term in block.lower() for term in ("login", "subscribe", "permission denied")):
                    result.rejected += 1
                else:
                    result.lead_only += 1
                if result.processed % 25 == 0:
                    print_route_progress(result, started_at)
        result.stop_reason = "probe_directory_or_search_page_discovery_only"
        result.resume_cursor = {"exhausted": True, "updated_at": utc_now_iso()}
    except Exception as exc:  # noqa: BLE001
        result.errors += 1
        result.stop_reason = f"probe_error:{type(exc).__name__}"
        result.notes.append(str(exc))
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def abc_algolia_query(route: dict[str, Any], query: str, page: int) -> dict[str, Any]:
    app_id = str(route.get("algolia_app_id") or "Y63Q32NVDL")
    api_key = str(route.get("algolia_api_key") or "bcdf11ba901b780dc3c0a3ca677fbefc")
    index_name = str(route.get("algolia_index") or "ABC_production_all")
    hits_per_page = int(route.get("hits_per_page") or 20)
    params = urlencode(
        {
            "query": query,
            "hitsPerPage": hits_per_page,
            "page": page,
            "ruleContexts": '["global_search"]',
        }
    )
    request = Request(
        f"https://{app_id}-dsn.algolia.net/1/indexes/{index_name}/query",
        data=json.dumps({"params": params}).encode("utf-8"),
        headers={
            "X-Algolia-API-Key": api_key,
            "X-Algolia-Application-Id": app_id,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def abc_hit_text(hit: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("title", "synopsis", "caption", "transcript"):
        value = hit.get(key)
        if isinstance(value, str) and value:
            parts.append(value)
    keywords = hit.get("keywords") or []
    if isinstance(keywords, list):
        parts.extend(str(keyword) for keyword in keywords if keyword)
    return canonicalise_whitespace("\n".join(parts))


def abc_publication_date(hit: dict[str, Any]) -> str:
    dates = hit.get("dates") or {}
    for key in ("displayPublished", "published", "availableFrom"):
        value = dates.get(key)
        if value:
            return str(value)[:10]
    return ""


def place_aliases(place: dict[str, Any]) -> list[str]:
    aliases = [str(place.get("name") or "")]
    aliases.extend(str(alias) for alias in place.get("aliases") or [] if alias)
    return [alias for alias in aliases if alias]


def text_has_place(text: str, place: dict[str, Any]) -> str:
    for alias in place_aliases(place):
        if contains_term(text, alias):
            return alias
    return ""


def source_label_from_text(text: str) -> str:
    match = ABC_STRONG_NARRATIVE_RE.search(text) or ABC_SUPERNATURAL_RE.search(text)
    if not match:
        return "reported_ghost_or_apparition"
    value = canonicalise_whitespace(match.group(0)).lower()
    if value in {"haunted", "paranormal", "supernatural"}:
        return "reported_ghost_or_apparition"
    return value.replace(" ", "_")


def abc_evidence_window(text: str, place_alias: str, radius: int = 520) -> str:
    place_match = re.search(r"\b" + re.escape(place_alias) + r"\b", text, re.I)
    ghost_match = ABC_SUPERNATURAL_RE.search(text)
    if place_match and ghost_match:
        start = max(0, min(place_match.start(), ghost_match.start()) - radius)
        end = min(len(text), max(place_match.end(), ghost_match.end()) + radius)
        return short_excerpt(text[start:end], 760)
    if place_match:
        start = max(0, place_match.start() - radius)
        end = min(len(text), place_match.end() + radius)
        return short_excerpt(text[start:end], 760)
    return short_excerpt(text, 760)


def place_centered_evidence_window(text: str, place_alias: str, radius: int = 640) -> str:
    place_match = re.search(r"\b" + re.escape(place_alias) + r"\b", text, re.I)
    if not place_match:
        return short_excerpt(text, 760)
    ghost_matches = list(ABC_SUPERNATURAL_RE.finditer(text))
    nearest = min(ghost_matches, key=lambda match: abs(match.start() - place_match.start())) if ghost_matches else None
    if nearest and abs(nearest.start() - place_match.start()) <= radius * 2:
        start = max(0, min(place_match.start(), nearest.start()) - radius)
        end = min(len(text), max(place_match.end(), nearest.end()) + radius)
    else:
        start = max(0, place_match.start() - radius)
        end = min(len(text), place_match.end() + radius)
    return short_excerpt(text[start:end], 900)


def geocode_route_place(place: dict[str, Any], cache: dict[str, Any], sleep_seconds: float) -> dict[str, Any] | None:
    if place.get("latitude") and place.get("longitude"):
        return {
            "lat": place["latitude"],
            "lon": place["longitude"],
            "display_name": place.get("coordinate_evidence_note") or place.get("name"),
        }
    state = str(place.get("state") or "")
    if not state:
        return None
    query = str(place.get("query") or f"{place.get('name')}, {STATE_ALIASES.get(state, state)}, Australia")
    with GEOCODE_LOCK:
        if query in cache and not (isinstance(cache[query], dict) and cache[query].get("error")):
            rows = cache[query]
        else:
            url = "https://nominatim.openstreetmap.org/search?" + urlencode(
                {"q": query, "format": "jsonv2", "limit": "5", "addressdetails": "1", "countrycodes": "au"}
            )
            try:
                rows = json.loads(http_get(url).decode("utf-8", "ignore"))
            except Exception as exc:  # noqa: BLE001
                cache[query] = {"error": f"{type(exc).__name__}: {exc}", "updated_at": utc_now_iso()}
                write_geocode_cache(cache)
                return None
            cache[query] = rows
            write_geocode_cache(cache)
            if sleep_seconds:
                time.sleep(sleep_seconds)
    if not isinstance(rows, list):
        return None
    expected_state = STATE_ALIASES.get(state, state).lower()
    for row in rows:
        address = row.get("address") or {}
        display = canonicalise_whitespace(row.get("display_name") or "")
        state_values = {
            str(address.get(key) or "").lower()
            for key in ("state", "territory", "region", "ISO3166-2-lvl4")
        }
        if str(address.get("country_code") or "").lower() != "au":
            continue
        if expected_state not in state_values and expected_state not in display.lower() and f"au-{state.lower()}" not in state_values:
            continue
        try:
            float(row["lat"])
            float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        return row
    return None


def make_abc_candidate(
    route: dict[str, Any],
    hit: dict[str, Any],
    place: dict[str, Any],
    place_alias: str,
    geocode: dict[str, Any],
    evidence: str,
) -> dict[str, Any]:
    title = canonicalise_whitespace(hit.get("title") or hit.get("titleAlt", {}).get("lg") or "ABC public record")
    canonical_url = str(hit.get("canonicalURL") or "")
    hit_id = str(hit.get("id") or hit.get("objectID") or slug(title))
    external_id = f"abc:{slug(hit_id, 24)}:{slug(place.get('name') or place_alias, 24)}"
    program = canonicalise_whitespace(hit.get("programTitle") or hit.get("ABCSEARCH_programTitle") or "ABC")
    place_name = f"{canonicalise_whitespace(place.get('name') or place_alias)}, {place.get('state')}"
    display = canonicalise_whitespace(geocode.get("display_name") or "")
    return {
        "candidate_status": "accepted",
        "source_name": route["source_name"],
        "source_type": route["source_type"],
        "source_tier": route["source_tier"],
        "title": title,
        "publication_or_organisation": f"ABC; {program}",
        "publication_date_text": abc_publication_date(hit),
        "access_date": date.today().isoformat(),
        "url": canonical_url,
        "canonical_url": canonical_url,
        "external_id": external_id,
        "publicness_status": "public_media_page",
        "rights_access_status": "public_access_short_excerpt_only",
        "narrative_type": route.get("narrative_type_override") or "apparition_account",
        "secondary_role": "place_first_public_media_record",
        "australian_relation": route.get("australian_relation", "Australian ABC public media item with source-stated place evidence."),
        "humanoid_basis": "explicit_supernatural_or_anomalous_person_form_agent",
        "source_label": source_label_from_text(evidence),
        "location_text": place_name,
        "location_role": place.get("location_role") or route.get("default_location_role", "apparition_location"),
        "latitude": geocode["lat"],
        "longitude": geocode["lon"],
        "location_precision": place.get("location_type") or "locality",
        "geocode_source": "nominatim_openstreetmap_state_checked_abc_place_2026-06-22",
        "geocode_verification_status": "verified_gazetteer_point",
        "coordinate_evidence_note": (
            f"ABC text names `{place_alias}` in a ghost/supernatural context; "
            f"gazetteer result state-checked as {display}."
        ),
        "duplicate_check_status": "abc_canonical_url_external_id_and_excerpt_hash_checked",
        "quality_class": "B",
        "ethics_review_status": route.get("ethics_review_status", "public_media_context_reviewed"),
        "cultural_sensitivity": route.get("cultural_sensitivity", "low"),
        "acceptance_decision": "accepted",
        "rejection_reason": "",
        "evidence_summary": evidence,
    }


def collect_abc_algolia_place_route(
    route: dict[str, Any],
    stage_dir: Path,
    scaled: bool,
    cursor: dict[str, Any] | None = None,
) -> RouteResult:
    started_at = time.monotonic()
    cursor = cursor or {}
    route_id = route["route_id"]
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="scaled" if scaled else "probe",
    )
    max_candidates = int(route.get("max_candidates_scaled" if scaled else "max_candidates_probe") or 30)
    accepted_target = int(route.get("accepted_target") or 0)
    max_runtime = float(route.get("max_runtime_seconds") or 900)
    queries = [str(query) for query in route.get("queries") or []]
    allowed_states = {
        part.strip()
        for part in re.split(r"[/,\s]+", str(route.get("jurisdiction") or ""))
        if part.strip() in STATE_ALIASES
    }
    places = [
        place
        for place in route.get("place_catalog") or []
        if place.get("name") and place.get("state") and (not allowed_states or place.get("state") in allowed_states)
    ]
    cache = load_geocode_cache()
    seen_source_place: set[tuple[str, str]] = set()
    seen_digest: set[str] = set()
    query_index = int(cursor.get("query_index") or 0)
    page_index = int(cursor.get("page_index") or 0)
    try:
        for q_idx, query in enumerate(queries[query_index:], start=query_index):
            pages = int(route.get("pages_per_query") or 2)
            start_page = page_index if q_idx == query_index else 0
            for page in range(start_page, pages):
                if result.processed >= max_candidates:
                    break
                if accepted_target and result.accepted_provisional >= accepted_target:
                    break
                if time.monotonic() - started_at > max_runtime:
                    result.stop_reason = "route_runtime_limit_reached"
                    break
                try:
                    payload = abc_algolia_query(route, query, page)
                    result.fetched += 1
                except Exception as exc:  # noqa: BLE001
                    result.errors += 1
                    result.notes.append(f"{query} page {page}: {type(exc).__name__}: {exc}")
                    continue
                hits = payload.get("hits") or []
                print(
                    "[collection-sprint] "
                    f"route_id={route_id} abc_query={q_idx + 1}/{len(queries)} page={page + 1}/{pages} "
                    f"hits={len(hits)} processed={result.processed} accepted_provisional={result.accepted_provisional} "
                    f"map_candidates={result.map_candidates} elapsed={time.monotonic() - started_at:.1f}s",
                    flush=True,
                )
                for hit in hits:
                    if result.processed >= max_candidates:
                        break
                    if accepted_target and result.accepted_provisional >= accepted_target:
                        break
                    canonical_url = str(hit.get("canonicalURL") or "")
                    if not canonical_url or "abc.net.au" not in canonical_url:
                        result.rejected += 1
                        continue
                    text = abc_hit_text(hit)
                    if len(text) < 120 or ABC_SKIP_RE.search(text) or not ABC_STRONG_NARRATIVE_RE.search(text):
                        result.rejected += 1
                        continue
                    matched = False
                    for place in places:
                        alias = text_has_place(text, place)
                        if not alias:
                            continue
                        key = (canonical_url, str(place.get("name")))
                        if key in seen_source_place:
                            result.duplicates += 1
                            continue
                        evidence = abc_evidence_window(text, alias)
                        if not ABC_STRONG_NARRATIVE_RE.search(evidence) or ABC_SKIP_RE.search(evidence):
                            result.rejected += 1
                            continue
                        digest = hashlib.sha256(canonicalise_whitespace(f"{canonical_url}:{place.get('name')}:{evidence}").lower().encode("utf-8")).hexdigest()
                        if digest in seen_digest:
                            result.duplicates += 1
                            continue
                        geocode = geocode_route_place(place, cache, float(route.get("geocode_rate_limit_seconds") or 1.0))
                        result.processed += 1
                        matched = True
                        if not geocode:
                            result.rejected += 1
                            continue
                        seen_source_place.add(key)
                        seen_digest.add(digest)
                        candidate = make_abc_candidate(route, hit, place, alias, geocode, evidence)
                        candidate["raw_metadata_json"] = {
                            "route_id": route_id,
                            "source_family": route.get("family"),
                            "abc_hit_id": hit.get("id") or hit.get("objectID"),
                            "abc_query": query,
                            "place_alias": alias,
                            "evidence_sha256": digest,
                            "scope_classifier": "abc_algolia_place_first_v1",
                        }
                        result.candidates.append(candidate)
                        result.accepted_provisional += 1
                        result.map_candidates += 1
                        if result.processed % 25 == 0:
                            print_route_progress(result, started_at)
                    if not matched:
                        result.lead_only += 1
                if result.stop_reason:
                    break
                page_index = page + 1
            if result.stop_reason or result.processed >= max_candidates or (accepted_target and result.accepted_provisional >= accepted_target):
                query_index = q_idx
                break
            page_index = 0
            query_index = q_idx + 1
        result.resume_cursor = {
            "query_index": query_index,
            "page_index": page_index,
            "total_queries": len(queries),
            "exhausted": query_index >= len(queries),
            "updated_at": utc_now_iso(),
        }
        if not result.stop_reason:
            result.stop_reason = "accepted_target_reached" if accepted_target and result.accepted_provisional >= accepted_target else "route_candidate_limit_or_source_exhausted"
        if result.resume_cursor.get("exhausted") and not result.accepted_provisional:
            result.stop_reason = "abc_search_low_yield_or_exhausted"
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def title_from_page_text(text: str, fallback: str) -> str:
    compact = canonicalise_whitespace(text)
    if not compact:
        return fallback
    first = re.split(r"\s{2,}|\s+-\s+ABC|\s+\|\s+", compact, maxsplit=1)[0].strip()
    if 8 <= len(first) <= 180:
        return first
    return fallback


def resolve_config_place(route: dict[str, Any], page: dict[str, Any]) -> dict[str, Any] | None:
    if isinstance(page.get("place"), dict):
        return dict(page["place"])
    name = str(page.get("place_name") or "")
    if not name:
        return None
    for place in route.get("place_catalog") or []:
        if str(place.get("name") or "").lower() == name.lower():
            return dict(place)
        if any(str(alias).lower() == name.lower() for alias in place.get("aliases") or []):
            return dict(place)
    return {
        "name": name,
        "state": page.get("state"),
        "aliases": page.get("aliases") or [],
        "query": page.get("query"),
        "location_type": page.get("location_type") or "locality",
        "location_role": page.get("location_role") or route.get("default_location_role", "apparition_location"),
    }


def make_public_page_candidate(
    route: dict[str, Any],
    page: dict[str, Any],
    title: str,
    place: dict[str, Any],
    place_alias: str,
    geocode: dict[str, Any],
    evidence: str,
) -> dict[str, Any]:
    url = str(page["url"])
    place_name = f"{canonicalise_whitespace(place.get('name') or place_alias)}, {place.get('state')}"
    display = canonicalise_whitespace(geocode.get("display_name") or "")
    return {
        "candidate_status": "accepted",
        "source_name": route["source_name"],
        "source_type": route["source_type"],
        "source_tier": route["source_tier"],
        "title": canonicalise_whitespace(page.get("title") or title),
        "publication_or_organisation": route.get("publication_or_organisation") or route["organisation"],
        "publication_date_text": str(page.get("publication_date_text") or route.get("publication_date_text") or ""),
        "access_date": date.today().isoformat(),
        "url": url,
        "canonical_url": url,
        "external_id": f"public-page:{slug(url, 36)}:{slug(place.get('name') or place_alias, 24)}",
        "publicness_status": route.get("publicness_status", "public_web_page"),
        "rights_access_status": route.get("rights_access_status", "public_access_short_excerpt_only"),
        "narrative_type": route.get("narrative_type_override") or page.get("narrative_type") or "apparition_account",
        "secondary_role": route.get("secondary_role", "place_first_public_page_record"),
        "australian_relation": route.get("australian_relation", "Australian public page with source-stated place evidence."),
        "humanoid_basis": route.get("humanoid_basis", "explicit_supernatural_or_anomalous_person_form_agent"),
        "source_label": page.get("source_label") or source_label_from_text(evidence),
        "location_text": place_name,
        "location_role": place.get("location_role") or page.get("location_role") or route.get("default_location_role", "apparition_location"),
        "latitude": geocode["lat"],
        "longitude": geocode["lon"],
        "location_precision": place.get("location_type") or page.get("location_type") or "locality",
        "geocode_source": "nominatim_openstreetmap_state_checked_public_page_2026-06-22",
        "geocode_verification_status": "verified_gazetteer_point",
        "coordinate_evidence_note": (
            f"Public page text names `{place_alias}` in a ghost/supernatural context; "
            f"gazetteer result state-checked as {display}."
        ),
        "duplicate_check_status": "canonical_url_external_id_and_excerpt_hash_checked",
        "quality_class": route.get("quality_class", "B"),
        "ethics_review_status": route.get("ethics_review_status", "public_page_context_reviewed"),
        "cultural_sensitivity": route.get("cultural_sensitivity", "low"),
        "acceptance_decision": "accepted",
        "rejection_reason": "",
        "evidence_summary": evidence,
    }


def collect_public_page_place_route(
    route: dict[str, Any],
    stage_dir: Path,
    scaled: bool,
    cursor: dict[str, Any] | None = None,
) -> RouteResult:
    started_at = time.monotonic()
    cursor = cursor or {}
    route_id = route["route_id"]
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="scaled" if scaled else "probe",
    )
    try:
        if cursor.get("exhausted") and route.get("resume_strategy") != "rescan_new_evidence":
            result.stop_reason = "route_cursor_exhausted"
            result.resume_cursor = cursor
            return result
        max_candidates = int(route.get("max_candidates_scaled" if scaled else "max_candidates_probe") or 30)
        accepted_target = int(route.get("accepted_target") or 0)
        cache = load_geocode_cache()
        pages = list(route.get("pages") or [])
        start_page_index = 0 if route.get("resume_strategy") == "rescan_new_evidence" else int(cursor.get("page_index") or 0)
        next_page_index = start_page_index
        seen_external_ids: set[str] = set()
        for page_index, page in enumerate(pages[start_page_index:], start=start_page_index):
            if result.processed >= max_candidates:
                break
            if accepted_target and result.accepted_provisional >= accepted_target:
                break
            next_page_index = page_index
            try:
                text = fetch_text(page["url"])
                result.fetched += 1
            except Exception as exc:  # noqa: BLE001
                result.errors += 1
                result.notes.append(f"{page.get('url')}: {type(exc).__name__}: {exc}")
                next_page_index = page_index + 1
                continue
            next_page_index = page_index + 1
            text = canonicalise_whitespace(text)
            title = title_from_page_text(text, str(page.get("title") or page["url"].rsplit("/", 1)[-1]))
            page_places = [{**page, **place_row} for place_row in page.get("places", [])] if page.get("places") else [page]
            print(
                "[collection-sprint] "
                f"route_id={route_id} public_page_index={page_index + 1}/{len(pages)} "
                f"fetched={result.fetched} processed={result.processed} accepted_provisional={result.accepted_provisional} "
                f"map_candidates={result.map_candidates} elapsed={time.monotonic() - started_at:.1f}s",
                flush=True,
            )
            if len(text) < 120:
                result.rejected += len(page_places)
                continue
            for page_place in page_places:
                if result.processed >= max_candidates:
                    break
                if accepted_target and result.accepted_provisional >= accepted_target:
                    break
                place = resolve_config_place(route, page_place)
                result.processed += 1
                if not place or not place.get("state"):
                    result.rejected += 1
                    continue
                place_alias = text_has_place(text, place)
                if not place_alias:
                    result.rejected += 1
                    continue
                evidence = place_centered_evidence_window(text, place_alias, radius=int(route.get("evidence_radius") or 640))
                if not ABC_STRONG_NARRATIVE_RE.search(evidence):
                    result.rejected += 1
                    continue
                skip_pattern = route.get("skip_pattern")
                if skip_pattern and re.search(str(skip_pattern), evidence, re.I):
                    result.rejected += 1
                    continue
                geocode = geocode_route_place(place, cache, float(route.get("geocode_rate_limit_seconds") or 1.0))
                if not geocode:
                    result.lead_only += 1
                    continue
                candidate = make_public_page_candidate(route, page_place, title, place, place_alias, geocode, evidence)
                digest = hashlib.sha256(canonicalise_whitespace(f"{candidate['canonical_url']}:{evidence}").lower().encode("utf-8")).hexdigest()
                if candidate["external_id"] in seen_external_ids:
                    result.duplicates += 1
                    continue
                seen_external_ids.add(candidate["external_id"])
                candidate["raw_metadata_json"] = {
                    "route_id": route_id,
                    "source_family": route.get("family"),
                    "page_index": page_index,
                    "scope_classifier": "public_page_place_strong_ghost_gate_v1",
                    "evidence_sha256": digest,
                }
                result.candidates.append(candidate)
                result.accepted_provisional += 1
                result.map_candidates += 1
                if result.processed % 25 == 0:
                    print_route_progress(result, started_at)
        result.resume_cursor = {
            "page_index": next_page_index,
            "total_pages": len(pages),
            "exhausted": next_page_index >= len(pages),
            "updated_at": utc_now_iso(),
        }
        result.stop_reason = "accepted_target_reached" if accepted_target and result.accepted_provisional >= accepted_target else "route_candidate_limit_or_source_exhausted"
        if result.resume_cursor.get("exhausted") and not result.accepted_provisional:
            result.stop_reason = "public_page_low_yield_or_exhausted"
    except Exception as exc:  # noqa: BLE001
        result.errors += 1
        result.stop_reason = f"public_page_route_error:{type(exc).__name__}"
        result.notes.append(str(exc))
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def haversine_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(a_lat), math.radians(b_lat)
    delta_phi = math.radians(b_lat - a_lat)
    delta_lam = math.radians(b_lon - a_lon)
    value = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lam / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def verify_with_nominatim(place: str, state: str) -> dict[str, Any] | None:
    query = f"{place}, {STATE_ALIASES.get(state, state)}, Australia"
    url = "https://nominatim.openstreetmap.org/search?" + urlencode(
        {"q": query, "format": "jsonv2", "limit": "3", "addressdetails": "1"}
    )
    rows = json.loads(http_get(url).decode("utf-8", "ignore"))
    for row in rows:
        address = row.get("address") or {}
        row_state = address.get("state") or address.get("territory") or ""
        country_code = str(address.get("country_code") or "").upper()
        display = str(row.get("display_name") or "")
        if country_code == "AU" and (STATE_ALIASES.get(state, state).lower() in row_state.lower() or state in display):
            return row
    return None


def collect_map_queue_route(
    route: dict[str, Any],
    stage_dir: Path,
    scaled: bool,
    cursor: dict[str, Any] | None = None,
) -> RouteResult:
    started_at = time.monotonic()
    route_id = route["route_id"]
    result = RouteResult(
        route_id=route_id,
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route_id}.csv"),
        stage_ndjson=str(stage_dir / f"{route_id}.ndjson"),
        route_phase="scaled" if scaled else "probe",
    )
    limit = int(route.get("max_candidates_scaled" if scaled else "max_candidates_probe") or 30)
    target = int(route.get("map_target") or 0)
    queue_path = ROOT / route["queue_path"]
    with queue_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if result.processed >= limit:
            break
        if target and result.map_candidates >= target:
            break
        if row.get("promotion_status") not in {"not_promoted", "pending", ""}:
            continue
        result.processed += 1
        place = row.get("current_place_name") or row.get("previous_place") or ""
        state = row.get("current_state_territory") or ""
        try:
            gazetteer = verify_with_nominatim(place, state)
            result.fetched += 1
            time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            result.errors += 1
            result.notes.append(f"{place}: {type(exc).__name__}: {exc}")
            gazetteer = None
        if not gazetteer:
            result.rejected += 1
        else:
            lat = float(gazetteer["lat"])
            lon = float(gazetteer["lon"])
            old_lat = float(row.get("current_latitude") or row.get("previous_latitude") or lat)
            old_lon = float(row.get("current_longitude") or row.get("previous_longitude") or lon)
            distance = haversine_km(old_lat, old_lon, lat, lon)
            if distance > 35:
                result.rejected += 1
                result.notes.append(f"{place}: gazetteer distance {distance:.1f}km exceeds tolerance")
            elif row.get("current_relation_type") in {"publication_location", "source_collection_location"}:
                result.rejected += 1
            else:
                result.map_candidates += 1
                result.accepted_provisional += 1
                result.map_updates.append(
                    {
                        "record_id": int(row["record_id"]),
                        "place_name": place,
                        "state": state,
                        "latitude": lat,
                        "longitude": lon,
                        "geocode_source": "nominatim_openstreetmap_verified_2026-06-22",
                        "verification_status": "verified_gazetteer_point",
                        "evidence": f"Nominatim gazetteer verified {gazetteer.get('display_name')}; distance from queued coordinate {distance:.1f} km; source-stated place evidence: {row.get('source_evidence_text')}",
                    }
                )
        if result.processed % 25 == 0:
            print_route_progress(result, started_at)
    result.stop_reason = "map_target_reached" if target and result.map_candidates >= target else "queue_limit_or_unverified_rows"
    remaining = sum(1 for row in rows if row.get("promotion_status") in {"not_promoted", "pending", ""})
    result.resume_cursor = {
        "remaining_queue_rows": remaining,
        "exhausted": remaining == 0,
        "updated_at": utc_now_iso(),
    }
    result.runtime_seconds = time.monotonic() - started_at
    write_route_stage(result)
    print_route_progress(result, started_at)
    return result


def write_route_stage(result: RouteResult) -> None:
    csv_path = Path(result.stage_csv)
    ndjson_path = Path(result.stage_ndjson)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with ndjson_path.open("w", encoding="utf-8") as handle:
        for candidate in result.candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
        for update in result.map_updates:
            handle.write(json.dumps({"map_update": update}, ensure_ascii=False, sort_keys=True) + "\n")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for candidate in result.candidates:
            writer.writerow({field: candidate.get(field, "") for field in CSV_FIELDS})


def run_route(route: dict[str, Any], stage_dir: Path, scaled: bool = False, cursor: dict[str, Any] | None = None) -> RouteResult:
    if route.get("retrieval_method") == "abc_algolia_place_search":
        return collect_abc_algolia_place_route(route, stage_dir, scaled=scaled, cursor=cursor)
    if route.get("retrieval_method") == "public_page_place_text":
        return collect_public_page_place_route(route, stage_dir, scaled=scaled, cursor=cursor)
    if route.get("retrieval_method") == "exact_queue_gazetteer_verification":
        return collect_map_queue_route(route, stage_dir, scaled=scaled, cursor=cursor)
    if route.get("retrieval_method") == "recollect_search_item_ocr":
        return collect_recollect_ocr_route(route, stage_dir, scaled=scaled, cursor=cursor)
    if route.get("pages") or route.get("archive_identifier"):
        return collect_text_route(route, stage_dir, scaled=scaled, cursor=cursor)
    return collect_probe_only(route, stage_dir, cursor=cursor)


def failed_route_result(route: dict[str, Any], stage_dir: Path, exc: BaseException, scaled: bool) -> RouteResult:
    result = RouteResult(
        route_id=route["route_id"],
        family=route.get("family", ""),
        organisation=route.get("organisation", ""),
        source_name=route.get("source_name", ""),
        retrieval_method=route.get("retrieval_method", ""),
        stage_csv=str(stage_dir / f"{route['route_id']}.csv"),
        stage_ndjson=str(stage_dir / f"{route['route_id']}.ndjson"),
        route_phase="scaled" if scaled else "probe",
        errors=1,
        runtime_seconds=0.0,
        stop_reason=f"route_worker_error:{type(exc).__name__}",
        notes=[str(exc)],
        resume_cursor={"blocked": True, "updated_at": utc_now_iso()},
    )
    write_route_stage(result)
    print_route_progress(result, time.monotonic())
    return result


def load_export_counts() -> dict[str, int]:
    data = json.loads(FRONTEND_DATA.read_text(encoding="utf-8"))
    return {
        "public_records": len(data.get("records") or []),
        "map_points": len(data.get("map_points") or []),
        "map_flags": len(data.get("map_flags") or []),
    }


def db_public_counts() -> dict[str, int]:
    with connect(DEFAULT_DB_PATH) as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"]
        public = conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM records r
            LEFT JOIN coding c ON c.record_id = r.record_id
            WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
              AND COALESCE(c.relevance_code, '') != 'scope_excluded'
            """
        ).fetchone()["n"]
    return {"db_records": int(total), "db_public_records": int(public)}


def dedupe_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen_source: set[tuple[str, str]] = set()
    seen_text: set[str] = set()
    kept: list[dict[str, Any]] = []
    duplicates = 0
    for row in candidates:
        key = (row.get("canonical_url") or row.get("url") or "", row.get("external_id") or "")
        digest = hashlib.sha256(canonicalise_whitespace(row.get("evidence_summary")).lower().encode("utf-8")).hexdigest()
        narrative_key = f"{row.get('source_label','').lower()}:{digest}"
        if key in seen_source or narrative_key in seen_text:
            duplicates += 1
            continue
        seen_source.add(key)
        seen_text.add(narrative_key)
        kept.append(row)
    return kept, duplicates


def import_candidates_serial(candidates: list[dict[str, Any]], run_id: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    with connect(DEFAULT_DB_PATH) as conn:
        for row in candidates:
            data = dict(row)
            data["run_id"] = run_id
            status = insert_candidate(conn, data)
            counts[status] += 1
        conn.commit()
    return counts


def apply_map_updates_serial(updates: list[dict[str, Any]]) -> int:
    applied = 0
    seen_updates: set[tuple[int, str]] = set()
    with connect(DEFAULT_DB_PATH) as conn:
        for update in updates:
            update_key = (int(update["record_id"]), str(update["place_name"]))
            if update_key in seen_updates:
                continue
            seen_updates.add(update_key)
            row = conn.execute(
                """
                SELECT l.location_id
                FROM record_locations rl
                JOIN locations l ON l.location_id = rl.location_id
                WHERE rl.record_id = ?
                  AND l.place_name = ?
                  AND rl.relation_type NOT IN ('publication_location', 'source_collection_location')
                ORDER BY l.location_id
                LIMIT 1
                """,
                (update["record_id"], update["place_name"]),
            ).fetchone()
            if not row:
                continue
            conn.execute(
                """
                UPDATE locations
                SET latitude = ?,
                    longitude = ?,
                    state_territory = ?,
                    country = 'Australia',
                    location_type = COALESCE(location_type, 'locality'),
                    geocode_source = ?,
                    verification_status = ?,
                    notes = TRIM(COALESCE(notes, '') || char(10) || ?)
                WHERE location_id = ?
                """,
                (
                    update["latitude"],
                    update["longitude"],
                    update["state"],
                    update["geocode_source"],
                    update["verification_status"],
                    update["evidence"],
                    row["location_id"],
                ),
            )
            applied += 1
        conn.commit()
    if applied:
        queue_path = ROOT / "data" / "exports" / "v2" / "map_geocode_verification_queue.csv"
        if queue_path.exists():
            by_record = {str(update["record_id"]): update for update in updates}
            with queue_path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
                fieldnames = list(reader.fieldnames or [])
            changed = False
            for row in rows:
                update = by_record.get(row.get("record_id", ""))
                if not update:
                    continue
                row["required_source_place_confirmation"] = "passed"
                row["required_gazetteer_coordinate_verification"] = "passed"
                row["required_state_match_check"] = "passed"
                row["required_not_publication_place_check"] = "passed"
                row["required_verification_status_update"] = "passed"
                row["promotion_status"] = "promoted"
                row["review_note"] = update["evidence"]
                changed = True
            if changed:
                with queue_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(rows)
    return applied


def run_subprocess(args: list[str]) -> None:
    print(f"[collection-sprint] running {' '.join(args)}", flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def source_breakdowns(record_id_start: int, run_prefix: str | None = None) -> dict[str, dict[str, int]]:
    with connect(DEFAULT_DB_PATH) as conn:
        if run_prefix:
            rows = conn.execute(
                """
                SELECT r.record_id, s.source_name, s.source_type, c.ontology_code,
                       COALESCE(l.state_territory, '') AS state_territory
                FROM collection_candidates_v2 cc
                JOIN collection_candidate_record_mappings m ON m.candidate_id = cc.candidate_id
                JOIN records r ON r.record_id = m.record_id
                JOIN sources s ON s.source_id = r.source_id
                LEFT JOIN coding c ON c.record_id = r.record_id
                LEFT JOIN record_locations rl ON rl.record_id = r.record_id
                LEFT JOIN locations l ON l.location_id = rl.location_id
                WHERE cc.run_id LIKE ?
                  AND COALESCE(r.publicness_level, '') != 'restricted_excluded'
                  AND COALESCE(c.relevance_code, '') != 'scope_excluded'
                """,
                (f"{run_prefix}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.record_id, s.source_name, s.source_type, c.ontology_code,
                       COALESCE(l.state_territory, '') AS state_territory
                FROM records r
                JOIN sources s ON s.source_id = r.source_id
                LEFT JOIN coding c ON c.record_id = r.record_id
                LEFT JOIN record_locations rl ON rl.record_id = r.record_id
                LEFT JOIN locations l ON l.location_id = rl.location_id
                WHERE r.record_id > ?
                  AND COALESCE(r.publicness_level, '') != 'restricted_excluded'
                  AND COALESCE(c.relevance_code, '') != 'scope_excluded'
                """,
                (record_id_start,),
            ).fetchall()
    by_org: Counter[str] = Counter()
    by_type: Counter[str] = Counter()
    by_jurisdiction: Counter[str] = Counter()
    by_source_family: Counter[str] = Counter()
    seen_record_org: set[int] = set()
    seen_record_type: set[int] = set()
    states_by_record: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        record_id = int(row["record_id"])
        if record_id not in seen_record_org:
            by_org[row["source_name"] or "unknown"] += 1
            by_source_family[row["source_type"] or "unknown"] += 1
            seen_record_org.add(record_id)
        if record_id not in seen_record_type:
            by_type[row["ontology_code"] or "unknown"] += 1
            seen_record_type.add(record_id)
        if row["state_territory"]:
            states_by_record[record_id].add(row["state_territory"])
    for states in states_by_record.values():
        by_jurisdiction["/".join(sorted(states))] += 1
    return {
        "by_source_organisation": dict(sorted(by_org.items())),
        "by_source_family": dict(sorted(by_source_family.items())),
        "by_jurisdiction": dict(sorted(by_jurisdiction.items())),
        "by_narrative_type": dict(sorted(by_type.items())),
    }


def map_invariant() -> dict[str, int | bool]:
    counts = load_export_counts()
    return {
        "mapped_record_count": counts["map_flags"],
        "map_points_length": counts["map_points"],
        "map_flags_length": counts["map_flags"],
        "ok": counts["map_points"] == counts["map_flags"],
    }


def launch_targets(config: dict[str, Any]) -> dict[str, int]:
    active = config.get("launch_targets") or {}
    legacy = config.get("targets") or {}
    minimum_records = int(active.get("minimum_public_records") or legacy.get("public_records") or 3500)
    preferred_records = int(active.get("preferred_public_records") or max(3800, minimum_records))
    soft_maximum_records = int(active.get("soft_maximum_public_records") or max(4000, preferred_records))
    minimum_map_flags = int(active.get("minimum_map_flags") or legacy.get("map_flags") or 1200)
    return {
        "minimum_public_records": minimum_records,
        "preferred_public_records": preferred_records,
        "soft_maximum_public_records": soft_maximum_records,
        "minimum_map_flags": minimum_map_flags,
    }


def active_collection_mode(public_records: int, map_flags: int, targets: dict[str, int]) -> str:
    if public_records >= targets["minimum_public_records"] and map_flags >= targets["minimum_map_flags"]:
        return "complete"
    if public_records >= targets["minimum_public_records"] and map_flags < targets["minimum_map_flags"]:
        return "map_first"
    if map_flags >= targets["minimum_map_flags"] and public_records < targets["minimum_public_records"]:
        return "record_growth"
    return "balanced_growth"


def target_progress_fields(public_records: int, map_flags: int, state: dict[str, Any], targets: dict[str, int]) -> dict[str, Any]:
    records_since_checkpoint = public_records - int(state.get("records_at_last_checkpoint") or public_records)
    maps_since_checkpoint = map_flags - int(state.get("map_flags_at_last_checkpoint") or map_flags)
    return {
        "target_public_records": targets["minimum_public_records"],
        "target_preferred_public_records": targets["preferred_public_records"],
        "target_soft_maximum_public_records": targets["soft_maximum_public_records"],
        "target_map_flags": targets["minimum_map_flags"],
        "current_public_records": public_records,
        "current_public_record_count": public_records,
        "gap_to_minimum_3500": max(0, targets["minimum_public_records"] - public_records),
        "gap_to_preferred_3800": max(0, targets["preferred_public_records"] - public_records),
        "soft_ceiling_remaining": max(0, targets["soft_maximum_public_records"] - public_records),
        "current_map_flags": map_flags,
        "current_map_flag_count": map_flags,
        "gap_to_map_1200": max(0, targets["minimum_map_flags"] - map_flags),
        "current_map_ratio": round(map_flags / public_records, 4) if public_records else 0,
        "records_added_since_checkpoint": records_since_checkpoint,
        "map_flags_added_since_checkpoint": maps_since_checkpoint,
        "records_per_new_map_flag": round(records_since_checkpoint / maps_since_checkpoint, 2) if maps_since_checkpoint else None,
        "active_collection_mode": active_collection_mode(public_records, map_flags, targets),
        "record_gap": max(0, targets["minimum_public_records"] - public_records),
        "map_gap": max(0, targets["minimum_map_flags"] - map_flags),
    }


def fresh_state(config: dict[str, Any]) -> dict[str, Any]:
    counts = load_export_counts()
    targets = launch_targets(config)
    state = {
        "schema_version": "collection-sprint-state/v1",
        "created_at": utc_now_iso(),
        "updated_at": utc_now_iso(),
        "launch_start_public_record_count": counts["public_records"],
        "launch_start_map_flag_count": counts["map_flags"],
        "active_routes": [],
        "productive_routes": [],
        "exhausted_routes": [],
        "blocked_routes": [],
        "next_route_queue": [],
        "candidates_processed": 0,
        "accepted_records": 0,
        "context_records": 0,
        "suppressed_rows": 0,
        "duplicates": 0,
        "rejected_rows": 0,
        "map_candidates": 0,
        "verified_map_flags": 0,
        "last_completed_checkpoint": "",
        "checkpoint_index": 0,
        "records_at_last_checkpoint": counts["public_records"],
        "map_flags_at_last_checkpoint": counts["map_flags"],
        "resume_cursor_per_route": {},
        "route_totals": {},
        "history": [],
    }
    state.update(target_progress_fields(counts["public_records"], counts["map_flags"], state, targets))
    if STATUS_JSON.exists():
        try:
            status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            status = {}
        route_yield = status.get("aggregated_route_yield") or []
        route_by_id = {route["route_id"]: route for route in config.get("routes", [])}
        productive: set[str] = set()
        exhausted: set[str] = set()
        blocked: set[str] = set()
        for row in route_yield:
            route_id = row.get("route_id")
            if not route_id:
                continue
            accepted = int(row.get("accepted_provisional") or 0)
            total = {
                "processed": int(row.get("processed") or 0),
                "accepted": accepted,
                "context": int(row.get("context_provisional") or 0),
                "duplicates": int(row.get("duplicates") or 0),
                "rejected": int(row.get("rejected") or 0),
                "errors": 0,
                "map_candidates": int(row.get("map_candidates") or 0),
                "latest_acceptance_rate": accepted / int(row.get("processed") or 1),
            }
            state["route_totals"][route_id] = total
            route = route_by_id.get(route_id) or {}
            pages = route.get("pages") or []
            if pages:
                consumed_pages = int(route.get("bootstrap_consumed_pages") or len(pages))
                state["resume_cursor_per_route"][route_id] = {
                    "page_index": min(consumed_pages, len(pages)),
                    "total_pages": len(pages),
                    "exhausted": consumed_pages >= len(pages),
                    "updated_at": utc_now_iso(),
                    "bootstrap_from": "collection_sprint_status",
                }
            elif route.get("archive_identifier"):
                state["resume_cursor_per_route"][route_id] = {
                    "exhausted": True,
                    "updated_at": utc_now_iso(),
                    "bootstrap_from": "collection_sprint_status",
                }
            if accepted >= 6:
                productive.add(route_id)
            if accepted == 0:
                exhausted.add(route_id)
            if "probe_error" in str(row.get("stop_reason") or ""):
                blocked.add(route_id)
        state["productive_routes"] = sorted(productive)
        state["exhausted_routes"] = sorted(exhausted)
        state["blocked_routes"] = sorted(blocked)
    state["next_route_queue"] = [route["route_id"] for route in rank_routes(config, state)]
    return state


def load_state(config: dict[str, Any], resume: bool) -> dict[str, Any]:
    if resume and STATE_JSON.exists():
        state = json.loads(STATE_JSON.read_text(encoding="utf-8"))
    else:
        state = fresh_state(config)
    state.setdefault("resume_cursor_per_route", {})
    state.setdefault("route_totals", {})
    state.setdefault("routes", state.get("route_totals", {}))
    state.setdefault("history", [])
    counts = load_export_counts()
    state.update(target_progress_fields(counts["public_records"], counts["map_flags"], state, launch_targets(config)))
    return state


def route_is_blocked(route: dict[str, Any], state: dict[str, Any]) -> bool:
    route_id = route["route_id"]
    cursor = state.get("resume_cursor_per_route", {}).get(route_id) or {}
    if cursor.get("exhausted"):
        return True
    if route_id in set(state.get("blocked_routes") or []):
        return True
    return False


def rank_routes(config: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    routes = [route for route in config.get("routes", []) if route.get("enabled", True)]
    productive = set(state.get("productive_routes") or [])
    mode = state.get("active_collection_mode") or "balanced_growth"
    if mode == "map_first":
        routes = [
            route
            for route in routes
            if route.get("family") == "place_first_map_records"
            or route.get("map_target")
            or route.get("map_capable")
            or route.get("default_location_role") in {"apparition_location", "legend_associated_place", "narrative_setting"}
            and any((page.get("latitude") and page.get("longitude")) for page in route.get("pages", []))
        ]

    def score(route: dict[str, Any]) -> tuple[int, str]:
        family = str(route.get("family") or "")
        bonus = 0
        if mode == "balanced_growth" and (route.get("family") == "place_first_map_records" or route.get("map_target") or route.get("map_capable")):
            bonus -= 25
        if route["route_id"] in productive or route.get("scaled"):
            bonus -= 40
        if family in {"local_archive_historical_society", "repository_institutional_full_text", "place_first_map_records"}:
            bonus -= 10
        return (bonus, route["route_id"])

    return sorted([route for route in routes if not route_is_blocked(route, state)], key=score)


def update_state_after_checkpoint(
    state: dict[str, Any],
    config: dict[str, Any],
    run_id: str,
    results: list[RouteResult],
    imported: Counter[str],
    final_export: dict[str, int],
    applied_map_updates: int,
) -> None:
    targets = launch_targets(config)
    state["updated_at"] = utc_now_iso()
    state.update(target_progress_fields(final_export["public_records"], final_export["map_flags"], state, targets))
    state["candidates_processed"] = int(state.get("candidates_processed") or 0) + sum(result.processed for result in results)
    state["accepted_records"] = int(state.get("accepted_records") or 0) + int(imported.get("accepted", 0))
    state["context_records"] = int(state.get("context_records") or 0) + int(imported.get("lead_only", 0))
    state["suppressed_rows"] = int(state.get("suppressed_rows") or 0) + sum(result.suppressed for result in results)
    state["duplicates"] = int(state.get("duplicates") or 0) + int(imported.get("duplicate", 0)) + sum(result.duplicates for result in results)
    state["rejected_rows"] = int(state.get("rejected_rows") or 0) + int(imported.get("rejected", 0)) + sum(result.rejected for result in results)
    state["map_candidates"] = int(state.get("map_candidates") or 0) + sum(result.map_candidates for result in results)
    state["verified_map_flags"] = int(state.get("verified_map_flags") or 0) + applied_map_updates
    route_totals = state.setdefault("route_totals", {})
    cursors = state.setdefault("resume_cursor_per_route", {})
    productive: set[str] = set(state.get("productive_routes") or [])
    exhausted: set[str] = set(state.get("exhausted_routes") or [])
    blocked: set[str] = set(state.get("blocked_routes") or [])
    for result in results:
        total = route_totals.setdefault(
            result.route_id,
            {
                "processed": 0,
                "accepted": 0,
                "context": 0,
                "duplicates": 0,
                "rejected": 0,
                "errors": 0,
                "map_candidates": 0,
                "latest_acceptance_rate": 0,
                "last_accepted": 0,
            },
        )
        total["processed"] += result.processed
        total["accepted"] += result.accepted_provisional
        total["context"] += result.context_provisional
        total["duplicates"] += result.duplicates
        total["rejected"] += result.rejected
        total["errors"] += result.errors
        total["map_candidates"] += result.map_candidates
        total["latest_acceptance_rate"] = result.accepted_provisional / result.processed if result.processed else 0
        total["last_accepted"] = result.accepted_provisional
        if result.resume_cursor:
            cursors[result.route_id] = result.resume_cursor
        if result.accepted_provisional >= 6 or result.map_candidates >= 6:
            productive.add(result.route_id)
            exhausted.discard(result.route_id)
        if result.resume_cursor.get("exhausted") and result.accepted_provisional == 0:
            exhausted.add(result.route_id)
        if result.errors and not result.processed:
            blocked.add(result.route_id)
    queue = [route["route_id"] for route in rank_routes(config, state)]
    state["active_routes"] = [result.route_id for result in results]
    state["productive_routes"] = sorted(productive)
    state["exhausted_routes"] = sorted(exhausted)
    state["blocked_routes"] = sorted(blocked)
    state["next_route_queue"] = queue
    state["routes"] = route_totals
    state["last_completed_checkpoint"] = run_id
    state["history"].append(
        {
            "run_id": run_id,
            "completed_at": utc_now_iso(),
            "public_records": final_export["public_records"],
            "map_flags": final_export["map_flags"],
            "processed": sum(result.processed for result in results),
            "accepted": int(imported.get("accepted", 0)),
            "map_updates": applied_map_updates,
        }
    )
    STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def checkpoint_due(state: dict[str, Any], config: dict[str, Any]) -> bool:
    record_interval = int(config.get("checkpoint_record_interval") or 250)
    map_interval = int(config.get("checkpoint_map_interval") or 75)
    records_delta = int(state["current_public_record_count"]) - int(state.get("records_at_last_checkpoint") or 0)
    map_delta = int(state["current_map_flag_count"]) - int(state.get("map_flags_at_last_checkpoint") or 0)
    return records_delta >= record_interval or map_delta >= map_interval


def commit_and_push_checkpoint(state: dict[str, Any]) -> str | None:
    index = int(state.get("checkpoint_index") or 0) + 1
    message = f"collection sprint checkpoint {index:02d}"
    state["checkpoint_index"] = index
    state["records_at_last_checkpoint"] = state["current_public_record_count"]
    state["map_flags_at_last_checkpoint"] = state["current_map_flag_count"]
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    stage_paths = [
        f"data/interim/collection_sprint/{entry['run_id']}"
        for entry in state.get("history", [])
        if entry.get("run_id")
        and (
            int(entry.get("processed") or 0) > 0
            or int(entry.get("accepted") or 0) > 0
            or int(entry.get("map_updates") or 0) > 0
        )
    ]
    paths = [
        "config/collection_routes.yml",
        "config/collection_sprint.yml",
        "data/exports/v2/map_geocode_verification_queue.csv",
        "data/processed/australian_humanoid_figures.sqlite",
        "data/processed/v2/collection_route_registry.csv",
        "data/processed/v2/collection_route_registry.md",
        "data/processed/v2/collection_sprint_status.json",
        "data/processed/v2/collection_sprint_status.md",
        "data/processed/v2/collection_sprint_state.json",
        "data/processed/v2/validation_v2_report.md",
        "public/data/frontend-data.json",
        "scripts/run_collection_sprint.py",
        *stage_paths,
    ]
    run_subprocess(["git", "add", *paths])
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT)
    if diff.returncode == 0:
        return None
    run_subprocess(["git", "commit", "-m", message])
    run_subprocess(["git", "push", "origin", "main"])
    return message


def update_route_registry(config: dict[str, Any], results: list[RouteResult], imported: Counter[str]) -> None:
    raw = yaml.safe_load(ROUTES_PATH.read_text(encoding="utf-8")) or {}
    routes = raw.setdefault("routes", [])
    by_id = {row.get("route_id"): row for row in routes}
    now = date.today().isoformat()
    result_by_id = {result.route_id: result for result in results}
    for route in config.get("routes", []):
        route_id = route["route_id"]
        result = result_by_id.get(route_id)
        if not result:
            continue
        row = by_id.get(route_id)
        if row is None:
            row = {
                "route_id": route_id,
                "source_name": route.get("source_name", ""),
                "organisation": route.get("organisation", ""),
                "domain": route.get("base_url") or route.get("search_url") or route.get("archive_identifier") or "",
                "jurisdiction": route.get("jurisdiction", ""),
                "source_class": route.get("source_type", ""),
                "retrieval_method": route.get("retrieval_method", ""),
                "endpoint_or_seed_url": route.get("base_url") or route.get("search_url") or "",
                "authentication_required": False,
                "credentials_available": True,
                "robots_status": "exact_public_pages_checked",
                "terms_status": "public_access_text_or_discovery_page",
                "publicness_status": "public",
                "first_attempted_at": now,
            }
            routes.append(row)
            by_id[route_id] = row
        seen = int(row.get("candidates_seen") or 0) + result.processed
        accepted = int(row.get("accepted_count") or 0) + result.accepted_provisional
        dupes = int(row.get("duplicate_count") or 0) + result.duplicates
        leads = int(row.get("lead_count") or 0) + result.lead_only + result.context_provisional
        rejected = int(row.get("rejected_count") or 0) + result.rejected + result.suppressed
        row.update(
            {
                "last_attempted_at": now,
                "attempt_count": int(row.get("attempt_count") or 0) + 1,
                "candidates_seen": seen,
                "accepted_count": accepted,
                "duplicate_count": dupes,
                "lead_count": leads,
                "rejected_count": rejected,
                "average_seconds_per_candidate": round(result.runtime_seconds / result.processed, 3) if result.processed else "",
                "blocker": "" if result.accepted_provisional else "low_yield_or_discovery_only",
                "failure_reason": "" if result.accepted_provisional else result.stop_reason,
                "retry_condition": "Continue exact route scaling while stable public text and scope yield remain acceptable.",
                "next_action": "Scale productive route" if result.accepted_provisional >= 6 else "Keep as probe/discovery route only",
                "route_status": "productive" if result.accepted_provisional >= 6 else "low_yield",
            }
        )
    ROUTES_PATH.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")
    run_subprocess(["python3", "scripts/update_collection_route_registry.py"])


def write_status(
    config: dict[str, Any],
    stage_dir: Path,
    baseline_export: dict[str, int],
    final_export: dict[str, int],
    baseline_db: dict[str, int],
    final_db: dict[str, int],
    results: list[RouteResult],
    imported: Counter[str],
    promoted: dict[str, int],
    applied_map_updates: int,
    breakdowns: dict[str, dict[str, int]],
    validation_ok: bool,
    build_ok: bool,
    previous_status: dict[str, Any] | None = None,
) -> None:
    targets = launch_targets(config)
    previous_status = previous_status or {}
    previous_results = previous_status.get("route_results") or []
    current_results = [result.as_dict() for result in results]
    combined_results = previous_results + current_results
    previous_processed = int(previous_status.get("candidates_processed") or 0)
    previous_map_updates = int(previous_status.get("map_queue_updates_applied") or 0)
    checkpoint_state = {}
    if STATE_JSON.exists():
        try:
            checkpoint_state = json.loads(STATE_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            checkpoint_state = {}
    status_progress = target_progress_fields(
        final_export["public_records"],
        final_export["map_flags"],
        {
            "records_at_last_checkpoint": checkpoint_state.get("records_at_last_checkpoint")
            or previous_status.get("records_at_last_checkpoint")
            or baseline_export["public_records"],
            "map_flags_at_last_checkpoint": checkpoint_state.get("map_flags_at_last_checkpoint")
            or previous_status.get("map_flags_at_last_checkpoint")
            or baseline_export["map_flags"],
        },
        targets,
    )
    status = {
        "generated_at": utc_now_iso(),
        "run_id": config.get("run_id"),
        "stage_dir": str(stage_dir),
        "starting_public_records": baseline_export["public_records"],
        "ending_public_records": final_export["public_records"],
        "net_new_public_records": final_export["public_records"] - baseline_export["public_records"],
        "starting_map_flags": baseline_export["map_flags"],
        "ending_map_flags": final_export["map_flags"],
        "net_new_map_flags": final_export["map_flags"] - baseline_export["map_flags"],
        "starting_db": baseline_db,
        "ending_db": final_db,
        "candidates_processed": previous_processed + sum(result.processed for result in results),
        "staged_import_counts": dict(imported),
        "promotion": promoted,
        "map_queue_updates_applied": previous_map_updates + applied_map_updates,
        "route_results": combined_results,
        "productive_routes": sorted({row["route_id"] for row in combined_results if int(row.get("accepted_provisional") or 0) >= 6}),
        "exhausted_routes": sorted({row["route_id"] for row in combined_results if not int(row.get("accepted_provisional") or 0)}),
        "launch_targets": targets,
        "records_at_last_checkpoint": status_progress["current_public_records"] - status_progress["records_added_since_checkpoint"],
        "map_flags_at_last_checkpoint": status_progress["current_map_flags"] - status_progress["map_flags_added_since_checkpoint"],
        "map_invariant": map_invariant(),
        "validation_ok": validation_ok,
        "build_ok": build_ok,
        **status_progress,
        **breakdowns,
    }
    STATUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    STATUS_JSON.write_text(json.dumps(status, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Collection Sprint Status",
        "",
        f"- Generated: `{status['generated_at']}`",
        f"- Run id: `{status['run_id']}`",
        f"- Stage directory: `{status['stage_dir']}`",
        f"- Starting public records: `{status['starting_public_records']}`",
        f"- Ending public records: `{status['ending_public_records']}`",
        f"- Net-new public records: `{status['net_new_public_records']}`",
        f"- Starting map flags: `{status['starting_map_flags']}`",
        f"- Ending map flags: `{status['ending_map_flags']}`",
        f"- Net-new map flags: `{status['net_new_map_flags']}`",
        f"- Candidates processed: `{status['candidates_processed']}`",
        f"- Context/lead staged: `{imported.get('lead_only', 0)}`",
        f"- Suppressed/rejected staged: `{imported.get('rejected', 0)}`",
        f"- Duplicate staged: `{imported.get('duplicate', 0)}`",
        f"- Gap to minimum 3,500 public records: `{status['gap_to_minimum_3500']}`",
        f"- Gap to preferred 3,800 public records: `{status['gap_to_preferred_3800']}`",
        f"- Soft ceiling remaining before 4,000: `{status['soft_ceiling_remaining']}`",
        f"- Gap to 1,200 map flags: `{status['gap_to_map_1200']}`",
        f"- Current map ratio: `{status['current_map_ratio']}`",
        f"- Records added since checkpoint: `{status['records_added_since_checkpoint']}`",
        f"- Map flags added since checkpoint: `{status['map_flags_added_since_checkpoint']}`",
        f"- Records per new map flag: `{status['records_per_new_map_flag']}`",
        f"- Active collection mode: `{status['active_collection_mode']}`",
        f"- Map invariant ok: `{status['map_invariant']['ok']}`",
        "",
        "## Records by Source Organisation",
    ]
    for key, value in status["by_source_organisation"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Records by Source Family")
    for key, value in status["by_source_family"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Records by Jurisdiction")
    for key, value in status["by_jurisdiction"].items():
        lines.append(f"- {key or 'unmapped/broad'}: {value}")
    lines.append("")
    lines.append("## Records by Narrative Type")
    for key, value in status["by_narrative_type"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append("## Per-Route Yield")
    lines.append("")
    lines.append("| route_id | family | processed | accepted | context | rejected | duplicates | map_candidates | runtime_s | stop_reason |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in combined_results:
        lines.append(
            f"| {row.get('route_id', '')} | {row.get('family', '')} | {row.get('processed', 0)} | {row.get('accepted_provisional', row.get('accepted', 0))} | "
            f"{row.get('context_provisional', row.get('context', 0))} | {row.get('rejected', 0)} | {row.get('duplicates', 0)} | {row.get('map_candidates', 0)} | "
            f"{row.get('runtime_seconds', 0)} | {row.get('stop_reason', '')} |"
        )
    lines.extend(
        [
            "",
            "## Productive Routes",
            "",
            *(f"- {route_id}" for route_id in status["productive_routes"]),
            "",
            "## Exhausted or Discovery-Only Routes",
            "",
            *(f"- {route_id}" for route_id in status["exhausted_routes"]),
        ]
    )
    STATUS_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_collection_iteration(
    config: dict[str, Any],
    state: dict[str, Any],
    run_id: str,
    skip_build: bool,
) -> tuple[dict[str, Any], int, int]:
    stage_dir = ROOT / "data" / "interim" / "collection_sprint" / run_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    previous_status = json.loads(STATUS_JSON.read_text(encoding="utf-8")) if STATUS_JSON.exists() else {}
    live_export = load_export_counts()
    baseline_export = {
        "public_records": int(state.get("launch_start_public_record_count") or live_export["public_records"]),
        "map_points": int(state.get("launch_start_map_flag_count") or live_export["map_points"]),
        "map_flags": int(state.get("launch_start_map_flag_count") or live_export["map_flags"]),
    }
    baseline_db = db_public_counts()
    with connect(DEFAULT_DB_PATH) as conn:
        max_record_id = int(conn.execute("SELECT COALESCE(MAX(record_id), 0) AS n FROM records").fetchone()["n"])

    routes = rank_routes(config, state)
    worker_count = min(int(config.get("worker_count") or 4), 6)
    selected_routes = routes[:worker_count]
    if not selected_routes:
        print("[collection-sprint] no active routes remain", flush=True)
        return state, 0, 0
    state["next_route_queue"] = [route["route_id"] for route in routes]
    state["active_routes"] = [route["route_id"] for route in selected_routes]
    STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"[collection-sprint] run_id={run_id} live_public_records={live_export['public_records']} "
        f"live_map_flags={live_export['map_flags']} active_routes={','.join(state['active_routes'])}",
        flush=True,
    )
    results: list[RouteResult] = []
    cursors = state.get("resume_cursor_per_route", {})
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {}
        for route in selected_routes:
            route_cursor = cursors.get(route["route_id"]) or {}
            scaled = bool(route.get("scaled") or route["route_id"] in set(state.get("productive_routes") or []))
            futures[executor.submit(run_route, route, stage_dir, scaled, route_cursor)] = (route, scaled)
        for future in as_completed(futures):
            route, scaled = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:  # noqa: BLE001
                print(
                    "[collection-sprint] "
                    f"route_id={route['route_id']} worker_error={type(exc).__name__}: {exc}",
                    flush=True,
                )
                results.append(failed_route_result(route, stage_dir, exc, scaled))

    all_candidates = [candidate for result in results for candidate in result.candidates]
    deduped_candidates, staged_duplicates = dedupe_candidates(all_candidates)
    if staged_duplicates:
        print(f"[collection-sprint] staged_dedupe_duplicates={staged_duplicates}", flush=True)
    imported = import_candidates_serial(deduped_candidates, run_id)
    promoted = promote_candidates(DEFAULT_DB_PATH)
    applied_map_updates = apply_map_updates_serial([update for result in results for update in result.map_updates])
    update_route_registry(config, results, imported)

    run_subprocess(["python3", "scripts/export_frontend_json.py"])
    validation_ok = True
    try:
        run_subprocess(["python3", "scripts/validate_v2.py"])
    except subprocess.CalledProcessError:
        validation_ok = False
    build_ok = True
    if not skip_build:
        try:
            run_subprocess(["npm", "run", "build"])
        except subprocess.CalledProcessError:
            build_ok = False
    final_export = load_export_counts()
    final_db = db_public_counts()
    breakdowns = source_breakdowns(max_record_id)
    write_status(
        config,
        stage_dir,
        baseline_export,
        final_export,
        baseline_db,
        final_db,
        results,
        imported,
        promoted,
        applied_map_updates,
        breakdowns,
        validation_ok,
        build_ok,
        previous_status,
    )
    records_added = final_export["public_records"] - live_export["public_records"]
    maps_added = final_export["map_flags"] - live_export["map_flags"]
    update_state_after_checkpoint(state, config, run_id, results, imported, final_export, applied_map_updates)
    print(
        "[collection-sprint] iteration_complete "
        f"records_added={records_added} map_flags_added={maps_added} "
        f"public_records={final_export['public_records']} map_flags={final_export['map_flags']}",
        flush=True,
    )
    return state, records_added, maps_added


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--skip-build", action="store_true", help="Skip final npm production build")
    parser.add_argument("--resume", action="store_true", help="Resume from collection_sprint_state.json")
    parser.add_argument("--until-launch-target", action="store_true", help="Continue until public launch record and map targets are met")
    parser.add_argument("--max-loops", type=int, default=1, help="Safety cap for non-launch runs")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    state = load_state(config, resume=args.resume or args.until_launch_target)
    if not STATE_JSON.exists():
        STATE_JSON.parent.mkdir(parents=True, exist_ok=True)
        STATE_JSON.write_text(json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    loops = 0
    while True:
        counts = load_export_counts()
        targets = launch_targets(config)
        state.update(target_progress_fields(counts["public_records"], counts["map_flags"], state, targets))
        launch_ready = (
            counts["public_records"] >= targets["minimum_public_records"]
            and counts["map_flags"] >= targets["minimum_map_flags"]
            and counts["map_points"] == counts["map_flags"]
        )
        if launch_ready:
            print("[collection-sprint] launch targets reached; final build/export/report can run", flush=True)
            if not args.skip_build:
                run_subprocess(["python3", "scripts/export_frontend_json.py"])
                run_subprocess(["python3", "scripts/validate_v2.py"])
                run_subprocess(["npm", "run", "build"])
            break
        if not args.until_launch_target and loops >= args.max_loops:
            break
        loops += 1
        checkpoint_next = int(state.get("checkpoint_index") or 0) + 1
        run_id = f"collection_sprint_launch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{checkpoint_next:03d}"
        state, records_added, maps_added = run_collection_iteration(
            config,
            state,
            run_id,
            skip_build=True if args.until_launch_target else args.skip_build,
        )
        if checkpoint_due(state, config):
            commit_and_push_checkpoint(state)
        if records_added == 0 and maps_added == 0:
            active = rank_routes(config, state)
            if not active:
                print("[collection-sprint] hard stop: no active usable routes remain", flush=True)
                break
        if not args.until_launch_target and loops >= args.max_loops:
            break


if __name__ == "__main__":
    main()
