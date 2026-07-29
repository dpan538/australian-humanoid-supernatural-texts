#!/usr/bin/env python3
"""Diagnose why structured endpoint near misses cannot safely fetch detail pages."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.structured_robots_rescue import (
    diagnose_robots,
    ensure_near_miss_tables,
    joined_near_misses,
    recommended_recovery_path,
    robots_url_for,
    url_issue,
)


FIELDS = [
    "near_miss_id",
    "near_miss_type",
    "endpoint_type",
    "source_name",
    "item_url",
    "detail_url",
    "domain",
    "robots_url",
    "robots_status",
    "robots_error",
    "http_status_if_known",
    "url_issue",
    "can_fetch_detail_safely",
    "recommended_recovery_path",
]


def audit(db_path: Path, run_id: str, out_dir: Path) -> dict[str, object]:
    ensure_near_miss_tables(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    domain_status: dict[str, dict[str, object]] = {}
    malformed: list[dict[str, object]] = []
    with sqlite3.connect(db_path) as conn:
        near_rows = joined_near_misses(conn, run_id)
    for near in near_rows:
        detail_url = str(near.get("detail_url") or near.get("item_url") or "")
        issue = url_issue(near)
        diagnosis = None
        if detail_url and issue not in {"DETAIL_URL_MISSING", "DETAIL_URL_MALFORMED", "DETAIL_URL_LOGIN_OR_AUTH", "DETAIL_URL_ARCHIVED_OR_ACCESS_PLATFORM", "DETAIL_URL_OFF_DOMAIN"}:
            diagnosis = diagnose_robots(detail_url)
        else:
            diagnosis = type("D", (), {"robots_status": issue or "DETAIL_URL_MISSING", "robots_url": robots_url_for(detail_url), "robots_error": issue, "http_status_if_known": "", "allowed": False})()
        safe = bool(diagnosis.allowed and not issue)
        route = recommended_recovery_path(near, issue, diagnosis.robots_status)
        domain = urlparse(detail_url).netloc.lower()
        row = {
            "near_miss_id": near.get("near_miss_id"),
            "near_miss_type": near.get("near_miss_type"),
            "endpoint_type": near.get("endpoint_type"),
            "source_name": near.get("source_name"),
            "item_url": near.get("item_url"),
            "detail_url": detail_url,
            "domain": domain,
            "robots_url": diagnosis.robots_url,
            "robots_status": diagnosis.robots_status,
            "robots_error": diagnosis.robots_error,
            "http_status_if_known": diagnosis.http_status_if_known,
            "url_issue": issue,
            "can_fetch_detail_safely": "true" if safe else "false",
            "recommended_recovery_path": route,
        }
        rows.append(row)
        diagnostics.append(row | {"endpoint_url": near.get("endpoint_url"), "base_url": near.get("base_url")})
        if issue:
            malformed.append(row)
        if domain:
            status_row = domain_status.setdefault(domain, {"domain": domain, "robots_url": diagnosis.robots_url, "robots_status": diagnosis.robots_status, "near_misses": 0, "safe_to_fetch": 0})
            status_row["near_misses"] = int(status_row["near_misses"]) + 1
            if safe:
                status_row["safe_to_fetch"] = int(status_row["safe_to_fetch"]) + 1
    status_counts = Counter(str(row["robots_status"]) for row in rows)
    issue_counts = Counter(str(row["url_issue"] or "NO_URL_ISSUE") for row in rows)
    path_counts = Counter(str(row["recommended_recovery_path"]) for row in rows)
    write_csv(out_dir / "robots_block_audit.csv", rows, FIELDS)
    write_csv(out_dir / "detail_url_diagnostics.csv", diagnostics, FIELDS + ["endpoint_url", "base_url"])
    write_csv(out_dir / "domain_robots_status.csv", list(domain_status.values()), ["domain", "robots_url", "robots_status", "near_misses", "safe_to_fetch"])
    write_csv(out_dir / "malformed_or_missing_detail_urls.csv", malformed, FIELDS)
    lines = [
        "# Robots Block Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Near misses audited: `{len(rows)}`",
        f"- Safe detail fetch rows: `{sum(1 for row in rows if row['can_fetch_detail_safely'] == 'true')}`",
        "",
        "## Robots Status",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(status_counts.items())] or ["- None"])
    lines.extend(["", "## URL Issues"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(issue_counts.items())] or ["- None"])
    lines.extend(["", "## Recommended Recovery Paths"])
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(path_counts.items())] or ["- None"])
    lines.extend(
        [
            "",
            "## Interpretation",
            "- `ROBOTS_EXPLICITLY_DENIED` means detail fetch is held.",
            "- `ROBOTS_UNKNOWN_*` means uncertainty is blocked closed, not treated as permission.",
            "- Missing, malformed, off-domain, login/auth, access-platform, and endpoint-duplicate URLs are separated from robots decisions.",
            "- Endpoint-native inline metadata paths remain available without network detail fetches.",
        ]
    )
    (out_dir / "robots_block_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "near_misses": len(rows),
        "safe_detail_fetches": sum(1 for row in rows if row["can_fetch_detail_safely"] == "true"),
        "robots_status_counts": dict(status_counts),
        "url_issue_counts": dict(issue_counts),
        "recommended_recovery_paths": dict(path_counts),
        "out_dir": str(out_dir),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(Path(args.db), args.run_id, Path(args.out_dir)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
