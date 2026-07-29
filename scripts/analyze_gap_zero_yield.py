#!/usr/bin/env python3
"""Analyze why a gap-targeted autoharvest run produced zero target records."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.autoharvest_gap import DEFAULT_TERMS, term_hit
from lib.temporal_evidence import classify_temporal_evidence
from migrate_autoharvest_gap_v2 import migrate


NEAR_MISS_FIELDS = [
    "candidate_id", "route_id", "source_name", "source_tier", "route_family", "target_state",
    "title", "url", "near_miss_category", "has_term", "has_date", "is_item_level",
    "item_format", "date_confidence", "term_hit_confidence", "item_level_confidence", "gate_reasons",
]


def parse_reasons(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data]
    except Exception:
        pass
    return [part for part in str(raw).split(";") if part]


def near_miss_category(row: dict[str, Any]) -> str:
    reasons = parse_reasons(row.get("gate_reasons_json"))
    text = " ".join([str(row.get("title") or ""), str(row.get("snippet") or ""), str(row.get("url") or "")])
    has_term = float(row.get("term_hit_confidence") or 0) >= 0.7 or term_hit(text, DEFAULT_TERMS)[0]
    has_date = float(row.get("date_confidence") or 0) >= 0.7 or bool(row.get("temporal_evidence_type"))
    item_format = row.get("item_format") or ""
    is_item = float(row.get("item_level_confidence") or 0) >= 0.7 or item_format in {"CATALOGUE_ITEM", "SERIAL_ISSUE_ITEM", "ARTICLE_PAGE", "PDF_ISSUE", "BROADCAST_ITEM", "ARCHIVE_FINDING_AID_ITEM"}
    url = str(row.get("url") or "").lower()
    title = str(row.get("title") or "").lower()
    if url.endswith(".pdf") or ".pdf" in url:
        return "PDF_LINK_NOT_PROCESSED" if not has_date or not has_term else "DATE_TERM_NOT_ITEM_LEVEL"
    if "newsletter" in title or "journal" in title or "bulletin" in title or item_format in {"SERIAL_ISSUE_ITEM", "PDF_ISSUE"}:
        if has_term and not has_date:
            return "POSSIBLE_NEWSLETTER"
        return "POSSIBLE_SERIAL_ISSUE"
    if "catalogue" in title or item_format == "CATALOGUE_ITEM":
        return "POSSIBLE_CATALOGUE_RESULT"
    if item_format == "BROADCAST_ITEM" or "broadcast" in title or "radio" in title or "abc" in title:
        return "POSSIBLE_BROADCAST_METADATA"
    if "search" in item_format or any("search" in reason for reason in reasons):
        return "SEARCH_FORM_NOT_USED"
    if any(reason.startswith("not_item_level") for reason in reasons) or item_format == "DIRECTORY_PAGE":
        if has_term and has_date:
            return "DATE_TERM_NOT_ITEM_LEVEL"
        return "DIRECTORY_ONLY"
    if has_term and not has_date:
        return "TERM_NO_DATE"
    if has_date and not has_term:
        return "DATE_NO_TERM"
    if is_item and not has_date:
        return "ITEM_NO_DATE"
    if is_item and not has_term:
        return "ITEM_NO_TERM"
    return "SITEMAP_ONLY_NO_ITEM"


def analyze(db_path: Path, run_id: str, out_dir: Path) -> dict[str, int]:
    migrate(db_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        candidates = [dict(row) for row in conn.execute("SELECT * FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchall()]
        provisional = [dict(row) for row in conn.execute("SELECT * FROM provisional_records WHERE run_id=?", (run_id,)).fetchall()]
        routes = [dict(row) for row in conn.execute("SELECT * FROM harvest_route_stats WHERE run_id=?", (run_id,)).fetchall()]
    failure_counts: Counter[str] = Counter()
    near_misses: list[dict[str, Any]] = []
    route_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in candidates:
        reasons = parse_reasons(row.get("gate_reasons_json"))
        for reason in reasons:
            if "missing_explicit_target_temporal_evidence" in reason:
                failure_counts["missing_explicit_1926_1976_evidence"] += 1
            elif "missing_controlled_term" in reason:
                failure_counts["missing_controlled_term"] += 1
            elif reason.startswith("not_item_level"):
                failure_counts["not_item_level"] += 1
            elif "duplicate" in reason:
                failure_counts["duplicate"] += 1
            elif "noise" in reason or "tourism" in reason:
                failure_counts["noise_or_tourism"] += 1
            else:
                failure_counts[reason] += 1
        category = near_miss_category(row)
        route_counts[str(row.get("route_id") or "")][category] += 1
        if category not in {"SITEMAP_ONLY_NO_ITEM"}:
            text = " ".join([str(row.get("title") or ""), str(row.get("snippet") or ""), str(row.get("url") or "")])
            near_misses.append(
                {
                    "candidate_id": row.get("candidate_id"),
                    "route_id": row.get("route_id"),
                    "source_name": row.get("source_name"),
                    "source_tier": row.get("source_tier"),
                    "route_family": row.get("route_family"),
                    "target_state": row.get("target_state"),
                    "title": row.get("title"),
                    "url": row.get("url"),
                    "near_miss_category": category,
                    "has_term": int(term_hit(text, DEFAULT_TERMS)[0] or float(row.get("term_hit_confidence") or 0) >= 0.7),
                    "has_date": int(float(row.get("date_confidence") or 0) >= 0.7 or bool(row.get("temporal_evidence_type"))),
                    "is_item_level": int(float(row.get("item_level_confidence") or 0) >= 0.7),
                    "item_format": row.get("item_format"),
                    "date_confidence": row.get("date_confidence"),
                    "term_hit_confidence": row.get("term_hit_confidence"),
                    "item_level_confidence": row.get("item_level_confidence"),
                    "gate_reasons": ";".join(reasons),
                }
            )
    aux_counts = Counter(row.get("auxiliary_status") or "unknown" for row in provisional if not row.get("target_gap_eligible"))
    route_failures: list[dict[str, Any]] = []
    for route_id, counts in route_counts.items():
        aux = sum(1 for row in provisional if row.get("route_id") == route_id and not row.get("target_gap_eligible"))
        target = sum(1 for row in provisional if row.get("route_id") == route_id and row.get("target_gap_eligible"))
        route_failures.append(
            {
                "route_id": route_id,
                "auxiliary_records": aux,
                "target_records": target,
                "term_no_date": counts.get("TERM_NO_DATE", 0),
                "date_no_term": counts.get("DATE_NO_TERM", 0),
                "directory_only": counts.get("DIRECTORY_ONLY", 0),
                "possible_pdf": counts.get("PDF_LINK_NOT_PROCESSED", 0),
                "possible_serial": counts.get("POSSIBLE_SERIAL_ISSUE", 0) + counts.get("POSSIBLE_NEWSLETTER", 0),
                "recommended_action": "PAUSE_AUXILIARY_ONLY_ROUTE" if aux >= 20 and target == 0 else "REPROBE_WITH_ADAPTER",
            }
        )
    surface_rows = []
    for row in route_failures:
        action = row["recommended_action"]
        if row["possible_pdf"]:
            action = "PROBE_PUBLIC_PDF_SNIPPETS"
        elif row["possible_serial"]:
            action = "PROBE_NEWSLETTER_ARCHIVE"
        elif row["term_no_date"] or row["date_no_term"]:
            action = "PROBE_CATALOGUE_HTML_ADAPTER"
        surface_rows.append({**row, "surface_diagnosis": action})
    write_csv(out_dir / "candidate_gate_failure_breakdown.csv", [{"failure_reason": k, "count": v} for k, v in failure_counts.most_common()], ["failure_reason", "count"])
    write_csv(out_dir / "auxiliary_reason_breakdown.csv", [{"auxiliary_status": k, "count": v} for k, v in aux_counts.most_common()], ["auxiliary_status", "count"])
    write_csv(out_dir / "route_failure_breakdown.csv", route_failures, list(route_failures[0].keys()) if route_failures else ["route_id"])
    write_csv(out_dir / "near_miss_candidates.csv", near_misses[:5000], NEAR_MISS_FIELDS)
    write_csv(out_dir / "route_surface_diagnosis.csv", surface_rows, list(surface_rows[0].keys()) if surface_rows else ["route_id"])
    lines = [
        "# Gap Zero-Yield Postmortem",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Candidates inspected: `{len(candidates)}`",
        f"- Provisional auxiliary records inspected: `{len(provisional)}`",
        f"- Target records: `{sum(1 for row in provisional if row.get('target_gap_eligible'))}`",
        "",
        "## Top Failure Reasons",
    ]
    lines.extend([f"- `{k}`: {v}" for k, v in failure_counts.most_common(12)] or ["- None"])
    lines.extend(["", "## Auxiliary Breakdown"])
    lines.extend([f"- `{k}`: {v}" for k, v in aux_counts.most_common()] or ["- None"])
    lines.extend(["", "## Diagnosis", "The previous frontier produced safe auxiliary material but no complete target-gap item/date/term combination. Reprobe with PDF/newsletter/search-form/catalogue adapters before resuming the full marathon."])
    (out_dir / "zero_yield_postmortem.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"candidates": len(candidates), "near_misses": len(near_misses), "routes": len(route_failures)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(analyze(Path(args.db), args.run_id, Path(args.out_dir)))


if __name__ == "__main__":
    main()
