#!/usr/bin/env python3
"""Collect card-ready public metadata records from Internet Archive."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.classify import classify_record
from aus_humanoid.db import DEFAULT_DB_PATH, connect, initialise_database
from aus_humanoid.normalise import normalise_alias, slugify
from aus_humanoid.utils import PROJECT_ROOT, json_dumps, utc_now_iso


LOGGER = logging.getLogger("collect_internet_archive_metadata")
BASE_URL = "https://archive.org/advancedsearch.php"
SOURCE_NAME = "Internet Archive"
SOURCE_TYPE = "internet_archive_metadata"
ROUND_NAME = "internet_archive_public_metadata_round_003"
USER_AGENT = "AustralianHumanoidPublicTexts/0.3 research contact: local"
RAW_TEXT_DIR = PROJECT_ROOT / "data" / "raw" / "text"
DEFAULT_STATUS_CSV = PROJECT_ROOT / "data" / "interim" / "internet_archive_round_003_candidates.csv"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "internet_archive_round_003_report.md"


@dataclass(frozen=True)
class TermSpec:
    figure: str
    term: str
    state: str
    region: str
    confidence: str
    priority: int


TERM_SPECS = [
    TermSpec("Yowie", "Yowie", "AU", "Australia", "low", 5),
    TermSpec("Wandjina", "Wandjina", "WA", "Western Australia", "medium", 5),
    TermSpec("Quinkan", "Quinkan", "QLD", "Queensland", "medium", 5),
    TermSpec("Mimih", "Mimih", "NT", "Northern Territory", "medium", 4),
    TermSpec("Nargun", "Nargun", "VIC", "Victoria", "medium", 4),
    TermSpec("Pangkarlangu", "Pangkarlangu", "NT", "Northern Territory", "medium", 4),
    TermSpec("Yara-ma-yha-who", "Yara-ma-yha-who", "AU", "Australia", "low", 4),
    TermSpec("Hairy Man", "hairy man", "AU", "Australia", "low", 3),
    TermSpec("Garkain", "Garkain", "NT", "Northern Territory", "medium", 3),
    TermSpec("Mokoi", "Mokoi", "NT", "Northern Territory", "medium", 3),
    TermSpec("Mamu", "Mamu", "AU", "Australia", "low", 2),
    TermSpec("Puttikan", "Puttikan", "VIC", "Victoria", "medium", 2),
    TermSpec("Yaroma", "Yaroma", "AU", "Australia", "low", 2),
    TermSpec("Doolaga", "Doolaga", "AU", "Australia", "low", 1),
    TermSpec("Dooligah", "Dooligah", "AU", "Australia", "low", 1),
    TermSpec("Thoolagal", "Thoolagal", "AU", "Australia", "low", 1),
    TermSpec("Tjangara", "Tjangara", "AU", "Australia", "low", 1),
]


NOISE_PATTERNS = [
    "Yowie Group",
    "Yowie Deschanel",
    "Whetstone Industries",
    "commercial for Yowie",
    "Across America",
    "The Godamn Slanderbob",
    "TY the Tasmanian Tiger",
    "Ty the Tasmanian Tiger",
    "Night of the Quinkan",
    "Ceratodus nargun",
    "Witcher",
    "Gwent",
    "Monster Slayer",
    "Alpha Garkain",
    "virtual photography",
    "Nigeria",
    "China Mail",
    "By Wikipedia",
    "Wikipedia 2",
    "Wikipedia 3",
    "Poeżija",
    "Joe Saliba",
    "Nazca",
    "América do Sul",
    "America do Sul",
    "Alien",
    "Extraterrestre",
    "Palenque",
    "Cadbury",
    "chocolate",
    "toy",
    "Kinder",
    "unboxing",
    "Yowie Bay",
    "Yahoo",
    "Mamu-B",
    "SIV",
    "HIV",
    "macaque",
    "anime",
    "fanfiction",
    "music video",
]

AUSTRALIA_CONTEXT = [
    "australia",
    "australian",
    "aboriginal",
    "indigenous",
    "arnhem",
    "kimberley",
    "cape york",
    "queensland",
    "victoria",
    "tasmania",
    "western australia",
    "south australia",
    "northern territory",
    "bunyip",
]

STATE_CONTEXT = {
    "WA": ["western australia", "kimberley", "wandjina"],
    "QLD": ["queensland", "cape york", "quinkan", "laura"],
    "NT": ["northern territory", "arnhem", "mimih", "garkain", "pangkarlangu"],
    "VIC": ["victoria", "gippsland", "nargun", "puttikan"],
    "TAS": ["tasmania", "tasmanian"],
    "ACT": ["canberra", "australian capital territory"],
    "SA": ["south australia"],
}


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def clean_space(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value if item)
    return " ".join(str(value or "").replace("\xa0", " ").split())


def parse_year(value: Any) -> int | None:
    match = re.search(r"(18\d{2}|19\d{2}|20[0-2]\d)", clean_space(value))
    if not match:
        return None
    year = int(match.group(1))
    if 1803 <= year <= 2026:
        return year
    return None


def title_matches(spec: TermSpec, text: str) -> bool:
    norm_text = normalise_alias(text)
    norm_term = normalise_alias(spec.term)
    if norm_term in norm_text:
        return True
    return spec.figure == "Yara-ma-yha-who" and "yara ma yha who" in norm_text


def has_noise(text: str) -> str | None:
    lowered = text.lower()
    for pattern in NOISE_PATTERNS:
        if pattern.lower() in lowered:
            return pattern
    return None


def has_australia_context(spec: TermSpec, text: str) -> bool:
    lowered = text.lower()
    if spec.figure == "Yowie":
        return any(
            term in lowered
            for term in [
                "australia",
                "australian",
                "cryptid",
                "bigfoot",
                "rex gilroy",
                "tony healy",
            ]
        )
    if spec.state != "AU" and any(term in lowered for term in STATE_CONTEXT.get(spec.state, [])):
        return True
    return any(term in lowered for term in AUSTRALIA_CONTEXT)


def infer_state(spec: TermSpec, text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    names = {
        "WA": "Western Australia",
        "QLD": "Queensland",
        "NT": "Northern Territory",
        "VIC": "Victoria",
        "TAS": "Tasmania",
        "ACT": "Australian Capital Territory",
        "SA": "South Australia",
    }
    for state, patterns in STATE_CONTEXT.items():
        if any(pattern in lowered for pattern in patterns):
            return state, names[state], "medium"
    if spec.state == "AU":
        return "", "Australia", "low"
    return spec.state, spec.region, spec.confidence


def fetch_docs(spec: TermSpec, rows: int, max_pages: int, delay: float) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    query = f'title:("{spec.term}") OR description:("{spec.term}")'
    params = [
        ("q", query),
        ("fl[]", "identifier"),
        ("fl[]", "title"),
        ("fl[]", "date"),
        ("fl[]", "creator"),
        ("fl[]", "description"),
        ("fl[]", "mediatype"),
        ("fl[]", "collection"),
        ("fl[]", "publicdate"),
        ("fl[]", "year"),
        ("rows", str(rows)),
        ("output", "json"),
    ]
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for page in range(1, max_pages + 1):
        request_params = params + [("page", str(page))]
        LOGGER.info("Fetching %s page %s", spec.figure, page)
        response = None
        for attempt in range(3):
            try:
                response = requests.get(BASE_URL, params=request_params, headers=headers, timeout=35)
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    LOGGER.warning("Skipping %s page %s after request failure: %s", spec.figure, page, exc)
                    return docs
                time.sleep(delay + attempt)
        if response is None:
            return docs
        batch = response.json().get("response", {}).get("docs", [])
        if not batch:
            break
        docs.extend(batch)
        if len(batch) < rows:
            break
        time.sleep(delay)
    return docs


def candidate_from_doc(spec: TermSpec, doc: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_space(doc.get("title"))
    description = clean_space(doc.get("description"))
    year = parse_year(doc.get("date")) or parse_year(doc.get("year")) or parse_year(doc.get("publicdate"))
    if not title or year is None:
        return None
    text = "\n".join([title, description, clean_space(doc.get("collection"))])
    if not title_matches(spec, text):
        return None
    noise = has_noise(text)
    if noise:
        return {
            "status": "skipped",
            "skip_reason": f"noise:{noise}",
            "figure": spec.figure,
            "year": year,
            "title": title,
            "url": item_url(doc),
        }
    if not has_australia_context(spec, text):
        return {
            "status": "skipped",
            "skip_reason": "missing_australia_context",
            "figure": spec.figure,
            "year": year,
            "title": title,
            "url": item_url(doc),
        }
    state_code, region, confidence = infer_state(spec, text)
    snippet_parts = [
        f"Public Internet Archive metadata record matching '{spec.term}'.",
        f"Media type: {clean_space(doc.get('mediatype')) or 'unknown'}.",
        f"Location signal is figure-associated region ({region}), not a verified event place.",
    ]
    if description:
        snippet_parts.append("Description excerpt: " + description[:420])
    return {
        "status": "card_ready",
        "skip_reason": "",
        "figure": spec.figure,
        "term": spec.term,
        "state_code": state_code,
        "region": region,
        "location_confidence": confidence,
        "year": year,
        "date_published": clean_space(doc.get("date")) or str(year),
        "title": title,
        "url": item_url(doc),
        "external_id": "internet_archive:" + clean_space(doc.get("identifier")),
        "publication": "Internet Archive",
        "author": clean_space(doc.get("creator")),
        "snippet": " ".join(snippet_parts),
        "raw_metadata": doc,
        "description": description,
        "media_type": clean_space(doc.get("mediatype")),
    }


def item_url(doc: dict[str, Any]) -> str:
    ident = clean_space(doc.get("identifier"))
    return f"https://archive.org/details/{ident}" if ident else ""


def ensure_source(conn) -> int:
    row = conn.execute("SELECT source_id FROM sources WHERE source_name = ?", (SOURCE_NAME,)).fetchone()
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
                "https://archive.org/advancedsearch.php",
                "public_metadata_api",
                "public_metadata",
                "Internet Archive public metadata only; no restricted full text is collected.",
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
            "https://archive.org/advancedsearch.php",
            "public_metadata_api",
            "public_metadata",
            "Internet Archive public metadata only; no restricted full text is collected.",
        ),
    )
    return int(cursor.lastrowid)


def figure_id(conn, name: str) -> int | None:
    row = conn.execute("SELECT figure_id FROM figures WHERE canonical_name = ?", (name,)).fetchone()
    return int(row["figure_id"]) if row else None


def location_id(conn, state_code: str, region: str) -> int:
    place = region if not state_code else f"Figure-associated region: {region}"
    conn.execute(
        """
        INSERT INTO locations (
            place_name, region, state_territory, country, location_type,
            geocode_source, verification_status, notes
        ) VALUES (?, ?, ?, 'Australia', ?, ?, ?, ?)
        ON CONFLICT(place_name) DO UPDATE SET
            region = excluded.region,
            state_territory = excluded.state_territory,
            location_type = excluded.location_type,
            geocode_source = excluded.geocode_source,
            verification_status = excluded.verification_status,
            notes = excluded.notes
        """,
        (
            place,
            region,
            state_code,
            "figure_associated_region" if state_code else "country_or_unclear",
            "internet_archive_term_region_hint",
            "needs_review",
            "Region inferred from matched figure/term context in public metadata, not a verified event place.",
        ),
    )
    row = conn.execute("SELECT location_id FROM locations WHERE place_name = ?", (place,)).fetchone()
    if row is None:
        raise ValueError(f"Location insert failed for {place}")
    return int(row["location_id"])


def save_raw_text(record_id: int, row: dict[str, Any]) -> str:
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_TEXT_DIR / f"record_{record_id}_{slugify(row['title'])}.txt"
    raw = {
        "title": row["title"],
        "source": SOURCE_NAME,
        "url": row["url"],
        "matched_term": row["term"],
        "figure": row["figure"],
        "date_published": row["date_published"],
        "author": row["author"],
        "region_signal": row["region"],
        "location_confidence": row["location_confidence"],
        "description": row["description"],
        "note": "Internet Archive public metadata only; full text was not collected.",
    }
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(PROJECT_ROOT))


def existing_keys(conn) -> tuple[set[str], set[str], set[tuple[str, int]]]:
    external_ids = {
        row["external_id"]
        for row in conn.execute("SELECT external_id FROM records WHERE external_id LIKE 'internet_archive:%'")
        if row["external_id"]
    }
    urls = {normalise_alias(row["url"]) for row in conn.execute("SELECT url FROM records WHERE url IS NOT NULL AND url != ''")}
    title_year = {
        (normalise_alias(row["title"]), int(row["year"]))
        for row in conn.execute("SELECT title, year FROM records WHERE title IS NOT NULL AND year IS NOT NULL")
        if row["title"]
    }
    return external_ids, urls, title_year


def insert_record(conn, row: dict[str, Any], source_id: int) -> int:
    fig_id = figure_id(conn, row["figure"])
    now = utc_now_iso()
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
            fig_id,
            row["external_id"],
            row["title"],
            row["publication"],
            row["author"],
            row["date_published"],
            row["year"],
            row["url"],
            row["snippet"],
            json_dumps(
                {
                    "collector": ROUND_NAME,
                    "matched_term": row["term"],
                    "figure": row["figure"],
                    "state_code": row["state_code"],
                    "region": row["region"],
                    "location_confidence": row["location_confidence"],
                    "media_type": row["media_type"],
                    "card_ready": True,
                    "card_ready_fields": ["year", "title", "source", "url", "snippet", "region_signal"],
                    "metadata": row["raw_metadata"],
                    "collected_at": now,
                }
            ),
            "public_metadata_collected",
            "public_metadata",
            "raw_public_metadata_card_ready",
            now,
            now,
        ),
    )
    record_id = int(cursor.lastrowid)
    full_text_path = save_raw_text(record_id, row)
    conn.execute("UPDATE records SET full_text_path = ? WHERE record_id = ?", (full_text_path, record_id))
    classify_record(conn, record_id)
    ethics_flag = "caution_indigenous_knowledge" if row["figure"] not in {"Yowie", "Hairy Man", "Yaroma"} else "ok_public"
    conn.execute(
        """
        INSERT INTO coding (
            record_id, canonical_figure_guess, figure_name_as_printed,
            variant_normalisation, ontology_code, humanoid_degree_code,
            source_voice, genre, publicness_code, relevance_code, ethics_flag,
            notes, coded_by, coded_at
        ) VALUES (?, ?, ?, ?, 'unclear', 'unclear', 'unknown',
                  'catalogue_metadata', 'public_metadata', 'needs_review', ?, ?,
                  'system_internet_archive_collector', ?)
        ON CONFLICT(record_id) DO UPDATE SET
            canonical_figure_guess = excluded.canonical_figure_guess,
            figure_name_as_printed = excluded.figure_name_as_printed,
            variant_normalisation = excluded.variant_normalisation,
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
            row["figure"],
            row["term"],
            row["term"],
            ethics_flag,
            "Internet Archive public metadata record; region is a reviewable figure-associated signal, not a verified event place.",
            now,
        ),
    )
    loc_id = location_id(conn, row["state_code"], row["region"])
    conn.execute(
        """
        INSERT OR REPLACE INTO record_locations (
            record_id, location_id, relation_type, evidence_text, confidence, notes
        ) VALUES (?, ?, 'figure_associated_region', ?, ?, ?)
        """,
        (
            record_id,
            loc_id,
            f"Matched term '{row['term']}' in Internet Archive title/description metadata.",
            row["location_confidence"],
            "Internet Archive metadata region hint for display/review; not a geocoded sighting place.",
        ),
    )
    return record_id


def write_status(rows: list[dict[str, Any]], path: Path) -> None:
    fields = ["status", "skip_reason", "record_id", "figure", "term", "state_code", "year", "title", "url"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def date_band(year: int | None) -> str:
    if year is None:
        return "undated"
    if 1803 <= int(year) <= 1841:
        return "backsearch_1803_1841"
    if int(year) <= 1875:
        return "anchor_1842_1875"
    if int(year) <= 1969:
        return "expansion_1876_1969"
    return "modern_1970_present"


def write_report(path: Path, statuses: list[dict[str, Any]], started: str, finished: str, start_count: int, end_count: int, target: int) -> None:
    inserted = [row for row in statuses if row.get("status") == "inserted"]
    skipped = [row for row in statuses if row.get("status") != "inserted"]
    lines = [
        "# Internet Archive Public Metadata Collection Report",
        "",
        "## Execution Context",
        f"- Run: `{ROUND_NAME}`",
        f"- Started: `{started}`",
        f"- Finished: `{finished}`",
        f"- Starting record count: {start_count}",
        f"- Ending record count: {end_count}",
        f"- Target new card-ready metadata records: {target}",
        f"- Inserted new card-ready metadata records: {len(inserted)}",
        "",
        "## Guardrails",
        "- Internet Archive records are public metadata, not collected full text.",
        "- Region fields are figure-associated review signals, not verified event places.",
        "",
        "## New Records By State/Territory Signal",
    ]
    for state, count in Counter(row.get("state_code") or "UNKNOWN" for row in inserted).most_common():
        lines.append(f"- {state}: {count}")
    lines.extend(["", "## New Records By Figure"])
    for figure, count in Counter(row.get("figure") for row in inserted).most_common():
        lines.append(f"- {figure}: {count}")
    lines.extend(["", "## New Records By Date Band"])
    for band, count in Counter(date_band(row.get("year")) for row in inserted).most_common():
        lines.append(f"- {band}: {count}")
    lines.extend(["", "## Skipped"])
    for reason, count in Counter(row.get("skip_reason") for row in skipped if row.get("skip_reason")).most_common(25):
        lines.append(f"- {reason}: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect(args: argparse.Namespace) -> int:
    started = utc_now_iso()
    initialise_database(args.db)
    conn = connect(args.db)
    source_id = ensure_source(conn)
    start_count = conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
    external_ids, urls, title_year = existing_keys(conn)
    statuses: list[dict[str, Any]] = []
    inserted_count = 0
    for spec in sorted(TERM_SPECS, key=lambda item: -item.priority):
        if inserted_count >= args.target:
            break
        for doc in fetch_docs(spec, args.rows, args.max_pages, args.delay):
            candidate = candidate_from_doc(spec, doc)
            if candidate is None:
                continue
            if candidate["status"] == "skipped":
                statuses.append(candidate)
                continue
            key = (normalise_alias(candidate["title"]), int(candidate["year"]))
            url_key = normalise_alias(candidate["url"])
            if candidate["external_id"] in external_ids or url_key in urls or key in title_year:
                candidate["status"] = "skipped"
                candidate["skip_reason"] = "duplicate_existing_record"
                statuses.append(candidate)
                continue
            if args.dry_run:
                candidate["status"] = "dry_run_card_ready"
                statuses.append(candidate)
            else:
                record_id = insert_record(conn, candidate, source_id)
                candidate["status"] = "inserted"
                candidate["record_id"] = record_id
                statuses.append(candidate)
                external_ids.add(candidate["external_id"])
                urls.add(url_key)
                title_year.add(key)
                inserted_count += 1
            if inserted_count >= args.target:
                break
    if not args.dry_run:
        conn.commit()
    end_count = conn.execute("SELECT COUNT(*) AS count FROM records").fetchone()["count"]
    finished = utc_now_iso()
    write_status(statuses, args.candidates_output)
    write_report(args.report, statuses, started, finished, start_count, end_count, args.target)
    LOGGER.info("Inserted %s records", inserted_count)
    return 0 if inserted_count >= args.target or args.dry_run else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--rows", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--candidates-output", type=Path, default=DEFAULT_STATUS_CSV)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    if not args.db.exists():
        LOGGER.error("Database not found: %s. Run `make init seed queries` first.", args.db)
        return 1
    try:
        return collect(args)
    except requests.RequestException as exc:
        LOGGER.error("Internet Archive request failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
