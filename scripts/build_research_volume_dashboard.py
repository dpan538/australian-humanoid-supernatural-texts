#!/usr/bin/env python3
"""Build a non-expert dashboard for research-volume expansion."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from migrate_research_volume_expansion_v1 import migrate


def dashboard(db_path: Path, run_id: str, out: Path) -> dict[str, object]:
    migrate(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        items = [dict(row) for row in conn.execute("SELECT * FROM research_volume_items WHERE run_id=?", (run_id,)).fetchall()]
        run = dict(conn.execute("SELECT * FROM research_volume_runs WHERE run_id=?", (run_id,)).fetchone() or {})
    layers = Counter(row["layer"] for row in items)
    families = Counter(row.get("route_family") or "unknown" for row in items)
    states = Counter(row.get("target_state") or "unknown" for row in items)
    bands = Counter(row.get("time_band") or "unknown" for row in items)
    tiers = Counter(row.get("source_tier") or "unknown" for row in items)
    target_period = sum(1 for row in items if int(row.get("is_target_period") or 0))
    priority = sum(1 for row in items if int(row.get("is_priority_item") or 0))
    non_aggregator = sum(1 for row in items if int(row.get("is_non_aggregator") or 0))
    meaningful = len(items) >= 5000 and priority >= 5000 and target_period >= 2000
    concentration_top = families.most_common(1)[0][1] / len(items) * 100 if items and families else 0
    continue_or_pause = "pause for analysis" if len(items) >= 25000 else "continue volume expansion"
    if concentration_top > 60:
        continue_or_pause = "pause for source-balance analysis"
    lines = [
        "# Research Volume Non-Expert Dashboard",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        "",
        "## Is Growth Meaningful?",
        f"- New research-layer items: `{len(items)}`",
        f"- Priority leads or provisional candidates: `{priority}`",
        f"- 1926-1976 targeted items: `{target_period}`",
        f"- Growth is meaningful: `{str(meaningful).lower()}`",
        "",
        "## Layer Separation",
        f"- Accepted public records automatically created: `0`",
        f"- Provisional records: `{layers.get('provisional_record', 0)}`",
        f"- Target-gap leads: `{layers.get('target_gap_lead', 0)}`",
        f"- Metadata-only leads: `{layers.get('metadata_only_lead', 0)}`",
        f"- Auxiliary source intelligence: `{layers.get('auxiliary_source_intelligence', 0)}`",
        "",
        "## Source Families Expanding",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in families.most_common(10)] or ["- None"])
    lines.extend(["", "## 1926-1976 Improvement"])
    lines.extend([f"- `{key}`: {value}" for key, value in bands.most_common()] or ["- None"])
    lines.extend(["", "## Priority-State Improvement"])
    lines.extend([f"- `{key}`: {value}" for key, value in states.most_common()] or ["- None"])
    lines.extend(
        [
            "",
            "## Source Concentration",
            f"- Top source-family concentration: `{round(concentration_top, 2)}%`",
            f"- Non-AYR/Wikipedia/tourism/paranormal share: `{round((non_aggregator / len(items) * 100) if items else 0, 2)}%`",
            "",
            "## Evidence-Tier Distribution",
        ]
    )
    lines.extend([f"- `{key}`: {value}" for key, value in tiers.most_common()] or ["- None"])
    lines.extend(
        [
            "",
            "## Recommendation",
            f"- Continue crawling or pause: `{continue_or_pause}`",
            "- Public record promotion remains closed.",
            "- Row-level CSV review is not required for this dashboard.",
        ]
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"new_items": len(items), "priority_items": priority, "target_period_items": target_period, "recommendation": continue_or_pause, "out": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default="research_volume_expansion_001")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    print(json.dumps(dashboard(Path(args.db), args.run_id, Path(args.out)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
