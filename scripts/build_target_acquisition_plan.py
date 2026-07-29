#!/usr/bin/env python3
"""Build a target acquisition plan from zero-yield diagnostics."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.autoharvest_engine import classify_route_safety, load_autoharvest_config

PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
ACTION_FIELDS = [
    "action_id", "action_type", "route_id", "source_name", "source_tier", "route_family", "state",
    "official_url", "target_url_or_template", "query_string", "target_time_band", "target_locality",
    "term_family", "term", "expected_target_signal", "why_selected", "should_fetch",
    "should_pdf_snippet", "should_use_search_form", "should_use_adapter", "priority_score", "safety_notes",
]


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_yaml_rows(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return [row for row in data if isinstance(row, dict)]


def action_id(*parts) -> str:
    return "act_" + hashlib.sha256("|".join(str(part or "") for part in parts).encode("utf-8")).hexdigest()[:20]


def base_score(route: dict, action_type: str, band: str) -> int:
    score = 0
    if route.get("state") in PRIORITY_STATES:
        score += 70
    if band in {"1955_1964", "1965_1976"}:
        score += 80
    elif band in {"1926_1939", "1940_1954"}:
        score += 50
    if route.get("source_tier") == "A":
        score += 30
    elif route.get("source_tier") in {"B", "C"}:
        score += 20
    if route.get("route_family") in {"local_history_serial", "council_local_studies", "historical_society"}:
        score += 35
    if action_type in {"PROBE_PUBLIC_PDF_SNIPPETS", "PROBE_NEWSLETTER_ARCHIVE", "PROBE_JOURNAL_INDEX"}:
        score += 40
    return score


def route_action_type(route: dict, diagnosis: dict | None = None) -> str:
    hay = " ".join(str(route.get(key) or "") for key in ["route_id", "source_name", "route_family", "official_url"]).lower()
    if diagnosis and diagnosis.get("surface_diagnosis") not in {"", None, "PAUSE_AUXILIARY_ONLY_ROUTE"}:
        return diagnosis["surface_diagnosis"]
    if any(token in hay for token in ["newsletter", "journal", "bulletin"]):
        return "PROBE_NEWSLETTER_ARCHIVE"
    if route.get("route_family") == "local_history_serial":
        return "PROBE_JOURNAL_INDEX"
    if route.get("route_family") == "council_local_studies":
        return "PROBE_COUNCIL_LOCAL_STUDIES"
    if route.get("route_family") in {"state_library_catalogue", "national_library_catalogue"}:
        return "PROBE_CATALOGUE_HTML_ADAPTER"
    if route.get("route_family") == "state_archive_catalogue":
        return "PROBE_ARCHIVE_FINDING_AID"
    if route.get("route_family") == "broadcast_catalogue":
        return "PROBE_BROADCAST_METADATA"
    if route.get("route_family") == "museum_heritage_page":
        return "PROBE_HERITAGE_PAGE_WITH_DATE"
    return "DISCOVER_MORE_PDFS"


def build_queries(route: dict) -> list[tuple[str, str, str]]:
    terms = ["ghost", "haunted hotel", "apparition", "yowie", "bunyip", "Min Min", "local legend"]
    bands = [("1955_1964", "1964"), ("1965_1976", "1971"), ("1940_1954", "1950s"), ("1926_1939", "1930s")]
    locality = route.get("state") or "Australia"
    out: list[tuple[str, str, str]] = []
    for band, date_token in bands:
        for term in terms:
            out.append((band, term, f"\"{term}\" \"{locality}\" \"{date_token}\""))
    return out


def build_plan(db_path: Path, postmortem_dir: Path, seeds_path: Path, registry_path: Path, matrix_path: Path, out_path: Path, report_path: Path, max_actions: int) -> list[dict]:
    seeds = load_yaml_rows(seeds_path)
    config = load_autoharvest_config(ROOT / "config" / "autoharvest_gap_rescue.yml")
    diagnosis_rows = read_csv(postmortem_dir / "route_surface_diagnosis.csv")
    diagnosis_by_route = {row.get("route_id"): row for row in diagnosis_rows}
    search_forms = read_csv(ROOT / "data" / "interim" / "source_discovery" / "noauth_search_forms.csv")
    forms_by_route = {}
    for form in search_forms:
        if str(form.get("safe_to_use") or "").lower() in {"1", "true", "yes"}:
            forms_by_route.setdefault(form.get("route_id"), []).append(form)
    rows: list[dict] = []
    for seed in seeds:
        ok, reasons = classify_route_safety(seed, config)
        if not ok:
            continue
        if seed.get("source_tier") not in {"A", "B", "C"}:
            continue
        action_type = route_action_type(seed, diagnosis_by_route.get(seed.get("route_id")))
        if diagnosis_by_route.get(seed.get("route_id"), {}).get("recommended_action") == "PAUSE_AUXILIARY_ONLY_ROUTE":
            pause = {
                "action_id": action_id("pause", seed.get("route_id")),
                "action_type": "PAUSE_AUXILIARY_ONLY_ROUTE",
                "route_id": seed.get("route_id"),
                "source_name": seed.get("source_name"),
                "source_tier": seed.get("source_tier"),
                "route_family": seed.get("route_family"),
                "state": seed.get("state"),
                "official_url": seed.get("official_url"),
                "target_url_or_template": seed.get("official_url"),
                "query_string": "",
                "target_time_band": "",
                "target_locality": seed.get("state"),
                "term_family": "",
                "term": "",
                "expected_target_signal": "auxiliary_only_zero_target",
                "why_selected": "route produced auxiliary records but zero target records",
                "should_fetch": 0,
                "should_pdf_snippet": 0,
                "should_use_search_form": 0,
                "should_use_adapter": 0,
                "priority_score": 1,
                "safety_notes": "pause only; no fetch",
            }
            rows.append(pause)
        for band, term, query in build_queries(seed)[:12]:
            forms = forms_by_route.get(seed.get("route_id")) or []
            if forms:
                for form in forms[:2]:
                    template = form["search_url_template"]
                    rows.append(make_action(seed, "PROBE_GET_SEARCH_FORM", template, query, band, term, "safe GET source-native search form", True, False, True, True, base_score(seed, "PROBE_GET_SEARCH_FORM", band)))
            rows.append(make_action(seed, action_type, seed.get("official_url"), query, band, term, "explicit date plus controlled term on item/PDF/metadata page", True, action_type in {"PROBE_PUBLIC_PDF_SNIPPETS", "PROBE_NEWSLETTER_ARCHIVE", "PROBE_JOURNAL_INDEX", "PROBE_COUNCIL_LOCAL_STUDIES"}, False, True, base_score(seed, action_type, band)))
    rows = sorted(rows, key=lambda row: float(row["priority_score"]), reverse=True)[:max_actions]
    write_csv(out_path, rows, ACTION_FIELDS)
    counts = Counter(row["action_type"] for row in rows)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Target Acquisition Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Actions planned: `{len(rows)}`",
        f"- Safe GET search forms available: `{sum(len(v) for v in forms_by_route.values())}`",
        "- Previous frontier failed because it produced auxiliary/directories without explicit target date plus term plus item-level evidence.",
        "",
        "## Action Types",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in counts.most_common()] or ["- None"])
    lines.extend(["", "## Exact Next Command", "`make gap-viability-test`"])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return rows


def make_action(seed: dict, action_type: str, target: str, query: str, band: str, term: str, signal: str, fetch: bool, pdf: bool, search: bool, adapter: bool, score: int) -> dict:
    return {
        "action_id": action_id(action_type, seed.get("route_id"), target, query),
        "action_type": action_type,
        "route_id": seed.get("route_id"),
        "source_name": seed.get("source_name"),
        "source_tier": seed.get("source_tier"),
        "route_family": seed.get("route_family"),
        "state": seed.get("state"),
        "official_url": seed.get("official_url"),
        "target_url_or_template": target,
        "query_string": query,
        "target_time_band": band,
        "target_locality": seed.get("state"),
        "term_family": "controlled_supernatural",
        "term": term,
        "expected_target_signal": signal,
        "why_selected": f"{action_type} for {seed.get('route_family')} {seed.get('state')}",
        "should_fetch": int(fetch),
        "should_pdf_snippet": int(pdf),
        "should_use_search_form": int(search),
        "should_use_adapter": int(adapter),
        "priority_score": score,
        "safety_notes": "no api keys; no login; robots required; metadata/snippets only",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--postmortem-dir", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--max-actions", type=int, default=1000)
    args = parser.parse_args()
    rows = build_plan(Path(args.db), Path(args.postmortem_dir), Path(args.seeds), Path(args.registry), Path(args.matrix), Path(args.out), Path(args.report), args.max_actions)
    print(f"Wrote target acquisition plan: {args.out}")
    print({"actions": len(rows)})


if __name__ == "__main__":
    main()
