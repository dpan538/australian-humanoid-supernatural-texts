#!/usr/bin/env python3
"""Validate the HSS paper release outputs for safety and count consistency."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

from paper_common import (
    DEFAULT_CONFIG,
    docs_dir,
    has_sensitive_term,
    load_config,
    load_json,
    rel_path,
    release_dir,
    resolve_repo_path,
    row_is_sensitive,
    write_csv,
    write_json,
    write_manifest,
)


SCRIPT_NAME = "validate_paper_release.py"

SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|cookie|authorization|bearer|token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-./+=]{12,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_SAMPLE_COLUMNS = {
    "snippet",
    "description",
    "summary",
    "raw_metadata_json",
    "source_chain_json",
    "url",
    "full_url",
    "full_text_path",
    "extracted_text_path",
    "raw_snapshot_path",
}

REQUIRED_COUNT_FAMILIES = {
    "live_public_website_display_counts",
    "local_frontend_export_display_counts",
    "legacy_flat_record_corpus_counts",
    "v2_normalized_public_corpus_counts",
    "strict_no_credential_record_gate_experiment_counts",
    "lead_mode_conversion_counts",
    "priority_lead_counts",
    "mapped_public_record_counts",
    "source_organisation_source_type_counts",
    "source_family_concentration_counts",
    "blocker_counts",
    "missingness_counts",
}


def iter_files(paths: list[Path], suffixes: set[str] | None = None) -> list[Path]:
    files: list[Path] = []
    for root in paths:
        if not root.exists():
            continue
        if root.is_file():
            if suffixes is None or root.suffix.lower() in suffixes:
                files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and (suffixes is None or path.suffix.lower() in suffixes):
                files.append(path)
    return sorted(files)


def check_secrets(paths: list[Path], suffixes: set[str]) -> list[dict[str, str]]:
    findings = []
    for path in iter_files(paths, suffixes):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append({"check": "no_secrets", "status": "FAIL", "details": f"secret-like pattern in {rel_path(path)}"})
                break
    return findings


def check_forbidden_extensions(root: Path, forbidden: set[str]) -> list[dict[str, str]]:
    findings = []
    for path in iter_files([root], None):
        if path.suffix.lower() in forbidden:
            findings.append({"check": "no_raw_or_binary_copied", "status": "FAIL", "details": f"forbidden extension in release: {rel_path(path)}"})
    return findings


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def check_audit_sample(path: Path) -> list[dict[str, str]]:
    findings = []
    if not path.exists():
        return [{"check": "audit_sample_present", "status": "WARN", "details": f"missing audit sample: {rel_path(path)}"}]
    rows = read_csv_dicts(path)
    columns = set(rows[0].keys()) if rows else set()
    forbidden = sorted(columns.intersection(FORBIDDEN_SAMPLE_COLUMNS))
    if forbidden:
        findings.append({"check": "sample_no_raw_text_columns", "status": "FAIL", "details": f"forbidden sample columns: {', '.join(forbidden)}"})
    metadata_fields = [
        "lead_type",
        "constraint_blocker",
        "source_family",
        "route_family",
        "source_name",
        "target_state",
        "url_domain",
    ]
    for index, row in enumerate(rows, start=2):
        sample_view = {field: row.get(field, "") for field in metadata_fields}
        if row_is_sensitive(sample_view) or any(has_sensitive_term(row.get(field, "")) for field in metadata_fields):
            findings.append({"check": "sample_no_sensitive_rows", "status": "FAIL", "details": f"sensitive-looking metadata in {rel_path(path)} line {index}"})
            break
    return findings


def markdown_count_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    rows = []
    in_table = False
    headers: list[str] = []
    for line in lines:
        if not line.startswith("|"):
            if in_table and rows:
                break
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if parts[:3] == ["count_family", "metric", "value"]:
            headers = parts
            in_table = True
            continue
        if in_table and parts and set(parts[0]) <= {"-", ":"}:
            continue
        if in_table and headers and len(parts) == len(headers):
            rows.append(dict(zip(headers, parts)))
    return rows


def check_count_markdown(stats_path: Path, markdown_paths: list[Path]) -> list[dict[str, str]]:
    stats, warnings = load_json(stats_path)
    findings = []
    if not stats:
        return [{"check": "stats_json_present", "status": "FAIL", "details": f"missing or invalid stats JSON: {rel_path(stats_path)}"}]
    count_map = {
        (str(row.get("count_family")), str(row.get("metric"))): str(row.get("value", ""))
        for row in stats.get("counts", [])
    }
    for path in markdown_paths:
        rows = markdown_count_rows(path)
        if not rows:
            findings.append({"check": "markdown_counts_present", "status": "FAIL", "details": f"no generated count table in {rel_path(path)}"})
            continue
        for row in rows:
            key = (row.get("count_family", ""), row.get("metric", ""))
            if key not in count_map:
                findings.append({"check": "markdown_count_matches_json", "status": "FAIL", "details": f"markdown count not in JSON: {rel_path(path)} {key}"})
                continue
            if str(row.get("value", "")) != count_map[key]:
                findings.append({"check": "markdown_count_matches_json", "status": "FAIL", "details": f"value mismatch in {rel_path(path)} {key}: {row.get('value')} != {count_map[key]}"})
                break
    return findings


def check_count_family_separation(stats_path: Path) -> list[dict[str, str]]:
    stats, _ = load_json(stats_path)
    if not stats:
        return []
    families = {str(row.get("count_family")) for row in stats.get("counts", [])}
    missing = sorted(REQUIRED_COUNT_FAMILIES - families)
    findings = []
    if missing:
        findings.append({"check": "required_count_families_present", "status": "FAIL", "details": f"missing count families: {', '.join(missing)}"})
    for row in stats.get("counts", []):
        joined = f"{row.get('count_family')} {row.get('metric')}".lower()
        if "combined" in joined and "frontend" in joined and ("lead" in joined or "experiment" in joined):
            findings.append({"check": "frontend_not_mixed_with_experiment_counts", "status": "FAIL", "details": f"combined frontend/experiment metric: {row.get('count_family')}.{row.get('metric')}"})
    return findings


def validate(config: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    validation_config = config.get("validation", {})
    scan_suffixes = {str(ext).lower() for ext in validation_config.get("secret_scan_extensions", [".csv", ".json", ".md", ".svg"])}
    forbidden_exts = {str(ext).lower() for ext in validation_config.get("forbidden_release_extensions", [])}
    markdown_paths = [resolve_repo_path(path) for path in validation_config.get("generated_markdown_with_counts", [])]
    stats_path = out_dir / "paper_stats.json"

    findings: list[dict[str, str]] = []
    findings.extend(check_secrets([out_dir, docs_dir(config)], scan_suffixes))
    findings.extend(check_forbidden_extensions(out_dir, forbidden_exts))
    findings.extend(check_audit_sample(out_dir / "paper_manual_audit_sample.csv"))
    findings.extend(check_count_markdown(stats_path, markdown_paths))
    findings.extend(check_count_family_separation(stats_path))

    if not findings:
        findings.append({"check": "paper_release_validation", "status": "PASS", "details": "all validation checks passed"})
    status = "FAIL" if any(row["status"] == "FAIL" for row in findings) else ("WARN" if any(row["status"] == "WARN" for row in findings) else "PASS")
    payload = {"status": status, "findings": findings}
    write_json(out_dir / "paper_validation.json", payload)
    write_csv(out_dir / "paper_validation.csv", findings, ["check", "status", "details"])
    lines = ["# Paper Release Validation", "", f"- Status: `{status}`", "", "## Findings"]
    lines.extend([f"- `{row['check']}`: {row['status']} - {row['details']}" for row in findings])
    (out_dir / "paper_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_manifest(
        out_dir / "validation_script_manifest.json",
        SCRIPT_NAME,
        [out_dir / "paper_validation.json", out_dir / "paper_validation.csv", out_dir / "paper_validation.md"],
        [stats_path, out_dir / "paper_manual_audit_sample.csv"] + markdown_paths,
        [],
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()
    config = load_config(Path(args.config))
    out_dir = Path(args.out_dir) if args.out_dir else release_dir(config)
    payload = validate(config, out_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    raise SystemExit(1 if payload["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
