#!/usr/bin/env python3
"""Discover and crawl public yowiehunters.com.au pages via Common Crawl URL index.

Common Crawl is used only for URL discovery. Candidate evidence comes from the
current public page HTML after robots.txt checks. This script writes stage-only
candidates; it does not import production records.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import time
import urllib.robotparser
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from crawl_public_books_metadata import FIELDNAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
OUT_DIR = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "ayr_public_site"
DEFAULT_OUTPUT = OUT_DIR / "ayr_public_site_round024_candidates.csv"
DEFAULT_RAW = OUT_DIR / "ayr_public_site_round024_raw.ndjson"
DEFAULT_REQUESTS = OUT_DIR / "ayr_public_site_round024_requests.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_ayr_public_site_round024.md"
USER_AGENT = "AusFiguresGapCrawler/0.4 public AYR site research"
CC_INDEX = "https://index.commoncrawl.org/CC-MAIN-2026-25-index"
DOMAIN = "www.yowiehunters.com.au"

SUPERNATURAL_RE = re.compile(r"\b(yowies?|yahoo|hairy man|hairy men|hairy people|bigfoot|creature|encounter|sighting|report)\b", re.I)
NOISE_RE = re.compile(r"\b(about us|what is a yowie|search ayr|forum|contact|copyright|login|register)\b", re.I)
INDIGENOUS_RE = re.compile(r"\b(aboriginal|indigenous|first nations|dreaming|dreamtime|sacred|ceremony)\b", re.I)
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b")


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.meta_description = ""
        self._in_title = False
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag.lower() == "title":
            self._in_title = True
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip = True
        if tag.lower() == "meta" and attrs_dict.get("name", "").lower() == "description":
            self.meta_description = attrs_dict.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        text = clean(data)
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        elif not self._skip:
            self.body_parts.append(text)

    @property
    def title(self) -> str:
        return clean(" ".join(self.title_parts))

    @property
    def body(self) -> str:
        return clean(" ".join(self.body_parts))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = "https"
    netloc = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path or "/")
    return urlunparse((scheme, netloc, path.rstrip("/") or "/", "", "", ""))


def cc_query(limit: int, timeout: int) -> tuple[list[str], list[dict[str, Any]]]:
    params = {
        "url": "yowiehunters.com.au/*",
        "output": "json",
        "fl": "url,status,mime,timestamp",
        "limit": str(limit),
    }
    url = CC_INDEX + "?" + urlencode(params)
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    urls: list[str] = []
    request_rows: list[dict[str, Any]] = []
    text = ""
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", "ignore")
            break
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}:{clean(str(exc))[:160]}"
            time.sleep(attempt)
    if not text:
        result = subprocess.run(
            ["curl", "-L", "--silent", "--show-error", "--max-time", str(timeout), "-A", USER_AGENT, url],
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout + 5,
        )
        if result.returncode == 0:
            text = result.stdout
        else:
            last_error = result.stderr.strip() or f"curl_exit_{result.returncode}"
    if not text:
        request_rows.append({"stage": "commoncrawl_index", "url": url, "status": "fetch_error", "note": last_error})
        return urls, request_rows
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        request_rows.append({"stage": "commoncrawl_index", "url": row.get("url", ""), "status": row.get("status", ""), "note": row.get("mime", "")})
        if row.get("status") == "200" and "html" in clean(row.get("mime")).lower():
            urls.append(clean(row.get("url")))
    return urls, request_rows


def url_allowed_by_path(url: str) -> bool:
    path = urlparse(url).path.lower()
    if any(part in path for part in ("/administrator/", "/cache/", "/components/", "/images/", "/templates/", "/plugins/", "/modules/")):
        return False
    if path.endswith("/robots.txt"):
        return False
    return any(part in path for part in ("/media-clips/", "/historical-articles/", "/new-south-wales/", "/queensland/", "/victoria/", "/western-australia/", "/south-australia/", "/northern-territory/", "/tasmania/"))


def robots_parser(timeout: int) -> urllib.robotparser.RobotFileParser:
    parser = urllib.robotparser.RobotFileParser(f"https://{DOMAIN}/robots.txt")
    try:
        parser.read()
    except Exception:
        # Fail closed for disallowed technical paths; current allowed content
        # paths are also filtered by url_allowed_by_path.
        pass
    return parser


def fetch_html(url: str, timeout: int, max_bytes: int) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    with urlopen(request, timeout=timeout) as response:
        content_type = clean(response.headers.get("content-type")).lower()
        if "html" not in content_type:
            raise ValueError(f"non_html:{content_type}")
        return response.read(max_bytes).decode("utf-8", "ignore")


def place_catalog(frontend: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    catalog: dict[str, dict[str, Any]] = {}
    for record in data.get("records", []):
        lat = record.get("map_latitude")
        lon = record.get("map_longitude")
        place = clean(record.get("map_place_name") or record.get("location_summary"))
        if lat in (None, "") or lon in (None, "") or not place:
            continue
        short = place.split(",", 1)[0].split("(", 1)[0].strip()
        if len(short) < 4:
            continue
        key = norm(short)
        catalog.setdefault(
            key,
            {
                "name": short,
                "location_text": place,
                "latitude": lat,
                "longitude": lon,
                "precision": record.get("map_location_type") or record.get("location_precision_status") or "reviewed_place",
            },
        )
    return catalog


def match_place(text: str, catalog: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    lowered = text.lower()
    # Prefer longer names first to avoid town/common-word collisions.
    for key, value in sorted(catalog.items(), key=lambda item: len(item[0]), reverse=True):
        name = value["name"]
        if len(name) < 5:
            continue
        if re.search(r"\b" + re.escape(name) + r"\b", lowered, re.I):
            return value
    return None


def existing_keys(frontend: Path) -> tuple[set[str], set[str], set[tuple[str, str]]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    urls: set[str] = set()
    external_ids: set[str] = set()
    title_years: set[tuple[str, str]] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(canonical_url(url).lower())
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
        title = norm(record.get("title") or "")
        year = record.get("year")
        if title and year:
            title_years.add((title, str(year)))
    return urls, external_ids, title_years


def year_from_text(text: str) -> int | None:
    years = [int(match.group(1)) for match in YEAR_RE.finditer(text)]
    if not years:
        return None
    # AYR media pages often have source-year first and encounter-year later.
    # The annual trend is public-record oriented, so use the first listed year.
    for year in years:
        if 1926 <= year <= 2026:
            return year
    return years[0]


def date_scope(year: int | None) -> str:
    if year is None:
        return "undated"
    if 1926 <= year <= 2011:
        return "gap_window_1926_2011"
    if year >= 2012:
        return "post_gap_after_2011"
    return "pre_gap_before_1926"


def evidence_window(text: str) -> str:
    match = SUPERNATURAL_RE.search(text)
    if not match:
        return clean(text[:900])
    start = max(0, match.start() - 450)
    end = min(len(text), match.end() + 450)
    return clean(text[start:end])[:900]


def classify(url: str, html: str, catalog: dict[str, dict[str, Any]], duplicate_keys: tuple[set[str], set[str], set[tuple[str, str]]]) -> dict[str, Any]:
    parser = TextExtractor()
    parser.feed(html)
    title = clean(parser.title.replace("Australian Yowie Research -", "").strip(" -")) or "AYR public page"
    text = clean(" ".join([title, parser.meta_description, parser.body[:6000]]))
    year = year_from_text(" ".join([title, parser.meta_description, url]))
    canonical = canonical_url(url)
    external_id = "ayr-public-site:" + re.sub(r"[^a-z0-9]+", "-", urlparse(canonical).path.lower()).strip("-")[:80]
    place = match_place(text, catalog)
    urls, external_ids, title_years = duplicate_keys
    status = "accepted"
    rejection = ""
    if canonical.lower() in urls or external_id in external_ids or (norm(title), str(year or "")) in title_years:
        status = "duplicate_existing_record"
        rejection = "duplicate_against_current_overlay"
    elif NOISE_RE.search(title):
        status = "rejected"
        rejection = "site_navigation_or_about_page"
    elif not SUPERNATURAL_RE.search(text):
        status = "rejected"
        rejection = "missing_yowie_or_encounter_context"
    elif INDIGENOUS_RE.search(text):
        status = "lead_only"
        rejection = "indigenous_related_public_page_requires_manual_review"
    elif year is not None and year < 1926:
        status = "lead_only"
        rejection = "pre_gap_year"

    terms = sorted({clean(match.group(0)).lower() for match in SUPERNATURAL_RE.finditer(text)})
    mapped = bool(place and status == "accepted")
    return {
        "candidate_status": status,
        "source_name": "Australian Yowie Research public website",
        "source_type": "public_web_yowiehunters_site_page",
        "source_tier": "public_claim_report_index",
        "query_family_id": "ayr_public_site_commoncrawl_discovery",
        "query_string": "Common Crawl URL index discovery for yowiehunters.com.au public pages",
        "abc_hit_id": "",
        "title": title,
        "publication_or_organisation": "Australian Yowie Research",
        "publication_date_text": str(year) if year else "",
        "year": year or "",
        "date_scope": date_scope(year),
        "access_date": date.today().isoformat(),
        "url": canonical,
        "canonical_url": canonical,
        "external_id": external_id,
        "publicness_status": "public_web_page",
        "rights_access_status": "public_page_short_summary_only",
        "narrative_type": "cryptid_style_apeman",
        "secondary_role": "ayr_public_site_page_candidate",
        "australian_relation": "Public Australian Yowie Research website page discovered through Common Crawl URL index and fetched from current public URL.",
        "humanoid_basis": "public_yowie_report_or_article_metadata",
        "source_label": "yowie",
        "matched_terms": ";".join(terms),
        "matched_place": place["name"] if place else "",
        "location_text": place["location_text"] if place else "",
        "location_role": "reported_place" if place else "",
        "latitude": place["latitude"] if mapped else "",
        "longitude": place["longitude"] if mapped else "",
        "location_precision": place["precision"] if mapped else "",
        "geocode_source": "existing_frontend_or_stage_place_catalog" if mapped else "",
        "geocode_verification_status": "reviewed_place_catalog_match" if mapped else "",
        "coordinate_evidence_note": "AYR page text matched existing reviewed place catalog; coordinates reused as public display point only." if mapped else "",
        "duplicate_check_status": "checked_against_current_overlay_url_external_id_title_year",
        "quality_class": "B" if mapped else "C",
        "ethics_review_status": "public_web_context_reviewed" if status == "accepted" else "needs_review",
        "cultural_sensitivity": "low" if status == "accepted" else "review_required",
        "risk_flags": "",
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": rejection,
        "evidence_summary": evidence_window(text),
        "raw_metadata_json": json.dumps({"discovery": "commoncrawl", "source_url": canonical}, ensure_ascii=False, sort_keys=True),
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


def write_raw(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_report(path: Path, rows: list[dict[str, Any]], request_rows: list[dict[str, Any]], output: Path) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    bucket_counts: Counter[str] = Counter()
    mapped = 0
    for row in rows:
        if row["candidate_status"] != "accepted":
            continue
        if row.get("latitude") and row.get("longitude"):
            mapped += 1
        year = row.get("year")
        if not year:
            bucket_counts["undated"] += 1
        else:
            y = int(year)
            if 1926 <= y <= 1945:
                bucket_counts["1926-1945"] += 1
            elif 1946 <= y <= 1969:
                bucket_counts["1946-1969"] += 1
            elif 1970 <= y <= 1990:
                bucket_counts["1970-1990"] += 1
            elif 1991 <= y <= 2011:
                bucket_counts["1991-2011"] += 1
            elif y >= 2012:
                bucket_counts["2012-2026"] += 1
            else:
                bucket_counts["pre-1926"] += 1
    request_counts = Counter(row["status"] for row in request_rows)
    lines = [
        "# AYR Public Site Crawl From Common Crawl Discovery",
        "",
        "Stage-only crawl. Common Crawl is used only for URL discovery; evidence comes from current public AYR pages.",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Candidate CSV: `{output.resolve().relative_to(ROOT)}`",
        f"- Rows written: `{len(rows)}`",
        f"- Accepted candidates: `{status_counts.get('accepted', 0)}`",
        f"- Accepted mapped candidates: `{mapped}`",
        "",
        "## Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Accepted By Year Bucket", "| bucket | accepted |", "|---|---:|"])
    for key in ["1926-1945", "1946-1969", "1970-1990", "1991-2011", "2012-2026", "undated"]:
        lines.append(f"| {key} | {bucket_counts.get(key, 0)} |")
    lines.extend(["", "## Request Outcomes"])
    for key, count in request_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes"])
    lines.append("- Robots.txt is checked before current page fetches.")
    lines.append("- Coordinates are reused only from the current reviewed/stage place catalog.")
    lines.append("- Public source exists does not verify the supernatural claim.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--requests-output", type=Path, default=DEFAULT_REQUESTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--cc-limit", type=int, default=800)
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-bytes", type=int, default=500_000)
    args = parser.parse_args()

    urls, request_rows = cc_query(args.cc_limit, args.timeout)
    seen_urls: set[str] = set()
    filtered_urls: list[str] = []
    for url in urls:
        canonical = canonical_url(url)
        if canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        if url_allowed_by_path(canonical):
            filtered_urls.append(canonical)
    filtered_urls = filtered_urls[: args.max_pages]

    parser_robot = robots_parser(args.timeout)
    catalog = place_catalog(args.frontend)
    duplicate_keys = existing_keys(args.frontend)
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    host_last_fetch: defaultdict[str, float] = defaultdict(float)
    for url in filtered_urls:
        host = urlparse(url).netloc.lower()
        if parser_robot and not parser_robot.can_fetch(USER_AGENT, url):
            request_rows.append({"stage": "current_fetch", "url": url, "status": "robots_disallowed", "note": ""})
            continue
        elapsed = time.monotonic() - host_last_fetch[host]
        if elapsed < args.delay:
            time.sleep(args.delay - elapsed)
        try:
            html = fetch_html(url, args.timeout, args.max_bytes)
            request_rows.append({"stage": "current_fetch", "url": url, "status": "ok", "note": str(len(html))})
            row = classify(url, html, catalog, duplicate_keys)
            rows.append(row)
            raw_rows.append({"url": url, "title": row["title"], "candidate_status": row["candidate_status"], "evidence_summary": row["evidence_summary"]})
        except Exception as exc:  # noqa: BLE001
            request_rows.append({"stage": "current_fetch", "url": url, "status": "fetch_error", "note": f"{type(exc).__name__}:{clean(str(exc))[:160]}"})
        host_last_fetch[host] = time.monotonic()

    write_csv(args.output, rows)
    write_raw(args.raw_output, raw_rows)
    write_rows_csv(args.requests_output, ["stage", "url", "status", "note"], request_rows)
    write_report(args.report, rows, request_rows, args.output)
    status_counts = Counter(row["candidate_status"] for row in rows)
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    print(f"Wrote AYR public site candidates: {args.output}")
    print(f"Fetched candidate pages: {len(rows)}")
    print(f"Accepted: {status_counts.get('accepted', 0)}")
    print(f"Mapped accepted: {mapped}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
