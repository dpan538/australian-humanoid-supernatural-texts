#!/usr/bin/env python3
"""Find candidate no-auth source routes from trusted official/local seed pages."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_yaml, now_iso, stable_query_id, write_csv
from lib.noauth_web import RouteSafety, USER_AGENT, allowed_by_robots, extract_links, fetch_html_safe, same_domain


FIELDS = [
    "candidate_route_id",
    "source_seed_route_id",
    "candidate_source_name",
    "candidate_url",
    "state",
    "route_family_guess",
    "source_tier_guess",
    "collection_mode_guess",
    "evidence_or_discovery_guess",
    "reason_discovered",
    "anchor_text",
    "context_snippet",
    "robots_status",
    "recommended_action",
]
KEYWORDS = [
    "history",
    "historical society",
    "local studies",
    "archives",
    "archive",
    "museum",
    "heritage",
    "collection",
    "catalogue",
    "library",
    "gaol",
    "cemetery",
    "oral history",
    "newsletter",
    "journal",
]
TRUSTED_HOST_TOKENS = {".gov.au", ".edu.au", "museum", "history", "historical", "heritage", "library", "archives"}


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def trusted_outgoing(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return any(token in host for token in TRUSTED_HOST_TOKENS)


def link_reason(text: str, url: str) -> str:
    hay = f"{text} {url}".lower()
    return ";".join(keyword for keyword in KEYWORDS if keyword in hay)


def guess_family(reason: str) -> str:
    if "archive" in reason:
        return "state_archive_catalogue"
    if "museum" in reason:
        return "museum_heritage_page"
    if "heritage" in reason or "gaol" in reason or "cemetery" in reason:
        return "heritage_register"
    if "library" in reason or "catalogue" in reason:
        return "state_library_catalogue"
    return "local_history_serial"


def discover(seeds_path: Path, out_path: Path, report_path: Path, limit: int, execute: bool) -> dict[str, Any]:
    seeds = load_yaml(seeds_path) or []
    rows: list[dict[str, Any]] = []
    fetched = 0
    robots_blocked = 0
    session = requests.Session()
    for seed in seeds:
        if len(rows) >= limit:
            break
        if truthy(seed.get("api_key_required")) or truthy(seed.get("login_required")) or truthy(seed.get("paywall_required")):
            continue
        route_id = seed.get("route_id") or seed.get("source_id")
        url = seed.get("official_url") or ""
        if not url:
            continue
        if not execute:
            rows.append(
                {
                    "candidate_route_id": "dry_" + stable_query_id(route_id, url),
                    "source_seed_route_id": route_id,
                    "candidate_source_name": seed.get("source_name"),
                    "candidate_url": url,
                    "state": seed.get("state"),
                    "route_family_guess": seed.get("route_family"),
                    "source_tier_guess": seed.get("source_tier"),
                    "collection_mode_guess": "review_candidate_only",
                    "evidence_or_discovery_guess": "discovery_only",
                    "reason_discovered": "dry_run_seed_inventory",
                    "anchor_text": "",
                    "context_snippet": "",
                    "robots_status": "dry_run_not_checked",
                    "recommended_action": "REVIEW_ROUTE_CANDIDATE",
                }
            )
            continue
        if not allowed_by_robots(url, USER_AGENT):
            robots_blocked += 1
            continue
        html = fetch_html_safe(url, RouteSafety(route_id=str(route_id), rate_limit_seconds=3.0), session)
        if not html:
            continue
        fetched += 1
        for link in extract_links(html, url):
            reason = link_reason(link.get("text", ""), link.get("url", ""))
            if not reason:
                continue
            if not same_domain(url, link["url"]) and not trusted_outgoing(link["url"]):
                continue
            rows.append(
                {
                    "candidate_route_id": "noauth_route_" + stable_query_id(route_id, link["url"]),
                    "source_seed_route_id": route_id,
                    "candidate_source_name": re.sub(r"\s+", " ", link.get("text") or "").strip()[:120],
                    "candidate_url": link["url"],
                    "state": seed.get("state"),
                    "route_family_guess": guess_family(reason),
                    "source_tier_guess": "B" if same_domain(url, link["url"]) else "C",
                    "collection_mode_guess": "static_html_metadata",
                    "evidence_or_discovery_guess": "evidence_possible",
                    "reason_discovered": reason,
                    "anchor_text": link.get("text"),
                    "context_snippet": link.get("text"),
                    "robots_status": "seed_page_allowed",
                    "recommended_action": "REVIEW_ROUTE_CANDIDATE",
                }
            )
            if len(rows) >= limit:
                break
    write_csv(out_path, rows[:limit], FIELDS)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "\n".join(
            [
                "# No-Auth Discovered Route Candidates",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Mode: `{'execute' if execute else 'dry_run'}`",
                f"- Candidate routes written: `{len(rows[:limit])}`",
                f"- Seed pages fetched: `{fetched}`",
                f"- Robots blocked/unconfirmed: `{robots_blocked}`",
                "- Source registry mutations: `none`",
                "- Candidate routes are review tasks only.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"rows": len(rows[:limit]), "robots_blocked": robots_blocked, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    summary = discover(Path(args.seeds), Path(args.out), Path(args.report), args.limit, bool(args.execute and not args.dry_run))
    print(f"Wrote route candidates: {summary['rows']}")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
