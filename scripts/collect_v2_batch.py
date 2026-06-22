#!/usr/bin/env python3
"""Stage V2 collection candidates without lowering acceptance standards."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.collectors.manual_import import REQUIRED_MANUAL_COLUMNS
from aus_humanoid.collectors.internet_archive import InternetArchiveCollector
from aus_humanoid.collectors.seeded_web import SeededWebCollector
from aus_humanoid.collectors.trove import TroveCollector
from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso

import update_collection_route_registry


DEFAULT_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "collection_500_progress.md"
STRICT_GEO_REPORT = PROJECT_ROOT / "data" / "processed" / "v2" / "collection_3000_strict_geo_progress.md"

STRICT_GEO_ACCEPTED_STATUSES = {
    "verified_place",
    "verified_locality",
    "verified_gazetteer_point",
    "verified_institutional_coordinate",
}

STRICT_GEO_ACCEPTED_PRECISIONS = {
    "exact_site",
    "town",
    "locality",
    "named_feature",
}

PROGRESS_EVERY_CANDIDATES = 25

STRICT_GEO_REJECTED_LOCATION_ROLES = {
    "publication_location",
    "source_collection_location",
}

GEO_COLUMNS = {
    "access_date": "TEXT",
    "publicness_status": "TEXT",
    "rights_access_status": "TEXT",
    "latitude": "REAL",
    "longitude": "REAL",
    "location_precision": "TEXT",
    "geocode_source": "TEXT",
    "geocode_verification_status": "TEXT",
    "coordinate_evidence_note": "TEXT",
    "duplicate_check_status": "TEXT",
    "quality_class": "TEXT",
}


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


def safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def ensure_candidate_geo_columns(conn) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(collection_candidates_v2)").fetchall()}
    for column, column_type in GEO_COLUMNS.items():
        if column not in columns:
            conn.execute(f"ALTER TABLE collection_candidates_v2 ADD COLUMN {column} {column_type}")


def strict_geo_gate(row: dict[str, Any]) -> tuple[bool, str]:
    latitude = safe_float(row.get("latitude"))
    longitude = safe_float(row.get("longitude"))
    if latitude is None or longitude is None:
        return False, "strict_geo_missing_latitude_longitude"
    if not (-44.5 <= latitude <= -9.0 and 112.0 <= longitude <= 154.5):
        return False, "strict_geo_coordinates_outside_australia_bounds"
    if canonicalise_whitespace(row.get("location_role")) in STRICT_GEO_REJECTED_LOCATION_ROLES:
        return False, "strict_geo_publication_or_source_location_only"
    verification = canonicalise_whitespace(row.get("geocode_verification_status"))
    if verification not in STRICT_GEO_ACCEPTED_STATUSES:
        return False, "strict_geo_unverified_geocode"
    precision = canonicalise_whitespace(row.get("location_precision"))
    if precision not in STRICT_GEO_ACCEPTED_PRECISIONS:
        return False, "strict_geo_location_precision_too_broad"
    required = [
        "access_date",
        "publicness_status",
        "rights_access_status",
        "location_text",
        "geocode_source",
        "coordinate_evidence_note",
        "duplicate_check_status",
        "quality_class",
    ]
    missing = [field for field in required if not canonicalise_whitespace(row.get(field))]
    if missing:
        return False, "strict_geo_missing_fields:" + ",".join(missing)
    if canonicalise_whitespace(row.get("quality_class")) not in {"A", "B", "C"}:
        return False, "strict_geo_quality_class_not_countable"
    return True, ""


def progress_line(route_id: str, processed: int, counts: dict[str, int], failed: int, started_at: float) -> str:
    accepted = counts.get("accepted", 0)
    runtime = max(0.001, time.monotonic() - started_at)
    acceptance_rate = accepted / processed if processed else 0.0
    return (
        f"[collect-v2] route_id={route_id or 'unregistered'} processed={processed} "
        f"accepted={accepted} duplicates={counts.get('duplicate', 0)} "
        f"leads={counts.get('lead_only', 0)} rejected={counts.get('rejected', 0)} "
        f"requests_failed={failed} runtime={runtime:.1f}s acceptance_rate={acceptance_rate:.3f}"
    )


def maybe_print_progress(route_id: str, processed: int, counts: dict[str, int], failed: int, started_at: float) -> None:
    if processed and processed % PROGRESS_EVERY_CANDIDATES == 0:
        print(progress_line(route_id, processed, counts, failed, started_at), flush=True)


def enforce_route_registry(route_id: str, registry_csv: Path) -> None:
    if not route_id:
        return
    routes = update_collection_route_registry.registry_by_id(registry_csv)
    route = routes.get(route_id)
    if route is None:
        raise SystemExit(
            f"Route `{route_id}` is not registered. Add it to config/collection_routes.yml and run scripts/update_collection_route_registry.py."
        )
    allowed, reason = update_collection_route_registry.route_allows_probe(route)
    if not allowed:
        if route_id == "trove_api_without_key" and not canonicalise_whitespace(os.environ.get("TROVE_API_KEY")):
            raise SystemExit(reason)
        raise SystemExit(reason)


def has_required_acceptance_fields(row: dict[str, Any], strict_geo_only: bool = False) -> tuple[bool, str]:
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
    if strict_geo_only:
        return strict_geo_gate(row)
    return True, ""


def existing_candidate_keys(conn, current_run_id: str = "") -> tuple[set[str], set[tuple[str, str]]]:
    """Return existing accepted source keys.

    A single public page may contain multiple distinct narrative records. When
    callers provide a stable external_id, use (canonical_url, external_id) as
    the duplicate key; otherwise fall back to canonical_url alone. This keeps
    exact source duplicates out while allowing audited multi-record source
    pages such as local-history articles with several place-linked accounts.
    """

    url_only: set[str] = set()
    url_external: set[tuple[str, str]] = set()
    for row in conn.execute(
        """
        SELECT canonical_url, external_id
        FROM source_items
        WHERE COALESCE(canonical_url, '') != ''
        """
    ).fetchall():
        url = row["canonical_url"]
        external_id = canonicalise_whitespace(row["external_id"])
        if external_id:
            url_external.add((url, external_id))
        else:
            url_only.add(url)
    for row in conn.execute(
        """
        SELECT canonical_url, external_id
        FROM collection_candidates_v2
        WHERE candidate_status = 'accepted'
          AND COALESCE(canonical_url, '') != ''
          AND COALESCE(run_id, '') != ?
        """,
        (current_run_id,),
    ).fetchall():
        url = row["canonical_url"]
        external_id = canonicalise_whitespace(row["external_id"])
        if external_id:
            url_external.add((url, external_id))
        else:
            url_only.add(url)
    return url_only, url_external


def is_duplicate_candidate(conn, canonical_url: str, external_id: str, current_run_id: str = "") -> bool:
    if not canonical_url:
        return False
    url_only, url_external = existing_candidate_keys(conn, current_run_id)
    clean_external_id = canonicalise_whitespace(external_id)
    if clean_external_id:
        return (canonical_url, clean_external_id) in url_external
    return canonical_url in url_only


def insert_candidate(conn, data: dict[str, Any], strict_geo_only: bool = False) -> str:
    now = utc_now_iso()
    canonical_url = canonicalize_url(data.get("canonical_url") or data.get("url") or "")
    data["canonical_url"] = canonical_url
    ok, reason = has_required_acceptance_fields(data, strict_geo_only=strict_geo_only)
    if is_duplicate_candidate(
        conn,
        canonical_url,
        canonicalise_whitespace(data.get("external_id")),
        str(data.get("run_id") or ""),
    ):
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
            title, publication_or_organisation, publication_date_text, access_date, url,
            canonical_url, external_id, publicness_status, rights_access_status,
            narrative_type, secondary_role,
            australian_relation, humanoid_basis, source_label, location_text,
            location_role, latitude, longitude, location_precision,
            geocode_source, geocode_verification_status, coordinate_evidence_note,
            duplicate_check_status, quality_class, ethics_review_status, cultural_sensitivity,
            acceptance_decision, rejection_reason, evidence_summary,
            raw_metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, canonical_url, external_id) DO UPDATE SET
            candidate_status=excluded.candidate_status,
            source_name=excluded.source_name,
            source_type=excluded.source_type,
            source_tier=excluded.source_tier,
            title=excluded.title,
            publication_or_organisation=excluded.publication_or_organisation,
            publication_date_text=excluded.publication_date_text,
            access_date=excluded.access_date,
            url=excluded.url,
            publicness_status=excluded.publicness_status,
            rights_access_status=excluded.rights_access_status,
            narrative_type=excluded.narrative_type,
            secondary_role=excluded.secondary_role,
            australian_relation=excluded.australian_relation,
            humanoid_basis=excluded.humanoid_basis,
            source_label=excluded.source_label,
            location_text=excluded.location_text,
            location_role=excluded.location_role,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            location_precision=excluded.location_precision,
            geocode_source=excluded.geocode_source,
            geocode_verification_status=excluded.geocode_verification_status,
            coordinate_evidence_note=excluded.coordinate_evidence_note,
            duplicate_check_status=excluded.duplicate_check_status,
            quality_class=excluded.quality_class,
            ethics_review_status=excluded.ethics_review_status,
            cultural_sensitivity=excluded.cultural_sensitivity,
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
            data.get("access_date"),
            data.get("url"),
            canonical_url,
            data.get("external_id"),
            data.get("publicness_status"),
            data.get("rights_access_status"),
            data.get("narrative_type"),
            data.get("secondary_role"),
            data.get("australian_relation") or data.get("australia_relation"),
            data.get("humanoid_basis"),
            data.get("source_label"),
            data.get("location_text"),
            data.get("location_role"),
            safe_float(data.get("latitude")),
            safe_float(data.get("longitude")),
            data.get("location_precision"),
            data.get("geocode_source"),
            data.get("geocode_verification_status"),
            data.get("coordinate_evidence_note"),
            data.get("duplicate_check_status"),
            data.get("quality_class"),
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


def stage_manual_csv(conn, path: Path, run_id: str, strict_geo_only: bool = False, route_id: str = "") -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    started_at = time.monotonic()
    processed = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in REQUIRED_MANUAL_COLUMNS if field not in (reader.fieldnames or [])]
        if missing:
            raise SystemExit(f"Manual CSV missing columns: {', '.join(missing)}")
        for raw in reader:
            processed += 1
            raw["run_id"] = run_id
            raw.setdefault("candidate_status", "accepted")
            status = insert_candidate(conn, raw, strict_geo_only=strict_geo_only)
            counts[status] = counts.get(status, 0) + 1
            maybe_print_progress(route_id, processed, counts, 0, started_at)
    print(progress_line(route_id, processed, counts, 0, started_at), flush=True)
    return counts


def stage_trove_leads(conn, run_id: str, limit: int, strict_geo_only: bool = False, route_id: str = "") -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    started_at = time.monotonic()
    processed = 0
    failed = 0
    collector = TroveCollector(run_id=run_id, limit=limit)
    for candidate in collector.collect():
        processed += 1
        row = candidate.as_row()
        row["raw_metadata_json"] = candidate.raw_metadata_json
        status = insert_candidate(conn, row, strict_geo_only=strict_geo_only)
        counts[status] = counts.get(status, 0) + 1
        maybe_print_progress(route_id, processed, counts, failed, started_at)
    print(progress_line(route_id, processed, counts, failed, started_at), flush=True)
    return counts


def stage_internet_archive(conn, run_id: str, limit: int, strict_geo_only: bool = False, route_id: str = "") -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    started_at = time.monotonic()
    processed = 0
    failed = 0
    collector = InternetArchiveCollector(run_id=run_id, limit=limit)
    for candidate in collector.collect():
        processed += 1
        row = candidate.as_row()
        row["raw_metadata_json"] = candidate.raw_metadata_json
        status = insert_candidate(conn, row, strict_geo_only=strict_geo_only)
        counts[status] = counts.get(status, 0) + 1
        maybe_print_progress(route_id, processed, counts, failed, started_at)
    print(progress_line(route_id, processed, counts, failed, started_at), flush=True)
    return counts


def stage_seeded_web(conn, run_id: str, seed_path: Path, limit: int, strict_geo_only: bool = False, route_id: str = "") -> dict[str, int]:
    counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
    started_at = time.monotonic()
    processed = 0
    failed = 0
    collector = SeededWebCollector(run_id=run_id, seed_path=seed_path, limit=limit)
    for candidate in collector.collect():
        processed += 1
        row = candidate.as_row()
        row["raw_metadata_json"] = candidate.raw_metadata_json
        status = insert_candidate(conn, row, strict_geo_only=strict_geo_only)
        counts[status] = counts.get(status, 0) + 1
        maybe_print_progress(route_id, processed, counts, failed, started_at)
    print(progress_line(route_id, processed, counts, failed, started_at), flush=True)
    return counts


def write_progress(conn, report: Path, target: int, strict_geo_only: bool = False) -> None:
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
        "# V2 Collection Progress",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Accepted net-new source items: {accepted}",
        f"- Target: {target}",
        f"- Remaining: {max(0, target - accepted)}",
        f"- Strict geography only: `{strict_geo_only}`",
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
            f"- Metadata-only, unresolved leads, duplicate URLs, restricted records, controls, and exclusions do not count toward the {target} accepted target.",
            "- In strict-geography mode, candidates without verified latitude/longitude, locality precision, geocode source, coordinate evidence, duplicate status, and quality class A/B/C are rejected.",
            "- Outside strict-geography mode, substantive public-text candidates with broad or unresolved geography may be accepted for dashboard/density review surfaces only; they are excluded from the map until strict coordinates are verified.",
            "- Trove article-level collection requires a supplied `TROVE_API_KEY` or manual verified imports.",
            "- Internet Archive strict-map items require public text/OCR, source label in text, and a strict gazetteer place. Internet Archive public-display items may use broad geography but must still expose public text/OCR and source-label evidence.",
            "- Seeded public-web rows count only when the configured public page or manual public excerpt verifies both the source label and the strict place.",
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
    parser.add_argument("--internet-archive", action="store_true", help="Stage strict public-text Internet Archive candidates")
    parser.add_argument("--seeded-web", help="YAML seed list for strict public-web candidates")
    parser.add_argument("--limit", type=int, default=50, help="Maximum collector candidates")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="Progress report path")
    parser.add_argument("--target", type=int, default=500, help="Accepted source-item target for progress reporting")
    parser.add_argument("--strict-geo-only", action="store_true", help="Require verified coordinates and quality class A/B/C for accepted candidates")
    parser.add_argument("--route-id", default="", help="Registered route id for this collection run")
    parser.add_argument(
        "--route-registry",
        default=str(update_collection_route_registry.DEFAULT_CSV),
        help="Rendered collection route registry CSV",
    )
    args = parser.parse_args()

    enforce_route_registry(args.route_id, Path(args.route_registry))

    with connect(args.db) as conn:
        if "collection_candidates_v2" not in {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            raise SystemExit("V2 schema missing. Run make migrate-v2 first.")
        ensure_candidate_geo_columns(conn)
        counts = {"accepted": 0, "rejected": 0, "duplicate": 0, "lead_only": 0}
        if args.manual_csv:
            for key, value in stage_manual_csv(conn, Path(args.manual_csv), args.run_id, strict_geo_only=args.strict_geo_only, route_id=args.route_id).items():
                counts[key] = counts.get(key, 0) + value
        if args.trove_leads or (not args.manual_csv and not args.internet_archive and not args.seeded_web):
            for key, value in stage_trove_leads(conn, args.run_id, args.limit, strict_geo_only=args.strict_geo_only, route_id=args.route_id).items():
                counts[key] = counts.get(key, 0) + value
        if args.internet_archive:
            for key, value in stage_internet_archive(conn, args.run_id, args.limit, strict_geo_only=args.strict_geo_only, route_id=args.route_id).items():
                counts[key] = counts.get(key, 0) + value
        if args.seeded_web:
            for key, value in stage_seeded_web(conn, args.run_id, Path(args.seeded_web), args.limit, strict_geo_only=args.strict_geo_only, route_id=args.route_id).items():
                counts[key] = counts.get(key, 0) + value
        conn.commit()
        write_progress(conn, Path(args.report), args.target, strict_geo_only=args.strict_geo_only)
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
