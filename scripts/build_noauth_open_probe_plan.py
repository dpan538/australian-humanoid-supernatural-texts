#!/usr/bin/env python3
"""Build a no-auth open-records probe plan from seed routes and gap queries."""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_yaml, make_query, now_iso, stable_query_id, write_csv


PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
LATE_BANDS = {"1955_1964", "1965_1976"}
EARLY_BANDS = {"1926_1939", "1940_1954"}
PREFERRED_FAMILIES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "museum_heritage_page",
    "heritage_register",
    "broadcast_catalogue",
}
FETCH_MODES = {"semi_automated_metadata", "static_html_metadata", "sitemap_metadata", "pdf_metadata_only"}
MANUAL_MODES = {"manual_search_task", "manual_sensitive_review"}

AUTO_FIELDS = [
    "query_id",
    "route_id",
    "source_id",
    "source_name",
    "official_url",
    "state",
    "route_family",
    "source_tier",
    "collection_mode",
    "probe_mode",
    "time_band",
    "start_year",
    "end_year",
    "target_state",
    "target_locality",
    "term_family",
    "term",
    "query_string",
    "search_url",
    "should_fetch",
    "should_download_pdf",
    "should_extract_pdf_text",
    "ethics_risk",
    "sample_weight",
    "sample_reason",
]
MANUAL_FIELDS = [
    "task_id",
    "route_id",
    "source_name",
    "official_url",
    "state",
    "reason_manual",
    "time_band",
    "target_locality",
    "term_family",
    "term",
    "query_string",
    "suggested_manual_search_url",
    "reviewer_notes",
]


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def route_states(route: dict[str, Any]) -> set[str]:
    states = route.get("states") or []
    if states:
        return {str(state) for state in states}
    state = str(route.get("state") or "")
    return PRIORITY_STATES if state == "NATIONAL" else {state}


def route_query_url(route: dict[str, Any], query: str) -> str:
    template = str(route.get("search_url_template") or route.get("official_url") or "")
    if "{query}" in template:
        return template.replace("{query}", quote_plus(query))
    return template


def is_sensitive_family(family: str, cfg: dict[str, Any]) -> bool:
    risk = str(cfg.get("ethics_risk") or "")
    return family == "named_local_legend" or risk in {"medium_high", "high"}


def route_auto_allowed(route: dict[str, Any]) -> bool:
    if truthy(route.get("api_key_required")) or truthy(route.get("login_required")) or truthy(route.get("paywall_required")):
        return False
    if str(route.get("evidence_or_discovery")) in {"discovery_only", "manual_only_sensitive"}:
        return False
    if str(route.get("collection_mode")) in MANUAL_MODES or str(route.get("collection_mode")) == "discovery_only":
        return False
    if str(route.get("source_tier")) not in {"A", "B", "C"}:
        return False
    return True


def manual_reason(route: dict[str, Any], sensitive: bool = False) -> str | None:
    if truthy(route.get("api_key_required")):
        return "api_key_required_excluded"
    if truthy(route.get("login_required")):
        return "login_required_excluded"
    if truthy(route.get("paywall_required")):
        return "paywall_required_excluded"
    if str(route.get("evidence_or_discovery")) == "manual_only_sensitive" or str(route.get("collection_mode")) == "manual_sensitive_review":
        return "manual_sensitive_review"
    if str(route.get("evidence_or_discovery")) == "discovery_only" or str(route.get("collection_mode")) == "discovery_only":
        return "discovery_only_manual_source_route"
    if str(route.get("collection_mode")) == "manual_search_task":
        return "manual_search_task"
    if sensitive:
        return "sensitive_term_family_manual_review"
    return None


def score(route: dict[str, Any], state: str, band_id: str, locality: str) -> tuple[int, list[str]]:
    value = 0
    reasons: list[str] = []
    if state in PRIORITY_STATES:
        value += 60
        reasons.append("priority_state")
    if band_id in LATE_BANDS:
        value += 40
        reasons.append("late_gap_1955_1976")
    elif band_id in EARLY_BANDS and str(route.get("route_family")) in PREFERRED_FAMILIES:
        value += 30
        reasons.append("early_local_institutional")
    if route.get("source_tier") == "A":
        value += 25
        reasons.append("tier_A")
    elif route.get("source_tier") in {"B", "C"}:
        value += 20
        reasons.append("tier_BC")
    if route.get("route_family") in PREFERRED_FAMILIES:
        value += 20
        reasons.append("preferred_route_family")
    if locality:
        value += 15
        reasons.append("locality_present")
    if route.get("state") == "NATIONAL" and not locality:
        value -= 50
        reasons.append("broad_national_no_locality")
    return value, reasons


def build_rows(seeds: list[dict[str, Any]], matrix: dict[str, Any], max_automated: int, max_manual: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Counter[str]]:
    bands = matrix.get("time_bands") or []
    states = matrix.get("states") or {}
    term_families = matrix.get("term_families") or {}
    auto_rows: list[dict[str, Any]] = []
    manual_rows: list[dict[str, Any]] = []
    excluded: Counter[str] = Counter()
    route_caps: dict[str, int] = {}

    for route in seeds:
        route_id = str(route.get("route_id") or route.get("source_id") or "")
        route_caps[route_id] = max(1, int(route.get("max_pages_per_run") or 10))
        if not truthy(route.get("noauth_allowed", True)):
            excluded["noauth_not_allowed"] += 1
            continue
        if truthy(route.get("api_key_required")):
            excluded["api_key_required"] += 1
        if truthy(route.get("login_required")):
            excluded["login_required"] += 1
        if truthy(route.get("paywall_required")):
            excluded["paywall_required"] += 1
        max_pages = int(route.get("max_pages_per_run") or 0)
        for band in bands:
            band_id = str(band.get("id") or "")
            if band_id not in EARLY_BANDS | LATE_BANDS:
                continue
            for state, state_cfg in states.items():
                state = str(state)
                if state not in PRIORITY_STATES or state not in route_states(route):
                    continue
                localities = (state_cfg.get("locality_terms") or [""])[:4]
                for family, family_cfg in term_families.items():
                    if family == "context_filter_exclusions":
                        continue
                    sensitive = is_sensitive_family(str(family), family_cfg or {})
                    for term in (family_cfg.get("terms") or [])[:3]:
                        for locality in localities:
                            query = make_query(str(term), str(locality), state, int(band["start_year"]), int(band["end_year"]), trove=False)
                            probe_modes = route.get("probe_modes") or ["static_html"]
                            probe_mode = str(probe_modes[0])
                            weight, reasons = score(route, state, band_id, str(locality))
                            reason = manual_reason(route, sensitive=sensitive)
                            if route_auto_allowed(route) and not sensitive:
                                row = {
                                    "query_id": "noauth_" + stable_query_id(route_id, band_id, state, locality, family, term),
                                    "route_id": route_id,
                                    "source_id": route.get("source_id") or route_id,
                                    "source_name": route.get("source_name"),
                                    "official_url": route.get("official_url"),
                                    "state": route.get("state"),
                                    "route_family": route.get("route_family"),
                                    "source_tier": route.get("source_tier"),
                                    "collection_mode": route.get("collection_mode"),
                                    "probe_mode": probe_mode,
                                    "time_band": band_id,
                                    "start_year": band.get("start_year"),
                                    "end_year": band.get("end_year"),
                                    "target_state": state,
                                    "target_locality": locality,
                                    "term_family": family,
                                    "term": term,
                                    "query_string": query,
                                    "search_url": route_query_url(route, query),
                                    "should_fetch": "true",
                                    "should_download_pdf": "false",
                                    "should_extract_pdf_text": "false",
                                    "ethics_risk": family_cfg.get("ethics_risk") or "",
                                    "sample_weight": weight,
                                    "sample_reason": ";".join(reasons),
                                }
                                auto_rows.append(row)
                            elif reason:
                                task_id = "noauth_manual_" + stable_query_id(route_id, band_id, state, locality, family, term)
                                manual_rows.append(
                                    {
                                        "task_id": task_id,
                                        "route_id": route_id,
                                        "source_name": route.get("source_name"),
                                        "official_url": route.get("official_url"),
                                        "state": route.get("state"),
                                        "reason_manual": reason,
                                        "time_band": band_id,
                                        "target_locality": locality,
                                        "term_family": family,
                                        "term": term,
                                        "query_string": query,
                                        "suggested_manual_search_url": route_query_url(route, query),
                                        "reviewer_notes": "",
                                    }
                                )

    auto_rows.sort(key=lambda row: (-int(row["sample_weight"]), row["route_id"], row["query_id"]))
    manual_rows.sort(key=lambda row: (row["reason_manual"], row["route_id"], row["task_id"]))
    return select_with_route_caps(auto_rows, max_automated, route_caps), select_with_route_caps(manual_rows, max_manual, route_caps), excluded


def select_with_route_caps(rows: list[dict[str, Any]], limit: int, route_caps: dict[str, int]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()

    def try_add(row: dict[str, Any]) -> bool:
        route_id = str(row.get("route_id") or "")
        if counts[route_id] >= route_caps.get(route_id, 10):
            return False
        if row in selected:
            return False
        selected.append(row)
        counts[route_id] += 1
        return True

    if rows and "target_state" in rows[0]:
        for state in ["WA", "SA", "NT", "TAS", "ACT"]:
            for band in ["1926_1939", "1940_1954", "1955_1964", "1965_1976"]:
                for row in rows:
                    if row.get("target_state") == state and row.get("time_band") == band and try_add(row):
                        break

    for row in rows:
        try_add(row)
        if len(selected) >= limit:
            break
    return selected


def write_report(path: Path, auto: list[dict[str, Any]], manual: list[dict[str, Any]], excluded: Counter[str]) -> None:
    state_counts = Counter(row["target_state"] for row in auto)
    band_counts = Counter(row["time_band"] for row in auto)
    route_counts = Counter(row["route_id"] for row in auto)
    manual_reasons = Counter(row["reason_manual"] for row in manual)
    lines = [
        "# No-Auth Open Probe Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Automated no-auth planned rows: `{len(auto)}`",
        f"- Manual review tasks: `{len(manual)}`",
        f"- API-key routes in automated plan: `0`",
        f"- Login/paywall routes in automated plan: `0`",
        "- Trove API route used: `no`",
        "- Candidate acceptance: `not performed`",
        "- Public map flag publication: `not performed`",
        "",
        "## Automated Coverage By State",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(state_counts.items())] or ["- None"])
    lines.extend(["", "## Automated Coverage By Time Band"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(band_counts.items())] or ["- None"])
    lines.extend(["", "## Top Automated Routes"])
    lines.extend([f"- `{key}`: {count}" for key, count in route_counts.most_common(20)] or ["- None"])
    lines.extend(["", "## Manual Task Reasons"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(manual_reasons.items())] or ["- None"])
    lines.extend(["", "## Excluded Route Counts"])
    if excluded:
        lines.extend([f"- `{key}`: {count}" for key, count in sorted(excluded.items())])
    else:
        lines.append("- No seed routes required API keys, logins, or paywalls.")
    lines.extend(
        [
            "",
            "## Safety",
            "- Automated rows are metadata-first public HTML/catalogue/sitemap probes.",
            "- Discovery-only and sensitive routes are manual tasks, not fetches.",
            "- PDF rows are link/HEAD metadata only; text extraction is disabled by default.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--manual-out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-automated", type=int, default=500)
    parser.add_argument("--max-manual", type=int, default=500)
    args = parser.parse_args()
    del args.targets
    seeds = load_yaml(Path(args.seeds)) or []
    matrix = load_yaml(Path(args.matrix)) or {}
    auto, manual, excluded = build_rows(seeds, matrix, args.max_automated, args.max_manual)
    write_csv(Path(args.out), auto, AUTO_FIELDS)
    write_csv(Path(args.manual_out), manual, MANUAL_FIELDS)
    write_report(Path(args.report), auto, manual, excluded)
    print(f"Wrote no-auth automated plan rows: {len(auto)}")
    print(f"Wrote no-auth manual tasks: {len(manual)}")


if __name__ == "__main__":
    main()
