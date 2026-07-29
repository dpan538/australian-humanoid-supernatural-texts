#!/usr/bin/env python3
"""Probe Trove hit counts for the 1926-2011 gap plan.

Default mode is dry-run: it writes planned request rows and performs no network
requests. Live mode requires --live and a TROVE_API_KEY environment variable or
--api-key-file. Outputs are hit-count/probe metadata only, not records.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso, write_csv


DEFAULT_CONFIG = PROJECT_ROOT / "config" / "gap_probe_1926_2011.yml"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "interim" / "gap_probe_1926_2011" / "trove_probe_requests.csv"
TROVE_ENDPOINT = "https://api.trove.nla.gov.au/v3/result"
USER_AGENT = "AusFiguresGapProbe/0.1 public-text research; contact: local"

OUTPUT_FIELDS = [
    "probe_status",
    "probed_at",
    "source_target_id",
    "source_target_label",
    "zone",
    "date_window_id",
    "year",
    "query_family_id",
    "query_family_label",
    "priority",
    "query_template",
    "expected_noise",
    "cultural_sensitivity_default",
    "request_url_redacted",
    "hit_count",
    "sample_count",
    "samples_json",
    "error",
    "publicness_note",
    "rights_note",
    "ingestion_status",
]


def api_key_from_args(args: argparse.Namespace) -> str:
    if args.api_key_file:
        return Path(args.api_key_file).read_text(encoding="utf-8").strip()
    return os.environ.get("TROVE_API_KEY", "").strip()


def trove_zone(source_target_id: str) -> str | None:
    if "newspaper" in source_target_id:
        return "newspaper"
    if "magazine" in source_target_id:
        return "magazine"
    return None


def request_url(query: str, zone: str, year: int, api_key: str) -> str:
    params = {
        "key": api_key,
        "encoding": "json",
        "zone": zone,
        "q": query,
        "reclevel": "brief",
        "l-year": str(year),
        "n": "3",
    }
    return TROVE_ENDPOINT + "?" + urllib.parse.urlencode(params)


def redacted_url(query: str, zone: str, year: int) -> str:
    return request_url(query, zone, year, "REDACTED")


def planned_rows(config: dict[str, Any], max_priority: int, source_target_filter: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    trove_targets = []
    for target in config.get("source_targets", []):
        zone = trove_zone(str(target.get("id", "")))
        if zone is None:
            continue
        if source_target_filter and target.get("id") != source_target_filter:
            continue
        trove_targets.append((target, zone))

    for window in config.get("date_windows", []):
        start = int(window["start_year"])
        end = int(window["end_year"])
        for family in config.get("query_families", []):
            priority = int(family.get("priority") or 999)
            if priority > max_priority:
                continue
            for template in family.get("templates", []):
                for target, zone in trove_targets:
                    for year in range(start, end + 1):
                        rows.append(
                            {
                                "probe_status": "planned_probe_not_requested",
                                "probed_at": "",
                                "source_target_id": target["id"],
                                "source_target_label": target["label"],
                                "zone": zone,
                                "date_window_id": window["id"],
                                "year": year,
                                "query_family_id": family["id"],
                                "query_family_label": family["label"],
                                "priority": priority,
                                "query_template": template,
                                "expected_noise": family.get("expected_noise", ""),
                                "cultural_sensitivity_default": family.get("cultural_sensitivity_default", ""),
                                "request_url_redacted": redacted_url(template, zone, year),
                                "hit_count": "",
                                "sample_count": "",
                                "samples_json": "",
                                "error": "",
                                "publicness_note": target.get("publicness_check", ""),
                                "rights_note": "metadata-only probe; article text/content requires separate review",
                                "ingestion_status": "not_ingested",
                            }
                        )
    return rows


def extract_records(payload: dict[str, Any], zone: str) -> tuple[int | None, list[dict[str, Any]]]:
    categories = payload.get("category") or []
    if isinstance(categories, dict):
        categories = [categories]
    selected: dict[str, Any] | None = None
    for category in categories:
        if not isinstance(category, dict):
            continue
        if str(category.get("code") or category.get("name") or "").lower() == zone:
            selected = category
            break
    if selected is None and categories:
        selected = categories[0] if isinstance(categories[0], dict) else None

    records = (selected or {}).get("records") if selected else payload.get("records")
    if not isinstance(records, dict):
        records = {}

    raw_total = records.get("total") or records.get("totalResults") or (selected or {}).get("total")
    try:
        total = int(str(raw_total).replace(",", ""))
    except (TypeError, ValueError):
        total = None

    items: Any = (
        records.get("article")
        or records.get("work")
        or records.get("list")
        or records.get("item")
        or []
    )
    if isinstance(items, dict):
        items = [items]
    if not isinstance(items, list):
        items = []
    return total, [item for item in items if isinstance(item, dict)]


def sample_item(item: dict[str, Any]) -> dict[str, Any]:
    article_id = item.get("id") or item.get("troveId") or item.get("identifier")
    trove_url = item.get("troveUrl") or item.get("url")
    if not trove_url and article_id:
        trove_url = f"https://nla.gov.au/{article_id}"
    return {
        "id": article_id,
        "title": item.get("title") or item.get("heading"),
        "date": item.get("date") or item.get("issued"),
        "newspaper": item.get("newspaper") or item.get("titleName"),
        "url": trove_url,
    }


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - official public API URL.
        return json.loads(response.read().decode("utf-8", errors="replace"))


def run_live(rows: list[dict[str, Any]], api_key: str, delay_seconds: float) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        url = request_url(row["query_template"], row["zone"], int(row["year"]), api_key)
        live_row = {**row, "probe_status": "requested", "probed_at": utc_now_iso()}
        try:
            payload = fetch_json(url)
            total, items = extract_records(payload, row["zone"])
            samples = [sample_item(item) for item in items[:3]]
            live_row.update(
                {
                    "probe_status": "hit_count_metadata_only",
                    "hit_count": "" if total is None else total,
                    "sample_count": len(samples),
                    "samples_json": json.dumps(samples, ensure_ascii=False, sort_keys=True),
                    "error": "",
                }
            )
        except Exception as exc:  # pragma: no cover - live network path.
            live_row.update({"probe_status": "probe_error", "error": str(exc)})
        output.append(live_row)
        time.sleep(delay_seconds)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--max-requests", type=int, default=80)
    parser.add_argument("--max-priority", type=int, default=2)
    parser.add_argument("--source-target", choices=["trove_newspapers_metadata", "trove_magazines_metadata"])
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    parser.add_argument("--live", action="store_true", help="Perform official Trove API requests")
    parser.add_argument("--api-key-file", help="Read TROVE_API_KEY from this local file instead of the environment")
    args = parser.parse_args()

    config = read_yaml(args.config)
    rows = planned_rows(config, args.max_priority, args.source_target)
    limited_rows = rows[: max(0, args.max_requests)]
    if args.live:
        api_key = api_key_from_args(args)
        if not api_key:
            raise SystemExit("Live mode requires TROVE_API_KEY or --api-key-file")
        limited_rows = run_live(limited_rows, api_key, args.delay_seconds)

    write_csv(args.output, limited_rows, OUTPUT_FIELDS)
    mode = "live hit-count probe" if args.live else "dry-run request plan"
    print(f"Wrote Trove {mode}: {args.output}")
    print(f"Rows written: {len(limited_rows)} of {len(rows)} planned rows")


if __name__ == "__main__":
    main()
