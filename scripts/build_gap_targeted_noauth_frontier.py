#!/usr/bin/env python3
"""Build gap-targeted no-auth frontier rows for explicit 1926-1976 discovery."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote_plus

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collection_expansion_common import now_iso
from lib.autoharvest_engine import classify_route_safety, frontier_priority, load_autoharvest_config, load_noauth_seeds, stable_id
from migrate_autoharvest_gap_v2 import migrate

PRIORITY_LOCALITIES = {
    "WA": ["Kalgoorlie", "Broome", "Bunbury", "Fremantle", "Kimberley"],
    "SA": ["Adelaide", "Port Adelaide", "Mount Gambier", "Burra"],
    "NT": ["Darwin", "Alice Springs", "Katherine", "Northern Territory"],
    "TAS": ["Hobart", "Launceston", "Port Arthur", "Tasmania"],
    "ACT": ["Canberra", "Acton", "Australian Capital Territory"],
}


def read_forms(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if str(row.get("safe_to_use") or "").lower() in {"1", "true", "yes"}]


def query_patterns(config: dict, state: str) -> list[str]:
    terms = config.get("term_gate", {}).get("controlled_terms") or ["ghost", "haunted hotel", "yowie", "Min Min"]
    years = ["1955", "1960", "1964", "1965", "1970", "1976", "1950s", "1960s", "1970s"]
    localities = PRIORITY_LOCALITIES.get(state, [state])
    out: list[str] = []
    for term in terms[:12]:
        for locality in localities[:4]:
            for year in years:
                out.append(f"\"{term}\" \"{locality}\" \"{year}\"")
    return out


def route_score(seed: dict, config, state: str, query: str) -> float:
    route = dict(seed)
    route["state"] = state
    score = frontier_priority(route, config, state)
    if any(token in query for token in ["1955", "1960", "1964", "1965", "1970", "1976", "1950s", "1960s", "1970s"]):
        score += 80
    if state in {"WA", "SA", "NT", "TAS", "ACT"}:
        score += 70
    if seed.get("route_family") in {"local_history_serial", "council_local_studies", "historical_society"}:
        score += 25
    return score


def build_frontier(db_path: Path, config_path: Path, seeds_path: Path, search_forms_path: Path, run_id: str, out_path: Path, execute: bool) -> dict[str, int]:
    migrate(db_path)
    config = load_autoharvest_config(config_path)
    config_data = config.data
    seeds = load_noauth_seeds(seeds_path)
    forms = read_forms(search_forms_path)
    forms_by_route = {str(row.get("route_id")): row for row in forms}
    queued = static = rejected = 0
    examples: list[str] = []
    with sqlite3.connect(db_path) as conn:
        if execute:
            conn.execute(
                """
                INSERT INTO harvest_runs(run_id, run_name, status, started_at, target_effective_records, notes)
                VALUES (?, ?, 'running', ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET status='running', target_effective_records=excluded.target_effective_records
                """,
                (run_id, config_data.get("run_name", "noauth_gap_marathon"), now_iso(), int(config_data.get("target", {}).get("target_gap_effective_records", 2000)), "gap-targeted no-auth provisional growth layer"),
            )
        for seed in seeds:
            ok, reasons = classify_route_safety(seed, config)
            if not ok:
                rejected += 1
                continue
            state = str(seed.get("state") or "")
            if state == "NATIONAL":
                state = "ACT"
            if state not in {"WA", "SA", "NT", "TAS", "ACT", "NSW", "QLD", "VIC"}:
                state = str(seed.get("state") or "")
            route_id = str(seed.get("route_id") or seed.get("source_id") or "")
            form = forms_by_route.get(route_id)
            patterns = query_patterns(config_data, state or "WA")
            if form:
                for query in patterns[:20]:
                    url = str(form["search_url_template"]).replace("%7Bquery%7D", quote_plus(query)).replace("{query}", quote_plus(query))
                    frontier_id = stable_id("frontier_", run_id, route_id, url)
                    if execute:
                        conn.execute(
                            """
                            INSERT OR IGNORE INTO harvest_frontier (
                                frontier_id, run_id, route_id, source_id, source_name, source_tier,
                                route_family, state, url, url_type, parent_url, depth, priority_score,
                                status, discovered_at, notes
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gap_search_query', ?, 0, ?, 'queued', ?, ?)
                            """,
                            (
                                frontier_id,
                                run_id,
                                route_id,
                                seed.get("source_id") or route_id,
                                seed.get("source_name"),
                                seed.get("source_tier"),
                                seed.get("route_family"),
                                state,
                                url,
                                seed.get("official_url"),
                                route_score(seed, config, state, query),
                                now_iso(),
                                f"gap_query={query}",
                            ),
                        )
                    queued += 1
                    if len(examples) < 12:
                        examples.append(f"{route_id}: {query}")
            else:
                url = str(seed.get("official_url") or "")
                if not url:
                    rejected += 1
                    continue
                frontier_id = stable_id("frontier_", run_id, route_id, url)
                if execute:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO harvest_frontier (
                            frontier_id, run_id, route_id, source_id, source_name, source_tier,
                            route_family, state, url, url_type, parent_url, depth, priority_score,
                            status, discovered_at, notes
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gap_seed_static', '', 0, ?, 'queued', ?, ?)
                        """,
                        (
                            frontier_id,
                            run_id,
                            route_id,
                            seed.get("source_id") or route_id,
                            seed.get("source_name"),
                            seed.get("source_tier"),
                            seed.get("route_family"),
                            state,
                            url,
                            route_score(seed, config, state, ""),
                            now_iso(),
                            "gap static seed; must produce item-level target evidence before counting",
                        ),
                    )
                static += 1
        if execute:
            conn.commit()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Gap-Targeted No-Auth Frontier Plan",
        "",
        f"- Generated: `{now_iso()}`",
        f"- Run ID: `{run_id}`",
        f"- Execute: `{str(execute).lower()}`",
        f"- Search-form query frontier rows planned: `{queued}`",
        f"- Static seed frontier rows planned: `{static}`",
        f"- Rejected unsafe seeds: `{rejected}`",
        "- Trove API used: `no`",
        "- Google/Bing APIs used: `no`",
        "",
        "## Example Queries",
    ]
    lines.extend([f"- {example}" for example in examples] or ["- No safe search forms discovered; static official pages seeded."])
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"search_query_rows": queued, "static_seed_rows": static, "rejected": rejected}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--seeds", required=True)
    parser.add_argument("--search-forms", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    summary = build_frontier(Path(args.db), Path(args.config), Path(args.seeds), Path(args.search_forms), args.run_id, Path(args.out), execute=bool(args.execute and not args.dry_run))
    print(f"Wrote gap frontier plan: {args.out}")
    print(summary)


if __name__ == "__main__":
    main()
