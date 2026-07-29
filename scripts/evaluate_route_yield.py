#!/usr/bin/env python3
"""Evaluate small-batch route yield from machine-scored candidates."""

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
    "route_key",
    "source_id",
    "source_name",
    "target_state",
    "time_band",
    "candidate_count",
    "priority_review_count",
    "route_yield_signal_count",
    "duplicate_count",
    "noise_count",
    "missing_date_count",
    "missing_source_count",
    "poor_source_chain_count",
    "priority_review_rate",
    "duplicate_rate",
    "noise_rate",
    "missing_metadata_rate",
    "recommended_action",
    "recommended_next_batch_size",
    "rationale",
]


def read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def group_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_id") or row.get("source_name") or "unknown"),
        str(row.get("source_name") or row.get("source_id") or "unknown"),
        str(row.get("target_state") or "unknown"),
        str(row.get("time_band") or "unknown"),
    )


def source_chain_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        candidate_id = str(row.get("candidate_id") or "")
        if candidate_id:
            lookup[candidate_id] = row
    return lookup


def recommended_action(metrics: dict[str, Any]) -> tuple[str, int, str]:
    total = int(metrics["candidate_count"])
    priority = int(metrics["priority_review_count"])
    noise_rate = float(metrics["noise_rate"])
    duplicate_rate = float(metrics["duplicate_rate"])
    missing_rate = float(metrics["missing_metadata_rate"])
    poor_chains = int(metrics["poor_source_chain_count"])

    if noise_rate > 60:
        return "PAUSE_NOISE", 0, "Context-noise rate is above 60 percent."
    if duplicate_rate > 50:
        return "PAUSE_DUPLICATES", 0, "Duplicate rate is above 50 percent."
    if missing_rate > 50:
        return "NEEDS_QUERY_REWRITE", 50, "Missing date/source/location metadata is too high."
    if poor_chains >= max(3, total // 3):
        return "NEEDS_SOURCE_CHAIN_REPAIR", 50, "Too many candidates have weak evidence-source chains."
    if priority < 3 and total >= 20:
        return "PAUSE_LOW_YIELD", 0, "Fewer than three candidates reached priority review."
    if total and priority / total >= 0.10 and noise_rate <= 40 and duplicate_rate <= 30:
        return "CONTINUE_SMALL_BATCH", min(300, max(50, total * 2)), "Priority yield is healthy for a small controlled batch."
    return "HOLD", 50, "Not enough signal for expansion or pause."


def evaluate(candidate_scores: list[dict[str, Any]], source_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chain_by_candidate = source_chain_lookup(source_scores)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_scores:
        grouped[group_key(row)].append(row)

    outputs: list[dict[str, Any]] = []
    for key in sorted(grouped):
        source_id, source_name, state, time_band = key
        rows = grouped[key]
        total = len(rows)
        buckets = Counter(row.get("machine_bucket") or "unknown" for row in rows)
        noise_count = buckets.get("EXCLUDE_CONTEXT_NOISE", 0)
        dup_count = buckets.get("EXCLUDE_DUPLICATE", 0)
        missing_date = buckets.get("AMBER_MISSING_DATE", 0)
        missing_source = buckets.get("AMBER_MISSING_SOURCE", 0)
        poor_chains = 0
        for row in rows:
            chain = chain_by_candidate.get(str(row.get("candidate_id") or ""))
            if chain and str(chain.get("machine_bucket") or "").startswith(("RED_", "AMBER_")):
                poor_chains += 1
        metrics = {
            "route_key": "|".join(key),
            "source_id": source_id,
            "source_name": source_name,
            "target_state": state,
            "time_band": time_band,
            "candidate_count": total,
            "priority_review_count": buckets.get("PRIORITY_REVIEW", 0),
            "route_yield_signal_count": buckets.get("ROUTE_YIELD_SIGNAL", 0),
            "duplicate_count": dup_count,
            "noise_count": noise_count,
            "missing_date_count": missing_date,
            "missing_source_count": missing_source,
            "poor_source_chain_count": poor_chains,
            "priority_review_rate": pct(buckets.get("PRIORITY_REVIEW", 0), total),
            "duplicate_rate": pct(dup_count, total),
            "noise_rate": pct(noise_count, total),
            "missing_metadata_rate": pct(missing_date + missing_source, total),
        }
        action, next_size, rationale = recommended_action(metrics)
        metrics.update(
            {
                "recommended_action": action,
                "recommended_next_batch_size": next_size,
                "rationale": rationale,
            }
        )
        outputs.append(metrics)
    return outputs


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    actions = Counter(row.get("recommended_action") or "unknown" for row in rows)
    lines = [
        "# Route Yield Evaluation",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Routes evaluated: `{len(rows)}`",
        "",
        "## Recommended Actions",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in actions.most_common()] or ["- None"])
    lines.extend(["", "## Next Recommended Batch Composition"])
    for row in rows:
        if row.get("recommended_action") == "CONTINUE_SMALL_BATCH":
            lines.append(
                f"- `{row.get('source_name')}` / `{row.get('target_state')}` / `{row.get('time_band')}`: "
                f"{row.get('recommended_next_batch_size')} rows"
            )
    if lines[-1] == "## Next Recommended Batch Composition":
        lines.append("- No routes currently qualify for expansion.")
    lines.extend(["", "## Route Details"])
    for row in rows:
        lines.append(
            f"- `{row.get('route_key')}`: {row.get('recommended_action')} "
            f"(priority {row.get('priority_review_rate')}%, duplicate {row.get('duplicate_rate')}%, noise {row.get('noise_rate')}%)"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def evaluate_files(candidate_scores: Path, source_scores: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    rows = evaluate(read_rows(candidate_scores), read_rows(source_scores))
    write_csv(out_path, rows, FIELDS)
    write_report(report_path, rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-scores", required=True, help="probe candidate score CSV")
    parser.add_argument("--source-chain-scores", required=True, help="source-chain score CSV")
    parser.add_argument("--out", required=True, help="route-yield CSV output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    args = parser.parse_args()
    rows = evaluate_files(Path(args.candidate_scores), Path(args.source_chain_scores), Path(args.out), Path(args.report))
    print(f"Evaluated {len(rows)} route groups.")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
