#!/usr/bin/env python3
"""Discover safe public GET search forms from no-auth official routes."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus, urlencode, urljoin, urlparse

import requests
import yaml
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.autoharvest_engine import classify_route_safety, is_api_url, load_autoharvest_config
from lib.noauth_web import same_domain

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]


FIELD_HINTS = {"q", "query", "search", "keywords", "keyword", "s", "search_api_fulltext"}
BAD_FIELD_HINTS = {"password", "email", "token", "captcha", "auth", "login"}
CMS_TEMPLATES = [
    "/?s={query}",
    "/search/node/{query}",
    "/search?search={query}",
    "/search?query={query}",
    "/search?queries_keywords_query={query}",
    "/items/browse?search={query}",
    "/index.php/informationobject/browse?topLod=0&query={query}",
    "/index.php/index.php/informationobject/browse?query={query}",
    "/search?q={query}",
    "/search?keyword={query}",
    "/search?keywords={query}",
    "/search?term={query}",
    "/catalogue/search?search={query}",
]

_ROBOTS_CACHE: dict[str, RobotFileParser | None] = {}


def quick_allowed_by_robots(url: str, user_agent: str, session: requests.Session, timeout: int = 10) -> bool:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    root = f"{parsed.scheme}://{parsed.netloc}"
    if root not in _ROBOTS_CACHE:
        parser = RobotFileParser()
        try:
            response = session.get(root + "/robots.txt", headers={"User-Agent": user_agent}, timeout=timeout)
            if response.status_code >= 400:
                _ROBOTS_CACHE[root] = None
            else:
                parser.parse(response.text.splitlines())
                _ROBOTS_CACHE[root] = parser
        except Exception:
            _ROBOTS_CACHE[root] = None
    parser = _ROBOTS_CACHE[root]
    return bool(parser and parser.can_fetch(user_agent, url))


def fetch_html_quick(url: str, user_agent: str, session: requests.Session, timeout: int = 20) -> str:
    if not quick_allowed_by_robots(url, user_agent, session):
        return ""
    response = session.get(url, headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"}, timeout=timeout)
    if response.status_code != 200:
        return ""
    ctype = response.headers.get("content-type", "").lower()
    if "text/html" not in ctype and "application/xhtml+xml" not in ctype:
        return ""
    return (response.text or "")[:2_000_000]


def load_seeds(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [row for row in data if isinstance(row, dict)]


def form_candidates(html: str, base_url: str) -> list[dict]:
    rows: list[dict] = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html or "", "html.parser")
        form_iter = []
        for form in soup.select("form"):
            inputs = form.select("input[name], textarea[name], select[name]")
            names = [(field.get("name") or "").strip() for field in inputs]
            types = [(field.get("type") or "").strip().lower() for field in inputs if field.name == "input"]
            form_iter.append(((form.get("method") or "get").strip().lower(), form.get("action") or base_url, names, types, form.get_text(" ", strip=True)))
    else:
        form_iter = []
        for match in re.finditer(r"<form\b([^>]*)>(.*?)</form>", html or "", flags=re.IGNORECASE | re.DOTALL):
            attrs, body = match.group(1), match.group(2)
            method_match = re.search(r"method=[\"']?([^\"'\s>]+)", attrs, flags=re.IGNORECASE)
            action_match = re.search(r"action=[\"']?([^\"'\s>]+)", attrs, flags=re.IGNORECASE)
            names = re.findall(r"name=[\"']([^\"']+)[\"']", body, flags=re.IGNORECASE)
            types = re.findall(r"type=[\"']([^\"']+)[\"']", body, flags=re.IGNORECASE)
            form_iter.append(((method_match.group(1) if method_match else "get").lower(), action_match.group(1) if action_match else base_url, names, types, re.sub(r"<[^>]+>", " ", body)))
    for method, action_raw, names, types, text in form_iter:
        if method != "get":
            continue
        hay = " ".join(names + types + [text]).lower()
        if any(bad in hay for bad in BAD_FIELD_HINTS):
            continue
        query_param = next((name for name in names if name.lower() in FIELD_HINTS), "")
        if not query_param:
            query_param = next((name for name in names if "search" in name.lower() or "query" in name.lower()), "")
        if not query_param:
            continue
        action = urljoin(base_url, action_raw or base_url)
        if not same_domain(base_url, action) or is_api_url(action):
            continue
        separator = "&" if "?" in action else "?"
        template = f"{action}{separator}{urlencode({query_param: '{query}'})}"
        rows.append(
            {
                "search_url_template": template,
                "method": "GET",
                "query_param": query_param,
                "confidence": 0.85 if "search" in hay else 0.7,
                "reason": "safe_get_search_form",
            }
        )
    return rows


def template_candidates(base_url: str) -> list[dict]:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return []
    root = f"{parsed.scheme}://{parsed.netloc}"
    rows: list[dict] = []
    seen: set[str] = set()
    for template in CMS_TEMPLATES:
        url = urljoin(root, template)
        if url in seen:
            continue
        seen.add(url)
        rows.append(
            {
                "search_url_template": url,
                "method": "GET",
                "query_param": "path_or_query",
                "confidence": 0.55,
                "reason": "cms_common_template",
            }
        )
    return rows


def test_search_template(template: str, query: str, config, session: requests.Session) -> dict:
    if not query:
        return {"tested": 0, "safe_to_probe": 0, "result_status": "not_tested", "result_hint": ""}
    test_url = template.replace("%7Bquery%7D", quote_plus(query)).replace("{query}", quote_plus(query))
    if not quick_allowed_by_robots(test_url, config.user_agent, session):
        return {"tested": 1, "safe_to_probe": 0, "result_status": "robots_blocked", "result_hint": ""}
    try:
        html = fetch_html_quick(test_url, config.user_agent, session)
    except Exception:
        return {"tested": 1, "safe_to_probe": 0, "result_status": "fetch_exception_or_timeout", "result_hint": ""}
    if not html:
        return {"tested": 1, "safe_to_probe": 0, "result_status": "empty_or_non_html", "result_hint": ""}
    lower = html.lower()
    has_term = query.lower() in lower
    has_item_link = any(token in lower for token in ["href=", ".pdf", "record", "item", "article", "newsletter", "journal"])
    return {"tested": 1, "safe_to_probe": int(has_term and has_item_link), "result_status": "ok", "result_hint": "term_and_item_links" if has_term and has_item_link else "weak_result"}


def discover(seeds_path: Path, out_path: Path, report_path: Path, execute: bool, test_query: str = "") -> list[dict]:
    seeds = load_seeds(seeds_path)
    config = load_autoharvest_config(ROOT / "config" / "autoharvest_gap_rescue.yml")
    session = requests.Session()
    rows: list[dict] = []
    test_rows: list[dict] = []
    rejected: dict[str, int] = {}
    for seed in seeds:
        ok, reasons = classify_route_safety(seed, config)
        url = str(seed.get("official_url") or "")
        if not ok or not url:
            for reason in reasons or ["missing_url"]:
                rejected[reason] = rejected.get(reason, 0) + 1
            continue
        robots = quick_allowed_by_robots(url, config.user_agent, session)
        if not robots:
            rejected["robots_disallowed_or_unknown"] = rejected.get("robots_disallowed_or_unknown", 0) + 1
            continue
        if not execute:
            continue
        try:
            html = fetch_html_quick(url, config.user_agent, session)
        except Exception:
            rejected["fetch_exception_or_timeout"] = rejected.get("fetch_exception_or_timeout", 0) + 1
            continue
        if not html:
            rejected["fetch_failed_or_non_html"] = rejected.get("fetch_failed_or_non_html", 0) + 1
            continue
        found_rows = form_candidates(html, url) + template_candidates(url)
        seen_templates: set[str] = set()
        for found in found_rows:
            template = found["search_url_template"]
            if template in seen_templates:
                continue
            seen_templates.add(template)
            test_url = template.replace("%7Bquery%7D", "ghost").replace("{query}", "ghost")
            safe_to_use = quick_allowed_by_robots(test_url, config.user_agent, session) and same_domain(url, test_url)
            test_result = test_search_template(template, test_query, config, session) if safe_to_use else {"tested": 0, "safe_to_probe": 0, "result_status": "robots_blocked", "result_hint": ""}
            rows.append(
                {
                    "route_id": seed.get("route_id") or seed.get("source_id"),
                    "source_name": seed.get("source_name"),
                    "state": seed.get("state"),
                    "search_url_template": template,
                    "method": found["method"],
                    "query_param": found["query_param"],
                    "confidence": found["confidence"],
                    "reason": found["reason"],
                    "robots_status": "allowed" if safe_to_use else "blocked_or_unknown",
                    "safe_to_use": 1 if safe_to_use else 0,
                    "safe_to_probe": test_result.get("safe_to_probe", 0),
                }
            )
            test_rows.append(
                {
                    "route_id": seed.get("route_id") or seed.get("source_id"),
                    "search_url_template": template,
                    "test_query": test_query,
                    **test_result,
                }
            )
    fields = ["route_id", "source_name", "state", "search_url_template", "method", "query_param", "confidence", "reason", "robots_status", "safe_to_use", "safe_to_probe"]
    write_csv(out_path, rows, fields)
    test_path = out_path.with_name(out_path.stem + "_test_results.csv")
    write_csv(test_path, test_rows, ["route_id", "search_url_template", "test_query", "tested", "safe_to_probe", "result_status", "result_hint"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# No-Auth Search Form Discovery",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Safe GET forms discovered: `{sum(1 for row in rows if str(row.get('safe_to_use')) == '1')}`",
        f"- Safe templates with positive first-page test: `{sum(1 for row in rows if str(row.get('safe_to_probe')) == '1')}`",
        "- POST/login/auth/captcha forms excluded: `yes`",
        "- External search APIs used: `no`",
        "- Forms submitted: `no`" if not test_query else f"- Optional test query supplied: `{test_query}`",
        "",
        "## Rejections",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(rejected.items())] or ["- None"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-query", default="")
    args = parser.parse_args()
    rows = discover(Path(args.seeds), Path(args.out), Path(args.report), execute=bool(args.execute and not args.dry_run), test_query=args.test_query)
    print(f"Wrote search forms: {args.out}")
    print({"forms": len(rows)})


if __name__ == "__main__":
    main()
