#!/usr/bin/env python3
"""Discover sitemap URLs from no-auth seed routes without using APIs."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_yaml, now_iso, write_csv
from lib.noauth_web import USER_AGENT, allowed_by_robots, discover_sitemaps


FILTER_TERMS = {
    "history",
    "local-history",
    "archive",
    "archives",
    "heritage",
    "museum",
    "collection",
    "catalogue",
    "search",
    "gaol",
    "cemetery",
    "hotel",
    "ghost",
    "haunted",
    "apparition",
    "legend",
    "folklore",
}
FIELDS = ["route_id", "source_name", "state", "sitemap_url", "candidate_url", "matched_terms", "robots_status", "dry_run"]


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def extract_locs(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml or "", flags=re.IGNORECASE)


def matching_terms(url: str) -> list[str]:
    lower = url.lower()
    return sorted(term for term in FILTER_TERMS if term in lower)


def discover(seeds_path: Path, out_path: Path, report_path: Path, limit_routes: int, execute: bool) -> dict[str, Any]:
    seeds = load_yaml(seeds_path) or []
    rows: list[dict[str, Any]] = []
    checked = 0
    robots_blocked = 0
    huge_capped = 0
    session = requests.Session()
    for route in seeds[:limit_routes]:
        if truthy(route.get("api_key_required")) or truthy(route.get("login_required")) or truthy(route.get("paywall_required")):
            continue
        route_id = route.get("route_id") or route.get("source_id")
        base = route.get("official_url") or ""
        if not base:
            continue
        checked += 1
        sitemap_urls = discover_sitemaps(base) if execute else [base.rstrip("/") + "/sitemap.xml"]
        for sitemap_url in sitemap_urls[:3]:
            if not execute:
                rows.append(
                    {
                        "route_id": route_id,
                        "source_name": route.get("source_name"),
                        "state": route.get("state"),
                        "sitemap_url": sitemap_url,
                        "candidate_url": "",
                        "matched_terms": "",
                        "robots_status": "dry_run_not_checked",
                        "dry_run": "true",
                    }
                )
                continue
            if not allowed_by_robots(sitemap_url, USER_AGENT):
                robots_blocked += 1
                rows.append(
                    {
                        "route_id": route_id,
                        "source_name": route.get("source_name"),
                        "state": route.get("state"),
                        "sitemap_url": sitemap_url,
                        "candidate_url": "",
                        "matched_terms": "",
                        "robots_status": "blocked_or_unconfirmed",
                        "dry_run": "false",
                    }
                )
                continue
            try:
                response = session.get(sitemap_url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/plain"}, timeout=25)
            except Exception:
                continue
            if response.status_code != 200:
                continue
            locs = extract_locs(response.text)
            if len(locs) > 1000:
                huge_capped += 1
            for loc in locs[:1000]:
                terms = matching_terms(loc)
                if not terms:
                    continue
                rows.append(
                    {
                        "route_id": route_id,
                        "source_name": route.get("source_name"),
                        "state": route.get("state"),
                        "sitemap_url": sitemap_url,
                        "candidate_url": loc,
                        "matched_terms": ";".join(terms),
                        "robots_status": "allowed",
                        "dry_run": "false",
                    }
                )
    write_csv(out_path, rows, FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# No-Auth Sitemap Inventory",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Mode: `{'execute' if execute else 'dry_run'}`",
                f"- Routes checked: `{checked}`",
                f"- Inventory rows: `{len(rows)}`",
                f"- Robots blocked/unconfirmed: `{robots_blocked}`",
                f"- Huge sitemaps capped: `{huge_capped}`",
                "- APIs used: `no`",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"rows": len(rows), "robots_blocked": robots_blocked, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--limit-routes", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    summary = discover(Path(args.seeds), Path(args.out), Path(args.report), args.limit_routes, bool(args.execute and not args.dry_run))
    print(f"Wrote sitemap inventory rows: {summary['rows']}")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
