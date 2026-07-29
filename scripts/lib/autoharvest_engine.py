from __future__ import annotations

import csv
import hashlib
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
import yaml

from collection_expansion_common import duplicate_key, now_iso, stable_candidate_id, table_exists, write_csv
from lib.noauth_web import (
    RouteSafety,
    allowed_by_robots,
    extract_jsonld,
    extract_links,
    extract_pdf_links,
    extract_rss_links,
    extract_years,
    fetch_html_safe,
    normalize_url,
    same_domain,
)


ROOT = Path(__file__).resolve().parents[2]
PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
TARGET_BANDS = {"1926_1939", "1940_1954", "1955_1964", "1965_1976"}
APPROVED_ROUTE_FAMILIES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "museum_heritage_page",
    "heritage_register",
    "public_history_site",
    "broadcast_catalogue",
    "historical_society",
    "public_collection",
}
API_HOST_TOKENS = {
    "api.trove.nla.gov.au",
    "www.googleapis.com",
    "googleapis.com",
    "api.bing.microsoft.com",
    "bing.microsoft.com",
}


@dataclass
class HarvestConfig:
    data: dict[str, Any]

    @property
    def target_effective_records(self) -> int:
        return int(self.data.get("target", {}).get("effective_new_records", 2000))

    @property
    def user_agent(self) -> str:
        return str(self.data.get("safety", {}).get("user_agent") or "AusFiguresNoAuthAutoharvestBot/0.1 metadata-first no-login no-api")

    @property
    def min_score(self) -> float:
        return float(self.data.get("candidate_gates", {}).get("min_candidate_score_for_provisional", 80))


@dataclass
class RouteSeed:
    raw: dict[str, Any]

    @property
    def route_id(self) -> str:
        return str(self.raw.get("route_id") or self.raw.get("source_id") or "")

    @property
    def url(self) -> str:
        return str(self.raw.get("official_url") or "")


@dataclass
class FrontierItem:
    row: dict[str, Any]


@dataclass
class PageFetchResult:
    url: str
    status: str
    http_status: int | None = None
    html: str | None = None
    content_type: str = ""
    error: str = ""
    backoff_seconds: int = 0


@dataclass
class ExtractedCandidate:
    data: dict[str, Any]


@dataclass
class CandidateScore:
    score: float
    reasons: list[str]


@dataclass
class ProvisionalDecision:
    accepted: bool
    reasons: list[str]


@dataclass
class RouteStats:
    route_id: str
    yield_score: float
    recommended_action: str


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_autoharvest_config(path: Path) -> HarvestConfig:
    return HarvestConfig(load_yaml(path) or {})


def load_noauth_seeds(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path) or []
    return [item for item in data if isinstance(item, dict)]


def truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part or "") for part in parts)
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def is_api_url(url: str) -> bool:
    host = urlparse(str(url or "")).netloc.lower()
    return any(token in host for token in API_HOST_TOKENS) or "/api/" in str(url or "").lower()


def classify_route_safety(route: dict[str, Any], config: HarvestConfig | dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    url = str(route.get("official_url") or route.get("url") or route.get("search_url") or "")
    if truthy(route.get("api_key_required")):
        reasons.append("api_key_required")
    if truthy(route.get("login_required")):
        reasons.append("login_required")
    if truthy(route.get("paywall_required")):
        reasons.append("paywall_required")
    if str(route.get("evidence_or_discovery")) in {"discovery_only", "manual_only_sensitive"}:
        reasons.append("discovery_or_sensitive_route")
    if str(route.get("collection_mode")) in {"manual_sensitive_review", "manual_search_task", "discovery_only"}:
        reasons.append("manual_or_discovery_mode")
    if is_api_url(url):
        reasons.append("api_url_rejected")
    if "trove" in url.lower() and "api" in url.lower():
        reasons.append("trove_api_rejected")
    return not reasons, reasons


def initialize_run(conn: sqlite3.Connection, run_id: str, run_name: str, target_effective_records: int, execute: bool) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO harvest_runs (
            run_id, run_name, status, started_at, target_effective_records, notes
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status=CASE WHEN harvest_runs.status='completed' THEN harvest_runs.status ELSE excluded.status END,
            target_effective_records=excluded.target_effective_records,
            notes=excluded.notes
        """,
        (run_id, run_name, "running" if execute else "dry_run", ts, target_effective_records, "no-auth autoharvest provisional growth layer"),
    )


def frontier_priority(route: dict[str, Any], config: HarvestConfig, state: str | None = None) -> float:
    priority = config.data.get("priority", {})
    score = 0.0
    state_key = state or route.get("state")
    score += float(priority.get("states", {}).get(state_key, 0))
    score += float(priority.get("route_families", {}).get(route.get("route_family"), 0))
    if route.get("source_tier") == "A":
        score += 25
    elif route.get("source_tier") in {"B", "C"}:
        score += 15
    if str(route.get("temporal_value") or "").endswith("1955_1976"):
        score += 30
    return score


def seed_frontier(conn: sqlite3.Connection, run_id: str, seeds: list[dict[str, Any]], config: HarvestConfig, dry_run: bool = False) -> dict[str, int]:
    queued = 0
    rejected = 0
    for route in seeds:
        ok, reasons = classify_route_safety(route, config)
        if not ok:
            rejected += 1
            continue
        url = str(route.get("official_url") or "")
        if not url:
            rejected += 1
            continue
        route_id = str(route.get("route_id") or route.get("source_id"))
        item_id = stable_id("frontier_", run_id, route_id, url)
        state = str(route.get("state") or "")
        if dry_run:
            queued += 1
            continue
        before = conn.total_changes
        conn.execute(
            """
            INSERT INTO harvest_frontier (
                frontier_id, run_id, route_id, source_id, source_name, source_tier,
                route_family, state, url, url_type, parent_url, depth, priority_score,
                status, discovered_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
            ON CONFLICT(frontier_id) DO NOTHING
            """,
            (
                item_id,
                run_id,
                route_id,
                route.get("source_id") or route_id,
                route.get("source_name"),
                route.get("source_tier"),
                route.get("route_family"),
                state,
                url,
                "seed",
                "",
                0,
                frontier_priority(route, config, state),
                now_iso(),
                "seeded no-auth route",
            ),
        )
        queued += 1
    return {"queued": queued, "rejected": rejected}


def next_frontier_item(conn: sqlite3.Connection, run_id: str) -> dict[str, Any] | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        """
        SELECT * FROM harvest_frontier
        WHERE run_id=? AND status='queued'
        ORDER BY priority_score DESC, discovered_at ASC
        LIMIT 1
        """,
        (run_id,),
    ).fetchone()
    return dict(row) if row else None


def fetch_page_safe(url: str, route: dict[str, Any], config: HarvestConfig, session: requests.Session | None = None) -> PageFetchResult:
    if is_api_url(url):
        return PageFetchResult(url=url, status="blocked_policy", error="api_url_rejected")
    if not allowed_by_robots(url, config.user_agent):
        return PageFetchResult(url=url, status="robots_blocked", error="robots_disallowed_or_unknown")
    session = session or requests.Session()
    safety = RouteSafety(
        route_id=str(route.get("route_id") or ""),
        rate_limit_seconds=float(route.get("rate_limit_seconds") or config.data.get("safety", {}).get("rate_limit_seconds_default", 3.0)),
        max_pages_per_run=int(route.get("max_pages_per_run") or config.data.get("safety", {}).get("max_pages_per_route_per_loop", 50)),
        respect_robots=True,
    )
    try:
        html = fetch_html_safe(url, safety, session)
    except requests.HTTPError as exc:
        status = getattr(exc.response, "status_code", None)
        if status == 429:
            return PageFetchResult(url=url, status="backoff", http_status=429, error=str(exc), backoff_seconds=int(config.data["safety"]["backoff_on_429_seconds"]))
        if status == 403:
            return PageFetchResult(url=url, status="paused", http_status=403, error=str(exc), backoff_seconds=int(config.data["safety"]["backoff_on_403_seconds"]))
        return PageFetchResult(url=url, status="error", http_status=status, error=str(exc))
    except Exception as exc:
        return PageFetchResult(url=url, status="error", error=str(exc))
    if not html:
        return PageFetchResult(url=url, status="non_html_or_empty")
    return PageFetchResult(url=url, status="fetched", http_status=200, html=html, content_type="text/html")


def title_from_html(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1))).strip()


def text_sample(html: str, limit: int = 1500) -> str:
    text = re.sub(r"<(script|style|nav|footer)\b.*?</\1>", " ", html or "", flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def extract_page_metadata(html: str, url: str) -> dict[str, Any]:
    links = extract_links(html, url)
    return {
        "title": title_from_html(html),
        "text_sample": text_sample(html),
        "links": links,
        "pdf_links": extract_pdf_links(html, url),
        "rss_links": extract_rss_links(html, url),
        "jsonld": extract_jsonld(html),
    }


def time_band_for_year(year: int | None) -> str:
    if year is None:
        return ""
    if 1926 <= year <= 1939:
        return "1926_1939"
    if 1940 <= year <= 1954:
        return "1940_1954"
    if 1955 <= year <= 1964:
        return "1955_1964"
    if 1965 <= year <= 1976:
        return "1965_1976"
    return ""


def extract_candidates_from_page(page: dict[str, Any], route: dict[str, Any], run_id: str, page_id: str = "") -> list[dict[str, Any]]:
    html = page.get("html") or ""
    url = page.get("url") or route.get("url") or route.get("official_url") or ""
    meta = extract_page_metadata(html, str(url))
    base_text = " ".join([meta["title"], meta["text_sample"], str(url)])
    years = extract_years(base_text)
    year = next((value for value in years if 1926 <= value <= 1976), years[0] if years else None)
    candidates: list[dict[str, Any]] = []
    for data in meta["jsonld"]:
        title = data.get("name") or data.get("headline") or data.get("title")
        item_url = normalize_url(str(data.get("url") or url))
        if title:
            candidates.append(candidate_dict(run_id, page_id, route, str(title), str(data.get("description") or meta["text_sample"]), item_url, year))
    for link in meta["links"]:
        combined = " ".join([link.get("text", ""), link.get("url", ""), meta["text_sample"]])
        if relevant_context(combined):
            link_years = extract_years(combined)
            link_year = next((value for value in link_years if 1926 <= value <= 1976), year)
            candidates.append(candidate_dict(run_id, page_id, route, link.get("text") or meta["title"] or "Open record candidate", meta["text_sample"], link["url"], link_year))
    if not candidates and relevant_context(base_text):
        candidates.append(candidate_dict(run_id, page_id, route, meta["title"] or "Open record candidate", meta["text_sample"], str(url), year))
    return candidates


def relevant_context(text: str) -> bool:
    hay = (text or "").lower()
    return any(term in hay for term in ["yowie", "ghost", "apparition", "haunted", "bunyip", "local history", "heritage", "archive", "museum", "historical society", "collection"])


def candidate_dict(run_id: str, page_id: str, route: dict[str, Any], title: str, snippet: str, url: str, year: int | None) -> dict[str, Any]:
    ts = now_iso()
    source_id = str(route.get("source_id") or route.get("route_id") or "")
    cand_id = stable_candidate_id(source_id, url, url, title, str(year or ""), snippet[:80])
    state = str(route.get("state") or "")
    state = "" if state == "NATIONAL" else state
    dup = make_duplicate_key({"title": title, "source_name": route.get("source_name"), "date_published": str(year or ""), "url": url, "stable_id": url})
    return {
        "candidate_id": cand_id,
        "run_id": run_id,
        "page_id": page_id,
        "route_id": route.get("route_id") or route.get("source_id"),
        "source_id": source_id,
        "source_name": route.get("source_name"),
        "source_tier": route.get("source_tier"),
        "route_family": route.get("route_family"),
        "target_state": state,
        "target_locality": "",
        "time_band": time_band_for_year(year),
        "term_family": "",
        "term": "",
        "title": title[:500],
        "snippet": snippet[:1000],
        "url": normalize_url(url),
        "stable_id": normalize_url(url),
        "date_published": str(year or ""),
        "inferred_year": year,
        "source_stated_place_text": "",
        "locality_hint": "",
        "mappability_hint": "low",
        "evidence_source_name": route.get("source_name"),
        "evidence_source_url": normalize_url(url),
        "access_source_name": route.get("source_name"),
        "access_source_url": route.get("official_url") or url,
        "original_source_name": "",
        "rights_status": "metadata_only",
        "ethics_status": "not_sensitive",
        "metadata_only": 1,
        "candidate_score": 0,
        "duplicate_key": dup,
        "duplicate_status": "unchecked",
        "noise_flags_json": "[]",
        "gate_status": "candidate",
        "gate_reasons_json": "[]",
        "created_at": ts,
        "updated_at": ts,
        "evidence_or_discovery": route.get("evidence_or_discovery", "evidence_possible"),
    }


def classify_noise(text: str, config: HarvestConfig | dict[str, Any]) -> list[str]:
    data = config.data if isinstance(config, HarvestConfig) else config
    noise = data.get("noise_terms", {})
    hay = (text or "").lower()
    flags: list[str] = []
    if any(term.lower() in hay for term in noise.get("tourism", [])):
        flags.append("tourism_marketing")
    if any(term.lower() in hay for term in noise.get("context_noise", [])):
        flags.append("context_noise")
    return flags


def classify_sensitive(candidate: dict[str, Any], route: dict[str, Any]) -> str:
    text = " ".join([str(candidate.get("title") or ""), str(candidate.get("snippet") or ""), str(route.get("notes") or "")]).lower()
    if route.get("evidence_or_discovery") == "manual_only_sensitive" or route.get("collection_mode") == "manual_sensitive_review":
        return "manual_only"
    if any(term in text for term in ["secret/sacred", "restricted", "sensitive", "aiatsis", "austlang"]):
        return "sensitive"
    return "not_sensitive"


def score_candidate(candidate: dict[str, Any], route: dict[str, Any], config: HarvestConfig | dict[str, Any]) -> tuple[float, list[str]]:
    cfg = config if isinstance(config, HarvestConfig) else HarvestConfig(config)
    score = 0.0
    reasons: list[str] = []
    if route.get("source_tier") in {"A", "B", "C"} or candidate.get("source_tier") in {"A", "B", "C"}:
        score += 25
        reasons.append("tier_abc")
    if candidate.get("target_state") in PRIORITY_STATES or route.get("state") in PRIORITY_STATES:
        score += 25
        reasons.append("priority_state")
    year = candidate.get("inferred_year")
    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None
    if year and 1926 <= year <= 1976:
        score += 25
        reasons.append("target_year")
    elif candidate.get("time_band") in TARGET_BANDS:
        score += 15
        reasons.append("target_time_band")
    if (route.get("route_family") or candidate.get("route_family")) in APPROVED_ROUTE_FAMILIES:
        score += 20
        reasons.append("preferred_route_family")
    text = " ".join([str(candidate.get("title") or ""), str(candidate.get("snippet") or ""), str(candidate.get("url") or "")]).lower()
    terms = candidate.get("terms") or [candidate.get("term"), "yowie", "ghost", "apparition", "haunted", "bunyip"]
    if any(str(term).lower() in text for term in terms if term):
        score += 15
        reasons.append("term_hit")
    if candidate.get("source_stated_place_text") or candidate.get("locality_hint") or candidate.get("target_locality"):
        score += 10
        reasons.append("place_hint")
    if candidate.get("evidence_source_url"):
        score += 10
        reasons.append("evidence_url")
    noise_flags = classify_noise(text, cfg)
    if noise_flags:
        score -= 50
        reasons.append("noise:" + ",".join(noise_flags))
    ethics = candidate.get("ethics_status") or classify_sensitive(candidate, route)
    if ethics in {"sensitive", "manual_only", "restricted"}:
        score -= 100
        reasons.append("sensitive_or_restricted")
    if route.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"} or candidate.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"}:
        score -= 100
        reasons.append("invalid_evidence_route")
    return max(0.0, min(score, 100.0)), reasons


def make_duplicate_key(candidate: dict[str, Any]) -> str:
    return duplicate_key(candidate.get("title"), candidate.get("source_name"), candidate.get("date_published"), candidate.get("url"), candidate.get("stable_id"))


def check_duplicate_against_existing(conn: sqlite3.Connection, candidate: dict[str, Any]) -> str:
    key = candidate.get("duplicate_key") or make_duplicate_key(candidate)
    checks = []
    if table_exists(conn, "harvest_candidates"):
        checks.append(("harvest_candidates", "duplicate_key"))
    if table_exists(conn, "provisional_records"):
        checks.append(("provisional_records", "duplicate_key"))
    if table_exists(conn, "collection_candidates"):
        checks.append(("collection_candidates", "duplicate_key"))
    for table, column in checks:
        row = conn.execute(f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (key,)).fetchone()
        if row:
            return "duplicate"
    if table_exists(conn, "records") and candidate.get("title"):
        title = str(candidate.get("title"))
        row = conn.execute("SELECT 1 FROM records WHERE lower(title)=lower(?) LIMIT 1", (title,)).fetchone()
        if row:
            return "probably_duplicate"
    return "unique"


def provisional_gate(candidate: dict[str, Any], score: float, reasons: list[str], config: HarvestConfig | dict[str, Any]) -> tuple[bool, list[str]]:
    cfg = config if isinstance(config, HarvestConfig) else HarvestConfig(config)
    fail: list[str] = []
    if score < cfg.min_score:
        fail.append("score_below_threshold")
    for field in ["url", "title", "evidence_source_name", "evidence_source_url", "source_tier"]:
        if not candidate.get(field):
            fail.append(f"missing_{field}")
    if candidate.get("source_tier") not in {"A", "B", "C"}:
        fail.append("source_tier_not_abc")
    if candidate.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"}:
        fail.append("discovery_or_sensitive_route")
    if candidate.get("duplicate_status") not in {"unique", "probably_unique", "unique_or_probably_unique"}:
        fail.append("duplicate")
    if candidate.get("ethics_status") in {"sensitive", "restricted", "manual_only"}:
        fail.append("sensitive_or_restricted")
    if any(reason.startswith("noise:") for reason in reasons):
        fail.append("context_noise")
    if candidate.get("rights_status") in {"restricted", "paywalled", "login_required"}:
        fail.append("restricted_rights")
    return len(fail) == 0, fail


def growth_weight(candidate: dict[str, Any]) -> float:
    weight = 1.0
    if candidate.get("target_state") in PRIORITY_STATES:
        weight += 0.5
    year = candidate.get("inferred_year")
    try:
        year = int(year) if year else None
    except (TypeError, ValueError):
        year = None
    if year and 1926 <= year <= 1976:
        weight += 0.5
    if candidate.get("route_family") in {"local_history_serial", "council_local_studies"}:
        weight += 0.25
    if candidate.get("source_tier") == "A":
        weight += 0.25
    return min(2.0, weight)


HARVEST_CANDIDATE_FIELDS = [
    "candidate_id", "run_id", "page_id", "route_id", "source_id", "source_name", "source_tier", "route_family",
    "target_state", "target_locality", "time_band", "term_family", "term", "title", "snippet", "url", "stable_id",
    "date_published", "inferred_year", "source_stated_place_text", "locality_hint", "mappability_hint",
    "evidence_source_name", "evidence_source_url", "access_source_name", "access_source_url", "original_source_name",
    "rights_status", "ethics_status", "metadata_only", "candidate_score", "duplicate_key", "duplicate_status",
    "noise_flags_json", "gate_status", "gate_reasons_json", "created_at", "updated_at",
]


def insert_harvest_candidate(conn: sqlite3.Connection, candidate: dict[str, Any]) -> None:
    placeholders = ", ".join(["?"] * len(HARVEST_CANDIDATE_FIELDS))
    updates = ", ".join(f"{field}=excluded.{field}" for field in HARVEST_CANDIDATE_FIELDS if field != "candidate_id")
    conn.execute(
        f"""
        INSERT INTO harvest_candidates ({", ".join(HARVEST_CANDIDATE_FIELDS)})
        VALUES ({placeholders})
        ON CONFLICT(candidate_id) DO UPDATE SET {updates}
        """,
        tuple(candidate.get(field) for field in HARVEST_CANDIDATE_FIELDS),
    )


def insert_provisional_record(conn: sqlite3.Connection, candidate: dict[str, Any], score: float) -> bool:
    ts = now_iso()
    provisional_id = stable_id("prov_", candidate.get("candidate_id"), candidate.get("url"))
    try:
        conn.execute(
            """
            INSERT INTO provisional_records (
                provisional_record_id, run_id, candidate_id, title, summary, date_published, inferred_year,
                time_band, target_state, source_stated_place_text, source_name, source_url,
                evidence_source_name, evidence_source_url, access_source_name, access_source_url,
                original_source_name, source_tier, route_family, metadata_only, rights_status, ethics_status,
                provisional_score, duplicate_key, growth_weight, promotion_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'not_reviewed', ?, ?)
            """,
            (
                provisional_id,
                candidate.get("run_id"),
                candidate.get("candidate_id"),
                candidate.get("title"),
                candidate.get("snippet"),
                candidate.get("date_published"),
                candidate.get("inferred_year"),
                candidate.get("time_band"),
                candidate.get("target_state"),
                candidate.get("source_stated_place_text") or candidate.get("locality_hint") or "",
                candidate.get("source_name"),
                candidate.get("url"),
                candidate.get("evidence_source_name"),
                candidate.get("evidence_source_url"),
                candidate.get("access_source_name"),
                candidate.get("access_source_url"),
                candidate.get("original_source_name"),
                candidate.get("source_tier"),
                candidate.get("route_family"),
                candidate.get("metadata_only", 1),
                candidate.get("rights_status"),
                candidate.get("ethics_status"),
                score,
                candidate.get("duplicate_key"),
                growth_weight(candidate),
                ts,
                ts,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def extract_route_candidates(html: str, page_url: str, route: dict[str, Any], run_id: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for link in extract_links(html, page_url):
        text = link.get("text") or ""
        guess = guess_route_family(text, link["url"])
        if not guess:
            continue
        confidence = 0.85 if same_domain(page_url, link["url"]) else 0.65
        out.append(
            {
                "discovered_route_id": stable_id("droute_", run_id, route.get("route_id"), link["url"]),
                "run_id": run_id,
                "discovered_from_route_id": route.get("route_id"),
                "discovered_from_url": page_url,
                "candidate_source_name": text[:200],
                "candidate_url": link["url"],
                "state_guess": route.get("state"),
                "route_family_guess": guess,
                "source_tier_guess": "B" if same_domain(page_url, link["url"]) else "C",
                "collection_mode_guess": "static_html_metadata",
                "evidence_or_discovery_guess": "evidence_possible",
                "confidence": confidence,
                "status": "route_candidate" if confidence < 0.75 else "frontier_eligible",
                "reason_discovered": "trusted_directory_or_history_link",
                "robots_status": "not_checked",
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
        )
    return out


def guess_route_family(text: str, url: str) -> str:
    hay = f"{text} {url}".lower()
    if any(term in hay for term in ["library catalogue", "collection search", "state library"]):
        return "state_library_catalogue"
    if any(term in hay for term in ["archives", "recordsearch", "finding aid", "archive"]):
        return "state_archive_catalogue"
    if any(term in hay for term in ["journal", "newsletter", "historical society", "history journal"]):
        return "local_history_serial"
    if any(term in hay for term in ["local studies", "history centre", "city archives", "council archives"]):
        return "council_local_studies"
    if any(term in hay for term in ["museum", "collection", "exhibition"]):
        return "museum_heritage_page"
    if any(term in hay for term in ["heritage register", "listed place", "classified place"]):
        return "heritage_register"
    if any(term in hay for term in ["history", "historic site", "gaol", "prison", "cemetery", "homestead"]):
        return "public_history_site"
    return ""


def insert_discovered_routes(conn: sqlite3.Connection, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    fields = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(fields))
    inserted = 0
    for row in rows:
        conn.execute(
            f"INSERT OR IGNORE INTO harvest_discovered_routes ({', '.join(fields)}) VALUES ({placeholders})",
            tuple(row.get(field) for field in fields),
        )
        inserted += 1
    return inserted


def promote_discovered_routes_to_frontier(conn: sqlite3.Connection, run_id: str, config: HarvestConfig) -> int:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT * FROM harvest_discovered_routes
        WHERE run_id=? AND status='frontier_eligible'
          AND confidence >= 0.75
          AND source_tier_guess IN ('A','B','C')
          AND route_family_guess IN (
            'state_library_catalogue','state_archive_catalogue','local_history_serial',
            'council_local_studies','museum_heritage_page','heritage_register',
            'public_history_site','broadcast_catalogue','historical_society','public_collection'
          )
        """,
        (run_id,),
    ).fetchall()
    promoted = 0
    for row in rows:
        url = str(row["candidate_url"] or "")
        if is_api_url(url):
            continue
        route = {
            "route_id": row["discovered_route_id"],
            "source_id": row["discovered_route_id"],
            "source_name": row["candidate_source_name"],
            "source_tier": row["source_tier_guess"],
            "route_family": row["route_family_guess"],
            "state": row["state_guess"],
            "official_url": url,
            "evidence_or_discovery": row["evidence_or_discovery_guess"],
        }
        ok, _reasons = classify_route_safety(route, config)
        if not ok:
            continue
        frontier_id = stable_id("frontier_", run_id, row["discovered_route_id"], url)
        before = conn.total_changes
        conn.execute(
            """
            INSERT INTO harvest_frontier (
                frontier_id, run_id, route_id, source_id, source_name, source_tier,
                route_family, state, url, url_type, parent_url, depth, priority_score,
                status, discovered_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered_route', ?, 1, ?, 'queued', ?, ?)
            ON CONFLICT(frontier_id) DO NOTHING
            """,
            (
                frontier_id,
                run_id,
                row["discovered_route_id"],
                row["discovered_route_id"],
                row["candidate_source_name"],
                row["source_tier_guess"],
                row["route_family_guess"],
                row["state_guess"],
                url,
                row["discovered_from_url"],
                frontier_priority(route, config, row["state_guess"]),
                now_iso(),
                "promoted from high-confidence discovered route",
            ),
        )
        if conn.total_changes > before:
            promoted += 1
    return promoted


def update_route_stats(conn: sqlite3.Connection, run_id: str, route: dict[str, Any], pages: int = 0, candidates: int = 0, provisional: int = 0, duplicates: int = 0, noise: int = 0, robots_blocked: int = 0, errors: int = 0) -> None:
    ts = now_iso()
    route_id = str(route.get("route_id") or route.get("source_id") or "")
    current = conn.execute("SELECT * FROM harvest_route_stats WHERE run_id=? AND route_id=?", (run_id, route_id)).fetchone()
    if current is None:
        conn.execute(
            """
            INSERT INTO harvest_route_stats (
                run_id, route_id, source_name, state, route_family, pages_fetched, candidates_seen,
                provisional_records_added, duplicates, noise, robots_blocked, errors, yield_score,
                recommended_action, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                route_id,
                route.get("source_name"),
                route.get("state"),
                route.get("route_family"),
                pages,
                candidates,
                provisional,
                duplicates,
                noise,
                robots_blocked,
                errors,
                provisional * 5 - noise * 2 - duplicates,
                "EXPAND_NOAUTH_ROUTE" if provisional else "RETRY_WITH_BETTER_QUERY",
                ts,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE harvest_route_stats
            SET pages_fetched=pages_fetched+?, candidates_seen=candidates_seen+?,
                provisional_records_added=provisional_records_added+?, duplicates=duplicates+?,
                noise=noise+?, robots_blocked=robots_blocked+?, errors=errors+?,
                yield_score=yield_score+?, updated_at=?
            WHERE run_id=? AND route_id=?
            """,
            (pages, candidates, provisional, duplicates, noise, robots_blocked, errors, provisional * 5 - noise * 2 - duplicates, ts, run_id, route_id),
        )


def effective_growth(conn: sqlite3.Connection, run_id: str) -> tuple[int, float]:
    row = conn.execute("SELECT COUNT(*), COALESCE(SUM(growth_weight), 0) FROM provisional_records WHERE run_id=?", (run_id,)).fetchone()
    return int(row[0] or 0), float(row[1] or 0.0)


def checkpoint_run(conn: sqlite3.Connection, run_id: str, config: HarvestConfig, report_path: Path | None = None) -> Path:
    raw, weighted = effective_growth(conn, run_id)
    out_dir = Path(config.data.get("outputs", {}).get("checkpoint_dir", "data/autoharvest/checkpoints"))
    out_dir.mkdir(parents=True, exist_ok=True)
    path = report_path or out_dir / f"{run_id}_{int(time.time())}_checkpoint.json"
    payload = {"run_id": run_id, "raw_provisional_records": raw, "weighted_effective_growth": weighted, "generated": now_iso()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    conn.execute("UPDATE harvest_runs SET last_checkpoint_path=?, effective_records_added=? WHERE run_id=?", (str(path), int(weighted), run_id))
    return path


def should_stop(conn: sqlite3.Connection, run_id: str, target_effective_records: int, started_at: float, max_runtime_hours: float) -> tuple[bool, str]:
    _raw, weighted = effective_growth(conn, run_id)
    if weighted >= target_effective_records:
        return True, "target_reached"
    if (time.time() - started_at) / 3600 >= max_runtime_hours:
        return True, "max_runtime_hours_reached"
    queued = conn.execute("SELECT COUNT(*) FROM harvest_frontier WHERE run_id=? AND status='queued'", (run_id,)).fetchone()[0]
    if queued == 0:
        return True, "frontier_exhausted"
    return False, ""


def write_run_report(conn: sqlite3.Connection, run_id: str, config: HarvestConfig, out_path: Path, stop_reason: str = "") -> dict[str, Any]:
    raw, weighted = effective_growth(conn, run_id)
    pages = conn.execute("SELECT COUNT(*) FROM harvest_pages WHERE run_id=?", (run_id,)).fetchone()[0]
    candidates = conn.execute("SELECT COUNT(*) FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchone()[0]
    routes = conn.execute("SELECT COUNT(DISTINCT route_id) FROM harvest_frontier WHERE run_id=?", (run_id,)).fetchone()[0]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Autoharvest Run Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target effective records: `{config.target_effective_records}`",
        f"- Raw provisional records: `{raw}`",
        f"- Weighted effective growth: `{round(weighted, 2)}`",
        f"- Pages fetched: `{pages}`",
        f"- Candidates seen: `{candidates}`",
        f"- Routes attempted/frontiered: `{routes}`",
        f"- Stop reason: `{stop_reason}`",
        "- API keys used: `no`",
        "- Public records mutated: `no`",
        "- Public map flags mutated: `no`",
    ]
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"raw": raw, "weighted": weighted, "pages": pages, "candidates": candidates, "routes": routes, "report": out_path}


def export_rows(conn: sqlite3.Connection, query: str) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    return [dict(row) for row in conn.execute(query).fetchall()]


def write_rows(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0].keys()) if rows else ["id"]
    write_csv(path, rows, fields)
