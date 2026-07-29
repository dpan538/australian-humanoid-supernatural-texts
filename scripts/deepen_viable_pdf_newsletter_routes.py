#!/usr/bin/env python3
"""Deepen viable PDF/newsletter/journal routes in snippet-only mode."""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import write_csv
from lib.autoharvest_engine import load_autoharvest_config
from lib.gap_recovery import candidate_from_seed, classify_and_optionally_stage, read_csv, write_report
from lib.noauth_web import RouteSafety, allowed_by_robots, extract_pdf_links, fetch_html_safe, same_domain
from migrate_autoharvest_gap_v2 import migrate
from probe_public_pdf_snippets_gap import decode_pdf_text_snippet, extract_issue_date_text, extract_snippets


def candidate_routes(viability_dir: Path, limit_routes: int) -> list[dict]:
    rows = read_csv(viability_dir / "viability_candidates.csv")
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        hay = " ".join(str(row.get(k) or "") for k in ["url", "title", "route_family", "item_format"]).lower()
        if any(token in hay for token in [".pdf", "newsletter", "journal", "bulletin", "serial_issue_item", "pdf_issue"]):
            grouped[row.get("route_id") or row.get("source_id") or "unknown"].append(row)
    scored = sorted(grouped.items(), key=lambda item: (len(item[1]), item[0]), reverse=True)
    routes = []
    for route_id, items in scored[:limit_routes]:
        first = items[0]
        routes.append({**first, "route_id": route_id, "seed_count": len(items)})
    return routes


def fetch_page(url: str, route_id: str, config, session: requests.Session, execute: bool) -> str:
    if not execute:
        return ""
    return fetch_html_safe(
        url,
        RouteSafety(
            route_id=route_id,
            rate_limit_seconds=float(config.data.get("safety", {}).get("rate_limit_seconds_default", 3.0)),
            timeout_seconds=float(config.data.get("safety", {}).get("html_timeout_seconds", 8.0)),
        ),
        session,
    ) or ""


def fetch_pdf_snippets(url: str, config, session: requests.Session, terms: list[str]) -> tuple[list[str], str]:
    if not url.lower().split("?", 1)[0].endswith(".pdf"):
        return [], "not_pdf"
    if not allowed_by_robots(url, config.user_agent):
        return [], "robots_denied_or_unknown"
    max_bytes = int(config.data.get("safety", {}).get("max_pdf_bytes_for_snippet_mode", 15000000))
    try:
        head = session.head(url, headers={"User-Agent": config.user_agent}, timeout=(5, 8), allow_redirects=True)
        size = int(head.headers.get("content-length") or 0)
        if size and size > max_bytes:
            return [], "oversized_pdf"
        response = session.get(url, headers={"User-Agent": config.user_agent, "Accept": "application/pdf"}, timeout=(5, 12))
    except Exception:
        return [], "fetch_exception_or_timeout"
    if response.status_code != 200 or len(response.content) > max_bytes:
        return [], "fetch_failed_or_oversized"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp:
        temp.write(response.content)
        temp.flush()
        text = decode_pdf_text_snippet(response.content)
    if not re.search(r"[A-Za-z]{20,}", text or ""):
        return [], "image_only_or_unreadable_pdf"
    snippets = extract_snippets(text, terms)
    return snippets, "ok" if snippets else "no_controlled_term_snippet"


def deepen(db_path: Path, viability_dir: Path, run_id: str, limit_routes: int, limit_pdfs_per_route: int, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = load_autoharvest_config(ROOT / "config" / "autoharvest_gap_rescue.yml")
    terms = config.data.get("term_gate", {}).get("controlled_terms") or ["ghost", "haunted", "yowie", "bunyip"]
    out_dir = ROOT / "data" / "processed" / "v2" / "autoharvest" / "pdf_newsletter_deepening"
    out_dir.mkdir(parents=True, exist_ok=True)
    routes = candidate_routes(viability_dir, limit_routes)
    snippet_rows: list[dict] = []
    target_rows: list[dict] = []
    near_rows: list[dict] = []
    expand_rows: list[dict] = []
    pause_rows: list[dict] = []
    route_failures: Counter[str] = Counter()
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        for route in routes:
            route_id = route.get("route_id") or "unknown"
            urls: list[str] = []
            seed_url = route.get("url") or route.get("evidence_source_url") or route.get("access_source_url") or ""
            if seed_url.lower().split("?", 1)[0].endswith(".pdf"):
                urls.append(seed_url)
            elif seed_url.startswith(("http://", "https://")):
                html = fetch_page(seed_url, route_id, config, session, execute)
                for link in extract_pdf_links(html, seed_url):
                    if same_domain(seed_url, link["url"]):
                        urls.append(link["url"])
            urls = list(dict.fromkeys(urls))[:limit_pdfs_per_route]
            if not urls:
                pause_rows.append({**route, "pause_reason": "no_pdf_links_found"})
                continue
            for pdf_url in urls:
                snippets, status = fetch_pdf_snippets(pdf_url, config, session, terms) if execute else ([], "dry_run")
                if status != "ok":
                    route_failures[route_id] += 1
                    pause_rows.append({**route, "url": pdf_url, "pause_reason": status})
                    continue
                expand_rows.append({**route, "url": pdf_url, "next_action": "continue_pdf_snippet_lane"})
                for snippet in snippets[:3]:
                    date_text = extract_issue_date_text(route.get("title") or "", pdf_url, snippet)
                    candidate = candidate_from_seed(route, run_id, route.get("title") or Path(urlparse(pdf_url).path).name, pdf_url, snippet, date_text, "PDF_ISSUE")
                    decision, staged = classify_and_optionally_stage(conn, candidate, dict(route), config.data, snippet, execute)
                    snippet_rows.append(staged)
                    if decision.target_gap_eligible:
                        target_rows.append(staged)
                    else:
                        near_rows.append(staged)
        if execute:
            conn.commit()
    write_csv(out_dir / "pdf_snippet_candidates.csv", snippet_rows, list(snippet_rows[0].keys()) if snippet_rows else ["candidate_id"])
    write_csv(out_dir / "pdf_target_gap_candidates.csv", target_rows, list(target_rows[0].keys()) if target_rows else ["candidate_id"])
    write_csv(out_dir / "pdf_near_misses.csv", near_rows, list(near_rows[0].keys()) if near_rows else ["candidate_id"])
    write_csv(out_dir / "pdf_routes_to_expand.csv", expand_rows, list(expand_rows[0].keys()) if expand_rows else ["route_id"])
    write_csv(out_dir / "pdf_routes_to_pause.csv", pause_rows, list(pause_rows[0].keys()) if pause_rows else ["route_id"])
    write_report(
        out_dir / "pdf_newsletter_deepening_report.md",
        "PDF Newsletter Deepening Report",
        {
            "Run ID": run_id,
            "Routes inspected": len(routes),
            "Snippet candidates": len(snippet_rows),
            "Target-gap candidates": len(target_rows),
            "Near misses": len(near_rows),
            "Routes to expand": len(expand_rows),
            "Routes to pause": len(pause_rows),
            "PDF bodies stored": "no",
            "Full extracted text stored": "no",
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
    )
    return {"routes": len(routes), "snippets": len(snippet_rows), "targets": len(target_rows), "near_misses": len(near_rows), "expand": len(expand_rows)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--viability-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit-routes", type=int, default=20)
    parser.add_argument("--limit-pdfs-per-route", type=int, default=100)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(deepen(Path(args.db), Path(args.viability_dir), args.run_id, args.limit_routes, args.limit_pdfs_per_route, execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
