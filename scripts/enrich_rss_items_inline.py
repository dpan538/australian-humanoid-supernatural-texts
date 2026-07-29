#!/usr/bin/env python3
"""Enrich RSS/Atom near misses from already-fetched feed entry metadata."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.structured_robots_rescue import (
    diagnose_robots,
    ensure_near_miss_tables,
    joined_near_misses,
    load_default_config,
    parse_existing_metadata,
    score_metadata_only,
    url_issue,
    write_enriched_csv,
)


def enrich_rss_inline(db_path: Path, run_id: str, out_dir: Path, execute: bool, config_path: Path | None = None) -> dict[str, Any]:
    ensure_near_miss_tables(db_path)
    config = load_default_config(config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    processed: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    remaining: list[dict[str, Any]] = []
    allowed_queue: list[dict[str, Any]] = []
    blocked_queue: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as conn:
        rows = joined_near_misses(conn, run_id, "n.endpoint_type='RSS_ATOM'")
        for near in rows:
            metadata = parse_existing_metadata(near)
            result = score_metadata_only(conn, near, metadata, run_id, config, "structured_rss_inline_gap", execute)
            processed.append(result)
            if int(result.get("target_gap_eligible") or 0) == 1:
                targets.append(result)
            else:
                remaining.append(result)
            issue = url_issue(near)
            diagnosis = diagnose_robots(str(near.get("detail_url") or near.get("item_url") or "")) if (near.get("detail_url") or near.get("item_url")) and not issue else None
            queue_row = {
                "near_miss_id": near.get("near_miss_id"),
                "detail_url": near.get("detail_url") or near.get("item_url"),
                "url_issue": issue,
                "robots_status": diagnosis.robots_status if diagnosis else issue,
                "safe_to_fetch": "true" if diagnosis and diagnosis.allowed and not issue else "false",
                "reason": "robots_explicitly_allowed" if diagnosis and diagnosis.allowed and not issue else "blocked_or_uncertain",
            }
            (allowed_queue if queue_row["safe_to_fetch"] == "true" else blocked_queue).append(queue_row)
        if execute:
            conn.commit()
    write_enriched_csv(out_dir / "rss_inline_target_candidates.csv", targets)
    write_enriched_csv(out_dir / "rss_inline_near_misses_remaining.csv", remaining)
    write_csv(out_dir / "rss_detail_fetch_queue_allowed.csv", allowed_queue, ["near_miss_id", "detail_url", "url_issue", "robots_status", "safe_to_fetch", "reason"])
    write_csv(out_dir / "rss_detail_fetch_queue_blocked.csv", blocked_queue, ["near_miss_id", "detail_url", "url_issue", "robots_status", "safe_to_fetch", "reason"])
    remaining_counts = Counter(row.get("remaining_gate") or "TARGET_GAP_ELIGIBLE" for row in processed)
    lines = [
        "# RSS Inline Enrichment Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- RSS/Atom near misses processed: `{len(processed)}`",
        f"- Target candidates staged: `{len(targets)}`",
        f"- Remaining near misses: `{len(remaining)}`",
        f"- Allowed detail queue rows: `{len(allowed_queue)}`",
        f"- Blocked detail queue rows: `{len(blocked_queue)}`",
        "- Feed/item publish dates are not treated as target evidence unless the item metadata or text itself gives a 1926-1976 record, narrative, or coverage date.",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Remaining Gates",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(remaining_counts.items()) if key != "TARGET_GAP_ELIGIBLE"] or ["- None"])
    (out_dir / "rss_inline_enrichment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "processed": len(processed),
        "target_gap_records": len(targets),
        "remaining": len(remaining),
        "allowed_detail_queue": len(allowed_queue),
        "blocked_detail_queue": len(blocked_queue),
        "remaining_by_gate": dict(remaining_counts),
        "out_dir": str(out_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--config")
    args = parser.parse_args()
    print(json.dumps(enrich_rss_inline(Path(args.db), args.run_id, Path(args.out_dir), bool(args.execute and not args.dry_run), Path(args.config) if args.config else None), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
