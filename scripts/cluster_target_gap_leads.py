#!/usr/bin/env python3
"""Cluster target-gap leads for high-level planning."""

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
from lib.target_gap_leads import domain_for, read_leads, stable_id
from migrate_target_gap_leads_v1 import migrate


CLUSTER_FIELDS = ["cluster_id", "cluster_type", "cluster_label", "lead_count", "max_lead_score", "representative_lead_id", "recommended_action", "created_at", "updated_at"]


def build_cluster(cluster_type: str, label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    rows = sorted(rows, key=lambda row: (-float(row.get("lead_score") or 0), str(row.get("lead_id") or "")))
    return {
        "cluster_id": stable_id("tglc_", cluster_type, label),
        "cluster_type": cluster_type,
        "cluster_label": label or "unknown",
        "lead_count": len(rows),
        "max_lead_score": rows[0].get("lead_score") if rows else 0,
        "representative_lead_id": rows[0].get("lead_id") if rows else "",
        "recommended_action": rows[0].get("recommended_next_action") if rows else "keep_as_lead",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def cluster(db_path: Path, out: Path, execute: bool) -> dict[str, Any]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        leads = read_leads(conn)
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for row in leads:
            group_values = {
                "source_route": row.get("route_family") or row.get("source_name") or "",
                "domain": domain_for(row.get("url") or ""),
                "state": row.get("target_state") or "",
                "time_signal": row.get("temporal_signal") or "",
                "lead_type": row.get("lead_type") or "",
                "constraint_blocker": row.get("constraint_blocker") or "",
                "term_family": row.get("term_signal") or "",
                "place": row.get("place_signal") or row.get("target_locality") or "",
            }
            if row.get("source_tier") == "D" or "d_class" in str(row.get("evidence_gap") or ""):
                group_values["d_class_access_platform"] = row.get("source_name") or row.get("source_family") or "D-class"
            if "robots" in str(row.get("constraint_blocker") or ""):
                group_values["robots_domain"] = domain_for(row.get("url") or "") or row.get("source_name") or "robots"
            for ctype, label in group_values.items():
                if label:
                    groups[(ctype, str(label))].append(row)
        clusters = [build_cluster(ctype, label, rows) for (ctype, label), rows in groups.items()]
        clusters.sort(key=lambda row: (-int(row["lead_count"]), -float(row["max_lead_score"] or 0), row["cluster_type"], row["cluster_label"]))
        if execute:
            for row in clusters:
                placeholders = ", ".join(["?"] * len(CLUSTER_FIELDS))
                updates = ", ".join(f"{field}=excluded.{field}" for field in CLUSTER_FIELDS if field not in {"cluster_id", "created_at"})
                conn.execute(f"INSERT INTO target_gap_lead_clusters ({', '.join(CLUSTER_FIELDS)}) VALUES ({placeholders}) ON CONFLICT(cluster_id) DO UPDATE SET {updates}", tuple(row.get(field) for field in CLUSTER_FIELDS))
            conn.commit()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out.parent / "lead_clusters.csv", clusters, CLUSTER_FIELDS)
    write_csv(out.parent / "top_route_clusters.csv", [row for row in clusters if row["cluster_type"] == "source_route"][:50], CLUSTER_FIELDS)
    write_csv(out.parent / "top_robots_blocked_clusters.csv", [row for row in clusters if row["cluster_type"] == "robots_domain"][:50], CLUSTER_FIELDS)
    write_csv(out.parent / "top_d_class_clusters.csv", [row for row in clusters if row["cluster_type"] == "d_class_access_platform"][:50], CLUSTER_FIELDS)
    write_csv(out.parent / "top_metadata_only_1955_1976_clusters.csv", [row for row in clusters if "metadata" in row["cluster_label"].lower() or row["cluster_type"] == "time_signal"][:50], CLUSTER_FIELDS)
    lines = [
        "# Target-Gap Lead Cluster Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Leads clustered: `{len(leads)}`",
        f"- Clusters written: `{len(clusters)}`",
        "",
        "## Top Clusters",
    ]
    lines.extend([f"- `{row['cluster_type']}` / `{row['cluster_label']}`: {row['lead_count']} leads, max score {row['max_lead_score']}" for row in clusters[:20]] or ["- None"])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"leads": len(leads), "clusters": len(clusters), "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(cluster(Path(args.db), Path(args.out), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
