#!/usr/bin/env python3
"""Build target-gap query rows for noauth structured endpoints."""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from migrate_structured_endpoint_harvest_v1 import migrate


NO_QUERY_TYPES = {"RSS_ATOM", "IIIF", "JSON_LD"}


def query_id(endpoint_id: str, run_id: str, query_text: str, locality: str, date_term: str) -> str:
    raw = "|".join([endpoint_id, run_id, query_text, locality, date_term])
    return "epq_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def materialize_query_url(endpoint_url: str, query_text: str, endpoint_type: str) -> str:
    if endpoint_type in NO_QUERY_TYPES:
        return endpoint_url
    q = quote_plus(query_text)
    if "{query}" in endpoint_url:
        return endpoint_url.replace("{query}", q)
    if endpoint_type == "OAI_PMH":
        return endpoint_url
    sep = "&" if "?" in endpoint_url else "?"
    return f"{endpoint_url}{sep}q={q}"


def priority(endpoint: dict, query_text: str, date_term: str, locality: str, config: dict) -> int:
    score = 0
    states = set(config.get("target_queries", {}).get("priority_states", []))
    if endpoint.get("state") in states:
        score += 50
    if date_term in {"1950", "1950s", "1960", "1960s", "1970", "1970s", "1976"}:
        score += 35
    elif date_term:
        score += 25
    if locality:
        score += 20
    if endpoint.get("source_tier") == "A":
        score += 25
    elif endpoint.get("source_tier") in {"B", "C"}:
        score += 15
    if endpoint.get("endpoint_type") in {"OAI_PMH", "OMEKA_API", "ATOM_AtoM", "WORDPRESS_REST", "RSS_ATOM", "IIIF"}:
        score += 15
    if len(query_text.split()) >= 3:
        score += 10
    return score


def generate_queries(endpoint: dict, config: dict) -> list[dict]:
    if endpoint.get("status") in {"disallowed", "paused", "rejected"}:
        return []
    terms = config.get("target_queries", {}).get("controlled_terms", [])[:8]
    dates = config.get("target_queries", {}).get("date_terms", [])[:8]
    localities_by_state = config.get("target_queries", {}).get("priority_localities", {})
    state = endpoint.get("state") or ""
    localities = (localities_by_state.get(state) or [state])[:3]
    rows: list[dict] = []
    if endpoint.get("endpoint_type") in NO_QUERY_TYPES:
        rows.append({"query_text": "", "controlled_term": "", "date_term": "", "locality": "", "target_state": state})
        return rows
    for term in terms:
        rows.append({"query_text": term, "controlled_term": term, "date_term": "", "locality": "", "target_state": state})
        for locality in localities:
            if locality:
                rows.append({"query_text": f"{term} {locality}", "controlled_term": term, "date_term": "", "locality": locality, "target_state": state})
        for date in dates[:4]:
            rows.append({"query_text": f"{term} {date}", "controlled_term": term, "date_term": date, "locality": "", "target_state": state})
            for locality in localities[:2]:
                if locality:
                    rows.append({"query_text": f"{term} {locality} {date}", "controlled_term": term, "date_term": date, "locality": locality, "target_state": state})
    # OAI-PMH usually lacks arbitrary server-side search; one client-side query is enough.
    if endpoint.get("endpoint_type") == "OAI_PMH":
        return rows[:1]
    return rows[:50]


def build(db_path: Path, config_path: Path, run_id: str, out: Path, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    rows_written = 0
    endpoints_seen = 0
    counts = Counter()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        endpoints = [dict(row) for row in conn.execute("SELECT * FROM noauth_endpoint_inventory WHERE status='active' AND noauth_verified=1 AND api_key_required=0 AND login_required=0 AND paywall_required=0")]
        endpoints_seen = len(endpoints)
        for endpoint in endpoints:
            for q in generate_queries(endpoint, config):
                qurl = materialize_query_url(endpoint["endpoint_url"], q["query_text"], endpoint["endpoint_type"])
                row = {
                    "endpoint_query_id": query_id(endpoint["endpoint_id"], run_id, q["query_text"], q["locality"], q["date_term"]),
                    "endpoint_id": endpoint["endpoint_id"],
                    "run_id": run_id,
                    "query_text": q["query_text"],
                    "controlled_term": q["controlled_term"],
                    "date_term": q["date_term"],
                    "locality": q["locality"],
                    "target_state": q["target_state"],
                    "query_url": qurl,
                    "status": "queued",
                    "priority_score": priority(endpoint, q["query_text"], q["date_term"], q["locality"], config),
                    "created_at": now_iso(),
                    "attempted_at": "",
                    "notes": "no credential structured endpoint query",
                }
                if execute:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO noauth_endpoint_queries (
                            endpoint_query_id, endpoint_id, run_id, query_text, controlled_term,
                            date_term, locality, target_state, query_url, status, priority_score,
                            created_at, attempted_at, notes
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        tuple(row.values()),
                    )
                rows_written += 1
                counts[endpoint["endpoint_type"]] += 1
        if execute:
            conn.commit()
    out.parent.mkdir(parents=True, exist_ok=True)
    count_lines = [f"- `{key}`: {value}" for key, value in counts.most_common()] or ["- None"]
    lines = [
        "# Structured Endpoint Query Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Endpoints with queries: `{endpoints_seen}`",
        f"- Query rows generated: `{rows_written}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "",
        "## Query Rows By Endpoint Type",
        *count_lines,
        "",
        "## Next Command",
        "`make structured-endpoint-start`",
    ]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"endpoints": endpoints_seen, "queries": rows_written}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(build(Path(args.db), Path(args.config), args.run_id, Path(args.out), execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
