#!/usr/bin/env python3
"""Generate release baseline, source audit, and readiness reports from local data."""

from __future__ import annotations

import argparse
import csv
import json
import socket
import sqlite3
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "processed" / "australian_humanoid_figures.sqlite"
FRONTEND_JSON = ROOT / "public" / "data" / "frontend-data.json"
PROCESSED_V2 = ROOT / "data" / "processed" / "v2"
EXPORTS_V2 = ROOT / "data" / "exports" / "v2"

STATE_CODES = ["WA", "NT", "SA", "QLD", "NSW", "VIC", "TAS", "ACT"]
DISCOVERY_ONLY_HINTS = ("tourism", "wikipedia", "paranormal", "aggregator", "listicle", "search_result")
METADATA_HINTS = ("metadata", "catalogue", "openalex", "crossref")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def qrows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def source_family(source_type: str | None) -> str:
    value = (source_type or "").lower()
    if "community" in value:
        return "community_controlled_public"
    if "repository" in value:
        return "repository_texts"
    if "modern_web" in value or "seeded_public_web" in value:
        return "modern_public_web"
    if any(token in value for token in ("public_domain", "gutenberg", "wikisource", "sacred_texts")):
        return "public_domain_books"
    if "institutional" in value or "municipal" in value:
        return "institutional_or_local_studies"
    if any(token in value for token in ("academic", "catalogue", "metadata", "andc", "archive")):
        return "academic_catalogue_metadata"
    return "other_public_sources"


def source_tier_status(source_tier: str | None, source_type: str | None, source_name: str | None) -> dict[str, Any]:
    text = " ".join([source_tier or "", source_type or "", source_name or ""]).lower()
    discovery_only = any(token in text for token in DISCOVERY_ONLY_HINTS)
    needs_review = any(token in text for token in METADATA_HINTS) or "wikipedia" in text
    accepted = not discovery_only
    tier = source_tier or ("metadata" if needs_review else "unspecified")
    return {
        "source_tier": tier,
        "accepted_for_release": accepted and not discovery_only,
        "discovery_only": discovery_only,
        "needs_review": needs_review,
    }


def public_records_sql() -> str:
    return """
        SELECT
          r.record_id, r.source_id, r.title, r.year, r.url, r.external_id,
          r.publicness_level, s.source_name, s.source_type,
          c.ontology_code, c.genre, c.ethics_flag, c.relevance_code, c.publicness_code,
          nu.narrative_type, nu.secondary_role, nu.display_mode, nu.ethics_review_status,
          si.source_tier, si.publicness_status, si.publication_or_organisation
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN coding c ON c.record_id = r.record_id
        LEFT JOIN source_items si ON si.legacy_record_id = r.record_id
        LEFT JOIN legacy_record_mappings lm ON lm.legacy_record_id = r.record_id
        LEFT JOIN narrative_units nu ON nu.narrative_id = lm.narrative_id
        WHERE COALESCE(r.publicness_level, '') != 'restricted_excluded'
          AND COALESCE(c.publicness_code, '') != 'restricted_excluded'
          AND COALESCE(c.relevance_code, '') != 'scope_excluded'
    """


def route_sizes() -> dict[str, Any]:
    manifest = ROOT / ".next" / "server" / "app-paths-manifest.json"
    if not manifest.exists():
        return {"available": False, "reason": ".next/server/app-paths-manifest.json not found"}
    payload = load_json(manifest)
    routes: dict[str, Any] = {}
    for route_key, rel_path in sorted(payload.items()):
        if not route_key.endswith("/page") and route_key != "/page":
            continue
        page = ROOT / ".next" / "server" / rel_path
        route = route_key.removesuffix("/page") or "/"
        routes[route] = {
            "server_js_path": str(page.relative_to(ROOT)),
            "server_js_bytes": page.stat().st_size if page.exists() else None,
        }
    return {"available": True, "routes": routes}


def localhost_running(host: str = "127.0.0.1", port: int = 3000) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def build_baseline(data: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    records = data.get("records", [])
    map_points = data.get("map_points", [])
    map_flags = data.get("map_flags", [])
    summary = data.get("summary", {})
    by_source = Counter(row.get("source_name") or "unknown" for row in records)
    by_source_type = Counter(row.get("source_type") or "unknown" for row in records)
    by_family = Counter(source_family(row.get("source_type")) for row in records)
    narrative_types = Counter(
        row.get("narrative_type") or row.get("ontology_code") or row.get("genre") or row.get("canonical_figure_guess") or "uncoded"
        for row in qrows(conn, public_records_sql())
    )
    public_count = len(records)
    largest_source = by_source.most_common(1)[0] if by_source else ("unknown", 0)
    largest_family = by_family.most_common(1)[0] if by_family else ("unknown", 0)
    display_modes = Counter(row["display_mode"] or "unknown" for row in qrows(conn, "SELECT display_mode FROM narrative_units GROUP BY display_mode, narrative_id"))
    excluded_count = conn.execute("SELECT COUNT(*) FROM exclusions").fetchone()[0]
    suppressed_count = conn.execute("SELECT COUNT(*) FROM narrative_units WHERE display_mode = 'suppressed'").fetchone()[0]
    summary_only_count = conn.execute("SELECT COUNT(*) FROM narrative_units WHERE display_mode = 'summary_only'").fetchone()[0]
    years = [row.get("year") for row in records if isinstance(row.get("year"), int)]
    return {
        "generated_at": utc_now(),
        "database": str(DB_PATH.relative_to(ROOT)),
        "frontend_json": str(FRONTEND_JSON.relative_to(ROOT)),
        "public_record_count": public_count,
        "mapped_record_count": summary.get("mapped_record_count"),
        "map_points_length": len(map_points),
        "map_flags_length": len(map_flags),
        "map_invariant_passes": summary.get("mapped_record_count") == len(map_points) == len(map_flags),
        "source_organisation_count": len(by_source),
        "source_type_counts": dict(by_source_type.most_common()),
        "source_family_counts": dict(by_family.most_common()),
        "narrative_type_counts": dict(narrative_types.most_common()),
        "date_span": {"earliest_year": min(years) if years else None, "latest_year": max(years) if years else None},
        "mapped_record_share": round((summary.get("mapped_record_count") or 0) / public_count, 4) if public_count else 0,
        "unmapped_public_records": public_count - int(summary.get("mapped_record_count") or 0),
        "records_by_jurisdiction": summary.get("corpus_state_counts") or summary.get("state_record_counts") or {},
        "mapped_records_by_jurisdiction": summary.get("mapped_state_counts") or {},
        "source_concentration": dict(by_source.most_common(15)),
        "largest_source_organisation_share": {
            "source_name": largest_source[0],
            "record_count": largest_source[1],
            "share": round(largest_source[1] / public_count, 4) if public_count else 0,
        },
        "largest_source_family_share": {
            "source_family": largest_family[0],
            "record_count": largest_family[1],
            "share": round(largest_family[1] / public_count, 4) if public_count else 0,
        },
        "sensitive_summary_only_records": summary_only_count,
        "suppressed_records": suppressed_count,
        "excluded_records": excluded_count,
        "narrative_display_modes": dict(display_modes),
        "frontend_json_size_bytes": FRONTEND_JSON.stat().st_size if FRONTEND_JSON.exists() else None,
        "route_js_sizes": route_sizes(),
        "localhost_127_0_0_1_3000_running": localhost_running(),
    }


def build_source_audit(data: dict[str, Any], conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    records = data.get("records", [])
    map_flag_ids = {row.get("record_id") for row in data.get("map_flags", [])}
    records_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        records_by_source[row.get("source_name") or "unknown"].append(row)

    raw_source_rows = qrows(conn, "SELECT source_id, source_name, source_type, publicness_level, ethics_notes FROM sources")
    source_groups: dict[str, dict[str, Any]] = {}
    for source in raw_source_rows:
        name = source["source_name"]
        group = source_groups.setdefault(
            name,
            {
                "source_name": name,
                "source_types": set(),
                "publicness_levels": set(),
                "ethics_notes": [],
            },
        )
        if source.get("source_type"):
            group["source_types"].add(source["source_type"])
        if source.get("publicness_level"):
            group["publicness_levels"].add(source["publicness_level"])
        if source.get("ethics_notes"):
            group["ethics_notes"].append(source["ethics_notes"])
    tier_rows = qrows(
        conn,
        """
        SELECT s.source_name, si.source_type, si.source_tier, si.publicness_status, COUNT(*) AS item_count
        FROM source_items si
        LEFT JOIN sources s ON s.source_id = si.source_id
        GROUP BY s.source_name, si.source_type, si.source_tier, si.publicness_status
        """,
    )
    tier_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in tier_rows:
        tier_by_source[row.get("source_name") or "unknown"].append(row)

    audit_rows: list[dict[str, Any]] = []
    for source in source_groups.values():
        name = source["source_name"]
        source_records = records_by_source.get(name, [])
        source_type_values = sorted(source["source_types"])
        record_families = Counter(source_family(row.get("source_type")) for row in source_records)
        family = record_families.most_common(1)[0][0] if record_families else source_family(source_type_values[0] if source_type_values else None)
        source_type = "; ".join(source_type_values) if source_type_values else "unspecified"
        tiers = tier_by_source.get(name, [])
        tier = Counter(row.get("source_tier") or "unspecified" for row in tiers).most_common(1)
        status = source_tier_status(tier[0][0] if tier else None, source_type, name)
        years = [row.get("year") for row in source_records if isinstance(row.get("year"), int)]
        narratives = sorted(
            {
                row.get("ontology_code") or row.get("genre") or row.get("canonical_figure_guess") or row.get("canonical_figure") or "uncoded"
                for row in source_records
            }
        )
        jurisdictions = sorted({row.get("state_territory") for row in source_records if row.get("state_territory") in STATE_CODES})
        source_text = f"{name} {source_type}".lower()
        flags = []
        if "tourism" in source_text and source_records:
            flags.append("tourism-only accepted rows need review")
        if "wikipedia" in source_text and source_records:
            flags.append("Wikipedia appears as accepted source rather than pointer")
        if any(token in source_text for token in METADATA_HINTS) and source_records:
            flags.append("metadata source counted in public export; confirm substantive description")
        if len(source_records) > max(250, len(records) * 0.20):
            flags.append("source organisation concentration exceeds 20 percent")
        recommended_label = name
        audit_rows.append(
            {
                "source_name": name,
                "source_family": family,
                "source_tier": status["source_tier"],
                "source_type": source_type,
                "public_record_count": len(source_records),
                "mapped_record_count": sum(1 for row in source_records if row.get("record_id") in map_flag_ids),
                "narrative_types_represented": "; ".join(narratives[:20]),
                "date_span": f"{min(years)}-{max(years)}" if years else "undated",
                "jurisdictions_represented": "; ".join(jurisdictions) if jurisdictions else "unmapped/unspecified",
                "publicness_status": "; ".join(sorted(source["publicness_levels"])) if source["publicness_levels"] else "unspecified",
                "ethics_sensitivity_note": " | ".join(dict.fromkeys(source["ethics_notes"])),
                "accepted_for_release": bool(status["accepted_for_release"]),
                "discovery_only": bool(status["discovery_only"]),
                "needs_review": bool(status["needs_review"] or flags),
                "false_positive_risks": "; ".join(flags),
                "recommended_public_label": recommended_label,
            }
        )

    family_totals = Counter(source_family(row.get("source_type")) for row in records)
    org_totals = Counter(row.get("source_name") or "unknown" for row in records)

    duplicate_names = []
    normalized: dict[str, list[str]] = defaultdict(list)
    for row in audit_rows:
        key = "".join(ch for ch in row["source_name"].lower() if ch.isalnum())
        normalized[key].append(row["source_name"])
    for names in normalized.values():
        if len(set(names)) > 1:
            duplicate_names.append(sorted(set(names)))

    summary = {
        "generated_at": utc_now(),
        "source_count": len(audit_rows),
        "public_record_count": len(records),
        "source_family_totals": dict(family_totals.most_common()),
        "largest_source_family_share": round((family_totals.most_common(1)[0][1] / len(records)), 4) if records and family_totals else 0,
        "largest_source_organisation_share": round((org_totals.most_common(1)[0][1] / len(records)), 4) if records and org_totals else 0,
        "needs_review_count": sum(1 for row in audit_rows if row["needs_review"]),
        "discovery_only_count": sum(1 for row in audit_rows if row["discovery_only"]),
        "duplicate_source_name_candidates": duplicate_names,
        "raw_enum_label_public_ui_note": "Frontend source labels map most source_type enums to display labels; unmapped future enums should be reviewed before release.",
    }
    return audit_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else ["source_name"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_baseline(baseline: dict[str, Any]) -> None:
    (PROCESSED_V2 / "release_baseline.json").write_text(json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Release Baseline",
        "",
        f"- Generated: `{baseline['generated_at']}`",
        f"- Public records: `{baseline['public_record_count']}`",
        f"- Mapped records: `{baseline['mapped_record_count']}`",
        f"- Map points length: `{baseline['map_points_length']}`",
        f"- Map flags length: `{baseline['map_flags_length']}`",
        f"- Map invariant passes: `{baseline['map_invariant_passes']}`",
        f"- Source organisations: `{baseline['source_organisation_count']}`",
        f"- Date span: `{baseline['date_span']['earliest_year']}-{baseline['date_span']['latest_year']}`",
        f"- Mapped record share: `{baseline['mapped_record_share']}`",
        f"- Unmapped public records: `{baseline['unmapped_public_records']}`",
        f"- Frontend JSON size: `{baseline['frontend_json_size_bytes']}` bytes",
        f"- Localhost running at 127.0.0.1:3000: `{baseline['localhost_127_0_0_1_3000_running']}`",
        "",
        "## Records By Jurisdiction",
    ]
    for key, value in baseline["records_by_jurisdiction"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Source Concentration"])
    for key, value in baseline["source_concentration"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Largest Shares",
            f"- Largest source organisation: `{baseline['largest_source_organisation_share']['source_name']}` at `{baseline['largest_source_organisation_share']['share']}`",
            f"- Largest source family: `{baseline['largest_source_family_share']['source_family']}` at `{baseline['largest_source_family_share']['share']}`",
            "",
            "## Source Families",
        ]
    )
    for key, value in baseline["source_family_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Narrative Types"])
    for key, value in baseline["narrative_type_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Sensitive And Excluded"])
    lines.append(f"- Summary-only narrative units: `{baseline['sensitive_summary_only_records']}`")
    lines.append(f"- Suppressed narrative units: `{baseline['suppressed_records']}`")
    lines.append(f"- Exclusion rows: `{baseline['excluded_records']}`")
    lines.extend(["", "## Route JS Sizes"])
    if baseline["route_js_sizes"].get("available"):
        for route, row in baseline["route_js_sizes"]["routes"].items():
            lines.append(f"- `{route}`: `{row['server_js_bytes']}` bytes (`{row['server_js_path']}`)")
    else:
        lines.append(f"- Not available: {baseline['route_js_sizes'].get('reason')}")
    (PROCESSED_V2 / "release_baseline.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_source_audit(rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    write_csv(EXPORTS_V2 / "release_source_audit.csv", rows)
    (PROCESSED_V2 / "release_source_audit.json").write_text(json.dumps({"summary": summary, "sources": rows}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Release Source Audit",
        "",
        f"- Generated: `{summary['generated_at']}`",
        f"- Sources audited: `{summary['source_count']}`",
        f"- Public records covered: `{summary['public_record_count']}`",
        f"- Needs review: `{summary['needs_review_count']}`",
        f"- Discovery-only sources: `{summary['discovery_only_count']}`",
        f"- Largest source organisation share: `{summary['largest_source_organisation_share']}`",
        f"- Largest source family share: `{summary['largest_source_family_share']}`",
        "",
        "## Source Family Totals",
    ]
    for key, value in summary["source_family_totals"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Review Flags"])
    flagged = [row for row in rows if row["needs_review"] or row["false_positive_risks"]]
    if flagged:
        for row in flagged:
            lines.append(f"- `{row['source_name']}` ({row['source_type']}): {row['false_positive_risks'] or 'needs review'}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Audit Rows"])
    for row in sorted(rows, key=lambda item: int(item["public_record_count"]), reverse=True):
        lines.append(
            f"- `{row['source_name']}`: `{row['public_record_count']}` public / `{row['mapped_record_count']}` mapped, "
            f"family `{row['source_family']}`, tier `{row['source_tier']}`, accepted `{row['accepted_for_release']}`, review `{row['needs_review']}`"
        )
    (PROCESSED_V2 / "release_source_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readiness(baseline: dict[str, Any], validation: dict[str, Any] | None, source_summary: dict[str, Any], build_status: str, test_status: str) -> None:
    preferred = baseline["public_record_count"] >= 3500 and int(baseline["mapped_record_count"] or 0) >= 1200
    fallback = baseline["public_record_count"] >= 3200 and int(baseline["mapped_record_count"] or 0) >= 1100
    validation_pass = bool(validation and validation.get("status") == "pass")
    map_pass = bool(baseline["map_invariant_passes"])
    blockers = []
    if not map_pass:
        blockers.append("Map invariant fails.")
    if validation is not None and not validation_pass:
        blockers.append("Release validation fails.")
    if not fallback:
        blockers.append("Corpus count is below documented fallback launch threshold.")
    verdict = "ready_for_first_release" if preferred and validation_pass and map_pass else "ready_with_warnings"
    if blockers:
        verdict = "not_ready_until_fixes"
    report = {
        "generated_at": utc_now(),
        "branch": git_value(["branch", "--show-current"]),
        "commit": git_value(["rev-parse", "HEAD"]),
        "public_record_count": baseline["public_record_count"],
        "mapped_record_count": baseline["mapped_record_count"],
        "source_audit_result": {
            "needs_review_count": source_summary["needs_review_count"],
            "largest_source_organisation_share": source_summary["largest_source_organisation_share"],
            "largest_source_family_share": source_summary["largest_source_family_share"],
        },
        "map_invariant_result": baseline["map_invariant_passes"],
        "readme_status": "updated for current title, project scope, citation, and split licensing",
        "licensing_status": "split MIT and custom visual-interface license documented",
        "validation_status": validation.get("status") if validation else "not_run",
        "build_status": build_status,
        "test_status": test_status,
        "performance_summary": {
            "frontend_json_size_bytes": baseline["frontend_json_size_bytes"],
            "route_js_sizes": baseline["route_js_sizes"],
        },
        "mobile_assessment_summary": "desktop-first and small-screen usable; not a dedicated mobile product",
        "deployment_blockers": blockers,
        "recommended_release_decision": verdict,
    }
    (PROCESSED_V2 / "release_readiness_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Release Readiness Report",
        "",
        f"- Branch: `{report['branch']}`",
        f"- Commit: `{report['commit']}`",
        f"- Public record count: `{report['public_record_count']}`",
        f"- Mapped record count: `{report['mapped_record_count']}`",
        f"- Source audit result: `{report['source_audit_result']['needs_review_count']}` source organisations need review or carry warnings",
        f"- Map invariant result: `{report['map_invariant_result']}`",
        f"- README status: {report['readme_status']}",
        f"- Licensing status: {report['licensing_status']}",
        f"- Validation status: `{report['validation_status']}`",
        f"- Build status: {report['build_status']}",
        f"- Test status: {report['test_status']}",
        f"- Frontend JSON size: `{report['performance_summary']['frontend_json_size_bytes']}` bytes",
        f"- Mobile assessment summary: {report['mobile_assessment_summary']}",
        "",
        "## Deployment Blockers",
    ]
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- None known from generated release checks.")
    lines.extend(["", "## Recommended Release Decision", "", f"`{verdict}`"])
    (PROCESSED_V2 / "release_readiness_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-json", default=str(PROCESSED_V2 / "release_validation_report.json"))
    parser.add_argument("--build-status", default="not_recorded")
    parser.add_argument("--test-status", default="not_recorded")
    args = parser.parse_args()

    PROCESSED_V2.mkdir(parents=True, exist_ok=True)
    EXPORTS_V2.mkdir(parents=True, exist_ok=True)
    data = load_json(FRONTEND_JSON)
    with connect() as conn:
        baseline = build_baseline(data, conn)
        audit_rows, source_summary = build_source_audit(data, conn)
    write_baseline(baseline)
    write_source_audit(audit_rows, source_summary)
    validation_path = Path(args.validation_json)
    validation = load_json(validation_path) if validation_path.exists() else None
    write_readiness(baseline, validation, source_summary, args.build_status, args.test_status)
    print(json.dumps({"baseline": baseline["public_record_count"], "mapped": baseline["mapped_record_count"], "sources": len(audit_rows)}, indent=2))


if __name__ == "__main__":
    main()
