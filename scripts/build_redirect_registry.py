#!/usr/bin/env python3
"""Build canonical ID and URL redirect registries."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.final_release import canonical_url, stable_id
from migrate_redirect_registry_v1 import migrate


ID_FIELDS = ["redirect_id", "redirect_type", "from_id", "to_id", "from_slug", "to_slug", "source_table", "target_table", "reason", "confidence", "active", "created_at", "updated_at"]
URL_FIELDS = ["redirect_id", "from_url", "to_url", "url_role", "source_name", "redirect_status", "http_status_chain", "reason", "confidence", "active", "created_at", "updated_at"]


def slug(value: str) -> str:
    return str(value or "").lower().replace(" ", "-")[:120]


def build(db_path: Path, out_dir: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    id_rows = []
    url_rows = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        canon_by_key = {}
        for row in conn.execute("SELECT lead_id, duplicate_key, title FROM target_gap_leads WHERE duplicate_status IN ('canonical','unique')"):
            canon_by_key[row["duplicate_key"]] = dict(row)
        for row in conn.execute("SELECT lead_id, duplicate_key, title FROM target_gap_leads WHERE duplicate_status IN ('duplicate','probable_duplicate')"):
            target = canon_by_key.get(row["duplicate_key"])
            if not target:
                continue
            ts = now_iso()
            id_rows.append({"redirect_id": stable_id("redir_", row["lead_id"], target["lead_id"]), "redirect_type": "duplicate_lead_to_canonical", "from_id": row["lead_id"], "to_id": target["lead_id"], "from_slug": slug(row["title"]), "to_slug": slug(target["title"]), "source_table": "target_gap_leads", "target_table": "target_gap_leads", "reason": "duplicate_key_cluster", "confidence": 0.95, "active": 1, "created_at": ts, "updated_at": ts})
        for table, id_col, url_col, name_col in [("target_gap_leads", "lead_id", "url", "source_name"), ("release_metadata_gap_items", "release_item_id", "url", "source_name"), ("release_lead_overlay_items", "release_lead_id", "url", "source_name")]:
            if not conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]:
                continue
            for row in conn.execute(f"SELECT {id_col} AS id, {url_col} AS url, {name_col} AS source_name FROM {table} WHERE COALESCE({url_col},'')!='' LIMIT 20000"):
                target = canonical_url(row["url"])
                if target and target != row["url"]:
                    ts = now_iso()
                    url_rows.append({"redirect_id": stable_id("urlredir_", row["url"], target), "from_url": row["url"], "to_url": target, "url_role": "source_url", "source_name": row["source_name"], "redirect_status": "normalized", "http_status_chain": "", "reason": "source_url_canonicalization", "confidence": 0.9, "active": 1, "created_at": ts, "updated_at": ts})
        if execute:
            for row in id_rows:
                placeholders = ", ".join(["?"] * len(ID_FIELDS))
                updates = ", ".join(f"{field}=excluded.{field}" for field in ID_FIELDS if field not in {"redirect_id", "created_at"})
                conn.execute(f"INSERT INTO canonical_id_redirects ({', '.join(ID_FIELDS)}) VALUES ({placeholders}) ON CONFLICT(redirect_id) DO UPDATE SET {updates}", tuple(row[field] for field in ID_FIELDS))
            for row in url_rows:
                placeholders = ", ".join(["?"] * len(URL_FIELDS))
                updates = ", ".join(f"{field}=excluded.{field}" for field in URL_FIELDS if field not in {"redirect_id", "created_at"})
                conn.execute(f"INSERT INTO canonical_url_redirects ({', '.join(URL_FIELDS)}) VALUES ({placeholders}) ON CONFLICT(redirect_id) DO UPDATE SET {updates}", tuple(row[field] for field in URL_FIELDS))
            conn.commit()
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "canonical_id_redirects.csv", id_rows, ID_FIELDS)
    write_csv(out_dir / "canonical_url_redirects.csv", url_rows, URL_FIELDS)
    write_csv(out_dir / "duplicate_to_canonical_redirects.csv", id_rows, ID_FIELDS)
    (out_dir / "frontend_redirects.json").write_text(json.dumps({"id_redirects": id_rows[:5000], "url_redirects": url_rows[:5000]}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_csv(out_dir / "source_url_canonicalization.csv", url_rows, URL_FIELDS)
    report = out_dir / "redirect_registry_report.md"
    report.write_text("\n".join(["# Redirect Registry Report", "", f"- Generated: `{now_iso()}`", f"- ID redirects: `{len(id_rows)}`", f"- URL redirects: `{len(url_rows)}`", "- Duplicate rows deleted: `0`", "- Frontend routing changed: `no`"]) + "\n", encoding="utf-8")
    return {"id_redirects": len(id_rows), "url_redirects": len(url_rows), "out_dir": str(out_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), Path(args.out_dir), args.execute), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
