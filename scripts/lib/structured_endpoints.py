from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import requests

from collection_expansion_common import now_iso, stable_candidate_id
from lib.autoharvest_engine import make_duplicate_key
from lib.autoharvest_gap import classify_gap_candidate
from lib.noauth_web import RouteSafety, allowed_by_robots, extract_jsonld, extract_rss_links, fetch_html_safe

USER_AGENT = "AusFiguresStructuredEndpointBot/0.1 metadata-first no-login no-api"


@dataclass
class EndpointConfig:
    timeout_seconds: float = 25.0
    rate_limit_seconds: float = 2.5
    max_pages: int = 25
    max_records: int = 500


@dataclass
class EndpointRecord:
    item_url: str
    item_id: str = ""
    title: str = ""
    description: str = ""
    creator: str = ""
    publisher: str = ""
    date_text: str = ""
    coverage_start_year: int | None = None
    coverage_end_year: int | None = None
    subjects: list[str] = field(default_factory=list)
    place_text: str = ""
    format_text: str = ""
    rights_text: str = ""
    source_name: str = ""
    source_tier: str = ""
    endpoint_type: str = ""
    raw_metadata_json: str = "{}"

    def text_blob(self) -> str:
        return " ".join([self.title, self.description, self.date_text, " ".join(self.subjects), self.place_text, self.format_text])


def clean_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def first(value: Any) -> str:
    if isinstance(value, list):
        return str(value[0]) if value else ""
    if isinstance(value, dict):
        return clean_html(value.get("rendered") or value.get("@value") or json.dumps(value, sort_keys=True))
    return str(value or "")


def text_of(elem: ET.Element, names: list[str]) -> str:
    values: list[str] = []
    for child in elem.iter():
        tag = child.tag.split("}", 1)[-1].lower()
        if tag in names and child.text:
            values.append(child.text.strip())
    return "; ".join(dict.fromkeys(values))


def stable_endpoint_record_id(run_id: str, endpoint_id: str, item_url: str, title: str, date_text: str) -> str:
    return stable_candidate_id(endpoint_id, item_url, item_url, title, date_text, run_id).replace("cand_", "eprec_")


def is_disallowed_url(url: str) -> bool:
    lower = str(url or "").lower()
    return any(token in lower for token in ["api.trove.nla.gov.au", "googleapis.com", "api.bing.microsoft.com", "login", "captcha"])


class BaseEndpointClient:
    endpoint_type = "GENERIC"

    def __init__(self, config: EndpointConfig | None = None, session: requests.Session | None = None):
        self.config = config or EndpointConfig()
        self.session = session or requests.Session()
        self.headers = {"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, text/html;q=0.8"}

    def no_credentials(self) -> bool:
        return "Authorization" not in self.headers

    def get_text(self, url: str) -> tuple[int, str, str]:
        if is_disallowed_url(url):
            return 0, "", "disallowed_url"
        if not allowed_by_robots(url, USER_AGENT):
            return 0, "", "robots_denied_or_unknown"
        time.sleep(max(0.0, self.config.rate_limit_seconds))
        try:
            connect_timeout = min(3.0, self.config.timeout_seconds)
            response = self.session.get(url, headers=self.headers, timeout=(connect_timeout, self.config.timeout_seconds), allow_redirects=True)
        except Exception:
            return 0, "", "fetch_exception"
        return response.status_code, response.text or "", response.headers.get("content-type", "")

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        raise NotImplementedError


class OaiPmhClient(BaseEndpointClient):
    endpoint_type = "OAI_PMH"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        url = endpoint["endpoint_url"]
        query_url = url + ("&" if "?" in url else "?") + "verb=ListRecords&metadataPrefix=oai_dc"
        status, text, _ctype = self.get_text(query_url)
        if status != 200:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        rows: list[EndpointRecord] = []
        for record in root.iter():
            if record.tag.split("}", 1)[-1] != "record":
                continue
            title = text_of(record, ["title"])
            if not title:
                continue
            item_url = text_of(record, ["identifier"]).split("; ", 1)[0] or query_url
            rows.append(
                EndpointRecord(
                    item_url=item_url,
                    item_id=item_url,
                    title=title,
                    description=text_of(record, ["description"]),
                    creator=text_of(record, ["creator"]),
                    publisher=text_of(record, ["publisher"]),
                    date_text=text_of(record, ["date"]),
                    subjects=[s for s in text_of(record, ["subject"]).split("; ") if s],
                    format_text=text_of(record, ["format", "type"]),
                    rights_text=text_of(record, ["rights"]),
                    source_name=endpoint.get("source_name") or "",
                    source_tier=endpoint.get("source_tier") or "",
                    endpoint_type=self.endpoint_type,
                    raw_metadata_json=json.dumps({"xml_excerpt": ET.tostring(record, encoding="unicode")[:3000]}),
                )
            )
            if len(rows) >= self.config.max_records:
                break
        return rows


class WordpressRestClient(BaseEndpointClient):
    endpoint_type = "WORDPRESS_REST"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        q = quote_plus(query.get("query_text") or query.get("controlled_term") or "")
        url = endpoint["endpoint_url"].replace("{query}", q)
        status, text, _ctype = self.get_text(url)
        if status != 200:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
        rows = []
        for item in items[: self.config.max_records]:
            title = clean_html(first(item.get("title")))
            link = item.get("url") or item.get("link") or item.get("guid") or endpoint["endpoint_url"]
            rows.append(
                EndpointRecord(
                    item_url=first(link),
                    item_id=str(item.get("id") or first(link)),
                    title=title or clean_html(item.get("subtype") or item.get("type") or first(link)),
                    description=clean_html(first(item.get("excerpt") or item.get("description") or item.get("content"))),
                    date_text=first(item.get("date") or item.get("modified")),
                    subjects=[clean_html(first(item.get("type") or ""))],
                    source_name=endpoint.get("source_name") or "",
                    source_tier=endpoint.get("source_tier") or "",
                    endpoint_type=self.endpoint_type,
                    raw_metadata_json=json.dumps(item, sort_keys=True)[:5000],
                )
            )
        return rows


class OmekaClient(BaseEndpointClient):
    endpoint_type = "OMEKA_API"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        q = quote_plus(query.get("query_text") or query.get("controlled_term") or "")
        url = endpoint["endpoint_url"].replace("{query}", q)
        status, text, _ctype = self.get_text(url)
        if status != 200:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        items = data if isinstance(data, list) else data.get("items", []) if isinstance(data, dict) else []
        rows = []
        for item in items[: self.config.max_records]:
            title = first(item.get("title") or item.get("o:title") or item.get("dcterms:title"))
            desc = first(item.get("description") or item.get("dcterms:description"))
            date = first(item.get("date") or item.get("dcterms:date"))
            subjects = item.get("subjects") or item.get("dcterms:subject") or []
            link = first(item.get("url") or item.get("@id") or item.get("o:url") or endpoint["endpoint_url"])
            rows.append(EndpointRecord(link, first(item.get("id") or link), title, desc, date_text=date, subjects=[first(s) for s in subjects] if isinstance(subjects, list) else [first(subjects)], source_name=endpoint.get("source_name") or "", source_tier=endpoint.get("source_tier") or "", endpoint_type=self.endpoint_type, raw_metadata_json=json.dumps(item, sort_keys=True)[:5000]))
        return rows


class AtomAtoMClient(BaseEndpointClient):
    endpoint_type = "ATOM_AtoM"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        url = endpoint["endpoint_url"].replace("{query}", quote_plus(query.get("query_text") or ""))
        html = fetch_html_safe(url, RouteSafety(endpoint.get("endpoint_id") or "atom", self.config.rate_limit_seconds, self.config.timeout_seconds), self.session)
        if not html:
            return []
        rows = []
        for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S):
            title = clean_html(match.group(2))
            href = urljoin(url, match.group(1))
            if title and href.startswith(("http://", "https://")) and any(token in (title + href).lower() for token in ["ghost", "haunted", "yowie", "bunyip", "archive", "record", "item"]):
                rows.append(EndpointRecord(href, href, title, title, source_name=endpoint.get("source_name") or "", source_tier=endpoint.get("source_tier") or "", endpoint_type=self.endpoint_type, raw_metadata_json=json.dumps({"anchor": title})))
            if len(rows) >= self.config.max_records:
                break
        return rows


class DrupalJsonClient(WordpressRestClient):
    endpoint_type = "DRUPAL_JSON"


class CkanClient(WordpressRestClient):
    endpoint_type = "CKAN_PUBLIC"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        rows = super().fetch_records(endpoint, query)
        if rows:
            return rows
        status, text, _ctype = self.get_text(endpoint["endpoint_url"].replace("{query}", quote_plus(query.get("query_text") or "")))
        if status != 200:
            return []
        try:
            result = json.loads(text).get("result", {})
        except Exception:
            return []
        items = result.get("results", [])
        return [
            EndpointRecord(item.get("url") or endpoint["endpoint_url"], item.get("id") or item.get("name") or "", item.get("title") or item.get("name") or "", item.get("notes") or "", date_text=item.get("metadata_created") or "", subjects=item.get("tags") or [], source_name=endpoint.get("source_name") or "", source_tier=endpoint.get("source_tier") or "", endpoint_type=self.endpoint_type, raw_metadata_json=json.dumps(item, sort_keys=True)[:5000])
            for item in items[: self.config.max_records]
        ]


class RssAtomClient(BaseEndpointClient):
    endpoint_type = "RSS_ATOM"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        del query
        status, text, _ctype = self.get_text(endpoint["endpoint_url"])
        if status != 200:
            return []
        try:
            root = ET.fromstring(text)
        except ET.ParseError:
            return []
        rows = []
        for item in root.iter():
            tag = item.tag.split("}", 1)[-1].lower()
            if tag not in {"item", "entry"}:
                continue
            title = text_of(item, ["title"])
            link = text_of(item, ["link", "id"])
            desc = text_of(item, ["description", "summary", "content"])
            date = text_of(item, ["pubdate", "updated", "published", "date"])
            rows.append(EndpointRecord(link or endpoint["endpoint_url"], link or title, title, desc, date_text=date, source_name=endpoint.get("source_name") or "", source_tier=endpoint.get("source_tier") or "", endpoint_type=self.endpoint_type, raw_metadata_json=json.dumps({"xml_excerpt": ET.tostring(item, encoding="unicode")[:3000]})))
        return rows[: self.config.max_records]


class IiifClient(BaseEndpointClient):
    endpoint_type = "IIIF"

    def fetch_records(self, endpoint: dict[str, Any], query: dict[str, Any]) -> list[EndpointRecord]:
        del query
        status, text, _ctype = self.get_text(endpoint["endpoint_url"])
        if status != 200:
            return []
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return []
        items = data.get("items") or data.get("manifests") or [data]
        rows = []
        for item in items[: self.config.max_records]:
            label = first(item.get("label"))
            metadata = item.get("metadata") or []
            desc = " ".join(first(m.get("value")) for m in metadata if isinstance(m, dict))
            rows.append(EndpointRecord(first(item.get("id") or item.get("@id") or endpoint["endpoint_url"]), first(item.get("id") or item.get("@id") or label), label, desc, source_name=endpoint.get("source_name") or "", source_tier=endpoint.get("source_tier") or "", endpoint_type=self.endpoint_type, raw_metadata_json=json.dumps(item, sort_keys=True)[:5000]))
        return rows


class GenericJsonCatalogueClient(WordpressRestClient):
    endpoint_type = "PUBLIC_CATALOGUE_JSON"


class InternetArchiveMetadataClient(WordpressRestClient):
    endpoint_type = "INTERNET_ARCHIVE_METADATA"


class WikisourceAccessClient(AtomAtoMClient):
    endpoint_type = "WIKISOURCE_ACCESS"


class GutenbergAccessClient(AtomAtoMClient):
    endpoint_type = "GUTENBERG_ACCESS"


class OpenLibraryDiscoveryClient(WordpressRestClient):
    endpoint_type = "OPEN_LIBRARY_DISCOVERY"


CLIENTS = {
    "OAI_PMH": OaiPmhClient,
    "OMEKA_API": OmekaClient,
    "ATOM_AtoM": AtomAtoMClient,
    "WORDPRESS_REST": WordpressRestClient,
    "DRUPAL_JSON": DrupalJsonClient,
    "RSS_ATOM": RssAtomClient,
    "IIIF": IiifClient,
    "CKAN_PUBLIC": CkanClient,
    "PUBLIC_CATALOGUE_JSON": GenericJsonCatalogueClient,
    "PUBLIC_REPOSITORY_METADATA": GenericJsonCatalogueClient,
    "INTERNET_ARCHIVE_METADATA": InternetArchiveMetadataClient,
    "WIKISOURCE_ACCESS": WikisourceAccessClient,
    "GUTENBERG_ACCESS": GutenbergAccessClient,
    "OPEN_LIBRARY_DISCOVERY": OpenLibraryDiscoveryClient,
}


def client_for(endpoint_type: str, config: EndpointConfig | None = None, session: requests.Session | None = None) -> BaseEndpointClient:
    cls = CLIENTS.get(endpoint_type, GenericJsonCatalogueClient)
    return cls(config, session)


def discover_embedded_structured_links(html: str, base_url: str) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []
    for rss in extract_rss_links(html, base_url):
        links.append(("RSS_ATOM", rss))
    for data in extract_jsonld(html):
        for key in ["@id", "url", "mainEntityOfPage"]:
            value = data.get(key)
            if isinstance(value, str) and "iiif" in value.lower():
                links.append(("IIIF", urljoin(base_url, value)))
        if "iiif" in json.dumps(data).lower():
            links.append(("JSON_LD", base_url))
    return links


def normalized_to_candidate(record: EndpointRecord, endpoint: dict[str, Any], query: dict[str, Any], run_id: str) -> dict[str, Any]:
    return {
        "candidate_id": stable_candidate_id(endpoint.get("endpoint_id") or endpoint.get("route_id") or "", record.item_id or record.item_url, record.item_url, record.title, record.date_text, query.get("query_text")),
        "run_id": run_id,
        "page_id": "",
        "route_id": endpoint.get("route_id"),
        "source_id": endpoint.get("source_id") or endpoint.get("route_id"),
        "source_name": endpoint.get("source_name") or record.source_name,
        "source_tier": endpoint.get("source_tier") or record.source_tier,
        "route_family": endpoint.get("route_family"),
        "target_state": endpoint.get("state") or query.get("target_state"),
        "target_locality": query.get("locality") or endpoint.get("state") or "",
        "time_band": "",
        "term_family": "structured_endpoint",
        "term": query.get("controlled_term") or "",
        "title": record.title,
        "snippet": record.description or " ".join(record.subjects),
        "url": record.item_url,
        "stable_id": record.item_id or record.item_url,
        "date_published": record.date_text,
        "source_stated_place_text": record.place_text,
        "locality_hint": query.get("locality") or endpoint.get("state") or "",
        "mappability_hint": "low",
        "evidence_source_name": endpoint.get("source_name") or record.source_name,
        "evidence_source_url": record.item_url,
        "access_source_name": endpoint.get("source_name") or record.source_name,
        "access_source_url": endpoint.get("endpoint_url") or record.item_url,
        "original_source_name": "" if endpoint.get("source_tier") == "D" else endpoint.get("source_name") or record.source_name,
        "rights_status": record.rights_text or "metadata_only",
        "ethics_status": "not_sensitive",
        "metadata_only": 1,
        "candidate_score": 80,
        "duplicate_key": "",
        "duplicate_status": "unchecked",
        "noise_flags_json": "[]",
        "gate_status": "candidate",
        "gate_reasons_json": "[]",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "evidence_or_discovery": "evidence_only_if_original_source_identified" if endpoint.get("source_tier") == "D" else "evidence_possible",
        "item_format": "CATALOGUE_ITEM",
        "record_publication_date_text": record.date_text,
    }


def score_endpoint_record(record: EndpointRecord, endpoint: dict[str, Any], query: dict[str, Any], config_data: dict[str, Any], run_id: str, duplicate_status: str = "unchecked") -> dict[str, Any]:
    candidate = normalized_to_candidate(record, endpoint, query, run_id)
    candidate["duplicate_key"] = make_duplicate_key(candidate)
    candidate["duplicate_status"] = duplicate_status
    decision = classify_gap_candidate(
        candidate,
        {**endpoint, "evidence_or_discovery": candidate.get("evidence_or_discovery")},
        config_data,
        page_text=record.text_blob(),
        metadata={
            "record_publication_date": record.date_text,
            "date_is_record_publication": True,
            "title": record.title,
            "description": record.description,
            "item_format": "CATALOGUE_ITEM",
        },
    )
    if endpoint.get("source_tier") == "D" and not candidate.get("original_source_name"):
        decision.target_gap_eligible = False
        if "d_class_requires_original_source_decomposition" not in decision.reasons:
            decision.reasons.append("d_class_requires_original_source_decomposition")
        decision.reason = ";".join(decision.reasons)
    text = record.text_blob().lower()
    controlled_hits = [term for term in config_data.get("target_queries", {}).get("controlled_terms", []) if str(term).lower() in text]
    score = 0.0
    if decision.temporal.confidence >= 0.7:
        score += 35
    if controlled_hits or decision.term_hit_confidence >= 0.7:
        score += 35
    if record.item_url:
        score += 15
    if endpoint.get("source_tier") in {"A", "B", "C"}:
        score += 15
    return {
        "candidate": candidate,
        "decision": decision,
        "controlled_term_hits": controlled_hits,
        "target_gap_score": score,
        "status": "TARGET_GAP_EFFECTIVE" if decision.target_gap_eligible else "HIGH_QUALITY_NEAR_MISS" if decision.temporal.confidence >= 0.7 or decision.term_hit_confidence >= 0.7 else "HOLD",
    }
