#!/usr/bin/env python3
"""Validate final redirect registry."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from migrate_redirect_registry_v1 import migrate


FIELDS = ["check", "status", "details"]


def validate(db_path: Path, redirect_dir: Path, out: Path) -> dict[str, object]:
    migrate(db_path)
    results = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        id_rows = [dict(row) for row in conn.execute("SELECT * FROM canonical_id_redirects WHERE active=1")]
        url_rows = [dict(row) for row in conn.execute("SELECT * FROM canonical_url_redirects WHERE active=1")]
        lead_ids = {row[0] for row in conn.execute("SELECT lead_id FROM target_gap_leads")} if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='target_gap_leads'").fetchone()[0] else set()
    edges = {row["from_id"]: row["to_id"] for row in id_rows}
    loops = []
    for start in edges:
        seen = set()
        cur = start
        while cur in edges:
            if cur in seen:
                loops.append(start)
                break
            seen.add(cur)
            cur = edges[cur]
    dangling = [row for row in id_rows if row["target_table"] == "target_gap_leads" and row["to_id"] not in lead_ids]
    multi = {}
    for row in id_rows:
        multi.setdefault(row["from_id"], set()).add(row["to_id"])
    multi_bad = {key: value for key, value in multi.items() if len(value) > 1}
    bad_urls = [row for row in url_rows if urlparse(row["from_url"]).scheme not in {"http", "https"} or urlparse(row["to_url"]).scheme not in {"http", "https"}]
    role_confusion = [row for row in url_rows if row.get("url_role") == "evidence_source" and "archive.org" in row.get("to_url", "")]
    try:
        json.loads((redirect_dir / "frontend_redirects.json").read_text(encoding="utf-8"))
        json_ok = True
    except Exception:
        json_ok = False
    checks = [
        ("no_redirect_loops", not loops, f"{len(loops)} loops"),
        ("no_dangling_target_ids", not dangling, f"{len(dangling)} dangling"),
        ("no_duplicate_active_from_id", not multi_bad, f"{len(multi_bad)} duplicate from_id mappings"),
        ("no_invalid_url_schemes", not bad_urls, f"{len(bad_urls)} invalid URL redirects"),
        ("no_evidence_access_role_confusion", not role_confusion, f"{len(role_confusion)} role confusion rows"),
        ("frontend_redirects_json_valid", json_ok, "valid JSON" if json_ok else "invalid JSON"),
        ("old_id_resolves_to_canonical", not loops and not dangling, f"{len(id_rows)} active ID redirects"),
    ]
    for name, ok, details in checks:
        results.append({"check": name, "status": "PASS" if ok else "FAIL", "details": details})
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out.with_suffix(".csv"), results, FIELDS)
    status = "PASS" if all(row["status"] == "PASS" for row in results) else "FAIL"
    lines = ["# Redirect Validation Report", "", f"- Generated: `{now_iso()}`", f"- Status: `{status}`", f"- ID redirects: `{len(id_rows)}`", f"- URL redirects: `{len(url_rows)}`", "", "## Checks"]
    lines.extend([f"- `{row['check']}`: {row['status']} - {row['details']}" for row in results])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"status": status, "id_redirects": len(id_rows), "url_redirects": len(url_rows), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(validate(Path(args.db), Path(args.redirect_dir), Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
