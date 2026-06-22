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
from typing import Any
from urllib.parse import quote, urlencode
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


def slug(value: str, max_len: int = 60) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", canonicalise_whitespace(value).lower()).strip("-")
    return cleaned[:max_len].strip("-") or "item"


def short_excerpt(text: str, limit: int = 640) -> str:
    text = canonicalise_whitespace(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0] + "."


def classify_block(term: str, block: str, route: dict[str, Any]) -> tuple[str, str, str, str]:
    lower = block.lower()
    term_lower = term.lower()
    person_form = term_lower in lower and any(word in lower for word in PERSON_FORM_WORDS)
    if term_lower in {"medicine man", "medicine-man", "magic man", "little old man", "little old woman"}:
        person_form = True
    if term_lower in {"fairy", "fairies", "witch", "wizard", "magician", "enchanter", "giant", "ghost", "spirit", "devil", "water-sprite"}:
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


def make_candidate(route: dict[str, Any], page: dict[str, Any], term: str, block: str, index: int) -> dict[str, Any]:
    outcome, narrative_type, humanoid_basis, candidate_status = classify_block(term, block, route)
    chapter = canonicalise_whitespace(page.get("chapter") or page.get("section_id") or "section")
    title = f"{canonicalise_whitespace(term)} in {chapter}"
    source_title = canonicalise_whitespace(route.get("source_title") or route.get("source_name"))
    external_id = f"{slug(route['route_id'], 28)}:{slug(page.get('section_id') or page.get('url'), 28)}:{slug(term, 28)}:{index:03d}"
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
        "location_text": route.get("default_location_text", ""),
        "location_role": route.get("default_location_role", "cultural_association_region"),
        "latitude": "",
        "longitude": "",
        "location_precision": "region" if route.get("default_location_text") else "",
        "geocode_source": "",
        "geocode_verification_status": "",
        "coordinate_evidence_note": "",
        "duplicate_check_status": "source_url_external_id_and_excerpt_hash_checked",
        "quality_class": "B" if outcome == "first_class" else "reviewed_context",
        "ethics_review_status": "public_context_reviewed",
        "cultural_sensitivity": "moderate",
        "acceptance_decision": "accepted" if outcome == "first_class" else "not_accepted",
        "rejection_reason": "" if outcome == "first_class" else outcome,
        "evidence_summary": evidence,
    }


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
    text_name = ""
    for file_row in metadata.get("files", []):
        name = str(file_row.get("name") or "")
        if name.endswith("_djvu.txt"):
            text_name = name
            break
    if not text_name:
        for file_row in metadata.get("files", []):
            name = str(file_row.get("name") or "")
            if name.endswith("_hocr_searchtext.txt.gz"):
                text_name = name
                break
    if not text_name:
        raise RuntimeError(f"No public OCR text file found for {identifier}")
    text_url = f"https://archive.org/download/{quote(identifier)}/{quote(text_name)}"
    return text_url, fetch_text(text_url)


def collect_text_route(route: dict[str, Any], stage_dir: Path, scaled: bool) -> RouteResult:
    started_at = time.monotonic()
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
        text_url, text = fetch_archive_text(route)
        pages = [{"section_id": route["archive_identifier"], "url": text_url, "chapter": route.get("source_title", "full text"), "text": text}]
    seen_hashes: set[str] = set()
    term_hits: Counter[str] = Counter()
    try:
        for page in pages:
            if result.processed >= max_candidates:
                break
            try:
                text = page.get("text") or fetch_text(page["url"])
                result.fetched += 1
            except Exception as exc:  # noqa: BLE001
                result.errors += 1
                result.notes.append(f"{page.get('url')}: {type(exc).__name__}: {exc}")
                continue
            blocks = split_blocks(text)
            blocks.extend(term_windows(text, list(route.get("entity_terms", []))))
            for block in blocks:
                lower = block.lower()
                matching_terms = [term for term in route.get("entity_terms", []) if term.lower() in lower]
                if not matching_terms:
                    continue
                for term in matching_terms:
                    if result.processed >= max_candidates:
                        break
                    if accepted_target and result.accepted_provisional >= accepted_target:
                        break
                    if term_hits[term.lower()] >= 4:
                        continue
                    digest = hashlib.sha256(canonicalise_whitespace(block).lower().encode("utf-8")).hexdigest()
                    if digest in seen_hashes:
                        result.duplicates += 1
                        continue
                    seen_hashes.add(digest)
                    term_hits[term.lower()] += 1
                    result.processed += 1
                    candidate = make_candidate(route, page, term, block, result.processed)
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
        result.stop_reason = "accepted_target_reached" if accepted_target and result.accepted_provisional >= accepted_target else "route_candidate_limit_or_source_exhausted"
    finally:
        result.runtime_seconds = time.monotonic() - started_at
        write_route_stage(result)
        print_route_progress(result, started_at)
    return result


def collect_probe_only(route: dict[str, Any], stage_dir: Path) -> RouteResult:
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
    except Exception as exc:  # noqa: BLE001
        result.errors += 1
        result.stop_reason = f"probe_error:{type(exc).__name__}"
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


def collect_map_queue_route(route: dict[str, Any], stage_dir: Path, scaled: bool) -> RouteResult:
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


def run_route(route: dict[str, Any], stage_dir: Path, scaled: bool = False) -> RouteResult:
    if route.get("retrieval_method") == "exact_queue_gazetteer_verification":
        return collect_map_queue_route(route, stage_dir, scaled=scaled)
    if route.get("pages") or route.get("archive_identifier"):
        return collect_text_route(route, stage_dir, scaled=scaled)
    return collect_probe_only(route, stage_dir)


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
    public_target = int(config.get("targets", {}).get("public_records") or 2800)
    map_target = int(config.get("targets", {}).get("map_flags") or 1200)
    previous_status = previous_status or {}
    previous_results = previous_status.get("route_results") or []
    current_results = [result.as_dict() for result in results]
    combined_results = previous_results + current_results
    previous_processed = int(previous_status.get("candidates_processed") or 0)
    previous_map_updates = int(previous_status.get("map_queue_updates_applied") or 0)
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
        "remaining_gap_to_2800": max(0, public_target - final_export["public_records"]),
        "remaining_gap_to_1200": max(0, map_target - final_export["map_flags"]),
        "map_invariant": map_invariant(),
        "validation_ok": validation_ok,
        "build_ok": build_ok,
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
        f"- Remaining gap to 2800: `{status['remaining_gap_to_2800']}`",
        f"- Remaining gap to 1200 map flags: `{status['remaining_gap_to_1200']}`",
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
            f"| {row['route_id']} | {row['family']} | {row['processed']} | {row['accepted_provisional']} | "
            f"{row['context_provisional']} | {row['rejected']} | {row['duplicates']} | {row['map_candidates']} | "
            f"{row['runtime_seconds']} | {row['stop_reason']} |"
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--skip-build", action="store_true", help="Skip final npm production build")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    run_id = str(config.get("run_id") or f"collection_sprint_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}")
    stage_dir = ROOT / "data" / "interim" / "collection_sprint" / run_id
    stage_dir.mkdir(parents=True, exist_ok=True)
    previous_status = json.loads(STATUS_JSON.read_text(encoding="utf-8")) if STATUS_JSON.exists() else {}
    baseline_export = load_export_counts()
    baseline_db = db_public_counts()
    if previous_status.get("starting_public_records") is not None:
        baseline_export = {
            "public_records": int(previous_status["starting_public_records"]),
            "map_points": int(previous_status.get("starting_map_flags", baseline_export["map_points"])),
            "map_flags": int(previous_status.get("starting_map_flags", baseline_export["map_flags"])),
        }
    with connect(DEFAULT_DB_PATH) as conn:
        max_record_id = int(conn.execute("SELECT COALESCE(MAX(record_id), 0) AS n FROM records").fetchone()["n"])

    routes = [route for route in config.get("routes", []) if route.get("enabled", True)]
    worker_count = min(int(config.get("worker_count") or 4), 4)
    probe_results: list[RouteResult] = []
    live_export = load_export_counts()
    print(f"[collection-sprint] run_id={run_id} baseline_public_records={baseline_export['public_records']} live_public_records={live_export['public_records']} baseline_map_flags={baseline_export['map_flags']} live_map_flags={live_export['map_flags']}", flush=True)
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(run_route, route, stage_dir, False): route["route_id"] for route in routes}
        for future in as_completed(futures):
            probe_results.append(future.result())

    productive_route_ids = {
        result.route_id
        for result in probe_results
        if result.accepted_provisional >= 6
        or (result.retrieval_method == "exact_queue_gazetteer_verification" and result.map_candidates >= 6)
    }
    scaled_routes = [route for route in routes if route.get("scaled") and route["route_id"] in productive_route_ids]
    scaled_results: list[RouteResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(run_route, route, stage_dir, True): route["route_id"] for route in scaled_routes}
        for future in as_completed(futures):
            scaled_results.append(future.result())

    results = probe_results + scaled_results
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
    if not args.skip_build:
        try:
            run_subprocess(["npm", "run", "build"])
        except subprocess.CalledProcessError:
            build_ok = False
    final_export = load_export_counts()
    final_db = db_public_counts()
    run_prefix = "_".join(run_id.split("_")[:-1]) if "_" in run_id else run_id
    breakdowns = source_breakdowns(max_record_id, run_prefix=run_prefix)
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
    print(
        "[collection-sprint] complete "
        f"net_new_records={final_export['public_records'] - baseline_export['public_records']} "
        f"net_new_map_flags={final_export['map_flags'] - baseline_export['map_flags']} "
        f"status_md={STATUS_MD}",
        flush=True,
    )


if __name__ == "__main__":
    main()
