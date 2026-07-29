#!/usr/bin/env python3
"""Strict-clean stage-only public web gap candidates."""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search" / "abc_public_search_round011_abc_place_expanded_candidates.csv"
DEFAULT_OUTPUT = ROOT / "data" / "interim" / "gap_probe_1926_2011" / "abc_public_search" / "abc_public_search_round011_abc_place_expanded_strict_candidates.csv"
DEFAULT_REPORT = ROOT / "data" / "processed" / "v2" / "1926_2011_abc_public_search_round011_strict_cleaning.md"

NOISE_RE = re.compile(
    r"\b("
    r"halloween costume|decoration ideas|last-minute australian celebration|"
    r"artist creates monsters|doll parts|self-acceptance after disfiguring|"
    r"sea level rise|climate change damage|displaying evidence of damage|"
    r"rugby league|koori knockout|grand final|newcastle yowies|"
    r"ghost writer|ghostwriter|ghost net|ghost gum|ghost shark|ghost bat|"
    r"book show|jeanette winterson|karaoke|new single|"
    r"wild man of australian sport|wild man of australian jazz|wild man of australian design"
    r")\b",
    re.I,
)

WEAK_GHOSTLY_RE = re.compile(r"\bghostly\b", re.I)
GHOSTLY_PERSON_FORM_RE = re.compile(
    r"\b(ghostly (?:figure|woman|man|lady|apparition|presence)|ghost stories?|ghost tours?|"
    r"haunted|apparitions?|phantoms?|spectres?|resident ghost|blue lady|white lady)\b",
    re.I,
)

WEAK_SPOOK_RE = re.compile(r"\bspook(?:y|ed)?\b", re.I)
SPOOK_PERSON_FORM_RE = re.compile(r"\b(ghost|haunted|apparition|figure|person|man|woman|lady|spirit)\b", re.I)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def downgrade(row: dict[str, str], status: str, reason: str) -> None:
    row["candidate_status"] = status
    row["acceptance_decision"] = "not_accepted"
    existing = clean(row.get("rejection_reason"))
    row["rejection_reason"] = f"{existing};{reason}".strip(";") if existing else reason


def strict_clean(row: dict[str, str]) -> dict[str, str]:
    if row.get("candidate_status") != "accepted":
        return row
    text = " ".join(
        clean(row.get(key))
        for key in ("title", "evidence_summary", "matched_terms", "source_label", "query_string", "url")
    )
    label = clean(row.get("source_label")).lower()
    if NOISE_RE.search(text):
        downgrade(row, "rejected", "strict_noise_pattern")
        return row
    if WEAK_GHOSTLY_RE.search(label) and not GHOSTLY_PERSON_FORM_RE.search(text):
        downgrade(row, "lead_only", "weak_ghostly_adjective_without_person_form")
        return row
    if WEAK_SPOOK_RE.search(label) and not SPOOK_PERSON_FORM_RE.search(text):
        downgrade(row, "lead_only", "weak_spook_context_without_person_form")
        return row
    if not row.get("location_text") and label in {"ghost", "ghosts"} and not re.search(
        r"\b(indigenous ghost stories|australian ghost stories|great australian ghost stories|"
        r"australia'?s most haunted|the darkside|haunted places in australia)\b",
        text,
        re.I,
    ):
        downgrade(row, "lead_only", "unmapped_generic_ghost_context")
        return row
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        rows = [strict_clean(dict(row)) for row in reader]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    status_counts = Counter(row.get("candidate_status") for row in rows)
    accepted = [row for row in rows if row.get("candidate_status") == "accepted"]
    mapped = [row for row in accepted if row.get("latitude") and row.get("longitude")]
    scope_counts = Counter(row.get("date_scope") for row in accepted)
    query_counts = Counter(row.get("query_family_id") for row in accepted)
    try:
        input_label = str(args.input.resolve().relative_to(ROOT))
    except ValueError:
        input_label = str(args.input)
    try:
        output_label = str(args.output.resolve().relative_to(ROOT))
    except ValueError:
        output_label = str(args.output)
    lines = [
        "# 1926-2011 ABC Public Search Strict Cleaning",
        "",
        f"- Generated: `{utc_now_iso()}`",
        f"- Input: `{input_label}`",
        f"- Output: `{output_label}`",
        f"- Rows: `{len(rows)}`",
        f"- Strict accepted: `{len(accepted)}`",
        f"- Strict accepted with coordinates: `{len(mapped)}`",
        "",
        "## Status Counts",
    ]
    for key, count in status_counts.most_common():
        lines.append(f"- {key or 'blank'}: {count}")
    lines.extend(["", "## Accepted Date Scope"])
    for key, count in scope_counts.most_common():
        lines.append(f"- {key or 'blank'}: {count}")
    lines.extend(["", "## Accepted Query Families"])
    for key, count in query_counts.most_common():
        lines.append(f"- {key or 'blank'}: {count}")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote strict public web candidates: {args.output}")
    print(f"Strict accepted: {len(accepted)}")
    print(f"Strict mapped: {len(mapped)}")


if __name__ == "__main__":
    main()
