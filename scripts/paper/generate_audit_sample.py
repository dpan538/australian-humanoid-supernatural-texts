#!/usr/bin/env python3
"""Generate a deterministic redacted manual-audit lead sample."""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from paper_common import (
    DEFAULT_CONFIG,
    configured_path,
    connect,
    docs_dir,
    domain_only,
    load_config,
    now_iso,
    redacted_text,
    rel_path,
    release_dir,
    row_is_sensitive,
    sqlite_db_path,
    table_columns,
    table_exists,
    write_csv,
    write_json,
    write_manifest,
)


SCRIPT_NAME = "generate_audit_sample.py"

METADATA_FIELDS = [
    "sample_id",
    "source_population",
    "lead_id",
    "lead_type",
    "constraint_blocker",
    "source_family",
    "route_family",
    "priority_bucket",
    "lead_score",
    "source_name",
    "source_tier",
    "target_state",
    "inferred_year",
    "temporal_signal_present",
    "term_signal_present",
    "place_signal_present",
    "url_domain",
    "duplicate_status",
    "sample_stratum",
    "redaction_note",
]


def load_leads(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    db_path = sqlite_db_path(config)
    with connect(db_path) as conn:
        if not table_exists(conn, "target_gap_leads"):
            return [], ["target_gap_leads table not available; audit sample is empty."]
        columns = table_columns(conn, "target_gap_leads")
        expected = {
            "lead_id",
            "lead_type",
            "constraint_blocker",
            "source_family",
            "route_family",
            "priority_bucket",
            "lead_score",
            "source_name",
            "source_tier",
            "target_state",
            "inferred_year",
            "temporal_signal",
            "term_signal",
            "place_signal",
            "url",
            "duplicate_status",
            "ethics_status",
            "title",
            "evidence_gap",
        }
        missing = sorted(expected - columns)
        if missing:
            warnings.append(f"target_gap_leads missing optional expected fields: {', '.join(missing)}")
        selected = sorted(columns.intersection(expected))
        rows = [dict(row) for row in conn.execute(f"SELECT {', '.join(selected)} FROM target_gap_leads").fetchall()]
    return rows, warnings


def stratum_for(row: dict[str, Any]) -> str:
    blocker = str(row.get("constraint_blocker") or "(missing)").strip() or "(missing)"
    family = str(row.get("source_family") or "(missing)").strip() or "(missing)"
    return f"{blocker} / {family}"


def sample_rows(rows: list[dict[str, Any]], sample_size: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        strata[stratum_for(row)].append(row)
    for bucket in strata.values():
        rng.shuffle(bucket)

    selected: list[dict[str, Any]] = []
    ordered_keys = sorted(strata, key=lambda key: (-len(strata[key]), key))
    while ordered_keys and len(selected) < sample_size:
        next_keys = []
        for key in ordered_keys:
            if len(selected) >= sample_size:
                break
            bucket = strata[key]
            if bucket:
                selected.append(bucket.pop())
            if bucket:
                next_keys.append(key)
        ordered_keys = next_keys
    rng.shuffle(selected)
    return selected[:sample_size]


def redacted_sample_row(row: dict[str, Any], index: int, coding_columns: list[str]) -> dict[str, Any]:
    output = {
        "sample_id": f"audit_{index:03d}",
        "source_population": "target_gap_leads",
        "lead_id": row.get("lead_id", ""),
        "lead_type": row.get("lead_type", ""),
        "constraint_blocker": row.get("constraint_blocker", ""),
        "source_family": row.get("source_family", ""),
        "route_family": row.get("route_family", ""),
        "priority_bucket": row.get("priority_bucket", ""),
        "lead_score": row.get("lead_score", ""),
        "source_name": redacted_text(row.get("source_name", ""), 100),
        "source_tier": row.get("source_tier", ""),
        "target_state": row.get("target_state", ""),
        "inferred_year": row.get("inferred_year", ""),
        "temporal_signal_present": "1" if str(row.get("temporal_signal") or "").strip() else "0",
        "term_signal_present": "1" if str(row.get("term_signal") or "").strip() else "0",
        "place_signal_present": "1" if str(row.get("place_signal") or "").strip() else "0",
        "url_domain": domain_only(row.get("url")),
        "duplicate_status": row.get("duplicate_status", ""),
        "sample_stratum": stratum_for(row),
        "redaction_note": "metadata_only_no_snippet_no_description_no_raw_text_sensitive_rows_excluded",
    }
    for column in coding_columns:
        output[column] = ""
    return output


def write_sample_doc(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Manual Audit Sample",
        "",
        f"- Generated: `{payload['generated_at']}`",
        f"- Sample size requested: `{payload['sample_size_requested']}`",
        f"- Sample size written: `{payload['sample_size_written']}`",
        f"- Deterministic random seed: `{payload['random_seed']}`",
        f"- Candidate leads before sensitivity filter: `{payload['lead_rows_seen']}`",
        f"- Rows excluded by sensitivity/redaction rule: `{payload['sensitive_rows_excluded']}`",
        f"- Output CSV: `{payload['sample_csv']}`",
        "",
        "## Columns For Human Coding",
    ]
    lines.extend([f"- `{column}`" for column in payload["coding_columns"]])
    lines.extend(
        [
            "",
            "The sample omits snippets, descriptions, summaries, raw metadata, source-chain JSON, raw text paths, and full URLs. It includes only review metadata and URL domains.",
        ]
    )
    if payload["warnings"]:
        lines.extend(["", "## Warnings"])
        lines.extend([f"- {warning}" for warning in payload["warnings"]])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate(config: dict[str, Any], out_dir: Path, sample_size: int | None, seed: int | None) -> dict[str, Any]:
    audit_config = config.get("manual_audit", {})
    requested_size = int(sample_size or audit_config.get("sample_size") or 100)
    random_seed = int(seed if seed is not None else audit_config.get("random_seed") or 538)
    coding_columns = list(audit_config.get("coding_columns") or [])
    rows, warnings = load_leads(config)
    exclude_sensitive = bool(audit_config.get("exclude_sensitive_rows", True))
    filtered = []
    sensitive_count = 0
    for row in rows:
        if exclude_sensitive and row_is_sensitive(row):
            sensitive_count += 1
            continue
        filtered.append(row)
    selected = sample_rows(filtered, min(requested_size, len(filtered)), random_seed)
    sample = [redacted_sample_row(row, index + 1, coding_columns) for index, row in enumerate(selected)]

    sample_csv = out_dir / "paper_manual_audit_sample.csv"
    manifest_json = out_dir / "paper_manual_audit_sample_manifest.json"
    sample_md = out_dir / "paper_manual_audit_sample.md"
    fieldnames = METADATA_FIELDS + coding_columns
    write_csv(sample_csv, sample, fieldnames)
    payload = {
        "generated_at": now_iso(),
        "sample_size_requested": requested_size,
        "sample_size_written": len(sample),
        "random_seed": random_seed,
        "lead_rows_seen": len(rows),
        "sensitive_rows_excluded": sensitive_count,
        "stratification": audit_config.get("stratify_by", ["constraint_blocker", "source_family"]),
        "sample_csv": rel_path(sample_csv),
        "coding_columns": coding_columns,
        "warnings": warnings,
    }
    write_json(manifest_json, payload)
    write_sample_doc(sample_md, payload)
    write_manifest(
        out_dir / "audit_sample_script_manifest.json",
        SCRIPT_NAME,
        [sample_csv, manifest_json, sample_md],
        [sqlite_db_path(config), configured_path(config, "inputs", "constraint_decision_yaml")],
        warnings,
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--sample-size", type=int)
    parser.add_argument("--seed", type=int)
    args = parser.parse_args()
    config = load_config(Path(args.config))
    out_dir = Path(args.out_dir) if args.out_dir else release_dir(config)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = generate(config, out_dir, args.sample_size, args.seed)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
