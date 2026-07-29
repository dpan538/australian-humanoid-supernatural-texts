#!/usr/bin/env python3
"""Estimate source-chain remediation impact before any import or display change."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, pct, write_csv


FIELDS = [
    "scenario",
    "current_ayr_frontend_share",
    "current_ayr_1926_1976_share",
    "tasks_assumed_successful",
    "estimated_ayr_rows_after_replacement",
    "estimated_ayr_share_after_replacement",
    "new_non_ayr_records_needed_for_5pt_drop",
    "new_non_ayr_records_needed_for_10pt_drop",
    "new_non_ayr_records_needed_for_20pt_drop",
    "note",
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_metrics(rows: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    total = sum(int(row.get("row_count") or 0) for row in rows)
    ayr_total = sum(int(row.get("row_count") or 0) for row in rows if row.get("source_family") == "AYR_FAMILY")
    total_1926 = sum(int(row.get("rows_1926_1976") or 0) for row in rows)
    ayr_1926 = sum(int(row.get("rows_1926_1976") or 0) for row in rows if row.get("source_family") == "AYR_FAMILY")
    return total, ayr_total, total_1926, ayr_1926


def additions_needed(total: int, ayr_rows: int, drop_points: float) -> int:
    current = 0 if total == 0 else ayr_rows / total * 100
    target = max(0, current - drop_points)
    if target <= 0:
        return 0
    additions = 0
    while total + additions and ayr_rows / (total + additions) * 100 > target:
        additions += 1
    return additions


def estimate(frontend_audit: Path, replacement_tasks: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    audit_rows = read_rows(frontend_audit)
    tasks = read_rows(replacement_tasks)
    total, ayr_total, total_1926, ayr_1926 = audit_metrics(audit_rows)
    current_share = pct(ayr_total, total)
    current_gap_share = pct(ayr_1926, total_1926)
    rows: list[dict[str, Any]] = []
    for top_n in [50, 100, 250]:
        successful = min(top_n, len(tasks))
        estimated_ayr_after = max(0, ayr_total - successful)
        rows.append(
            {
                "scenario": f"top_{top_n}_replacement_tasks_succeed",
                "current_ayr_frontend_share": current_share,
                "current_ayr_1926_1976_share": current_gap_share,
                "tasks_assumed_successful": successful,
                "estimated_ayr_rows_after_replacement": estimated_ayr_after,
                "estimated_ayr_share_after_replacement": pct(estimated_ayr_after, total),
                "new_non_ayr_records_needed_for_5pt_drop": additions_needed(total, ayr_total, 5),
                "new_non_ayr_records_needed_for_10pt_drop": additions_needed(total, ayr_total, 10),
                "new_non_ayr_records_needed_for_20pt_drop": additions_needed(total, ayr_total, 20),
                "note": "source-chain replacement improves evidence quality; frontend source display must be updated to change displayed source share",
            }
        )
    write_csv(out_path, rows, FIELDS)
    write_report(report_path, rows)
    return rows


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    first = rows[0] if rows else {}
    lines = [
        "# Source Chain Remediation Impact",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Current AYR-family share among frontend map rows: `{first.get('current_ayr_frontend_share', 0)}`%",
        f"- Current AYR-family share among 1926-1976 frontend map rows: `{first.get('current_ayr_1926_1976_share', 0)}`%",
        "",
        "## Scenarios",
    ]
    for row in rows:
        lines.append(
            f"- `{row['scenario']}`: AYR rows after replacement `{row['estimated_ayr_rows_after_replacement']}`, "
            f"estimated displayed share `{row['estimated_ayr_share_after_replacement']}`%"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "- Source replacement improves evidence quality but may not reduce `source_name` share unless frontend source display is updated.",
            "- Adding new non-AYR institutional records reduces concentration more directly.",
            "- Best strategy: replace weak evidence chains for existing public rows and add new non-AYR 1926-1976 institutional records.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-source-audit", required=True)
    parser.add_argument("--replacement-tasks", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    rows = estimate(Path(args.frontend_source_audit), Path(args.replacement_tasks), Path(args.out), Path(args.report))
    print(f"Wrote remediation impact scenarios: {len(rows)}")


if __name__ == "__main__":
    main()
