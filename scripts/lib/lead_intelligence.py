from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from collection_expansion_common import write_csv
from lib.target_gap_leads import domain_for


PRIORITY_BUCKETS = {"PRIORITY_LEAD", "GOOD_LEAD"}
ROUTE_LEAD_TYPES = {"SOURCE_ATLAS_ROUTE_LEAD", "STRUCTURED_ENDPOINT_ROUTE_LEAD", "SEARCH_FORM_ROUTE_LEAD", "PDF_NEWSLETTER_ROUTE_LEAD"}
SOURCE_CHAIN_TYPES = {"ACCESS_PLATFORM_DECOMPOSITION_LEAD", "DISCOVERY_ONLY_REPLACEMENT_LEAD", "UNKNOWN_SOURCE_REGISTRY_LEAD", "SOURCE_ATLAS_ROUTE_LEAD"}
METADATA_ROUTE_FAMILIES = {
    "local_history_serial",
    "council_local_studies",
    "state_archive",
    "state_archive_catalogue",
    "state_library",
    "state_library_catalogue",
    "broadcast_catalogue",
    "museum_heritage_page",
    "national_library_catalogue",
    "heritage_register",
}
TECHNICAL_BLOCKERS = {"robots_unknown", "robots_denied", "missing_item_url", "field_mapping_sparse"}
STRUCTURAL_BLOCKERS = {"missing_date", "missing_term", "d_class_needs_original", "discovery_only_needs_evidence", "source_unknown", "ethics_sensitive"}


def norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def norm_title(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", norm(value))
    return re.sub(r"\s+", " ", text).strip()


def norm_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")
    return f"{parsed.scheme.lower() or 'https'}://{host}{path}".lower()


def domain_slug(value: Any) -> str:
    parsed = urlparse(str(value or ""))
    domain = parsed.netloc.lower().removeprefix("www.")
    slug = Path(parsed.path or "").stem.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return f"{domain}/{slug}" if domain and slug else ""


def lead_kind(row: dict[str, Any]) -> str:
    lead_type = str(row.get("lead_type") or "")
    blocker = str(row.get("constraint_blocker") or "")
    gaps = str(row.get("evidence_gap") or "")
    if "robots" in blocker or "robots" in gaps or lead_type == "ROBOTS_BLOCKED_NEAR_MISS":
        return "robots_permission_lead"
    if lead_type in ROUTE_LEAD_TYPES:
        return "source_route_lead"
    if lead_type in SOURCE_CHAIN_TYPES or "d_class" in gaps or "discovery_only" in gaps:
        return "source_chain_remediation_lead"
    if str(row.get("url") or "").strip():
        return "item_or_metadata_lead"
    return "auxiliary_or_noise"


def useful_for_observation(row: dict[str, Any]) -> bool:
    if row.get("priority_bucket") in PRIORITY_BUCKETS:
        return True
    if str(row.get("temporal_signal") or row.get("term_signal") or "").strip():
        return True
    if row.get("route_family") in METADATA_ROUTE_FAMILIES and (row.get("target_state") or row.get("target_locality")):
        return True
    return False


def ignored_as_auxiliary(row: dict[str, Any]) -> bool:
    if row.get("priority_bucket") in {"HOLD", "SENSITIVE_HOLD"}:
        return True
    if lead_kind(row) == "auxiliary_or_noise":
        return True
    return False


def date_text(row: dict[str, Any]) -> str:
    keys = [
        "title",
        "description",
        "url",
        "source_name",
        "source_family",
        "route_family",
        "temporal_signal",
        "source_chain_json",
    ]
    return " ".join(str(row.get(key) or "") for key in keys)


def _ignore_context(text: str, start: int, end: int) -> bool:
    window = text[max(0, start - 36) : min(len(text), end + 36)].lower()
    ignored = [
        "crawl date",
        "crawled",
        "export date",
        "generated",
        "created_at",
        "updated_at",
        "query plan",
        "query year",
        "route target",
        "target year",
        "search query",
    ]
    return any(token in window for token in ignored)


def extract_date_signal(row: dict[str, Any]) -> dict[str, Any]:
    text = date_text(row)
    lowered = text.lower()

    range_match = None
    for match in re.finditer(r"\b(19[2-7][0-9])\s*[-–]\s*(19[2-7][0-9])\b", lowered):
        if _ignore_context(lowered, match.start(), match.end()):
            continue
        start, end = int(match.group(1)), int(match.group(2))
        if start <= 1976 and end >= 1926:
            range_match = (start, end, match.group(0))
            break
    if range_match:
        start, end, signal = range_match
        return {"temporal_signal": signal, "inferred_year": start, "coverage_start_year": start, "coverage_end_year": end, "date_status": "salvaged_range"}

    decade_match = None
    for match in re.finditer(r"\b(1930|1940|1950|1960|1970)s\b", lowered):
        if _ignore_context(lowered, match.start(), match.end()):
            continue
        start = int(match.group(1))
        decade_match = (start, min(start + 9, 1976), match.group(0))
        break
    if decade_match:
        start, end, signal = decade_match
        return {"temporal_signal": signal, "inferred_year": start, "coverage_start_year": start, "coverage_end_year": end, "date_status": "salvaged_decade"}

    serial = re.search(r"\b(?:vol\.?|volume|no\.?|number|newsletter|journal|bulletin|annual report|issue)\b.{0,48}\b(19[2-7][0-9])\b", lowered)
    if serial and not _ignore_context(lowered, serial.start(1), serial.end(1)):
        year = int(serial.group(1))
        if 1926 <= year <= 1976:
            return {"temporal_signal": str(year), "inferred_year": year, "coverage_start_year": year, "coverage_end_year": year, "date_status": "salvaged_serial_issue"}

    for match in re.finditer(r"\b(19[2-7][0-9])\b", lowered):
        if _ignore_context(lowered, match.start(), match.end()):
            continue
        year = int(match.group(1))
        if 1926 <= year <= 1976:
            return {"temporal_signal": str(year), "inferred_year": year, "coverage_start_year": year, "coverage_end_year": year, "date_status": "salvaged_exact_year"}

    ambiguous = re.search(r"\b(?:1920s|1970s|late 1970s|mid century|postwar|post-war)\b", lowered)
    if ambiguous:
        return {"temporal_signal": ambiguous.group(0), "inferred_year": None, "coverage_start_year": None, "coverage_end_year": None, "date_status": "ambiguous"}
    return {"temporal_signal": "", "inferred_year": None, "coverage_start_year": None, "coverage_end_year": None, "date_status": "missing"}


def overlaps(row: dict[str, Any], start_year: int, end_year: int) -> bool:
    for key in ["inferred_year", "coverage_start_year", "coverage_end_year"]:
        value = row.get(key)
        try:
            if value not in {None, ""} and start_year <= int(value) <= end_year:
                return True
        except (TypeError, ValueError):
            pass
    try:
        start = int(row.get("coverage_start_year")) if row.get("coverage_start_year") not in {None, ""} else None
        end = int(row.get("coverage_end_year")) if row.get("coverage_end_year") not in {None, ""} else None
    except (TypeError, ValueError):
        start = end = None
    return bool(start is not None and end is not None and start <= end_year and end >= start_year)


def metadata_class(row: dict[str, Any]) -> str:
    ethics = str(row.get("ethics_status") or "")
    if ethics in {"sensitive", "restricted", "manual_only"} or row.get("priority_bucket") == "SENSITIVE_HOLD":
        return ""
    date_ok = overlaps(row, 1955, 1976)
    term = bool(str(row.get("term_signal") or "").strip())
    url = bool(str(row.get("url") or "").strip())
    route = str(row.get("route_family") or "")
    tier = str(row.get("source_tier") or "")
    locality = bool(str(row.get("target_locality") or row.get("place_signal") or row.get("target_state") or "").strip())
    blocker = str(row.get("constraint_blocker") or "")
    gaps = str(row.get("evidence_gap") or "")
    source_chain = row.get("source_chain_json") and row.get("source_chain_json") != "{}"
    eligible_tier = tier in {"A", "B", "C"} or ("d_class_needs_original" in gaps and source_chain)
    eligible_route = route in METADATA_ROUTE_FAMILIES or any(token in route for token in ["catalogue", "archive", "library", "museum", "council", "serial", "broadcast"])
    if not (date_ok or term):
        return ""
    if not (eligible_tier or eligible_route):
        return ""
    if "robots" in blocker and (date_ok or term):
        return "METADATA_ONLY_ROBOTS_BLOCKED"
    if date_ok and term and url:
        return "METADATA_ONLY_STRONG"
    if date_ok and eligible_route and locality and not term:
        return "METADATA_ONLY_ROUTE_LEAD"
    if term and eligible_route:
        return "METADATA_ONLY_TERM_LEAD"
    if source_chain and ("discovery_only" in gaps or "d_class" in gaps):
        return "METADATA_ONLY_SOURCE_CHAIN_LEAD"
    return ""


def write_count_csv(path: Path, rows: list[dict[str, Any]], key_name: str = "category") -> None:
    write_csv(path, rows, [key_name, "count"])


def counter_rows(counter: Counter) -> list[dict[str, Any]]:
    return [{"category": str(key or "unknown"), "count": value} for key, value in counter.most_common()]


def group_counter(rows: list[dict[str, Any]], key: str) -> Counter:
    return Counter(str(row.get(key) or "unknown") for row in rows)


def top_groups(rows: list[dict[str, Any]], *keys: str, limit: int = 20) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key) or "unknown") for key in keys)].append(row)
    output = []
    for labels, grouped_rows in grouped.items():
        output.append(
            {
                **{key: labels[index] for index, key in enumerate(keys)},
                "lead_count": len(grouped_rows),
                "priority_leads": sum(1 for row in grouped_rows if row.get("priority_bucket") == "PRIORITY_LEAD"),
                "max_lead_score": max(float(row.get("lead_score") or 0) for row in grouped_rows),
            }
        )
    output.sort(key=lambda row: (-row["lead_count"], -row["max_lead_score"], str(row)))
    return output[:limit]
