#!/usr/bin/env python3
"""Collect card-ready public metadata records from OpenAlex.

This collector is intentionally metadata-only. It uses the public OpenAlex API
to discover published works that explicitly mention project lexicon terms in
their title or abstract. It does not fetch restricted full text, and it records
figure-associated regions as reviewable location signals rather than verified
event places.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.classify import classify_record
from aus_humanoid.db import DEFAULT_DB_PATH, connect, initialise_database
from aus_humanoid.normalise import normalise_alias, slugify
from aus_humanoid.utils import PROJECT_ROOT, json_dumps, utc_now_iso


LOGGER = logging.getLogger("collect_openalex_metadata")

BASE_URL = "https://api.openalex.org/works"
SOURCE_NAME = "OpenAlex"
SOURCE_TYPE = "academic_metadata"
ROUND_NAME = "openalex_public_metadata_round_003"
USER_AGENT = "AustralianHumanoidPublicTexts/0.3 research contact: local"
RAW_TEXT_DIR = PROJECT_ROOT / "data" / "raw" / "text"
DEFAULT_STATUS_CSV = PROJECT_ROOT / "data" / "interim" / "openalex_round_003_candidates.csv"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "openalex_round_003_report.md"


@dataclass(frozen=True)
class TermSpec:
    figure: str
    term: str
    query: str
    state: str
    region: str
    confidence: str
    priority: int


TERM_SPECS = [
    TermSpec("Yowie", "Yowie", "Yowie Australia", "AU", "Australia", "low", 3),
    TermSpec("Hairy Man", "hairy man", '"hairy man" Australia Aboriginal', "AU", "Australia", "low", 2),
    TermSpec("Yaroma", "Yaroma", "Yaroma Australia Aboriginal", "AU", "Australia", "low", 2),
    TermSpec("Yara-ma-yha-who", "Yara-ma-yha-who", '"Yara-ma-yha-who"', "AU", "Australia", "low", 4),
    TermSpec("Mimih", "Mimih", "Mimih Australia Aboriginal spirit", "NT", "Northern Territory", "medium", 5),
    TermSpec("Quinkan", "Quinkan", "Quinkan Australia", "QLD", "Queensland", "medium", 5),
    TermSpec("Wandjina", "Wandjina", "Wandjina Australia", "WA", "Western Australia", "medium", 5),
    TermSpec("Nargun", "Nargun", "Nargun Australia", "VIC", "Victoria", "medium", 5),
    TermSpec("Garkain", "Garkain", "Garkain Arnhem Land", "NT", "Northern Territory", "medium", 4),
    TermSpec("Mokoi", "Mokoi", "Mokoi Australia Aboriginal spirit", "NT", "Northern Territory", "medium", 4),
    TermSpec("Mamu", "Mamu", "Mamu Australia Aboriginal spirit", "AU", "Australia", "low", 3),
    TermSpec("Pangkarlangu", "Pangkarlangu", "Pangkarlangu Australia", "NT", "Northern Territory", "medium", 4),
    TermSpec("Puttikan", "Puttikan", "Puttikan Australia", "VIC", "Victoria", "medium", 3),
    TermSpec("Doolaga", "Doolaga", "Doolaga Australia Yowie", "AU", "Australia", "low", 1),
    TermSpec("Dooligah", "Dooligah", "Dooligah Australia Yowie", "AU", "Australia", "low", 1),
    TermSpec("Thoolagal", "Thoolagal", "Thoolagal Australia Yowie", "AU", "Australia", "low", 1),
    TermSpec("Tjangara", "Tjangara", "Tjangara Australia giant", "AU", "Australia", "low", 1),
]

NOISE_PATTERNS = [
    "Yahoo",
    "Yahoos",
    "Yahoo!",
    "Yowie Bay",
    "Cadbury",
    "chocolate",
    "toy",
    "Information Extraction",
    "Service Enabled World",
    "heavy metal contaminations",
    "sediments",
    "macaque",
    "Mamu-B",
    "SIV",
    "HIV",
    "Twitter",
    "Yahoo Answers",
    "Yahoo! Answers",
    "Yahoo Mail",
    "Yahoo News",
    "finance.yahoo",
    "sports.yahoo",
    "Boheme",
    "GeoGebra",
    "qudit",
    "multipartite",
    "Irrigation",
    "Rice Cultivation",
    "South America",
    "Ruínas",
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
    "western desert",
    "northern territory",
    "western australia",
    "south australia",
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


def clean_space(value: str | None) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def reconstruct_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions:
            words.append((int(position), word))
    return clean_space(" ".join(word for _position, word in sorted(words)))


def fetch_json(url: str, timeout: int = 35) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(0.8 + attempt * 0.7)

    result = subprocess.run(
        [
            "curl",
            "-L",
            "--retry",
            "2",
            "--retry-delay",
            "2",
            "--fail",
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
    if result.returncode != 0:
        if last_error:
            raise last_error
        raise RuntimeError(result.stderr.strip() or f"curl exit {result.returncode}")
    return json.loads(result.stdout)


def work_url(work: dict[str, Any]) -> str:
    primary = work.get("primary_location") or {}
    landing = primary.get("landing_page_url") or primary.get("pdf_url")
    return landing or work.get("doi") or work.get("id") or ""


def publication_name(work: dict[str, Any]) -> str:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    return clean_space(source.get("display_name")) or "OpenAlex"


def authors(work: dict[str, Any], limit: int = 4) -> str:
    names = []
    for item in work.get("authorships") or []:
        author = item.get("author") or {}
        if author.get("display_name"):
            names.append(author["display_name"])
    if len(names) > limit:
        return ", ".join(names[:limit]) + " et al."
    return ", ".join(names)


def title_matches(spec: TermSpec, text: str) -> bool:
    norm_text = normalise_alias(text)
    norm_term = normalise_alias(spec.term)
    if norm_term in norm_text:
        return True
    if spec.figure == "Yara-ma-yha-who" and "yara ma yha who" in norm_text:
        return True
    return False


def has_noise(text: str) -> str | None:
    lowered = text.lower()
    for pattern in NOISE_PATTERNS:
        if pattern.lower() in lowered:
            return pattern
    return None


def has_australia_context(spec: TermSpec, text: str) -> bool:
    lowered = text.lower()
    if spec.state != "AU" and any(term in lowered for term in STATE_CONTEXT.get(spec.state, [])):
        return True
    return any(term in lowered for term in AUSTRALIA_CONTEXT)


def infer_state(spec: TermSpec, text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    for state, patterns in STATE_CONTEXT.items():
        if any(pattern in lowered for pattern in patterns):
            names = {
                "WA": "Western Australia",
                "QLD": "Queensland",
                "NT": "Northern Territory",
                "VIC": "Victoria",
                "TAS": "Tasmania",
                "ACT": "Australian Capital Territory",
                "SA": "South Australia",
            }
            return state, names[state], "medium"
    if spec.state == "AU":
        return "", "Australia", "low"
    return spec.state, spec.region, spec.confidence


def candidate_from_work(spec: TermSpec, work: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_space(work.get("display_name"))
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    year = work.get("publication_year")
    if not title or not isinstance(year, int) or year < 1803 or year > 2026:
        return None
    text = "\n".join([title, abstract])
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
            "url": work_url(work),
        }
    if not has_australia_context(spec, text):
        return {
            "status": "skipped",
            "skip_reason": "missing_australia_context",
            "figure": spec.figure,
            "year": year,
            "title": title,
            "url": work_url(work),
        }
    state_code, region, confidence = infer_state(spec, text)
    url = work_url(work)
    if not url:
        return {
            "status": "skipped",
            "skip_reason": "missing_public_url",
            "figure": spec.figure,
            "year": year,
            "title": title,
            "url": "",
        }
    snippet_parts = [
        f"Public OpenAlex metadata record for a published work matching '{spec.term}'.",
        f"Work type: {work.get('type') or 'unknown'}.",
        f"Publication/source: {publication_name(work)}.",
        f"Location signal is figure-associated region ({region}), not a verified event place.",
    ]
    if abstract:
        snippet_parts.append("Abstract excerpt: " + clean_space(abstract[:420]))
    return {
        "status": "card_ready",
        "skip_reason": "",
        "figure": spec.figure,
        "term": spec.term,
        "state_code": state_code,
        "region": region,
        "location_confidence": confidence,
        "year": year,
        "date_published": work.get("publication_date") or str(year),
        "title": title,
        "url": url,
        "external_id": "openalex:" + str(work.get("id", "")).rsplit("/", 1)[-1],
        "publication": publication_name(work),
        "author": authors(work),
        "snippet": " ".join(snippet_parts),
        "raw_metadata": work,
        "abstract": abstract,
        "openalex_id": work.get("id"),
        "doi": work.get("doi"),
        "work_type": work.get("type"),
        "priority": spec.priority,
    }


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
                "https://openalex.org/",
                "public_metadata_api",
                "public_metadata",
                (
                    "OpenAlex public metadata only. Records are discovery/display "
                    "signals for published works; no restricted full text is collected."
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
            "https://openalex.org/",
            "public_metadata_api",
            "public_metadata",
            (
                "OpenAlex public metadata only. Records are discovery/display "
                "signals for published works; no restricted full text is collected."
            ),
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
            "openalex_term_region_hint",
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
        "publication": row["publication"],
        "author": row["author"],
        "region_signal": row["region"],
        "location_confidence": row["location_confidence"],
        "abstract": row["abstract"],
        "note": "OpenAlex public metadata only; full text was not collected.",
    }
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path.relative_to(PROJECT_ROOT))


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
                    "openalex_id": row["openalex_id"],
                    "doi": row["doi"],
                    "work_type": row["work_type"],
                    "matched_term": row["term"],
                    "figure": row["figure"],
                    "state_code": row["state_code"],
                    "region": row["region"],
                    "location_confidence": row["location_confidence"],
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
    ethics_flag = "caution_indigenous_knowledge" if row["figure"] not in {"Yowie", "Yahoo", "Hairy Man", "Yaroma"} else "ok_public"
    conn.execute(
        """
        INSERT INTO coding (
            record_id, canonical_figure_guess, figure_name_as_printed,
            variant_normalisation, ontology_code, humanoid_degree_code,
            source_voice, genre, publicness_code, relevance_code, ethics_flag,
            notes, coded_by, coded_at
        ) VALUES (?, ?, ?, ?, 'unclear', 'unclear', 'scholar',
                  'academic_text', 'public_metadata', 'needs_review', ?, ?,
                  'system_openalex_collector', ?)
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
            "OpenAlex public metadata record; region is a reviewable figure-associated signal, not a verified event place.",
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
            f"Matched term '{row['term']}' in OpenAlex title/abstract metadata.",
            row["location_confidence"],
            "OpenAlex metadata region hint for display/review; not a geocoded sighting place.",
        ),
    )
    return record_id


def existing_external_ids(conn) -> set[str]:
    return {
        row["external_id"]
        for row in conn.execute("SELECT external_id FROM records WHERE external_id LIKE 'openalex:%'")
        if row["external_id"]
    }


def write_status(rows: list[dict[str, Any]], path: Path) -> None:
    fields = ["status", "skip_reason", "record_id", "figure", "term", "state_code", "year", "title", "url"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        import csv

        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_report(path: Path, statuses: list[dict[str, Any]], started: str, finished: str, start_count: int, end_count: int, target: int) -> None:
    inserted = [row for row in statuses if row.get("status") == "inserted"]
    skipped = [row for row in statuses if row.get("status") != "inserted"]
    by_state = Counter(row.get("state_code") or "UNKNOWN" for row in inserted)
    by_figure = Counter(row.get("figure") for row in inserted)
    by_year_band = Counter(date_band(row.get("year")) for row in inserted)
    by_skip = Counter(row.get("skip_reason") for row in skipped if row.get("skip_reason"))
    lines = [
        "# OpenAlex Public Metadata Collection Report",
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
        "- OpenAlex records are public metadata, not collected full text.",
        "- Region fields are figure-associated review signals, not verified event places.",
        "- Obvious high-noise matches such as Cadbury Yowie, Yowie Bay, biomedical Mamu-B, and unrelated Yahoo items are skipped.",
        "",
        "## New Records By State/Territory Signal",
    ]
    for state, count in by_state.most_common():
        lines.append(f"- {state}: {count}")
    lines.extend(["", "## New Records By Figure"])
    for figure, count in by_figure.most_common():
        lines.append(f"- {figure}: {count}")
    lines.extend(["", "## New Records By Date Band"])
    for band, count in by_year_band.most_common():
        lines.append(f"- {band}: {count}")
    lines.extend(["", "## Skipped"])
    for reason, count in by_skip.most_common(20):
        lines.append(f"- {reason}: {count}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def collect(args: argparse.Namespace) -> int:
    started = utc_now_iso()
    initialise_database(args.db)
    statuses: list[dict[str, Any]] = []
    inserted = 0
    seen_candidate_ids: set[str] = set()
    with connect(args.db) as conn:
        source_id = ensure_source(conn)
        start_count = int(conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"])
        existing = existing_external_ids(conn)
        specs = sorted(TERM_SPECS, key=lambda item: item.priority, reverse=True)
        for spec in specs:
            if inserted >= args.target:
                break
            for page in range(1, args.max_pages + 1):
                if inserted >= args.target:
                    break
                params = {
                    "search": spec.query,
                    "filter": "from_publication_date:1803-01-01",
                    "per-page": args.per_page,
                    "page": page,
                    "mailto": args.mailto,
                }
                url = BASE_URL + "?" + urlencode(params)
                LOGGER.info("Fetching %s page %d", spec.figure, page)
                try:
                    data = fetch_json(url)
                except Exception as exc:
                    statuses.append(
                        {
                            "status": "skipped",
                            "skip_reason": f"fetch_error:{exc.__class__.__name__}",
                            "figure": spec.figure,
                            "term": spec.term,
                        }
                    )
                    LOGGER.warning("Fetch failed for %s page %d: %s", spec.figure, page, exc)
                    break
                results = data.get("results") or []
                if not results:
                    break
                for work in results:
                    if inserted >= args.target:
                        break
                    candidate = candidate_from_work(spec, work)
                    if not candidate:
                        continue
                    candidate["term"] = spec.term
                    external_id = candidate.get("external_id")
                    if external_id in seen_candidate_ids or external_id in existing:
                        statuses.append(
                            {
                                **candidate,
                                "status": "skipped",
                                "skip_reason": "duplicate_existing_record",
                            }
                        )
                        continue
                    seen_candidate_ids.add(external_id)
                    if candidate.get("status") != "card_ready":
                        statuses.append(candidate)
                        continue
                    if args.dry_run:
                        candidate["status"] = "dry_run_card_ready"
                        candidate["record_id"] = ""
                    else:
                        candidate["record_id"] = insert_record(conn, candidate, source_id)
                        candidate["status"] = "inserted"
                    inserted += 1
                    statuses.append(candidate)
                    if inserted % 25 == 0:
                        conn.commit()
                        LOGGER.info("Accepted %d/%d", inserted, args.target)
                time.sleep(args.delay)
        conn.commit()
        end_count = int(conn.execute("SELECT COUNT(*) AS n FROM records").fetchone()["n"])
    finished = utc_now_iso()
    write_status(statuses, Path(args.candidates_output))
    write_report(Path(args.report), statuses, started, finished, start_count, end_count, args.target)
    LOGGER.info("Inserted %d records", inserted)
    return 0 if inserted >= args.target or args.dry_run else 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--target", type=int, default=500)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--mailto", default="research@example.com")
    parser.add_argument("--candidates-output", default=str(DEFAULT_STATUS_CSV))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
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
