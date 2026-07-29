#!/usr/bin/env python3
"""Generate post-release display cards from accepted data and release-layer sidecars."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso, write_csv
from lib.post_release_site import (  # noqa: E402
    canonical_url_from_redirects,
    read_csv_rows,
    read_json,
    read_url_redirect_map,
    table_exists,
    table_rows,
    write_json,
    write_markdown,
    year_or_range,
)


CARD_FIELDS = [
    "id",
    "canonical_id",
    "card_type",
    "title",
    "subtitle",
    "source_name",
    "source_family",
    "layer_type",
    "display_label",
    "year_or_range",
    "state_or_region",
    "url",
    "canonical_url",
    "redirect_target",
    "badge",
    "caveat",
    "public_record_status",
    "map_display_status",
]


def text(value: Any, fallback: str = "") -> str:
    value = "" if value is None else str(value)
    return value.strip() or fallback


def accepted_record_cards(frontend_data: Path, url_redirects: dict[str, str]) -> list[dict[str, str]]:
    data = read_json(frontend_data, {}) or {}
    cards: list[dict[str, str]] = []
    for row in data.get("records", [])[:]:
        rid = text(row.get("record_id"))
        url = text(row.get("url"))
        cards.append({
            "id": f"accepted_record_{rid}",
            "canonical_id": rid,
            "card_type": "accepted_record_card",
            "title": text(row.get("title"), f"Accepted public record {rid}"),
            "subtitle": text(row.get("publication") or row.get("canonical_figure") or row.get("source_type"), "Accepted public record"),
            "source_name": text(row.get("source_name")),
            "source_family": text(row.get("source_type")),
            "layer_type": "accepted_public_record",
            "display_label": "Accepted public record",
            "year_or_range": text(row.get("year"), "undated"),
            "state_or_region": text(row.get("state_territory") or row.get("location_summary")),
            "url": url,
            "canonical_url": canonical_url_from_redirects(url, url_redirects),
            "redirect_target": "",
            "badge": "Accepted record",
            "caveat": "Accepted public record; public source exists does not verify the supernatural claim.",
            "public_record_status": "accepted_public_record",
            "map_display_status": "accepted_public_map_point" if row.get("has_strict_map_point") else "not_public_map",
        })
    return cards


def release_layer_cards(db_path: Path, url_redirects: dict[str, str]) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    if not db_path.exists():
        return cards
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if table_exists(conn, "release_metadata_gap_items"):
            for row in table_rows(conn, "release_metadata_gap_items"):
                url = text(row.get("url"))
                cards.append({
                    "id": f"metadata_gap_{row.get('release_item_id')}",
                    "canonical_id": text(row.get("release_item_id")),
                    "card_type": "metadata_gap_card",
                    "title": text(row.get("title"), "Metadata-only gap item"),
                    "subtitle": text(row.get("evidence_gap"), "Metadata-only gap item"),
                    "source_name": text(row.get("source_name")),
                    "source_family": text(row.get("source_family") or row.get("route_family")),
                    "layer_type": "metadata_only_gap_item",
                    "display_label": "Metadata-only gap item",
                    "year_or_range": year_or_range(row),
                    "state_or_region": text(row.get("target_state") or row.get("target_locality")),
                    "url": url,
                    "canonical_url": canonical_url_from_redirects(url, url_redirects),
                    "redirect_target": "",
                    "badge": "Metadata-only",
                    "caveat": "Metadata-only item; not an accepted public record.",
                    "public_record_status": "not_public_record",
                    "map_display_status": text(row.get("map_display_status"), "not_public_map"),
                })
        if table_exists(conn, "release_lead_overlay_items"):
            for row in table_rows(conn, "release_lead_overlay_items"):
                url = text(row.get("url"))
                caveat = "Research lead; requires evidence review."
                if "d_class" in text(row.get("blocker") or row.get("evidence_gap")).lower():
                    caveat = "Access-platform lead; original source unresolved."
                cards.append({
                    "id": f"lead_overlay_{row.get('release_lead_id')}",
                    "canonical_id": text(row.get("release_lead_id")),
                    "card_type": "lead_overlay_card",
                    "title": text(row.get("title"), "Research lead"),
                    "subtitle": text(row.get("evidence_gap") or row.get("blocker"), "Research lead"),
                    "source_name": text(row.get("source_name")),
                    "source_family": text(row.get("source_family") or row.get("route_family")),
                    "layer_type": "research_lead",
                    "display_label": "Research lead",
                    "year_or_range": year_or_range(row),
                    "state_or_region": text(row.get("target_state") or row.get("target_locality")),
                    "url": url,
                    "canonical_url": canonical_url_from_redirects(url, url_redirects),
                    "redirect_target": "",
                    "badge": "Research lead",
                    "caveat": caveat,
                    "public_record_status": "not_public_record",
                    "map_display_status": text(row.get("map_display_status"), "not_public_map"),
                })
        if table_exists(conn, "release_source_intelligence_items"):
            for row in table_rows(conn, "release_source_intelligence_items"):
                cards.append({
                    "id": f"source_intelligence_{row.get('source_intel_id')}",
                    "canonical_id": text(row.get("source_intel_id")),
                    "card_type": "source_intelligence_card",
                    "title": text(row.get("source_name"), "Source intelligence item"),
                    "subtitle": text(row.get("opportunity_type") or row.get("blocker"), "Source intelligence"),
                    "source_name": text(row.get("source_name")),
                    "source_family": text(row.get("source_family") or row.get("route_family")),
                    "layer_type": "source_intelligence_item",
                    "display_label": "Source intelligence item",
                    "year_or_range": "route",
                    "state_or_region": text(row.get("state")),
                    "url": "",
                    "canonical_url": "",
                    "redirect_target": "",
                    "badge": "Source intelligence",
                    "caveat": "Source intelligence item; not an accepted public record.",
                    "public_record_status": "not_public_record",
                    "map_display_status": "not_public_map",
                })
    return cards


def redirect_cards(redirect_dir: Path) -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    for row in read_csv_rows(redirect_dir / "canonical_id_redirects.csv"):
        from_id = text(row.get("from_id"))
        to_id = text(row.get("to_id"))
        if not from_id or not to_id:
            continue
        cards.append({
            "id": f"redirect_notice_{text(row.get('redirect_id'), from_id)}",
            "canonical_id": to_id,
            "card_type": "redirect_notice_card",
            "title": f"Redirect {from_id}",
            "subtitle": text(row.get("reason"), "Canonical redirect"),
            "source_name": text(row.get("source_table")),
            "source_family": "redirect_registry",
            "layer_type": "redirect_notice",
            "display_label": "Redirected",
            "year_or_range": "n/a",
            "state_or_region": "",
            "url": "",
            "canonical_url": "",
            "redirect_target": to_id,
            "badge": "Redirected",
            "caveat": "Redirect notice; old IDs resolve to canonical IDs and do not change evidence status.",
            "public_record_status": "not_public_record",
            "map_display_status": "not_public_map",
        })
    return cards


def generate(db_path: Path, release_package: Path, redirect_dir: Path, out: Path, report: Path, execute: bool) -> dict[str, object]:
    frontend_data = ROOT / "public" / "data" / "frontend-data.json"
    url_redirects = read_url_redirect_map(redirect_dir)
    cards = [
        *accepted_record_cards(frontend_data, url_redirects),
        *release_layer_cards(db_path, url_redirects),
        *redirect_cards(redirect_dir),
    ]
    failures = []
    ids = [card["id"] for card in cards]
    if len(ids) != len(set(ids)):
        failures.append("duplicate card IDs")
    for card in cards:
        if card["card_type"] in {"metadata_gap_card", "lead_overlay_card"} and "not an accepted public record" not in card["caveat"] and "requires evidence review" not in card["caveat"]:
            failures.append(f"{card['id']} missing research-layer caveat")
        if card["card_type"] in {"metadata_gap_card", "lead_overlay_card"} and card["public_record_status"] != "not_public_record":
            failures.append(f"{card['id']} has incorrect public_record_status")
        if card["card_type"] == "redirect_notice_card" and not card["redirect_target"]:
            failures.append(f"{card['id']} unresolved redirect target")
    data = {"generated_at": now_iso(), "schema": "release-cards/v1", "cards": cards}
    if execute:
        write_json(out, data)
        write_csv(report.parent / "release_cards.csv", cards, CARD_FIELDS)
    counts: dict[str, int] = {}
    for card in cards:
        counts[card["card_type"]] = counts.get(card["card_type"], 0) + 1
    write_markdown(
        report,
        [
            "# Release Cards Report",
            "",
            f"- Generated: `{data['generated_at']}`",
            f"- Status: `{'FAIL' if failures else 'PASS'}`",
            f"- Cards generated: `{len(cards)}`",
            f"- Accepted record cards: `{counts.get('accepted_record_card', 0)}`",
            f"- Metadata gap cards: `{counts.get('metadata_gap_card', 0)}`",
            f"- Lead overlay cards: `{counts.get('lead_overlay_card', 0)}`",
            f"- Source intelligence cards: `{counts.get('source_intelligence_card', 0)}`",
            f"- Redirect notice cards: `{counts.get('redirect_notice_card', 0)}`",
            "",
            "## Layer Rules",
            "- Metadata-only cards are labelled not accepted public records.",
            "- Lead cards are labelled research leads and not accepted public records.",
            "- Redirect cards resolve old IDs to canonical IDs without changing evidence status.",
            *(["", "## Failures", *[f"- {failure}" for failure in failures]] if failures else []),
        ],
    )
    if failures:
        raise SystemExit(json.dumps({"status": "FAIL", "failures": failures[:10]}, indent=2))
    return {"status": "PASS", "cards": len(cards), **counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--release-package", required=True)
    parser.add_argument("--redirect-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result = generate(Path(args.db), Path(args.release_package), Path(args.redirect_dir), Path(args.out), Path(args.report), args.execute)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
