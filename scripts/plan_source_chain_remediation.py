#!/usr/bin/env python3
"""Turn source-chain score buckets into remediation review batches."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_batch(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    write_csv(path, rows, fieldnames)


def plan_remediation(source_chain_scores: Path, out_dir: Path) -> dict[str, int]:
    rows = read_rows(source_chain_scores)
    fieldnames = list(rows[0].keys()) if rows else ["record_id", "narrative_unit_id", "candidate_id", "machine_bucket", "reviewer_notes"]
    batches = {
        "access_platform_decompose_batch.csv": [row for row in rows if row.get("machine_bucket") == "AMBER_D_NEEDS_ORIGINAL"],
        "discovery_only_replacement_batch.csv": [row for row in rows if row.get("machine_bucket") == "RED_DISCOVERY_ONLY_LEAKAGE"],
        "unknown_source_registry_batch.csv": [row for row in rows if row.get("machine_bucket") == "AMBER_UNKNOWN_SOURCE"],
        "hold_batch.csv": [row for row in rows if row.get("machine_bucket") == "HOLD"],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, batch in batches.items():
        write_batch(out_dir / name, batch, fieldnames)
    counts = {name: len(batch) for name, batch in batches.items()}
    bucket_counts = Counter(row.get("machine_bucket") or "unknown" for row in rows)
    lines = [
        "# Source Chain Remediation Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Source-chain rows scored: `{len(rows)}`",
        "",
        "## Batch Counts",
    ]
    lines.extend([f"- `{name}`: {count}" for name, count in counts.items()])
    lines.extend(["", "## Proposed Automated Strategy"])
    lines.extend(
        [
            "- Internet Archive, Project Gutenberg, Gutenberg Australia, Wikisource, and PANDORA rows: parse or review original publication metadata; keep access platform tier D until original source is explicit.",
            "- Australian Yowie Research, Wikipedia, paranormal aggregators, and tourism pages: search for stronger public evidence sources; do not treat aggregators as evidence.",
            "- Unknown source names: attempt `source_registry.yml` matching or create source-registry candidate rows for review.",
            "",
            "## Batch Size Recommendations",
            "- Top 100 access-platform decomposition rows first.",
            "- Top 100 discovery-only replacement rows second.",
            "- Top 50 unknown-source registry rows third.",
            "",
            "## Bucket Distribution",
        ]
    )
    lines.extend([f"- `{key}`: {bucket_counts[key]}" for key in sorted(bucket_counts)] or ["- None"])
    (out_dir / "remediation_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-chain-scores", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    counts = plan_remediation(Path(args.source_chain_scores), Path(args.out_dir))
    print(f"Wrote source-chain remediation plan: {args.out_dir}")
    for name, count in counts.items():
        print(f"{name}: {count}")


if __name__ == "__main__":
    main()
