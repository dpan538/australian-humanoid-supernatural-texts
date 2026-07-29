#!/usr/bin/env python3
"""Mine no-key access platforms for gap discovery and decomposed source candidates."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

from collection_expansion_common import write_csv
from lib.gap_recovery import TARGET_TERMS, read_yaml_rows, write_report

FIELDS = [
    "candidate_id",
    "run_id",
    "access_platform",
    "title",
    "creator",
    "date_text",
    "url",
    "snippet",
    "current_status",
    "source_chain_status",
    "rights_status",
    "target_signal",
    "next_action",
]


def ia_queries() -> list[str]:
    return [
        '("Western Australia" OR Tasmania OR "Northern Territory" OR "South Australia") AND (ghost OR haunted OR yowie OR bunyip) AND mediatype:texts',
        '("local history" OR newsletter OR journal OR bulletin) AND (ghost OR haunted OR yowie OR bunyip) AND mediatype:texts',
    ]


def internet_archive_metadata(limit: int = 50) -> list[dict]:
    rows: list[dict] = []
    session = requests.Session()
    for query in ia_queries():
        params = {
            "q": query,
            "fl[]": ["identifier", "title", "creator", "date", "description", "rights"],
            "rows": str(limit // len(ia_queries()) or 10),
            "output": "json",
        }
        try:
            response = session.get("https://archive.org/advancedsearch.php", params=params, headers={"User-Agent": "AusFiguresNoAuthResearchBot/0.1 metadata-first no-login no-api"}, timeout=(5, 12))
            docs = response.json().get("response", {}).get("docs", []) if response.status_code == 200 else []
        except Exception:
            docs = []
        for doc in docs:
            identifier = doc.get("identifier") or ""
            if not identifier:
                continue
            text = " ".join(str(doc.get(k) or "") for k in ["title", "creator", "date", "description"])
            rows.append(
                {
                    "candidate_id": f"ia_{identifier}",
                    "access_platform": "Internet Archive",
                    "title": doc.get("title") or identifier,
                    "creator": doc.get("creator") or "",
                    "date_text": doc.get("date") or "",
                    "url": f"https://archive.org/details/{identifier}",
                    "snippet": re.sub(r"\s+", " ", text)[:800],
                    "rights_status": doc.get("rights") or "unknown",
                }
            )
    return rows[:limit]


def classify_access(row: dict, run_id: str) -> dict:
    hay = " ".join(str(row.get(k) or "") for k in ["title", "snippet", "date_text"]).lower()
    term_hit = any(term.replace("-", " ") in hay or term in hay for term in TARGET_TERMS[:12])
    year_hit = bool(re.search(r"\b(19[2-7]\d|1930s|1940s|1950s|1960s|1970s)\b", hay))
    rights = str(row.get("rights_status") or "").lower()
    publicish = any(token in rights for token in ["public", "pd", "not in copyright", "creative commons", "cc0"])
    status = "ORIGINAL_SOURCE_DECOMPOSED_CANDIDATE" if term_hit and year_hit and publicish else "TARGET_GAP_ACCESS_CANDIDATE" if term_hit or year_hit else "DISCOVERY_ONLY_NEEDS_EVIDENCE"
    return {
        **row,
        "run_id": run_id,
        "current_status": status,
        "source_chain_status": "requires_original_source_decomposition",
        "target_signal": ";".join([x for x, ok in [("term", term_hit), ("date", year_hit), ("public_rights", publicish)] if ok]),
        "next_action": "decompose_original_source_before_evidence_use",
    }


def mine(db_path: Path, registry: Path, run_id: str, out_dir: Path, execute: bool) -> dict[str, int]:
    del db_path
    registry_rows = read_yaml_rows(registry)
    rows = internet_archive_metadata(50) if execute else []
    classified = [classify_access(row, run_id) for row in rows]
    decomposed = [row for row in classified if row["current_status"] == "ORIGINAL_SOURCE_DECOMPOSED_CANDIDATE"]
    public_domain = [row for row in classified if "public_rights" in row["target_signal"]]
    holds = [row for row in classified if row["current_status"] == "DISCOVERY_ONLY_NEEDS_EVIDENCE"]
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "access_platform_candidates.csv", classified, FIELDS)
    write_csv(out_dir / "decomposed_original_source_candidates.csv", decomposed, FIELDS)
    write_csv(out_dir / "discovery_only_holds.csv", holds, FIELDS)
    write_csv(out_dir / "public_domain_snippet_candidates.csv", public_domain, FIELDS)
    write_report(
        out_dir / "access_platform_gap_mining_report.md",
        "Access Platform Gap Mining Report",
        {
            "Run ID": run_id,
            "Execute": str(execute).lower(),
            "Registry rows available": len(registry_rows),
            "Access platform candidates": len(classified),
            "Decomposed original-source candidates": len(decomposed),
            "Discovery-only holds": len(holds),
            "Access platform is evidence by default": "no",
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
    )
    return {"candidates": len(classified), "decomposed": len(decomposed), "holds": len(holds), "public_domain": len(public_domain)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(mine(Path(args.db), Path(args.registry), args.run_id, Path(args.out_dir), execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
