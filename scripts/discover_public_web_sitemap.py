#!/usr/bin/env python3
"""Discover public web leads from site maps without accepting them.

The script is intentionally a lead generator. It reads public sitemap files,
keeps URLs that match person-form supernatural terms, fetches a small capped
sample, and writes a review CSV. Acceptance still happens through audited
seeded batches after source text, location role, and publicness are checked.
"""

from __future__ import annotations

import argparse
import csv
import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_TERMS = [
    "ghost",
    "haunt",
    "apparition",
    "spirit",
    "afterlife",
    "paranormal",
    "legend",
    "hairy-man",
    "wild-man",
    "mimih",
    "mimi",
    "wandjina",
    "quinkan",
    "nargun",
    "garkain",
    "mamu",
    "pangkarlangu",
]

STRONG_SUPERNATURAL_CONTENT_TERMS = [
    "ghost",
    "haunt",
    "apparition",
    "afterlife",
    "paranormal",
]

WEAK_CONTEXT_TERMS = [
    "spirit",
    "legend",
]

PERSON_FORM_CONTENT_TERMS = [
    "lady",
    "woman",
    "man",
    "figure",
    "convict",
    "inmate",
    "prisoner",
    "hairy man",
    "wild man",
    "mimih",
    "mimi",
    "wandjina",
    "quinkan",
    "nargun",
    "garkain",
    "mamu",
    "pangkarlangu",
]

ENTITY_CONTENT_TERMS = [
    "hairy man",
    "wild man",
    "mimih",
    "mimi",
    "wandjina",
    "quinkan",
    "nargun",
    "garkain",
    "mamu",
    "pangkarlangu",
]

CONTENT_TERMS = STRONG_SUPERNATURAL_CONTENT_TERMS + WEAK_CONTEXT_TERMS + PERSON_FORM_CONTENT_TERMS

DEFAULT_ROOTS = [
    "https://www.nationaltrust.org.au/sitemap.xml",
    "https://portarthur.org.au/sitemap.xml",
    "https://fremantleprison.com.au/sitemap.xml",
    "https://www.oldmelbournegaol.com.au/sitemap.xml",
    "https://www.adelaidegaol.sa.gov.au/sitemap.xml",
    "https://www.sovereignhill.com.au/sitemap.xml",
    "https://www.migrationmuseum.com.au/sitemap.xml",
    "https://www.history.sa.gov.au/sitemap.xml",
    "https://www.wamuseum.com.au/sitemap.xml",
    "https://visit.museum.wa.gov.au/sitemap.xml",
    "https://www.museum.wa.gov.au/sitemap.xml",
    "https://www.magnt.net.au/sitemap.xml",
    "https://libraries.tas.gov.au/sitemap.xml",
    "https://www.narrynah.com.au/sitemap.xml",
    "https://www.qvmag.tas.gov.au/sitemap.xml",
]

DISCOVERY_ONLY_TOURISM_ROOTS = [
    "https://www.visitvictoria.com/sitemap.xml",
    "https://www.westernaustralia.com/sitemap.xml",
    "https://southaustralia.com/sitemap.xml",
    "https://northernterritory.com/sitemap.xml",
    "https://www.discovertasmania.com.au/sitemap.xml",
    "https://visitcanberra.com.au/sitemap.xml",
]

USER_AGENT = (
    "AustralianHumanoidArchive/0.2 "
    "(public research; https://github.com/dpan538/australian-humanoid-supernatural-texts)"
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "svg", "noscript"}:
            self.skip_depth += 1
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "br", "section", "article"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "svg", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
        if tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "section", "article"}:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            self.parts.append(data)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def html_to_text(value: str) -> str:
    parser = VisibleTextParser()
    parser.feed(value)
    return clean_text(" ".join(parser.parts))


def extract_locs(value: str) -> list[str]:
    locs = [clean_text(match) for match in re.findall(r"<loc>\s*(.*?)\s*</loc>", value, flags=re.I | re.S)]
    cleaned = []
    for loc in locs:
        if loc.startswith("<![CDATA[") and loc.endswith("]]>"):
            loc = loc[9:-3]
        cleaned.append(clean_text(loc))
    return cleaned


def fetch(url: str, timeout: int) -> requests.Response:
    return requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html, text/xml, application/xml;q=0.9,*/*;q=0.2"},
        timeout=timeout,
        allow_redirects=True,
        verify=False,
    )


def crawl_sitemap(root: str, timeout: int, max_sitemaps: int) -> list[str]:
    seen: set[str] = set()
    queue = [root]
    pages: set[str] = set()
    while queue and len(seen) < max_sitemaps:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            response = fetch(url, timeout)
        except requests.RequestException:
            continue
        for loc in extract_locs(response.text):
            if not loc.startswith("http"):
                continue
            if loc.endswith(".xml") or "sitemap" in urlsplit(loc).path.lower():
                if loc not in seen:
                    queue.append(loc)
            else:
                pages.add(loc)
    return sorted(pages)


def title_from_html(value: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", value, flags=re.I | re.S)
    return clean_text(match.group(1)) if match else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", dest="roots", help="Sitemap root URL. Repeatable.")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "data" / "interim" / "public_web_sitemap_leads.csv"))
    parser.add_argument("--limit", type=int, default=120, help="Maximum URL-term candidates to fetch.")
    parser.add_argument("--max-sitemaps", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--term", action="append", dest="terms", help="URL term. Repeatable.")
    parser.add_argument("--per-root-limit", type=int, default=80, help="Maximum page URLs fetched from each sitemap root in content-scan mode.")
    parser.add_argument(
        "--content-scan",
        action="store_true",
        help="Fetch sitemap pages even when the URL does not contain a target term, then classify by visible text.",
    )
    parser.add_argument(
        "--include-tourism-discovery",
        action="store_true",
        help="Include official tourism sitemaps as discovery-only leads. These should not be accepted without stronger source backing.",
    )
    args = parser.parse_args()

    terms = [term.lower() for term in (args.terms or DEFAULT_TERMS)]
    term_pattern = re.compile("|".join(re.escape(term) for term in terms), flags=re.I)
    roots = args.roots or DEFAULT_ROOTS
    if args.include_tourism_discovery and not args.roots:
        roots = [*roots, *DISCOVERY_ONLY_TOURISM_ROOTS]

    pages: list[str] = []
    for root in roots:
        root_pages = crawl_sitemap(root, timeout=args.timeout, max_sitemaps=args.max_sitemaps)
        if args.content_scan:
            root_pages = root_pages[: args.per_root_limit]
        pages.extend(root_pages)

    unique_pages = list(dict.fromkeys(pages))
    url_candidates = unique_pages[: args.limit] if args.content_scan else sorted(url for url in unique_pages if term_pattern.search(url))[: args.limit]
    rows = []
    for url in url_candidates:
        try:
            response = fetch(url, args.timeout)
            text = html_to_text(response.text)
            title = title_from_html(response.text)
            text_lower = text.lower()
            hits = [term for term in CONTENT_TERMS if term.lower() in text_lower]
            supernatural_hits = [term for term in STRONG_SUPERNATURAL_CONTENT_TERMS if term.lower() in text_lower]
            weak_hits = [term for term in WEAK_CONTEXT_TERMS if term.lower() in text_lower]
            person_hits = [term for term in PERSON_FORM_CONTENT_TERMS if term.lower() in text_lower]
            entity_hits = [term for term in ENTITY_CONTENT_TERMS if term.lower() in text_lower]
            url_hit = bool(term_pattern.search(url))
            status = "review_candidate" if len(text) >= 240 and ((supernatural_hits and (person_hits or url_hit)) or entity_hits) else "weak_lead"
            rows.append(
                {
                    "generated_at": utc_now_iso(),
                    "url": response.url,
                    "http_status": response.status_code,
                    "title": title,
                    "text_length": len(text),
                    "matched_terms": ";".join(hits),
                    "supernatural_terms": ";".join(supernatural_hits),
                    "weak_context_terms": ";".join(weak_hits),
                    "person_form_terms": ";".join(person_hits),
                    "entity_terms": ";".join(entity_hits),
                    "lead_status": status,
                    "review_note": "Review for person-form narrative, location role, source publicness, and duplication before seeding. Tourism pages are discovery-only unless backed by an institutional, archival, newspaper, book, or community-controlled public source.",
                    "snippet": text[:420],
                }
            )
        except requests.RequestException as exc:
            rows.append(
                {
                    "generated_at": utc_now_iso(),
                    "url": url,
                    "http_status": "",
                    "title": "",
                    "text_length": 0,
                    "matched_terms": "",
                    "supernatural_terms": "",
                    "weak_context_terms": "",
                    "person_form_terms": "",
                    "entity_terms": "",
                    "lead_status": "fetch_failed",
                    "review_note": str(exc),
                    "snippet": "",
                }
            )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "generated_at",
        "url",
        "http_status",
        "title",
        "text_length",
        "matched_terms",
        "supernatural_terms",
        "weak_context_terms",
        "person_form_terms",
        "entity_terms",
        "lead_status",
        "review_note",
        "snippet",
    ]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} sitemap leads to {output}")


if __name__ == "__main__":
    main()
