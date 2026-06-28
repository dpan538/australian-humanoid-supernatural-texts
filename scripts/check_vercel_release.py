#!/usr/bin/env python3
"""Validate the static frontend export used by Vercel deployments."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_JSON = ROOT / "public" / "data" / "frontend-data.json"
REPORT_DIR = ROOT / "data" / "processed" / "v2"
CHECK_JSON = REPORT_DIR / "vercel_release_check.json"
CHECK_MD = REPORT_DIR / "vercel_release_check.md"
BASELINE_JSON = REPORT_DIR / "vercel_release_baseline.json"
BASELINE_MD = REPORT_DIR / "vercel_release_baseline.md"


def load_frontend_data() -> dict[str, Any]:
  with FRONTEND_JSON.open("r", encoding="utf-8") as handle:
    return json.load(handle)


def contains_text(value: Any, needle: str) -> bool:
  if isinstance(value, str):
    return needle in value
  if isinstance(value, list):
    return any(contains_text(item, needle) for item in value)
  if isinstance(value, dict):
    return any(contains_text(item, needle) for item in value.values())
  return False


def main() -> int:
  REPORT_DIR.mkdir(parents=True, exist_ok=True)
  errors: list[str] = []
  warnings: list[str] = []

  if not FRONTEND_JSON.exists():
    errors.append("public/data/frontend-data.json is missing.")
    data: dict[str, Any] = {}
  else:
    try:
      data = load_frontend_data()
    except json.JSONDecodeError as exc:
      errors.append(f"frontend-data.json is not parseable JSON: {exc}")
      data = {}

  records = data.get("records") if isinstance(data.get("records"), list) else []
  map_flags = data.get("map_flags") if isinstance(data.get("map_flags"), list) else []
  map_points = data.get("map_points") if isinstance(data.get("map_points"), list) else []
  sources = data.get("sources") if isinstance(data.get("sources"), list) else []
  summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}

  if not isinstance(data.get("records"), list):
    errors.append("records array is missing or invalid.")
  if not isinstance(data.get("map_flags"), list):
    errors.append("map_flags array is missing or invalid.")
  if not isinstance(data.get("map_points"), list):
    errors.append("map_points array is missing or invalid.")

  record_ids = [record.get("record_id") for record in records if isinstance(record, dict)]
  record_id_counts = Counter(record_ids)
  duplicate_record_ids = sorted(record_id for record_id, count in record_id_counts.items() if count > 1)
  if duplicate_record_ids:
    errors.append(f"duplicate public record_id values: {duplicate_record_ids[:10]}")

  public_record_ids = set(record_ids)
  flag_record_ids = [flag.get("record_id") for flag in map_flags if isinstance(flag, dict)]
  missing_flag_refs = sorted(record_id for record_id in flag_record_ids if record_id not in public_record_ids)
  if missing_flag_refs:
    errors.append(f"map flags reference missing public records: {missing_flag_refs[:10]}")

  mapped_record_count = int(summary.get("mapped_record_count") or 0)
  if mapped_record_count != len(map_flags) or len(map_flags) != len(map_points):
    errors.append(
      "map invariant failed: "
      f"mapped_record_count={mapped_record_count}, map_flags={len(map_flags)}, map_points={len(map_points)}"
    )

  restricted_statuses = {"suppressed", "restricted", "rejected"}
  restricted_records = [
    record.get("record_id")
    for record in records
    if isinstance(record, dict)
    and (
      str(record.get("include_status") or "").lower() in restricted_statuses
      or str(record.get("publicness_level") or "").lower() in restricted_statuses
      or str(record.get("ingestion_status") or "").lower() in restricted_statuses
    )
  ]
  if restricted_records:
    errors.append(f"restricted/suppressed/rejected records appear in public export: {restricted_records[:10]}")

  if contains_text(data, "/Users/"):
    errors.append("frontend JSON contains a local /Users/ path.")
  if contains_text(data, "localhost") or contains_text(data, "127.0.0.1"):
    errors.append("frontend JSON contains a localhost URL or reference.")

  for field_name in ("record_count", "mapped_record_count", "source_count"):
    if field_name not in summary:
      warnings.append(f"summary.{field_name} is missing.")

  source_types = Counter(
    str(source.get("source_type") or "unknown")
    for source in sources
    if isinstance(source, dict)
  )
  source_orgs = {
    str(source.get("source_organization") or source.get("source_name") or source.get("name") or "unknown")
    for source in sources
    if isinstance(source, dict)
  }

  frontend_size = FRONTEND_JSON.stat().st_size if FRONTEND_JSON.exists() else 0
  package_lock = ROOT / "package-lock.json"
  package_manager = "npm" if package_lock.exists() else "unknown"

  result = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "domain_target": "ausfigures.com",
    "frontend_json": str(FRONTEND_JSON.relative_to(ROOT)),
    "frontend_json_bytes": frontend_size,
    "public_record_count": len(records),
    "summary_record_count": summary.get("record_count"),
    "mapped_record_count": mapped_record_count,
    "map_flags_length": len(map_flags),
    "map_points_length": len(map_points),
    "source_count": len(sources),
    "source_organization_count": len(source_orgs),
    "source_type_counts": dict(sorted(source_types.items())),
    "earliest_year": summary.get("earliest_year"),
    "latest_year": summary.get("latest_year"),
    "package_manager": package_manager,
    "next_version": read_next_version(),
    "build_command": "npm run build",
    "errors": errors,
    "warnings": warnings,
    "status": "pass" if not errors else "fail",
  }

  CHECK_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  BASELINE_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

  markdown = render_markdown(result)
  CHECK_MD.write_text(markdown, encoding="utf-8")
  BASELINE_MD.write_text(markdown.replace("# Vercel Release Check", "# Vercel Release Baseline", 1), encoding="utf-8")

  print(f"Vercel release check: {result['status']}")
  print(f"public_records={len(records)} mapped_records={mapped_record_count} map_flags={len(map_flags)} map_points={len(map_points)}")
  print(f"frontend_json_bytes={frontend_size}")
  for warning in warnings:
    print(f"WARNING: {warning}")
  for error in errors:
    print(f"ERROR: {error}")
  return 0 if not errors else 1


def read_next_version() -> str:
  package_json = ROOT / "package.json"
  if not package_json.exists():
    return "unknown"
  data = json.loads(package_json.read_text(encoding="utf-8"))
  return str(data.get("dependencies", {}).get("next") or "unknown")


def render_markdown(result: dict[str, Any]) -> str:
  lines = [
    "# Vercel Release Check",
    "",
    f"Generated: `{result['generated_at']}`",
    f"Status: `{result['status']}`",
    f"Domain target: `{result['domain_target']}`",
    "",
    "## Static Data",
    "",
    f"- Frontend JSON: `{result['frontend_json']}`",
    f"- Frontend JSON size: `{result['frontend_json_bytes']}` bytes",
    f"- Public records: `{result['public_record_count']}`",
    f"- Mapped records: `{result['mapped_record_count']}`",
    f"- map_flags length: `{result['map_flags_length']}`",
    f"- map_points length: `{result['map_points_length']}`",
    f"- Source organizations: `{result['source_organization_count']}`",
    f"- Source rows: `{result['source_count']}`",
    f"- Date span: `{result['earliest_year']}`-`{result['latest_year']}`",
    "",
    "## Build Model",
    "",
    f"- Package manager: `{result['package_manager']}`",
    f"- Next.js dependency: `{result['next_version']}`",
    f"- Production build command: `{result['build_command']}`",
    "- Runtime SQLite dependency: none detected by this static export check",
    "",
    "## Source Types",
    "",
  ]
  for key, value in result["source_type_counts"].items():
    lines.append(f"- `{key}`: `{value}`")
  lines.extend(["", "## Warnings", ""])
  lines.extend([f"- {warning}" for warning in result["warnings"]] or ["- None"])
  lines.extend(["", "## Errors", ""])
  lines.extend([f"- {error}" for error in result["errors"]] or ["- None"])
  return "\n".join(lines) + "\n"


if __name__ == "__main__":
  raise SystemExit(main())
