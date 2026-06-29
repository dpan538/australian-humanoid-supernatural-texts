#!/usr/bin/env python3
"""Freeze current corpus state and generate pre-frontend audit reports.

This script is intentionally local-only. It does not run collection routes,
call external APIs, or mutate canonical records except for writing reports and
snapshot files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from aus_humanoid.db import DEFAULT_DB_PATH


FRONTEND_JSON = ROOT / "public" / "data" / "frontend-data.json"
PROCESSED = ROOT / "data" / "processed" / "v2"
EXPORTS = ROOT / "data" / "exports" / "v2"
ATLAS_DOCX = ROOT / "Australian Public Text Archive of Supernatural Humanoid Narratives and Encounters.docx"

PUBLIC_RECORD_SQL = """
FROM records r
JOIN sources s ON s.source_id = r.source_id
LEFT JOIN coding c ON c.record_id = r.record_id
WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
  AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
  AND COALESCE(c.relevance_code, '') != 'scope_excluded'
"""

PUBLIC_RECORD_SELECT = f"""
SELECT
  r.record_id, r.source_id, r.external_id, r.title, r.publication, r.author,
  r.date_published, r.year, r.url, r.snippet, r.publicness_level, r.ingestion_status,
  s.source_name, s.source_type,
  c.canonical_figure_guess, c.figure_name_as_printed, c.ontology_code,
  c.humanoid_degree_code, c.source_voice, c.genre, c.publicness_code,
  c.relevance_code, c.ethics_flag, c.notes AS coding_notes
{PUBLIC_RECORD_SQL}
"""


def rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def run_git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def short_hash(value: object) -> str:
    return hashlib.sha256(norm(value).encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def frontend_counts() -> dict:
    data = read_json(FRONTEND_JSON)
    records = data.get("records") or []
    map_points = data.get("map_points") or []
    map_flags = data.get("map_flags") or []
    return {
        "records": len(records),
        "map_points": len(map_points),
        "map_flags": len(map_flags),
        "record_ids": [int(row["record_id"]) for row in records],
        "map_record_ids": [int(row["record_id"]) for row in map_flags],
        "json": data,
    }


def classify_status_paths(status_lines: list[str]) -> dict:
    collection_owned_prefixes = (
        "config/",
        "data/exports/v2/",
        "data/interim/collection_sprint/",
        "data/processed/",
        "public/data/",
        "scripts/run_collection_sprint.py",
    )
    unrelated = []
    modified_collection = []
    untracked_collection = []
    for line in status_lines:
        path = line[3:] if len(line) > 3 else line
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if line.startswith("??"):
            if path.startswith(collection_owned_prefixes):
                untracked_collection.append(path)
            else:
                unrelated.append(line)
        elif path.startswith(collection_owned_prefixes):
            modified_collection.append(line)
        else:
            unrelated.append(line)
    return {
        "modified_collection_owned_files": modified_collection,
        "untracked_collection_artifacts": untracked_collection,
        "unrelated_pre_existing_dirty_files": unrelated,
    }


def local_remote_reconciliation() -> dict:
    status_short = run_git(["status", "--short", "--branch"]).splitlines()
    head = run_git(["rev-parse", "HEAD"])
    origin = run_git(["rev-parse", "origin/main"])
    behind, ahead = [int(part) for part in run_git(["rev-list", "--left-right", "--count", "origin/main...HEAD"]).split()]
    parsed = classify_status_paths([line for line in status_short if not line.startswith("##")])
    counts = frontend_counts()
    state_status = "committed" if head != origin else "uncommitted_or_export_only"
    if parsed["modified_collection_owned_files"] or parsed["untracked_collection_artifacts"]:
        state_status = "uncommitted_worktree_export"
    payload = {
        "local_head": head,
        "origin_main_head": origin,
        "commits_ahead": ahead,
        "commits_behind": behind,
        "branch_status": status_short[0] if status_short else "",
        **parsed,
        "reported_state": {
            "public_records": counts["records"],
            "map_flags": counts["map_flags"],
            "map_points": counts["map_points"],
            "state_location": state_status,
        },
    }
    modified_lines = [f"- `{line}`" for line in parsed["modified_collection_owned_files"]] or ["- None"]
    untracked_lines = [f"- `{line}`" for line in parsed["untracked_collection_artifacts"]] or ["- None"]
    unrelated_lines = [f"- `{line}`" for line in parsed["unrelated_pre_existing_dirty_files"]] or ["- None"]
    md = [
        "# Local/Remote State Reconciliation",
        "",
        f"- Local HEAD: `{head}`",
        f"- origin/main HEAD: `{origin}`",
        f"- Ahead/behind: `{ahead}` ahead, `{behind}` behind",
        f"- Public export records: `{counts['records']}`",
        f"- Public map flags: `{counts['map_flags']}`",
        f"- Public map points: `{counts['map_points']}`",
        f"- 2397/921 state: `{state_status}`",
        "",
        "## Modified Collection-Owned Files",
        *modified_lines,
        "",
        "## Untracked Collection Artifacts",
        *untracked_lines,
        "",
        "## Unrelated Pre-Existing Dirty Files",
        *unrelated_lines,
    ]
    write_json(PROCESSED / "local_remote_state_reconciliation.json", payload)
    write_md(PROCESSED / "local_remote_state_reconciliation.md", "\n".join(md))
    return payload


def active_database_report() -> dict:
    db_path = Path(DEFAULT_DB_PATH)
    conn = db_connect()
    schema_version = conn.execute("PRAGMA schema_version").fetchone()[0]
    user_version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()
    sqlite_files = sorted(
        p for p in (ROOT / "data").rglob("*") if p.suffix in {".db", ".sqlite", ".sqlite3"}
    )
    return {
        "active_database_path": rel(db_path),
        "active_database_size_bytes": db_path.stat().st_size,
        "active_database_sha256": sha256(db_path),
        "sqlite_schema_version": schema_version,
        "sqlite_user_version": user_version,
        "frontend_json_path": rel(FRONTEND_JSON),
        "frontend_json_sha256": sha256(FRONTEND_JSON),
        "other_sqlite_files": [
            {
                "path": rel(p),
                "size_bytes": p.stat().st_size,
                "sha256": sha256(p) if p.stat().st_size else hashlib.sha256(b"").hexdigest(),
                "status": "active" if p.resolve() == db_path.resolve() else "inactive",
            }
            for p in sqlite_files
        ],
    }


def db_baseline(conn: sqlite3.Connection) -> dict:
    fc = frontend_counts()
    public_ids = set(fc["record_ids"])
    total_records = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    public_db = conn.execute(f"SELECT COUNT(*) {PUBLIC_RECORD_SQL}").fetchone()[0]
    suppressed = conn.execute(
        """
        SELECT COUNT(*)
        FROM records r
        LEFT JOIN coding c ON c.record_id = r.record_id
        WHERE COALESCE(r.publicness_level, '') = 'restricted_excluded'
           OR COALESCE(c.publicness_code, '') = 'restricted_excluded'
           OR COALESCE(c.relevance_code, '') = 'scope_excluded'
        """
    ).fetchone()[0]
    coding_counts = dict(
        conn.execute(
            """
            SELECT COALESCE(ontology_code, '') AS key, COUNT(*) AS n
            FROM coding c JOIN records r ON r.record_id = c.record_id
            GROUP BY key
            """
        ).fetchall()
    )
    candidate_counts = dict(
        conn.execute("SELECT candidate_status AS key, COUNT(*) AS n FROM collection_candidates_v2 GROUP BY candidate_status").fetchall()
    )
    promoted = conn.execute("SELECT COUNT(DISTINCT candidate_id) FROM collection_candidate_record_mappings").fetchone()[0]
    unpromoted_accepted = conn.execute(
        """
        SELECT COUNT(*)
        FROM collection_candidates_v2 cc
        LEFT JOIN collection_candidate_record_mappings m ON m.candidate_id = cc.candidate_id
        WHERE cc.candidate_status = 'accepted' AND m.candidate_id IS NULL
        """
    ).fetchone()[0]
    source_items = conn.execute("SELECT COUNT(*) FROM source_items").fetchone()[0]
    narrative_units = conn.execute("SELECT COUNT(*) FROM narrative_units").fetchone()[0]
    source_orgs = conn.execute("SELECT COUNT(DISTINCT source_name) FROM sources").fetchone()[0]
    source_families = conn.execute("SELECT COUNT(DISTINCT source_type) FROM sources").fetchone()[0]
    mapped = len(set(fc["map_record_ids"]))
    context_count = conn.execute(
        f"""
        SELECT COUNT(*)
        {PUBLIC_RECORD_SQL}
          AND (
            COALESCE(c.relevance_code, '') LIKE '%context%'
            OR COALESCE(c.genre, '') LIKE '%context%'
            OR COALESCE(c.source_voice, '') LIKE '%context%'
          )
        """
    ).fetchone()[0]
    first_class = public_db - context_count
    rejected_excluded = candidate_counts.get("rejected", 0) + suppressed
    public_id_rows = conn.execute(PUBLIC_RECORD_SELECT).fetchall()
    missing_from_export = sorted(set(int(row["record_id"]) for row in public_id_rows) - public_ids)
    extra_in_export = sorted(public_ids - set(int(row["record_id"]) for row in public_id_rows))
    return {
        "total_canonical_records_sqlite": total_records,
        "public_db_records": public_db,
        "public_export_records": fc["records"],
        "suppressed_records": suppressed,
        "context_records_estimated": context_count,
        "first_class_records_estimated": first_class,
        "rejected_or_excluded_rows_estimated": rejected_excluded,
        "collection_candidates_by_status": candidate_counts,
        "promoted_candidates": promoted,
        "unpromoted_accepted_candidates": unpromoted_accepted,
        "source_items": source_items,
        "narrative_units": narrative_units,
        "source_organisations": source_orgs,
        "source_families": source_families,
        "mapped_public_records": mapped,
        "map_points_length": fc["map_points"],
        "map_flags_length": fc["map_flags"],
        "unmapped_public_records": fc["records"] - mapped,
        "coding_ontology_counts": coding_counts,
        "missing_public_db_records_from_export": missing_from_export[:100],
        "extra_export_records_not_public_db": extra_in_export[:100],
        "invariants": frontend_invariants(conn),
    }


def frontend_invariants(conn: sqlite3.Connection) -> dict:
    fc = frontend_counts()
    record_ids = fc["record_ids"]
    public_ids = set(record_ids)
    flag_ids = fc["map_record_ids"]
    data = fc["json"]
    suppressed_export = [
        r["record_id"]
        for r in data.get("records", [])
        if r.get("publicness_level") == "restricted_excluded"
        or r.get("publicness_code") == "restricted_excluded"
        or r.get("relevance_code") == "scope_excluded"
    ]
    exporter_text = (ROOT / "scripts" / "export_frontend_json.py").read_text(encoding="utf-8")
    return {
        "mapped_public_records_equals_map_lengths": len(set(flag_ids)) == fc["map_points"] == fc["map_flags"],
        "every_map_flag_references_public_record": all(rid in public_ids for rid in flag_ids),
        "public_record_ids_unique": len(record_ids) == len(public_ids),
        "map_record_ids_unique": len(flag_ids) == len(set(flag_ids)),
        "suppressed_or_restricted_absent_from_export": not suppressed_export,
        "suppressed_or_restricted_export_record_ids": suppressed_export[:50],
        "exporter_candidate_append_absent": "900000000" not in exporter_text
        and "collection_candidates_v2" not in exporter_text,
    }


def create_snapshot(conn: sqlite3.Connection, baseline: dict) -> dict:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    release_dir = ROOT / "data" / "releases" / f"pre_frontend_optimization_{timestamp}"
    release_dir.mkdir(parents=True, exist_ok=True)
    db_out = release_dir / "australian_humanoid_figures.sqlite"
    frontend_out = release_dir / "frontend-data.json"
    backup_conn = sqlite3.connect(db_out)
    conn.backup(backup_conn)
    backup_conn.close()
    shutil.copy2(FRONTEND_JSON, frontend_out)
    files = [db_out, frontend_out]
    manifest_lines = [f"{sha256(path)}  {path.name}" for path in files]
    (release_dir / "MANIFEST.sha256").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    readme = [
        "# Pre-Frontend Optimization Snapshot",
        "",
        f"- Generated: {datetime.now(timezone.utc).isoformat()}",
        f"- Local commit SHA: `{run_git(['rev-parse', 'HEAD'])}`",
        f"- Public record count: `{baseline['public_export_records']}`",
        f"- Mapped-record count: `{baseline['mapped_public_records']}`",
        f"- Candidate counts: `{json.dumps(baseline['collection_candidates_by_status'], sort_keys=True)}`",
        "",
        "Collection is paused for frontend optimization. This snapshot preserves the current canonical SQLite database and generated frontend JSON before cleanup and UI work.",
        "",
        "Current limitations: the worktree contains uncommitted collection outputs ahead of the latest committed checkpoint; map growth remains below the 1,200 target; this snapshot is a freeze point, not a launch-complete corpus.",
    ]
    (release_dir / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")
    return {
        "snapshot_dir": rel(release_dir),
        "database": rel(db_out),
        "frontend_json": rel(frontend_out),
        "manifest": rel(release_dir / "MANIFEST.sha256"),
        "timestamp": timestamp,
    }


def structural_audit(conn: sqlite3.Connection) -> dict:
    checks = {}
    queries = {
        "duplicate_canonical_record_ids": "SELECT COUNT(*) FROM (SELECT record_id FROM records GROUP BY record_id HAVING COUNT(*) > 1)",
        "orphan_coding_rows": "SELECT COUNT(*) FROM coding c LEFT JOIN records r ON r.record_id = c.record_id WHERE r.record_id IS NULL",
        "orphan_location_links": "SELECT COUNT(*) FROM record_locations rl LEFT JOIN records r ON r.record_id = rl.record_id LEFT JOIN locations l ON l.location_id = rl.location_id WHERE r.record_id IS NULL OR l.location_id IS NULL",
        "orphan_source_item_links": "SELECT COUNT(*) FROM narrative_source_links nsl LEFT JOIN narrative_units nu ON nu.narrative_id = nsl.narrative_id LEFT JOIN source_items si ON si.source_item_id = nsl.source_item_id WHERE nu.narrative_id IS NULL OR si.source_item_id IS NULL",
        "orphan_candidate_mappings": "SELECT COUNT(*) FROM collection_candidate_record_mappings m LEFT JOIN collection_candidates_v2 cc ON cc.candidate_id = m.candidate_id LEFT JOIN records r ON r.record_id = m.record_id WHERE cc.candidate_id IS NULL OR r.record_id IS NULL",
        "accepted_candidates_without_canonical_records": "SELECT COUNT(*) FROM collection_candidates_v2 cc LEFT JOIN collection_candidate_record_mappings m ON m.candidate_id = cc.candidate_id WHERE cc.candidate_status='accepted' AND m.candidate_id IS NULL",
        "multi_record_candidate_mappings": "SELECT COUNT(*) FROM (SELECT candidate_id FROM collection_candidate_record_mappings GROUP BY candidate_id HAVING COUNT(DISTINCT record_id) > 1)",
        "canonical_records_with_no_source": "SELECT COUNT(*) FROM records r LEFT JOIN sources s ON s.source_id = r.source_id WHERE s.source_id IS NULL",
        "public_records_with_no_title": f"SELECT COUNT(*) {PUBLIC_RECORD_SQL} AND TRIM(COALESCE(r.title,''))=''",
        "public_records_with_no_url_or_identifier": f"SELECT COUNT(*) {PUBLIC_RECORD_SQL} AND TRIM(COALESCE(r.url,''))='' AND TRIM(COALESCE(r.external_id,''))=''",
        "public_records_with_no_evidence_summary": f"SELECT COUNT(*) {PUBLIC_RECORD_SQL} AND TRIM(COALESCE(r.snippet,''))=''",
        "public_records_with_no_narrative_type": f"SELECT COUNT(*) {PUBLIC_RECORD_SQL} AND TRIM(COALESCE(c.ontology_code,''))=''",
        "public_records_marked_suppressed": f"SELECT COUNT(*) {PUBLIC_RECORD_SQL} AND (COALESCE(r.publicness_level,'')='restricted_excluded' OR COALESCE(c.publicness_code,'')='restricted_excluded' OR COALESCE(c.relevance_code,'')='scope_excluded')",
    }
    for key, sql in queries.items():
        checks[key] = conn.execute(sql).fetchone()[0]
    return checks


def duplicate_audits(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    rows = [dict(row) for row in conn.execute(PUBLIC_RECORD_SELECT).fetchall()]
    exact_groups: defaultdict[tuple[str, str], list[dict]] = defaultdict(list)
    near_groups: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        canonical_url = norm(row.get("url")).split("?", 1)[0]
        exact_groups[("canonical_url_external_id", f"{canonical_url}|{norm(row.get('external_id'))}")].append(row)
        exact_groups[("title_source_date", f"{norm(row.get('title'))}|{norm(row.get('source_name'))}|{norm(row.get('date_published'))}")].append(row)
        exact_groups[("evidence_summary_hash", short_hash(row.get("snippet")))].append(row)
        first_words = " ".join(norm(row.get("snippet")).split()[:160])
        if first_words:
            near_groups[first_words[:900]].append(row)
    exact = []
    for (basis, key), group in exact_groups.items():
        ids = sorted({int(g["record_id"]) for g in group})
        if len(ids) > 1 and key.strip("|"):
            exact.append(
                {
                    "basis": basis,
                    "match_key": key[:240],
                    "record_ids": ";".join(map(str, ids)),
                    "count": len(ids),
                    "titles": " | ".join(sorted({str(g["title"]) for g in group})[:5]),
                    "source_names": " | ".join(sorted({str(g["source_name"]) for g in group})[:5]),
                    "review_action": "review_exact_duplicate_narrative_unit",
                }
            )
    near = []
    for key, group in near_groups.items():
        ids = sorted({int(g["record_id"]) for g in group})
        if len(ids) > 1:
            near.append(
                {
                    "basis": "same_first_160_normalized_words",
                    "match_key": key[:240],
                    "record_ids": ";".join(map(str, ids)),
                    "count": len(ids),
                    "titles": " | ".join(sorted({str(g["title"]) for g in group})[:5]),
                    "source_names": " | ".join(sorted({str(g["source_name"]) for g in group})[:5]),
                    "review_action": "manual_near_duplicate_review",
                }
            )
    return sorted(exact, key=lambda r: (-int(r["count"]), r["basis"]))[:2000], sorted(near, key=lambda r: -int(r["count"]))[:2000]


def section_split_audit(conn: sqlite3.Connection) -> list[dict]:
    rows = [dict(row) for row in conn.execute(PUBLIC_RECORD_SELECT).fetchall()]
    by_item: defaultdict[str, list[dict]] = defaultdict(list)
    for row in rows:
        key = row.get("url") or row.get("publication") or row.get("external_id") or f"record:{row['record_id']}"
        by_item[norm(key)].append(row)
    output = []
    for key, group in by_item.items():
        labels = Counter(norm(g.get("figure_name_as_printed") or g.get("canonical_figure_guess")) for g in group)
        evidence_hashes = Counter(short_hash(g.get("snippet")) for g in group)
        avg_len = sum(len(str(g.get("snippet") or "")) for g in group) / max(1, len(group))
        warnings = []
        if len(group) > 50:
            warnings.append("more_than_50_records_from_one_source_item")
        if labels and labels.most_common(1)[0][1] > 25:
            warnings.append("more_than_25_records_with_same_source_label")
        repeated_evidence_pct = round(100 * sum(n for n in evidence_hashes.values() if n > 1) / max(1, len(group)), 2)
        repeated_label_pct = round(100 * (labels.most_common(1)[0][1] if labels else 0) / max(1, len(group)), 2)
        if repeated_evidence_pct > 20:
            warnings.append("more_than_20_percent_repeated_evidence")
        top_label = labels.most_common(1)[0][0] if labels else ""
        if top_label in {"spirit", "ghost", "person", "man", "woman"}:
            warnings.append("generic_source_label_high_reuse")
        if warnings:
            output.append(
                {
                    "source_item_key": key[:240],
                    "sample_title": group[0].get("title"),
                    "sample_url": group[0].get("url"),
                    "source_name": group[0].get("source_name"),
                    "public_records": len(group),
                    "first_class_records_estimated": len(group),
                    "context_records_estimated": 0,
                    "suppressed_rows_estimated": 0,
                    "average_evidence_length": round(avg_len, 1),
                    "repeated_evidence_percentage": repeated_evidence_pct,
                    "repeated_source_label_percentage": repeated_label_pct,
                    "top_source_label": top_label,
                    "warning": ";".join(warnings),
                }
            )
    return sorted(output, key=lambda r: -int(r["public_records"]))[:1000]


def scope_and_quality_audits(conn: sqlite3.Connection) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    rows = [dict(row) for row in conn.execute(PUBLIC_RECORD_SELECT).fetchall()]
    scope = []
    source_label = []
    evidence = []
    sensitive = []
    idioms = ["ghost of a chance", "spirit of adventure", "spirit of enterprise", "spirit of the age", "poor devil"]
    non_person_context = ["flood", "sun", "moon", "star", "animal", "bird", "tree", "plant"]
    for row in rows:
        snippet = str(row.get("snippet") or "")
        label = str(row.get("figure_name_as_printed") or row.get("canonical_figure_guess") or "")
        title = str(row.get("title") or "")
        reasons = []
        low = snippet.lower()
        if any(term in low for term in idioms):
            reasons.append("idiomatic_supernatural_term")
        if any(term in low for term in non_person_context) and row.get("ontology_code") in {"spirit_person_narrative", "apparition_account"}:
            reasons.append("possible_non_humanoid_origin_story_marked_first_class")
        if "victorian" in low and row.get("source_name") == "Internet Archive":
            reasons.append("victorian_period_vs_victoria_check")
        if reasons:
            scope.append(review_row(row, ";".join(reasons)))
        if label and (norm(label) == norm(title) or label.lower() in {"spirit", "ghost", "person", "man", "woman", "old man", "old woman"}):
            source_label.append(review_row(row, "source_label_generic_or_title_like"))
        if len(snippet.strip()) < 80 or norm(snippet) == norm(title) or snippet[:80] in title:
            evidence.append(review_row(row, "short_or_title_repeated_evidence"))
        if any(term in " ".join([str(row.get(k) or "") for k in row]).lower() for term in ["aboriginal", "indigenous", "tribe", "native tribes", "dream", "totem"]):
            missing = []
            if not row.get("ethics_flag"):
                missing.append("missing_ethics_flag")
            if not row.get("author"):
                missing.append("missing_collector_author_context")
            if missing:
                sensitive.append(review_row(row, ";".join(missing)))
    return scope[:2000], source_label[:2000], evidence[:2000], sensitive[:2000]


def review_row(row: dict, reason: str) -> dict:
    return {
        "record_id": row.get("record_id"),
        "title": row.get("title"),
        "source_name": row.get("source_name"),
        "source_type": row.get("source_type"),
        "url": row.get("url"),
        "external_id": row.get("external_id"),
        "narrative_type": row.get("ontology_code"),
        "source_label": row.get("figure_name_as_printed") or row.get("canonical_figure_guess"),
        "evidence_summary": str(row.get("snippet") or "")[:500],
        "review_reason": reason,
    }


def map_health(conn: sqlite3.Connection) -> list[dict]:
    data = frontend_counts()["json"]
    records = {int(r["record_id"]): r for r in data.get("records", [])}
    allowed_roles = {
        "alleged_event_location",
        "apparition_location",
        "narrative_setting",
        "legend_associated_place",
        "rumour_circulation_place",
        "reported_place",
        "source_visible_place",
        "source_visible_place_hint",
        "mentioned_place",
    }
    rows = []
    coord_counts = Counter((round(float(p.get("latitude") or 0), 4), round(float(p.get("longitude") or 0), 4)) for p in data.get("map_points", []))
    for point in data.get("map_points", []):
        rid = int(point["record_id"])
        issues = []
        lat = point.get("latitude")
        lon = point.get("longitude")
        role = point.get("relation_type")
        if rid not in records:
            issues.append("map_flag_record_not_public")
        if role not in allowed_roles:
            issues.append("invalid_location_role")
        if role in {"publication_location", "source_collection_location"}:
            issues.append("publication_or_source_collection_location")
        if lat is None or lon is None or not (-44.5 <= float(lat) <= -9.0 and 112.0 <= float(lon) <= 154.5):
            issues.append("coordinates_outside_australia_bounds")
        if not point.get("evidence_text"):
            issues.append("missing_source_stated_place_evidence")
        if "verified" not in str(point.get("verification_status") or "").lower():
            issues.append("unverified_coordinate")
        if not point.get("state_territory"):
            issues.append("missing_state_territory")
        if coord_counts[(round(float(lat or 0), 4), round(float(lon or 0), 4))] > 25:
            issues.append("high_coordinate_repetition_review")
        if issues:
            rows.append(
                {
                    "record_id": rid,
                    "title": point.get("title"),
                    "place_name": point.get("place_name"),
                    "state_territory": point.get("state_territory"),
                    "latitude": lat,
                    "longitude": lon,
                    "relation_type": role,
                    "verification_status": point.get("verification_status"),
                    "geocode_source": point.get("geocode_source"),
                    "evidence_text": point.get("evidence_text"),
                    "review_reason": ";".join(issues),
                }
            )
    return rows


def source_concentration(conn: sqlite3.Connection) -> dict:
    data = frontend_counts()["json"]
    records = data.get("records", [])
    by_org = Counter(r.get("source_name") or "unknown" for r in records)
    by_family = Counter(r.get("source_type") or "unknown" for r in records)
    by_item = Counter((r.get("publication") or r.get("url") or r.get("source_name") or "unknown") for r in records)
    total = max(1, len(records))
    org_pct = {k: round(v * 100 / total, 2) for k, v in by_org.items()}
    return {
        "records_by_source_organisation": dict(by_org.most_common()),
        "records_by_source_family": dict(by_family.most_common()),
        "records_by_individual_book_or_source_item": dict(by_item.most_common(50)),
        "percentage_from_AYR": org_pct.get("Australian Yowie Research", 0),
        "percentage_from_Internet_Archive": org_pct.get("Internet Archive", 0),
        "percentage_from_Gutenberg_family": round(sum(v for k, v in by_org.items() if "Gutenberg" in k) * 100 / total, 2),
        "percentage_from_Wikisource": org_pct.get("Wikisource", 0),
        "percentage_from_Sacred_Texts": org_pct.get("Internet Sacred Text Archive", 0),
        "top_10_source_items_by_record_count": by_item.most_common(10),
    }


def route_capacity_assessment() -> tuple[dict, list[dict]]:
    config_text = (ROOT / "config" / "collection_sprint.yml").read_text(encoding="utf-8")
    routes_text = (ROOT / "config" / "collection_routes.yml").read_text(encoding="utf-8")
    state = read_json(PROCESSED / "collection_sprint_state.json") if (PROCESSED / "collection_sprint_state.json").exists() else {}
    status = read_json(PROCESSED / "collection_sprint_status.json") if (PROCESSED / "collection_sprint_status.json").exists() else {}
    atlas_text = extract_docx_text(ATLAS_DOCX) if ATLAS_DOCX.exists() else ""
    route_totals = state.get("route_totals") or state.get("routes") or {}
    cursors = state.get("resume_cursor_per_route") or {}
    exhausted = set(state.get("exhausted_routes") or [])
    matrix = []
    for route_id, total in sorted(route_totals.items()):
        processed = int(total.get("processed") or 0)
        accepted = int(total.get("accepted") or 0)
        duplicates = int(total.get("duplicates") or 0)
        context = int(total.get("context") or 0)
        suppressed = int(total.get("suppressed") or 0)
        errors = int(total.get("errors") or 0)
        cursor = cursors.get(route_id) or {}
        rate = round(accepted / processed, 4) if processed else 0
        if route_id in exhausted and accepted > 0:
            classification = "productive_but_current_cursor_exhausted"
        elif accepted >= 6 and not cursor.get("exhausted"):
            classification = "productive_with_remaining_material"
        elif duplicates > accepted and duplicates / max(1, processed) > 0.8:
            classification = "duplicate_saturated"
        elif processed and accepted == 0:
            classification = "exhausted_low_yield"
        elif errors and not processed:
            classification = "blocked_access"
        else:
            classification = "discovery_only"
        matrix.append(
            {
                "route_id": route_id,
                "classification": classification,
                "processed_candidates": processed,
                "accepted_records": accepted,
                "duplicates": duplicates,
                "context": context,
                "suppressed": suppressed,
                "errors": errors,
                "acceptance_rate": rate,
                "last_cursor": json.dumps(cursor, sort_keys=True),
                "known_remaining_pages_or_items": "unknown" if not cursor else ("0" if cursor.get("exhausted") else "some"),
                "another_run_justified": "yes" if classification == "productive_with_remaining_material" else "no",
            }
        )
    configured_ids = set(re.findall(r"route_id:\s*([A-Za-z0-9_:-]+)", config_text))
    seen_ids = set(route_totals)
    for route_id in sorted(configured_ids - seen_ids):
        matrix.append(
            {
                "route_id": route_id,
                "classification": "untried_configured",
                "processed_candidates": 0,
                "accepted_records": 0,
                "duplicates": 0,
                "context": 0,
                "suppressed": 0,
                "errors": 0,
                "acceptance_rate": 0,
                "last_cursor": "",
                "known_remaining_pages_or_items": "configured_not_run",
                "another_run_justified": "yes_after_frontend_work",
            }
        )
    high_potential = [
        "DSpace/EPrints/OAI-PMH repository full-text adapters",
        "RHSV affiliate historical society newsletters",
        "History West affiliate publications",
        "SA History Network downstream local museum pages",
        "council local-studies PDF newsletters",
        "regional museum narrative/story pages",
        "state-library item pages with public text",
        "place-first public heritage records",
    ]
    assessment = {
        "verdict": "map_constrained",
        "general_public_record_growth_exhausted": False,
        "exact_public_domain_book_routes_becoming_saturated": True,
        "map_growth_now_harder_constraint": True,
        "bottleneck": "engineering_adapters_and_human_location_verification",
        "deep_research_source_discovery_needed_now": False,
        "lane_A_existing_configured_exact_text_routes": "Low to moderate remaining capacity; many configured routes are cursor-exhausted, but untried exact title routes and rescan-safe evidence-hash routes remain.",
        "lane_B_additional_public_domain_and_repository_full_text": "Moderate capacity if exact Australian titles and repository full-text endpoints are added; broad searches are saturated or frozen.",
        "lane_C_local_and_regional_archives": "High potential but adapter-limited; atlas names multiple downstream organisations and newsletter/PDF collections not yet implemented.",
        "lane_D_map_capable_place_first_records": "High value and hardest lane; remaining target requires named-place evidence plus gazetteer verification.",
        "next_five_source_families": high_potential[:5],
        "evidence_summary": {
            "configured_route_count": len(configured_ids),
            "route_totals_count": len(route_totals),
            "atlas_text_available": bool(atlas_text),
            "collection_sprint_status_routes": len(status.get("aggregated_route_yield") or status.get("route_results") or []),
            "collection_routes_mentions": {
                "blocked_auth": routes_text.count("blocked_auth"),
                "low_yield": routes_text.count("low_yield"),
                "exhausted": routes_text.count("exhausted"),
                "discovery_only": routes_text.count("discovery_only"),
            },
        },
    }
    return assessment, matrix


def extract_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml")
    except Exception:
        return ""
    root = ET.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    parts = [node.text for node in root.findall(".//w:t", ns) if node.text]
    return "\n".join(parts)


def safe_cleaning_report(before: dict, after: dict) -> dict:
    changes: list[dict] = []
    write_csv(
        EXPORTS / "pre_frontend_cleaning_changes.csv",
        changes,
        ["change_type", "table_name", "record_id", "field_name", "before_value", "after_value", "reason"],
    )
    payload = {
        "applied_changes": changes,
        "automatic_changes_applied": 0,
        "before_public_records": before["public_export_records"],
        "before_map_flags": before["map_flags_length"],
        "after_public_records": after["public_export_records"],
        "after_map_flags": after["map_flags_length"],
        "note": "No deterministic row-level corrections were applied; all non-trivial issues were written to review queues.",
    }
    write_json(PROCESSED / "pre_frontend_cleaning_changes.json", payload)
    write_md(
        PROCESSED / "pre_frontend_cleaning_changes.md",
        "\n".join(
            [
                "# Pre-Frontend Cleaning Changes",
                "",
                "- Automatic deterministic changes applied: `0`",
                f"- Before public records: `{before['public_export_records']}`",
                f"- Before map flags: `{before['map_flags_length']}`",
                f"- After public records: `{after['public_export_records']}`",
                f"- After map flags: `{after['map_flags_length']}`",
                "",
                "No canonical records, map flags, or classifications were changed in this pass. Reviewable issues were exported to queues.",
            ]
        ),
    )
    return payload


def write_baseline_reports(active_db: dict, baseline: dict, snapshot: dict) -> None:
    payload = {"active_database": active_db, "baseline": baseline, "snapshot": snapshot}
    write_json(PROCESSED / "pre_frontend_baseline.json", payload)
    md = [
        "# Pre-Frontend Baseline",
        "",
        f"- Active database: `{active_db['active_database_path']}`",
        f"- Active database size: `{active_db['active_database_size_bytes']}` bytes",
        f"- Active database SHA256: `{active_db['active_database_sha256']}`",
        f"- SQLite schema version: `{active_db['sqlite_schema_version']}`",
        f"- Frontend JSON: `{active_db['frontend_json_path']}`",
        f"- Frontend JSON SHA256: `{active_db['frontend_json_sha256']}`",
        f"- Snapshot: `{snapshot['snapshot_dir']}`",
        "",
        "## Counts",
    ]
    for key in [
        "total_canonical_records_sqlite",
        "public_export_records",
        "suppressed_records",
        "context_records_estimated",
        "first_class_records_estimated",
        "rejected_or_excluded_rows_estimated",
        "promoted_candidates",
        "unpromoted_accepted_candidates",
        "source_items",
        "narrative_units",
        "source_organisations",
        "source_families",
        "mapped_public_records",
        "map_points_length",
        "map_flags_length",
        "unmapped_public_records",
    ]:
        md.append(f"- {key}: `{baseline[key]}`")
    md.extend(["", "## Invariants"])
    for key, value in baseline["invariants"].items():
        if not key.endswith("_record_ids"):
            md.append(f"- {key}: `{value}`")
    write_md(PROCESSED / "pre_frontend_baseline.md", "\n".join(md))


def write_health_reports(conn: sqlite3.Connection) -> dict:
    structural = structural_audit(conn)
    exact, near = duplicate_audits(conn)
    section = section_split_audit(conn)
    scope, source_label, evidence, sensitive = scope_and_quality_audits(conn)
    map_rows = map_health(conn)
    concentration = source_concentration(conn)
    write_csv(EXPORTS / "exact_duplicate_review.csv", exact, ["basis", "match_key", "record_ids", "count", "titles", "source_names", "review_action"])
    write_csv(EXPORTS / "near_duplicate_review.csv", near, ["basis", "match_key", "record_ids", "count", "titles", "source_names", "review_action"])
    write_csv(EXPORTS / "section_split_review.csv", section, ["source_item_key", "sample_title", "sample_url", "source_name", "public_records", "first_class_records_estimated", "context_records_estimated", "suppressed_rows_estimated", "average_evidence_length", "repeated_evidence_percentage", "repeated_source_label_percentage", "top_source_label", "warning"])
    review_fields = ["record_id", "title", "source_name", "source_type", "url", "external_id", "narrative_type", "source_label", "evidence_summary", "review_reason"]
    write_csv(EXPORTS / "scope_review_queue.csv", scope, review_fields)
    write_csv(EXPORTS / "source_label_review.csv", source_label, review_fields)
    write_csv(EXPORTS / "evidence_quality_review.csv", evidence, review_fields)
    write_csv(EXPORTS / "sensitive_record_review.csv", sensitive, review_fields)
    write_csv(EXPORTS / "map_health_review.csv", map_rows, ["record_id", "title", "place_name", "state_territory", "latitude", "longitude", "relation_type", "verification_status", "geocode_source", "evidence_text", "review_reason"])
    payload = {
        "structural_integrity": structural,
        "review_queue_counts": {
            "exact_duplicate_review": len(exact),
            "near_duplicate_review": len(near),
            "section_split_review": len(section),
            "scope_review_queue": len(scope),
            "source_label_review": len(source_label),
            "evidence_quality_review": len(evidence),
            "sensitive_record_review": len(sensitive),
            "map_health_review": len(map_rows),
        },
        "source_concentration": concentration,
        "location_and_map_audit": {
            "map_review_rows": len(map_rows),
            "note": "Rows are review flags only; no map flags were removed.",
        },
    }
    write_json(PROCESSED / "pre_frontend_data_health_audit.json", payload)
    md = [
        "# Pre-Frontend Data Health Audit",
        "",
        "No canonical records were deleted or merged. Review queues identify issues for later human or deterministic cleanup.",
        "",
        "## Structural Integrity",
        *[f"- {k}: `{v}`" for k, v in structural.items()],
        "",
        "## Review Queue Counts",
        *[f"- {k}: `{v}`" for k, v in payload["review_queue_counts"].items()],
        "",
        "## Source Concentration",
        f"- AYR share: `{concentration['percentage_from_AYR']}%`",
        f"- Internet Archive share: `{concentration['percentage_from_Internet_Archive']}%`",
        f"- Gutenberg-family share: `{concentration['percentage_from_Gutenberg_family']}%`",
        f"- Wikisource share: `{concentration['percentage_from_Wikisource']}%`",
        f"- Sacred Texts share: `{concentration['percentage_from_Sacred_Texts']}%`",
        "",
        "## Map Audit",
        f"- Map health review rows: `{len(map_rows)}`",
        "- Repeated coordinates are flagged for review but were not removed.",
    ]
    write_md(PROCESSED / "pre_frontend_data_health_audit.md", "\n".join(md))
    return payload


def write_capacity_reports() -> dict:
    assessment, matrix = route_capacity_assessment()
    write_csv(EXPORTS / "route_capacity_matrix.csv", matrix, ["route_id", "classification", "processed_candidates", "accepted_records", "duplicates", "context", "suppressed", "errors", "acceptance_rate", "last_cursor", "known_remaining_pages_or_items", "another_run_justified"])
    write_json(PROCESSED / "collection_capacity_assessment.json", {"assessment": assessment, "routes": matrix})
    md = [
        "# Collection Capacity Assessment",
        "",
        f"- Verdict: `{assessment['verdict']}`",
        f"- Is general public-record growth exhausted? `{assessment['general_public_record_growth_exhausted']}`",
        f"- Are exact public-domain book routes becoming saturated? `{assessment['exact_public_domain_book_routes_becoming_saturated']}`",
        f"- Is map growth now the harder constraint? `{assessment['map_growth_now_harder_constraint']}`",
        f"- Bottleneck: `{assessment['bottleneck']}`",
        f"- Is another Deep Research source-discovery pass necessary now? `{assessment['deep_research_source_discovery_needed_now']}`",
        "",
        "## Lanes",
        f"- Lane A: {assessment['lane_A_existing_configured_exact_text_routes']}",
        f"- Lane B: {assessment['lane_B_additional_public_domain_and_repository_full_text']}",
        f"- Lane C: {assessment['lane_C_local_and_regional_archives']}",
        f"- Lane D: {assessment['lane_D_map_capable_place_first_records']}",
        "",
        "## Next Five Source Families",
        *[f"- {item}" for item in assessment["next_five_source_families"]],
    ]
    write_md(PROCESSED / "collection_capacity_assessment.md", "\n".join(md))
    return assessment


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    EXPORTS.mkdir(parents=True, exist_ok=True)
    reconciliation = local_remote_reconciliation()
    active_db = active_database_report()
    with db_connect() as conn:
        baseline_before = db_baseline(conn)
        snapshot = create_snapshot(conn, baseline_before)
        write_baseline_reports(active_db, baseline_before, snapshot)
        health = write_health_reports(conn)
        baseline_after = db_baseline(conn)
    cleaning = safe_cleaning_report(baseline_before, baseline_after)
    capacity = write_capacity_reports()
    summary = {
        "reconciliation": reconciliation,
        "active_database": active_db,
        "baseline": baseline_after,
        "snapshot": snapshot,
        "health": health,
        "cleaning": cleaning,
        "capacity_verdict": capacity["verdict"],
    }
    write_json(PROCESSED / "pre_frontend_freeze_audit_summary.json", summary)
    print(json.dumps({
        "public_records": baseline_after["public_export_records"],
        "map_flags": baseline_after["map_flags_length"],
        "snapshot": snapshot["snapshot_dir"],
        "capacity_verdict": capacity["verdict"],
    }, indent=2))


if __name__ == "__main__":
    main()
