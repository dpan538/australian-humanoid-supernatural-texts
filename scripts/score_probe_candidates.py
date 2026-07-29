#!/usr/bin/env python3
"""Score staged probe candidates for review priority and route-yield signal."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, table_exists, write_csv


PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
HIGH_VALUE_TERMS = {"yowie", "hairy man", "wild man", "bunyip", "apparition", "ghost", "spirit", "monster"}
NOISE_TERMS = {
    "advertisement",
    "classified",
    "shipping",
    "horse race",
    "football",
    "theatre",
    "recipe",
    "weather",
    "stock sale",
}
DISCOVERY_ONLY = {"discovery_only", "manual_only_sensitive"}

FIELDS = [
    "candidate_id",
    "run_id",
    "route_id",
    "source_id",
    "source_name",
    "source_tier",
    "evidence_or_discovery",
    "target_state",
    "time_band",
    "term_family",
    "title",
    "date_published",
    "publication",
    "url",
    "query_string",
    "snippet",
    "duplicate_key",
    "duplicate_status",
    "candidate_score",
    "machine_bucket",
    "hard_fail_reasons",
    "machine_recommendation",
    "machine_confidence",
    "reviewer_decision",
    "reviewer_notes",
]


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def rows_from_db(db_path: Path, run_id: str | None, limit: int | None) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if not table_exists(conn, "collection_candidates"):
            return []
        params: list[Any] = []
        where = ""
        if run_id:
            where = "WHERE run_id = ?"
            params.append(run_id)
        suffix = "ORDER BY run_id, target_state, time_band, source_name, title"
        if limit:
            suffix += " LIMIT ?"
            params.append(limit)
        rows = conn.execute(f"SELECT * FROM collection_candidates {where} {suffix}", params).fetchall()
        return [dict(row) for row in rows]


def contains_any(text: str, tokens: set[str]) -> bool:
    haystack = text.lower()
    return any(token in haystack for token in tokens)


def time_band_in_scope(value: Any) -> bool:
    raw = str(value or "")
    if raw in {"1926_1939", "1940_1954", "1955_1964", "1965_1976"}:
        return True
    digits = "".join(ch if ch.isdigit() else " " for ch in raw).split()
    years = [int(part) for part in digits if len(part) == 4]
    return any(1926 <= year <= 1976 for year in years)


def score_candidate(row: dict[str, Any], seen_duplicates: set[str] | None = None) -> dict[str, Any]:
    score = 0
    hard: list[str] = []
    text = " ".join(str(row.get(key) or "") for key in ["title", "snippet", "query_string", "term_family"])
    tier = str(row.get("source_tier") or "").upper()
    mode = str(row.get("evidence_or_discovery") or "").lower()
    duplicate_key = str(row.get("duplicate_key") or "")

    if tier in {"A", "B", "C"}:
        score += 25
    elif tier == "D":
        score += 10
    elif tier == "E":
        score -= 30
        hard.append("tier_E_discovery_only")

    if time_band_in_scope(row.get("time_band") or row.get("date_published")):
        score += 20
    else:
        score -= 15
        hard.append("outside_target_period_or_missing_time_band")

    if str(row.get("target_state") or "").upper() in PRIORITY_STATES:
        score += 20
    if contains_any(text, HIGH_VALUE_TERMS):
        score += 15
    if row.get("target_locality") and str(row.get("target_locality")).lower() in text.lower():
        score += 10
    elif row.get("source_stated_place_text"):
        score += 10

    if row.get("url"):
        score += 10
    else:
        score -= 15
        hard.append("missing_url")
    if row.get("publication") or row.get("source_name"):
        score += 10
    else:
        score -= 15
        hard.append("missing_source")
    if row.get("date_published") or row.get("inferred_year"):
        score += 10
    else:
        score -= 15
        hard.append("missing_date")

    if mode in DISCOVERY_ONLY:
        score -= 50
        hard.append(f"{mode}_not_auto_evidence")
    if contains_any(text, NOISE_TERMS):
        score -= 35
        hard.append("context_noise")
    if str(row.get("duplicate_status") or "").lower() in {"duplicate", "skipped_duplicate"}:
        score -= 40
        hard.append("duplicate_candidate")
    if seen_duplicates is not None and duplicate_key:
        if duplicate_key in seen_duplicates:
            score -= 40
            hard.append("duplicate_candidate")
        else:
            seen_duplicates.add(duplicate_key)

    score = max(0, min(score, 100))
    if "duplicate_candidate" in hard:
        bucket = "EXCLUDE_DUPLICATE"
        confidence = 0.95
    elif "context_noise" in hard and score < 50:
        bucket = "EXCLUDE_CONTEXT_NOISE"
        confidence = 0.85
    elif "missing_date" in hard:
        bucket = "AMBER_MISSING_DATE"
        confidence = 0.75
    elif "missing_source" in hard:
        bucket = "AMBER_MISSING_SOURCE"
        confidence = 0.75
    elif score >= 75:
        bucket = "PRIORITY_REVIEW"
        confidence = 0.85
    elif score >= 55:
        bucket = "ROUTE_YIELD_SIGNAL"
        confidence = 0.75
    else:
        bucket = "HOLD"
        confidence = 0.55

    return {
        "candidate_score": score,
        "machine_bucket": bucket,
        "hard_fail_reasons": ";".join(dict.fromkeys(hard)),
        "machine_recommendation": bucket,
        "machine_confidence": f"{confidence:.2f}",
    }


def score_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_duplicates: set[str] = set()
    scored: list[dict[str, Any]] = []
    for row in rows:
        output = dict(row)
        output.update(score_candidate(row, seen_duplicates))
        scored.append(output)
    return scored


def write_report(path: Path, rows: list[dict[str, Any]]) -> None:
    buckets = Counter(row.get("machine_bucket") or "unknown" for row in rows)
    by_source = Counter(row.get("source_name") or row.get("source_id") or "unknown" for row in rows)
    by_state_time = Counter((row.get("target_state") or "unknown", row.get("time_band") or "unknown") for row in rows)
    noise = Counter()
    for row in rows:
        for reason in str(row.get("hard_fail_reasons") or "").split(";"):
            if reason:
                noise[reason] += 1
    lines = [
        "# Probe Candidate Machine Score Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Total candidates scored: `{len(rows)}`",
        f"- Priority review: `{buckets.get('PRIORITY_REVIEW', 0)}`",
        f"- Route yield signal: `{buckets.get('ROUTE_YIELD_SIGNAL', 0)}`",
        "",
        "## Buckets",
    ]
    lines.extend([f"- `{key}`: {buckets[key]}" for key in sorted(buckets)] or ["- None"])
    lines.extend(["", "## Route Yield By Source"])
    lines.extend([f"- `{key}`: {count}" for key, count in by_source.most_common(25)] or ["- None"])
    lines.extend(["", "## State And Time Band"])
    lines.extend([f"- `{state}` / `{time_band}`: {count}" for (state, time_band), count in by_state_time.most_common(40)] or ["- None"])
    lines.extend(["", "## Top Noise Or Review Reasons"])
    lines.extend([f"- `{key}`: {count}" for key, count in noise.most_common(25)] or ["- None"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def score_file(db_path: Path, candidates_path: Path | None, run_id: str | None, out_path: Path, report_path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    rows = read_csv_rows(candidates_path) if candidates_path else []
    if not rows:
        rows = rows_from_db(db_path, run_id, limit)
    if limit:
        rows = rows[:limit]
    scored = score_rows(rows)
    write_csv(out_path, scored, FIELDS)
    write_report(report_path, scored)
    return scored


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, help="SQLite database path")
    parser.add_argument("--candidates", help="optional candidate CSV")
    parser.add_argument("--run-id", help="optional run id for DB candidates")
    parser.add_argument("--out", required=True, help="score CSV output")
    parser.add_argument("--report", required=True, help="Markdown report output")
    parser.add_argument("--limit", type=int, help="maximum rows to score")
    args = parser.parse_args()
    rows = score_file(
        Path(args.db),
        Path(args.candidates) if args.candidates else None,
        args.run_id,
        Path(args.out),
        Path(args.report),
        args.limit,
    )
    print(f"Scored {len(rows)} probe candidates.")
    print(f"Wrote report: {args.report}")


if __name__ == "__main__":
    main()
