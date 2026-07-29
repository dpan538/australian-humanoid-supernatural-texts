#!/usr/bin/env python3
"""Cluster discovered no-auth search forms and build a repaired probe plan."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

from collection_expansion_common import write_csv
from lib.gap_recovery import PRIORITY_STATES, read_csv, stable_action_id, top_counts, truthy, write_report

PLAN_FIELDS = [
    "action_id",
    "route_id",
    "source_name",
    "state",
    "search_url_template",
    "cluster_label",
    "adapter_hint",
    "query_string",
    "priority_score",
    "should_fetch",
    "should_manual_review",
    "safety_notes",
]


def cluster_form(row: dict) -> tuple[str, str, list[str]]:
    template = str(row.get("search_url_template") or "")
    hay = " ".join(str(row.get(k) or "") for k in ["source_name", "route_id", "reason", "query_param", "search_url_template"]).lower()
    reasons: list[str] = []
    if str(row.get("method") or "").upper() != "GET":
        return "POST_FORM", "", ["non_get"]
    auth_hay = hay.replace("{query}", "").replace("%7bquery%7d", "")
    if any(token in auth_hay for token in ["login", "password", "captcha", "auth=", "token=", "email="]):
        return "LOGIN_OR_AUTH", "", ["auth_or_token"]
    if not truthy(row.get("safe_to_use")):
        return "UNKNOWN_UNSAFE", "", ["not_safe_to_use"]
    if "wp-" in hay or "/?s=" in template:
        return "WORDPRESS", "wordpress", reasons
    if "search/node" in template or "drupal" in hay:
        return "DRUPAL", "drupal", reasons
    if "items/browse" in template or "omeka" in hay:
        return "OMEKA", "omeka", reasons
    if "informationobject" in template or "atom" in hay:
        return "ATOM", "atom", reasons
    if "queries_keywords_query" in template or "funnelback" in hay or "squiz" in hay:
        return "SQUIZ_FUNNELBACK", "generic_council", reasons
    if any(token in hay for token in ["museum", "collection", "heritage"]):
        return "MUSEUM_COLLECTION", "generic_museum", reasons
    if any(token in hay for token in ["historical society", "history", "newsletter", "journal", "bulletin"]):
        return "HISTORICAL_SOCIETY", "generic_historical_society", reasons
    if ".pdf" in hay:
        return "PDF_INDEX", "generic_pdf_index", reasons
    if any(token in hay for token in ["council", "local"]):
        return "GENERIC_COUNCIL", "generic_council", reasons
    return "GENERIC_COUNCIL", "generic_catalogue", reasons


def priority(row: dict, label: str) -> int:
    score = 0
    if row.get("state") in PRIORITY_STATES:
        score += 50
    if label in {"WORDPRESS", "DRUPAL", "OMEKA", "ATOM", "SQUIZ_FUNNELBACK"}:
        score += 25
    if label in {"HISTORICAL_SOCIETY", "PDF_INDEX", "GENERIC_COUNCIL", "MUSEUM_COLLECTION"}:
        score += 20
    if truthy(row.get("safe_to_probe")):
        score += 30
    try:
        score += int(float(row.get("confidence") or 0) * 20)
    except ValueError:
        pass
    return score


def repair(search_forms: Path, viability_dir: Path, out_dir: Path, execute: bool) -> dict[str, int]:
    del viability_dir, execute
    rows = read_csv(search_forms)
    clusters: list[dict] = []
    pauses: list[dict] = []
    for row in rows:
        label, adapter, reasons = cluster_form(row)
        clustered = {**row, "cluster_label": label, "adapter_hint": adapter, "cluster_reasons": ";".join(reasons), "priority_score": priority(row, label)}
        clusters.append(clustered)
        if label in {"UNKNOWN_UNSAFE", "LOGIN_OR_AUTH", "POST_FORM", "CAPTCHA_OR_TOKEN"}:
            pauses.append({**clustered, "pause_reason": label})
    allowed = [row for row in clusters if row["cluster_label"] not in {"UNKNOWN_UNSAFE", "LOGIN_OR_AUTH", "POST_FORM", "CAPTCHA_OR_TOKEN"}]
    allowed = sorted(allowed, key=lambda row: int(row.get("priority_score") or 0), reverse=True)[:200]
    plan = []
    queries = ['"ghost" "1968"', '"haunted" "1964"', '"yowie" "1971"', '"bunyip" "1950s"']
    for row in allowed:
        for query in queries[:1]:
            plan.append(
                {
                    "action_id": stable_action_id("repaired_form", row.get("route_id"), row.get("search_url_template"), query),
                    "route_id": row.get("route_id"),
                    "source_name": row.get("source_name"),
                    "state": row.get("state"),
                    "search_url_template": row.get("search_url_template"),
                    "cluster_label": row.get("cluster_label"),
                    "adapter_hint": row.get("adapter_hint"),
                    "query_string": query,
                    "priority_score": row.get("priority_score"),
                    "should_fetch": 1,
                    "should_manual_review": 0,
                    "safety_notes": "GET only; same-domain; robots required; first result page only; no pagination",
                }
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "search_form_clusters.csv", clusters, list(clusters[0].keys()) if clusters else ["route_id"])
    write_csv(out_dir / "repaired_search_form_probe_plan.csv", plan, PLAN_FIELDS)
    write_csv(out_dir / "search_form_routes_to_pause.csv", pauses, list(pauses[0].keys()) if pauses else ["route_id"])
    counts = Counter(row["cluster_label"] for row in clusters)
    tasks = [
        "- Improve result parsing for `WORDPRESS`, `DRUPAL`, `OMEKA`, and `ATOM` clusters before pagination.",
        "- Keep `POST_FORM`, `LOGIN_OR_AUTH`, `CAPTCHA_OR_TOKEN`, and `UNKNOWN_UNSAFE` out of automation.",
        "- Probe only the top repaired plan rows first; do not sweep all discovered forms.",
    ]
    (out_dir / "adapter_improvement_tasks.md").write_text("# Adapter Improvement Tasks\n\n" + "\n".join(tasks) + "\n", encoding="utf-8")
    write_report(
        out_dir / "search_form_cluster_report.md",
        "Search Form Cluster Report",
        {
            "Forms inspected": len(rows),
            "Repaired probe plan rows": len(plan),
            "Paused/unsafe forms": len(pauses),
            "Public records mutated": "no",
            "Map flags mutated": "no",
        },
        {"Cluster Counts": [f"- `{key}`: {value}" for key, value in counts.most_common()], "Top States": top_counts(clusters, "state")},
    )
    return {"forms": len(rows), "plan": len(plan), "paused": len(pauses), "clusters": len(counts)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-forms", required=True)
    parser.add_argument("--viability-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(repair(Path(args.search_forms), Path(args.viability_dir), Path(args.out_dir), execute=bool(args.execute and not args.dry_run)))


if __name__ == "__main__":
    main()
