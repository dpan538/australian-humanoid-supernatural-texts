#!/usr/bin/env python3
"""Stage-only public books/catalogue metadata crawl for the post-1926 gap.

This crawler uses no-key public metadata APIs (Google Books and Open Library).
It writes reviewable candidates only; it does not ingest into production data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
FALLBACK_FRONTEND = ROOT / "public" / "data" / "frontend-data.live-crawl.json"
OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "public_books_metadata"
DEFAULT_OUTPUT = OUT_DIR / "public_books_metadata_round016_candidates.csv"
DEFAULT_RAW = OUT_DIR / "public_books_metadata_round016_raw.ndjson"
DEFAULT_REQUESTS = OUT_DIR / "public_books_metadata_round016_requests.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_public_books_metadata_round016.md"

IA_URL = "https://archive.org/advancedsearch.php"
USER_AGENT = "AusFiguresGapCrawler/0.4 public books metadata research"
START_YEAR = 1926
END_YEAR = 2011

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


@dataclass(frozen=True)
class QueryFamily:
    family_id: str
    label: str
    queries: tuple[str, ...]
    terms: tuple[str, ...]
    narrative_type: str
    sensitivity: str = "standard_public_metadata_review"
    mapped_place_hint: str = ""


QUERY_FAMILIES = [
    QueryFamily(
        "books_yowie_named",
        "Yowie named books and catalogue metadata",
        ("Yowie Australia", "Yowie sightings Australia", "Australian Bigfoot Yowie", "Rex Gilroy Yowie", "Tony Healy Yowie"),
        ("yowie", "australian bigfoot", "rex gilroy", "tony healy"),
        "cryptid_style_apeman",
    ),
    QueryFamily(
        "books_hairy_wild_man_variants",
        "Hairy/wild man language variants",
        ('"hairy man" Australia folklore', '"wild man" Australia folklore', '"hairy people" Australia'),
        ("hairy man", "wild man", "hairy people"),
        "cryptid_style_apeman",
    ),
    QueryFamily(
        "books_bunyip_adjacent",
        "Bunyip adjacent public-text records",
        ("Bunyip Australia folklore", "Bunyip stories Australia", "Bunyip sightings Australia"),
        ("bunyip",),
        "other_supernatural_humanoid_or_adjacent",
    ),
    QueryFamily(
        "books_australian_ghost_stories",
        "Australian ghost story collections",
        ("Australian ghost stories", "ghost stories Australia", "haunted Australia", "apparition Australia folklore"),
        ("ghost", "haunted", "apparition"),
        "ghost_legend",
    ),
    QueryFamily(
        "books_fishers_ghost",
        "Fisher's Ghost books/catalogue metadata",
        ('"Fisher\'s Ghost"', '"Fishers Ghost" Australia'),
        ("fisher's ghost", "fishers ghost"),
        "ghost_legend",
        mapped_place_hint="Campbelltown",
    ),
    QueryFamily(
        "books_princess_theatre_federici",
        "Federici / Princess Theatre ghost metadata",
        ('"Federici" "Princess Theatre" ghost', '"Princess Theatre" ghost Melbourne'),
        ("federici", "princess theatre", "ghost"),
        "ghost_legend",
        mapped_place_hint="Princess Theatre",
    ),
    QueryFamily(
        "books_port_arthur_ghost",
        "Port Arthur ghost/haunted metadata",
        ('"Port Arthur" ghost Australia', '"Port Arthur" haunted'),
        ("port arthur", "ghost", "haunted"),
        "ghost_legend",
        mapped_place_hint="Port Arthur",
    ),
    QueryFamily(
        "books_picton_ghost",
        "Picton ghost metadata",
        ('"Picton" ghost Australia', '"Picton tunnel" ghost'),
        ("picton", "picton tunnel", "ghost"),
        "ghost_legend",
        mapped_place_hint="Picton",
    ),
    QueryFamily(
        "books_known_haunted_places",
        "Known haunted-place public metadata",
        (
            '"Monte Cristo" ghost Australia',
            '"Fremantle Prison" ghost',
            '"Old Melbourne Gaol" ghost',
            '"Beechworth Asylum" ghost',
            '"Adelaide Gaol" ghost',
            '"Quarantine Station" ghost Australia',
        ),
        ("monte cristo", "fremantle prison", "old melbourne gaol", "beechworth", "adelaide gaol", "quarantine station", "ghost"),
        "ghost_legend",
    ),
    QueryFamily(
        "books_public_indigenous_named_figures",
        "Public metadata for named Indigenous-related figures",
        (
            "Mimih Australia folklore",
            "Quinkan Australia folklore",
            "Wandjina Australia folklore",
            "Pangkarlangu Australia",
            '"Yara-ma-yha-who"',
        ),
        ("mimih", "mimi", "quinkan", "wandjina", "pangkarlangu", "yara-ma-yha-who"),
        "traditional_narrative",
        sensitivity="indigenous_related_public_metadata_human_review_required",
    ),
]

SUPERNATURAL_RE = re.compile(
    r"\b(yowies?|australian bigfoot|bigfoot|hairy man|hairy people|wild man|"
    r"bunyips?|ghosts?|ghost stories?|haunted|haunting|apparitions?|phantoms?|"
    r"spectral|spirits?|spooks?|fisher'?s ghost|fishers ghost|federici|"
    r"mimih?|mimi spirits?|quinkan|quinkin|wandjina|wanjina|pangkarlangu|"
    r"yara-ma-yha-who|yara ma yha who)\b",
    re.I,
)

AUSTRALIA_RE = re.compile(
    r"\b(australia|australian|aboriginal|indigenous|new south wales|queensland|"
    r"victoria|tasmania|south australia|western australia|northern territory|"
    r"melbourne|sydney|brisbane|adelaide|perth|hobart|canberra|campbelltown|"
    r"port arthur|picton|fremantle|beechworth|monte cristo|princess theatre|"
    r"old melbourne gaol|adelaide gaol|quarantine station|blue mountains|"
    r"grafton|gympie|kilcoy|woodenbong|springbrook|rex gilroy|tony healy)\b",
    re.I,
)

NOISE_RE = re.compile(
    r"\b(software|information extraction|database systems?|web strategies|"
    r"internet shopping|computer science|yowie bay school|rugby league|"
    r"koori knockout|chocolate|lolly|cartoon|episode|video game|role-playing|"
    r"music album|rock band|sports club|yahoo!|yahoo answers|stock market|"
    r"ghost writer|ghostwriter|ghost net|ghost bat|ghost shark|ghost gear|"
    r"ghost gum|ghost town only|white spruce|balsam fir|grafton, richard|"
    r"anthony grafton|picton,|john picton|gorell|parroy)\b",
    re.I,
)

INDIGENOUS_RE = re.compile(
    r"\b(aboriginal|indigenous|first nations|torres strait|dreaming|dreamtime|"
    r"mimih?|mimi spirits?|quinkan|quinkin|wandjina|wanjina|pangkarlangu|"
    r"yara-ma-yha-who|yara ma yha who|spirit people|hairy people)\b",
    re.I,
)

KNOWN_PLACES = {
    "Campbelltown": ("Campbelltown, NSW", -34.0667, 150.8167, "town"),
    "Princess Theatre": ("Princess Theatre, VIC", -37.8102, 144.9715, "building"),
    "Port Arthur": ("Port Arthur, TAS", -43.1470, 147.8505, "historic_site"),
    "Picton": ("Picton, NSW", -34.1689, 150.6110, "town"),
    "Monte Cristo": ("Monte Cristo Homestead, NSW", -34.8734, 147.5823, "historic_site"),
    "Fremantle Prison": ("Fremantle Prison, WA", -32.0559, 115.7536, "building"),
    "Old Melbourne Gaol": ("Old Melbourne Gaol, VIC", -37.8078, 144.9653, "building"),
    "Beechworth": ("Beechworth Asylum, VIC", -36.3542, 146.6837, "historic_site"),
    "Adelaide Gaol": ("Adelaide Gaol, SA", -34.9132, 138.5872, "building"),
    "Quarantine Station": ("North Head Quarantine Station, NSW", -33.8126, 151.2967, "historic_site"),
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def year_from_text(value: str) -> int | None:
    match = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", value or "")
    return int(match.group(1)) if match else None


def date_scope(year: int | None) -> str:
    if year is None:
        return "undated"
    if START_YEAR <= year <= END_YEAR:
        return "gap_window_1926_2011"
    if year > END_YEAR:
        return "post_gap_after_2011"
    return "pre_gap_before_1926"


def compact_id(value: str, length: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:length].strip("-") or hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def frontend_path(path: Path) -> Path:
    if path.exists():
        return path
    return FALLBACK_FRONTEND


def existing_keys(path: Path) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    data = load_json(frontend_path(path))
    urls: set[str] = set()
    external_ids: set[str] = set()
    title_years: set[tuple[str, str]] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(url)
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
        year = record.get("year")
        title = norm(record.get("title") or "")
        if title and year:
            title_years.add((title, str(year)))
    return urls, external_ids, title_years


def is_duplicate(url: str, external_id: str, title: str, year: int | None, keys: tuple[set[str], set[str], set[tuple[str, str]]]) -> bool:
    urls, external_ids, title_years = keys
    if url and url.lower() in urls:
        return True
    if external_id and external_id in external_ids:
        return True
    if title and year and (norm(title), str(year)) in title_years:
        return True
    return False


def fetch_json(url: str, timeout: int) -> dict[str, Any]:
    result = subprocess.run(
        [
            "curl",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            str(timeout),
            "-A",
            USER_AGENT,
            "-H",
            "Accept: application/json",
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout + 5,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"curl_exit_{result.returncode}")
    return json.loads(result.stdout)


def fetch_json_urllib(url: str, timeout: int) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "ignore"))


def fetch_source_json(source_api: str, url: str, timeout: int) -> dict[str, Any]:
    if source_api == "internet_archive":
        return fetch_json_urllib(url, timeout)
    return fetch_json(url, timeout)


def error_status(exc: Exception) -> str:
    code = getattr(exc, "code", "")
    message = clean(str(exc)).replace(",", ";")[:140]
    return f"error:{type(exc).__name__}{':' + str(code) if code else ''}{':' + message if message else ''}"


def google_books_url(query: str, start_index: int, max_results: int) -> str:
    params = {
        "q": query,
        "startIndex": str(start_index),
        "maxResults": str(max_results),
        "printType": "books",
        "langRestrict": "en",
        "orderBy": "relevance",
    }
    return "https://www.googleapis.com/books/v1/volumes?" + urlencode(params)


def openlibrary_url(query: str, page: int, limit: int) -> str:
    params = {
        "q": query,
        "page": str(page),
        "limit": str(limit),
        "fields": "key,title,subtitle,author_name,first_publish_year,publish_year,subject,place,publisher,isbn,edition_key",
    }
    return "https://openlibrary.org/search.json?" + urlencode(params)


def internet_archive_url(family: QueryFamily, page: int, limit: int) -> str:
    term_parts = []
    for term in family.terms[:4]:
        term_parts.append(f'title:("{term}")')
        term_parts.append(f'description:("{term}")')
        term_parts.append(f'subject:("{term}")')
    query = "(" + " OR ".join(term_parts) + ") AND (title:(Australia) OR description:(Australia) OR subject:(Australia) OR title:(Australian) OR description:(Australian) OR subject:(Australian))"
    params: list[tuple[str, str]] = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "date"),
        ("fl[]", "year"),
        ("fl[]", "creator"),
        ("fl[]", "description"),
        ("fl[]", "subject"),
        ("fl[]", "collection"),
        ("fl[]", "mediatype"),
        ("rows", str(limit)),
        ("page", str(page)),
        ("output", "json"),
    ]
    return IA_URL + "?" + urlencode(params)


def text_from_google(item: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    info = item.get("volumeInfo") if isinstance(item.get("volumeInfo"), dict) else {}
    title = clean(" ".join(part for part in [info.get("title"), info.get("subtitle")] if part))
    published = clean(info.get("publishedDate") or "")
    publisher = clean(info.get("publisher") or "Google Books")
    authors = ", ".join(info.get("authors") or [])
    context_parts = [
        title,
        clean(info.get("description")),
        " ".join(info.get("categories") or []),
        authors,
    ]
    parts = [*context_parts, publisher]
    return title, published, publisher, authors, clean(" ".join(parts)), clean(" ".join(context_parts))


def text_from_openlibrary(doc: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    title = clean(" ".join(part for part in [doc.get("title"), doc.get("subtitle")] if part))
    year = clean(doc.get("first_publish_year") or "")
    publisher = clean("; ".join((doc.get("publisher") or [])[:3]) or "Open Library")
    authors = clean("; ".join((doc.get("author_name") or [])[:4]))
    context_parts = [
        title,
        " ".join(doc.get("subject") or []),
        " ".join(doc.get("place") or []),
        authors,
    ]
    parts = [*context_parts, publisher]
    return title, year, publisher, authors, clean(" ".join(parts)), clean(" ".join(context_parts))


def first_scalar(value: Any) -> str:
    if isinstance(value, list):
        return clean(value[0] if value else "")
    return clean(value)


def join_metadata(value: Any, limit: int = 12) -> str:
    if isinstance(value, list):
        return " ".join(clean(item) for item in value[:limit])
    return clean(value)


def text_from_internet_archive(doc: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    title = clean(doc.get("title"))
    year_text = first_scalar(doc.get("date") or doc.get("year"))
    publisher = "Internet Archive"
    authors = join_metadata(doc.get("creator"), 4)
    subjects = join_metadata(doc.get("subject"), 16)
    description = join_metadata(doc.get("description"), 6)
    context_parts = [title, description, subjects, authors]
    parts = [*context_parts, publisher, join_metadata(doc.get("collection"), 8)]
    return title, year_text, publisher, authors, clean(" ".join(parts)), clean(" ".join(context_parts))


def matched_terms(text: str) -> list[str]:
    return sorted({clean(match.group(0)).lower() for match in SUPERNATURAL_RE.finditer(text)})


def place_match(family: QueryFamily, text: str) -> tuple[str, float | str, float | str, str, str]:
    candidates = []
    if family.mapped_place_hint:
        candidates.append(family.mapped_place_hint)
    candidates.extend(KNOWN_PLACES.keys())
    for key in candidates:
        if re.search(r"\b" + re.escape(key) + r"\b", text, re.I):
            label, lat, lon, precision = KNOWN_PLACES[key]
            return label, lat, lon, precision, key
    return "", "", "", "", ""


def family_specific_ok(family: QueryFamily, title: str, text: str, context_text: str) -> tuple[bool, str]:
    title_l = title.lower()
    text_l = text.lower()
    context_l = context_text.lower()
    if family.family_id == "books_yowie_named":
        if "yowie" in title_l or "australian bigfoot" in text_l:
            return True, ""
        return False, "yowie_not_title_or_australian_bigfoot_metadata"
    if family.family_id == "books_hairy_wild_man_variants":
        if any(term in title_l for term in ("hairy man", "wild man", "hairy people")):
            return True, ""
        return False, "hairy_wild_man_not_title_anchor"
    if family.family_id == "books_bunyip_adjacent":
        if "bunyip" not in title_l and "bunyips" not in title_l:
            return False, "bunyip_not_title_anchor"
        if re.search(r"\b(horse racing|gold coast turf|school|teachers|cats|carnivals|juvenile poetry|humorous stories)\b", text_l):
            return False, "bunyip_adjacent_literary_or_non_supernatural_noise"
        if not re.search(r"\b(bunyips?|folklore|monsters?|mythology|myths?)\b", context_l):
            return False, "bunyip_missing_subject_or_context_anchor"
        return True, ""
    if family.family_id == "books_australian_ghost_stories":
        if not any(term in title_l for term in ("ghost", "ghosts", "haunted", "apparition", "phantom", "spook")):
            return False, "ghost_family_missing_title_anchor"
        if "haunted london" in title_l:
            return False, "non_australian_haunted_place_title"
        if "australia" in context_l or "australian" in context_l:
            return True, ""
        return False, "ghost_family_missing_australia_context_outside_publisher"
    if family.family_id in {"books_fishers_ghost", "books_princess_theatre_federici", "books_port_arthur_ghost", "books_picton_ghost", "books_known_haunted_places"}:
        place_terms = [term for term in family.terms if term not in {"ghost", "haunted"}]
        if not any(term in text_l for term in place_terms):
            return False, "known_place_family_missing_place_term"
        if not re.search(r"\b(ghosts?|haunted|haunting|apparition|phantom)\b", text_l):
            return False, "known_place_family_missing_ghost_term"
        return True, ""
    if family.family_id == "books_public_indigenous_named_figures":
        if not any(term in title_l for term in family.terms):
            return False, "indigenous_related_term_not_title_anchor"
        if not AUSTRALIA_RE.search(context_text):
            return False, "indigenous_related_missing_public_australia_context"
        return True, ""
    return True, ""


def evidence_window(text: str, radius: int = 520) -> str:
    match = SUPERNATURAL_RE.search(text) or AUSTRALIA_RE.search(text)
    if not match:
        return clean(text[:900])
    center = match.start()
    start = max(0, center - radius)
    end = min(len(text), center + radius)
    return clean(text[start:end])[:900]


def classify(
    *,
    source_api: str,
    family: QueryFamily,
    query: str,
    item: dict[str, Any],
    duplicate_keys: tuple[set[str], set[str], set[tuple[str, str]]],
) -> dict[str, Any]:
    if source_api == "google_books":
        title, published, publisher, authors, text, context_text = text_from_google(item)
        item_id = clean(item.get("id") or "")
        info = item.get("volumeInfo") if isinstance(item.get("volumeInfo"), dict) else {}
        url = clean(info.get("canonicalVolumeLink") or info.get("infoLink") or "")
        source_name = "Google Books Books API"
        source_type = "public_books_metadata_google_books"
        raw_id = item_id or hashlib.sha1(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()[:16]
        external_id = f"googlebooks:{raw_id}"
    elif source_api == "openlibrary":
        title, published, publisher, authors, text, context_text = text_from_openlibrary(item)
        key = clean(item.get("key") or "")
        url = f"https://openlibrary.org{key}" if key else ""
        source_name = "Open Library Search API"
        source_type = "public_books_metadata_openlibrary"
        raw_id = compact_id(key or title)
        external_id = f"openlibrary:{raw_id}"
    else:
        title, published, publisher, authors, text, context_text = text_from_internet_archive(item)
        ident = clean(item.get("identifier") or "")
        url = f"https://archive.org/details/{ident}" if ident else ""
        source_name = "Internet Archive Advanced Search"
        source_type = "public_books_metadata_internet_archive"
        raw_id = compact_id(ident or title)
        external_id = f"internet_archive:{raw_id}"

    year = year_from_text(published)
    terms = matched_terms(text)
    place_text, lat, lon, precision, place_alias = place_match(family, text)
    status = "accepted"
    rejection = ""
    if not title or not url:
        status = "rejected"
        rejection = "missing_title_or_public_url"
    elif year is None or not (START_YEAR <= year <= END_YEAR):
        status = "lead_only"
        rejection = "outside_gap_year_window_or_undated"
    elif NOISE_RE.search(text):
        status = "rejected"
        rejection = "noise_pattern"
    elif not terms:
        status = "rejected"
        rejection = "missing_supernatural_term_in_metadata"
    elif not AUSTRALIA_RE.search(context_text):
        status = "rejected"
        rejection = "missing_australia_context_outside_publisher"
    else:
        required = [term for term in family.terms if len(term) > 3]
        if required and not any(term.lower() in text.lower() for term in required):
            status = "rejected"
            rejection = "missing_required_family_term"
        else:
            ok, reason = family_specific_ok(family, title, text, context_text)
            if not ok:
                status = "rejected"
                rejection = reason

    if status == "accepted" and family.sensitivity.startswith("indigenous_related"):
        if not INDIGENOUS_RE.search(text):
            status = "lead_only"
            rejection = "indigenous_related_family_without_explicit_public_context"

    if status == "accepted" and is_duplicate(url, external_id, title, year, duplicate_keys):
        status = "duplicate_existing_record"
        rejection = "duplicate_against_current_overlay"

    risk_flags = []
    if INDIGENOUS_RE.search(text) or family.sensitivity.startswith("indigenous_related"):
        risk_flags.append("indigenous_related_public_metadata_human_review_required")

    label = terms[0].replace(" ", "_") if terms else "reported_supernatural_figure"
    raw = {
        "source_api": source_api,
        "query_family_id": family.family_id,
        "query": query,
        "source_item_id": external_id,
        "authors": authors,
        "date_scope": date_scope(year),
    }
    return {
        "candidate_status": status,
        "source_name": source_name,
        "source_type": source_type,
        "source_tier": "public_metadata",
        "query_family_id": family.family_id,
        "query_string": query,
        "abc_hit_id": "",
        "title": title,
        "publication_or_organisation": publisher or source_name,
        "publication_date_text": published or (str(year) if year else ""),
        "year": year or "",
        "date_scope": date_scope(year),
        "access_date": date.today().isoformat(),
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_books_metadata",
        "rights_access_status": "public_metadata_only_no_full_text_reproduction",
        "narrative_type": family.narrative_type,
        "secondary_role": "public_books_metadata_gap_candidate",
        "australian_relation": "Public books/catalogue metadata with Australia context, collected as a post-1926 gap candidate.",
        "humanoid_basis": "metadata_term_suggests_supernatural_or_humanoid_figure" if terms else "needs_review",
        "source_label": label,
        "matched_terms": ";".join(terms),
        "matched_place": place_alias,
        "location_text": place_text,
        "location_role": "metadata_place_anchor" if place_text else "",
        "latitude": lat,
        "longitude": lon,
        "location_precision": precision,
        "geocode_source": "curated_known_place_anchor" if place_text else "",
        "geocode_verification_status": "reviewed_place_catalog_match" if place_text else "",
        "coordinate_evidence_note": (
            f"Metadata text matched known place anchor `{place_alias}`; coordinates are public display coordinates only."
            if place_text
            else ""
        ),
        "duplicate_check_status": "checked_against_current_overlay_url_external_id_title_year",
        "quality_class": "B" if status == "accepted" and place_text else "C",
        "ethics_review_status": "needs_human_ethics_review" if risk_flags else "public_metadata_context_reviewed",
        "cultural_sensitivity": "high_public_source_summary_only" if risk_flags else "low",
        "risk_flags": ";".join(risk_flags),
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": rejection,
        "evidence_summary": evidence_window(text),
        "raw_metadata_json": json.dumps(raw, ensure_ascii=False, sort_keys=True),
    }


def crawl(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []
    duplicate_keys = existing_keys(args.frontend)
    seen_items: set[str] = set()
    families = QUERY_FAMILIES
    if args.family_id:
        requested = set(args.family_id)
        families = [family for family in QUERY_FAMILIES if family.family_id in requested]
        missing = sorted(requested - {family.family_id for family in families})
        if missing:
            raise SystemExit("Unknown query family id(s): " + ", ".join(missing))
    for family in families:
        family_queries = family.queries[: args.max_queries_per_family] if args.max_queries_per_family else family.queries
        for query in family_queries:
            if args.source in {"google_books", "both", "all"}:
                for start in range(0, args.max_google_results, args.google_page_size):
                    url = google_books_url(query, start, args.google_page_size)
                    try:
                        payload = fetch_source_json("google_books", url, args.timeout)
                        items = payload.get("items") or []
                        request_rows.append({"source_api": "google_books", "query_family_id": family.family_id, "query": query, "offset": start, "status": "ok", "items": len(items)})
                        for item in items:
                            key = f"google:{item.get('id')}"
                            if key in seen_items:
                                continue
                            seen_items.add(key)
                            raw_rows.append({"source_api": "google_books", "query_family_id": family.family_id, "query": query, "raw": item})
                            rows.append(classify(source_api="google_books", family=family, query=query, item=item, duplicate_keys=duplicate_keys))
                    except Exception as exc:  # noqa: BLE001 - report crawl failure per request
                        request_rows.append({"source_api": "google_books", "query_family_id": family.family_id, "query": query, "offset": start, "status": error_status(exc), "items": 0})
                    time.sleep(args.delay)
            if args.source in {"openlibrary", "both", "all"}:
                for page in range(args.openlibrary_start_page, args.openlibrary_start_page + args.openlibrary_pages):
                    url = openlibrary_url(query, page, args.openlibrary_page_size)
                    try:
                        payload = fetch_source_json("openlibrary", url, args.timeout)
                        docs = payload.get("docs") or []
                        request_rows.append({"source_api": "openlibrary", "query_family_id": family.family_id, "query": query, "offset": page, "status": "ok", "items": len(docs)})
                        for doc in docs:
                            key = f"ol:{doc.get('key')}"
                            if key in seen_items:
                                continue
                            seen_items.add(key)
                            raw_rows.append({"source_api": "openlibrary", "query_family_id": family.family_id, "query": query, "raw": doc})
                            rows.append(classify(source_api="openlibrary", family=family, query=query, item=doc, duplicate_keys=duplicate_keys))
                    except Exception as exc:  # noqa: BLE001 - report crawl failure per request
                        request_rows.append({"source_api": "openlibrary", "query_family_id": family.family_id, "query": query, "offset": page, "status": error_status(exc), "items": 0})
                    time.sleep(args.delay)
            if args.source in {"internet_archive", "all"}:
                if query != family.queries[0]:
                    continue
                for page in range(1, args.ia_pages + 1):
                    url = internet_archive_url(family, page, args.ia_page_size)
                    try:
                        payload = fetch_source_json("internet_archive", url, args.timeout)
                        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
                        docs = response.get("docs") or []
                        request_rows.append({"source_api": "internet_archive", "query_family_id": family.family_id, "query": query, "offset": page, "status": "ok", "items": len(docs)})
                        for doc in docs:
                            key = f"ia:{doc.get('identifier')}"
                            if key in seen_items:
                                continue
                            seen_items.add(key)
                            raw_rows.append({"source_api": "internet_archive", "query_family_id": family.family_id, "query": query, "raw": doc})
                            rows.append(classify(source_api="internet_archive", family=family, query=query, item=doc, duplicate_keys=duplicate_keys))
                    except Exception as exc:  # noqa: BLE001 - report crawl failure per request
                        request_rows.append({"source_api": "internet_archive", "query_family_id": family.family_id, "query": query, "offset": page, "status": error_status(exc), "items": 0})
                    time.sleep(args.delay)
    return rows, raw_rows, request_rows


def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        key = row.get("external_id") or row.get("canonical_url") or f"{row.get('title')}:{row.get('year')}"
        if key in seen:
            if row.get("candidate_status") == "accepted":
                row = dict(row)
                row["candidate_status"] = "duplicate_existing_record"
                row["acceptance_decision"] = "not_accepted"
                row["rejection_reason"] = "duplicate_within_public_books_metadata_round"
            else:
                continue
        seen.add(key)
        unique.append(row)
    return unique


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_raw(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def bucket(year: Any) -> str:
    try:
        y = int(year)
    except (TypeError, ValueError):
        return "undated"
    if 1926 <= y <= 1945:
        return "1926-1945"
    if 1946 <= y <= 1969:
        return "1946-1969"
    if 1970 <= y <= 1990:
        return "1970-1990"
    if 1991 <= y <= 2011:
        return "1991-2011"
    if y >= 2012:
        return "2012-2026"
    return "pre-1926"


def write_report(path: Path, rows: list[dict[str, Any]], request_rows: list[dict[str, Any]], output: Path) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    family_counts = Counter(row["query_family_id"] for row in rows if row["candidate_status"] == "accepted")
    source_counts = Counter(row["source_type"] for row in rows if row["candidate_status"] == "accepted")
    bucket_counts = Counter(bucket(row.get("year")) for row in rows if row["candidate_status"] == "accepted")
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    try:
        output_label = str(output.resolve().relative_to(ROOT))
    except ValueError:
        output_label = str(output)
    lines = [
        "# 1926-2011 Public Books Metadata Crawl",
        "",
        "Stage-only crawl. These are public metadata candidates, not production imports and not claim verification.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate CSV: `{output_label}`",
        f"- Requests: `{len(request_rows)}`",
        f"- Rows written: `{len(rows)}`",
        f"- Accepted candidates: `{status_counts.get('accepted', 0)}`",
        f"- Accepted with public display coordinates: `{mapped}`",
        f"- Duplicate against current overlay: `{status_counts.get('duplicate_existing_record', 0)}`",
        "",
        "## Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted By Year Bucket", "| bucket | accepted |", "|---|---:|"])
    for key in ["1926-1945", "1946-1969", "1970-1990", "1991-2011", "undated", "2012-2026"]:
        lines.append(f"| {key} | {bucket_counts.get(key, 0)} |")
    lines.extend(["", "## Accepted By Source"])
    for key, count in source_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted By Query Family"])
    for key, count in family_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Request Outcomes"])
    request_counts = Counter(row["status"] for row in request_rows)
    for key, count in request_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes"])
    lines.append("- Public metadata records remain stage-only until human review checks full source context, publicness, duplicates, and cultural sensitivity.")
    lines.append("- Indigenous-related rows are flagged for human ethics review and use metadata summaries only.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global START_YEAR, END_YEAR

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--requests-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--source", choices=["google_books", "openlibrary", "internet_archive", "both", "all"], default="both")
    parser.add_argument("--family-id", action="append", help="Run only this query family id. May be repeated.")
    parser.add_argument("--max-google-results", type=int, default=80)
    parser.add_argument("--google-page-size", type=int, default=40)
    parser.add_argument("--openlibrary-pages", type=int, default=1)
    parser.add_argument("--openlibrary-start-page", type=int, default=1)
    parser.add_argument("--openlibrary-page-size", type=int, default=100)
    parser.add_argument("--ia-pages", type=int, default=1)
    parser.add_argument("--ia-page-size", type=int, default=50)
    parser.add_argument("--max-queries-per-family", type=int, default=0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--year-start", type=int, default=START_YEAR)
    parser.add_argument("--year-end", type=int, default=END_YEAR)
    args = parser.parse_args()

    START_YEAR = args.year_start
    END_YEAR = args.year_end

    rows, raw_rows, request_rows = crawl(args)
    rows = dedupe_rows(rows)
    write_csv(args.output, FIELDNAMES, rows)
    write_raw(args.raw_output, raw_rows)
    write_csv(args.requests_output, ["source_api", "query_family_id", "query", "offset", "status", "items"], request_rows)
    write_report(args.report, rows, request_rows, args.output)

    status_counts = Counter(row["candidate_status"] for row in rows)
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    print(f"Wrote public books metadata candidates: {args.output}")
    print(f"Rows: {len(rows)}")
    print(f"Accepted: {status_counts.get('accepted', 0)}")
    print(f"Mapped accepted: {mapped}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
