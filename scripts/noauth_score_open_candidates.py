#!/usr/bin/env python3
"""Score metadata-only candidates from a no-auth open-records probe."""

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


PRIORITY_STATES = {"WA", "SA", "NT", "TAS", "ACT"}
OFFICIAL_FAMILIES = {
    "state_library_catalogue",
    "state_archive_catalogue",
    "local_history_serial",
    "council_local_studies",
    "museum_heritage_page",
    "heritage_register",
    "broadcast_catalogue",
}
TOURISM_TERMS = {"tour", "tickets", "event", "booking", "visit us", "ghost tour", "festival"}
NOISE_TERMS = {"fiction", "poem", "poetry", "theatre", "advertisement", "book review", "schedule", "program"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def has_year(row: dict[str, Any]) -> bool:
    value = str(row.get("inferred_year") or row.get("date_published") or "")
    return any(token.isdigit() and len(token) == 4 for token in value.replace("-", " ").split())


def text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in ["title", "snippet", "url", "query_string"]).lower()


def score_row(row: dict[str, Any]) -> tuple[int, str, list[str]]:
    score = 0
    reasons: list[str] = []
    haystack = text(row)
    if row.get("source_tier") in {"A", "B", "C"}:
        score += 25
        reasons.append("tier_ABC")
    if row.get("target_state") in PRIORITY_STATES:
        score += 25
        reasons.append("priority_state")
    if row.get("time_band") in {"1926_1939", "1940_1954", "1955_1964", "1965_1976"} or has_year(row):
        score += 20
        reasons.append("gap_year_or_band")
    if row.get("route_family") in OFFICIAL_FAMILIES or row.get("route_id"):
        score += 15
        reasons.append("official_local_route")
    term = str(row.get("term_family") or row.get("query_string") or "").lower()
    if term and any(part for part in term.split("_") if part in haystack):
        score += 15
        reasons.append("term_signal")
    locality = str(row.get("target_locality") or "").lower()
    if locality and locality in haystack:
        score += 10
        reasons.append("locality_signal")
    if ".gov.au" in haystack or ".edu.au" in haystack or "museum" in haystack or "library" in haystack:
        score += 10
        reasons.append("official_domain_signal")
    if has_year(row):
        score += 10
        reasons.append("date_present")
    if row.get("source_stated_place_text"):
        score += 10
        reasons.append("place_hint_present")
    if any(term in haystack for term in TOURISM_TERMS):
        score -= 40
        reasons.append("tourism_marketing")
    if any(term in haystack for term in NOISE_TERMS):
        score -= 40
        reasons.append("context_noise")
    if row.get("evidence_or_discovery") == "discovery_only":
        score -= 30
        reasons.append("discovery_only")
    if not has_year(row):
        score -= 20
        reasons.append("missing_date")
    if not row.get("source_stated_place_text") and not row.get("target_locality"):
        score -= 20
        reasons.append("missing_locality")
    if row.get("duplicate_status") and row.get("duplicate_status") != "unchecked":
        score -= 20
        reasons.append("duplicate")

    if "duplicate" in reasons:
        bucket = "EXCLUDE_DUPLICATE"
    elif "tourism_marketing" in reasons:
        bucket = "EXCLUDE_TOURISM_MARKETING"
    elif "context_noise" in reasons:
        bucket = "EXCLUDE_CONTEXT_NOISE"
    elif "missing_date" in reasons:
        bucket = "AMBER_NEEDS_DATE"
    elif "missing_locality" in reasons:
        bucket = "AMBER_NEEDS_PLACE"
    elif score >= 80:
        bucket = "PRIORITY_REVIEW_OPEN_RECORD"
    elif score >= 55:
        bucket = "PROMISING_SOURCE_ROUTE"
    else:
        bucket = "HOLD"
    return score, bucket, reasons


def score_file(candidate_csv: Path, out_path: Path, report_path: Path, run_id: str = "") -> dict[str, Any]:
    rows = read_csv(candidate_csv)
    scored: list[dict[str, Any]] = []
    for row in rows:
        score, bucket, reasons = score_row(row)
        scored.append({**row, "machine_score": score, "machine_bucket": bucket, "machine_reasons": ";".join(reasons)})
    fieldnames = list(scored[0].keys()) if scored else ["candidate_id", "run_id", "machine_score", "machine_bucket", "machine_reasons"]
    write_csv(out_path, scored, fieldnames)
    buckets = Counter(row["machine_bucket"] for row in scored)
    states = Counter(row.get("target_state") or "" for row in scored)
    bands = Counter(row.get("time_band") or "" for row in scored)
    routes = Counter(row.get("route_id") or row.get("source_id") or "" for row in scored)
    top = sorted(scored, key=lambda row: -int(row["machine_score"]))[:20]
    lines = [
        "# No-Auth Candidate Score Report",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Candidate rows scored: `{len(scored)}`",
        f"- Priority candidates: `{buckets.get('PRIORITY_REVIEW_OPEN_RECORD', 0)}`",
        f"- Noise candidates: `{buckets.get('EXCLUDE_CONTEXT_NOISE', 0) + buckets.get('EXCLUDE_TOURISM_MARKETING', 0)}`",
        f"- Duplicate candidates: `{buckets.get('EXCLUDE_DUPLICATE', 0)}`",
        "",
        "## Buckets",
    ]
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(buckets.items())] or ["- None"])
    lines.extend(["", "## Candidates By State"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(states.items())] or ["- None"])
    lines.extend(["", "## Candidates By Time Band"])
    lines.extend([f"- `{key}`: {count}" for key, count in sorted(bands.items())] or ["- None"])
    lines.extend(["", "## Candidates By Route"])
    lines.extend([f"- `{key}`: {count}" for key, count in routes.most_common(20)] or ["- None"])
    lines.extend(["", "## Top 20 Candidates"])
    for row in top:
        lines.append(f"- `{row.get('machine_score')}` `{row.get('machine_bucket')}` {row.get('title')} | {row.get('url')}")
    lines.extend(["", "## Recommended Next Route Expansion", "- Expand routes with high priority-review rate and low context noise."])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"rows": len(scored), "buckets": dict(buckets), "report": report_path}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--candidate-csv", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    del args.db
    summary = score_file(Path(args.candidate_csv), Path(args.out), Path(args.report), args.run_id)
    print(f"Scored no-auth candidates: {summary['rows']}")
    print(f"Wrote report: {summary['report']}")


if __name__ == "__main__":
    main()
