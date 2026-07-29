#!/usr/bin/env python3
"""Stage-only Wikidata entity crawl for AusFigures gap expansion.

This uses public no-key Wikidata APIs. It collects entity metadata only and
does not promote rows into production.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from crawl_public_books_metadata import FIELDNAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "wikidata_entities"
DEFAULT_OUTPUT = OUT_DIR / "wikidata_entities_round022_candidates.csv"
DEFAULT_RAW = OUT_DIR / "wikidata_entities_round022_raw.ndjson"
DEFAULT_REQUESTS = OUT_DIR / "wikidata_entities_round022_requests.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_wikidata_entities_round022.md"
USER_AGENT = "AusFiguresGapCrawler/0.4 public Wikidata metadata research"
WIKIDATA_API = "https://www.wikidata.org/w/api.php"


@dataclass(frozen=True)
class QueryFamily:
    family_id: str
    query: str
    terms: tuple[str, ...]
    narrative_type: str
    sensitivity: str = "standard_public_metadata_review"


QUERY_FAMILIES = [
    QueryFamily("wikidata_yowie", "Yowie", ("yowie",), "cryptid_style_apeman"),
    QueryFamily("wikidata_bunyip", "Bunyip", ("bunyip",), "other_supernatural_humanoid_or_adjacent"),
    QueryFamily("wikidata_fishers_ghost", "Fisher's Ghost", ("fisher's ghost", "fishers ghost"), "ghost_legend"),
    QueryFamily("wikidata_federici", "Frederick Federici ghost", ("federici", "princess theatre"), "ghost_legend"),
    QueryFamily("wikidata_port_arthur_ghost", "Port Arthur ghost", ("port arthur", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_monte_cristo_ghost", "Monte Cristo Homestead ghost", ("monte cristo", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_picton_tunnel_ghost", "Picton tunnel ghost", ("picton", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_fremantle_prison_ghost", "Fremantle Prison ghost", ("fremantle prison", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_old_melbourne_gaol_ghost", "Old Melbourne Gaol ghost", ("old melbourne gaol", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_beechworth_asylum_ghost", "Beechworth Asylum ghost", ("beechworth", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_willow_court_ghost", "Willow Court ghost", ("willow court", "ghost"), "ghost_legend"),
    QueryFamily("wikidata_quarantine_station_ghost", "North Head Quarantine Station ghost", ("quarantine station", "ghost"), "ghost_legend"),
    QueryFamily(
        "wikidata_public_indigenous_named_figures",
        "Mimih Quinkan Wandjina Pangkarlangu",
        ("mimih", "quinkan", "wandjina", "pangkarlangu"),
        "traditional_narrative",
        "indigenous_related_public_metadata_human_review_required",
    ),
]

AUSTRALIA_RE = re.compile(
    r"\b(australia|australian|aboriginal|indigenous|new south wales|queensland|victoria|tasmania|"
    r"south australia|western australia|northern territory|melbourne|sydney|brisbane|adelaide|perth|"
    r"hobart|canberra|campbelltown|port arthur|picton|fremantle|beechworth|monte cristo|"
    r"princess theatre|old melbourne gaol|willow court|quarantine station)\b",
    re.I,
)

SUPERNATURAL_RE = re.compile(
    r"\b(yowies?|bunyips?|ghosts?|haunted|haunting|apparitions?|phantoms?|fisher'?s ghost|"
    r"fishers ghost|federici|mimih?|quinkan|wandjina|pangkarlangu)\b",
    re.I,
)

INDIGENOUS_RE = re.compile(r"\b(aboriginal|indigenous|mimih?|quinkan|wandjina|pangkarlangu|dreaming|dreamtime)\b", re.I)
NOISE_RE = re.compile(r"\b(song|album|video game|software|rugby|football|school|company|surname)\b", re.I)
PLACE_ONLY_RE = re.compile(
    r"\b(suburb|bay|mountain|hill|rockhole|point|reserve|town|railway station|station|protected area|"
    r"parish|river|locality|post office|substation|dam|park|weir|swamp|plan of management|"
    r"shire|lga|county)\b",
    re.I,
)
ENTITY_CONTEXT_RE = re.compile(
    r"\b(creature|mythical|mythology|folklore|legend|ghost story|ghost|haunted|haunting|"
    r"apparition|operetta|film|story|newspaper|public text)\b",
    re.I,
)
CREATURE_CONTEXT_RE = re.compile(r"\b(creature|mythical|mythology|folklore|legend)\b", re.I)
FISHERS_CONTEXT_RE = re.compile(r"\b(ghost story|ghost|film|operetta|story)\b", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def fetch_json(params: dict[str, str], timeout: int) -> dict[str, Any]:
    url = WIKIDATA_API + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def search_entities(query: str, limit: int, timeout: int) -> dict[str, Any]:
    return fetch_json(
        {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": str(limit),
        },
        timeout,
    )


def get_entities(ids: list[str], timeout: int) -> dict[str, Any]:
    return fetch_json(
        {
            "action": "wbgetentities",
            "ids": "|".join(ids),
            "props": "labels|descriptions|claims|sitelinks",
            "languages": "en",
            "format": "json",
        },
        timeout,
    )


def label(entity: dict[str, Any], field: str) -> str:
    value = entity.get(field)
    if isinstance(value, dict):
        en = value.get("en")
        if isinstance(en, dict):
            return clean(en.get("value"))
    return ""


def coordinate(entity: dict[str, Any]) -> tuple[str, str]:
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    for claim in claims.get("P625", []):
        value = (((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")) or {}
        if isinstance(value, dict) and "latitude" in value and "longitude" in value:
            return str(value["latitude"]), str(value["longitude"])
    return "", ""


def country_is_australia(entity: dict[str, Any]) -> bool:
    claims = entity.get("claims") if isinstance(entity.get("claims"), dict) else {}
    for prop in ("P17", "P131", "P495"):
        for claim in claims.get(prop, []):
            value = (((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value")) or {}
            if isinstance(value, dict) and value.get("id") == "Q408":
                return True
    return False


def sitelink_title(entity: dict[str, Any]) -> str:
    sitelinks = entity.get("sitelinks") if isinstance(entity.get("sitelinks"), dict) else {}
    enwiki = sitelinks.get("enwiki") if isinstance(sitelinks.get("enwiki"), dict) else {}
    return clean(enwiki.get("title"))


def existing_keys(frontend: Path) -> tuple[set[str], set[str]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    urls: set[str] = set()
    external_ids: set[str] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(url)
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
    return urls, external_ids


def classify(entity_id: str, entity: dict[str, Any], family: QueryFamily, duplicate_keys: tuple[set[str], set[str]]) -> dict[str, Any]:
    title = label(entity, "labels") or entity_id
    desc = label(entity, "descriptions")
    wiki_title = sitelink_title(entity)
    text = clean(" ".join([title, desc, wiki_title, family.query]))
    lat, lon = coordinate(entity)
    url = f"https://www.wikidata.org/wiki/{entity_id}"
    external_id = f"wikidata:{entity_id}"
    urls, external_ids = duplicate_keys
    status = "accepted"
    rejection = ""
    if external_id in external_ids or url.lower() in urls:
        status = "duplicate_existing_record"
        rejection = "duplicate_against_current_overlay"
    elif NOISE_RE.search(text):
        status = "rejected"
        rejection = "noise_pattern"
    elif PLACE_ONLY_RE.search(text) and not ENTITY_CONTEXT_RE.search(text):
        status = "rejected"
        rejection = "place_name_only_same_word_match"
    elif not any(term in text.lower() for term in family.terms):
        status = "rejected"
        rejection = "missing_required_family_term"
    elif not (country_is_australia(entity) or AUSTRALIA_RE.search(text)):
        status = "rejected"
        rejection = "missing_australia_context"
    elif not (SUPERNATURAL_RE.search(text) or family.family_id.startswith("wikidata_public_indigenous")):
        status = "lead_only"
        rejection = "weak_supernatural_context"
    elif family.family_id in {"wikidata_yowie", "wikidata_bunyip"} and not CREATURE_CONTEXT_RE.search(text):
        status = "rejected"
        rejection = "same_name_cultural_or_place_entity_without_creature_context"
    elif family.family_id == "wikidata_fishers_ghost" and not FISHERS_CONTEXT_RE.search(text):
        status = "rejected"
        rejection = "fishers_ghost_without_story_context"

    risk_flags = []
    if INDIGENOUS_RE.search(text) or family.sensitivity.startswith("indigenous_related"):
        risk_flags.append("indigenous_related_public_metadata_human_review_required")

    if status == "accepted" and family.sensitivity.startswith("indigenous_related"):
        status = "lead_only"
        rejection = "indigenous_related_wikidata_entity_requires_manual_review"

    source_label = (SUPERNATURAL_RE.search(text).group(0).lower().replace(" ", "_") if SUPERNATURAL_RE.search(text) else "wikidata_entity")
    raw = {"entity_id": entity_id, "query_family_id": family.family_id, "query": family.query, "wiki_title": wiki_title}
    return {
        "candidate_status": status,
        "source_name": "Wikidata",
        "source_type": "public_wikidata_entity_metadata",
        "source_tier": "public_metadata",
        "query_family_id": family.family_id,
        "query_string": family.query,
        "abc_hit_id": "",
        "title": f"Wikidata entity: {title}",
        "publication_or_organisation": "Wikidata",
        "publication_date_text": "Undated public entity metadata",
        "year": "",
        "date_scope": "undated_entity_record",
        "access_date": date.today().isoformat(),
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_wikidata_metadata",
        "rights_access_status": "public_metadata_only_no_full_text_reproduction",
        "narrative_type": family.narrative_type,
        "secondary_role": "public_entity_metadata_cross_source_record",
        "australian_relation": "Public Wikidata entity metadata with Australia context.",
        "humanoid_basis": "wikidata_public_entity_metadata_requires_review",
        "source_label": source_label,
        "matched_terms": ";".join(sorted({match.group(0).lower() for match in SUPERNATURAL_RE.finditer(text)})),
        "matched_place": title,
        "location_text": title if lat and lon else "",
        "location_role": "wikidata_coordinate_display_location" if lat and lon else "",
        "latitude": lat,
        "longitude": lon,
        "location_precision": "wikidata_coordinate" if lat and lon else "",
        "geocode_source": "wikidata_P625_coordinate" if lat and lon else "",
        "geocode_verification_status": "public_wikidata_coordinate_unreviewed" if lat and lon else "",
        "coordinate_evidence_note": "Coordinates from Wikidata P625; public display point only, not habitat/proof." if lat and lon else "",
        "duplicate_check_status": "checked_against_current_overlay_url_external_id",
        "quality_class": "B" if lat and lon else "C",
        "ethics_review_status": "needs_human_ethics_review" if risk_flags else "public_metadata_context_reviewed",
        "cultural_sensitivity": "high_public_source_summary_only" if risk_flags else "low",
        "risk_flags": ";".join(risk_flags),
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": rejection,
        "evidence_summary": text[:900],
        "raw_metadata_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def write_rows_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(path: Path, rows: list[dict[str, Any]], requests: list[dict[str, Any]], output: Path) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    family_counts = Counter(row["query_family_id"] for row in rows if row["candidate_status"] == "accepted")
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    lines = [
        "# 1926-2011 Wikidata Entity Crawl",
        "",
        "Stage-only public entity metadata crawl. These rows are not production imports.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate CSV: `{output.resolve().relative_to(ROOT)}`",
        f"- Requests: `{len(requests)}`",
        f"- Rows written: `{len(rows)}`",
        f"- Accepted candidates: `{status_counts.get('accepted', 0)}`",
        f"- Accepted with Wikidata coordinates: `{mapped}`",
        "",
        "## Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted By Query Family"])
    for key, count in family_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Request Outcomes"])
    for key, count in Counter(row["status"] for row in requests).most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes"])
    lines.append("- Wikidata rows are undated entity records and should not be used as annual trend evidence.")
    lines.append("- Coordinates are public display coordinates only.")
    lines.append("- Indigenous-related entities are held as lead-only/manual review unless separately approved.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--requests-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.8)
    args = parser.parse_args()

    duplicate_keys = existing_keys(args.frontend)
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for family in QUERY_FAMILIES:
        try:
            payload = search_entities(family.query, args.limit, args.timeout)
            search_rows = payload.get("search") or []
            ids = [row.get("id") for row in search_rows if row.get("id")]
            request_rows.append({"query_family_id": family.family_id, "query": family.query, "request_type": "search", "status": "ok", "items": len(ids)})
        except Exception as exc:  # noqa: BLE001
            request_rows.append({"query_family_id": family.family_id, "query": family.query, "request_type": "search", "status": f"error:{type(exc).__name__}:{clean(str(exc))[:120]}", "items": 0})
            time.sleep(args.delay)
            continue
        time.sleep(args.delay)
        for offset in range(0, len(ids), 50):
            chunk = [entity_id for entity_id in ids[offset : offset + 50] if entity_id not in seen]
            if not chunk:
                continue
            for entity_id in chunk:
                seen.add(entity_id)
            try:
                payload = get_entities(chunk, args.timeout)
                entities = payload.get("entities") or {}
                request_rows.append({"query_family_id": family.family_id, "query": family.query, "request_type": "entities", "status": "ok", "items": len(entities)})
                for entity_id, entity in entities.items():
                    raw_rows.append({"query_family_id": family.family_id, "entity_id": entity_id, "raw": entity})
                    rows.append(classify(entity_id, entity, family, duplicate_keys))
            except Exception as exc:  # noqa: BLE001
                request_rows.append({"query_family_id": family.family_id, "query": family.query, "request_type": "entities", "status": f"error:{type(exc).__name__}:{clean(str(exc))[:120]}", "items": 0})
            time.sleep(args.delay)

    write_csv(args.output, rows)
    write_ndjson(args.raw_output, raw_rows)
    write_rows_csv(args.requests_output, ["query_family_id", "query", "request_type", "status", "items"], request_rows)
    write_report(args.report, rows, request_rows, args.output)
    status_counts = Counter(row["candidate_status"] for row in rows)
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    print(f"Wrote Wikidata entity candidates: {args.output}")
    print(f"Rows: {len(rows)}")
    print(f"Accepted: {status_counts.get('accepted', 0)}")
    print(f"Mapped accepted: {mapped}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
