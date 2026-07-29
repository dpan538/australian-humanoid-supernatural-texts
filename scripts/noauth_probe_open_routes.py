#!/usr/bin/env python3
"""Safely probe no-auth open routes and stage metadata-only candidates."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv, write_jsonl
from lib.noauth_web import (
    RouteSafety,
    USER_AGENT,
    allowed_by_robots,
    discover_sitemaps,
    extract_jsonld,
    extract_links,
    extract_pdf_links,
    extract_years,
    fetch_html_safe,
    looks_relevant,
    normalize_url,
    same_domain,
)
from probe_public_sources import CANDIDATE_FIELDS, REVIEW_FIELDS, candidate_from_probe, upsert_candidate, upsert_source_chain


NOAUTH_REVIEW_FIELDS = REVIEW_FIELDS
REPORT_DIR = ROOT / "data" / "processed" / "v2"
DISCOVERY_DIR = ROOT / "data" / "interim" / "source_discovery"
REVIEW_DIR = ROOT / "data" / "review" / "v2"


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def route_from_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "route_id": row.get("route_id") or row.get("source_id"),
        "source_id": row.get("source_id") or row.get("route_id"),
        "source_name": row.get("source_name"),
        "source_tier": row.get("source_tier"),
        "evidence_or_discovery": "evidence_possible",
        "route_family": row.get("route_family"),
        "base_url": row.get("official_url") or row.get("search_url"),
        "access_method": row.get("collection_mode"),
        "allowed_content_mode": "metadata_only",
    }


def query_row_from_plan(row: dict[str, str]) -> dict[str, str]:
    return {
        "query_id": row.get("query_id", ""),
        "query_string": row.get("query_string", ""),
        "term_family": row.get("term_family", ""),
        "time_band": row.get("time_band", ""),
        "target_state": row.get("target_state", ""),
        "target_locality": row.get("target_locality", ""),
        "start_year": row.get("start_year", ""),
        "end_year": row.get("end_year", ""),
        "review_mode": "noauth_open_records",
    }


def year_in_band(year: int | None, row: dict[str, str]) -> bool:
    if year is None:
        return False
    try:
        start = int(row.get("start_year") or 0)
        end = int(row.get("end_year") or 9999)
    except ValueError:
        return False
    return start <= year <= end


def title_from_html(html: str) -> str:
    import re

    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    text = re.sub(r"<[^>]+>", " ", match.group(1))
    return " ".join(text.split())


def page_text_summary(html: str) -> str:
    import re

    text = re.sub(r"<(script|style|nav|footer)\b.*?</\1>", " ", html or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())[:1500]


def item_from_link(link: dict[str, str], row: dict[str, str], page_url: str, context: str) -> dict[str, Any]:
    text = link.get("text") or link.get("url") or "Open record candidate"
    years = extract_years(" ".join([text, link.get("url", ""), context]))
    year = next((value for value in years if year_in_band(value, row)), years[0] if years else None)
    return {
        "stable_id": normalize_url(link.get("url", "")),
        "title": text[:300],
        "publication": row.get("source_name") or "",
        "date_published": str(year or ""),
        "url": normalize_url(link.get("url", "")),
        "snippet": context[:700],
        "source_stated_place_text": row.get("target_locality") or "",
        "location_role": "source_stated_place" if row.get("target_locality") else "",
        "rights_status": "metadata_only",
    }


def item_from_jsonld(data: dict[str, Any], row: dict[str, str], page_url: str) -> dict[str, Any] | None:
    title = data.get("name") or data.get("headline") or data.get("title")
    if not title:
        return None
    date = data.get("datePublished") or data.get("dateCreated") or data.get("temporalCoverage") or ""
    description = data.get("description") or ""
    url = data.get("url") or page_url
    return {
        "stable_id": normalize_url(str(url)),
        "title": str(title)[:300],
        "publication": row.get("source_name") or "",
        "date_published": str(date)[:40],
        "url": normalize_url(str(url)),
        "snippet": str(description)[:700],
        "source_stated_place_text": row.get("target_locality") or "",
        "location_role": "source_stated_place" if row.get("target_locality") else "",
        "rights_status": "metadata_only",
    }


def candidates_from_html(html: str, row: dict[str, str], page_url: str) -> tuple[list[dict[str, Any]], int]:
    terms = [row.get("term", ""), row.get("term_family", "")]
    localities = [row.get("target_locality", ""), row.get("target_state", "")]
    context = page_text_summary(html)
    candidates: list[dict[str, Any]] = []
    pdf_links = 0
    for data in extract_jsonld(html):
        item = item_from_jsonld(data, row, page_url)
        if item and looks_relevant(" ".join([item["title"], item["snippet"], item["url"]]), terms, localities):
            candidates.append(item)
    for link in extract_links(html, page_url):
        combined = " ".join([link.get("text", ""), link.get("url", ""), context])
        if looks_relevant(combined, terms, localities):
            candidates.append(item_from_link(link, row, page_url, context))
    pdf_links = len(extract_pdf_links(html, page_url))
    if not candidates and looks_relevant(" ".join([title_from_html(html), context, page_url]), terms, localities):
        candidates.append(
            {
                "stable_id": normalize_url(page_url),
                "title": title_from_html(html) or f"Open page candidate: {row.get('source_name')}",
                "publication": row.get("source_name") or "",
                "date_published": "",
                "url": normalize_url(page_url),
                "snippet": context[:700],
                "source_stated_place_text": row.get("target_locality") or "",
                "location_role": "source_stated_place" if row.get("target_locality") else "",
                "rights_status": "metadata_only",
            }
        )
    return candidates, pdf_links


def manual_candidate(run_id: str, row: dict[str, str], reason: str) -> dict[str, Any]:
    route = route_from_row(row)
    query_row = query_row_from_plan(row)
    item = {
        "stable_id": f"manual:{row.get('route_id')}:{row.get('query_id')}",
        "title": f"Manual no-auth review: {row.get('source_name')}",
        "publication": row.get("source_name") or "",
        "date_published": "",
        "url": row.get("search_url") or row.get("official_url") or "",
        "snippet": reason,
        "source_stated_place_text": row.get("target_locality") or "",
        "rights_status": "metadata_only",
    }
    return candidate_from_probe(run_id=run_id, route=route, query_row=query_row, item=item, review_status="manual_search_task", notes=reason)


def page_urls_for_row(row: dict[str, str]) -> list[str]:
    mode = row.get("probe_mode") or ""
    search_url = row.get("search_url") or row.get("official_url") or ""
    official_url = row.get("official_url") or search_url
    if mode == "sitemap":
        return discover_sitemaps(official_url)[:1]
    return [search_url]


def run_probe(db_path: Path, plan_path: Path, run_id: str, limit: int, execute: bool, extract_public_pdf_text: bool = False) -> dict[str, Any]:
    rows = read_plan(plan_path)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    skipped: Counter[str] = Counter()
    by_state: Counter[str] = Counter()
    by_band: Counter[str] = Counter()
    by_route: Counter[str] = Counter()
    warnings: list[str] = []
    routes_attempted: set[str] = set()
    robots_skipped: set[str] = set()
    policy_skipped: set[str] = set()
    pages_fetched = 0
    pdf_links = 0
    manual_tasks = 0
    duplicate_skipped = 0
    would_fetch = 0
    session = requests.Session()

    def add_candidate(candidate: dict[str, Any]) -> None:
        nonlocal duplicate_skipped
        candidate_id = str(candidate.get("candidate_id") or "")
        if candidate_id in seen:
            duplicate_skipped += 1
            return
        seen.add(candidate_id)
        candidates.append(candidate)
        by_state[str(candidate.get("target_state") or "")] += 1
        by_band[str(candidate.get("time_band") or "")] += 1
        by_route[str(candidate.get("route_id") or "")] += 1

    for row in rows:
        if len(candidates) >= limit:
            break
        route_id = row.get("route_id") or ""
        routes_attempted.add(route_id)
        if row.get("collection_mode") in {"manual_search_task", "manual_sensitive_review", "discovery_only"}:
            skipped["manual_or_discovery_route"] += 1
            policy_skipped.add(route_id)
            continue
        if truthy(row.get("should_download_pdf")) or (truthy(row.get("should_extract_pdf_text")) and not extract_public_pdf_text):
            skipped["pdf_body_or_text_blocked"] += 1
            policy_skipped.add(route_id)
            continue
        if not truthy(row.get("should_fetch")):
            skipped["not_marked_for_fetch"] += 1
            continue
        urls = page_urls_for_row(row)
        if not execute:
            would_fetch += len(urls)
            continue
        safety = RouteSafety(route_id=route_id, rate_limit_seconds=3.0, max_pages_per_run=1, respect_robots=True)
        for url in urls:
            if len(candidates) >= limit:
                break
            if not allowed_by_robots(url, USER_AGENT):
                robots_skipped.add(route_id)
                add_candidate(manual_candidate(run_id, row, f"robots.txt could not confirm safe metadata fetch for {url}"))
                manual_tasks += 1
                continue
            try:
                html = fetch_html_safe(url, safety, session)
            except Exception as exc:
                warnings.append(f"{route_id}: fetch failed: {exc}")
                continue
            if not html:
                skipped["non_html_or_fetch_failed"] += 1
                continue
            pages_fetched += 1
            items, pdf_count = candidates_from_html(html, row, url)
            pdf_links += pdf_count
            for item in items:
                add_candidate(candidate_from_probe(run_id=run_id, route=route_from_row(row), query_row=query_row_from_plan(row), item=item, review_status="needs_review"))
                if len(candidates) >= limit:
                    break

    jsonl_path = DISCOVERY_DIR / f"{run_id}_candidates.jsonl"
    review_path = REVIEW_DIR / f"{run_id}_candidate_review.csv"
    report_path = REPORT_DIR / f"{run_id}_report.md"
    write_jsonl(jsonl_path, candidates)
    write_csv(review_path, candidates, NOAUTH_REVIEW_FIELDS)

    staged = 0
    if execute:
        with sqlite3.connect(db_path) as conn:
            missing = [table for table in ("collection_candidates", "source_chains") if not table_exists(conn, table)]
            if missing:
                raise RuntimeError("Missing migration tables: " + ", ".join(missing))
            for candidate in candidates:
                upsert_candidate(conn, candidate)
                upsert_source_chain(conn, candidate, route_from_row({**candidate, "official_url": candidate.get("url", "")}))
                if candidate.get("review_status") == "needs_review":
                    staged += 1
            conn.commit()

    lines = [
        "# No-Auth Open Probe Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Plan rows read: `{len(rows)}`",
        f"- Routes attempted: `{len(routes_attempted)}`",
        f"- Dry-run pages that would be fetched: `{would_fetch}`",
        f"- Pages fetched: `{pages_fetched}`",
        f"- Candidates written to review CSV: `{len(candidates)}`",
        f"- Metadata candidates staged in SQLite: `{staged}`",
        f"- Manual task count: `{manual_tasks}`",
        f"- Duplicates skipped: `{duplicate_skipped}`",
        f"- PDF links recorded: `{pdf_links}`",
        f"- API keys used: `no`",
        f"- Full text downloaded: `no`",
        f"- PDF text extracted: `{'yes' if extract_public_pdf_text else 'no'}`",
        f"- JSONL: `{jsonl_path}`",
        f"- Review CSV: `{review_path}`",
        "",
        "## Skipped Counts",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(skipped.items())] or ["- None"])
    lines.extend(["", "## Routes Skipped By Robots Or Terms"])
    lines.extend([f"- `{route}`" for route in sorted(robots_skipped | policy_skipped)] or ["- None"])
    lines.extend(["", "## Candidate Distribution By State"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(by_state.items())] or ["- None"])
    lines.extend(["", "## Candidate Distribution By Time Band"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(by_band.items())] or ["- None"])
    lines.extend(["", "## Top Source Routes By Candidate Count"])
    lines.extend([f"- `{key}`: {value}" for key, value in by_route.most_common(20)] or ["- None"])
    if warnings:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {warning}" for warning in warnings[:50]])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "routes_attempted": len(routes_attempted),
        "would_fetch": would_fetch,
        "pages_fetched": pages_fetched,
        "candidates": len(candidates),
        "staged": staged,
        "manual_tasks": manual_tasks,
        "robots_skipped": len(robots_skipped),
        "policy_skipped": len(policy_skipped),
        "report": report_path,
        "review_csv": review_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--extract-public-pdf-text", action="store_true")
    args = parser.parse_args()
    execute = bool(args.execute and not args.dry_run)
    summary = run_probe(Path(args.db), Path(args.plan), args.run_id, args.limit, execute, args.extract_public_pdf_text)
    print(f"No-auth probe wrote {summary['candidates']} review rows.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
