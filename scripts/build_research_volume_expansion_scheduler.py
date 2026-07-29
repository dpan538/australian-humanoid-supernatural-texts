#!/usr/bin/env python3
"""Build a safe no-auth research-volume expansion schedule."""

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
from lib.research_volume import load_safe_sources, make_schedule, write_schedule
from migrate_research_volume_expansion_v1 import migrate


def build(db_path: Path, run_id: str, target_new_items: int, out: Path, report: Path, execute: bool) -> dict[str, object]:
    migrate(db_path)
    rows = make_schedule(run_id, target_new_items)
    if execute:
        out.parent.mkdir(parents=True, exist_ok=True)
        write_schedule(out, rows)
    layers = Counter(row["planned_layer"] for row in rows)
    families = Counter(row["route_family"] for row in rows)
    states = Counter(row["target_state"] for row in rows)
    blockers = Counter(row["constraint_blocker"] for row in rows)
    sources = load_safe_sources()
    lines = [
        "# Research Volume Expansion Schedule",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target new research-layer items: `{target_new_items}`",
        f"- Scheduled items: `{len(rows)}`",
        f"- Safe no-auth sources considered: `{len(sources)}`",
        "- Network fetches performed: `0`",
        "- Public records mutated: `no`",
        "- Map flags mutated: `no`",
        "- Frontend/public data promoted: `no`",
        "",
        "## Layers",
    ]
    lines.extend([f"- `{key}`: {value}" for key, value in layers.most_common()] or ["- None"])
    lines.extend(["", "## Expansion Opportunities"])
    lines.extend([f"- `{key}`: {value} scheduled items" for key, value in families.most_common(12)] or ["- None"])
    lines.extend(["", "## Priority-State Coverage"])
    lines.extend([f"- `{key}`: {value}" for key, value in states.most_common()] or ["- None"])
    lines.extend(["", "## Top Blockers Expected"])
    lines.extend([f"- `{key}`: {value}" for key, value in blockers.most_common()] or ["- None"])
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"scheduled_items": len(rows), "layers": dict(layers), "safe_sources": len(sources), "out": str(out), "report": str(report)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", default="research_volume_expansion_001")
    parser.add_argument("--target-new-items", type=int, default=25000)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build(Path(args.db), args.run_id, args.target_new_items, Path(args.out), Path(args.report), bool(args.execute and not args.dry_run)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
