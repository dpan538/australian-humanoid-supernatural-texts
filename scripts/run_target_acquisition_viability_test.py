#!/usr/bin/env python3
"""Run a bounded target acquisition viability test."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from adapters.noauth_sites.generic import matching_adapters
from collection_expansion_common import now_iso, stable_candidate_id, write_csv
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, is_api_url, load_autoharvest_config, make_duplicate_key
from lib.autoharvest_gap import classify_gap_candidate, update_candidate_gap_fields
from lib.gap_recovery import classify_recovery_status, read_csv as read_recovery_csv
from lib.noauth_web import RouteSafety, allowed_by_robots, fetch_html_safe, same_domain
from migrate_autoharvest_gap_v2 import migrate

VIABILITY_DIR = ROOT / "data" / "processed" / "v2" / "autoharvest" / "target_acquisition_viability"


def read_plan(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def materialize_url(template: str, query: str) -> str:
    return str(template or "").replace("%7Bquery%7D", quote_plus(query or "")).replace("{query}", quote_plus(query or ""))


def fetch_public_html(url: str, route_id: str, config, session: requests.Session) -> tuple[str, str]:
    if not url or is_api_url(url):
        return "", "api_or_missing_url"
    if not allowed_by_robots(url, config.user_agent):
        return "", "robots_denied_or_unknown"
    try:
        html = fetch_html_safe(
            url,
            RouteSafety(
                route_id=route_id,
                rate_limit_seconds=float(config.data.get("safety", {}).get("rate_limit_seconds_default", 3.0)),
                timeout_seconds=float(config.data.get("safety", {}).get("html_timeout_seconds", 8.0)),
            ),
            session,
        )
    except Exception:
        return "", "fetch_exception_or_timeout"
    return html or "", "ok" if html else "empty_or_non_html"


def candidate_from_result(result, action: dict, run_id: str) -> dict:
    url = result.url
    title = result.title or action.get("source_name") or "Target acquisition candidate"
    snippet = result.snippet or ""
    return {
        "candidate_id": stable_candidate_id(action.get("route_id"), url, url, title, result.date_text, snippet[:120]),
        "run_id": run_id,
        "page_id": "",
        "route_id": action.get("route_id"),
        "source_id": action.get("route_id"),
        "source_name": action.get("source_name"),
        "source_tier": action.get("source_tier"),
        "route_family": action.get("route_family"),
        "target_state": action.get("state"),
        "target_locality": action.get("target_locality"),
        "time_band": action.get("target_time_band"),
        "term_family": action.get("term_family"),
        "term": action.get("term"),
        "title": title[:500],
        "snippet": snippet[:1000],
        "url": url,
        "stable_id": url,
        "date_published": result.date_text,
        "inferred_year": None,
        "source_stated_place_text": "",
        "locality_hint": action.get("target_locality"),
        "mappability_hint": "low",
        "evidence_source_name": action.get("source_name"),
        "evidence_source_url": url,
        "access_source_name": action.get("source_name"),
        "access_source_url": action.get("official_url"),
        "original_source_name": "",
        "rights_status": "metadata_only",
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
        "evidence_or_discovery": "evidence_possible",
        "item_format": result.item_format,
        "record_publication_date_text": result.date_text,
    }


def run_viability(db_path: Path, plan_path: Path, run_id: str, max_actions: int, execute: bool) -> dict[str, int | bool]:
    migrate(db_path)
    config = load_autoharvest_config(ROOT / "config" / "autoharvest_gap_rescue.yml")
    actions = [row for row in read_plan(plan_path) if str(row.get("should_fetch") or "").lower() in {"1", "true", "yes"}][:max_actions]
    session = requests.Session()
    target_rows: list[dict] = []
    candidate_rows: list[dict] = []
    failed_rows: list[dict] = []
    yield_counts: dict[str, Counter] = defaultdict(Counter)
    route_failures: Counter[str] = Counter()
    near_misses = 0
    viable_pdf_routes: set[str] = set()
    with sqlite3.connect(db_path) as conn:
        for action in actions:
            route_id = action.get("route_id") or "unknown"
            if route_failures[route_id] >= 3:
                failed_rows.append({**action, "failure_reason": "route_paused_after_repeated_failures"})
                continue
            route = {
                "route_id": route_id,
                "source_name": action.get("source_name"),
                "source_tier": action.get("source_tier"),
                "route_family": action.get("route_family"),
                "state": action.get("state"),
                "official_url": action.get("official_url"),
                "evidence_or_discovery": "evidence_possible",
            }
            target_url = materialize_url(action.get("target_url_or_template") or "", action.get("query_string") or "")
            if not same_domain(action.get("official_url") or target_url, target_url):
                failed_rows.append({**action, "failure_reason": "cross_domain_target"})
                route_failures[route_id] += 1
                continue
            html, status = fetch_public_html(target_url, route_id, config, session) if execute else ("", "dry_run")
            if status != "ok":
                failed_rows.append({**action, "failure_reason": status})
                route_failures[route_id] += 1
                continue
            adapters = matching_adapters(target_url, route)
            results = []
            pdf_links = []
            for adapter in adapters[:2]:
                results.extend(adapter.parse_result_page(html, target_url, route))
                pdf_links.extend(adapter.extract_pdf_links(html, target_url))
            if pdf_links:
                viable_pdf_routes.add(action.get("route_id") or "")
            if not results and pdf_links:
                for pdf in pdf_links[:5]:
                    results.append(type("PdfResult", (), {"title": pdf.text or pdf.url, "url": pdf.url, "snippet": pdf.text, "date_text": pdf.date_text, "item_format": "PDF_ISSUE"})())
            if not results:
                failed_rows.append({**action, "failure_reason": "no_item_results"})
                route_failures[route_id] += 1
                continue
            route_failures[route_id] = 0
            for result in results[:10]:
                candidate = candidate_from_result(result, action, run_id)
                candidate["duplicate_key"] = make_duplicate_key(candidate)
                candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
                decision = classify_gap_candidate(candidate, route, config.data, page_text=candidate["snippet"], metadata={"record_publication_date": result.date_text, "title": result.title, "description": result.snippet, "item_format": result.item_format})
                candidate["gate_status"] = "target_gap_accepted" if decision.target_gap_eligible else "high_quality_near_miss" if decision.term_hit_confidence >= 0.7 or decision.temporal.confidence >= 0.7 else "candidate_hold"
                candidate["gate_reasons_json"] = json.dumps(decision.reasons)
                candidate_rows.append({**candidate, "target_gap_eligible": int(decision.target_gap_eligible), "near_miss": int(candidate["gate_status"] == "high_quality_near_miss"), "target_gap_reason": decision.reason})
                yield_counts[route_id]["candidates"] += 1
                if candidate["gate_status"] == "high_quality_near_miss":
                    near_misses += 1
                if decision.target_gap_eligible:
                    target_rows.append({**candidate, "target_effective_weight": decision.target_effective_weight, "target_date_basis": decision.target_date_basis, "item_format": decision.item_format})
                    yield_counts[route_id]["target"] += 1
                if execute:
                    insert_harvest_candidate(conn, candidate)
                    update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
        if execute:
            conn.commit()
    route_rows = [{"route_id": route_id, **dict(counts)} for route_id, counts in yield_counts.items()]
    VIABILITY_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(VIABILITY_DIR / "viability_candidates.csv", candidate_rows, list(candidate_rows[0].keys()) if candidate_rows else ["candidate_id"])
    write_csv(VIABILITY_DIR / "viability_target_records.csv", target_rows, list(target_rows[0].keys()) if target_rows else ["candidate_id"])
    write_csv(VIABILITY_DIR / "viability_route_yield.csv", route_rows, list(route_rows[0].keys()) if route_rows else ["route_id"])
    write_csv(VIABILITY_DIR / "viability_failed_actions.csv", failed_rows, list(failed_rows[0].keys()) if failed_rows else ["action_id"])
    forms_count = len(read_recovery_csv(ROOT / "data" / "interim" / "source_discovery" / "noauth_search_forms.csv"))
    viability_status = classify_recovery_status(len(target_rows), near_misses, len(viable_pdf_routes), search_forms=forms_count)
    should_resume_gap_marathon = viability_status == "PASSED_TARGET"
    lines = [
        "# Target Acquisition Viability Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Actions attempted: `{len(actions)}`",
        f"- Target-gap effective candidates found: `{len(target_rows)}`",
        f"- High-quality near misses: `{near_misses}`",
        f"- Viable PDF/newsletter/journal routes: `{len(viable_pdf_routes)}`",
        f"- Viability status: `{viability_status}`",
        f"- Should resume gap marathon: `{str(should_resume_gap_marathon).lower()}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "",
        "## Recommendation",
        "Continue to full gap marathon." if should_resume_gap_marathon else "Continue recovery; the current no-auth frontier failed, but the no-key no-auth strategy is not exhausted.",
    ]
    (VIABILITY_DIR / "viability_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "target_records": len(target_rows),
        "near_misses": near_misses,
        "viable_pdf_routes": len(viable_pdf_routes),
        "viability_status": viability_status,
        "viable": should_resume_gap_marathon,
        "should_resume_gap_marathon": should_resume_gap_marathon,
        "failed_actions": len(failed_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--max-actions", type=int, default=500)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(run_viability(Path(args.db), Path(args.plan), args.run_id, args.max_actions, execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
