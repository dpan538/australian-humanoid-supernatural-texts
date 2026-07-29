from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal environments
    BeautifulSoup = None  # type: ignore[assignment]

USER_AGENT = "AusFiguresNoAuthResearchBot/0.1 metadata-first no-login no-api"


@dataclass
class RouteSafety:
    route_id: str
    rate_limit_seconds: float = 3.0
    timeout_seconds: float = 8.0
    max_pages_per_run: int = 30
    respect_robots: bool = True
    full_text_allowed: bool = False
    pdf_text_allowed: bool = False


_robot_cache: dict[str, RobotFileParser | None] = {}


def normalize_url(url: str) -> str:
    cleaned, _fragment = urldefrag(str(url or "").strip())
    return cleaned


def root_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def read_robots(url: str) -> RobotFileParser | None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    root = root_url(url)
    if root in _robot_cache:
        return _robot_cache[root]
    parser = RobotFileParser()
    robots_url = root + "/robots.txt"
    parser.set_url(robots_url)
    try:
        response = requests.get(
            robots_url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/plain,*/*;q=0.8"},
            timeout=(5, 8),
        )
        if response.status_code >= 400:
            _robot_cache[root] = None
            return None
        parser.parse((response.text or "").splitlines())
    except Exception:
        _robot_cache[root] = None
        return None
    _robot_cache[root] = parser
    return parser


def allowed_by_robots(url: str, user_agent: str = USER_AGENT) -> bool:
    parser = read_robots(url)
    if parser is None:
        return False
    return parser.can_fetch(user_agent, url)


def discover_sitemaps(base_url: str) -> list[str]:
    parser = read_robots(base_url)
    urls: list[str] = []
    if parser is not None:
        try:
            urls.extend(parser.site_maps() or [])
        except Exception:
            pass
    fallback = root_url(base_url) + "/sitemap.xml"
    if fallback not in urls:
        urls.append(fallback)
    return [normalize_url(url) for url in urls if url]


def fetch_html_safe(url: str, route: RouteSafety, session: requests.Session) -> str | None:
    if route.respect_robots and not allowed_by_robots(url):
        return None
    time.sleep(max(0.0, float(route.rate_limit_seconds or 0.0)))
    response = session.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=(5, max(3.0, float(route.timeout_seconds or 8.0))),
    )
    if response.status_code != 200:
        return None
    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        return None
    text = response.text or ""
    return text[:2_000_000]


def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html or "", "html.parser")
        for anchor in soup.select("a[href]"):
            text = re.sub(r"\s+", " ", anchor.get_text(" ", strip=True))
            href = normalize_url(urljoin(base_url, anchor.get("href", "")))
            if href.startswith(("http://", "https://")):
                out.append({"url": href, "text": text[:500]})
        return out
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", flags=re.IGNORECASE | re.DOTALL):
        href = normalize_url(urljoin(base_url, match.group(1)))
        text = re.sub(r"<[^>]+>", " ", match.group(2))
        text = re.sub(r"\s+", " ", text).strip()
        if href.startswith(("http://", "https://")):
            out.append({"url": href, "text": text[:500]})
    return out


def extract_jsonld(html: str) -> list[dict]:
    items: list[dict] = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html or "", "html.parser")
        raws = [tag.string or tag.get_text() for tag in soup.select('script[type="application/ld+json"]')]
    else:
        raws = re.findall(
            r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
            html or "",
            flags=re.IGNORECASE | re.DOTALL,
        )
    for raw in raws:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list):
            items.extend(item for item in data if isinstance(item, dict))
        elif isinstance(data, dict):
            graph = data.get("@graph")
            if isinstance(graph, list):
                items.extend(item for item in graph if isinstance(item, dict))
            items.append(data)
    return items


def extract_rss_links(html: str, base_url: str) -> list[str]:
    links: list[str] = []
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html or "", "html.parser")
        for tag in soup.select('link[type="application/rss+xml"], link[type="application/atom+xml"]'):
            href = tag.get("href")
            if href:
                links.append(normalize_url(urljoin(base_url, href)))
        return links
    for match in re.finditer(r"<link\b[^>]*href=[\"']([^\"']+)[\"'][^>]*type=[\"']application/(?:rss|atom)\+xml[\"'][^>]*>", html or "", flags=re.IGNORECASE):
        links.append(normalize_url(urljoin(base_url, match.group(1))))
    return links


def extract_pdf_links(html: str, base_url: str) -> list[dict[str, str]]:
    return [link for link in extract_links(html, base_url) if ".pdf" in link["url"].lower().split("?", 1)[0]]


def extract_years(text: str) -> list[int]:
    years: set[int] = set()
    for match in re.finditer(r"\b(18\d{2}|19\d{2}|20\d{2})\b", text or ""):
        year = int(match.group(1))
        if 1800 <= year <= 2030:
            years.add(year)
    return sorted(years)


def looks_relevant(text: str, terms: Iterable[str], localities: Iterable[str]) -> bool:
    haystack = (text or "").lower()
    term_hit = any(str(term).lower() in haystack for term in terms if term)
    locality_hit = any(str(locality).lower() in haystack for locality in localities if locality)
    context_hit = any(
        token in haystack
        for token in [
            "local history",
            "heritage",
            "archive",
            "archives",
            "museum",
            "collection",
            "catalogue",
            "newsletter",
            "journal",
            "oral history",
            "historical society",
            "history centre",
            "gaol",
            "hotel",
            "cemetery",
        ]
    )
    return (term_hit and (locality_hit or context_hit)) or (locality_hit and context_hit)


def same_domain(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc.lower() == urlparse(url_b).netloc.lower()
