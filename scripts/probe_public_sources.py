#!/usr/bin/env python3
"""Safely stage public-source collection candidates from a query plan."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import (
    allowed_by_robots,
    duplicate_key,
    load_registry,
    normalize_space,
    now_iso,
    route_is_manual_only,
    source_lookup,
    stable_candidate_id,
    table_exists,
    write_csv,
    write_jsonl,
)


TROVE_ENDPOINT = "https://api.trove.nla.gov.au/v3/result"
USER_AGENT = "AusFiguresResearchBot/0.1"

CANDIDATE_FIELDS = [
    "candidate_id",
    "run_id",
    "route_id",
    "source_id",
    "source_name",
    "source_tier",
    "evidence_or_discovery",
    "query_string",
    "term_family",
    "time_band",
    "target_state",
    "target_locality",
    "title",
    "publication",
    "author",
    "date_published",
    "inferred_year",
    "url",
    "stable_id",
    "snippet",
    "raw_text_path",
    "source_stated_place_text",
    "inferred_state",
    "location_role",
    "mappability_hint",
    "ethics_flags_json",
    "rights_status",
    "metadata_only",
    "duplicate_key",
    "duplicate_status",
    "review_status",
    "reviewer_notes",
    "created_at",
    "updated_at",
]

REVIEW_FIELDS = CANDIDATE_FIELDS + [
    "accepted_record_type",
    "accepted_evidence_source_name",
    "accepted_evidence_source_url",
    "accepted_original_source_name",
    "accepted_publication_date",
    "evidence_strength",
    "jurisdiction_state",
    "ethics_review_status",
    "display_decision",
]


def safe_year(value: Any) -> int | None:
    text = str(value or "")
    for token in (text[:4],):
        if token.isdigit():
            return int(token)
    return None


def source_chain_id(candidate_id: str, source_id: str) -> str:
    return "schain_" + hashlib.sha256(f"{candidate_id}|{source_id}".encode("utf-8")).hexdigest()[:24]


def fetch_url(url: str, *, rate_limit_seconds: float, timeout: int = 20, user_agent: str = USER_AGENT) -> str:
    if not allowed_by_robots(url, user_agent=user_agent):
        raise RuntimeError(f"robots.txt disallows or cannot confirm access: {url}")
    time.sleep(rate_limit_seconds)
    resp = requests.get(
        url,
        headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml"},
        timeout=timeout,
    )
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise RuntimeError(f"Refusing non-HTML content by default: {content_type}")
    return resp.text


def search_trove_metadata(query: str, *, state: str | None = None, n: int = 20) -> list[dict[str, Any]]:
    api_key = os.environ.get("TROVE_API_KEY")
    if not api_key:
        raise RuntimeError("TROVE_API_KEY is not set; emit manual/API-key-needed tasks instead")

    params: dict[str, Any] = {
        "q": query,
        "category": "newspaper",
        "encoding": "json",
        "n": min(n, 100),
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

    candidates: list[dict[str, Any]] = []
    for category in data.get("category", []) or []:
        records = category.get("records", {}) or {}
        for item in (records.get("article", []) or records.get("work", []) or []):
            title_obj = item.get("title") or {}
            publication = title_obj.get("title") if isinstance(title_obj, dict) else ""
            candidates.append(
                {
                    "stable_id": str(item.get("id") or item.get("url") or ""),
                    "title": item.get("heading") or item.get("title") or "",
                    "publication": publication,
                    "date_published": item.get("date"),
                    "url": item.get("troveUrl") or item.get("url"),
                    "snippet": item.get("snippet") or "",
                    "metadata_only": 1,
                }
            )
    return candidates


def should_fetch_route(route: dict[str, Any], execute: bool) -> bool:
    if not execute:
        return False
    if route_is_manual_only(route):
        return False
    if route.get("evidence_or_discovery") == "manual_only_sensitive":
        return False
    access = str(route.get("access_method") or "")
    if access == "api" and route.get("source_id") == "trove_newspapers_gazettes":
        return True
    return False


def manual_task_url(route: dict[str, Any], query: str) -> str:
    template = str(route.get("search_url_template") or route.get("base_url") or "")
    if "{query}" in template:
        return template.replace("{query}", quote_plus(query))
    return template


def candidate_from_probe(
    *,
    run_id: str,
    route: dict[str, Any],
    query_row: dict[str, str],
    item: dict[str, Any],
    review_status: str,
    notes: str = "",
) -> dict[str, Any]:
    ts = now_iso()
    source_id = str(route["source_id"])
    stable_id = str(item.get("stable_id") or "")
    url = str(item.get("url") or "")
    title = str(item.get("title") or "")
    date_published = str(item.get("date_published") or "")
    candidate_id = stable_candidate_id(source_id, stable_id, url, title, date_published, query_row.get("query_string"))
    target_locality = query_row.get("target_locality") or ""
    source_place = str(item.get("source_stated_place_text") or "")
    mappability = "high" if source_place else ("medium" if target_locality else "low")
    inferred_year = safe_year(date_published) or safe_year(query_row.get("start_year"))
    row = {
        "candidate_id": candidate_id,
        "run_id": run_id,
        "route_id": route.get("route_id") or source_id,
        "source_id": source_id,
        "source_name": route.get("source_name"),
        "source_tier": route.get("source_tier"),
        "evidence_or_discovery": route.get("evidence_or_discovery"),
        "query_string": query_row.get("query_string"),
        "term_family": query_row.get("term_family"),
        "time_band": query_row.get("time_band"),
        "target_state": query_row.get("target_state"),
        "target_locality": target_locality,
        "title": title,
        "publication": item.get("publication") or "",
        "author": item.get("author") or "",
        "date_published": date_published,
        "inferred_year": inferred_year,
        "url": url,
        "stable_id": stable_id,
        "snippet": item.get("snippet") or "",
        "raw_text_path": "",
        "source_stated_place_text": source_place,
        "inferred_state": query_row.get("target_state"),
        "location_role": item.get("location_role") or "",
        "mappability_hint": mappability,
        "ethics_flags_json": json.dumps({"term_family": query_row.get("term_family"), "review_mode": query_row.get("review_mode")}),
        "rights_status": item.get("rights_status") or route.get("allowed_content_mode") or "",
        "metadata_only": 1,
        "duplicate_key": duplicate_key(title, item.get("publication"), date_published, url, stable_id),
        "duplicate_status": "unchecked",
        "review_status": review_status,
        "reviewer_notes": notes,
        "created_at": ts,
        "updated_at": ts,
    }
    return row


def manual_candidate(run_id: str, route: dict[str, Any], query_row: dict[str, str], reason: str) -> dict[str, Any]:
    query = query_row.get("query_string") or ""
    title = f"Manual search task: {route.get('source_name')}"
    return candidate_from_probe(
        run_id=run_id,
        route=route,
        query_row=query_row,
        item={
            "stable_id": stable_candidate_id(str(route["source_id"]), "", "", title, "", query),
            "title": title,
            "url": manual_task_url(route, query),
            "snippet": reason,
        },
        review_status="manual_search_task",
        notes=reason,
    )


def read_query_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def truthy(value: Any) -> bool:
    return normalize_space(value) in {"1", "true", "yes", "y"}


def has_sample_controls(row: dict[str, str]) -> bool:
    return "should_fetch" in row or "should_manual_review" in row or "route_safety_class" in row


def row_matches_filters(
    row: dict[str, str],
    *,
    only_route_family: str | None = None,
    only_state: str | None = None,
    only_time_band: str | None = None,
) -> tuple[bool, str]:
    if only_route_family and row.get("route_family") != only_route_family:
        return False, "filtered_route_family"
    if only_state and row.get("target_state") != only_state:
        return False, "filtered_state"
    if only_time_band and row.get("time_band") != only_time_band:
        return False, "filtered_time_band"
    return True, ""


def within_caps(
    *,
    source_id: str,
    row: dict[str, str],
    source_counts: Counter[str],
    state_counts: Counter[str],
    time_band_counts: Counter[str],
    max_per_source: int | None,
    max_per_state: int | None,
    max_per_time_band: int | None,
) -> tuple[bool, str]:
    if max_per_source is not None and source_counts[source_id] >= max_per_source:
        return False, "max_per_source"
    state = row.get("target_state") or ""
    if max_per_state is not None and state_counts[state] >= max_per_state:
        return False, "max_per_state"
    time_band = row.get("time_band") or ""
    if max_per_time_band is not None and time_band_counts[time_band] >= max_per_time_band:
        return False, "max_per_time_band"
    return True, ""


def upsert_candidate(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    placeholders = ", ".join(["?"] * len(CANDIDATE_FIELDS))
    update = ", ".join([f"{field}=excluded.{field}" for field in CANDIDATE_FIELDS if field != "candidate_id"])
    conn.execute(
        f"""
        INSERT INTO collection_candidates ({", ".join(CANDIDATE_FIELDS)})
        VALUES ({placeholders})
        ON CONFLICT(candidate_id) DO UPDATE SET {update}
        """,
        tuple(row.get(field) for field in CANDIDATE_FIELDS),
    )


def upsert_source_chain(conn: sqlite3.Connection, row: dict[str, Any], route: dict[str, Any]) -> None:
    ts = now_iso()
    evidence_name = row.get("publication") or route.get("source_name")
    access_name = route.get("source_name")
    conn.execute(
        """
        INSERT INTO source_chains (
            source_chain_id, candidate_id, discovery_source_name, discovery_source_type,
            discovery_source_url, access_source_name, access_source_type, access_source_url,
            original_source_name, original_publication, original_publication_date,
            evidence_source_name, evidence_source_type, evidence_source_url,
            evidence_source_family, evidence_source_tier, evidence_strength,
            rights_status, metadata_only, full_text_available,
            source_chain_review_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_chain_id) DO UPDATE SET
            source_chain_review_status=excluded.source_chain_review_status,
            updated_at=excluded.updated_at
        """,
        (
            source_chain_id(row["candidate_id"], str(route["source_id"])),
            row["candidate_id"],
            route.get("source_name"),
            route.get("evidence_or_discovery"),
            route.get("base_url"),
            access_name,
            route.get("access_method"),
            route.get("base_url"),
            row.get("publication") or "",
            row.get("publication") or "",
            row.get("date_published") or "",
            evidence_name,
            route.get("evidence_or_discovery"),
            row.get("url") or route.get("base_url"),
            route.get("route_family"),
            route.get("source_tier"),
            "needs_review",
            row.get("rights_status") or "",
            1,
            0,
            "needs_review",
            ts,
            ts,
        ),
    )


def write_run(conn: sqlite3.Connection, run_id: str, mode: str, status: str, query_count: int, candidate_count: int, fetched_count: int, error_count: int) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO collection_route_runs (
            run_id, route_id, started_at, finished_at, mode, status,
            query_count, fetched_count, candidate_count, error_count, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            finished_at=excluded.finished_at,
            mode=excluded.mode,
            status=excluded.status,
            query_count=excluded.query_count,
            fetched_count=excluded.fetched_count,
            candidate_count=excluded.candidate_count,
            error_count=excluded.error_count,
            notes=excluded.notes
        """,
        (run_id, "mixed", ts, ts, mode, status, query_count, fetched_count, candidate_count, error_count, "collection expansion probe"),
    )


def probe(
    *,
    db_path: Path,
    registry_path: Path,
    query_plan_path: Path,
    run_id: str,
    limit: int,
    execute: bool,
    only_source_id: str | None = None,
    only_route_family: str | None = None,
    only_state: str | None = None,
    only_time_band: str | None = None,
    max_per_source: int | None = None,
    max_per_state: int | None = None,
    max_per_time_band: int | None = None,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    sources = source_lookup(registry)
    query_rows = read_query_plan(query_plan_path)
    rows: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    fetched = 0
    manual_tasks = 0
    duplicate_skipped = 0
    staged = 0
    errors: list[str] = []
    skipped: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    state_counts: Counter[str] = Counter()
    time_band_counts: Counter[str] = Counter()
    api_key_required: set[str] = set()
    policy_skipped_routes: set[str] = set()

    def add_candidate(row: dict[str, Any]) -> bool:
        nonlocal duplicate_skipped
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id in seen_candidate_ids:
            duplicate_skipped += 1
            return False
        seen_candidate_ids.add(candidate_id)
        rows.append(row)
        return True

    for query_row in query_rows:
        if len(rows) >= limit:
            break
        matches, filter_reason = row_matches_filters(
            query_row,
            only_route_family=only_route_family,
            only_state=only_state,
            only_time_band=only_time_band,
        )
        if not matches:
            skipped[filter_reason] += 1
            continue
        try:
            source_ids = json.loads(query_row.get("preferred_source_ids_json") or "[]")
        except json.JSONDecodeError:
            source_ids = []
        if not source_ids:
            skipped["missing_preferred_source"] += 1
            continue
        for source_id in source_ids:
            if len(rows) >= limit:
                break
            if only_source_id and source_id != only_source_id:
                skipped["filtered_source_id"] += 1
                continue
            route = sources.get(source_id)
            if route is None:
                skipped["unknown_source_id"] += 1
                continue
            cap_ok, cap_reason = within_caps(
                source_id=source_id,
                row=query_row,
                source_counts=source_counts,
                state_counts=state_counts,
                time_band_counts=time_band_counts,
                max_per_source=max_per_source,
                max_per_state=max_per_state,
                max_per_time_band=max_per_time_band,
            )
            if not cap_ok:
                skipped[cap_reason] += 1
                continue

            query = query_row.get("query_string") or ""
            sampled = has_sample_controls(query_row)
            should_fetch = truthy(query_row.get("should_fetch")) if sampled else should_fetch_route(route, execute)
            should_manual = truthy(query_row.get("should_manual_review")) if sampled else True

            if sampled and route.get("evidence_or_discovery") in {"discovery_only", "manual_only_sensitive"} and should_fetch:
                skipped["sampled_fetch_blocked_by_route_policy"] += 1
                policy_skipped_routes.add(str(route.get("source_id")))
                should_fetch = False

            if not execute:
                reason = "dry run; no fetch performed" if not execute else "manual or non-fetch route; review search task"
                if should_fetch or should_manual:
                    if add_candidate(manual_candidate(run_id, route, query_row, reason)):
                        manual_tasks += 1
                        source_counts[source_id] += 1
                        state_counts[query_row.get("target_state") or ""] += 1
                        time_band_counts[query_row.get("time_band") or ""] += 1
                else:
                    skipped["sampled_not_fetch_or_manual"] += 1
                continue

            if sampled and not should_fetch:
                if should_manual:
                    if add_candidate(manual_candidate(run_id, route, query_row, "sampled manual review task")):
                        manual_tasks += 1
                        source_counts[source_id] += 1
                        state_counts[query_row.get("target_state") or ""] += 1
                        time_band_counts[query_row.get("time_band") or ""] += 1
                else:
                    skipped["sampled_not_fetch_or_manual"] += 1
                continue

            if not should_fetch_route(route, execute):
                if should_manual:
                    if add_candidate(manual_candidate(run_id, route, query_row, "manual or non-fetch route; review search task")):
                        manual_tasks += 1
                        source_counts[source_id] += 1
                        state_counts[query_row.get("target_state") or ""] += 1
                        time_band_counts[query_row.get("time_band") or ""] += 1
                else:
                    skipped["route_not_fetchable"] += 1
                    policy_skipped_routes.add(str(route.get("source_id")))
                continue
            try:
                if route.get("source_id") == "trove_newspapers_gazettes":
                    items = search_trove_metadata(query, state=query_row.get("target_state"), n=max(1, min(20, limit - len(rows))))
                else:
                    items = []
                fetched += 1
                if not items:
                    if add_candidate(manual_candidate(run_id, route, query_row, "no metadata results returned; review manually")):
                        manual_tasks += 1
                for item in items:
                    if add_candidate(candidate_from_probe(run_id=run_id, route=route, query_row=query_row, item=item, review_status="needs_review")):
                        staged += 1
                    if len(rows) >= limit:
                        break
                source_counts[source_id] += 1
                state_counts[query_row.get("target_state") or ""] += 1
                time_band_counts[query_row.get("time_band") or ""] += 1
            except Exception as exc:
                errors.append(f"{route.get('source_id')}: {exc}")
                if "TROVE_API_KEY" in str(exc):
                    api_key_required.add(str(route.get("source_id")))
                if add_candidate(manual_candidate(run_id, route, query_row, f"probe unavailable: {exc}")):
                    manual_tasks += 1

    discovery_path = ROOT / "data" / "interim" / "source_discovery" / f"{run_id}_candidates.jsonl"
    review_path = ROOT / "data" / "review" / "v2" / f"{run_id}_candidate_review.csv"
    report_path = ROOT / "data" / "processed" / "v2" / f"{run_id}_probe_report.md"
    write_jsonl(discovery_path, rows)
    write_csv(review_path, rows, REVIEW_FIELDS)

    if execute:
        with sqlite3.connect(db_path) as conn:
            missing = [table for table in ("collection_candidates", "source_chains", "collection_route_runs") if not table_exists(conn, table)]
            if missing:
                raise RuntimeError("Missing migration tables: " + ", ".join(missing))
            for row in rows:
                upsert_candidate(conn, row)
                route = sources.get(str(row.get("source_id")))
                if route:
                    upsert_source_chain(conn, row, route)
            write_run(conn, run_id, "execute", "completed_with_errors" if errors else "completed", len(query_rows), len(rows), fetched, len(errors))
            conn.commit()

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Public Source Probe Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Query plan rows read: `{len(query_rows)}`",
        f"- Candidate/manual-task rows written: `{len(rows)}`",
        f"- Fetch attempts: `{fetched}`",
        f"- Manual task count: `{manual_tasks}`",
        f"- Candidates staged: `{staged}`",
        f"- Duplicate candidates skipped: `{duplicate_skipped}`",
        f"- Errors: `{len(errors)}`",
        f"- JSONL: `{discovery_path}`",
        f"- Review CSV: `{review_path}`",
        "",
        "## Safety Notes",
        "- Dry runs do not fetch network content.",
        "- Manual-only and sensitive routes emit manual search tasks.",
        "- Trove uses the official v3 result API only when `TROVE_API_KEY` is present.",
        "- No PDFs or full text are downloaded by default.",
    ]
    lines.extend(["", "## Skipped Counts"])
    if skipped:
        lines.extend([f"- `{reason}`: {count}" for reason, count in sorted(skipped.items())])
    else:
        lines.append("- None")
    lines.extend(["", "## Routes Requiring API Key"])
    lines.extend([f"- `{route}`" for route in sorted(api_key_required)] or ["- None"])
    lines.extend(["", "## Routes Skipped For Policy Or Safety"])
    lines.extend([f"- `{route}`" for route in sorted(policy_skipped_routes)] or ["- None"])
    if errors:
        lines.extend(["", "## Errors"])
        lines.extend([f"- {error}" for error in errors[:25]])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "rows": len(rows),
        "fetched": fetched,
        "manual_tasks": manual_tasks,
        "staged": staged,
        "duplicate_skipped": duplicate_skipped,
        "skipped": dict(skipped),
        "errors": errors,
        "jsonl": discovery_path,
        "review_csv": review_path,
        "report": report_path,
        "execute": execute,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--registry", required=True, help="source_registry.yml path")
    parser.add_argument("--query-plan", required=True, help="query plan CSV path")
    parser.add_argument("--run-id", required=True, help="stable run id")
    parser.add_argument("--limit", type=int, default=50, help="maximum candidate/manual-task rows")
    parser.add_argument("--dry-run", action="store_true", help="force dry-run mode")
    parser.add_argument("--execute", action="store_true", help="perform allowed metadata probes and stage rows")
    parser.add_argument("--download-public-pdf-metadata", action="store_true", help="reserved; no PDF downloads are performed by this script")
    parser.add_argument("--only-source-id", help="limit to one source_id")
    parser.add_argument("--only-route-family", help="limit to one route family")
    parser.add_argument("--only-state", help="limit to one target state")
    parser.add_argument("--only-time-band", help="limit to one time band")
    parser.add_argument("--max-per-source", type=int, help="maximum query jobs per source")
    parser.add_argument("--max-per-state", type=int, help="maximum query jobs per state")
    parser.add_argument("--max-per-time-band", type=int, help="maximum query jobs per time band")
    args = parser.parse_args()

    execute = bool(args.execute and not args.dry_run)
    summary = probe(
        db_path=Path(args.db),
        registry_path=Path(args.registry),
        query_plan_path=Path(args.query_plan),
        run_id=args.run_id,
        limit=args.limit,
        execute=execute,
        only_source_id=args.only_source_id,
        only_route_family=args.only_route_family,
        only_state=args.only_state,
        only_time_band=args.only_time_band,
        max_per_source=args.max_per_source,
        max_per_state=args.max_per_state,
        max_per_time_band=args.max_per_time_band,
    )
    print(f"Wrote {summary['rows']} candidate/manual-task rows.")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
