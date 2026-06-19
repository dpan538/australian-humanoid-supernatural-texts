#!/usr/bin/env python3
"""Audit planned lead coverage for a public collection round.

This report is about planned public-source leads, not corpus records. A lead
becomes a record only after a concrete public source item has enough metadata
for the record card: date/year or date note, title or figure label, source,
URL/external id, snippet/description, publicness, and location evidence.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso


DEFAULT_LEADS_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_leads.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "public_round_002_coverage_audit.md"


def read_leads(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def planned_leads(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if row.get("collection_action") == "planned_public_query"
        and row.get("source_publicness_guard") == "ok_public_source"
        and row.get("high_noise_guard") != "BLOCKED_BARE_QUERY"
    ]


def counters(rows: list[dict[str, str]]) -> dict[str, Counter[str]]:
    by_band: Counter[str] = Counter()
    by_location_hint: Counter[str] = Counter()
    by_source_type: Counter[str] = Counter()
    by_figure: Counter[str] = Counter()
    by_priority: Counter[str] = Counter()
    by_guard: Counter[str] = Counter()
    for row in rows:
        by_band[row.get("date_band") or "unknown"] += 1
        hint = row.get("location_state_hint") or "source_required"
        if hint == "AU":
            hint = "article_specific_au"
        by_location_hint[hint] += 1
        by_source_type[row.get("source_type") or "unknown"] += 1
        by_figure[row.get("figure") or "unknown"] += 1
        by_priority[row.get("execution_priority") or "unknown"] += 1
        by_guard[row.get("high_noise_guard") or "unknown"] += 1
    return {
        "by_band": by_band,
        "by_location_hint": by_location_hint,
        "by_source_type": by_source_type,
        "by_figure": by_figure,
        "by_priority": by_priority,
        "by_guard": by_guard,
    }


def percent(count: int, total: int) -> str:
    return f"{count / total:.1%}" if total else "0.0%"


def write_counter(lines: list[str], title: str, counter: Counter[str], total: int) -> None:
    lines.extend(["", f"## {title}", ""])
    if not counter:
        lines.append("- None")
        return
    for key, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{key}`: {count} ({percent(count, total)})")


def imbalance_notes(total: int, counts: dict[str, Counter[str]]) -> list[str]:
    notes: list[str] = []
    by_band = counts["by_band"]
    expected_bands = [
        "backsearch_negative_control",
        "early_anchor",
        "publication_expansion",
        "modern_yowie_heritage_tourism_media",
    ]
    missing_bands = [band for band in expected_bands if by_band.get(band, 0) == 0]
    if missing_bands:
        notes.append(f"Missing planned date bands: {', '.join(missing_bands)}.")
    if total:
        modern_share = by_band.get("modern_yowie_heritage_tourism_media", 0) / total
        backsearch_share = by_band.get("backsearch_negative_control", 0) / total
        if modern_share > 0.45 or backsearch_share < 0.15:
            notes.append(
                "Planned lead coverage is not balanced: modern material dominates and the 1803-1841 backsearch window is thin."
            )
    if counts["by_location_hint"].get("article_specific_au", 0) / max(total, 1) > 0.35:
        notes.append("Most planned leads require article-specific location extraction before map placement.")
    state_like = {
        key: value
        for key, value in counts["by_location_hint"].items()
        if key not in {"article_specific_au", "source_required"}
    }
    missing_states = [state for state in ["NSW", "VIC", "QLD", "WA", "SA", "TAS", "NT", "ACT"] if state not in state_like]
    if missing_states:
        notes.append(f"Planned state/territory hints are missing: {', '.join(missing_states)}.")
    return notes


def next_round_500_plan() -> list[str]:
    return [
        "Do not count query-level leads as records or frontend record cards.",
        "A new record must have enough card fields: date/year or date note, title or figure label, source, URL/external id, snippet/description, publicness, and location evidence.",
        "Use source-specific collectors or manual exports for concrete items, starting with Trove/NLA where article-level metadata can be verified.",
        "Suggested date quotas for the next 500 true records: 160 backsearch 1803-1841, 130 early anchor 1842-1875, 130 publication expansion 1876-1969, 80 modern 1970-present.",
        "Suggested region work: resolve article-specific AU leads into states first, then prioritise NSW, SA, TAS, ACT, and VIC until each has visible map/card presence.",
        "Validation-queue terms remain leads only until manually promoted after public-source and ethics review.",
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", help="Accepted for Makefile compatibility; not used by this lead audit")
    parser.add_argument("--round-prefix", default="public_round_002", help="Round label for the report")
    parser.add_argument("--leads", default=str(DEFAULT_LEADS_PATH), help="Lead-plan CSV path")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Markdown audit report path")
    args = parser.parse_args()

    rows = planned_leads(read_leads(Path(args.leads)))
    counts = counters(rows)
    total = len(rows)
    lines = [
        "# Public Round Lead Coverage Audit",
        "",
        f"Created at: `{utc_now_iso()}`",
        f"Round: `{args.round_prefix}`",
        f"Planned public leads audited: {total}",
        "",
        "This audit covers planned leads only. Leads are not records and must not be counted as frontend record cards until source-item metadata is verified.",
    ]
    for note in imbalance_notes(total, counts):
        lines.append(f"- NOTE: {note}")
    write_counter(lines, "Planned Date Band Coverage", counts["by_band"], total)
    write_counter(lines, "Planned Location Hint Coverage", counts["by_location_hint"], total)
    write_counter(lines, "Planned Source-Type Coverage", counts["by_source_type"], total)
    write_counter(lines, "Planned Figure Coverage", counts["by_figure"], total)
    write_counter(lines, "Planned Execution Priority", counts["by_priority"], total)
    write_counter(lines, "Planned High-Noise Guard", counts["by_guard"], total)
    lines.extend(["", "## Next Round 500 Plan", ""])
    for item in next_round_500_plan():
        lines.append(f"- {item}")

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote lead coverage audit: {report_path}")


if __name__ == "__main__":
    main()
