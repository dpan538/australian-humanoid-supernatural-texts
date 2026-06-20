#!/usr/bin/env python3
"""Stage V2 collection candidates without lowering acceptance standards."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.collectors.manual_import import REQUIRED_MANUAL_COLUMNS
from aus_humanoid.collectors.trove import TroveCollector
from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "collection_500_progress.md"


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    tracking = {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    query = urlencode(
        [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k.lower() not in tracking],
        doseq=True,
    )
    path = parts.path.rstrip("/") or parts.path
    return urlunsplit((scheme, netloc, path, query, ""))


def has_required_acceptance_fields(row: dict[str, Any]) -> tuple[bool, str]:
    required = [
        "source_name",
        "source_type",
        "source_tier",
        "title",
        "publication_or_organisation",
        "publication_date_text",
        "url",
        "narrative_type",
        "australian_relation",
        "humanoid_basis",
        "source_label",
        "location_role",
        "ethics_review_status",
        "cultural_sensitivity",
        "evidence_summary",
    ]
    missing = [field for field in required if not canonicalise_whitespace(row.get(field))]
    if missing:
        return False, "missing_required_fields:" + ",".join(missing)
    if row.get("secondary_role") in {"unresolved_lead", "source_pointer", "catalogue_metadata"}:
        return False, "lead_or_metadata_role_not_countable"
    if row.get("source_type") in {"academic_metadata"}:
        return False, "metadata_only_source_type_not_countable"
    if row.get("ethics_review_status") in {"restricted_exclude", "restricted_excluded"}:
        return False, "restricted_content"
    return True, ""


def existing_urls(conn) -> set[str]:
    urls = {
        row[0]
        for row in conn.execute(
            "SELECT canonical_url FROM source_items WHERE COALESCE(canonical_url, '') != ''"
        ).fetchall()
    }
    urls.update(
        row[0]
        for row in conn.execute(
            "SELECT canonical_url FROM collection_candidates_v2 WHERE candidate_status = 'accepted' AND COALESCE(canonical_url, '') != ''"
        ).fetchall()
    )
    return urls


def insert_candidate(conn, data: dict[str, Any]) -> str:
    now = utc_now_iso()
    canonical_url = canonicalize_url(data.get("canonical_url") or data.get("url") or "")
    data["canonical_url"] = canonical_url
    ok, reason = has_required_acceptance_fields(data)
    if canonical_url and canonical_url in existing_urls(conn):
        status = "duplicate"
        decision = "not_accepted"
        rejection = "duplicate_canonical_url"
    elif ok and data.get("candidate_status") == "accepted":
        status = "accepted"
        decision = "accepted"
        rejection = ""
    elif data.get("candidate_status") in {"lead_only", "rejected", "duplicate"}:
        status = data["candidate_status"]
        decision = data.get("acceptance_decision") or "not_accepted"
        rejection = data.get("rejection_reason") or reason
    else:
        status = "rejected"
        decision = "not_accepted"
        rejection = reason or "not_marked_accepted"

    conn.execute(
        """
        INSERT INTO collection_candidates_v2(
            run_id, candidate_status, source_name, source_type, source_tier,
            title, publication_or_organisation, publication_date_text, url,
            canonical_url, external_id, narrative_type, secondary_role,
            australian_relation, humanoid_basis, source_label, location_text,
            location_role, ethics_review_status, cultural_sensitivity,
            acceptance_decision, rejection_reason, evidence_summary,
            raw_metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, canonical_url, external_id) DO UPDATE SET
            candidate_status=excluded.candidate_status,
            acceptance_decision=excluded.acceptance_decision,
            rejection_reason=excluded.rejection_reason,
            evidence_summary=excluded.evidence_summary,
            raw_metadata_json=excluded.raw_metadata_json,
            updated_at=excluded.updated_at
        """,
        (
            data.get("run_id"),
            status,
            data.get("source_name"),
            data.get("source_type"),
            data.get("source_tier"),
            data.get("title"),
            data.get("publication_or_organisation"),
            data.get("publication_date_text"),
            data.get("url"),
            canonical_url,
            data.get("external_id"),
            data.get("narrative_type"),
            data.get("secondary_role"),
            data.get("australian_relation") or data.get("australia_relation"),
            data.get("humanoid_basis"),
            data.get("source_label"),
            data.get("location_text"),
            data.get("location_role"),
            data.get("ethics_review_status"),
            data.get("cultural_sensitivity"),
            decision,
            rejection,
            data.get("evidence_summary"),
            json.dumps(data.get("raw_metadata_json") or data, ensure_ascii=False, sort_keys=True),
            now,
            now,
        ),
    )
    return status


def stage_manual_csv(conn, path: Path, run_id: str) -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_MANUAL_COLUMNS if field not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Manual CSV missing columns: {', '.join(missing)}")
        for raw in reader:
            raw["run_id"] = run_id
            raw.setdefault("candidate_status", "accepted")
            status = insert_candidate(conn, raw)
            counts[status] = counts.get(status, 0) + 1
    return counts


def stage_trove_leads(conn, run_id: str, limit: int) -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    collector = TroveCollector(run_id=run_id, limit=limit)
    for candidate in collector.collect():
        row = candidate.as_row()
        row["raw_metadata_json"] = candidate.raw_metadata_json
        status = insert_candidate(conn, row)
        counts[status] = counts.get(status, 0) + 1
    return counts


def write_progress(conn, report: Path) -> None:
    rows = conn.execute(
        """
        SELECT candidate_status, COUNT(*) AS count
        FROM collection_candidates_v2
        GROUP BY candidate_status
        ORDER BY candidate_status
        """
    ).fetchall()
    accepted = sum(int(row["count"]) for row in rows if row["candidate_status"] == "accepted")
    lines = [
        "# V2 Collection 500 Progress",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Accepted net-new source items: {accepted}",
        f"- Target: 500",
        f"- Remaining: {max(0, 500 - accepted)}",
        "",
        "## Candidate Status",
    ]
    for row in rows:
        lines.append(f"- {row['candidate_status']}: {row['count']}")
    lines.extend(
        [
            "",
            "## Current Limitation",
            "- This run stages leads and/or manually verified candidates only.",
            "- Metadata-only, unresolved leads, duplicate URLs, restricted records, controls, and exclusions do not count toward the 500 accepted target.",
            "- Trove article-level collection requires a supplied `TROVE_API_KEY` or manual verified imports.",
        ]
    )
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--run-id", default="v2_collection_batch_001", help="Deterministic run id")
    parser.add_argument("--manual-csv", help="Manually verified accepted/rejected candidates CSV")
    parser.add_argument("--trove-leads", action="store_true", help="Stage reproducible Trove public query leads")
    parser.add_argument("--limit", type=int, default=50, help="Maximum collector candidates")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Progress report path")
    args = parser.parse_args()

    with connect(args.db) as conn:
        if "collection_candidates_v2" not in {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            raise SystemExit("V2 schema missing. Run make migrate-v2 first.")
        counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
        if args.manual_csv:
            for key, value in stage_manual_csv(conn, Path(args.manual_csv), args.run_id).items():
                counts[key] = counts.get(key, 0) + value
        if args.trove_leads or not args.manual_csv:
            for key, value in stage_trove_leads(conn, args.run_id, args.limit).items():
                counts[key] = counts.get(key, 0) + value
        conn.commit()
        write_progress(conn, Path(args.report))
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
