#!/usr/bin/env python3
"""Fetch and enrich only robots-allowed detail alternatives."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.structured_endpoint_recovery import USER_AGENT, parse_html_metadata, parse_json_metadata, parse_oai_record
from lib.structured_robots_rescue import (
    diagnose_robots,
    ensure_near_miss_tables,
    joined_near_misses,
    load_alternatives,
    load_default_config,
    score_metadata_only,
    write_enriched_csv,
)


def fetch_alternative_url(url: str, session: requests.Session, timeout: float = 10.0) -> tuple[int, str, str]:
    try:
        time.sleep(0.25)
        response = session.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, application/xml, text/xml, text/html;q=0.8"}, timeout=(3.0, timeout), allow_redirects=True)
    except Exception as exc:
        return 0, "", exc.__class__.__name__
    return response.status_code, (response.text or "")[:2_000_000], response.headers.get("content-type", "")


def parse_body(text: str, content_type: str, endpoint_type: str, url: str) -> dict[str, Any]:
    if "json" in content_type.lower() or text.lstrip().startswith(("{", "[")):
        return parse_json_metadata(text, endpoint_type)
    if "xml" in content_type.lower() or "<OAI-PMH" in text[:500] or text.lstrip().startswith("<OAI"):
        return parse_oai_record(text)
    return parse_html_metadata(text, url)


def enrich_alternatives(db_path: Path, alternatives: Path, run_id: str, limit: int, execute: bool) -> dict[str, Any]:
    ensure_near_miss_tables(db_path)
    config = load_default_config()
    alt_rows = [row for row in load_alternatives(alternatives) if str(row.get("safe_to_fetch") or "").lower() == "true" and row.get("alternative_url")][:limit]
    processed: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    statuses: Counter[str] = Counter()
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        near_by_id = {row["near_miss_id"]: row for row in joined_near_misses(conn, run_id)}
        for alt in alt_rows:
            url = str(alt.get("alternative_url") or "")
            near = near_by_id.get(alt.get("near_miss_id"))
            if not near:
                statuses["missing_near_miss"] += 1
                continue
            diag = diagnose_robots(url)
            if not diag.allowed:
                statuses[diag.robots_status] += 1
                remaining.append({"near_miss_id": near.get("near_miss_id"), "remaining_gate": "STILL_ROBOTS_DETAIL_REQUIRED", "target_gap_eligible": 0, "title": near.get("title")})
                continue
            status, text, content_type = fetch_alternative_url(url, session)
            if status != 200 or not text:
                statuses[f"fetch_failed_{status}"] += 1
                remaining.append({"near_miss_id": near.get("near_miss_id"), "remaining_gate": "STILL_ROBOTS_DETAIL_REQUIRED", "target_gap_eligible": 0, "title": near.get("title")})
                continue
            metadata = parse_body(text, content_type, str(near.get("endpoint_type") or ""), url)
            metadata.setdefault("metadata", {})
            metadata["metadata"]["fetched_alternative_url"] = url
            metadata["metadata"]["alternative_type"] = alt.get("alternative_type")
            near_for_score = dict(near)
            near_for_score["detail_url"] = url
            result = score_metadata_only(conn, near_for_score, metadata, run_id, config, "structured_allowed_detail_gap", execute)
            processed.append(result)
            statuses["enriched"] += 1
            if int(result.get("target_gap_eligible") or 0) == 1:
                targets.append(result)
            else:
                remaining.append(result)
        if execute:
            conn.commit()
    review_dir = ROOT / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"
    report_path = ROOT / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints" / "allowed_detail_enrichment_report.md"
    write_enriched_csv(review_dir / "allowed_detail_target_candidates.csv", targets)
    write_enriched_csv(review_dir / "allowed_detail_remaining_near_misses.csv", remaining)
    lines = [
        "# Allowed Detail Enrichment Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Safe alternatives attempted: `{len(alt_rows)}`",
        f"- Enriched records: `{len(processed)}`",
        f"- Target candidates staged: `{len(targets)}`",
        f"- Remaining near misses: `{len(remaining)}`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Statuses",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(statuses.items())] or ["- None"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"attempted": len(alt_rows), "enriched_records": len(processed), "target_gap_records": len(targets), "remaining": len(remaining), "statuses": dict(statuses), "report": str(report_path)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--alternatives", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(enrich_alternatives(Path(args.db), Path(args.alternatives), args.run_id, args.limit, bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
