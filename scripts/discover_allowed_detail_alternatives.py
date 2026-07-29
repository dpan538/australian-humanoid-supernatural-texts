#!/usr/bin/env python3
"""Discover robots-allowed endpoint-native detail alternatives for near misses."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.structured_robots_rescue import diagnose_robots, ensure_near_miss_tables, joined_near_misses, parse_existing_metadata, same_domain, url_issue


FIELDS = ["near_miss_id", "original_detail_url", "alternative_url", "alternative_type", "robots_status", "safe_to_fetch", "reason", "priority_score"]


def alternative_for(near: dict[str, object]) -> tuple[str, str, str, int]:
    endpoint_type = str(near.get("endpoint_type") or "")
    metadata = parse_existing_metadata(near)
    item_url = str(metadata.get("item_url") or near.get("item_url") or near.get("detail_url") or "")
    endpoint_url = str(near.get("endpoint_url") or "")
    item_id = str(near.get("item_id") or "")
    if endpoint_type == "RSS_ATOM" and item_url:
        return item_url, "RSS_ITEM_LINK", "feed_entry_link", 80
    if endpoint_type == "ATOM_AtoM" and item_url and "informationobject/browse" not in item_url.lower():
        return item_url, "ATOM_ITEM_PAGE", "atom_item_like_url", 70
    if endpoint_type == "OAI_PMH" and endpoint_url and item_id:
        sep = "&" if "?" in endpoint_url else "?"
        return endpoint_url + sep + urlencode({"verb": "GetRecord", "metadataPrefix": "oai_dc", "identifier": item_id}), "OAI_GETRECORD", "oai_identifier_present", 85
    if endpoint_type == "OMEKA_API" and endpoint_url and item_id:
        base = endpoint_url.split("?", 1)[0].rstrip("/")
        if not base.endswith(str(item_id)):
            return f"{base}/{item_id}", "OMEKA_ITEM_API", "omeka_item_id_present", 85
    if endpoint_type == "WORDPRESS_REST" and endpoint_url and item_id.isdigit():
        base = endpoint_url.split("?", 1)[0].rstrip("/")
        base = base.rsplit("/", 1)[0] if base.endswith("/posts") is False else base
        return f"{base}/{item_id}", "WORDPRESS_REST_ITEM", "wordpress_post_id_present", 85
    for key in ["iiif_manifest_url", "linked_pdf_url"]:
        value = metadata.get(key)
        if value:
            return str(value), "IIIF_MANIFEST" if key == "iiif_manifest_url" else "LINKED_PDF", key, 60
    return "", "", "no_stable_endpoint_native_alternative", 0


def discover(db_path: Path, run_id: str, out: Path, report: Path, execute: bool) -> dict[str, object]:
    del execute
    ensure_near_miss_tables(db_path)
    rows: list[dict[str, object]] = []
    with sqlite3.connect(db_path) as conn:
        near_rows = joined_near_misses(conn, run_id)
    for near in near_rows:
        original = str(near.get("detail_url") or near.get("item_url") or "")
        alt, alt_type, reason, priority = alternative_for(near)
        safe = False
        robots_status = ""
        if alt and not url_issue({**near, "detail_url": alt}):
            if original and not same_domain(original, alt):
                reason = "alternative_off_original_domain"
            else:
                diag = diagnose_robots(alt)
                robots_status = diag.robots_status
                safe = bool(diag.allowed)
        elif alt:
            robots_status = url_issue({**near, "detail_url": alt})
        rows.append(
            {
                "near_miss_id": near.get("near_miss_id"),
                "original_detail_url": original,
                "alternative_url": alt,
                "alternative_type": alt_type,
                "robots_status": robots_status,
                "safe_to_fetch": "true" if safe else "false",
                "reason": reason,
                "priority_score": priority if safe else min(priority, 40),
            }
        )
    rows.sort(key=lambda row: (row["safe_to_fetch"] != "true", -int(row["priority_score"] or 0), str(row["near_miss_id"])))
    write_csv(out, rows, FIELDS)
    type_counts = Counter(str(row["alternative_type"] or "NONE") for row in rows)
    safe_count = sum(1 for row in rows if row["safe_to_fetch"] == "true")
    lines = [
        "# Allowed Detail Alternatives Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Alternatives considered: `{len(rows)}`",
        f"- Safe to fetch after explicit robots check: `{safe_count}`",
        f"- Output CSV: `{out}`",
        "",
        "## Alternative Types",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in sorted(type_counts.items())] or ["- None"])
    lines.extend(
        [
            "",
            "## Safety",
            "- Alternatives are endpoint-native only: feed links, OAI GetRecord, Omeka item APIs, WordPress item REST URLs, or linked IIIF/PDF metadata.",
            "- Robots UNKNOWN is not treated as allowed.",
            "- No broad frontier expansion or search-engine/API discovery is performed.",
        ]
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"alternatives": len(rows), "safe_to_fetch": safe_count, "types": dict(type_counts), "out": str(out), "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(discover(Path(args.db), args.run_id, Path(args.out), Path(args.report), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
