#!/usr/bin/env python3
"""Score source-chain quality for existing records and staged candidates."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import load_registry, now_iso, write_csv


DISCOVERY_ONLY_TOKENS = {
    "australian yowie research",
    "yowiehunters",
    "wikipedia",
    "openalex",
    "crossref",
    "worldcat",
    "open library",
    "paranormal",
    "haunted tour",
}

ACCESS_PLATFORM_TOKENS = {
    "internet archive",
    "archive.org",
    "project gutenberg",
    "gutenberg.net.au",
    "wikisource",
    "pandora",
}

FIELDS = [
    "record_id",
    "narrative_unit_id",
    "candidate_id",
    "existing_source_name",
    "existing_source_url",
    "inferred_discovery_source_name",
    "inferred_access_source_name",
    "inferred_original_source_name",
    "inferred_evidence_source_name",
    "inferred_evidence_source_tier",
    "source_chain_score",
    "machine_bucket",
    "hard_fail_reasons",
    "machine_recommendation",
    "machine_confidence",
    "reviewer_decision",
    "reviewer_notes",
]


def is_token_present(row: dict[str, Any], tokens: set[str]) -> bool:
    haystack = " ".join(str(row.get(key) or "") for key in row.keys()).lower()
    return any(token in haystack for token in tokens)


def score_source_chain(row: dict[str, Any]) -> dict[str, Any]:
    score = 0
    hard: list[str] = []
    tier = str(row.get("inferred_evidence_source_tier") or row.get("evidence_source_tier") or "").strip().upper()
    evidence_name = row.get("inferred_evidence_source_name") or row.get("reviewer_corrected_evidence_source_name")
    evidence_url = row.get("reviewer_corrected_evidence_source_url") or row.get("existing_source_url") or row.get("evidence_source_url")
    original = row.get("inferred_original_source_name") or row.get("reviewer_corrected_original_source_name")

    if evidence_name:
        score += 30
    else:
        hard.append("missing_evidence_source_name")
    if evidence_url:
        score += 20
    else:
        hard.append("missing_evidence_source_url")
    if tier in {"A", "B", "C"}:
        score += 20
    elif tier == "D":
        if original:
            score += 10
        else:
            score -= 30
            hard.append("tier_D_without_original_source")
    elif tier == "E" or is_token_present(row, DISCOVERY_ONLY_TOKENS):
        score -= 40
        hard.append("discovery_only_as_evidence")
    else:
        hard.append("unknown_source_tier")

    if original:
        score += 10
    if row.get("date_published") or row.get("accepted_publication_date"):
        score += 10
    if row.get("inferred_access_source_name"):
        score += 10
    if is_token_present(row, ACCESS_PLATFORM_TOKENS) and not original:
        if "tier_D_without_original_source" not in hard:
            hard.append("tier_D_without_original_source")
            score -= 15
    if is_token_present(row, DISCOVERY_ONLY_TOKENS):
        if "discovery_only_as_evidence" not in hard:
            hard.append("discovery_only_as_evidence")
            score -= 40
    if evidence_name and not evidence_url:
        score -= 20
    score = max(0, min(score, 100))

    if "discovery_only_as_evidence" in hard:
        bucket = "RED_DISCOVERY_ONLY_LEAKAGE"
        confidence = 0.95
    elif "tier_D_without_original_source" in hard:
        bucket = "AMBER_D_NEEDS_ORIGINAL"
        confidence = 0.85
    elif score >= 80 and tier in {"A", "B", "C"} and evidence_name and evidence_url:
        bucket = "GREEN_EVIDENCE_OK"
        confidence = 0.90
    elif tier == "D" and score >= 70 and original:
        bucket = "GREEN_D_DECOMPOSED"
        confidence = 0.80
    elif "missing_evidence_source_url" in hard:
        bucket = "AMBER_MISSING_EVIDENCE_URL"
        confidence = 0.75
    elif "unknown_source_tier" in hard:
        bucket = "AMBER_UNKNOWN_SOURCE"
        confidence = 0.70
    else:
        bucket = "HOLD"
        confidence = 0.50
    return {
        "source_chain_score": score,
        "hard_fail_reasons": ";".join(hard),
        "machine_bucket": bucket,
        "machine_recommendation": bucket,
        "machine_confidence": f"{confidence:.2f}",
    }


def read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    bucket_counts = Counter(row["machine_bucket"] for row in rows)
    access_counts = Counter(row.get("inferred_access_source_name") or "none" for row in rows)
    discovery_counts = Counter(row.get("inferred_discovery_source_name") or "none" for row in rows)
    tier_counts = Counter(row.get("inferred_evidence_source_tier") or "unknown" for row in rows)
    lines = [
        "# Source Chain Machine Score Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total rows: `{len(rows)}`",
        f"- Red discovery-only leakage: `{bucket_counts.get('RED_DISCOVERY_ONLY_LEAKAGE', 0)}`",
        f"- D platform missing original: `{bucket_counts.get('AMBER_D_NEEDS_ORIGINAL', 0)}`",
        "",
        "## Buckets",
    ]
    lines.extend([f"- `{key}`: {bucket_counts[key]}" for key in sorted(bucket_counts)] or ["- None"])
    lines.extend(["", "## Top Access Platforms"])
    lines.extend([f"- `{key}`: {count}" for key, count in access_counts.most_common(20)] or ["- None"])
    lines.extend(["", "## Top Discovery-Only Sources"])
    lines.extend([f"- `{key}`: {count}" for key, count in discovery_counts.most_common(20)] or ["- None"])
    lines.extend(["", "## Source Tier Distribution"])
    lines.extend([f"- `{key}`: {count}" for key, count in tier_counts.most_common()] or ["- None"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_file(db_path: Path, backfill_review: Path, registry_path: Path, out_path: Path, report_path: Path) -> list[dict[str, Any]]:
    load_registry(registry_path)
    rows = []
    for row in read_rows(backfill_review):
        scored = dict(row)
        scored.update(score_source_chain(row))
        rows.append(scored)
    write_csv(out_path, rows, FIELDS)
    write_report(report_path, rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--backfill-review", required=True, help="source chain backfill CSV")
    parser.add_argument("--registry", required=True, help="source registry YAML")
    parser.add_argument("--out", required=True, help="score CSV output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    args = parser.parse_args()
    rows = score_file(Path(args.db), Path(args.backfill_review), Path(args.registry), Path(args.out), Path(args.report))
    print(f"Scored {len(rows)} source-chain rows.")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
