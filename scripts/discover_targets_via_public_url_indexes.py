#!/usr/bin/env python3
"""Discover trusted-domain target URLs via no-key public URL indexes."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]

from collection_expansion_common import write_csv
from lib.gap_recovery import TARGET_TERMS, domain_of, read_yaml_rows, route_id_for_url, trusted_domains_from_sources, url_pattern_priority, write_report

FIELDS = [
    "discovered_url",
    "live_or_archived",
    "index_source",
    "route_id",
    "domain",
    "source_tier_guess",
    "route_family_guess",
    "matched_url_terms",
    "likely_item_level",
    "likely_pdf",
    "likely_newsletter",
    "likely_year_signal",
    "target_priority_score",
    "next_action",
]


def safe_index_source(url: str) -> bool:
    host = domain_of(url)
    if any(token in host for token in ["google", "bing", "trove"]):
        return False
    return host in {"web.archive.org", "index.commoncrawl.org", "archive.org", "archive-it.org"} or host.endswith("commoncrawl.org")


def seed_routes(seeds_path: Path, registry_path: Path) -> list[dict]:
    rows = read_yaml_rows(seeds_path) + read_yaml_rows(registry_path)
    out = []
    for row in rows:
        url = str(row.get("official_url") or row.get("url") or "")
        if not url.startswith(("http://", "https://")):
            continue
        if row.get("evidence_or_discovery") == "manual_only_sensitive" or row.get("collection_mode") == "manual_sensitive_review":
            continue
        if row.get("api_key_required") or "trove" in url.lower() and "api" in url.lower():
            continue
        out.append(row)
    return out


def wayback_query(domain: str, term: str, limit: int) -> str:
    pattern = f"{domain}/*{term}*"
    return f"https://web.archive.org/cdx?url={quote_plus(pattern)}&output=json&fl=original,timestamp,statuscode,mimetype&filter=statuscode:200&collapse=urlkey&limit={limit}"


def rows_from_wayback(data) -> list[dict]:
    if not isinstance(data, list) or len(data) < 2:
        return []
    header = data[0]
    out = []
    for values in data[1:]:
        row = dict(zip(header, values))
        if row.get("original"):
            out.append(row)
    return out


def classify_url(url: str, route: dict, index_source: str, live: bool) -> dict:
    score, reasons = url_pattern_priority(url, str(route.get("state") or ""), str(route.get("route_family") or ""))
    hay = url.lower()
    matched = [term for term in TARGET_TERMS if term in hay]
    likely_pdf = ".pdf" in hay
    likely_newsletter = any(token in hay for token in ["newsletter", "journal", "bulletin"])
    likely_year = any(token in hay for token in ["1930", "1940", "1950", "1960", "1970"])
    return {
        "discovered_url": url,
        "live_or_archived": "live_preferred" if live else "archived_only",
        "index_source": index_source,
        "route_id": route.get("route_id") or route.get("source_id") or route_id_for_url(url, "idx"),
        "domain": domain_of(url),
        "source_tier_guess": route.get("source_tier") or "B",
        "route_family_guess": route.get("route_family") or "public_history_site",
        "matched_url_terms": ";".join(matched),
        "likely_item_level": int(bool(matched or likely_pdf or likely_newsletter or likely_year)),
        "likely_pdf": int(likely_pdf),
        "likely_newsletter": int(likely_newsletter),
        "likely_year_signal": int(likely_year),
        "target_priority_score": score,
        "next_action": "PROBE_LIVE_URL_SNIPPET" if live else "ACCESS_ARCHIVE_CANDIDATE_REQUIRES_DECOMPOSITION",
    }


def discover(db_path: Path, seeds: Path, registry: Path, run_id: str, out_dir: Path, limit_domains: int, limit_url_hits_per_domain: int, execute: bool) -> dict[str, int]:
    del db_path
    routes = seed_routes(seeds, registry)
    trusted = trusted_domains_from_sources(seeds, registry)
    by_domain: dict[str, dict] = {}
    for route in routes:
        domain = domain_of(str(route.get("official_url") or ""))
        if domain in trusted and domain not in by_domain:
            by_domain[domain] = route
    discovered: list[dict] = []
    archived: list[dict] = []
    near: list[dict] = []
    route_candidates: list[dict] = []
    session = requests.Session()
    if execute:
        for domain, route in list(by_domain.items())[:limit_domains]:
            per_domain = 0
            for term in TARGET_TERMS[:12]:
                if per_domain >= limit_url_hits_per_domain:
                    break
                url = wayback_query(domain, term, min(20, limit_url_hits_per_domain - per_domain))
                if not safe_index_source(url):
                    continue
                try:
                    response = session.get(
                        url,
                        headers={"User-Agent": "AusFiguresNoAuthResearchBot/0.1 metadata-first no-login no-api"},
                        timeout=(5, 8),
                        allow_redirects=False,
                    )
                    data = response.json() if response.status_code == 200 else []
                except Exception:
                    data = []
                for hit in rows_from_wayback(data):
                    original = hit.get("original") or ""
                    if domain_of(original) != domain:
                        continue
                    row = classify_url(original, route, "WAYBACK_CDX", live=False)
                    archived.append(row)
                    if row["target_priority_score"] > 0:
                        near.append(row)
                        route_candidates.append({**row, "route_candidate_status": "discovered_from_public_index"})
                    per_domain += 1
    out_dir.mkdir(parents=True, exist_ok=True)
    discovered = [row for row in archived if row["live_or_archived"] == "live_preferred"]
    write_csv(out_dir / "discovered_target_urls.csv", discovered + archived, FIELDS)
    write_csv(out_dir / "live_url_probe_plan.csv", discovered, FIELDS)
    write_csv(out_dir / "archived_only_candidates.csv", archived, FIELDS)
    write_csv(out_dir / "public_index_near_misses.csv", near, FIELDS)
    write_csv(out_dir / "route_candidates_from_indexes.csv", route_candidates, list(route_candidates[0].keys()) if route_candidates else FIELDS + ["route_candidate_status"])
    write_report(
        out_dir / "public_index_discovery_report.md",
        "Public URL Index Discovery Report",
        {
            "Run ID": run_id,
            "Execute": str(execute).lower(),
            "Trusted domains considered": min(len(by_domain), limit_domains),
            "URL hits discovered": len(discovered) + len(archived),
            "Live URL probe rows": len(discovered),
            "Archived-only candidates": len(archived),
            "Index queries are discovery only": "yes",
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
    )
    return {"domains": min(len(by_domain), limit_domains), "urls": len(discovered) + len(archived), "live": len(discovered), "archived": len(archived), "route_candidates": len(route_candidates)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--limit-domains", type=int, default=200)
    parser.add_argument("--limit-url-hits-per-domain", type=int, default=200)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(discover(Path(args.db), Path(args.seeds), Path(args.registry), args.run_id, Path(args.out_dir), args.limit_domains, args.limit_url_hits_per_domain, execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
