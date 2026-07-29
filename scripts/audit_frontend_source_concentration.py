#!/usr/bin/env python3
"""Audit source concentration over the actual frontend public map rows."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, pct, write_csv


FIELDS = [
    "source_family",
    "source_name",
    "row_count",
    "share_percent",
    "rows_1926_1976",
    "rows_1930_1969",
    "rows_1955_1976",
    "recommended_action",
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def source_family(name: str | None) -> str:
    text = str(name or "").lower()
    if "australian yowie research" in text or "yowiehunters" in text or "ayr yowie" in text:
        return "AYR_FAMILY"
    if "internet archive" in text or "archive.org" in text:
        return "INTERNET_ARCHIVE_FAMILY"
    if "project gutenberg" in text or "gutenberg australia" in text:
        return "GUTENBERG_FAMILY"
    if "wikisource" in text:
        return "WIKISOURCE_FAMILY"
    if "trove" in text:
        return "TROVE_FAMILY"
    if "wikipedia" in text:
        return "WIKIPEDIA_FAMILY"
    return str(name or "UNKNOWN_SOURCE").strip() or "UNKNOWN_SOURCE"


def year(row: dict[str, Any]) -> int | None:
    raw = str(row.get("year") or row.get("date_published") or "")
    return int(raw[:4]) if len(raw) >= 4 and raw[:4].isdigit() else None


def in_range(row: dict[str, Any], start: int, end: int) -> bool:
    value = year(row)
    return value is not None and start <= value <= end


def recommended_action(family: str) -> str:
    if family == "AYR_FAMILY":
        return "keep_map_row_but_prioritize_stronger_evidence_source_chain"
    if family in {"INTERNET_ARCHIVE_FAMILY", "GUTENBERG_FAMILY", "WIKISOURCE_FAMILY"}:
        return "decompose_access_platform_to_original_source"
    if family in {"WIKIPEDIA_FAMILY"}:
        return "replace_discovery_source_with_evidence_source"
    return "monitor_source_balance"


def audit(canonical_map: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    rows = read_rows(canonical_map)
    by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_pair[(source_family(row.get("source_name")), str(row.get("source_name") or "UNKNOWN_SOURCE"))].append(row)
    output: list[dict[str, Any]] = []
    for (family, name), items in sorted(by_pair.items(), key=lambda item: (-len(item[1]), item[0])):
        output.append(
            {
                "source_family": family,
                "source_name": name,
                "row_count": len(items),
                "share_percent": pct(len(items), len(rows)),
                "rows_1926_1976": sum(1 for row in items if in_range(row, 1926, 1976)),
                "rows_1930_1969": sum(1 for row in items if in_range(row, 1930, 1969)),
                "rows_1955_1976": sum(1 for row in items if in_range(row, 1955, 1976)),
                "recommended_action": recommended_action(family),
            }
        )
    write_csv(out_path, output, FIELDS)
    write_report(report_path, rows, output)
    return output


def write_report(path: Path, rows: list[dict[str, Any]], output: list[dict[str, Any]]) -> None:
    family_counts = Counter()
    family_1926 = Counter()
    family_1930 = Counter()
    for row in rows:
        family = source_family(row.get("source_name"))
        family_counts[family] += 1
        if in_range(row, 1926, 1976):
            family_1926[family] += 1
        if in_range(row, 1930, 1969):
            family_1930[family] += 1
    total = len(rows)
    total_1926 = sum(family_1926.values())
    ayr_share = pct(family_counts.get("AYR_FAMILY", 0), total)
    combined_gap_share = pct(family_1926.get("AYR_FAMILY", 0) + family_1926.get("INTERNET_ARCHIVE_FAMILY", 0), total_1926)
    top5 = sum(count for _family, count in family_counts.most_common(5))
    lines = [
        "# Frontend Source Concentration Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total frontend public map rows: `{total}`",
        f"- Top 1 source family share: `{pct(family_counts.most_common(1)[0][1], total) if total else 0}`%",
        f"- Top 5 source family share: `{pct(top5, total)}`%",
        f"- AYR family share: `{ayr_share}`%",
        f"- AYR + Internet Archive share in 1926-1976 rows: `{combined_gap_share}`%",
        f"- AYR > 50 warning: `{'true' if ayr_share > 50 else 'false'}`",
        f"- 1926-1976 concentration warning: `{'true' if combined_gap_share > 80 else 'false'}`",
        "",
        "## Source Family Counts",
    ]
    lines.extend([f"- `{key}`: {count} ({pct(count, total)}%)" for key, count in family_counts.most_common()] or ["- None"])
    lines.extend(["", "## 1926-1976 Frontend Mapped Rows By Source Family"])
    lines.extend([f"- `{key}`: {count} ({pct(count, total_1926)}%)" for key, count in family_1926.most_common()] or ["- None"])
    lines.extend(["", "## 1930-1969 Frontend Mapped Rows By Source Family"])
    total_1930 = sum(family_1930.values())
    lines.extend([f"- `{key}`: {count} ({pct(count, total_1930)}%)" for key, count in family_1930.most_common()] or ["- None"])
    lines.extend(
        [
            "",
            "## Recommended Remediation",
            "- Do not demote map rows merely because source is AYR.",
            "- Add stronger evidence/source-chain replacement tasks for weak discovery chains.",
            "- Prioritize non-AYR institutional sources for new 1926-1976 additions.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-map", required=True)
    parser.add_argument("--canonical-map", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    del args.frontend_map
    rows = audit(Path(args.canonical_map), Path(args.out), Path(args.report))
    print(f"Wrote frontend source concentration audit rows: {len(rows)}")


if __name__ == "__main__":
    main()
