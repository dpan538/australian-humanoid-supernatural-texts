#!/usr/bin/env python3
"""Summarize machine QA outputs into a short non-expert action list."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def top_rows(rows: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    priority = [
        "RED_PUBLIC_SUPPRESS_ELIGIBLE",
        "RED_PUBLIC_DEMOTE_ELIGIBLE",
        "AMBER_PUBLIC_PLACE_REVIEW",
        "AMBER_PUBLIC_GEOCODE_REVIEW",
        "AMBER_PUBLIC_SOURCE_REVIEW",
    ]
    ranked = sorted(rows, key=lambda row: (priority.index(row.get("machine_bucket")) if row.get("machine_bucket") in priority else 99, row.get("record_id") or ""))
    return [row for row in ranked if row.get("machine_bucket") in priority][:limit]


def write_summary(map_scores: Path, source_scores: Path, route_yield: Path, out_path: Path) -> dict[str, Any]:
    map_rows = read_rows(map_scores)
    source_rows = read_rows(source_scores)
    route_rows = read_rows(route_yield)
    map_buckets = Counter(row.get("machine_bucket") or "unknown" for row in map_rows)
    source_buckets = Counter(row.get("machine_bucket") or "unknown" for row in source_rows)
    route_actions = Counter(row.get("recommended_action") or "unknown" for row in route_rows)
    public_need_action = sum(map_buckets.get(key, 0) for key in map_buckets if key.startswith("RED_PUBLIC") or key.startswith("AMBER_PUBLIC"))
    internal_ignore = map_buckets.get("NONPUBLIC_IGNORE", 0)
    cleanup_safe = bool(map_buckets.get("RED_PUBLIC_DEMOTE_ELIGIBLE", 0) or map_buckets.get("RED_PUBLIC_SUPPRESS_ELIGIBLE", 0))
    source_blocker = source_buckets.get("RED_DISCOVERY_ONLY_LEAKAGE", 0) + source_buckets.get("AMBER_UNKNOWN_SOURCE", 0) + source_buckets.get("AMBER_D_NEEDS_ORIGINAL", 0)
    needs_probe = not route_rows and not read_rows(ROOT / "data" / "processed" / "v2" / "probe_candidate_scores.csv")

    lines = [
        "# Actionable Rows Summary",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Frontend-public map rows needing action: `{public_need_action}`",
        f"- Internal/nonpublic rows to ignore for public map cleanup: `{internal_ignore}`",
        f"- Map cleanup appears safe to dry-run: `{str(cleanup_safe).lower()}`",
        f"- Source-chain remediation rows: `{source_blocker}`",
        f"- Real Trove metadata probe needed before candidate scoring is meaningful: `{str(needs_probe).lower()}`",
        "",
        "## Do This Now",
    ]
    if source_blocker:
        lines.append("- Work the source-chain remediation batches, starting with discovery-only replacement and unknown-source registry matching.")
    if needs_probe:
        lines.append("- Run the planned first real Trove metadata probe when a Trove API key is available.")
    if public_need_action:
        lines.append("- Review the top public-map action rows below; do not review thousands of internal rows.")
    lines.extend(["", "## Do Not Do This"])
    lines.extend(
        [
            "- Do not treat `NONPUBLIC_IGNORE` rows as failed public map rows.",
            "- Do not accept candidates automatically.",
            "- Do not publish or demote map flags without explicit execution and backup.",
        ]
    )
    lines.extend(["", "## Safe Automated Actions"])
    lines.append("- Report generation, dry-run cleanup, and metadata-only probe planning are safe.")
    lines.extend(["", "## Requires Reviewer"])
    lines.append("- AMBER public map rows and source-chain remediation batches require human review.")
    lines.extend(["", "## Ignore / Internal Only"])
    lines.append(f"- `{internal_ignore}` rows are internal/nonpublic for frontend map cleanup purposes.")
    lines.extend(["", "## Top 20 Rows Requiring Review"])
    for row in top_rows(map_rows, 20):
        lines.append(
            f"- `{row.get('machine_bucket')}` record `{row.get('record_id')}` narrative `{row.get('narrative_unit_id')}`: "
            f"{row.get('title') or ''} ({row.get('hard_fail_reasons') or ''})"
        )
    if lines[-1] == "## Top 20 Rows Requiring Review":
        lines.append("- No public-map action rows found.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"public_need_action": public_need_action, "internal_ignore": internal_ignore, "source_blocker": source_blocker}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map-scores", required=True)
    parser.add_argument("--source-chain-scores", required=True)
    parser.add_argument("--route-yield", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    summary = write_summary(Path(args.map_scores), Path(args.source_chain_scores), Path(args.route_yield), Path(args.out))
    print(f"Wrote actionable summary: {args.out}")
    print(f"Frontend-public map rows needing action: {summary['public_need_action']}")


if __name__ == "__main__":
    main()
