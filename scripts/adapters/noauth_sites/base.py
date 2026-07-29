from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover
    BeautifulSoup = None  # type: ignore[assignment]


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    date_text: str = ""
    item_format: str = "CATALOGUE_ITEM"


@dataclass
class ItemMetadata:
    title: str
    url: str
    snippet: str = ""
    date_text: str = ""
    item_format: str = "CATALOGUE_ITEM"
    extra: dict = field(default_factory=dict)


@dataclass
class TermEvidence:
    term: str = ""
    confidence: float = 0.0


@dataclass
class PdfLink:
    url: str
    text: str = ""
    date_text: str = ""


class BaseNoAuthAdapter:
    name = "base"
    templates: list[str] = []

    def match(self, url: str, route: dict) -> bool:
        return False

    def build_search_urls(self, route: dict, query: str) -> list[str]:
        base = str(route.get("official_url") or "")
        root = f"{urlparse(base).scheme}://{urlparse(base).netloc}"
        return [urljoin(root, template.replace("{query}", quote_plus(query))) for template in self.templates]

    def parse_result_page(self, html: str, url: str, route: dict) -> list[SearchResult]:
        rows: list[SearchResult] = []
        if BeautifulSoup is not None:
            anchors = [(anchor.get("href", ""), anchor.get_text(" ", strip=True)) for anchor in BeautifulSoup(html or "", "html.parser").select("a[href]")[:80]]
        else:
            anchors = [(match.group(1), re.sub(r"<[^>]+>", " ", match.group(2))) for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", flags=re.IGNORECASE | re.DOTALL)]
        for href_raw, raw_text in anchors[:80]:
            text = re.sub(r"\s+", " ", raw_text).strip()
            href = urljoin(url, href_raw)
            if not text or not href.startswith(("http://", "https://")):
                continue
            if any(token in text.lower() for token in ["ghost", "haunted", "yowie", "bunyip", "newsletter", "journal", "bulletin", "catalogue", "archives"]):
                rows.append(SearchResult(text[:300], href, text[:600], item_format=guess_item_format(text, href)))
        return rows[:50]

    def parse_item_page(self, html: str, url: str, route: dict) -> ItemMetadata:
        title = ""
        snippet = ""
        if BeautifulSoup is not None:
            soup = BeautifulSoup(html or "", "html.parser")
            title = soup.title.get_text(" ", strip=True) if soup.title else ""
            snippet = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:1200]
        else:
            match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
            title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1))).strip() if match else ""
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()[:1200]
        return ItemMetadata(title or url, url, snippet, item_format=guess_item_format(title + " " + snippet, url))

    def extract_date(self, metadata: ItemMetadata, html: str):
        from lib.temporal_evidence import best_temporal_evidence
        from lib.autoharvest_gap import DEFAULT_TERMS

        return best_temporal_evidence(metadata.snippet, {"record_publication_date": metadata.date_text, "title": metadata.title, "description": metadata.snippet}, DEFAULT_TERMS, [])

    def extract_terms(self, metadata: ItemMetadata, html: str) -> TermEvidence:
        from lib.autoharvest_gap import DEFAULT_TERMS, term_hit

        hit, confidence, term = term_hit(" ".join([metadata.title, metadata.snippet]), DEFAULT_TERMS)
        return TermEvidence(term if hit else "", confidence)

    def extract_pdf_links(self, html: str, url: str) -> list[PdfLink]:
        rows: list[PdfLink] = []
        if BeautifulSoup is not None:
            anchors = [(anchor.get("href", ""), anchor.get_text(" ", strip=True)) for anchor in BeautifulSoup(html or "", "html.parser").select("a[href]")]
        else:
            anchors = [(match.group(1), re.sub(r"<[^>]+>", " ", match.group(2))) for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", html or "", flags=re.IGNORECASE | re.DOTALL)]
        for href_raw, raw_text in anchors:
            href = urljoin(url, href_raw)
            if ".pdf" not in href.lower().split("?", 1)[0]:
                continue
            text = re.sub(r"\s+", " ", raw_text).strip()
            rows.append(PdfLink(href, text, extract_date_text(" ".join([text, href]))))
        return rows[:100]


def extract_date_text(text: str) -> str:
    match = re.search(r"\b(19[2-7]\d|1930s|1940s|1950s|1960s|1970s)\b", text or "", re.I)
    return match.group(0) if match else ""


def guess_item_format(text: str, url: str) -> str:
    hay = f"{text} {url}".lower()
    if ".pdf" in hay:
        return "PDF_ISSUE"
    if any(token in hay for token in ["newsletter", "journal", "bulletin", "vol.", "volume", "issue"]):
        return "SERIAL_ISSUE_ITEM"
    if any(token in hay for token in ["radio", "broadcast", "television", "episode"]):
        return "BROADCAST_ITEM"
    if any(token in hay for token in ["finding aid", "archival description", "archives"]):
        return "ARCHIVE_FINDING_AID_ITEM"
    if any(token in hay for token in ["search", "browse", "results"]):
        return "SEARCH_RESULT_PAGE"
    if any(token in hay for token in ["catalogue", "record", "item", "object"]):
        return "CATALOGUE_ITEM"
    return "ARTICLE_PAGE"
