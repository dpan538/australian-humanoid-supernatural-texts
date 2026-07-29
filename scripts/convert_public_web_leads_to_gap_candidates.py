#!/usr/bin/env python3
"""Strictly convert older public-web lead CSVs into stage-only gap candidates."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from crawl_public_books_metadata import FIELDNAMES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FRONTEND = ROOT / "public" / "data" / "frontend-data.gap-public-web.json"
DEFAULT_OUTPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "public_web_leads" / "public_web_leads_round025_strict_candidates.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_public_web_leads_round025_strict.md"
DEFAULT_INPUTS = [
    ROOT / "data" / "interim" / "public_web_sitemap_leads_20260621.csv",
    ROOT / "data" / "interim" / "public_web_sitemap_leads_20260621_expanded.csv",
    ROOT / "data" / "interim" / "public_web_archive_first_leads_20260621.csv",
    ROOT / "data" / "interim" / "public_web_archive_first_leads_balanced_20260621.csv",
]

STRONG_RE = re.compile(r"\b(ghosts?|haunted|haunts?|haunting|paranormal|apparitions?|spirits?|spectral|phantoms?|resident ghost|white lady|grey lady)\b", re.I)
NOISE_RE = re.compile(r"\b(ghost writer|ghostwriter|ghost gum|ghost net|energy efficiency|home page|about us|membership|donate|shop|venue hire|search)\b", re.I)
INDIGENOUS_RE = re.compile(r"\b(aboriginal|indigenous|first nations|dreaming|dreamtime|sacred|ceremony)\b", re.I)
YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")

ALLOWED_HOSTS = {
    "portarthur.org.au",
    "www.portarthur.org.au",
    "www.adelaidegaol.sa.gov.au",
    "adelaidegaol.sa.gov.au",
    "www.nationaltrust.org.au",
    "nationaltrust.org.au",
    "libraries.tas.gov.au",
    "www.fremantleprison.com.au",
}


def utc_now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def canonical_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def year_from_text(text: str) -> int | None:
    years = [int(match.group(1)) for match in YEAR_RE.finditer(text)]
    if not years:
        return None
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
        if len(short) < 5:
            continue
        catalog.setdefault(
            norm(short),
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
    for key, place in sorted(catalog.items(), key=lambda item: len(item[0]), reverse=True):
        name = place["name"]
        if re.search(r"\b" + re.escape(name) + r"\b", text, re.I):
            return place
    return None


def existing_keys(frontend: Path) -> tuple[set[str], set[str]]:
    data = json.loads(frontend.read_text(encoding="utf-8"))
    urls: set[str] = set()
    external_ids: set[str] = set()
    for record in data.get("records", []):
        url = clean(record.get("url")).lower()
        if url:
            urls.add(canonical_url(url).lower())
        external_id = clean(record.get("external_id"))
        if external_id:
            external_ids.add(external_id)
    return urls, external_ids


def source_name_for_host(host: str) -> str:
    if "portarthur" in host:
        return "Port Arthur Historic Site"
    if "adelaidegaol" in host:
        return "Adelaide Gaol"
    if "nationaltrust" in host:
        return "National Trust Australia"
    if "libraries.tas" in host:
        return "Libraries Tasmania"
    if "fremantleprison" in host:
        return "Fremantle Prison"
    return host


def classify(row: dict[str, str], catalog: dict[str, dict[str, Any]], duplicate_keys: tuple[set[str], set[str]]) -> dict[str, Any]:
    url = canonical_url(clean(row.get("url")))
    host = urlparse(url).netloc.lower()
    title = clean(row.get("title")) or "Public web lead"
    snippet = clean(row.get("snippet"))
    text = clean(" ".join([title, snippet, row.get("matched_terms", "") or ""]))
    year = year_from_text(text)
    source_name = source_name_for_host(host)
    external_id = "public-web-lead:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    urls, external_ids = duplicate_keys
    place = match_place(text, catalog)
    status = "accepted"
    rejection = ""
    if row.get("lead_status") != "review_candidate":
        status = "rejected"
        rejection = "not_review_candidate"
    elif host not in ALLOWED_HOSTS:
        status = "rejected"
        rejection = "host_not_in_strict_allowed_set"
    elif url.lower() in urls or external_id in external_ids:
        status = "duplicate_existing_record"
        rejection = "duplicate_against_current_overlay"
    elif NOISE_RE.search(text):
        status = "rejected"
        rejection = "noise_pattern"
    elif not (STRONG_RE.search(title) or STRONG_RE.search(url)):
        status = "rejected"
        rejection = "strong_term_only_in_navigation_or_body"
    elif not STRONG_RE.search(text):
        status = "rejected"
        rejection = "missing_strong_ghost_or_haunting_context"
    elif not place:
        status = "lead_only"
        rejection = "no_existing_place_coordinate_match"
    elif INDIGENOUS_RE.search(text):
        status = "lead_only"
        rejection = "indigenous_related_public_page_requires_manual_review"

    mapped = status == "accepted" and bool(place)
    terms = sorted({match.group(0).lower() for match in STRONG_RE.finditer(text)})
    return {
        "candidate_status": status,
        "source_name": source_name,
        "source_type": "institutional_or_public_heritage_web_page",
        "source_tier": "B",
        "query_family_id": "strict_public_web_haunted_place_leads",
        "query_string": "Strict conversion of prior public-web sitemap leads",
        "abc_hit_id": "",
        "title": title,
        "publication_or_organisation": source_name,
        "publication_date_text": str(year) if year else "",
        "year": year or "",
        "date_scope": date_scope(year),
        "access_date": date.today().isoformat(),
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_web_page",
        "rights_access_status": "public_web_short_summary_only",
        "narrative_type": "ghost_legend",
        "secondary_role": "strict_public_web_lead_conversion",
        "australian_relation": "Public Australian heritage/institutional page collected in prior public-web crawl.",
        "humanoid_basis": "person_form_or_ghost_context",
        "source_label": "ghost",
        "matched_terms": ";".join(terms),
        "matched_place": place["name"] if place else "",
        "location_text": place["location_text"] if place else "",
        "location_role": "public_display_place",
        "latitude": place["latitude"] if mapped else "",
        "longitude": place["longitude"] if mapped else "",
        "location_precision": place["precision"] if mapped else "",
        "geocode_source": "existing_frontend_or_stage_place_catalog" if mapped else "",
        "geocode_verification_status": "reviewed_place_catalog_match" if mapped else "",
        "coordinate_evidence_note": "Lead text matched existing reviewed place catalog; coordinates reused as public display point only." if mapped else "",
        "duplicate_check_status": "checked_against_current_overlay_url_external_id",
        "quality_class": "B" if mapped else "C",
        "ethics_review_status": "public_web_context_reviewed" if status == "accepted" else "needs_review",
        "cultural_sensitivity": "low" if status == "accepted" else "review_required",
        "risk_flags": "",
        "acceptance_decision": "accepted" if status == "accepted" else "not_accepted",
        "rejection_reason": rejection,
        "evidence_summary": snippet[:900],
        "raw_metadata_json": json.dumps({"source_lead_status": row.get("lead_status"), "source_matched_terms": row.get("matched_terms")}, ensure_ascii=False, sort_keys=True),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDNAMES})


def write_report(path: Path, rows: list[dict[str, Any]], output: Path) -> None:
    status_counts = Counter(row["candidate_status"] for row in rows)
    source_counts = Counter(row["source_name"] for row in rows if row["candidate_status"] == "accepted")
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    lines = [
        "# Strict Public Web Lead Conversion",
        "",
        "Stage-only conversion of prior public-web crawl leads.",
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
    lines.extend(["", "## Accepted By Source"])
    for key, count in source_counts.most_common():
        lines.append(f"- {key}: {count}")
    lines.extend(["", "## Notes"])
    lines.append("- Only review_candidate rows from prior public-web crawls are considered.")
    lines.append("- Rows must have strong ghost/haunting context and an existing reviewed place-coordinate match.")
    lines.append("- Coordinates are public display points, not proof or habitat locations.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", type=Path, default=DEFAULT_FRONTEND)
    parser.add_argument("--input", type=Path, nargs="*", default=DEFAULT_INPUTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    catalog = place_catalog(args.frontend)
    duplicate_keys = existing_keys(args.frontend)
    rows: list[dict[str, Any]] = []
    seen_source_rows: set[str] = set()
    for path in args.input:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as handle:
            for source_row in csv.DictReader(handle):
                key = clean(source_row.get("url"))
                if key in seen_source_rows:
                    continue
                seen_source_rows.add(key)
                rows.append(classify(source_row, catalog, duplicate_keys))
    write_csv(args.output, rows)
    write_report(args.report, rows, args.output)
    status_counts = Counter(row["candidate_status"] for row in rows)
    mapped = sum(1 for row in rows if row["candidate_status"] == "accepted" and row.get("latitude") and row.get("longitude"))
    print(f"Wrote strict public web lead candidates: {args.output}")
    print(f"Rows: {len(rows)}")
    print(f"Accepted: {status_counts.get('accepted', 0)}")
    print(f"Mapped accepted: {mapped}")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
