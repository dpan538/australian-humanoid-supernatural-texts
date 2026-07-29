#!/usr/bin/env python3
"""Record public PDF links from no-auth source pages as metadata only."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.noauth_web import RouteSafety, USER_AGENT, allowed_by_robots, extract_pdf_links, fetch_html_safe


FIELDS = [
    "source_page_url",
    "pdf_url",
    "link_text",
    "surrounding_context",
    "content_type",
    "content_length",
    "last_modified",
    "target_state",
    "route_id",
    "source_name",
    "query_string",
    "relevance_signals",
    "review_status",
]


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def head_pdf(session: requests.Session, url: str) -> dict[str, str]:
    if not allowed_by_robots(url, USER_AGENT):
        return {"content_type": "", "content_length": "", "last_modified": "", "relevance_signals": "pdf_head_robots_unconfirmed"}
    try:
        response = session.head(url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf,*/*"}, timeout=20, allow_redirects=True)
    except Exception:
        return {"content_type": "", "content_length": "", "last_modified": "", "relevance_signals": "pdf_head_failed"}
    return {
        "content_type": response.headers.get("content-type", ""),
        "content_length": response.headers.get("content-length", ""),
        "last_modified": response.headers.get("last-modified", ""),
        "relevance_signals": "pdf_link_metadata_only",
    }


def run(plan_path: Path, out_path: Path, report_path: Path, limit: int, execute: bool) -> dict[str, Any]:
    plan = read_plan(plan_path)
    rows: list[dict[str, Any]] = []
    fetched_pages = 0
    robots_blocked = 0
    session = requests.Session()
    for item in plan:
        if len(rows) >= limit:
            break
        page_url = item.get("search_url") or item.get("official_url") or ""
        if not page_url:
            continue
        if not execute:
            continue
        if not allowed_by_robots(page_url, USER_AGENT):
            robots_blocked += 1
            continue
        html = fetch_html_safe(page_url, RouteSafety(route_id=item.get("route_id", ""), rate_limit_seconds=3.0), session)
        if not html:
            continue
        fetched_pages += 1
        for link in extract_pdf_links(html, page_url):
            meta = head_pdf(session, link["url"])
            rows.append(
                {
                    "source_page_url": page_url,
                    "pdf_url": link["url"],
                    "link_text": link["text"],
                    "surrounding_context": link["text"],
                    "content_type": meta["content_type"],
                    "content_length": meta["content_length"],
                    "last_modified": meta["last_modified"],
                    "target_state": item.get("target_state"),
                    "route_id": item.get("route_id"),
                    "source_name": item.get("source_name"),
                    "query_string": item.get("query_string"),
                    "relevance_signals": meta["relevance_signals"],
                    "review_status": "manual_review_pdf_metadata",
                }
            )
            if len(rows) >= limit:
                break
    write_csv(out_path, rows, FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# No-Auth PDF Metadata Report",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Mode: `{'execute' if execute else 'dry_run'}`",
                f"- Plan rows read: `{len(plan)}`",
                f"- HTML pages fetched: `{fetched_pages}`",
                f"- Robots blocked/unconfirmed pages: `{robots_blocked}`",
                f"- PDF metadata rows: `{len(rows)}`",
                "- PDF body downloaded: `no`",
                "- PDF text extracted: `no`",
                "- API keys used: `no`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"rows": len(rows), "robots_blocked": robots_blocked, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    summary = run(Path(args.plan), Path(args.out), Path(args.report), args.limit, bool(args.execute and not args.dry_run))
    print(f"Wrote PDF metadata rows: {summary['rows']}")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
