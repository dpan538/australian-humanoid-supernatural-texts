#!/usr/bin/env python3
"""Cluster target-gap leads and mark duplicates without deleting rows."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.lead_intelligence import domain_slug, norm_title, norm_url
from lib.target_gap_leads import LEAD_FIELDS, read_leads
from migrate_target_gap_leads_v1 import migrate


CLUSTER_FIELDS = ["duplicate_key", "cluster_size", "canonical_lead_id", "duplicate_rule", "max_lead_score", "sample_title"]


def dedupe_key(row: dict[str, Any]) -> tuple[str, str]:
    source_row_id = str(row.get("source_row_id") or "").strip()
    source_table = str(row.get("source_table") or "").strip()
    url = norm_url(row.get("url"))
    title = norm_title(row.get("title"))
    source_name = norm_title(row.get("source_name"))
    locality = norm_title(row.get("target_locality") or row.get("place_signal") or row.get("target_state"))
    source_family = norm_title(row.get("source_family"))
    if url:
        return f"url:{url}", "exact_url"
    if source_row_id:
        return f"source_row:{source_table}:{source_row_id}", "source_row_id"
    if title and source_name:
        return f"title_source:{title}|{source_name}", "normalized_title_source"
    if title and locality and source_family:
        return f"title_locality_family:{title}|{locality}|{source_family}", "normalized_title_locality_source_family"
    slug = domain_slug(row.get("url"))
    if slug:
        return f"domain_slug:{slug}", "domain_slug"
    if "robots" in str(row.get("constraint_blocker") or "") and url:
        return f"robots_detail:{url}", "robots_blocked_detail_url"
    if row.get("source_table") == "structured_endpoint_near_misses" and source_row_id:
        return f"near_miss:{source_row_id}", "near_miss_lineage"
    return f"unique:{row.get('lead_id')}", "unique"


def dedupe(db_path: Path, out: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        rules: dict[str, str] = {}
        for row in leads:
            key, rule = dedupe_key(row)
            row["duplicate_key"] = key
            row["_duplicate_rule"] = rule
            groups[key].append(row)
            rules[key] = rule

        cluster_rows = []
        canonical_rows = []
        duplicate_rows = []
        status_updates: list[tuple[str, str, str]] = []
        for key, rows in groups.items():
            rows.sort(key=lambda row: (-float(row.get("lead_score") or 0), str(row.get("lead_id") or "")))
            canonical = rows[0]
            duplicate_rule = rules.get(key, "unique")
            if len(rows) == 1:
                canonical["duplicate_status"] = "unique"
                canonical_rows.append(canonical)
                status_updates.append((key, "unique", canonical["lead_id"]))
            else:
                canonical["duplicate_status"] = "canonical"
                canonical_rows.append(canonical)
                status_updates.append((key, "canonical", canonical["lead_id"]))
                for row in rows[1:]:
                    row["duplicate_status"] = "duplicate" if duplicate_rule in {"exact_url", "source_row_id", "robots_blocked_detail_url", "near_miss_lineage"} else "probable_duplicate"
                    duplicate_rows.append(row)
                    status_updates.append((key, row["duplicate_status"], row["lead_id"]))
            cluster_rows.append(
                {
                    "duplicate_key": key,
                    "cluster_size": len(rows),
                    "canonical_lead_id": canonical.get("lead_id"),
                    "duplicate_rule": duplicate_rule,
                    "max_lead_score": canonical.get("lead_score") or 0,
                    "sample_title": canonical.get("title") or "",
                }
            )
        if execute:
            for key, status, lead_id in status_updates:
                conn.execute("UPDATE target_gap_leads SET duplicate_key=?, duplicate_status=?, updated_at=? WHERE lead_id=?", (key, status, now_iso(), lead_id))
            conn.commit()
    cluster_rows.sort(key=lambda row: (-int(row["cluster_size"]), str(row["duplicate_key"])))
    canonical_rows.sort(key=lambda row: (-float(row.get("lead_score") or 0), str(row.get("lead_id") or "")))
    duplicate_rows.sort(key=lambda row: (str(row.get("duplicate_key") or ""), -float(row.get("lead_score") or 0)))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out.parent / "lead_duplicate_clusters.csv", cluster_rows, CLUSTER_FIELDS)
    write_csv(out.parent / "canonical_target_gap_leads.csv", canonical_rows, LEAD_FIELDS)
    write_csv(out.parent / "duplicate_leads.csv", duplicate_rows, LEAD_FIELDS)
    duplicate_count = len(duplicate_rows)
    lines = [
        "# Target-Gap Lead Dedupe Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Leads processed: `{len(leads)}`",
        f"- Canonical/unique leads: `{len(canonical_rows)}`",
        f"- Duplicate/probable duplicate leads: `{duplicate_count}`",
        "- Rows deleted: `0`",
        "- Public records mutated: `no`",
        "",
        "## Largest Duplicate Clusters",
    ]
    lines.extend([f"- `{row['duplicate_rule']}` / `{row['duplicate_key']}`: {row['cluster_size']} leads" for row in cluster_rows[:12] if int(row["cluster_size"]) > 1] or ["- None"])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads": len(leads), "canonical_leads": len(canonical_rows), "duplicate_leads": duplicate_count, "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(dedupe(Path(args.db), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
