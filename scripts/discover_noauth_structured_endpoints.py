#!/usr/bin/env python3
"""Discover no-credential structured metadata endpoints for trusted routes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.noauth_web import allowed_by_robots
from lib.structured_endpoints import USER_AGENT, discover_embedded_structured_links, is_disallowed_url
from migrate_structured_endpoint_harvest_v1 import migrate


def load_yaml_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [row for row in data if isinstance(row, dict)]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def endpoint_id(route_id: str, endpoint_type: str, endpoint_url: str) -> str:
    raw = "|".join([route_id or "", endpoint_type or "", endpoint_url or ""])
    return "ep_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def domain(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower().replace("www.", "")


def base_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


def route_key(row: dict) -> str:
    return str(row.get("route_id") or row.get("source_id") or domain(row.get("official_url") or ""))


def route_url(row: dict) -> str:
    return str(row.get("official_url") or row.get("url") or row.get("search_url") or "")


def disallowed_route(row: dict) -> tuple[bool, str]:
    url = route_url(row)
    hay = " ".join(str(row.get(key) or "") for key in ["route_id", "source_id", "source_name", "official_url", "access_method", "collection_mode", "evidence_or_discovery"]).lower()
    if is_disallowed_url(url) or "api.trove" in hay or "google" in hay or "bing" in hay:
        return True, "disallowed_api_or_search_provider"
    if any(token in hay for token in ["login", "paywall", "captcha", "api_key_required", "token_required"]):
        return True, "auth_paywall_or_token"
    if row.get("api_key_required") or row.get("login_required") or row.get("paywall_required"):
        return True, "auth_paywall_or_key_flag"
    if row.get("evidence_or_discovery") == "manual_only_sensitive" or row.get("collection_mode") == "manual_sensitive_review":
        return True, "manual_sensitive"
    return False, ""


def endpoint_patterns(root: str) -> list[tuple[str, str]]:
    return [
        ("WORDPRESS_REST", urljoin(root, "/wp-json/wp/v2/search?search={query}")),
        ("WORDPRESS_REST", urljoin(root, "/wp-json/wp/v2/posts?search={query}")),
        ("OMEKA_API", urljoin(root, "/api/items")),
        ("OMEKA_API", urljoin(root, "/api/search?query={query}")),
        ("ATOM_AtoM", urljoin(root, "/index.php/informationobject/browse?query={query}")),
        ("RSS_ATOM", urljoin(root, "/feed")),
        ("RSS_ATOM", urljoin(root, "/rss")),
        ("OAI_PMH", urljoin(root, "/oai?verb=Identify")),
        ("OAI_PMH", urljoin(root, "/oai/request?verb=Identify")),
        ("OAI_PMH", urljoin(root, "/oai2?verb=Identify")),
        ("OAI_PMH", urljoin(root, "/cgi/oai2?verb=Identify")),
        ("OAI_PMH", urljoin(root, "/repository/oai?verb=Identify")),
        ("OAI_PMH", urljoin(root, "/api/oai?verb=Identify")),
        ("ATOM_AtoM", urljoin(root, "/index.php/index.php/informationobject/browse?query={query}")),
        ("DRUPAL_JSON", urljoin(root, "/jsonapi")),
        ("DRUPAL_JSON", urljoin(root, "/search?search={query}")),
        ("RSS_ATOM", urljoin(root, "/atom.xml")),
        ("IIIF", urljoin(root, "/iiif/collection.json")),
        ("CKAN_PUBLIC", urljoin(root, "/api/3/action/package_search?q={query}")),
    ]


def classify_response(endpoint_type: str, status_code: int, text: str, content_type: str) -> tuple[bool, str, float, str]:
    lower = (text or "").lower()[:5000]
    if status_code in {401, 403} or any(token in lower for token in ["api key", "apikey", "access token", "login required", "captcha", "unauthorized"]):
        return False, "auth_or_key_required", 0.0, "disallowed"
    if status_code in {429}:
        return False, "rate_limited", 0.0, "paused"
    if status_code >= 400 or not text:
        return False, f"http_{status_code}", 0.0, "rejected"
    if endpoint_type == "OAI_PMH" and ("<oai-pmh" in lower or "<identify" in lower or "listmetadataformats" in lower):
        return True, "oai_response", 0.95, "active"
    if endpoint_type == "OMEKA_API" and ("application/json" in content_type or text.strip().startswith(("[", "{"))) and ("o:resource" in lower or "o:title" in lower or "dcterms" in lower or "items" in lower):
        return True, "omeka_json", 0.85, "active"
    if endpoint_type == "WORDPRESS_REST" and ("application/json" in content_type or text.strip().startswith(("[", "{"))) and ("wp/v2" in lower or "rest_route" in lower or '"title"' in lower):
        return True, "wordpress_rest_json", 0.8, "active"
    if endpoint_type == "DRUPAL_JSON" and ("application/vnd.api+json" in content_type or "jsonapi" in lower or text.strip().startswith("{")):
        return True, "drupal_json", 0.75, "active"
    if endpoint_type == "RSS_ATOM" and any(token in lower for token in ["<rss", "<feed", "<channel"]):
        return True, "feed", 0.85, "active"
    if endpoint_type == "IIIF" and ("iiif" in lower or "presentation" in lower or '"@context"' in lower and '"items"' in lower):
        return True, "iiif_json", 0.8, "active"
    if endpoint_type == "CKAN_PUBLIC" and ("package_search" in lower or '"result"' in lower and '"success"' in lower):
        return True, "ckan_json", 0.75, "active"
    if endpoint_type == "ATOM_AtoM" and ("informationobject" in lower or "archival description" in lower or "atom" in lower):
        return True, "atom_browse", 0.7, "active"
    if "application/json" in content_type and text.strip().startswith(("{", "[")):
        return True, "generic_json", 0.55, "active"
    return False, "not_structured_metadata", 0.0, "rejected"


def route_rows(seeds: Path, registry: Path, expanded: Path) -> list[dict]:
    rows = load_yaml_rows(seeds) + load_yaml_rows(expanded) + load_yaml_rows(registry)
    forms = read_csv(ROOT / "data" / "interim" / "source_discovery" / "noauth_search_forms.csv")
    for form in forms:
        rows.append(
            {
                "route_id": form.get("route_id"),
                "source_id": form.get("route_id"),
                "source_name": form.get("source_name"),
                "state": form.get("state"),
                "source_tier": "B",
                "route_family": "structured_search_form",
                "official_url": form.get("search_url_template"),
                "evidence_or_discovery": "evidence_possible",
            }
        )
    deduped: dict[str, dict] = {}
    for row in rows:
        url = route_url(row)
        if url.startswith(("http://", "https://")):
            key = route_key(row) + "|" + base_url(url)
            deduped.setdefault(key, row)
    return list(deduped.values())


def insert_endpoint(conn: sqlite3.Connection, row: dict) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO noauth_endpoint_inventory (
            endpoint_id, route_id, source_id, source_name, source_tier, route_family, state,
            domain, base_url, endpoint_url, endpoint_type, noauth_verified, robots_allowed,
            login_required, api_key_required, paywall_required, terms_status, confidence,
            status, discovered_at, last_tested_at, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["endpoint_id"],
            row.get("route_id"),
            row.get("source_id"),
            row.get("source_name"),
            row.get("source_tier"),
            row.get("route_family"),
            row.get("state"),
            row.get("domain"),
            row.get("base_url"),
            row.get("endpoint_url"),
            row.get("endpoint_type"),
            row.get("noauth_verified", 0),
            row.get("robots_allowed", 0),
            row.get("login_required", 0),
            row.get("api_key_required", 0),
            row.get("paywall_required", 0),
            row.get("terms_status"),
            row.get("confidence", 0),
            row.get("status"),
            row.get("discovered_at"),
            row.get("last_tested_at"),
            row.get("notes"),
        ),
    )


def discover(db_path: Path, config_path: Path, seeds: Path, registry: Path, expanded: Path, out: Path, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    limits = config.get("endpoint_probe_limits", {})
    max_domains = min(int(limits.get("max_domains_per_run", 500)), 25)
    max_tests = min(int(limits.get("max_endpoint_tests_per_domain", 20)), 8)
    timeout = min(float(limits.get("timeout_seconds", 25)), 4.0)
    session = requests.Session()
    endpoints: list[dict] = []
    rejected: list[dict] = []
    seen_domains: set[str] = set()
    with sqlite3.connect(db_path) as conn:
        for route in route_rows(seeds, registry, expanded):
            disallowed, reason = disallowed_route(route)
            root = base_url(route_url(route))
            if not root:
                continue
            dom = domain(root)
            if dom in seen_domains:
                continue
            seen_domains.add(dom)
            if len(seen_domains) > max_domains:
                break
            if disallowed:
                rejected.append({"domain": dom, "route_id": route_key(route), "reason": reason})
                continue
            tests = endpoint_patterns(root)[:max_tests]
            # HTML front page can expose RSS/IIIF/JSON-LD hints without extra guessing.
            if execute and allowed_by_robots(root, USER_AGENT):
                try:
                    resp = session.get(root, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, timeout=(5, timeout), allow_redirects=True)
                    if resp.status_code == 200:
                        tests.extend(discover_embedded_structured_links(resp.text, root))
                except Exception:
                    pass
            for endpoint_type, endpoint_url in tests[:max_tests]:
                robots = allowed_by_robots(endpoint_url.replace("{query}", "ghost"), USER_AGENT)
                if not robots:
                    rejected.append({"domain": dom, "route_id": route_key(route), "endpoint_type": endpoint_type, "endpoint_url": endpoint_url, "reason": "robots_denied_or_unknown"})
                    continue
                ok = False
                note = "dry_run"
                confidence = 0.0
                status = "discovered"
                if execute:
                    try:
                        test_url = endpoint_url.replace("{query}", "ghost")
                        resp = session.get(test_url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, text/html;q=0.8"}, timeout=(5, timeout), allow_redirects=False)
                        ok, note, confidence, status = classify_response(endpoint_type, resp.status_code, resp.text or "", resp.headers.get("content-type", ""))
                    except Exception as exc:
                        note = f"error:{type(exc).__name__}"
                if ok or not execute:
                    route_states = route.get("states")
                    state = route.get("state") or (route_states[0] if isinstance(route_states, list) and route_states else "")
                    row = {
                        "endpoint_id": endpoint_id(route_key(route), endpoint_type, endpoint_url),
                        "route_id": route_key(route),
                        "source_id": route.get("source_id") or route_key(route),
                        "source_name": route.get("source_name") or route_key(route),
                        "source_tier": route.get("source_tier") or "B",
                        "route_family": route.get("route_family") or "structured_endpoint",
                        "state": state,
                        "domain": dom,
                        "base_url": root,
                        "endpoint_url": endpoint_url,
                        "endpoint_type": endpoint_type,
                        "noauth_verified": 1 if ok else 0,
                        "robots_allowed": 1,
                        "login_required": 0,
                        "api_key_required": 0,
                        "paywall_required": 0,
                        "terms_status": "robots_allowed",
                        "confidence": confidence,
                        "status": status,
                        "discovered_at": now_iso(),
                        "last_tested_at": now_iso() if execute else "",
                        "notes": note,
                    }
                    endpoints.append(row)
                    if execute:
                        insert_endpoint(conn, row)
                else:
                    rejected.append({"domain": dom, "route_id": route_key(route), "endpoint_type": endpoint_type, "endpoint_url": endpoint_url, "reason": note})
        if execute:
            conn.commit()
    out.parent.mkdir(parents=True, exist_ok=True)
    counts = Counter(row["endpoint_type"] for row in endpoints)
    rej_counts = Counter(row.get("reason") for row in rejected)
    endpoint_lines = [f"- `{key}`: {value}" for key, value in counts.most_common()] or ["- None"]
    rejection_lines = [f"- `{key}`: {value}" for key, value in rej_counts.most_common(12)] or ["- None"]
    lines = [
        "# Structured Endpoint Discovery Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Domains tested: `{min(len(seen_domains), max_domains)}`",
        f"- Endpoints discovered: `{len(endpoints)}`",
        f"- Endpoints rejected: `{len(rejected)}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "",
        "## Endpoints By Type",
        *endpoint_lines,
        "",
        "## Rejection Reasons",
        *rejection_lines,
        "",
        "## Next Command",
        "`make structured-endpoint-build-queries`",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"domains": min(len(seen_domains), max_domains), "endpoints": len(endpoints), "rejected": len(rejected)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--expanded-seeds", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(discover(Path(args.db), Path(args.config), Path(args.seeds), Path(args.registry), Path(args.expanded_seeds), Path(args.out), execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
