#!/usr/bin/env python3
"""Stage-only ABC public search crawl for the post-1926 gap.

This is intentionally not an ingestion script. It queries the public ABC
Algolia index, classifies public metadata/snippet hits, marks duplicates
against the current frontend export, and writes reviewable candidate files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.json"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_abc_public_search_round.md"

USER_AGENT = "AusFiguresGapCrawler/0.3 public metadata research"
ABC_APP_ID = "Y63Q32NVDL"
ABC_API_KEY = "bcdf11ba901b780dc3c0a3ca677fbefc"
ABC_INDEX = "ABC_production_all"

STATE_NAMES = {
    "NSW": "New South Wales",
    "QLD": "Queensland",
    "VIC": "Victoria",
    "TAS": "Tasmania",
    "SA": "South Australia",
    "WA": "Western Australia",
    "NT": "Northern Territory",
    "ACT": "Australian Capital Territory",
}

STOP_PLACE_NAMES = {
    "",
    "Australia",
    "New South Wales",
    "Queensland",
    "Victoria",
    "Tasmania",
    "South Australia",
    "Western Australia",
    "Northern Territory",
    "Australian Capital Territory",
    "NSW",
    "QLD",
    "VIC",
    "TAS",
    "SA",
    "WA",
    "NT",
    "ACT",
}

HIGH_VALUE_PLACE_HINTS = {
    "adelaide arcade",
    "adelaide gaol",
    "beechworth asylum",
    "blundells cottage",
    "braidwood",
    "burnie arts",
    "burnie civic",
    "fremantle prison",
    "hotel kurrajong",
    "isle of the dead",
    "j ward",
    "junee",
    "majestic theatre",
    "monte cristo",
    "national film and sound archive",
    "nfsa",
    "old melbourne gaol",
    "picton",
    "port arthur",
    "princess theatre",
    "quarantine station",
    "sirius building",
    "the rocks",
    "willow court",
    "z ward",
}

SUPPLEMENTAL_PLACES = [
    {
        "name": "Picton",
        "state": "NSW",
        "aliases": ["Picton"],
        "lat": -34.1689,
        "lon": 150.6110,
        "precision": "town",
        "role": "legend_associated_place",
    },
    {
        "name": "Lake George",
        "state": "NSW",
        "aliases": ["Lake George"],
        "lat": -35.1120,
        "lon": 149.3910,
        "precision": "named_feature",
        "role": "reported_place",
    },
]

SUPERNATURAL_RE = re.compile(
    r"\b(ghosts?|ghost stories?|ghost tours?|haunted|haunting|apparitions?|"
    r"phantoms?|spectral|spectres?|spirits?|spooks?|blue lady|white lady|"
    r"grey lady|resident ghost|yowies?|yahoo|hairy man|hairy men|hairy people|"
    r"wild man|wild men|mimih?|mimi spirits?|spirit people|supernatural|"
    r"paranormal|ghostly|lost souls?|enraged spirits?)\b",
    re.I,
)

STRONG_RE = re.compile(
    r"\b(ghosts?|ghost stories?|ghost tours?|haunted (?:house|houses|homestead|"
    r"place|places|site|sites|gaol|jail|asylum|hospital|hotel|theatre|"
    r"cemetery|property|building|town|mansion)|apparitions?|phantoms?|spectres?|"
    r"spooks?|blue lady|white lady|grey lady|resident ghost|yowies?|yahoo|"
    r"hairy man|hairy men|hairy people|wild man|wild men|mimih?|mimi spirits?|"
    r"spirit people|ghostly|lost souls?|enraged spirits?)\b",
    re.I,
)

SKIP_RE = re.compile(
    r"\b(ghost writer|ghostwriter|ghost net|ghost nets|ghost gum|ghost gear|"
    r"ghost bat|ghost shark|ghost mushroom|ghost reef|ghost town only|"
    r"ghost of (?:a chance|workchoices|rudd|christmas past|the past)|"
    r"ghosts? of social media|snapchat|video game|film review|book review|"
    r"qantas|science show|passwords?|woodfires?|asthma|bioluminescence|"
    r"ghost-like|ghost theatre|political parties|federal election|"
    r"plumber'?s crack|hairy people in the basement|wild man of australian "
    r"(?:sport|jazz|design)|frontman .* wild man|koori knockout|rugby league|"
    r"grand final|newcastle yowies|kidslisten|stowaway snooze|weird things "
    r"called people)\b",
    re.I,
)

INDIGENOUS_RE = re.compile(
    r"\b(aboriginal|indigenous|first nations|torres strait|dreaming|dreamtime|"
    r"noongar|yanyuwa|jawoyn|mimih?|mimi spirits?|spirit people|hairy people|"
    r"yuuri|cleverman|fanny balbuk)\b",
    re.I,
)

CRYPTID_CONTEXT_RE = re.compile(
    r"\b(yowies?|yahoo|bigfoot|bunyips?|creatures?|monsters?|myths?|mythical|"
    r"legends?|folklore|cryptid|sightings?|encounters?|pangkarlangu|"
    r"indigenous|aboriginal|cleverman|spirit people|mimih?|mimi spirits?)\b",
    re.I,
)

YOWIE_SCOPE_RE = re.compile(
    r"\b(bigfoot|bunyips?|creatures?|monsters?|myths?|mythical|legends?|"
    r"folklore|cryptid|cryptobiology|sightings?|encounters?|hunters?|"
    r"half-ape|half-human|unknown animal|reports? of|rumou?red|prove "
    r"existence|mythological beasts?)\b",
    re.I,
)

ENTERTAINMENT_ONLY_RE = re.compile(
    r"\b(iview|episode|cartoon|animation|garage rock|jazz pianist|graphic design|"
    r"sportsman|afl creator|music feature|new leg|book'?s popularity|career building)\b",
    re.I,
)

FIELDNAMES = [
    "candidate_status",
    "source_name",
    "source_type",
    "source_tier",
    "query_family_id",
    "query_string",
    "abc_hit_id",
    "title",
    "publication_or_organisation",
    "publication_date_text",
    "year",
    "date_scope",
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
    "matched_terms",
    "matched_place",
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
    "risk_flags",
    "acceptance_decision",
    "rejection_reason",
    "evidence_summary",
    "raw_metadata_json",
]

QUERY_FAMILIES = [
    {
        "id": "abc_yowie_hairy_man",
        "queries": [
            "yowie",
            '"hairy man" Australia',
            '"hairy people" Australia',
            '"Yahoo" "hairy man"',
            '"Australian gorilla"',
            '"wild man" Australia',
        ],
    },
    {
        "id": "abc_ghost_haunted_places",
        "queries": [
            '"ghost stories" Australia',
            '"haunted places" Australia',
            '"most haunted" Australia',
            '"resident ghost" Australia',
            '"ghost tours" Australia',
            '"apparition" Australia',
        ],
    },
    {
        "id": "abc_known_place_gap_terms",
        "queries": [
            '"Port Arthur" ghost',
            '"Monte Cristo" ghost',
            '"Picton" ghost',
            '"Adelaide Gaol" ghost',
            '"Old Melbourne Gaol" ghost',
            '"Fremantle Prison" ghost',
            '"Beechworth Asylum" ghost',
            '"Quarantine Station" ghost',
            '"Willow Court" ghost',
            '"Princess Theatre" ghost',
            '"Burnie" ghost stories',
            '"Sirius building" ghost',
            '"Blundells Cottage" ghost',
            '"Hotel Kurrajong" ghost',
            '"National Film and Sound Archive" ghost',
            '"J Ward" ghost',
            '"Majestic Theatre" ghost',
            '"Z Ward" ghost',
        ],
    },
    {
        "id": "abc_public_indigenous_named_figures",
        "queries": [
            '"mimih" ABC',
            '"mimi spirit" ABC',
            '"spirit people" ABC Australia',
            '"hairy people" Cleverman',
            '"yuuri men"',
            '"Indigenous ghost stories" ABC',
        ],
    },
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def compact_id(value: str, length: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:length].strip("-") or "item"


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            parts.extend(flatten_strings(item))
        return parts
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if key in {"value", "matchLevel", "matchedWords", "fullyHighlighted"}:
                parts.extend(flatten_strings(item))
            elif key.startswith("_"):
                continue
            else:
                parts.extend(flatten_strings(item))
        return parts
    return []


def hit_text(hit: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "title",
        "titleAlt",
        "synopsis",
        "caption",
        "description",
        "summary",
        "transcript",
        "programTitle",
        "ABCSEARCH_programTitle",
    ):
        parts.extend(flatten_strings(hit.get(key)))
    keywords = hit.get("keywords")
    if isinstance(keywords, list):
        parts.extend(str(keyword) for keyword in keywords)
    highlight = hit.get("_highlightResult")
    if isinstance(highlight, dict):
        parts.extend(flatten_strings(highlight))
    return clean(" ".join(parts))


def publication_date(hit: dict[str, Any]) -> str:
    dates = hit.get("dates") if isinstance(hit.get("dates"), dict) else {}
    for key in ("displayPublished", "published", "availableFrom", "updated"):
        value = dates.get(key) or hit.get(key)
        if value:
            match = re.search(r"(19|20)\d{2}(?:-\d{2}-\d{2})?", str(value))
            if match:
                return match.group(0)
    text = hit_text(hit)
    match = re.search(r"\b(19[2-9]\d|20[0-2]\d)\b", text)
    return match.group(1) if match else ""


def year_from_date(value: str) -> int | None:
    match = re.search(r"\b(19[2-9]\d|20[0-2]\d)\b", value or "")
    if not match:
        return None
    return int(match.group(1))


def source_label(text: str) -> str:
    match = STRONG_RE.search(text) or SUPERNATURAL_RE.search(text)
    return clean(match.group(0)).lower().replace(" ", "_") if match else "reported_supernatural_figure"


def narrative_type(label: str) -> str:
    if any(term in label for term in ("yowie", "yahoo", "hairy", "wild_man")):
        return "cryptid_style_apeman"
    if any(term in label for term in ("mimih", "mimi", "spirit_people", "yuuri")):
        return "traditional_narrative"
    if "haunted" in label or "ghost" in label:
        return "ghost_legend"
    return "apparition_account"


def ambiguous_hairy_or_wild(label: str, text: str, has_place: bool) -> bool:
    if not any(term in label for term in ("hairy", "wild_man", "wild men", "hairy_people")):
        return False
    if CRYPTID_CONTEXT_RE.search(text):
        return False
    if has_place and "wild man" not in label:
        return False
    return True


def unmapped_scope_allowed(family_id: str, label: str, text: str) -> bool:
    if family_id == "abc_public_indigenous_named_figures" and INDIGENOUS_RE.search(text):
        return True
    if any(term in label for term in ("yowie", "yahoo", "hairy")) and (
        YOWIE_SCOPE_RE.search(text) or ("hairy_people" in label and INDIGENOUS_RE.search(text))
    ):
        return True
    if any(term in label for term in ("ghost", "haunted", "apparition", "phantom")) and re.search(
        r"\b(australia'?s most haunted|australian ghost stories|"
        r"urban legends|indigenous ghost stories|real life indigenous ghost stories|"
        r"haunted places in australia|spooky stories of aboriginal australia|"
        r"the darkside|great australian ghost stories)\b",
        text,
        re.I,
    ):
        return True
    return False


def entertainment_only(label: str, text: str, has_place: bool) -> bool:
    if has_place:
        return False
    if "yowie" in label and re.search(r"\b(myths?|mythical|legends?|folklore|cryptid|bunyips?|sightings?|encounters?)\b", text, re.I):
        return False
    return bool(ENTERTAINMENT_ONLY_RE.search(text))


def date_scope(year: int | None) -> str:
    if year is None:
        return "undated"
    if 1926 <= year <= 2011:
        return "gap_window_1926_2011"
    if year >= 2012:
        return "post_gap_after_2011"
    return "pre_gap_before_1926"


def evidence_window(text: str, place_alias: str | None = None, radius: int = 520) -> str:
    matches = list(STRONG_RE.finditer(text)) or list(SUPERNATURAL_RE.finditer(text))
    place_match = re.search(r"\b" + re.escape(place_alias) + r"\b", text, re.I) if place_alias else None
    anchors = [m.start() for m in matches]
    if place_match:
        anchors.append(place_match.start())
    if not anchors:
        return clean(text[:900])
    center = min(anchors)
    start = max(0, center - radius)
    end = min(len(text), center + radius)
    return clean(text[start:end])[:900]


def abc_query(query: str, page: int, hits_per_page: int, timeout: int) -> dict[str, Any]:
    params = urlencode(
        {
            "query": query,
            "hitsPerPage": str(hits_per_page),
            "page": str(page),
            "ruleContexts": '["global_search"]',
        }
    )
    request = Request(
        f"https://{ABC_APP_ID}-dsn.algolia.net/1/indexes/{ABC_INDEX}/query",
        data=json.dumps({"params": params}).encode("utf-8"),
        headers={
            "X-Algolia-API-Key": ABC_API_KEY,
            "X-Algolia-Application-Id": ABC_APP_ID,
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def place_aliases(name: str) -> list[str]:
    aliases = [name]
    if "," in name:
        aliases.append(name.split(",", 1)[0].strip())
    return [alias for alias in aliases if alias and alias not in STOP_PLACE_NAMES]


def add_place(catalog: dict[str, dict[str, Any]], row: dict[str, Any]) -> None:
    name = clean(row.get("name") or row.get("map_place_name") or row.get("location_text") or "")
    state = clean(row.get("state") or row.get("state_territory") or "")
    lat = row.get("lat") or row.get("latitude") or row.get("map_latitude")
    lon = row.get("lon") or row.get("longitude") or row.get("map_longitude")
    if not name or name in STOP_PLACE_NAMES or lat in (None, "") or lon in (None, ""):
        return
    short = name.split(",", 1)[0].strip()
    low = short.lower()
    precision = clean(row.get("location_precision") or row.get("map_location_type") or row.get("location_precision_status"))
    if low not in HIGH_VALUE_PLACE_HINTS and precision not in {"exact_site", "named_feature", "building", "town", "locality"}:
        return
    if low in {"sydney", "melbourne", "brisbane", "perth", "adelaide", "hobart", "darwin", "canberra"}:
        return
    key = norm(f"{short} {state}")
    if key in catalog:
        return
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return
    catalog[key] = {
        "name": short,
        "state": state,
        "aliases": place_aliases(name),
        "lat": lat_f,
        "lon": lon_f,
        "precision": precision or "reviewed_place",
        "role": clean(row.get("location_role") or row.get("map_location_role") or "reported_place"),
    }


def load_place_catalog(frontend_path: Path) -> list[dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    data = load_json(frontend_path)
    for record in data.get("records", []):
        if record.get("has_strict_map_point"):
            add_place(catalog, record)
    for csv_path in (ROOT / "data" / "interim" / "collection_sprint").glob("**/*.csv"):
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get("candidate_status") == "accepted":
                        add_place(catalog, row)
        except OSError:
            continue
    for place in SUPPLEMENTAL_PLACES:
        key = norm(f"{place['name']} {place.get('state', '')}")
        catalog.setdefault(key, place)
    priority = []
    other = []
    for place in catalog.values():
        alias_blob = " ".join(place.get("aliases") or []).lower()
        if any(hint in alias_blob for hint in HIGH_VALUE_PLACE_HINTS):
            priority.append(place)
        else:
            other.append(place)
    # Broad locality matching created many false map points in ABC search
    # snippets because Australian surnames and place names collide. Keep this
    # crawler on exact/high-value places; broader geocoding belongs in human
    # review or a source-specific route.
    return sorted(priority, key=lambda row: row["name"])


def match_place(text: str, places: list[dict[str, Any]], query: str) -> tuple[dict[str, Any] | None, str]:
    query_norm = norm(query)
    for place in places:
        aliases = place.get("aliases") or [place["name"]]
        for alias in aliases:
            alias_clean = clean(alias)
            if len(alias_clean) < 4:
                continue
            if re.search(r"\b" + re.escape(alias_clean) + r"\b", text, re.I):
                if place["name"].lower() in {"junee", "picton", "braidwood", "york", "hobart"} and norm(place["name"]) not in query_norm:
                    continue
                return place, alias_clean
    return None, ""


def existing_keys(frontend_path: Path) -> tuple[set[str], set[tuple[str, str]], set[str]]:
    data = load_json(frontend_path)
    urls: set[str] = set()
    url_places: set[tuple[str, str]] = set()
    external_ids: set[str] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(url)
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
        place_bits = [
            clean(record.get("map_place_name")),
            clean(record.get("location_summary")).split("(")[0].strip(),
            clean(record.get("title")),
            clean(record.get("snippet")),
        ]
        for bit in place_bits[:2]:
            if url and bit:
                url_places.add((url, norm(bit.split(",", 1)[0])))
        for place in HIGH_VALUE_PLACE_HINTS:
            if url and place in " ".join(place_bits).lower():
                url_places.add((url, norm(place)))
    return urls, url_places, external_ids


def is_duplicate(url: str, external_id: str, place_name: str, keys: tuple[set[str], set[tuple[str, str]], set[str]]) -> bool:
    urls, url_places, external_ids = keys
    url_key = url.lower()
    if external_id in external_ids:
        return True
    if place_name:
        return (url_key, norm(place_name)) in url_places
    return url_key in urls


def build_queries(max_place_queries: int) -> list[tuple[str, str]]:
    queries: list[tuple[str, str]] = []
    for family in QUERY_FAMILIES:
        for query in family["queries"]:
            queries.append((family["id"], query))
    place_queries = []
    for hint in sorted(HIGH_VALUE_PLACE_HINTS):
        if len(hint) >= 5:
            place_queries.extend(
                [
                    ("abc_place_specific_harvest", f'"{hint}" ghost'),
                    ("abc_place_specific_harvest", f'"{hint}" haunted'),
                ]
            )
    queries.extend(place_queries[:max_place_queries])
    seen = set()
    unique = []
    for family_id, query in queries:
        key = (family_id, query.lower())
        if key not in seen:
            seen.add(key)
            unique.append((family_id, query))
    return unique


def classify_hit(
    family_id: str,
    query: str,
    hit: dict[str, Any],
    places: list[dict[str, Any]],
    duplicate_keys: tuple[set[str], set[tuple[str, str]], set[str]],
    year_start: int,
    year_end: int,
) -> dict[str, Any]:
    text = hit_text(hit)
    title = clean(hit.get("title") or hit.get("titleAlt") or "ABC public record")
    url = clean(hit.get("canonicalURL") or hit.get("url") or "")
    hit_id = clean(hit.get("id") or hit.get("objectID") or hashlib.sha1(url.encode()).hexdigest()[:16])
    pub_date = publication_date(hit)
    year = year_from_date(pub_date)
    label = source_label(text)
    place, alias = match_place(text, places, query)
    evidence = evidence_window(text, alias or None)
    matched_terms = sorted({clean(match.group(0)).lower() for match in SUPERNATURAL_RE.finditer(text)})
    risk_flags = []
    if INDIGENOUS_RE.search(text):
        risk_flags.append("indigenous_related_public_source_summary_only")
    rejection = ""
    status = "accepted"
    if not url or "abc.net.au" not in url:
        status = "rejected"
        rejection = "non_abc_or_missing_url"
    elif not year or year < year_start or year > year_end:
        status = "lead_only"
        rejection = "outside_requested_year_range_or_undated"
    elif SKIP_RE.search(text):
        status = "rejected"
        rejection = "noise_pattern"
    elif not STRONG_RE.search(text):
        status = "lead_only"
        rejection = "weak_supernatural_context"
    elif ambiguous_hairy_or_wild(label, text, bool(place)):
        status = "rejected"
        rejection = "ambiguous_hairy_or_wild_person_phrase"
    elif entertainment_only(label, text, bool(place)):
        status = "lead_only"
        rejection = "entertainment_or_fiction_context_without_place_review"
    elif not place and family_id in {"abc_known_place_gap_terms", "abc_place_specific_harvest"}:
        status = "lead_only"
        rejection = "no_reviewed_place_match"
    elif not place and not unmapped_scope_allowed(family_id, label, text):
        status = "lead_only"
        rejection = "no_reviewed_place_or_scope_anchor"
    external_place = compact_id(place["name"] if place else label, 24)
    external_id = f"abc-gap:{hit_id}:{external_place}"
    duplicate = is_duplicate(url, external_id, place["name"] if place else "", duplicate_keys)
    if status == "accepted" and duplicate:
        status = "duplicate_existing_record"
        rejection = "duplicate_against_frontend_export"
    culture = "high_public_source_summary_only" if risk_flags else "low"
    ethics = "needs_human_ethics_review" if risk_flags else "public_media_context_reviewed"
    raw = {
        "abc_hit_id": hit_id,
        "query_family_id": family_id,
        "query": query,
        "objectID": hit.get("objectID"),
        "date_scope": date_scope(year),
    }
    return {
        "candidate_status": status,
        "source_name": "Australian Broadcasting Corporation",
        "source_type": "institutional_media_page",
        "source_tier": "A",
        "query_family_id": family_id,
        "query_string": query,
        "abc_hit_id": hit_id,
        "title": title,
        "publication_or_organisation": clean(hit.get("programTitle") or hit.get("ABCSEARCH_programTitle") or "ABC"),
        "publication_date_text": pub_date,
        "year": year or "",
        "date_scope": date_scope(year),
        "access_date": date.today().isoformat(),
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_media_page",
        "rights_access_status": "public_access_short_excerpt_only",
        "narrative_type": narrative_type(label),
        "secondary_role": "abc_public_search_gap_candidate",
        "australian_relation": "ABC public media/education/listen metadata hit collected as a post-1926 gap candidate.",
        "humanoid_basis": "explicit_supernatural_or_anomalous_person_form_agent" if matched_terms else "needs_review",
        "source_label": label,
        "matched_terms": ";".join(matched_terms),
        "matched_place": alias,
        "location_text": f"{place['name']}, {place.get('state', '')}".strip(", ") if place else "",
        "location_role": place.get("role", "") if place else "",
        "latitude": place.get("lat", "") if place else "",
        "longitude": place.get("lon", "") if place else "",
        "location_precision": place.get("precision", "") if place else "",
        "geocode_source": "existing_frontend_or_stage_place_catalog" if place else "",
        "geocode_verification_status": "reviewed_place_catalog_match" if place else "",
        "coordinate_evidence_note": (
            f"ABC search text matched `{alias}`; coordinates reused from existing reviewed frontend/stage place catalog."
            if place
            else ""
        ),
        "duplicate_check_status": "checked_against_frontend_url_place_and_external_id",
        "quality_class": "B" if status == "accepted" and place else "C",
        "ethics_review_status": ethics,
        "cultural_sensitivity": culture,
        "risk_flags": ";".join(risk_flags),
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": rejection,
        "evidence_summary": evidence,
        "raw_metadata_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def write_ndjson(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(path: Path, rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]], output_csv: Path) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    family_counts = Counter(row["query_family_id"] for row in rows if row["candidate_status"] == "accepted")
    scope_counts = Counter(row["date_scope"] for row in rows if row["candidate_status"] == "accepted")
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    lines = [
        "# 1926-2011 ABC Public Search Crawl",
        "",
        "Stage-only crawl. These are review candidates, not production imports.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate CSV: `{output_csv.relative_to(ROOT)}`",
        f"- Requests: `{len(summary_rows)}`",
        f"- Rows written: `{len(rows)}`",
        f"- Accepted new candidates: `{status_counts.get('accepted', 0)}`",
        f"- Accepted with reviewed place coordinates: `{mapped}`",
        f"- Duplicate against current frontend: `{status_counts.get('duplicate_existing_record', 0)}`",
        f"- Lead-only / weak or undated: `{status_counts.get('lead_only', 0)}`",
        f"- Rejected: `{status_counts.get('rejected', 0)}`",
        "",
        "## Accepted By Query Family",
    ]
    for key, count in family_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted By Date Scope"])
    for key, count in scope_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Request Summary"])
    lines.append("| query_family | query | page | hits | rows | accepted | duplicates | error |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|")
    for row in summary_rows:
        lines.append(
            f"| {row['query_family_id']} | {row['query_string']} | {row['page']} | "
            f"{row['hits']} | {row['rows']} | {row['accepted']} | {row['duplicates']} | {row.get('error', '')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-data", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--round-id", default="round001")
    parser.add_argument("--year-start", type=int, default=1926)
    parser.add_argument("--year-end", type=int, default=2026)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--hits-per-page", type=int, default=20)
    parser.add_argument("--max-queries", type=int, default=80)
    parser.add_argument("--max-place-queries", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=0.75)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    places = load_place_catalog(args.frontend_data)
    duplicate_keys = existing_keys(args.frontend_data)
    queries = build_queries(args.max_place_queries)[: args.max_queries]
    rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    seen_output_keys: set[tuple[str, str]] = set()
    for query_index, (family_id, query) in enumerate(queries, start=1):
        for page in range(args.pages):
            error = ""
            try:
                payload = abc_query(query, page, args.hits_per_page, args.timeout)
                hits = payload.get("hits") or []
            except Exception as exc:  # noqa: BLE001
                hits = []
                error = f"{type(exc).__name__}: {exc}"
                print(
                    f"[abc-gap-crawl] {query_index}/{len(queries)} page={page + 1}/{args.pages} "
                    f"query={query!r} error={error}",
                    flush=True,
                )
            before = len(rows)
            accepted_before = sum(1 for row in rows if row["candidate_status"] == "accepted")
            dup_before = sum(1 for row in rows if row["candidate_status"] == "duplicate_existing_record")
            for hit in hits:
                row = classify_hit(family_id, query, hit, places, duplicate_keys, args.year_start, args.year_end)
                dedupe_key = (row["canonical_url"], norm(row["location_text"] or row["source_label"]))
                if row["candidate_status"] == "accepted" and dedupe_key in seen_output_keys:
                    row["candidate_status"] = "duplicate_existing_record"
                    row["acceptance_decision"] = "not_accepted"
                    row["rejection_reason"] = "duplicate_within_this_crawl"
                if row["candidate_status"] == "accepted":
                    seen_output_keys.add(dedupe_key)
                rows.append(row)
            summary_rows.append(
                {
                    "query_family_id": family_id,
                    "query_string": query,
                    "page": page + 1,
                    "hits": len(hits),
                    "rows": len(rows) - before,
                    "accepted": sum(1 for row in rows if row["candidate_status"] == "accepted") - accepted_before,
                    "duplicates": sum(1 for row in rows if row["candidate_status"] == "duplicate_existing_record") - dup_before,
                    "error": error,
                }
            )
            print(
                f"[abc-gap-crawl] {query_index}/{len(queries)} page={page + 1}/{args.pages} "
                f"query={query!r} hits={len(hits)} accepted_total={sum(1 for row in rows if row['candidate_status'] == 'accepted')}",
                flush=True,
            )
            if args.sleep:
                time.sleep(args.sleep)
    output_csv = args.output_dir / f"abc_public_search_{args.round_id}_candidates.csv"
    output_ndjson = args.output_dir / f"abc_public_search_{args.round_id}_candidates.ndjson"
    request_csv = args.output_dir / f"abc_public_search_{args.round_id}_requests.csv"
    write_csv(output_csv, rows)
    write_ndjson(output_ndjson, rows)
    request_csv.parent.mkdir(parents=True, exist_ok=True)
    with request_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0].keys()) if summary_rows else [])
        if summary_rows:
            writer.writeheader()
            writer.writerows(summary_rows)
    write_report(args.report, rows, summary_rows, output_csv)
    print(f"Wrote ABC gap candidates: {output_csv}")
    print(f"Accepted: {sum(1 for row in rows if row['candidate_status'] == 'accepted')}")
    print(f"Mapped candidates: {sum(1 for row in rows if row['candidate_status'] == 'accepted' and row.get('latitude') and row.get('longitude'))}")


if __name__ == "__main__":
    main()
