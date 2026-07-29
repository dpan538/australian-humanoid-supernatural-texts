#!/usr/bin/env python3
"""Audit target-gap autoharvest milestone quality without applying promotion."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.autoharvest_gap import gap_count


def pct(part: int | float, whole: int | float) -> float:
    return round((float(part) / float(whole) * 100) if whole else 0.0, 2)


def run_audit(db_path: Path, run_id: str, target: int, out_dir: Path) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        target_count, target_weight = gap_count(conn, run_id)
        rows = [dict(row) for row in conn.execute("SELECT * FROM provisional_records WHERE run_id=? AND target_gap_eligible=1", (run_id,)).fetchall()]
        aux = conn.execute("SELECT COUNT(*) FROM provisional_records WHERE run_id=? AND COALESCE(target_gap_eligible,0)=0", (run_id,)).fetchone()[0]
        candidates = [dict(row) for row in conn.execute("SELECT * FROM harvest_candidates WHERE run_id=?", (run_id,)).fetchall()]
    tiers = Counter(row.get("source_tier") or "unknown" for row in rows)
    temporal = sum(1 for row in rows if row.get("temporal_evidence_type") and float(row.get("date_confidence") or 0) >= 0.7)
    missing_url = sum(1 for row in rows if not row.get("evidence_source_url"))
    avg_item = round(sum(float(row.get("item_level_confidence") or 0) for row in rows) / len(rows), 3) if rows else 0.0
    duplicate_rate = pct(sum(1 for row in candidates if row.get("duplicate_status") not in {"unique", "probably_unique", "unique_or_probably_unique", "unchecked", "", None}), len(candidates))
    noise_rate = pct(sum(1 for row in candidates if "noise" in str(row.get("gate_reasons_json") or "")), len(candidates))
    discovery = sum(1 for row in rows if row.get("evidence_or_discovery") == "discovery_only")
    sensitive = sum(1 for row in rows if row.get("ethics_status") in {"sensitive", "restricted", "manual_only"})
    quality_ok = (
        pct(tiers.get("A", 0) + tiers.get("B", 0) + tiers.get("C", 0), len(rows)) >= 90
        and discovery == 0
        and sensitive == 0
        and duplicate_rate <= 50
        and noise_rate <= 50
        and pct(missing_url, len(rows)) <= 5
        and pct(temporal, len(rows)) >= 95
        and avg_item >= 0.70
    ) if rows else False
    write_csv(
        out_dir / "target_gap_promotion_proposal.csv",
        rows,
        list(rows[0].keys()) if rows else ["provisional_record_id"],
    )
    aux_rows = [{"status": "auxiliary_records", "count": aux}, {"status": "target_gap_records", "count": target_count}]
    write_csv(out_dir / "gap_milestone_counts.csv", aux_rows, ["status", "count"])
    lines = [
        "# Gap Autoharvest Milestone Audit",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Target gap milestone: `{target}`",
        f"- Target-gap records: `{target_count}`",
        f"- Target-gap effective weight: `{round(target_weight, 2)}`",
        f"- Auxiliary records: `{aux}`",
        f"- Source tier A/B/C share: `{pct(tiers.get('A', 0) + tiers.get('B', 0) + tiers.get('C', 0), len(rows))}%`",
        f"- Discovery-only leakage: `{discovery}`",
        f"- Sensitive leakage: `{sensitive}`",
        f"- Duplicate rate: `{duplicate_rate}%`",
        f"- Noise rate: `{noise_rate}%`",
        f"- Missing evidence URL: `{pct(missing_url, len(rows))}%`",
        f"- Explicit temporal evidence coverage: `{pct(temporal, len(rows))}%`",
        f"- Item-level confidence average: `{avg_item}`",
        f"- Quality acceptable: `{str(quality_ok).lower()}`",
        "- Public records mutated: `no`",
        "- Promotion proposal applied: `no`",
    ]
    (out_dir / "milestone_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"target_count": target_count, "target_weight": target_weight, "quality_ok": quality_ok, "out": str(out_dir / "milestone_summary.md")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--target-gap-effective-records", type=int, default=2000)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    print(run_audit(Path(args.db), args.run_id, args.target_gap_effective_records, Path(args.out_dir)))


if __name__ == "__main__":
    main()
