#!/usr/bin/env python3
"""Merge and strictly re-clean live gap crawl candidate CSVs."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from crawl_gap_public_metadata import CANDIDATE_FIELDS, QUERY_FAMILIES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "live_crawl" / "public_metadata_live_combined_strict_candidates.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_live_crawl_strict_cleaning.md"

FAMILY_BY_ID = {family.family_id: family for family in QUERY_FAMILIES}


def strict_ok(row: dict[str, str]) -> tuple[bool, str]:
    if row.get("candidate_status") != "public_metadata_candidate":
        return False, row.get("relevance_status") or "not_candidate"
    family = FAMILY_BY_ID.get(row.get("query_family_id") or "")
    if family is None:
        return False, "unknown_query_family"
    matched = {term for term in (row.get("figure_terms_matched") or "").split(";") if term}
    family_id = family.family_id
    if family_id.endswith("_yowie_named") and family_id != "yowie_exact_named":
        place_terms = {term for term in family.terms if term not in {"yowie", "bigfoot", "australian bigfoot"}}
        if "yowie" not in matched or not (matched & place_terms):
            return False, "missing_required_place_yowie_pair"
    if "ghost_named" in family_id or "haunted_named" in family_id:
        place_terms = {term for term in family.terms if term not in {"ghost", "haunted", "asylum"}}
        if not ({"ghost", "haunted"} & matched) or not (matched & place_terms):
            return False, "missing_required_place_ghost_pair"
    return True, ""


def key_for(row: dict[str, str]) -> str:
    return row.get("external_id") or row.get("url") or f"{row.get('title')}:{row.get('year')}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    kept: list[dict[str, str]] = []
    seen: set[str] = set()
    reject_reasons: Counter[str] = Counter()
    input_rows = 0
    candidate_rows = 0
    family_kept: Counter[str] = Counter()
    family_rejected: Counter[str] = Counter()

    for path in args.inputs:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                input_rows += 1
                if row.get("candidate_status") == "public_metadata_candidate":
                    candidate_rows += 1
                ok, reason = strict_ok(row)
                if not ok:
                    reject_reasons[reason] += 1
                    family_rejected[row.get("query_family_id") or "unknown"] += 1
                    continue
                key = key_for(row)
                if key in seen:
                    reject_reasons["duplicate_after_strict_cleaning"] += 1
                    family_rejected[row.get("query_family_id") or "unknown"] += 1
                    continue
                seen.add(key)
                kept.append(row)
                family_kept[row.get("query_family_id") or "unknown"] += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_FIELDS)
        writer.writeheader()
        for row in kept:
            writer.writerow({field: row.get(field, "") for field in CANDIDATE_FIELDS})

    lines = [
        "# 1926-2011 Live Crawl Strict Cleaning",
        "",
        f"- Input rows: {input_rows}",
        f"- Public metadata candidate rows before strict filter: {candidate_rows}",
        f"- Strict deduped candidates kept: {len(kept)}",
        f"- Loss from candidate rows: {candidate_rows - len(kept)}",
        "",
        "## Kept By Query Family",
    ]
    for family, count in family_kept.most_common():
        lines.append(f"- {family}: {count}")
    lines.extend(["", "## Rejected By Reason"])
    for reason, count in reject_reasons.most_common():
        lines.append(f"- {reason}: {count}")
    lines.extend(["", "## Rejected By Query Family"])
    for family, count in family_rejected.most_common(30):
        lines.append(f"- {family}: {count}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote strict candidates: {args.output}")
    print(f"Wrote strict cleaning report: {args.report}")
    print(f"Strict candidates kept: {len(kept)}")


if __name__ == "__main__":
    main()
