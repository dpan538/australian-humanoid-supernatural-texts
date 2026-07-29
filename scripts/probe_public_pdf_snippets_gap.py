#!/usr/bin/env python3
"""Probe public PDFs in snippet-only gap mode."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, stable_candidate_id
from lib.autoharvest_engine import check_duplicate_against_existing, insert_harvest_candidate, insert_provisional_record, is_api_url, load_autoharvest_config, make_duplicate_key
from lib.autoharvest_gap import classify_gap_candidate, insert_temporal_evidence, provisional_id_for_candidate, update_candidate_gap_fields, update_provisional_gap_fields
from lib.noauth_web import allowed_by_robots
from migrate_autoharvest_gap_v2 import migrate


def extract_snippets(text: str, terms: list[str], radius: int = 300) -> list[str]:
    snippets: list[str] = []
    lower = (text or "").lower()
    for term in terms:
        idx = lower.find(term.lower())
        if idx < 0:
            continue
        start = max(0, idx - radius)
        end = min(len(text), idx + len(term) + radius)
        snippet = re.sub(r"\s+", " ", text[start:end]).strip()
        if snippet:
            snippets.append(snippet[:650])
    return snippets[:5]


def extract_issue_date_text(*parts: str) -> str:
    text = " ".join(str(part or "") for part in parts)
    match = re.search(r"\b(19[2-7]\d|1930s|1940s|1950s|1960s|1970s)\b", text, re.IGNORECASE)
    return match.group(0) if match else ""


def decode_pdf_text_snippet(data: bytes) -> str:
    # Snippet lane deliberately avoids durable full-text storage and OCR.
    text = data.decode("latin-1", errors="ignore")
    text = re.sub(r"\s+", " ", text)
    return text[:200000]


def safe_pdf_url(url: str, config: dict, source_tier: str = "A") -> tuple[bool, str]:
    if not url.lower().split("?", 1)[0].endswith(".pdf"):
        return False, "not_pdf"
    if is_api_url(url):
        return False, "api_url_rejected"
    if source_tier not in {"A", "B", "C"}:
        return False, "source_tier_not_abc"
    if not allowed_by_robots(url, config.get("safety", {}).get("user_agent", "")):
        return False, "robots_disallowed_or_unknown"
    return True, "ok"


def probe(db_path: Path, config_path: Path, run_id: str, limit: int, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = load_autoharvest_config(config_path)
    terms = config.data.get("term_gate", {}).get("controlled_terms") or ["ghost", "haunted", "yowie", "bunyip"]
    max_bytes = int(config.data.get("safety", {}).get("max_pdf_bytes_for_snippet_mode", 15000000))
    staged = skipped = fetched = 0
    report_rows: list[str] = []
    session = requests.Session()
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM harvest_frontier
            WHERE run_id=? AND status='queued' AND lower(url) LIKE '%.pdf%'
            ORDER BY priority_score DESC
            LIMIT ?
            """,
            (run_id, limit),
        ).fetchall()
        for row in rows:
            frontier = dict(row)
            ok, reason = safe_pdf_url(frontier["url"], config.data, frontier.get("source_tier") or "A")
            if not ok or not execute:
                skipped += 1
                report_rows.append(f"- `{frontier['url']}` skipped: `{reason if not ok else 'dry_run'}`")
                continue
            head = session.head(frontier["url"], headers={"User-Agent": config.user_agent}, timeout=20, allow_redirects=True)
            size = int(head.headers.get("content-length") or 0)
            if size and size > max_bytes:
                skipped += 1
                report_rows.append(f"- `{frontier['url']}` skipped: `oversized_pdf`")
                continue
            response = session.get(frontier["url"], headers={"User-Agent": config.user_agent, "Accept": "application/pdf"}, timeout=30)
            if response.status_code != 200 or len(response.content) > max_bytes:
                skipped += 1
                report_rows.append(f"- `{frontier['url']}` skipped: `fetch_failed_or_oversized`")
                continue
            fetched += 1
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp:
                temp.write(response.content)
                temp.flush()
                text = decode_pdf_text_snippet(response.content)
            snippets = extract_snippets(text, terms)
            if not snippets:
                skipped += 1
                report_rows.append(f"- `{frontier['url']}` skipped: `no_controlled_term_snippet`")
                continue
            title = frontier.get("source_name") or Path(urlparse(frontier["url"]).path).name
            candidate = {
                "candidate_id": stable_candidate_id(frontier.get("route_id"), frontier["url"], frontier["url"], title, "", snippets[0]),
                "run_id": run_id,
                "page_id": "",
                "route_id": frontier.get("route_id"),
                "source_id": frontier.get("source_id"),
                "source_name": frontier.get("source_name"),
                "source_tier": frontier.get("source_tier"),
                "route_family": frontier.get("route_family"),
                "target_state": frontier.get("state"),
                "target_locality": "",
                "time_band": "",
                "term_family": "pdf_snippet",
                "term": "",
                "title": title,
                "snippet": snippets[0],
                "url": frontier["url"],
                "stable_id": frontier["url"],
                "date_published": extract_issue_date_text(title, frontier["url"], snippets[0]),
                "inferred_year": None,
                "source_stated_place_text": "",
                "locality_hint": "",
                "mappability_hint": "low",
                "evidence_source_name": frontier.get("source_name"),
                "evidence_source_url": frontier["url"],
                "access_source_name": frontier.get("source_name"),
                "access_source_url": frontier["url"],
                "original_source_name": "",
                "rights_status": "metadata_only",
                "ethics_status": "not_sensitive",
                "metadata_only": 1,
                "candidate_score": 80,
                "duplicate_key": "",
                "duplicate_status": "unchecked",
                "noise_flags_json": "[]",
                "gate_status": "candidate",
                "gate_reasons_json": "[]",
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "evidence_or_discovery": "evidence_possible",
            }
            candidate["duplicate_key"] = make_duplicate_key(candidate)
            candidate["duplicate_status"] = check_duplicate_against_existing(conn, candidate)
            decision = classify_gap_candidate(candidate, dict(frontier), config.data, page_text=snippets[0], metadata={"url": frontier["url"], "title": title})
            candidate["gate_status"] = "provisional_accepted" if decision.target_gap_eligible else "candidate_hold"
            candidate["gate_reasons_json"] = json.dumps(decision.reasons)
            insert_harvest_candidate(conn, candidate)
            update_candidate_gap_fields(conn, candidate["candidate_id"], decision)
            if decision.target_gap_eligible and insert_provisional_record(conn, candidate, 90):
                update_provisional_gap_fields(conn, candidate["candidate_id"], decision)
                insert_temporal_evidence(conn, run_id, candidate["candidate_id"], provisional_id_for_candidate(candidate), decision, frontier["url"])
                staged += 1
        conn.commit()
    out_dir = Path(config.data.get("outputs", {}).get("reports_dir", "data/processed/v2/autoharvest"))
    out = out_dir / f"{run_id}_pdf_snippet_report.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(
            [
                "# Gap PDF Snippet Probe",
                "",
                f"- Generated: `{now_iso()}`",
                f"- Run ID: `{run_id}`",
                f"- Execute: `{str(execute).lower()}`",
                f"- PDFs fetched: `{fetched}`",
                f"- Target candidates staged: `{staged}`",
                f"- Skipped: `{skipped}`",
                "- PDF bodies stored: `no`",
                "- Full extracted text stored: `no`",
                "",
                "## Details",
                *report_rows[:50],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return {"fetched": fetched, "staged": staged, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = probe(Path(args.db), Path(args.config), args.run_id, args.limit, execute=bool(args.execute and not args.dry_run))
    print(summary)


if __name__ == "__main__":
    main()
