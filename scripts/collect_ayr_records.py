#!/usr/bin/env python3
"""Collect card-ready public Australian Yowie Research records.

This is a conservative live collector for public report pages on
yowiehunters.com.au. It does not insert search leads. A page must provide
enough information for the frontend record card before it is written to the
records table: year, title/figure, public source, Australian state/territory,
and an objective display summary.
"""

from __future__ import annotations

import argparse
import csv
import html
import logging
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.classify import classify_record
from aus_humanoid.db import DEFAULT_DB_PATH, connect, initialise_database
from aus_humanoid.normalise import parse_year, slugify
from aus_humanoid.utils import PROJECT_ROOT, json_dumps, utc_now_iso


LOGGER = logging.getLogger("collect_ayr_records")

BASE_URL = "https://www.yowiehunters.com.au/"
SOURCE_NAME = "Australian Yowie Research"
SOURCE_TYPE = "modern_web"
ROUND_NAME = "ayr_public_reports_round_001"
USER_AGENT = "AustralianHumanoidPublicTexts/0.2 research contact: local"
RAW_TEXT_DIR = PROJECT_ROOT / "data" / "raw" / "text"
INTERIM_CSV = PROJECT_ROOT / "data" / "interim" / "ayr_record_candidates.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "ayr_collection_report.md"

CURRENT_YEAR = 2026
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20[0-2]\d)\b")

STATE_PAGES: dict[str, dict[str, str]] = {
    "NSW": {"path": "/new-south-wales", "name": "New South Wales"},
    "QLD": {"path": "/queensland", "name": "Queensland"},
    "VIC": {"path": "/victoria", "name": "Victoria"},
    "WA": {"path": "/western-australia", "name": "Western Australia"},
    "SA": {"path": "/south-australia", "name": "South Australia"},
    "NT": {"path": "/northern-territory", "name": "Northern Territory"},
    "TAS": {"path": "/tasmania", "name": "Tasmania"},
}

# Low-availability states are exhausted first; high-availability states fill
# the remaining target using a year-spread selection.
DEFAULT_STATE_QUOTAS: dict[str, int] = {
    "WA": 10,
    "SA": 7,
    "NT": 9,
    "TAS": 4,
    "VIC": 40,
    "NSW": 65,
    "QLD": 65,
}

STATE_NAME_TO_CODE = {
    "new south wales": "NSW",
    "nsw": "NSW",
    "queensland": "QLD",
    "qld": "QLD",
    "victoria": "VIC",
    "vic": "VIC",
    "western australia": "WA",
    "wa": "WA",
    "south australia": "SA",
    "sa": "SA",
    "northern territory": "NT",
    "nt": "NT",
    "tasmania": "TAS",
    "tas": "TAS",
    "australian capital territory": "ACT",
    "act": "ACT",
}

STATE_CODE_TO_NAME = {code: row["name"] for code, row in STATE_PAGES.items()}
STATE_CODE_TO_NAME["ACT"] = "Australian Capital Territory"


@dataclass(frozen=True)
class Candidate:
    state_code: str
    state_name: str
    path: str
    url: str
    listing_title: str
    listing_year: int | None


@dataclass
class ParsedRecord:
    candidate: Candidate
    title: str
    year: int
    date_text: str
    place_name: str
    state_code: str
    state_name: str
    location_field: str
    event: str
    terrain: str
    body_excerpt: str
    display_summary: str
    raw_text: str


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def clean_space(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(html.unescape(value).replace("\xa0", " ").split())


def strip_tags(fragment: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", fragment)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("\xa0", " ")
    lines = [clean_space(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def compact_excerpt(text: str, limit: int = 320) -> str:
    cleaned = clean_space(text)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def fetch(session: requests.Session, url: str, timeout: int = 25) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def robots_allows_public_reports(session: requests.Session) -> tuple[bool, str]:
    text = fetch(session, urljoin(BASE_URL, "/robots.txt"), timeout=20)
    disallowed = []
    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("disallow:"):
            disallowed.append(line.split(":", 1)[1].strip())
    blocked_report_paths = [path for path in STATE_PAGES.values() if path["path"] in disallowed]
    if blocked_report_paths:
        return False, "State report paths are blocked by robots.txt."
    return True, "robots.txt checked; public state/report paths are not disallowed."


def parse_listing(html_text: str, state_code: str) -> list[Candidate]:
    state = STATE_PAGES[state_code]
    state_path = state["path"]
    pattern = re.compile(
        rf'href=["\']({re.escape(state_path)}/[^"\']+)["\'][^>]*>(.*?)</a>',
        flags=re.IGNORECASE | re.DOTALL,
    )
    candidates: list[Candidate] = []
    seen: set[str] = set()
    for href, anchor in pattern.findall(html_text):
        path = href.split("#", 1)[0].split("?", 1)[0]
        if path in seen:
            continue
        title = clean_space(re.sub(r"<[^>]+>", " ", anchor))
        year = parse_year(title) or parse_year(path)
        if not title or year is None:
            continue
        if year > CURRENT_YEAR:
            continue
        seen.add(path)
        candidates.append(
            Candidate(
                state_code=state_code,
                state_name=state["name"],
                path=path,
                url=urljoin(BASE_URL, path),
                listing_title=title,
                listing_year=year,
            )
        )
    return candidates


def extract_h1(html_text: str, fallback: str) -> str:
    match = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return clean_space(re.sub(r"<[^>]+>", " ", match.group(1)))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if title_match:
        title = clean_space(re.sub(r"<[^>]+>", " ", title_match.group(1)))
        return re.sub(r"^Australian Yowie Research\s*-\s*", "", title).strip() or fallback
    return fallback


def extract_body_text(html_text: str) -> str:
    match = re.search(
        r'<div[^>]+class=["\'][^"\']*com-content-article__body[^"\']*["\'][^>]*>(.*?)</div>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        return strip_tags(match.group(1))
    main_match = re.search(r"<main[^>]*>(.*?)</main>", html_text, flags=re.IGNORECASE | re.DOTALL)
    if main_match:
        return strip_tags(main_match.group(1))
    return strip_tags(html_text)


def labelled_field(text: str, label: str) -> str:
    pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$")
    match = pattern.search(text)
    if match:
        return clean_space(match.group(1))
    inline = re.compile(
        rf"(?is)\b{re.escape(label)}\s*:\s*(.+?)(?:\n[A-Z][A-Za-z ]{{2,18}}\s*:|\Z)"
    )
    match = inline.search(text)
    return clean_space(match.group(1)) if match else ""


def infer_state_code(text: str, fallback: str) -> str:
    lowered = text.lower()
    for name, code in sorted(STATE_NAME_TO_CODE.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered):
            return code
    return fallback


def infer_place(title: str, location_field: str, state_code: str) -> str:
    source = location_field or title
    source = re.sub(YEAR_RE, "", source)
    source = re.sub(r"\([^)]*\)", "", source)
    state_name = STATE_CODE_TO_NAME.get(state_code, "")
    for token in [state_name, state_code]:
        if token:
            source = re.sub(rf"\b{re.escape(token)}\b", "", source, flags=re.IGNORECASE)
    source = re.sub(r"\bAustralia\b", "", source, flags=re.IGNORECASE)
    source = source.replace("&amp;", "&")
    source = re.split(r"\s+-\s+|\s+:", source)[0]
    source = source.strip(" ,.-")
    if "," in source:
        source = source.split(",", 1)[0].strip()
    return clean_space(source) or state_name or "Australia"


def first_story_paragraph(body_text: str) -> str:
    skip_prefixes = ("location:", "event:", "date:", "terrain:", "x", "report by", "posted")
    paragraphs = [clean_space(part) for part in body_text.splitlines()]
    for paragraph in paragraphs:
        if len(paragraph) < 40:
            continue
        lowered = paragraph.lower()
        if lowered.startswith(skip_prefixes):
            continue
        return paragraph
    return ""


def parse_detail_page(candidate: Candidate, html_text: str) -> ParsedRecord | None:
    title = extract_h1(html_text, candidate.listing_title)
    body_text = extract_body_text(html_text)
    location_field = labelled_field(body_text, "Location")
    event = labelled_field(body_text, "Event")
    date_text = labelled_field(body_text, "Date")
    terrain = labelled_field(body_text, "Terrain")

    year = parse_year(date_text) or parse_year(title) or candidate.listing_year
    if year is None or year > CURRENT_YEAR:
        return None

    state_code = infer_state_code("\n".join([location_field, title, candidate.path]), candidate.state_code)
    if state_code not in STATE_CODE_TO_NAME:
        return None
    state_name = STATE_CODE_TO_NAME[state_code]
    place = infer_place(title, location_field, state_code)
    story = first_story_paragraph(body_text)
    body_excerpt = compact_excerpt(story or body_text, 360)

    display_parts = [
        f"Public AYR report page for {title}.",
        f"Source-stated location: {location_field or place + ', ' + state_name}.",
    ]
    if event:
        display_parts.append(f"Event field: {event}.")
    if terrain:
        display_parts.append(f"Terrain field: {terrain}.")
    if body_excerpt:
        display_parts.append(f"Body excerpt retained for review: {body_excerpt}")
    display_summary = " ".join(display_parts)

    if not (title and display_summary and place and state_code):
        return None

    raw_text = "\n".join(
        part
        for part in [
            title,
            f"URL: {candidate.url}",
            f"Source: {SOURCE_NAME}",
            f"Date: {date_text or year}",
            f"Location: {location_field or place + ', ' + state_name}",
            f"Event: {event}" if event else "",
            f"Terrain: {terrain}" if terrain else "",
            "",
            "Objective display summary:",
            display_summary,
        ]
        if part
    )
    return ParsedRecord(
        candidate=candidate,
        title=title,
        year=int(year),
        date_text=date_text or str(year),
        place_name=place,
        state_code=state_code,
        state_name=state_name,
        location_field=location_field,
        event=event,
        terrain=terrain,
        body_excerpt=body_excerpt,
        display_summary=display_summary,
        raw_text=raw_text,
    )


def date_band(year: int | None) -> str:
    if year is None:
        return "undated"
    if 1803 <= year <= 1841:
        return "backsearch_1803_1841"
    if 1842 <= year <= 1875:
        return "anchor_1842_1875"
    if 1876 <= year <= 1969:
        return "expansion_1876_1969"
    if year >= 1970:
        return "modern_1970_present"
    return "outside_scope"


def spread_select(candidates: list[Candidate], count: int) -> list[Candidate]:
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.listing_year if item.listing_year is not None else 9999,
            item.listing_title,
        ),
    )
    if count >= len(ordered):
        return ordered
    if count <= 0:
        return []
    if count == 1:
        return [ordered[0]]
    selected: list[Candidate] = []
    used: set[int] = set()
    step = (len(ordered) - 1) / (count - 1)
    for index in range(count):
        raw = round(index * step)
        while raw in used and raw + 1 < len(ordered):
            raw += 1
        used.add(raw)
        selected.append(ordered[raw])
    return selected


def ordered_candidates(candidates_by_state: dict[str, list[Candidate]], target: int) -> list[Candidate]:
    selected: list[Candidate] = []
    seen: set[str] = set()
    for state_code, quota in DEFAULT_STATE_QUOTAS.items():
        picks = spread_select(candidates_by_state.get(state_code, []), quota)
        for pick in picks:
            if pick.path not in seen:
                selected.append(pick)
                seen.add(pick.path)
    # If the target is higher than the default quota sum, or if some fetched
    # pages are skipped, continue with every remaining candidate in a round-robin
    # state order rather than silently stopping early.
    remaining = {
        state_code: [item for item in rows if item.path not in seen]
        for state_code, rows in candidates_by_state.items()
    }
    state_order = ["WA", "SA", "NT", "TAS", "VIC", "NSW", "QLD"]
    while len(selected) < target * 3 and any(remaining.values()):
        for state_code in state_order:
            if remaining.get(state_code):
                pick = remaining[state_code].pop(0)
                if pick.path not in seen:
                    selected.append(pick)
                    seen.add(pick.path)
    return selected


def ensure_source(conn) -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_name = ?",
        (SOURCE_NAME,),
    ).fetchone()
    if row:
        source_id = int(row["source_id"])
        conn.execute(
            """
            UPDATE sources
            SET source_type = ?, base_url = ?, access_method = ?,
                publicness_level = ?, ethics_notes = ?
            WHERE source_id = ?
            """,
            (
                SOURCE_TYPE,
                BASE_URL,
                "public_report_pages_low_rate",
                "public_page",
                (
                    "Public AYR report pages only. Records are display/review "
                    "signals and do not assert final truth or collect restricted material."
                ),
                source_id,
            ),
        )
        return source_id
    cursor = conn.execute(
        """
        INSERT INTO sources (
            source_name, source_type, base_url, access_method,
            publicness_level, ethics_notes
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            SOURCE_NAME,
            SOURCE_TYPE,
            BASE_URL,
            "public_report_pages_low_rate",
            "public_page",
            (
                "Public AYR report pages only. Records are display/review "
                "signals and do not assert final truth or collect restricted material."
            ),
        ),
    )
    return int(cursor.lastrowid)


def yowie_figure_id(conn) -> int:
    row = conn.execute("SELECT figure_id FROM figures WHERE canonical_name = 'Yowie'").fetchone()
    if row is None:
        raise ValueError("Yowie figure is not seeded. Run make seed first.")
    return int(row["figure_id"])


def existing_record_id(conn, external_id: str, url: str) -> int | None:
    row = conn.execute(
        "SELECT record_id FROM records WHERE external_id = ? OR url = ? LIMIT 1",
        (external_id, url),
    ).fetchone()
    return int(row["record_id"]) if row else None


def save_raw_text(record_id: int, title: str, raw_text: str) -> str:
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_TEXT_DIR / f"record_{record_id}_{slugify(title)}.txt"
    path.write_text(raw_text, encoding="utf-8")
    return str(path.relative_to(PROJECT_ROOT))


def upsert_location(conn, parsed: ParsedRecord) -> int:
    if parsed.place_name == parsed.state_name:
        stored_place = parsed.state_name
        location_type = "state_or_territory"
    else:
        stored_place = f"{parsed.place_name}, {parsed.state_code}"
        location_type = "locality"
    conn.execute(
        """
        INSERT INTO locations (
            place_name, region, state_territory, country, latitude, longitude,
            location_type, geocode_source, verification_status, notes
        ) VALUES (?, ?, ?, 'Australia', NULL, NULL, ?, ?, ?, ?)
        ON CONFLICT(place_name) DO UPDATE SET
            region = excluded.region,
            state_territory = excluded.state_territory,
            country = excluded.country,
            location_type = excluded.location_type,
            geocode_source = excluded.geocode_source,
            verification_status = excluded.verification_status,
            notes = excluded.notes
        """,
        (
            stored_place,
            parsed.place_name if parsed.place_name != parsed.state_name else parsed.state_name,
            parsed.state_code,
            location_type,
            "ayr_public_page_location_field",
            "source_named_place_needs_geocode",
            "Place/state extracted from public AYR page title or Location field; coordinates not asserted.",
        ),
    )
    row = conn.execute(
        "SELECT location_id FROM locations WHERE place_name = ?",
        (stored_place,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Location insert failed for {stored_place}")
    return int(row["location_id"])


def insert_record(conn, parsed: ParsedRecord, source_id: int, figure_id: int) -> int:
    external_id = f"ayr:{parsed.candidate.path.strip('/')}"
    now = utc_now_iso()
    metadata = {
        "collector": ROUND_NAME,
        "source": SOURCE_NAME,
        "source_url": parsed.candidate.url,
        "state_code": parsed.state_code,
        "state_name": parsed.state_name,
        "place_name": parsed.place_name,
        "location_field": parsed.location_field,
        "event": parsed.event,
        "terrain": parsed.terrain,
        "body_excerpt": parsed.body_excerpt,
        "listing_title": parsed.candidate.listing_title,
        "listing_path": parsed.candidate.path,
        "card_ready": True,
        "card_ready_fields": ["year", "title", "source", "state_territory", "display_summary"],
        "collected_at": now,
    }
    cursor = conn.execute(
        """
        INSERT INTO records (
            source_id, query_id, figure_id, external_id, title, publication,
            author, date_published, year, url, snippet, raw_metadata_json,
            access_status, publicness_level, ingestion_status, created_at,
            updated_at
        ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_id,
            figure_id,
            external_id,
            parsed.title,
            SOURCE_NAME,
            "",
            parsed.date_text,
            parsed.year,
            parsed.candidate.url,
            parsed.display_summary,
            json_dumps(metadata),
            "public_page_collected",
            "public_page",
            "raw_public_web_card_ready",
            now,
            now,
        ),
    )
    record_id = int(cursor.lastrowid)
    full_text_path = save_raw_text(record_id, parsed.title, parsed.raw_text)
    conn.execute(
        "UPDATE records SET full_text_path = ? WHERE record_id = ?",
        (full_text_path, record_id),
    )

    classify_record(conn, record_id)
    conn.execute(
        """
        INSERT INTO coding (
            record_id, canonical_figure_guess, figure_name_as_printed,
            variant_normalisation, ontology_code, humanoid_degree_code,
            source_voice, genre, publicness_code, relevance_code, ethics_flag,
            notes, coded_by, coded_at
        ) VALUES (?, 'Yowie', 'Yowie', 'Yowie', 'cryptid_style_apeman',
                  'explicit_humanoid', 'public_report_archive',
                  'sighting_report', 'public_heritage_page', 'relevant',
                  'ok_public', ?, 'system_ayr_collector', ?)
        ON CONFLICT(record_id) DO UPDATE SET
            canonical_figure_guess = excluded.canonical_figure_guess,
            figure_name_as_printed = excluded.figure_name_as_printed,
            variant_normalisation = excluded.variant_normalisation,
            ontology_code = excluded.ontology_code,
            humanoid_degree_code = excluded.humanoid_degree_code,
            source_voice = excluded.source_voice,
            genre = excluded.genre,
            publicness_code = excluded.publicness_code,
            relevance_code = excluded.relevance_code,
            ethics_flag = excluded.ethics_flag,
            notes = excluded.notes,
            coded_by = excluded.coded_by,
            coded_at = excluded.coded_at
        """,
        (
            record_id,
            "AYR public report page collected for card display; source fields require human review before analysis.",
            now,
        ),
    )

    location_id = upsert_location(conn, parsed)
    evidence = parsed.location_field or parsed.title
    conn.execute(
        """
        INSERT OR REPLACE INTO record_locations (
            record_id, location_id, relation_type, evidence_text, confidence, notes
        ) VALUES (?, ?, 'reported_place', ?, ?, ?)
        """,
        (
            record_id,
            location_id,
            evidence,
            "high" if parsed.location_field else "medium",
            "AYR page title/Location field; place is source-stated and awaits geocoding if needed.",
        ),
    )
    return record_id


def write_status_csv(rows: list[dict[str, Any]], path: Path = INTERIM_CSV) -> None:
    fieldnames = [
        "status",
        "record_id",
        "skip_reason",
        "state_code",
        "year",
        "title",
        "url",
        "place_name",
        "date_band",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_report(
    path: Path,
    started_at: str,
    finished_at: str,
    start_count: int,
    end_count: int,
    target: int,
    statuses: list[dict[str, Any]],
    robots_note: str,
) -> None:
    inserted = [row for row in statuses if row.get("status") == "inserted"]
    skipped = [row for row in statuses if row.get("status") != "inserted"]
    by_state = Counter(row.get("state_code") for row in inserted)
    by_band = Counter(row.get("date_band") for row in inserted)
    by_skip = Counter(row.get("skip_reason") for row in skipped if row.get("skip_reason"))
    lines = [
        "# AYR Public Record Card Collection Report",
        "",
        "## Execution Context",
        f"- Run: `{ROUND_NAME}`",
        f"- Started: `{started_at}`",
        f"- Finished: `{finished_at}`",
        f"- Source: [{SOURCE_NAME}]({BASE_URL})",
        f"- Robots/publicness check: {robots_note}",
        f"- Starting record count: {start_count}",
        f"- Ending record count: {end_count}",
        f"- Target new card-ready records: {target}",
        f"- Inserted new card-ready records: {len(inserted)}",
        f"- Candidate/status CSV: `{INTERIM_CSV.relative_to(PROJECT_ROOT)}`",
        "",
        "## Card-Ready Gate",
        "A page was inserted only when it supplied enough display data for the record card: year, title or Yowie figure, public source URL, Australian state/territory, and a concise objective summary. Search leads and pages missing those fields were skipped.",
        "",
        "## New Records By State/Territory",
    ]
    for code in ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"]:
        lines.append(f"- {code}: {by_state.get(code, 0)}")
    lines.extend(["", "## New Records By Date Band"])
    for band in [
        "backsearch_1803_1841",
        "anchor_1842_1875",
        "expansion_1876_1969",
        "modern_1970_present",
        "undated",
    ]:
        lines.append(f"- {band}: {by_band.get(band, 0)}")
    lines.extend(["", "## Skipped Candidates"])
    if by_skip:
        for reason, count in by_skip.most_common():
            lines.append(f"- {reason}: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Coverage Note",
            "The AYR state pages are not evenly distributed. NSW, QLD, and VIC have many more public report pages than WA, SA, NT, and TAS, so this run exhausts low-availability states first and fills the 200-record target from higher-availability states. The imbalance should be addressed in the next round with source-specific searches rather than by fabricating regional symmetry.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> int:
    started_at = utc_now_iso()
    initialise_database(args.db)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    robots_ok, robots_note = robots_allows_public_reports(session)
    if not robots_ok:
        raise RuntimeError(robots_note)

    candidates_by_state: dict[str, list[Candidate]] = {}
    for state_code in args.states:
        listing_url = urljoin(BASE_URL, STATE_PAGES[state_code]["path"])
        LOGGER.info("Fetching listing %s", listing_url)
        html_text = fetch(session, listing_url)
        candidates_by_state[state_code] = parse_listing(html_text, state_code)
        LOGGER.info("%s candidates: %d", state_code, len(candidates_by_state[state_code]))
        time.sleep(args.delay)

    candidates = ordered_candidates(candidates_by_state, args.target)
    statuses: list[dict[str, Any]] = []
    inserted_count = 0

    with connect(args.db) as conn:
        start_count = int(conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"])
        source_id = ensure_source(conn)
        figure_id = yowie_figure_id(conn)
        for index, candidate in enumerate(candidates, start=1):
            if inserted_count >= args.target:
                break
            external_id = f"ayr:{candidate.path.strip('/')}"
            duplicate_id = existing_record_id(conn, external_id, candidate.url)
            if duplicate_id is not None:
                statuses.append(
                    {
                        "status": "skipped",
                        "record_id": duplicate_id,
                        "skip_reason": "duplicate_existing_record",
                        "state_code": candidate.state_code,
                        "year": candidate.listing_year,
                        "title": candidate.listing_title,
                        "url": candidate.url,
                        "date_band": date_band(candidate.listing_year),
                    }
                )
                continue
            try:
                html_text = fetch(session, candidate.url)
                parsed = parse_detail_page(candidate, html_text)
            except requests.RequestException as exc:
                statuses.append(
                    {
                        "status": "skipped",
                        "skip_reason": f"fetch_error:{exc.__class__.__name__}",
                        "state_code": candidate.state_code,
                        "year": candidate.listing_year,
                        "title": candidate.listing_title,
                        "url": candidate.url,
                        "date_band": date_band(candidate.listing_year),
                    }
                )
                LOGGER.warning("Fetch failed for %s: %s", candidate.url, exc)
                time.sleep(args.delay)
                continue
            if parsed is None:
                statuses.append(
                    {
                        "status": "skipped",
                        "skip_reason": "missing_card_ready_fields",
                        "state_code": candidate.state_code,
                        "year": candidate.listing_year,
                        "title": candidate.listing_title,
                        "url": candidate.url,
                        "date_band": date_band(candidate.listing_year),
                    }
                )
                time.sleep(args.delay)
                continue
            if args.dry_run:
                record_id = ""
                status = "dry_run_card_ready"
                inserted_count += 1
            else:
                record_id = insert_record(conn, parsed, source_id, figure_id)
                inserted_count += 1
                status = "inserted"
                if inserted_count % 25 == 0:
                    conn.commit()
                    LOGGER.info("Inserted %d/%d records", inserted_count, args.target)
            statuses.append(
                {
                    "status": status,
                    "record_id": record_id,
                    "skip_reason": "",
                    "state_code": parsed.state_code,
                    "year": parsed.year,
                    "title": parsed.title,
                    "url": candidate.url,
                    "place_name": parsed.place_name,
                    "date_band": date_band(parsed.year),
                }
            )
            if index % 20 == 0:
                LOGGER.info("Checked %d candidates; inserted %d", index, inserted_count)
            time.sleep(args.delay)

        conn.commit()
        end_count = int(conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"])

    finished_at = utc_now_iso()
    write_status_csv(statuses, Path(args.candidates_output))
    write_report(
        Path(args.report),
        started_at,
        finished_at,
        start_count,
        end_count,
        args.target,
        statuses,
        robots_note,
    )
    LOGGER.info("Wrote status CSV: %s", args.candidates_output)
    LOGGER.info("Wrote report: %s", args.report)
    if not args.dry_run and inserted_count < args.target:
        LOGGER.error("Inserted %d card-ready records; target was %d", inserted_count, args.target)
        return 2
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--target", type=int, default=200, help="Number of new card-ready records to insert")
    parser.add_argument("--delay", type=float, default=0.25, help="Delay between HTTP requests in seconds")
    parser.add_argument(
        "--states",
        nargs="+",
        default=list(STATE_PAGES.keys()),
        choices=list(STATE_PAGES.keys()),
        help="State pages to collect from",
    )
    parser.add_argument("--candidates-output", default=str(INTERIM_CSV), help="Candidate/status CSV path")
    parser.add_argument("--report", default=str(REPORT_PATH), help="Markdown report path")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and parse, but do not insert records")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(args.verbose)
    try:
        raise SystemExit(collect(args))
    except KeyboardInterrupt:
        LOGGER.error("Interrupted")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
