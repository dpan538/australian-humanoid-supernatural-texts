#!/usr/bin/env python3
"""Run a narrow Trove metadata-only batch against sampled gap queries."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, now_iso, source_lookup, table_exists, write_csv, write_jsonl
from probe_public_sources import CANDIDATE_FIELDS, REVIEW_FIELDS, candidate_from_probe, source_chain_id, upsert_candidate, upsert_source_chain


TROVE_ENDPOINT = "https://api.trove.nla.gov.au/v3/result"
USER_AGENT = "AusFiguresResearchBot/0.1"
TROVE_SOURCE_IDS = {"trove_newspapers_gazettes", "trove_magazines_newsletters"}


def read_query_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def source_ids(row: dict[str, str]) -> list[str]:
    try:
        return [str(item) for item in json.loads(row.get("preferred_source_ids_json") or "[]")]
    except json.JSONDecodeError:
        return []


def trove_category(route: dict[str, Any]) -> str:
    if route.get("source_id") == "trove_magazines_newsletters":
        return "magazine"
    return "newspaper"


def extract_items(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    categories = data.get("category")
    if not isinstance(categories, list):
        return [], ["missing_or_unexpected_category_array"]
    items: list[dict[str, Any]] = []
    for category in categories:
        if not isinstance(category, dict):
            warnings.append("category_item_not_object")
            continue
        records = category.get("records") or {}
        if not isinstance(records, dict):
            warnings.append("records_not_object")
            continue
        record_list = records.get("article") or records.get("work") or records.get("item") or []
        if not isinstance(record_list, list):
            warnings.append("record_list_not_array")
            continue
        for item in record_list:
            if not isinstance(item, dict):
                continue
            title_obj = item.get("title") or {}
            publication = title_obj.get("title") if isinstance(title_obj, dict) else ""
            items.append(
                {
                    "stable_id": str(item.get("id") or item.get("url") or ""),
                    "title": item.get("heading") or item.get("title") or item.get("name") or "",
                    "publication": publication or item.get("newspaperTitle") or "",
                    "date_published": item.get("date") or item.get("issued"),
                    "url": item.get("troveUrl") or item.get("url"),
                    "snippet": item.get("snippet") or "",
                    "rights_status": "metadata_only",
                    "source_stated_place_text": "",
                }
            )
    return items, warnings


def search_trove(query: str, category: str, api_key: str, max_results: int, state: str | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    params: dict[str, Any] = {
        "q": query,
        "category": category,
        "encoding": "json",
        "n": min(max_results, 100),
    }
    if state:
        params["l-state"] = state
    resp = requests.get(
        TROVE_ENDPOINT,
        params=params,
        headers={"X-API-KEY": api_key, "User-Agent": USER_AGENT},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return extract_items(data)


def run_batch(
    *,
    db_path: Path,
    query_plan_path: Path,
    registry_path: Path,
    run_id: str,
    limit: int,
    max_results_per_query: int,
    execute: bool,
) -> dict[str, Any]:
    api_key = os.environ.get("TROVE_API_KEY")
    if execute and not api_key:
        raise RuntimeError("TROVE_API_KEY is required for Trove metadata batch execution")

    registry = load_registry(registry_path)
    routes = source_lookup(registry)
    query_rows = read_query_plan(query_plan_path)
    candidates: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    queries_attempted = 0

    for row in query_rows:
        if len(candidates) >= limit:
            break
        for source_id in source_ids(row):
            if source_id not in TROVE_SOURCE_IDS:
                continue
            route = routes.get(source_id)
            if not route:
                continue
            if row.get("should_fetch") and row.get("should_fetch") != "true":
                continue
            if not execute:
                candidates.append(
                    candidate_from_probe(
                        run_id=run_id,
                        route=route,
                        query_row=row,
                        item={
                            "stable_id": f"dry:{row.get('query_id')}:{source_id}",
                            "title": f"Dry run Trove metadata query: {row.get('query_string')}",
                            "url": route.get("search_url_template", "").replace("{query}", row.get("query_string", "")),
                            "snippet": "dry run; no Trove API request performed",
                        },
                        review_status="manual_search_task",
                        notes="dry run; no Trove API request performed",
                    )
                )
                break
            try:
                queries_attempted += 1
                items, item_warnings = search_trove(
                    row.get("query_string", ""),
                    trove_category(route),
                    api_key or "",
                    max_results_per_query,
                    state=row.get("target_state"),
                )
                warnings.extend([f"{row.get('query_id')}:{warning}" for warning in item_warnings])
                for item in items:
                    candidates.append(candidate_from_probe(run_id=run_id, route=route, query_row=row, item=item, review_status="needs_review"))
                    if len(candidates) >= limit:
                        break
            except Exception as exc:
                errors.append(f"{row.get('query_id')}:{source_id}:{exc}")
            break

    jsonl_path = ROOT / "data" / "interim" / "source_discovery" / f"{run_id}_trove_candidates.jsonl"
    review_path = ROOT / "data" / "review" / "v2" / f"{run_id}_candidate_review.csv"
    report_path = ROOT / "data" / "processed" / "v2" / f"{run_id}_trove_probe_report.md"
    write_jsonl(jsonl_path, candidates)
    write_csv(review_path, candidates, REVIEW_FIELDS)

    if execute:
        with sqlite3.connect(db_path) as conn:
            missing = [table for table in ("collection_candidates", "source_chains") if not table_exists(conn, table)]
            if missing:
                raise RuntimeError("Missing migration tables: " + ", ".join(missing))
            for candidate in candidates:
                upsert_candidate(conn, candidate)
                route = routes.get(str(candidate.get("source_id")))
                if route:
                    upsert_source_chain(conn, candidate, route)
            conn.commit()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Trove Metadata Batch Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Query rows read: `{len(query_rows)}`",
        f"- Trove API queries attempted: `{queries_attempted}`",
        f"- Candidate rows written: `{len(candidates)}`",
        f"- Response-shape warnings: `{len(warnings)}`",
        f"- Errors: `{len(errors)}`",
        "- Bulk harvest: `not used`",
        "- Full text stored: `no`",
        f"- JSONL: `{jsonl_path}`",
        f"- Review CSV: `{review_path}`",
    ]
    if warnings:
        lines.extend(["", "## Response Shape Warnings"])
        lines.extend([f"- {warning}" for warning in warnings[:50]])
    if errors:
        lines.extend(["", "## Errors"])
        lines.extend([f"- {error}" for error in errors[:50]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"candidates": len(candidates), "queries_attempted": queries_attempted, "warnings": warnings, "errors": errors, "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--query-plan", required=True, help="sampled query plan CSV")
    parser.add_argument("--registry", default=str(ROOT / "config" / "source_registry.yml"), help="source_registry.yml")
    parser.add_argument("--run-id", required=True, help="run id")
    parser.add_argument("--limit", type=int, default=200, help="candidate limit")
    parser.add_argument("--max-results-per-query", type=int, default=10, help="Trove metadata results per query")
    parser.add_argument("--dry-run", action="store_true", help="do not call Trove API or write SQLite")
    parser.add_argument("--execute", action="store_true", help="call Trove API and stage metadata candidates")
    args = parser.parse_args()

    execute = bool(args.execute and not args.dry_run)
    summary = run_batch(
        db_path=Path(args.db),
        query_plan_path=Path(args.query_plan),
        registry_path=Path(args.registry),
        run_id=args.run_id,
        limit=args.limit,
        max_results_per_query=args.max_results_per_query,
        execute=execute,
    )
    print(f"Trove metadata batch wrote {summary['candidates']} candidate rows.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
