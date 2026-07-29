#!/usr/bin/env python3
"""Build targeted structured endpoint queries from materialized near misses."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_structured_endpoint_queries import materialize_query_url, priority, query_id
from collection_expansion_common import now_iso, write_csv
from migrate_structured_near_miss_v1 import migrate


DATE_VARIANTS = ["1930s", "1940s", "1950s", "1960s", "1970s", "1926", "1976"]
TERM_VARIANTS = ["ghost", "haunted", "apparition", "phantom", "bunyip", "yowie", "local legend"]
DETAIL_ONLY_TYPES = {"ITEM_URL_NEEDS_DETAIL", "AtoM_DETAIL_REQUIRED", "OMEKA_ITEM_DETAIL_REQUIRED", "WORDPRESS_POST_DETAIL_REQUIRED", "RSS_ITEM_DETAIL_REQUIRED", "OAI_RECORD_DETAIL_REQUIRED", "DESCRIPTION_TRUNCATED"}
ADAPTER_FIX_TYPES = {"FIELD_MAPPING_SUSPECT"}


def query_tokens(row: dict[str, Any]) -> list[str]:
    values = []
    for value in [row.get("title"), row.get("description"), row.get("place_text"), row.get("item_url")]:
        values.extend(str(value or "").replace("+", " ").replace("%20", " ").split())
    parsed = urlparse(str(row.get("item_url") or ""))
    qs = parse_qs(parsed.query)
    for key in ["query", "q", "search"]:
        for value in qs.get(key, []):
            values.extend(value.replace("+", " ").split())
    tokens: list[str] = []
    for value in values:
        cleaned = "".join(ch for ch in value if ch.isalnum() or ch in {"'", "-"}).strip()
        if 2 <= len(cleaned) <= 40 and cleaned.lower() not in {"skip", "content", "navigation", "record", "item"}:
            tokens.append(cleaned)
    return list(dict.fromkeys(tokens))


def build_queries_for_near(row: dict[str, Any]) -> tuple[list[str], str]:
    near_type = row.get("near_miss_type")
    tokens = query_tokens(row)
    locality = row.get("place_text") or ""
    if not locality:
        locality = next((token for token in tokens if token.lower() in {"fremantle", "kalgoorlie", "albany", "perth", "darwin", "hobart", "adelaide"}), "")
    if near_type == "TERM_NO_DATE":
        base_terms = [token for token in tokens if token.lower() in TERM_VARIANTS] or [row.get("controlled_term") or "ghost"]
        queries = [f"{term} {date}" for term in base_terms[:3] for date in DATE_VARIANTS[:5]]
        return queries, "added date-bearing variants for TERM_NO_DATE evidence"
    if near_type == "DATE_NO_TERM":
        dates = [str(row.get("inferred_year") or ""), "1930s", "1940s"]
        dates = [date for date in dates if date]
        loc = f" {locality}" if locality else ""
        queries = [f"{term}{loc} {date}".strip() for term in TERM_VARIANTS[:5] for date in dates[:3]]
        return queries, "added controlled-term variants around date/locality evidence"
    if near_type in DETAIL_ONLY_TYPES:
        return [], "detail enrichment prioritized; no broad query expansion"
    if near_type in ADAPTER_FIX_TYPES:
        return [], "adapter repair prioritized; no query expansion"
    if near_type == "TARGET_SCORE_BORDERLINE":
        loc = f" {locality}" if locality else ""
        return [f"{term}{loc} {date}".strip() for term in TERM_VARIANTS[:3] for date in DATE_VARIANTS[:3]], "added narrow borderline variants"
    return [], "no safe targeted expansion"


def rebuild(db_path: Path, run_id: str, new_run_id: str, out: Path, execute: bool) -> dict[str, Any]:
    migrate(db_path)
    rows_written = 0
    recommendations: list[dict[str, Any]] = []
    skipped_by_type = Counter()
    inserted_by_type = Counter()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        near_rows = [
            dict(row)
            for row in conn.execute(
                """
                SELECT n.*, i.endpoint_url, i.state, i.status AS endpoint_status, i.noauth_verified,
                       i.api_key_required, i.login_required, i.paywall_required
                FROM structured_endpoint_near_misses n
                LEFT JOIN noauth_endpoint_inventory i ON i.endpoint_id=n.endpoint_id
                WHERE n.run_id=?
                ORDER BY n.recoverability_score DESC
                """,
                (run_id,),
            ).fetchall()
        ]
        for near in near_rows:
            queries, reason = build_queries_for_near(near)
            if not queries:
                skipped_by_type[near.get("near_miss_type") or "UNKNOWN"] += 1
                recommendations.append({"near_miss_id": near.get("near_miss_id"), "near_miss_type": near.get("near_miss_type"), "action": "no_query_added", "reason": reason, "queries_added": 0})
                continue
            if near.get("endpoint_status") not in {"active", "paused"} or near.get("api_key_required") or near.get("login_required") or near.get("paywall_required"):
                skipped_by_type[near.get("near_miss_type") or "UNKNOWN"] += 1
                recommendations.append({"near_miss_id": near.get("near_miss_id"), "near_miss_type": near.get("near_miss_type"), "action": "skipped_endpoint_policy", "reason": "endpoint inactive or credential/paywall constrained", "queries_added": 0})
                continue
            endpoint_type = near.get("endpoint_type") or ""
            endpoint_url = near.get("endpoint_url") or near.get("detail_url") or near.get("item_url") or ""
            added = 0
            for query_text in list(dict.fromkeys(queries))[:12]:
                date_term = next((date for date in DATE_VARIANTS if date in query_text), "")
                term = next((term for term in TERM_VARIANTS if term.lower() in query_text.lower()), "")
                qid = query_id(str(near.get("endpoint_id") or ""), new_run_id, query_text, str(near.get("place_text") or ""), date_term)
                row = {
                    "endpoint_query_id": qid,
                    "endpoint_id": near.get("endpoint_id"),
                    "run_id": new_run_id,
                    "query_text": query_text,
                    "controlled_term": term,
                    "date_term": date_term,
                    "locality": near.get("place_text") or "",
                    "target_state": near.get("state") or "",
                    "query_url": materialize_query_url(endpoint_url, query_text, endpoint_type),
                    "status": "queued",
                    "priority_score": priority(near, query_text, date_term, str(near.get("place_text") or ""), {"target_queries": {"priority_states": ["WA", "SA", "NT", "TAS", "ACT"]}}),
                    "created_at": now_iso(),
                    "attempted_at": "",
                    "notes": f"rebuilt from materialized near miss {near.get('near_miss_id')}: {reason}",
                }
                if execute:
                    before = conn.total_changes
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO noauth_endpoint_queries (
                            endpoint_query_id, endpoint_id, run_id, query_text, controlled_term,
                            date_term, locality, target_state, query_url, status, priority_score,
                            created_at, attempted_at, notes
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        tuple(row.values()),
                    )
                    if conn.total_changes > before:
                        added += 1
                else:
                    added += 1
            rows_written += added
            inserted_by_type[near.get("near_miss_type") or "UNKNOWN"] += added
            recommendations.append({"near_miss_id": near.get("near_miss_id"), "near_miss_type": near.get("near_miss_type"), "action": "queries_added" if added else "already_present", "reason": reason, "queries_added": added})
        if execute:
            conn.commit()

    report_csv = out.with_suffix(".csv")
    write_csv(report_csv, recommendations, ["near_miss_id", "near_miss_type", "action", "reason", "queries_added"])
    lines = [
        "# Enriched Structured Query Rebuild Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Base run ID: `{run_id}`",
        f"- New run ID: `{new_run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Materialized near misses reviewed: `{len(recommendations)}`",
        f"- New endpoint queries written: `{rows_written}`",
        f"- Recommendation CSV: `{report_csv}`",
        "- Query expansion is skipped for detail-required and adapter-fix near misses.",
        "",
        "## Queries Added By Near-Miss Type",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in inserted_by_type.most_common()] or ["- None"])
    lines.extend(["", "## Skipped By Near-Miss Type"])
    lines.extend([f"- `{key}`: {value}" for key, value in skipped_by_type.most_common()] or ["- None"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"near_misses": len(recommendations), "queries_written": rows_written, "out": str(out), "csv": str(report_csv)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--new-run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(rebuild(Path(args.db), args.run_id, args.new_run_id, Path(args.out), execute=bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
