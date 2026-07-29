#!/usr/bin/env python3
"""Evaluate useful no-auth routes from candidate machine scores."""

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
    "route_id",
    "source_name",
    "pages_attempted",
    "pages_fetched",
    "candidates_staged",
    "priority_review_candidates",
    "promising_source_route_candidates",
    "noise_candidates",
    "duplicate_candidates",
    "priority_state_share",
    "gap_1926_1976_share",
    "noauth_yield_score",
    "recommended_action",
]
PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
GAP_BANDS = {"1926_1939", "1940_1954", "1955_1964", "1965_1976"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def evaluate(scores_path: Path, out_path: Path, report_path: Path) -> dict[str, Any]:
    rows = read_csv(scores_path)
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("route_id") or row.get("source_id") or "unknown"].append(row)
    out: list[dict[str, Any]] = []
    for route_id, route_rows in grouped.items():
        total = len(route_rows)
        buckets = Counter(row.get("machine_bucket") for row in route_rows)
        priority = buckets.get("PRIORITY_REVIEW_OPEN_RECORD", 0)
        promising = buckets.get("PROMISING_SOURCE_ROUTE", 0)
        noise = buckets.get("EXCLUDE_CONTEXT_NOISE", 0) + buckets.get("EXCLUDE_TOURISM_MARKETING", 0)
        dupes = buckets.get("EXCLUDE_DUPLICATE", 0)
        priority_state = sum(1 for row in route_rows if row.get("target_state") in PRIORITY_STATES)
        gap = sum(1 for row in route_rows if row.get("time_band") in GAP_BANDS)
        score = priority * 5 + promising * 2 - noise * 3 - dupes * 2
        if any("robots" in (row.get("machine_reasons") or "") for row in route_rows):
            action = "PAUSE_ROBOTS_OR_TERMS"
        elif total and noise / total >= 0.5:
            action = "PAUSE_NOISE"
        elif total and dupes / total >= 0.5:
            action = "PAUSE_DUPLICATES"
        elif priority / max(total, 1) >= 0.2:
            action = "EXPAND_NOAUTH_ROUTE"
        elif promising:
            action = "RETRY_WITH_BETTER_QUERY"
        elif total == 0:
            action = "MANUAL_REVIEW_ONLY"
        else:
            action = "ADD_SITE_SPECIFIC_ADAPTER"
        out.append(
            {
                "route_id": route_id,
                "source_name": route_rows[0].get("source_name") or "",
                "pages_attempted": "",
                "pages_fetched": "",
                "candidates_staged": total,
                "priority_review_candidates": priority,
                "promising_source_route_candidates": promising,
                "noise_candidates": noise,
                "duplicate_candidates": dupes,
                "priority_state_share": pct(priority_state, total),
                "gap_1926_1976_share": pct(gap, total),
                "noauth_yield_score": score,
                "recommended_action": action,
            }
        )
    out.sort(key=lambda row: (-int(row["noauth_yield_score"]), row["route_id"]))
    write_csv(out_path, out, FIELDS)
    actions = Counter(row["recommended_action"] for row in out)
    lines = [
        "# No-Auth Route Yield",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Score rows read: `{len(rows)}`",
        f"- Routes evaluated: `{len(out)}`",
        "",
        "## Recommended Actions",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(actions.items())] or ["- None"])
    lines.extend(["", "## Top Routes"])
    for row in out[:20]:
        lines.append(f"- `{row['route_id']}` score `{row['noauth_yield_score']}` -> `{row['recommended_action']}`")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"routes": len(out), "actions": dict(actions), "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    summary = evaluate(Path(args.scores), Path(args.out), Path(args.report))
    print(f"Evaluated no-auth routes: {summary['routes']}")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
