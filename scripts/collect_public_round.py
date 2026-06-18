#!/usr/bin/env python3
"""Run one conservative public-source collection round.

This script intentionally collects a small number of public pages and public
metadata leads. It does not scrape restricted material, bypass access controls,
or require Trove API credentials.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.classify import classify_record
from aus_humanoid.db import DEFAULT_DB_PATH, connect, initialise_database
from aus_humanoid.geo import assign_locations_for_record, seed_locations
from aus_humanoid.normalise import parse_year, slugify
from aus_humanoid.sources import seed_sources
from aus_humanoid.utils import PROJECT_ROOT, json_dumps, read_yaml, utc_now_iso, write_csv


USER_AGENT = "AustralianHumanoidPublicTexts/0.1 research contact: local"
ROUND_NAME = "public_round_001"
RECORDS_CSV = PROJECT_ROOT / "data" / "interim" / "public_round_001_records.csv"
LEADS_CSV = PROJECT_ROOT / "data" / "interim" / "public_round_001_source_leads.csv"
REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "public_round_001_report.md"
RAW_TEXT_DIR = PROJECT_ROOT / "data" / "raw" / "text"
RAW_HTML_DIR = PROJECT_ROOT / "data" / "raw" / "html"


WIKIPEDIA_PAGES = [
    {"title": "Yowie", "figure": "Yowie"},
    {"title": "Yara-ma-yha-who", "figure": "Yara-ma-yha-who"},
    {"title": "Quinkan", "figure": "Quinkan"},
    {"title": "Wandjina", "figure": "Wandjina"},
    {"title": "Nargun", "figure": "Nargun"},
    {"title": "Bunyip", "figure": "Bunyip"},
    {"title": "Drop bear", "figure": "Drop bear"},
]

PUBLIC_WEB_PAGES = [
    {
        "source_name": "ABC News",
        "source_type": "modern_web",
        "url": "https://www.abc.net.au/news/2018-04-21/kilcoy-yowie-tourism-queensland/9675596",
        "query_string": '"Yowie" AND Kilcoy',
        "figure": "Yowie",
        "location_hint": "Kilcoy, Queensland",
    }
]

# These are stable, public bibliographic/source leads discovered through public
# Wikipedia references. They are inserted as public metadata leads, not as full
# text records.
EARLY_SOURCE_LEADS = [
    {
        "source_name": "Manual Import",
        "source_type": "manual",
        "query_string": '"Yahoo"',
        "external_id": "bibliographic-lead:1842:yahoo",
        "title": "Superstitions of the Australian Aborigines: The Yahoo",
        "publication": "Australian and New Zealand Monthly Magazine",
        "author": "",
        "date_published": "February 1842",
        "url": "",
        "snippet": "Bibliographic lead cited by public secondary references; earliest located Yahoo-cluster lead in this round.",
        "raw_text": "Public metadata lead only. Citation metadata: title 'Superstitions of the Australian Aborigines: The Yahoo', Australian and New Zealand Monthly Magazine, vol. 1 issue 2, February 1842. Requires full-text verification before semantic coding.",
        "publicness_level": "public_metadata",
        "access_status": "metadata_lead_needs_fulltext_review",
        "ingestion_status": "lead_public_metadata",
        "figure": "Yahoo",
        "location_text": "Australia",
    },
    {
        "source_name": "Trove Newspapers and Gazettes",
        "source_type": "trove_newspaper",
        "query_string": '"Yahoo-devil-devil"',
        "external_id": "nla.news-article70605854",
        "title": "Milburn Creek",
        "publication": "Australian Town and Country Journal",
        "author": "",
        "date_published": "18 November 1876",
        "url": "http://nla.gov.au/nla.news-article70605854",
        "snippet": "Public lead for a Yahoo-devil-devil / hairy man of the wood passage; NLA page requires manual/API-key review in this environment.",
        "raw_text": "Public metadata lead only. Cited passage describes 'Yahoo-Devil Devil, or hairy man of the wood'. Full Trove text not retrieved in this round.",
        "publicness_level": "public_metadata",
        "access_status": "metadata_lead_needs_fulltext_review",
        "ingestion_status": "lead_public_metadata",
        "figure": "Yahoo",
        "location_text": "Milburn Creek Australia",
    },
    {
        "source_name": "Trove Newspapers and Gazettes",
        "source_type": "trove_newspaper",
        "query_string": '"Australian Apes"',
        "external_id": "nla.news-article70993856",
        "title": "The Naturalist: Australian Apes",
        "publication": "Australian Town and Country Journal",
        "author": "H. J. M'Cooey",
        "date_published": "9 December 1882",
        "url": "http://nla.gov.au/nla.news-article70993856",
        "snippet": "Public lead for an 'indigenous ape' report on the New South Wales south coast, between Batemans Bay and Ulladulla.",
        "raw_text": "Public metadata lead only. The public citation places the reported sighting on the New South Wales south coast, between Batemans Bay and Ulladulla. Full Trove text not retrieved in this round.",
        "publicness_level": "public_metadata",
        "access_status": "metadata_lead_needs_fulltext_review",
        "ingestion_status": "lead_public_metadata",
        "figure": "Yowie",
        "location_text": "New South Wales south coast between Batemans Bay and Ulladulla",
    },
    {
        "source_name": "Trove Newspapers and Gazettes",
        "source_type": "trove_newspaper",
        "query_string": '"Home-made Yowie"',
        "external_id": "nla.news-article110832132",
        "title": "Home-made 'Yowie'",
        "publication": "The Canberra Times",
        "author": "",
        "date_published": "26 October 1976",
        "url": "http://nla.gov.au/nla.news-article110832132",
        "snippet": "Public lead for modern Yowie discourse in The Canberra Times.",
        "raw_text": "Public metadata lead only. Full Trove text not retrieved in this round.",
        "publicness_level": "public_metadata",
        "access_status": "metadata_lead_needs_fulltext_review",
        "ingestion_status": "lead_public_metadata",
        "figure": "Yowie",
        "location_text": "Australian Capital Territory Australia",
    },
    {
        "source_name": "Trove Magazines and Newsletters",
        "source_type": "trove_magazine",
        "query_string": '"Yowie" AND "Cape York"',
        "external_id": "nla.news-article54670677",
        "title": "It's huge, hairy and from Cape York to Tasmania the monster Yowie prowls",
        "publication": "The Australian Women's Weekly",
        "author": "Jill Bowen",
        "date_published": "15 December 1976",
        "url": "http://nla.gov.au/nla.news-article54670677",
        "snippet": "Public lead for nationalised modern Yowie discourse from Cape York to Tasmania.",
        "raw_text": "Public metadata lead only. Full Trove text not retrieved in this round.",
        "publicness_level": "public_metadata",
        "access_status": "metadata_lead_needs_fulltext_review",
        "ingestion_status": "lead_public_metadata",
        "figure": "Yowie",
        "location_text": "Cape York Tasmania Australia",
    },
]


def curl_fetch(url: str, output_path: Path) -> tuple[bool, str]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "curl",
        "-L",
        "--retry",
        "1",
        "--max-time",
        "15",
        "-A",
        USER_AGENT,
        "-s",
        url,
        "-o",
        str(output_path),
    ]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        if output_path.exists() and output_path.stat().st_size > 0:
            return True, "using cached response after fetch failure"
        return False, result.stderr.strip() or f"curl exit {result.returncode}"
    if output_path.exists() and output_path.stat().st_size > 0:
        return True, ""
    return False, "empty response"


def ensure_source(conn, source_name: str, source_type: str, base_url: str = "") -> int:
    row = conn.execute(
        "SELECT source_id FROM sources WHERE source_name = ?",
        (source_name,),
    ).fetchone()
    if row:
        return int(row["source_id"])
    cursor = conn.execute(
        """
        INSERT INTO sources (
            source_name, source_type, base_url, access_method,
            publicness_level, ethics_notes
        ) VALUES (?, ?, ?, 'public_web_round', 'public_page',
                  'Small public collection round; verify source voice and publicness before analysis.')
        """,
        (source_name, source_type, base_url),
    )
    return int(cursor.lastrowid)


def figure_id(conn, canonical_name: str | None) -> int | None:
    if not canonical_name:
        return None
    row = conn.execute(
        "SELECT figure_id FROM figures WHERE canonical_name = ?",
        (canonical_name,),
    ).fetchone()
    return int(row["figure_id"]) if row else None


def query_id(conn, source_id: int, query_string: str) -> int | None:
    row = conn.execute(
        """
        SELECT query_id FROM queries
        WHERE source_id = ? AND query_string = ?
        ORDER BY query_id
        LIMIT 1
        """,
        (source_id, query_string),
    ).fetchone()
    return int(row["query_id"]) if row else None


def save_raw_text(record_id: int, title: str, raw_text: str) -> str:
    RAW_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_TEXT_DIR / f"record_{record_id}_{slugify(title)}.txt"
    path.write_text(raw_text or "", encoding="utf-8")
    return str(path.relative_to(PROJECT_ROOT))


def upsert_record(conn, record: dict) -> int:
    source_id = ensure_source(
        conn,
        record["source_name"],
        record.get("source_type", "modern_web"),
        record.get("base_url", ""),
    )
    existing = None
    if record.get("external_id"):
        existing = conn.execute(
            "SELECT record_id FROM records WHERE source_id = ? AND external_id = ?",
            (source_id, record["external_id"]),
        ).fetchone()
    if existing is None and record.get("url"):
        existing = conn.execute(
            "SELECT record_id FROM records WHERE source_id = ? AND url = ?",
            (source_id, record["url"]),
        ).fetchone()

    now = utc_now_iso()
    year = parse_year(record.get("date_published"))
    values = (
        source_id,
        query_id(conn, source_id, record.get("query_string", "")),
        figure_id(conn, record.get("figure")),
        record.get("external_id"),
        record.get("title"),
        record.get("publication"),
        record.get("author"),
        record.get("date_published"),
        year,
        record.get("url"),
        record.get("snippet"),
        json_dumps({key: value for key, value in record.items() if key != "raw_text"}),
        record.get("access_status", "public_web_imported"),
        record.get("publicness_level", "public_page"),
        record.get("ingestion_status", "raw_public_web"),
        now,
    )

    if existing:
        record_id = int(existing["record_id"])
        conn.execute(
            """
            UPDATE records
            SET source_id = ?, query_id = ?, figure_id = ?, external_id = ?,
                title = ?, publication = ?, author = ?, date_published = ?,
                year = ?, url = ?, snippet = ?, raw_metadata_json = ?,
                access_status = ?, publicness_level = ?, ingestion_status = ?,
                updated_at = ?
            WHERE record_id = ?
            """,
            values + (record_id,),
        )
    else:
        cursor = conn.execute(
            """
            INSERT INTO records (
                source_id, query_id, figure_id, external_id, title, publication,
                author, date_published, year, url, snippet, raw_metadata_json,
                access_status, publicness_level, ingestion_status, created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            values + (now,),
        )
        record_id = int(cursor.lastrowid)

    raw_text = record.get("raw_text", "")
    full_text_path = save_raw_text(record_id, record.get("title") or "untitled", raw_text)
    conn.execute(
        "UPDATE records SET full_text_path = ? WHERE record_id = ?",
        (full_text_path, record_id),
    )
    classify_record(conn, record_id)
    location_text = "\n".join(
        part
        for part in [
            record.get("title", ""),
            record.get("publication", ""),
            record.get("snippet", ""),
            record.get("location_text", ""),
            raw_text,
        ]
        if part
    )
    assign_locations_for_record(conn, record_id, location_text)
    return record_id


def fetch_wikipedia_summary(page: dict) -> tuple[dict | None, dict | None]:
    title = page["title"]
    safe_title = quote(title.replace(" ", "_"), safe="_-()")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{safe_title}"
    path = RAW_HTML_DIR / f"wikipedia_summary_{slugify(title)}.json"
    ok, error = curl_fetch(url, path)
    if not ok:
        return None, {
            "lead_type": "fetch_error",
            "source": "English Wikipedia",
            "title": title,
            "url": url,
            "notes": error,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, {
            "lead_type": "parse_error",
            "source": "English Wikipedia",
            "title": title,
            "url": url,
            "notes": str(exc),
        }
    if data.get("type") == "https://mediawiki.org/wiki/HyperSwitch/errors/not_found":
        return None, {
            "lead_type": "not_found",
            "source": "English Wikipedia",
            "title": title,
            "url": url,
            "notes": "Wikipedia summary endpoint returned not found.",
        }
    page_url = data.get("content_urls", {}).get("desktop", {}).get("page", url)
    extract = data.get("extract") or ""
    record = {
        "source_name": "English Wikipedia",
        "source_type": "modern_web",
        "base_url": "https://en.wikipedia.org/",
        "query_string": f'"{title}"',
        "external_id": f"wikipedia:{data.get('pageid')}:{data.get('revision')}",
        "title": data.get("title") or title,
        "publication": "English Wikipedia",
        "author": "",
        "date_published": data.get("timestamp"),
        "url": page_url,
        "snippet": extract,
        "raw_text": "\n".join(
            part
            for part in [
                data.get("title") or title,
                data.get("description") or "",
                extract,
                f"Revision: {data.get('revision')}",
                f"Retrieved via Wikimedia summary API: {url}",
            ]
            if part
        ),
        "publicness_level": "public_page",
        "access_status": "public_summary_api",
        "ingestion_status": "raw_public_web_summary",
        "figure": page.get("figure"),
    }
    return record, None


def fetch_wikipedia_yowie_leads() -> list[dict]:
    url = "https://en.wikipedia.org/w/api.php?action=parse&page=Yowie&prop=externallinks&format=json&formatversion=2"
    path = RAW_HTML_DIR / "wikipedia_yowie_external_links.json"
    ok, error = curl_fetch(url, path)
    used_cache = False
    if not ok and path.exists() and path.stat().st_size > 0:
        used_cache = True
    elif not ok:
        return [
            {
                "lead_type": "fetch_error",
                "source": "English Wikipedia",
                "title": "Yowie external links",
                "url": url,
                "notes": error,
            }
        ]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            {
                "lead_type": "parse_error",
                "source": "English Wikipedia",
                "title": "Yowie external links",
                "url": url,
                "notes": str(exc),
            }
        ]
    leads = []
    for external_url in data.get("parse", {}).get("externallinks", []):
        if any(host in external_url for host in ["nla.gov.au", "abc.net.au", "nma.gov.au", "archive.org", "news.google.com"]):
            leads.append(
                {
                    "lead_type": "external_reference",
                    "source": "English Wikipedia Yowie references",
                    "title": "",
                    "url": external_url,
                    "notes": (
                        "Public external reference link discovered from the Yowie page; "
                        "requires source-level review before corpus use."
                        + (" Parsed from cached API response after current fetch failed." if used_cache else "")
                    ),
                }
            )
    return leads


def parse_json_ld(html: str) -> dict:
    match = re.search(
        r'<script type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return {}
    text = re.sub(r"<[^>]+>", "", match.group(1)).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    graph = data.get("@graph") if isinstance(data, dict) else None
    if isinstance(graph, list):
        for item in graph:
            if item.get("@type") in {"NewsArticle", "Article"}:
                return item
    return data if isinstance(data, dict) else {}


def fetch_public_web_page(page: dict) -> tuple[dict | None, dict | None]:
    url = page["url"]
    path = RAW_HTML_DIR / f"public_web_{slugify(page['source_name'] + '-' + page['figure'])}.html"
    ok, error = curl_fetch(url, path)
    if not ok:
        return None, {
            "lead_type": "fetch_error",
            "source": page["source_name"],
            "title": page.get("figure", ""),
            "url": url,
            "notes": error,
        }
    html = path.read_text(encoding="utf-8", errors="replace")
    article = parse_json_ld(html)
    title = article.get("headline") or page.get("title") or page["url"]
    description = article.get("description") or ""
    date_published = article.get("datePublished") or ""
    record = {
        "source_name": page["source_name"],
        "source_type": page.get("source_type", "modern_web"),
        "base_url": "https://www.abc.net.au/",
        "query_string": page.get("query_string", ""),
        "external_id": f"abc:{re.search(r'/([0-9]+)(?:[/?#]|$)', url).group(1) if re.search(r'/([0-9]+)(?:[/?#]|$)', url) else slugify(url)}",
        "title": title,
        "publication": page["source_name"],
        "author": "",
        "date_published": date_published,
        "url": url,
        "snippet": description,
        "raw_text": "\n".join(
            part
            for part in [
                title,
                description,
                f"Main entity page: {article.get('mainEntityOfPage', url)}",
                f"Location hint: {page.get('location_hint', '')}",
            ]
            if part
        ),
        "publicness_level": "public_page",
        "access_status": "public_web_downloaded",
        "ingestion_status": "raw_public_web",
        "figure": page.get("figure"),
        "location_text": page.get("location_hint", ""),
    }
    return record, None


def write_round_csv(records: list[dict], leads: list[dict]) -> None:
    record_fields = [
        "source_name",
        "source_type",
        "query_string",
        "external_id",
        "title",
        "publication",
        "author",
        "date_published",
        "year",
        "url",
        "snippet",
        "publicness_level",
        "access_status",
        "ingestion_status",
        "figure",
        "location_text",
    ]
    rows = []
    for record in records:
        row = dict(record)
        row["year"] = parse_year(record.get("date_published"))
        rows.append(row)
    write_csv(RECORDS_CSV, rows, record_fields)
    write_csv(LEADS_CSV, leads, ["lead_type", "source", "title", "url", "notes"])


def write_report(conn, inserted_ids: list[int], records: list[dict], leads: list[dict], failures: list[dict]) -> None:
    rows = conn.execute(
        """
        SELECT r.record_id, r.year, r.title, s.source_name, r.publicness_level,
               c.canonical_figure_guess, c.relevance_code, c.ethics_flag
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN coding c ON c.record_id = r.record_id
        WHERE r.record_id IN (%s)
        ORDER BY r.year, r.record_id
        """
        % ",".join("?" for _ in inserted_ids),
        inserted_ids,
    ).fetchall() if inserted_ids else []
    earliest = min((row["year"] for row in rows if row["year"]), default=None)
    location_rows = conn.execute(
        """
        SELECT COUNT(*) AS n FROM record_locations
        WHERE record_id IN (%s)
        """
        % ",".join("?" for _ in inserted_ids),
        inserted_ids,
    ).fetchone()["n"] if inserted_ids else 0

    lines = [
        "# Public Collection Round 001",
        "",
        f"Run name: `{ROUND_NAME}`",
        f"Records inserted or updated: {len(inserted_ids)}",
        f"Source leads written: {len(leads)}",
        f"Fetch failures logged: {len(failures)}",
        f"Earliest year in imported/lead records: {earliest or 'n/a'}",
        f"Record-location links written: {location_rows}",
        "",
        "## Method",
        "",
        "- Small, public-only collection round.",
        "- Wikimedia summaries were retrieved through public API endpoints.",
        "- ABC News Kilcoy page was downloaded as a public web page.",
        "- Trove/NLA early items were inserted as public metadata leads only because Trove API requires a key and full article pages were not reliably retrievable from this environment.",
        "- No restricted, secret/sacred, unpublished, or non-public materials were targeted.",
        "",
        "## Imported Records",
        "",
    ]
    if rows:
        for row in rows:
            lines.append(
                f"- {row['year'] or ''} | {row['source_name']} | "
                f"{row['title']} | figure={row['canonical_figure_guess'] or ''} | "
                f"ethics={row['ethics_flag'] or ''}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Fetch Failures", ""])
    lines.extend(
        [f"- {item.get('source')}: {item.get('title')} ({item.get('url')}) - {item.get('notes')}" for item in failures]
        or ["- None"]
    )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- `{RECORDS_CSV.relative_to(PROJECT_ROOT)}`",
            f"- `{LEADS_CSV.relative_to(PROJECT_ROOT)}`",
            "- `data/exports/records_review.csv` after running `make locations export`",
            "- `data/exports/record_locations.csv` after running `make locations export`",
        ]
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    args = parser.parse_args()

    initialise_database(args.db)
    records: list[dict] = []
    leads: list[dict] = []
    failures: list[dict] = []

    for page in WIKIPEDIA_PAGES:
        record, failure = fetch_wikipedia_summary(page)
        if record:
            records.append(record)
        if failure:
            failures.append(failure)

    for page in PUBLIC_WEB_PAGES:
        record, failure = fetch_public_web_page(page)
        if record:
            records.append(record)
        if failure:
            failures.append(failure)

    records.extend(EARLY_SOURCE_LEADS)
    leads.extend(fetch_wikipedia_yowie_leads())
    leads.extend(failures)
    write_round_csv(records, leads)

    with connect(args.db) as conn:
        seed_sources(conn)
        seed_locations(conn)
        started = utc_now_iso()
        cursor = conn.execute(
            """
            INSERT INTO collection_runs (
                run_name, run_started_at, scope_notes, methods, limitations
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                ROUND_NAME,
                started,
                "Small public-only seed collection for earlier/more source discovery and location evidence.",
                "Wikimedia summary API, one ABC public page, public metadata leads from NLA/Trove references.",
                "Trove API requires a key; early Trove leads were not treated as full-text records.",
            ),
        )
        run_id = int(cursor.lastrowid)
        inserted_ids = [upsert_record(conn, record) for record in records]
        conn.execute(
            "UPDATE collection_runs SET run_finished_at = ? WHERE collection_run_id = ?",
            (utc_now_iso(), run_id),
        )
        conn.commit()
        write_report(conn, inserted_ids, records, leads, failures)

    print(f"Imported or updated {len(records)} public records/leads")
    print(f"Wrote source leads: {LEADS_CSV}")
    print(f"Wrote report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
