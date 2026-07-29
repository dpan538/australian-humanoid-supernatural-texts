#!/usr/bin/env python3
"""Run a real public-metadata crawl for the 1926-2011 gap window.

The crawler is deliberately conservative: it uses public metadata APIs, writes
raw samples and cleaned candidates to interim files, and does not promote rows
to the production database or production frontend-data.json.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "live_crawl"
DEFAULT_CANDIDATES = OUT_DIR / "public_metadata_live_candidates.csv"
DEFAULT_REQUESTS = OUT_DIR / "public_metadata_live_request_summary.csv"
DEFAULT_RAW = OUT_DIR / "public_metadata_live_raw.ndjson"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_live_public_metadata_crawl.md"

OPENALEX_URL = "https://api.openalex.org/works"
CROSSREF_URL = "https://api.crossref.org/works"
IA_URL = "https://archive.org/advancedsearch.php"
USER_AGENT = "AusFiguresGapCrawler/0.2 public-text research; contact=research@ausfigures.com"

START_YEAR = 1926
END_YEAR = 2011


@dataclass(frozen=True)
class QueryFamily:
    family_id: str
    label: str
    search: str
    terms: tuple[str, ...]
    priority: int
    sensitivity: str = "standard_public_metadata_review"


QUERY_FAMILIES = [
    QueryFamily(
        "fisher_ghost_named",
        "Fisher's Ghost named records",
        '"Fisher\'s Ghost"',
        ("fisher's ghost", "fishers ghost"),
        0,
    ),
    QueryFamily(
        "federici_princess_theatre_named",
        "Federici / Princess Theatre named records",
        '"Federici" "Princess Theatre" ghost',
        ("federici", "princess theatre", "ghost"),
        0,
    ),
    QueryFamily(
        "port_arthur_ghost_named",
        "Port Arthur ghost named records",
        '"Port Arthur" ghost',
        ("port arthur", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "den_of_nargun_named",
        "Den of Nargun named records",
        '"Den of Nargun"',
        ("den of nargun", "nargun"),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "yowie_exact_named",
        "Yowie exact named metadata",
        "Yowie",
        ("yowie",),
        0,
    ),
    QueryFamily(
        "quinkan_exact_named",
        "Quinkan exact named metadata",
        "Quinkan",
        ("quinkan", "quinkin"),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "wandjina_exact_named",
        "Wandjina exact named metadata",
        "Wandjina",
        ("wandjina", "wanjina"),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "mimih_exact_named",
        "Mimih exact named metadata",
        "Mimih",
        ("mimih", "mimi spirit"),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "fremantle_prison_ghost_named",
        "Fremantle Prison ghost named records",
        '"Fremantle Prison" ghost',
        ("fremantle prison", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "fremantle_prison_haunted_named",
        "Fremantle Prison haunted named records",
        '"Fremantle Prison" haunted',
        ("fremantle prison", "haunted"),
        0,
    ),
    QueryFamily(
        "old_melbourne_gaol_ghost_named",
        "Old Melbourne Gaol ghost named records",
        '"Old Melbourne Gaol" ghost',
        ("old melbourne gaol", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "old_melbourne_gaol_haunted_named",
        "Old Melbourne Gaol haunted named records",
        '"Old Melbourne Gaol" haunted',
        ("old melbourne gaol", "haunted"),
        0,
    ),
    QueryFamily(
        "monte_cristo_ghost_named",
        "Monte Cristo ghost named records",
        '"Monte Cristo" ghost Australia',
        ("monte cristo", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "monte_cristo_homestead_ghost_named",
        "Monte Cristo Homestead ghost named records",
        '"Monte Cristo Homestead" ghost',
        ("monte cristo homestead", "monte cristo", "ghost"),
        0,
    ),
    QueryFamily(
        "picton_ghost_named",
        "Picton ghost named records",
        '"Picton" ghost Australia',
        ("picton", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "picton_tunnel_ghost_named",
        "Picton tunnel ghost named records",
        '"Picton tunnel" ghost',
        ("picton tunnel", "picton tunnels", "ghost"),
        0,
    ),
    QueryFamily(
        "q_station_ghost_named",
        "Q Station / North Head quarantine ghost records",
        '"Q Station" ghost OR "North Head Quarantine Station" ghost',
        ("q station", "north head quarantine station", "ghost"),
        0,
    ),
    QueryFamily(
        "beechworth_asylum_ghost_named",
        "Beechworth asylum ghost named records",
        '"Beechworth" asylum ghost',
        ("beechworth", "asylum", "ghost"),
        0,
    ),
    QueryFamily(
        "aradale_ghost_named",
        "Aradale ghost named records",
        '"Aradale" ghost',
        ("aradale", "ghost", "haunted"),
        0,
    ),
    QueryFamily(
        "narryna_ghost_named",
        "Narryna ghost named records",
        '"Narryna" ghost',
        ("narryna", "ghost"),
        0,
    ),
    QueryFamily(
        "pangkarlangu_exact_named",
        "Pangkarlangu exact named metadata",
        "Pangkarlangu",
        ("pangkarlangu",),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "mamu_exact_named",
        "Mamu exact named metadata",
        "Mamu Australia Aboriginal spirit",
        ("mamu",),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "mokoi_exact_named",
        "Mokoi exact named metadata",
        "Mokoi Australia Aboriginal spirit",
        ("mokoi",),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "yaroma_exact_named",
        "Yaroma exact named metadata",
        "Yaroma Australia",
        ("yaroma",),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "garkain_exact_named",
        "Garkain exact named metadata",
        "Garkain Arnhem Land",
        ("garkain",),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "yara_ma_yha_who_exact_named",
        "Yara-ma-yha-who exact named metadata",
        '"Yara-ma-yha-who"',
        ("yara-ma-yha-who", "yara ma yha who"),
        0,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "australian_bigfoot_yowie_named",
        "Australian Bigfoot / Yowie named metadata",
        '"Australian Bigfoot" Yowie',
        ("australian bigfoot", "yowie", "bigfoot"),
        0,
    ),
    QueryFamily(
        "rex_gilroy_yowie_named",
        "Rex Gilroy / Yowie named metadata",
        '"Rex Gilroy" Yowie',
        ("rex gilroy", "yowie"),
        0,
    ),
    QueryFamily(
        "tony_healy_yowie_named",
        "Tony Healy / Yowie named metadata",
        '"Tony Healy" Yowie',
        ("tony healy", "yowie"),
        0,
    ),
    QueryFamily(
        "blue_mountains_yowie_named",
        "Blue Mountains Yowie named metadata",
        '"Blue Mountains" Yowie',
        ("blue mountains", "yowie"),
        0,
    ),
    QueryFamily(
        "springbrook_yowie_named",
        "Springbrook Yowie named metadata",
        "Springbrook Yowie",
        ("springbrook", "yowie"),
        0,
    ),
    QueryFamily(
        "kilcoy_yowie_named",
        "Kilcoy Yowie named metadata",
        "Kilcoy Yowie",
        ("kilcoy", "yowie"),
        0,
    ),
    QueryFamily(
        "woodenbong_yowie_named",
        "Woodenbong Yowie named metadata",
        "Woodenbong Yowie",
        ("woodenbong", "yowie"),
        0,
    ),
    QueryFamily(
        "grafton_yowie_named",
        "Grafton Yowie named metadata",
        "Grafton Yowie",
        ("grafton", "yowie"),
        0,
    ),
    QueryFamily(
        "pilliga_yowie_named",
        "Pilliga Yowie named metadata",
        "Pilliga Yowie",
        ("pilliga", "yowie"),
        0,
    ),
    QueryFamily(
        "gympie_yowie_named",
        "Gympie Yowie named metadata",
        "Gympie Yowie",
        ("gympie", "yowie"),
        0,
    ),
    QueryFamily(
        "canungra_yowie_named",
        "Canungra Yowie named metadata",
        "Canungra Yowie",
        ("canungra", "yowie"),
        0,
    ),
    QueryFamily(
        "katoomba_yowie_named",
        "Katoomba Yowie named metadata",
        "Katoomba Yowie",
        ("katoomba", "yowie"),
        0,
    ),
    QueryFamily(
        "megalong_yowie_named",
        "Megalong Valley Yowie named metadata",
        '"Megalong Valley" Yowie',
        ("megalong valley", "megalong", "yowie"),
        0,
    ),
    QueryFamily(
        "ulladulla_yowie_named",
        "Ulladulla Yowie named metadata",
        "Ulladulla Yowie",
        ("ulladulla", "yowie"),
        0,
    ),
    QueryFamily(
        "boggo_road_gaol_ghost_named",
        "Boggo Road Gaol ghost named records",
        '"Boggo Road Gaol" ghost',
        ("boggo road gaol", "boggo road jail", "ghost"),
        0,
    ),
    QueryFamily(
        "maitland_gaol_ghost_named",
        "Maitland Gaol ghost named records",
        '"Maitland Gaol" ghost',
        ("maitland gaol", "maitland jail", "ghost"),
        0,
    ),
    QueryFamily(
        "j_ward_ararat_ghost_named",
        "J Ward Ararat ghost named records",
        '"J Ward" Ararat ghost',
        ("j ward", "ararat", "ghost"),
        0,
    ),
    QueryFamily(
        "old_government_house_ghost_named",
        "Old Government House ghost named records",
        '"Old Government House" ghost Australia',
        ("old government house", "ghost"),
        0,
    ),
    QueryFamily(
        "blundells_cottage_ghost_named",
        "Blundells Cottage ghost named records",
        '"Blundells Cottage" ghost',
        ("blundells cottage", "ghost"),
        0,
    ),
    QueryFamily(
        "hotel_kurrajong_ghost_named",
        "Hotel Kurrajong ghost named records",
        '"Hotel Kurrajong" ghost',
        ("hotel kurrajong", "ghost"),
        0,
    ),
    QueryFamily(
        "wakehurst_parkway_ghost_named",
        "Wakehurst Parkway ghost named records",
        '"Wakehurst Parkway" ghost',
        ("wakehurst parkway", "ghost"),
        0,
    ),
    QueryFamily(
        "quarantine_station_ghost_named",
        "Quarantine Station ghost named records",
        '"Quarantine Station" ghost Australia',
        ("quarantine station", "ghost"),
        0,
    ),
    QueryFamily(
        "gladesville_hospital_ghost_named",
        "Gladesville Hospital ghost named records",
        '"Gladesville Hospital" ghost',
        ("gladesville hospital", "ghost"),
        0,
    ),
    QueryFamily(
        "callan_park_ghost_named",
        "Callan Park ghost named records",
        '"Callan Park" ghost',
        ("callan park", "ghost"),
        0,
    ),
    QueryFamily(
        "toowong_cemetery_ghost_named",
        "Toowong Cemetery ghost named records",
        '"Toowong Cemetery" ghost',
        ("toowong cemetery", "ghost"),
        0,
    ),
    QueryFamily(
        "yowie_yahoo_named",
        "Yowie / Yahoo named forms",
        "Yowie Australia",
        ("yowie", "yahoo devil", "yahoo-devil", "yahoo devil devil", "devil-devil"),
        1,
    ),
    QueryFamily(
        "hairy_humanoid_descriptors",
        "Hairy humanoid descriptors",
        '"hairy man" Australia Aboriginal',
        ("hairy man", "hairyman", "wild man", "wildman", "ape man", "bush ape"),
        1,
    ),
    QueryFamily(
        "wild_man_giant_variants",
        "Wild man / giant / ogre variants",
        '"wild man" Australia folklore giant',
        ("wild man", "giant", "ogre", "supernatural figure"),
        2,
    ),
    QueryFamily(
        "apparition_ghost_public_places",
        "Ghost / apparition public-place records",
        "ghost apparition Australia folklore",
        ("ghost", "apparition", "phantom", "spectre", "spook", "haunted"),
        1,
    ),
    QueryFamily(
        "resident_ghost_place_terms",
        "Resident ghost / haunted place language",
        '"resident ghost" Australia',
        ("resident ghost", "haunted", "ghost story", "white lady"),
        2,
    ),
    QueryFamily(
        "local_legend_source_voice",
        "Local legend source-voice forms",
        '"local legend" Australia ghost',
        ("local legend", "bush legend", "district story", "old residents"),
        2,
    ),
    QueryFamily(
        "public_indigenous_named_figures",
        "Public named figure records requiring sensitivity review",
        "Wandjina Quinkan Nargun Mimih Pangkarlangu Australia",
        ("wandjina", "wanjina", "quinkan", "quinkin", "nargun", "mimih", "mamu", "pangkarlangu", "mokoi", "yaroma"),
        1,
        "indigenous_related_public_metadata_human_review_required",
    ),
    QueryFamily(
        "yara_bunyip_adjacent",
        "Yara-ma-yha-who / bunyip adjacent public texts",
        '"Yara-ma-yha-who" OR bunyip Australia folklore',
        ("yara-ma-yha-who", "yara ma yha who", "bunyip"),
        3,
        "scope_review_required",
    ),
    QueryFamily(
        "bunyip_exact_named",
        "Bunyip exact named metadata",
        "Bunyip Australia folklore",
        ("bunyip",),
        0,
        "scope_review_required",
    ),
    QueryFamily(
        "yahoo_devil_exact_named",
        "Yahoo-devil exact named metadata",
        '"Yahoo devil" Australia',
        ("yahoo devil", "yahoo-devil"),
        0,
    ),
    QueryFamily(
        "devil_devil_exact_named",
        "Devil-devil exact named metadata",
        '"devil-devil" Australia',
        ("devil-devil", "devil devil"),
        0,
    ),
    QueryFamily(
        "debil_debil_exact_named",
        "Debil-debil exact named metadata",
        '"debil-debil" Australia',
        ("debil-debil", "debil debil"),
        0,
    ),
]

NOISE_PATTERNS = (
    "cadbury",
    "chocolate",
    "toy",
    "yowie bay",
    "yahoo answers",
    "yahoo mail",
    "finance.yahoo",
    "sports.yahoo",
    "mamu-b",
    "hiv",
    "siv",
    "macaque",
    "ghost crab",
    "ghost crabs",
    "eucalyptus",
    "irrigation",
    "geogebra",
    "qudit",
    "ty the tasmanian tiger",
)

AUSTRALIA_CONTEXT = (
    "australia",
    "australian",
    "aboriginal",
    "indigenous",
    "arnhem",
    "kimberley",
    "cape york",
    "queensland",
    "new south wales",
    "victoria",
    "tasmania",
    "western australia",
    "south australia",
    "northern territory",
    "gippsland",
    "fisher's ghost",
    "fishers ghost",
    "campbelltown",
    "federici",
    "princess theatre",
    "port arthur",
    "den of nargun",
    "nargun",
    "fremantle",
    "fremantle prison",
    "old melbourne gaol",
    "monte cristo",
    "monte cristo homestead",
    "picton",
    "picton tunnel",
    "picton tunnels",
    "q station",
    "north head quarantine station",
    "beechworth",
    "aradale",
    "narryna",
    "pangkarlangu",
    "mokoi",
    "yaroma",
    "garkain",
    "yara-ma-yha-who",
    "yara ma yha who",
    "rex gilroy",
    "tony healy",
    "blue mountains",
    "springbrook",
    "kilcoy",
    "woodenbong",
    "grafton",
    "pilliga",
    "gympie",
    "canungra",
    "katoomba",
    "megalong valley",
    "megalong",
    "ulladulla",
    "boggo road gaol",
    "boggo road jail",
    "maitland gaol",
    "maitland jail",
    "j ward",
    "ararat",
    "old government house",
    "blundells cottage",
    "hotel kurrajong",
    "wakehurst parkway",
    "quarantine station",
    "gladesville hospital",
    "callan park",
    "toowong cemetery",
)

STATE_HINTS = {
    "WA": ("western australia", "kimberley", "wandjina", "wanjina"),
    "NT": ("northern territory", "arnhem", "mimih", "mamu", "pangkarlangu", "garkain"),
    "QLD": ("queensland", "cape york", "quinkan", "quinkin", "laura"),
    "NSW": ("new south wales", "nsw", "blue mountains", "illawarra"),
    "VIC": ("victoria", "gippsland", "nargun", "puttikan", "old melbourne gaol"),
    "TAS": ("tasmania", "tasmanian", "port arthur"),
    "SA": ("south australia",),
    "ACT": ("canberra", "australian capital territory"),
}

CANDIDATE_FIELDS = [
    "candidate_status",
    "source_api",
    "query_family_id",
    "query_family_label",
    "query_string",
    "year",
    "title",
    "publication",
    "author",
    "url",
    "external_id",
    "figure_terms_matched",
    "state_hint",
    "risk_flags",
    "publicness_status",
    "rights_access_status",
    "relevance_status",
    "narrative_type_guess",
    "location_role",
    "map_eligibility",
    "evidence_summary",
    "raw_rank",
]

REQUEST_FIELDS = [
    "source_api",
    "query_family_id",
    "query_string",
    "page",
    "status",
    "http_status_or_error",
    "raw_hit_count",
    "sampled_items",
    "clean_candidates",
    "rejected_items",
    "elapsed_seconds",
    "request_url_redacted",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(clean(item) for item in value if item)
    return " ".join(str(value or "").replace("\xa0", " ").split())


def lower_text(*values: Any) -> str:
    return "\n".join(clean(value).lower() for value in values if clean(value))


def reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            words.append((int(position), word))
    return clean(" ".join(word for _position, word in sorted(words)))


def crossref_year(item: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued", "created"):
        parts = ((item.get(key) or {}).get("date-parts") or [[]])[0]
        if parts and isinstance(parts[0], int):
            return parts[0]
    return None


def first_url(item: dict[str, Any]) -> str:
    primary = item.get("primary_location") or {}
    if primary.get("landing_page_url"):
        return str(primary["landing_page_url"])
    if primary.get("pdf_url"):
        return str(primary["pdf_url"])
    if item.get("URL"):
        return str(item["URL"])
    if item.get("DOI"):
        return "https://doi.org/" + str(item["DOI"])
    if item.get("doi"):
        return str(item["doi"])
    if item.get("id"):
        return str(item["id"])
    return ""


def author_list_openalex(item: dict[str, Any], limit: int = 4) -> str:
    names = []
    for author in item.get("authorships") or []:
        name = ((author or {}).get("author") or {}).get("display_name")
        if name:
            names.append(str(name))
    if len(names) > limit:
        return ", ".join(names[:limit]) + " et al."
    return ", ".join(names)


def author_list_crossref(item: dict[str, Any], limit: int = 4) -> str:
    names = []
    for author in item.get("author") or []:
        given = clean(author.get("given"))
        family = clean(author.get("family"))
        name = clean(f"{given} {family}")
        if name:
            names.append(name)
    if len(names) > limit:
        return ", ".join(names[:limit]) + " et al."
    return ", ".join(names)


def source_name_openalex(item: dict[str, Any]) -> str:
    primary = item.get("primary_location") or {}
    source = primary.get("source") or {}
    return clean(source.get("display_name")) or "OpenAlex"


def source_name_crossref(item: dict[str, Any]) -> str:
    container = item.get("container-title") or []
    if isinstance(container, list) and container:
        return clean(container[0])
    return clean(item.get("publisher")) or "Crossref"


def has_noise(text: str) -> str:
    for pattern in NOISE_PATTERNS:
        if pattern in text:
            return pattern
    return ""


def matched_terms(family: QueryFamily, text: str) -> list[str]:
    return [term for term in family.terms if term in text]


def required_terms_ok(family: QueryFamily, text: str, terms: list[str]) -> bool:
    if not terms:
        return False
    family_id = family.family_id
    if family_id.endswith("_yowie_named") and family_id != "yowie_exact_named":
        place_terms = [term for term in family.terms if term not in {"yowie", "bigfoot", "australian bigfoot"}]
        return "yowie" in text and any(term in text for term in place_terms)
    if "ghost_named" in family_id or "haunted_named" in family_id:
        figure_ok = "ghost" in text or "haunted" in text
        place_terms = [term for term in family.terms if term not in {"ghost", "haunted", "asylum"}]
        return figure_ok and any(term in text for term in place_terms)
    if family_id == "federici_princess_theatre_named":
        return "federici" in text and "princess theatre" in text and ("ghost" in text or "haunted" in text)
    return True


def state_hint(text: str) -> str:
    for state, patterns in STATE_HINTS.items():
        if any(pattern in text for pattern in patterns):
            return state
    return ""


def classify_candidate(
    *,
    source_api: str,
    family: QueryFamily,
    query: str,
    rank: int,
    year: int | None,
    title: str,
    publication: str,
    author: str,
    url: str,
    external_id: str,
    description: str,
) -> dict[str, Any]:
    text = lower_text(title, publication, description)
    risk_flags: list[str] = []
    if family.sensitivity != "standard_public_metadata_review":
        risk_flags.append(family.sensitivity)
    noise = has_noise(text)
    terms = matched_terms(family, text)
    australia_context = any(token in text for token in AUSTRALIA_CONTEXT)

    status = "public_metadata_candidate"
    relevance = "needs_review"
    if year is None or not (START_YEAR <= year <= END_YEAR):
        status = "rejected"
        relevance = "outside_gap_year_window"
    elif noise:
        status = "rejected"
        relevance = "noise_pattern"
        risk_flags.append("noise:" + noise)
    elif not required_terms_ok(family, text, terms):
        status = "rejected"
        relevance = "missing_required_place_figure_term_pair"
    elif not australia_context:
        status = "rejected"
        relevance = "missing_australia_context"
    elif not url:
        status = "rejected"
        relevance = "missing_public_url"

    narrative = "catalogue_metadata"
    if family.family_id.startswith("apparition") or "ghost" in family.family_id:
        narrative = "apparition_or_ghost_public_metadata"
    elif "yowie" in family.family_id or "hairy" in family.family_id or "wild" in family.family_id:
        narrative = "hairy_humanoid_public_metadata"
    elif family.family_id == "public_indigenous_named_figures":
        narrative = "public_named_figure_metadata_sensitive_review"

    return {
        "candidate_status": status,
        "source_api": source_api,
        "query_family_id": family.family_id,
        "query_family_label": family.label,
        "query_string": query,
        "year": year or "",
        "title": title,
        "publication": publication,
        "author": author,
        "url": url,
        "external_id": external_id,
        "figure_terms_matched": ";".join(terms),
        "state_hint": state_hint(text),
        "risk_flags": ";".join(risk_flags),
        "publicness_status": "public_metadata_api",
        "rights_access_status": "metadata_only_full_text_not_retrieved",
        "relevance_status": relevance,
        "narrative_type_guess": narrative,
        "location_role": "source_or_figure_associated_region_only",
        "map_eligibility": "not_map_eligible_without_place_review",
        "evidence_summary": (
            f"Public {source_api} metadata result matching query family `{family.family_id}`. "
            "This is a lead/candidate, not a verified supernatural claim."
        ),
        "raw_rank": rank,
    }


def curl_json(url: str, timeout: int) -> tuple[dict[str, Any] | None, str, float]:
    started = time.monotonic()
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
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        return None, result.stderr.strip() or f"curl_exit_{result.returncode}", elapsed
    try:
        return json.loads(result.stdout), "200", elapsed
    except json.JSONDecodeError as exc:
        return None, f"json_error:{exc}", elapsed


def openalex_url(family: QueryFamily, page: int, per_page: int, mailto: str) -> str:
    params = {
        "search": family.search,
        "filter": f"from_publication_date:{START_YEAR}-01-01,to_publication_date:{END_YEAR}-12-31",
        "per-page": str(per_page),
        "page": str(page),
        "mailto": mailto,
    }
    return OPENALEX_URL + "?" + urlencode(params)


def crossref_url(family: QueryFamily, page: int, per_page: int, mailto: str) -> str:
    params = {
        "query.title": family.search,
        "filter": f"from-pub-date:{START_YEAR}-01-01,until-pub-date:{END_YEAR}-12-31",
        "rows": str(per_page),
        "offset": str((page - 1) * per_page),
        "mailto": mailto,
    }
    return CROSSREF_URL + "?" + urlencode(params)


def ia_url(family: QueryFamily, page: int, per_page: int) -> str:
    term = family.terms[0]
    query = f'title:("{term}") OR description:("{term}")'
    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "date"),
        ("fl[]", "creator"),
        ("fl[]", "description"),
        ("fl[]", "mediatype"),
        ("rows", str(per_page)),
        ("page", str(page)),
        ("output", "json"),
    ]
    return IA_URL + "?" + urlencode(params)


def process_openalex(payload: dict[str, Any], family: QueryFamily, query: str, source_api: str) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    raw_count = int((payload.get("meta") or {}).get("count") or 0)
    raw_rows = payload.get("results") or []
    raw_items: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(raw_rows, start=1):
        title = clean(item.get("display_name"))
        abstract = reconstruct_abstract(item.get("abstract_inverted_index"))
        row = classify_candidate(
            source_api=source_api,
            family=family,
            query=query,
            rank=index,
            year=item.get("publication_year") if isinstance(item.get("publication_year"), int) else None,
            title=title,
            publication=source_name_openalex(item),
            author=author_list_openalex(item),
            url=first_url(item),
            external_id="openalex:" + str(item.get("id", "")).rsplit("/", 1)[-1],
            description=abstract,
        )
        raw_items.append({"source_api": source_api, "family": family.family_id, "raw": item, "candidate": row})
        candidates.append(row)
    return raw_count, raw_items, candidates


def process_crossref(payload: dict[str, Any], family: QueryFamily, query: str, source_api: str) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    message = payload.get("message") or {}
    raw_count = int(message.get("total-results") or 0)
    raw_rows = message.get("items") or []
    raw_items: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(raw_rows, start=1):
        title = clean((item.get("title") or [""])[0] if isinstance(item.get("title"), list) else item.get("title"))
        abstract = clean(item.get("abstract"))
        row = classify_candidate(
            source_api=source_api,
            family=family,
            query=query,
            rank=index,
            year=crossref_year(item),
            title=title,
            publication=source_name_crossref(item),
            author=author_list_crossref(item),
            url=first_url(item),
            external_id="crossref:" + clean(item.get("DOI")),
            description=abstract,
        )
        raw_items.append({"source_api": source_api, "family": family.family_id, "raw": item, "candidate": row})
        candidates.append(row)
    return raw_count, raw_items, candidates


def process_ia(payload: dict[str, Any], family: QueryFamily, query: str, source_api: str) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    response = payload.get("response") or {}
    raw_count = int(response.get("numFound") or 0)
    raw_rows = response.get("docs") or []
    raw_items: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(raw_rows, start=1):
        ident = clean(item.get("identifier"))
        year = None
        for value in (item.get("date"), item.get("year"), item.get("publicdate")):
            text = clean(value)
            for token in text.replace("-", " ").split():
                if token.isdigit() and len(token) == 4:
                    year = int(token)
                    break
            if year:
                break
        row = classify_candidate(
            source_api=source_api,
            family=family,
            query=query,
            rank=index,
            year=year,
            title=clean(item.get("title")),
            publication="Internet Archive",
            author=clean(item.get("creator")),
            url=f"https://archive.org/details/{ident}" if ident else "",
            external_id="internet_archive:" + ident,
            description=clean(item.get("description")),
        )
        raw_items.append({"source_api": source_api, "family": family.family_id, "raw": item, "candidate": row})
        candidates.append(row)
    return raw_count, raw_items, candidates


def redacted(url: str) -> str:
    return url.replace("mailto=research%40ausfigures.com", "mailto=REDACTED")


def write_report(path: Path, candidates: list[dict[str, Any]], requests: list[dict[str, Any]], started: str, finished: str) -> None:
    accepted = [row for row in candidates if row["candidate_status"] == "public_metadata_candidate"]
    rejected = [row for row in candidates if row["candidate_status"] != "public_metadata_candidate"]
    lines = [
        "# 1926-2011 Live Public Metadata Crawl",
        "",
        "This is a real public-metadata crawl, not a projection. It does not promote candidates to production records.",
        "",
        "## Execution",
        f"- Started: `{started}`",
        f"- Finished: `{finished}`",
        f"- Requests attempted: {len(requests)}",
        f"- Clean public metadata candidates: {len(accepted)}",
        f"- Rejected/noise/out-of-scope sampled rows: {len(rejected)}",
        "",
        "## Source Yield",
    ]
    for source, count in Counter(row["source_api"] for row in accepted).most_common():
        sampled = sum(int(req.get("sampled_items") or 0) for req in requests if req["source_api"] == source)
        lines.append(f"- {source}: {count} clean candidates from {sampled} sampled rows")
    lines.extend(["", "## Query Family Yield"])
    for family, count in Counter(row["query_family_id"] for row in accepted).most_common():
        lines.append(f"- {family}: {count}")
    lines.extend(["", "## Year Buckets"])
    buckets = Counter()
    for row in accepted:
        year = int(row["year"])
        if 1926 <= year <= 1929:
            buckets["1926-1929"] += 1
        elif 1930 <= year <= 1949:
            buckets["1930-1949"] += 1
        elif 1950 <= year <= 1969:
            buckets["1950-1969"] += 1
        elif 1970 <= year <= 1989:
            buckets["1970-1989"] += 1
        else:
            buckets["1990-2011"] += 1
    for bucket in ("1926-1929", "1930-1949", "1950-1969", "1970-1989", "1990-2011"):
        lines.append(f"- {bucket}: {buckets[bucket]}")
    lines.extend(["", "## Rejection Reasons"])
    for reason, count in Counter(row["relevance_status"] for row in rejected).most_common(20):
        lines.append(f"- {reason}: {count}")
    lines.extend(
        [
            "",
            "## Guardrails",
            "- Candidates are public metadata leads, not verified supernatural claims.",
            "- No restricted full text, paywalled content, or private material was fetched.",
            "- `map_eligibility` remains `not_map_eligible_without_place_review` until a specific display place is reviewed.",
            "- Indigenous-related public metadata remains human-review-only before any record import.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    global START_YEAR, END_YEAR

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", default="openalex,crossref", help="Comma-separated: openalex,crossref,internet_archive")
    parser.add_argument("--max-families", type=int, default=8)
    parser.add_argument("--family-id", action="append", help="Run only this query family id. May be repeated.")
    parser.add_argument("--start-page", type=int, default=1)
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--per-page", type=int, default=25)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--delay", type=float, default=0.7)
    parser.add_argument("--mailto", default="research@ausfigures.com")
    parser.add_argument("--year-start", type=int, default=START_YEAR)
    parser.add_argument("--year-end", type=int, default=END_YEAR)
    parser.add_argument("--candidates-output", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--request-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    START_YEAR = args.year_start
    END_YEAR = args.year_end

    sources = {source.strip() for source in args.sources.split(",") if source.strip()}
    families = sorted(QUERY_FAMILIES, key=lambda family: family.priority)
    if args.family_id:
        requested = set(args.family_id)
        families = [family for family in families if family.family_id in requested]
        missing = sorted(requested - {family.family_id for family in families})
        if missing:
            raise SystemExit("Unknown query family id(s): " + ", ".join(missing))
    else:
        families = families[: args.max_families]
    args.candidates_output.parent.mkdir(parents=True, exist_ok=True)
    args.request_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)

    started = utc_now_iso()
    candidates: list[dict[str, Any]] = []
    request_rows: list[dict[str, Any]] = []

    with args.candidates_output.open("w", encoding="utf-8", newline="") as cand_handle, args.request_output.open(
        "w", encoding="utf-8", newline=""
    ) as req_handle, args.raw_output.open("w", encoding="utf-8") as raw_handle:
        cand_writer = csv.DictWriter(cand_handle, fieldnames=CANDIDATE_FIELDS)
        req_writer = csv.DictWriter(req_handle, fieldnames=REQUEST_FIELDS)
        cand_writer.writeheader()
        req_writer.writeheader()

        for family in families:
            for source_api in ("openalex", "crossref", "internet_archive"):
                if source_api not in sources:
                    continue
                for page in range(args.start_page, args.start_page + args.pages):
                    if source_api == "openalex":
                        url = openalex_url(family, page, args.per_page, args.mailto)
                        processor = process_openalex
                    elif source_api == "crossref":
                        url = crossref_url(family, page, args.per_page, args.mailto)
                        processor = process_crossref
                    else:
                        url = ia_url(family, page, args.per_page)
                        processor = process_ia

                    payload, status, elapsed = curl_json(url, args.timeout)
                    if payload is None:
                        req_row = {
                            "source_api": source_api,
                            "query_family_id": family.family_id,
                            "query_string": family.search,
                            "page": page,
                            "status": "fetch_error",
                            "http_status_or_error": status,
                            "raw_hit_count": "",
                            "sampled_items": 0,
                            "clean_candidates": 0,
                            "rejected_items": 0,
                            "elapsed_seconds": round(elapsed, 3),
                            "request_url_redacted": redacted(url),
                        }
                        req_writer.writerow(req_row)
                        req_handle.flush()
                        request_rows.append(req_row)
                        print(f"[crawl-gap] {source_api} {family.family_id} page={page} fetch_error={status}", flush=True)
                        continue

                    raw_count, raw_items, rows = processor(payload, family, family.search, source_api)
                    clean_count = sum(1 for row in rows if row["candidate_status"] == "public_metadata_candidate")
                    req_row = {
                        "source_api": source_api,
                        "query_family_id": family.family_id,
                        "query_string": family.search,
                        "page": page,
                        "status": "ok",
                        "http_status_or_error": status,
                        "raw_hit_count": raw_count,
                        "sampled_items": len(rows),
                        "clean_candidates": clean_count,
                        "rejected_items": len(rows) - clean_count,
                        "elapsed_seconds": round(elapsed, 3),
                        "request_url_redacted": redacted(url),
                    }
                    req_writer.writerow(req_row)
                    req_handle.flush()
                    request_rows.append(req_row)
                    for raw in raw_items:
                        raw["crawled_at"] = utc_now_iso()
                        raw_handle.write(json.dumps(raw, ensure_ascii=False, sort_keys=True) + "\n")
                    raw_handle.flush()
                    for row in rows:
                        cand_writer.writerow(row)
                        candidates.append(row)
                    cand_handle.flush()
                    print(
                        f"[crawl-gap] {source_api} {family.family_id} page={page} "
                        f"hits={raw_count} sampled={len(rows)} clean={clean_count}",
                        flush=True,
                    )
                    time.sleep(args.delay)

    finished = utc_now_iso()
    write_report(args.report, candidates, request_rows, started, finished)
    accepted_count = sum(1 for row in candidates if row["candidate_status"] == "public_metadata_candidate")
    print(f"[crawl-gap] finished requests={len(request_rows)} clean_candidates={accepted_count} report={args.report}", flush=True)


if __name__ == "__main__":
    main()
