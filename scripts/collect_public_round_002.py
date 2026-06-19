#!/usr/bin/env python3
"""Plan a second public-source collection round without fetching content.

The default mode is deliberately conservative: no network requests, no record
inserts, and no scraping. The script writes a public-source lead plan and a
location-review queue so the next live collection round can be checked before
it touches external services or the records table.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_alias
from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso, write_csv


ROUND_ID = "public_round_002"
DEFAULT_LEADS_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_leads.csv"
DEFAULT_LOCATION_REVIEW_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_location_review.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "public_round_002_plan.md"
DEFAULT_NOISE_RULES_PATH = PROJECT_ROOT / "config" / "noise_rules.yml"

PUBLIC_SOURCE_TYPES = (
    "trove_newspaper",
    "trove_magazine",
    "nla_catalogue",
    "aiatsis_public_catalogue",
    "andc",
    "modern_web",
)

VALIDATION_SOURCE_TYPES = (
    "trove_newspaper",
    "trove_magazine",
    "nla_catalogue",
    "aiatsis_public_catalogue",
    "andc",
)

HISTORICAL_BANDS = (
    {
        "band_name": "backsearch_negative_control",
        "date_start": "1803",
        "date_end": "1841",
        "label": "Retrospective Trove backsearch / negative-control window",
    },
    {
        "band_name": "early_anchor",
        "date_start": "1842",
        "date_end": "1875",
        "label": "Primary corpus early anchor period",
    },
    {
        "band_name": "publication_expansion",
        "date_start": "1876",
        "date_end": "1969",
        "label": "Pre-modern newspaper and publication expansion",
    },
    {
        "band_name": "modern_yowie_heritage_tourism_media",
        "date_start": "1970",
        "date_end": "present",
        "label": "Modern Yowie, heritage, tourism, and media period",
    },
)

LOCATION_HINTS = {
    "Yowie": ("AU", "", "Article-specific place/state required"),
    "Yahoo": ("AU", "", "Article-specific place/state required"),
    "Hairy Man": ("AU", "", "Article-specific place/state required"),
    "Yaroma": ("AU", "", "Public source must provide place or region; do not infer"),
    "Yara-ma-yha-who": ("AU", "", "Public source must provide place or region; do not infer"),
    "Mimih": ("NT", "Arnhem Land / Top End if source states it", "Public-source region only"),
    "Quinkan": ("QLD", "Cape York / Laura region if source states it", "Public-source region only"),
    "Wandjina": ("WA", "Kimberley if source states it", "Public-source region only"),
    "Nargun": ("VIC", "Gippsland / Mitchell River if source states it", "Public-source region only"),
    "Garkain": ("NT", "", "Public source must provide place or region; do not infer"),
    "Mokoi": ("AU", "", "Public source must provide place or region; do not infer"),
    "Mamu": ("AU", "", "High-noise term; verify organisation/place noise before geocoding"),
    "Pangkarlangu": ("NT", "", "Public source must provide place or region; do not infer"),
    "Puttikan": ("AU", "", "Public source must provide place or region; do not infer"),
}

LEAD_FIELDS = [
    "round_id",
    "lead_id",
    "collection_action",
    "source_name",
    "source_type",
    "source_publicness_level",
    "figure",
    "include_status",
    "tier",
    "involves_indigenous_knowledge",
    "query_id",
    "query_string",
    "query_type",
    "date_start",
    "date_end",
    "date_band",
    "expected_noise_level",
    "manual_search_url",
    "high_noise_guard",
    "location_state_hint",
    "location_region_hint",
    "location_precision_target",
    "ethics_gate",
    "notes",
]

LOCATION_FIELDS = [
    "round_id",
    "record_id",
    "year",
    "title",
    "source_name",
    "figure",
    "url",
    "verified_places",
    "state_territories",
    "broad_regions",
    "location_precision",
    "location_evidence",
    "needs_location_review",
    "notes",
]


def clean_query_for_bare_check(query: str) -> str:
    text = query.strip()
    if text.startswith('"') and text.endswith('"') and text.count('"') == 2:
        text = text[1:-1]
    return normalise_alias(text)


def forbidden_bare_terms(noise_rules_path: Path) -> set[str]:
    rules = read_yaml(noise_rules_path)
    forbidden = rules.get("bare_query_policy", {}).get("forbidden", [])
    return {normalise_alias(term) for term in forbidden}


def is_forbidden_bare_query(query: str, forbidden: set[str]) -> bool:
    return clean_query_for_bare_check(query) in forbidden


def date_band_name(date_start: str | None, date_end: str | None) -> str:
    for band in HISTORICAL_BANDS:
        if band["date_start"] == (date_start or "") and band["date_end"] == (date_end or ""):
            return band["band_name"]
    if date_start == "2004":
        return "google_trends_attention"
    if date_start == "2015-07-01":
        return "wikimedia_pageviews_attention"
    return "custom_or_unbanded"


def manual_search_url(source_type: str, base_url: str | None, query: str) -> str:
    encoded = quote_plus(query)
    if source_type == "trove_newspaper":
        return f"https://trove.nla.gov.au/search/category/newspapers?keyword={encoded}"
    if source_type == "trove_magazine":
        return f"https://trove.nla.gov.au/search/category/magazines?keyword={encoded}"
    if source_type == "nla_catalogue":
        return f"https://catalogue.nla.gov.au/catalog?search_field=all_fields&q={encoded}"
    if source_type == "aiatsis_public_catalogue":
        return f"https://aiatsis.gov.au/search?keywords={encoded}"
    if source_type == "andc":
        return f"https://researchdata.edu.au/search#!/q={encoded}"
    if source_type == "modern_web":
        return f"https://www.google.com/search?q={quote_plus(query + ' Australia public source')}"
    return base_url or ""


def ethics_gate(row: dict) -> str:
    if int(row.get("involves_indigenous_knowledge") or 0):
        return (
            "public_metadata_or_public_page_only; exclude restricted, secret/sacred, "
            "community-controlled, unpublished, or non-public material"
        )
    return "public_published_only; verify Australia scope and humanoid relevance"


def location_hint_for(figure: str | None) -> tuple[str, str, str]:
    if not figure:
        return ("", "", "location evidence must come from source")
    return LOCATION_HINTS.get(figure, ("", "", "location evidence must come from source"))


def source_ids_by_type(conn) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT source_id, source_name, source_type, base_url, publicness_level
        FROM sources
        ORDER BY source_id
        """
    ).fetchall()
    found: dict[str, dict] = {}
    for row in rows:
        found.setdefault(row["source_type"], dict(row))
    return found


def planned_query_leads(conn, forbidden: set[str]) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            q.query_id, q.query_string, q.query_type, q.date_start, q.date_end,
            q.expected_noise_level, q.notes,
            s.source_name, s.source_type, s.base_url, s.publicness_level,
            f.canonical_name, f.include_status, f.tier,
            f.involves_indigenous_knowledge
        FROM queries q
        JOIN sources s ON s.source_id = q.source_id
        LEFT JOIN figures f ON f.figure_id = q.figure_id
        WHERE q.status = 'planned'
          AND s.source_type IN (%s)
        ORDER BY s.source_type, q.date_start, q.query_id
        """
        % ",".join("?" for _ in PUBLIC_SOURCE_TYPES),
        PUBLIC_SOURCE_TYPES,
    ).fetchall()
    leads: list[dict] = []
    for row in rows:
        query = row["query_string"]
        state_hint, region_hint, precision = location_hint_for(row["canonical_name"])
        bare_forbidden = is_forbidden_bare_query(query, forbidden)
        leads.append(
            {
                "round_id": ROUND_ID,
                "lead_id": f"{ROUND_ID}:query:{row['query_id']}",
                "collection_action": "planned_public_query",
                "source_name": row["source_name"],
                "source_type": row["source_type"],
                "source_publicness_level": row["publicness_level"],
                "figure": row["canonical_name"] or "",
                "include_status": row["include_status"] or "",
                "tier": row["tier"] or "",
                "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                "query_id": row["query_id"],
                "query_string": query,
                "query_type": row["query_type"],
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "date_band": date_band_name(row["date_start"], row["date_end"]),
                "expected_noise_level": row["expected_noise_level"],
                "manual_search_url": manual_search_url(row["source_type"], row["base_url"], query),
                "high_noise_guard": "BLOCKED_BARE_QUERY" if bare_forbidden else "ok",
                "location_state_hint": state_hint,
                "location_region_hint": region_hint,
                "location_precision_target": precision,
                "ethics_gate": ethics_gate(dict(row)),
                "notes": row["notes"] or "",
            }
        )
    return leads


def validation_queue_leads(conn, forbidden: set[str]) -> list[dict]:
    sources = source_ids_by_type(conn)
    rows = conn.execute(
        """
        SELECT
            f.canonical_name, f.include_status, f.tier,
            f.involves_indigenous_knowledge, a.alias
        FROM figures f
        JOIN aliases a ON a.figure_id = f.figure_id
        WHERE f.include_status = 'validate_before_include'
        ORDER BY f.canonical_name, a.search_priority DESC, a.alias
        """
    ).fetchall()
    leads: list[dict] = []
    for row in rows:
        query = f'"{row["alias"]}"'
        state_hint, region_hint, precision = location_hint_for(row["canonical_name"])
        for band in HISTORICAL_BANDS:
            for source_type in VALIDATION_SOURCE_TYPES:
                source = sources.get(source_type)
                if not source:
                    continue
                lead_id = (
                    f"{ROUND_ID}:validation:{normalise_alias(row['canonical_name']).replace(' ', '-')}:"
                    f"{source_type}:{band['band_name']}"
                )
                bare_forbidden = is_forbidden_bare_query(query, forbidden)
                leads.append(
                    {
                        "round_id": ROUND_ID,
                        "lead_id": lead_id,
                        "collection_action": "validation_queue_only",
                        "source_name": source["source_name"],
                        "source_type": source["source_type"],
                        "source_publicness_level": source["publicness_level"],
                        "figure": row["canonical_name"],
                        "include_status": row["include_status"],
                        "tier": row["tier"],
                        "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                        "query_id": "",
                        "query_string": query,
                        "query_type": "validation_exact_phrase",
                        "date_start": band["date_start"],
                        "date_end": band["date_end"],
                        "date_band": band["band_name"],
                        "expected_noise_level": "high",
                        "manual_search_url": manual_search_url(source["source_type"], source["base_url"], query),
                        "high_noise_guard": "BLOCKED_BARE_QUERY" if bare_forbidden else "ok",
                        "location_state_hint": state_hint,
                        "location_region_hint": region_hint,
                        "location_precision_target": precision,
                        "ethics_gate": ethics_gate(dict(row)),
                        "notes": (
                            "Validation queue lead only. Do not ingest as include_v1 unless "
                            "manually promoted after public-source and ethics review."
                        ),
                    }
                )
    return leads


def location_precision(location_rows: list[dict]) -> str:
    statuses = {row["verification_status"] or "" for row in location_rows}
    types = {row["location_type"] or "" for row in location_rows}
    if "needs_review" in statuses:
        return "needs_review"
    if "town" in types or "locality" in types:
        return "verified_place"
    if "state_or_territory" in types:
        return "verified_region"
    if "broad_region" in types:
        return "broad_region"
    if location_rows:
        return "country_or_unclear"
    return "unknown"


def location_review_rows(conn) -> list[dict]:
    records = conn.execute(
        """
        SELECT r.record_id, r.year, r.title, r.url, s.source_name,
               f.canonical_name AS figure
        FROM records r
        JOIN sources s ON s.source_id = r.source_id
        LEFT JOIN figures f ON f.figure_id = r.figure_id
        ORDER BY COALESCE(r.year, 9999), r.record_id
        """
    ).fetchall()
    output: list[dict] = []
    for record in records:
        locations = [
            dict(row)
            for row in conn.execute(
                """
                SELECT l.place_name, l.region, l.state_territory, l.location_type,
                       l.verification_status, rl.evidence_text, rl.confidence, rl.notes
                FROM record_locations rl
                JOIN locations l ON l.location_id = rl.location_id
                WHERE rl.record_id = ?
                ORDER BY l.location_type, l.place_name
                """,
                (record["record_id"],),
            ).fetchall()
        ]
        places = sorted(
            row["place_name"]
            for row in locations
            if row["location_type"] in {"town", "locality", "locality_or_article_title"}
        )
        states = sorted({row["state_territory"] for row in locations if row["state_territory"]})
        broad_regions = sorted(
            {
                row["region"] or row["place_name"]
                for row in locations
                if row["location_type"] in {"broad_region", "state_or_territory", "country"}
            }
        )
        evidence = " | ".join(
            sorted({row["evidence_text"] for row in locations if row["evidence_text"]})
        )
        precision = location_precision(locations)
        output.append(
            {
                "round_id": ROUND_ID,
                "record_id": record["record_id"],
                "year": record["year"],
                "title": record["title"],
                "source_name": record["source_name"],
                "figure": record["figure"] or "",
                "url": record["url"] or "",
                "verified_places": "; ".join(places),
                "state_territories": "; ".join(states),
                "broad_regions": "; ".join(broad_regions),
                "location_precision": precision,
                "location_evidence": evidence,
                "needs_location_review": "yes" if precision in {"unknown", "needs_review", "country_or_unclear"} else "no",
                "notes": "Human review should confirm whether place is setting, publication place, sighting location, or broad discourse region.",
            }
        )
    return output


def write_report(path: Path, leads: list[dict], locations: list[dict], blocked_count: int) -> None:
    by_action = Counter(row["collection_action"] for row in leads)
    by_source = Counter(row["source_type"] for row in leads)
    by_band = Counter(row["date_band"] for row in leads)
    location_needs_review = sum(1 for row in locations if row["needs_location_review"] == "yes")

    lines = [
        "# Public Collection Round 002 Plan",
        "",
        f"Run id: `{ROUND_ID}`",
        f"Created at: `{utc_now_iso()}`",
        "Mode: plan only; no network requests; no records inserted.",
        "",
        "## Purpose",
        "",
        "Prepare a broader but still conservative public-source collection round before live fetching starts.",
        "The plan prioritises earlier source discovery, public metadata review, and explicit location-evidence tracking.",
        "",
        "## Safety Gates",
        "",
        "- Australia-only scope.",
        "- Public, published, openly discoverable sources only.",
        "- No restricted, secret/sacred, unpublished, community-controlled, or non-public materials.",
        "- Public catalogue metadata is treated as a lead, not permission to extract restricted cultural knowledge.",
        "- Validation-queue terms are written as validation leads only and are not promoted to `include_v1`.",
        "- High-noise bare queries are blocked by the plan validator.",
        "",
        "## Lead Counts",
        "",
        f"- Total lead rows: {len(leads)}",
        f"- Blocked high-noise bare rows: {blocked_count}",
    ]
    for label, counter in [
        ("By action", by_action),
        ("By source type", by_source),
        ("By date band", by_band),
    ]:
        lines.extend(["", f"### {label}", ""])
        for key, count in sorted(counter.items()):
            lines.append(f"- `{key}`: {count}")

    lines.extend(
        [
            "",
            "## Location Review",
            "",
            f"- Records in location queue: {len(locations)}",
            f"- Records needing location review: {location_needs_review}",
            "",
            "Location fields are evidence fields, not final geocoding truth. Review should distinguish sighting/setting location, publication place, broad region, and country-only mentions.",
            "",
            "## Outputs",
            "",
            f"- `{DEFAULT_LEADS_PATH.relative_to(PROJECT_ROOT)}`",
            f"- `{DEFAULT_LOCATION_REVIEW_PATH.relative_to(PROJECT_ROOT)}`",
            "",
            "## Next Live-Collection Step",
            "",
            "After reviewing this plan, implement source-specific collectors one at a time. Start with manual Trove/NLA metadata verification, then add API-backed retrieval only where credentials, publicness, and rate limits are clear.",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--noise-rules", default=str(DEFAULT_NOISE_RULES_PATH), help="Noise rules YAML path")
    parser.add_argument("--leads-output", default=str(DEFAULT_LEADS_PATH), help="Lead-plan CSV output path")
    parser.add_argument(
        "--location-output",
        default=str(DEFAULT_LOCATION_REVIEW_PATH),
        help="Location-review CSV output path",
    )
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Markdown report output path")
    parser.add_argument(
        "--without-validation-queue",
        action="store_true",
        help="Omit validation-queue-only leads from the plan",
    )
    parser.add_argument(
        "--fail-on-blocked",
        action="store_true",
        help="Exit non-zero if the generated plan contains a forbidden bare high-noise query",
    )
    args = parser.parse_args()

    forbidden = forbidden_bare_terms(Path(args.noise_rules))
    with connect(args.db) as conn:
        leads = planned_query_leads(conn, forbidden)
        if not args.without_validation_queue:
            leads.extend(validation_queue_leads(conn, forbidden))
        locations = location_review_rows(conn)

    blocked_count = sum(1 for row in leads if row["high_noise_guard"] == "BLOCKED_BARE_QUERY")
    write_csv(args.leads_output, leads, LEAD_FIELDS)
    write_csv(args.location_output, locations, LOCATION_FIELDS)
    write_report(Path(args.report), leads, locations, blocked_count)

    print(f"Wrote round 002 lead plan: {args.leads_output}")
    print(f"Wrote round 002 location review: {args.location_output}")
    print(f"Wrote round 002 report: {args.report}")
    if blocked_count:
        print(f"WARNING: {blocked_count} blocked high-noise bare query row(s) found.")
        if args.fail_on_blocked:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
