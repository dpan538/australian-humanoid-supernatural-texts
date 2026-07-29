#!/usr/bin/env python3
"""Backfill source-chain skeletons for existing records and narrative units."""

from __future__ import annotations

import argparse
import csv
import hashlib
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, normalize_space, now_iso, table_exists, write_csv


ACCESS_PLATFORMS = {
    "project gutenberg australia": ("Project Gutenberg Australia", "D"),
    "gutenberg.net.au": ("Project Gutenberg Australia", "D"),
    "project gutenberg": ("Project Gutenberg", "D"),
    "internet archive": ("Internet Archive", "D"),
    "archive.org": ("Internet Archive", "D"),
    "wikisource": ("Wikisource", "D"),
    "pandora": ("PANDORA", "D"),
}

DISCOVERY_ONLY = {
    "australian yowie research": "Australian Yowie Research",
    "yowiehunters": "Australian Yowie Research",
    "wikipedia": "Wikipedia",
    "paranormal database": "Paranormal Database",
    "paranormaldatabase": "Paranormal Database",
    "hauntedplaces": "Haunted Places",
    "haunted tourism": "Haunted Tourism Page",
    "openalex": "OpenAlex",
    "crossref": "Crossref",
    "worldcat": "WorldCat",
    "open library": "Open Library",
    "openlibrary": "Open Library",
    "blogspot": "Generic Blog",
    "wordpress": "Generic Blog",
}

REVIEW_FIELDS = [
    "record_id",
    "narrative_unit_id",
    "existing_source_name",
    "existing_source_url",
    "inferred_discovery_source_name",
    "inferred_access_source_name",
    "inferred_original_source_name",
    "inferred_evidence_source_name",
    "inferred_evidence_source_tier",
    "inferred_evidence_or_discovery",
    "source_chain_review_status",
    "reviewer_corrected_original_source_name",
    "reviewer_corrected_evidence_source_name",
    "reviewer_corrected_evidence_source_url",
    "reviewer_notes",
]


def platform_original_name(name: str | None, title: str | None) -> str:
    clean_name = str(name or "").strip()
    clean_title = str(title or "").strip()
    haystack = normalize_space(clean_name)
    if clean_title and not any(token in normalize_space(clean_title) for token in ACCESS_PLATFORMS):
        return clean_title
    if clean_name and not any(token in haystack for token in ACCESS_PLATFORMS):
        return clean_name
    return ""


def registry_match(name: str | None, url: str | None, registry: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    haystack = normalize_space(f"{name or ''} {url or ''}")
    if registry:
        matches: list[dict[str, Any]] = []
        for route in registry:
            candidates = [route.get("source_name"), route.get("institution"), route.get("source_id")]
            for candidate in candidates:
                token = normalize_space(candidate)
                if len(token) >= 6 and token in haystack:
                    matches.append(route)
                    break
        if matches:
            return sorted(matches, key=lambda route: (str(route.get("source_tier") or "Z"), str(route.get("source_id"))))[0]
    if "state library" in haystack or "national library" in haystack or "state records" in haystack or "archives" in haystack:
        return {
            "source_name": name or "Public archive/library",
            "institution": name or "Public archive/library",
            "source_tier": "A",
            "evidence_or_discovery": "evidence_possible",
            "route_family": "institutional_public_source",
        }
    return None


def classify_existing_source(name: str | None, url: str | None, registry: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    haystack = normalize_space(f"{name or ''} {url or ''}")

    for token, (label, tier) in ACCESS_PLATFORMS.items():
        if token in haystack:
            return {
                "source_tier": tier,
                "kind": "access_platform",
                "label": label,
                "evidence_or_discovery": "evidence_only_if_original_source_identified",
                "review_status": "needs_original_source_review",
            }

    for token, label in DISCOVERY_ONLY.items():
        if token in haystack:
            return {
                "source_tier": "E",
                "kind": "discovery_only",
                "label": label,
                "evidence_or_discovery": "discovery_only",
                "review_status": "needs_evidence_source_review",
            }

    matched = registry_match(name, url, registry)
    if matched:
        return {
            "source_tier": matched.get("source_tier"),
            "kind": "institutional_public_source",
            "label": matched.get("institution") or matched.get("source_name"),
            "evidence_or_discovery": matched.get("evidence_or_discovery", "evidence_possible"),
            "review_status": "provisionally_ok" if matched.get("source_tier") in {"A", "B", "C"} else "needs_review",
            "route_family": matched.get("route_family"),
        }

    return {
        "source_tier": None,
        "kind": "unknown",
        "label": name or "",
        "evidence_or_discovery": "unknown",
        "review_status": "needs_review",
    }


def safe_year(value: Any) -> int | None:
    text = str(value or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def fetch_existing_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if table_exists(conn, "source_items"):
        rows = conn.execute(
            """
            SELECT
                CAST(COALESCE(si.legacy_record_id, m.legacy_record_id, '') AS TEXT) AS record_id,
                CAST(COALESCE(nsl.narrative_id, m.narrative_id, '') AS TEXT) AS narrative_unit_id,
                CAST(si.source_item_id AS TEXT) AS source_item_id,
                COALESCE(si.publication_or_organisation, si.source_type, '') AS existing_source_name,
                COALESCE(si.url, si.canonical_url, '') AS existing_source_url,
                COALESCE(si.title, '') AS title,
                COALESCE(si.publication_date_start, si.publication_date_text, '') AS date_published,
                COALESCE(si.source_type, '') AS source_family
            FROM source_items si
            LEFT JOIN narrative_source_links nsl ON nsl.source_item_id = si.source_item_id
            LEFT JOIN legacy_record_mappings m ON m.source_item_id = si.source_item_id
            ORDER BY si.source_item_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    if table_exists(conn, "records"):
        rows = conn.execute(
            """
            SELECT
                CAST(record_id AS TEXT) AS record_id,
                '' AS narrative_unit_id,
                CAST(record_id AS TEXT) AS source_item_id,
                COALESCE(publication, '') AS existing_source_name,
                COALESCE(url, '') AS existing_source_url,
                COALESCE(title, '') AS title,
                COALESCE(date_published, CAST(year AS TEXT), '') AS date_published,
                '' AS source_family
            FROM records
            ORDER BY record_id
            """
        ).fetchall()
        return [dict(row) for row in rows]
    return []


def backfill_row(row: dict[str, Any], registry: list[dict[str, Any]]) -> dict[str, Any]:
    classification = classify_existing_source(row.get("existing_source_name"), row.get("existing_source_url"), registry)
    kind = classification["kind"]
    discovery = ""
    access = ""
    original = ""
    evidence = ""
    if kind == "access_platform":
        access = classification["label"]
        original = platform_original_name(row.get("existing_source_name"), row.get("title"))
        evidence = original
    elif kind == "discovery_only":
        discovery = classification["label"]
    elif kind == "institutional_public_source":
        evidence = classification["label"]
    else:
        evidence = row.get("existing_source_name") or ""

    return {
        "record_id": row.get("record_id", ""),
        "narrative_unit_id": row.get("narrative_unit_id", ""),
        "source_item_id": row.get("source_item_id", ""),
        "title": row.get("title", ""),
        "date_published": row.get("date_published", ""),
        "existing_source_name": row.get("existing_source_name", ""),
        "existing_source_url": row.get("existing_source_url", ""),
        "inferred_discovery_source_name": discovery,
        "inferred_access_source_name": access,
        "inferred_original_source_name": original,
        "inferred_evidence_source_name": evidence,
        "inferred_evidence_source_tier": classification.get("source_tier") or "",
        "inferred_evidence_or_discovery": classification.get("evidence_or_discovery") or "",
        "source_chain_review_status": classification.get("review_status") or "needs_review",
        "reviewer_corrected_original_source_name": "",
        "reviewer_corrected_evidence_source_name": "",
        "reviewer_corrected_evidence_source_url": "",
        "reviewer_notes": "",
        "_kind": kind,
    }


def source_chain_id(row: dict[str, Any]) -> str:
    raw = "|".join(str(row.get(key) or "") for key in ["record_id", "narrative_unit_id", "source_item_id", "existing_source_url"])
    return "schain_existing_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def upsert_source_chain(conn: sqlite3.Connection, row: dict[str, Any]) -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO source_chains (
            source_chain_id, record_id, narrative_unit_id,
            discovery_source_name, discovery_source_type, discovery_source_url,
            access_source_name, access_source_type, access_source_url,
            original_source_name, original_publication, original_publication_date,
            evidence_source_name, evidence_source_type, evidence_source_url,
            evidence_source_family, evidence_source_tier, evidence_strength,
            rights_status, metadata_only, full_text_available,
            source_chain_review_status, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_chain_id) DO UPDATE SET
            discovery_source_name=excluded.discovery_source_name,
            access_source_name=excluded.access_source_name,
            original_source_name=excluded.original_source_name,
            evidence_source_name=excluded.evidence_source_name,
            evidence_source_tier=excluded.evidence_source_tier,
            source_chain_review_status=excluded.source_chain_review_status,
            updated_at=excluded.updated_at
        """,
        (
            source_chain_id(row),
            row.get("record_id") or "",
            row.get("narrative_unit_id") or "",
            row.get("inferred_discovery_source_name") or "",
            "discovery_only" if row.get("inferred_discovery_source_name") else "",
            row.get("existing_source_url") if row.get("inferred_discovery_source_name") else "",
            row.get("inferred_access_source_name") or "",
            "access_platform" if row.get("inferred_access_source_name") else "",
            row.get("existing_source_url") if row.get("inferred_access_source_name") else "",
            row.get("inferred_original_source_name") or "",
            row.get("inferred_original_source_name") or "",
            row.get("date_published") or "",
            row.get("inferred_evidence_source_name") or "",
            row.get("inferred_evidence_or_discovery") or "",
            row.get("existing_source_url") or "",
            row.get("_kind") or "",
            row.get("inferred_evidence_source_tier") or "",
            "backfilled_needs_review",
            "metadata_only",
            1,
            0,
            row.get("source_chain_review_status") or "needs_review",
            ts,
            ts,
        ),
    )


def write_report(path: Path, rows: list[dict[str, Any]], execute: bool) -> None:
    access_counts = Counter(row.get("inferred_access_source_name") or "none" for row in rows)
    missing_original = [row for row in rows if row.get("inferred_access_source_name") and not row.get("inferred_original_source_name")]
    discovery_leakage = sum(1 for row in rows if row.get("inferred_evidence_source_tier") == "E")
    gap_rows = [row for row in rows if (year := safe_year(row.get("date_published"))) is not None and 1926 <= year <= 1976]
    ayr_gap = sum(1 for row in gap_rows if "australian yowie research" in normalize_space(row.get("existing_source_name")) or "yowiehunters" in normalize_space(row.get("existing_source_url")))
    decomposable = sum(1 for row in rows if row.get("inferred_access_source_name") in {"Internet Archive", "Project Gutenberg", "Project Gutenberg Australia", "Wikisource"})
    lines = [
        "# Source Chain Backfill Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Mode: `{'execute' if execute else 'dry_run'}`",
        f"- Source chains created/updated: `{len(rows) if execute else 0}`",
        f"- Review rows written: `{len(rows)}`",
        f"- Missing original source cases: `{len(missing_original)}`",
        f"- Discovery-only leakage count: `{discovery_leakage}`",
        f"- AYR share among 1926-1976 rows: `{0 if not gap_rows else round(ayr_gap / len(gap_rows) * 100, 2)}%`",
        f"- Internet Archive/Gutenberg/Wikisource decomposability count: `{decomposable}`",
        "",
        "## Top Access Platforms",
    ]
    lines.extend([f"- `{name}`: {count}" for name, count in access_counts.most_common(20)] or ["- None"])
    lines.extend(["", "## Top Missing Original Source Cases"])
    for row in missing_original[:30]:
        lines.append(f"- `{row.get('record_id') or row.get('narrative_unit_id')}` {row.get('existing_source_name')} {row.get('existing_source_url')}")
    if not missing_original:
        lines.append("- None")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def backfill(db_path: Path, registry_path: Path, out_path: Path, report_path: Path, execute: bool) -> list[dict[str, Any]]:
    registry = load_registry(registry_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        existing = fetch_existing_sources(conn)
        rows = [backfill_row(row, registry) for row in existing]
        if execute:
            if not table_exists(conn, "source_chains"):
                raise RuntimeError("source_chains table is missing. Run collection expansion migration first.")
            for row in rows:
                upsert_source_chain(conn, row)
            conn.commit()
    write_csv(out_path, rows, REVIEW_FIELDS)
    write_report(report_path, rows, execute)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--registry", required=True, help="source_registry.yml path")
    parser.add_argument("--out", required=True, help="review CSV output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    parser.add_argument("--dry-run", action="store_true", help="write review files but do not update source_chains")
    parser.add_argument("--execute", action="store_true", help="upsert source_chains")
    args = parser.parse_args()

    execute = bool(args.execute and not args.dry_run)
    rows = backfill(Path(args.db), Path(args.registry), Path(args.out), Path(args.report), execute)
    print(f"Backfilled source-chain review rows: {len(rows)}")
    print(f"Wrote review CSV: {args.out}")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
