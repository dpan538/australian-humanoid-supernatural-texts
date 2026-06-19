#!/usr/bin/env python3
"""Plan a second public-source collection round without fetching content.

The default mode is deliberately conservative: no network requests, no record
inserts, and no scraping. The script writes a public-source lead plan and a
location-review queue so the next live collection round can be checked before
it touches external services or the records table.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import normalise_alias, slugify
from aus_humanoid.utils import PROJECT_ROOT, read_yaml, utc_now_iso, write_csv


DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "round_002.yml"
DEFAULT_LEADS_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_leads.csv"
DEFAULT_LOCATION_REVIEW_PATH = PROJECT_ROOT / "data" / "interim" / "public_round_002_location_review.csv"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "data" / "processed" / "public_round_002_plan.md"
DEFAULT_NOISE_RULES_PATH = PROJECT_ROOT / "config" / "noise_rules.yml"

LOGGER = logging.getLogger("collect_public_round_002")

LeadRow = dict[str, Any]
LocationRow = dict[str, Any]

LEAD_FIELDS = [
    "round_id",
    "lead_id",
    "collection_action",
    "source_name",
    "source_type",
    "source_publicness_level",
    "source_publicness_guard",
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
    "has_uncertain_locations",
    "locations_json",
    "location_evidence",
    "needs_location_review",
    "notes",
]


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


def load_round_config(path: str | Path) -> dict[str, Any]:
    config = read_yaml(path)
    required = [
        "round_id",
        "public_source_types",
        "validation_source_types",
        "allowed_publicness_levels",
        "planned_include_statuses",
        "historical_bands",
        "search_url_templates",
        "location_hints",
    ]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Missing round config key(s): {', '.join(missing)}")
    return config


def clean_query_for_bare_check(query: str) -> str:
    text = query.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1]
    return normalise_alias(text)


def forbidden_bare_terms(noise_rules_path: Path) -> set[str]:
    rules = read_yaml(noise_rules_path)
    forbidden = rules.get("bare_query_policy", {}).get("forbidden", [])
    return {normalise_alias(term) for term in forbidden}


def is_forbidden_bare_query(query: str, forbidden: set[str]) -> bool:
    return clean_query_for_bare_check(query) in forbidden


def date_band_name(config: dict[str, Any], date_start: str | None, date_end: str | None) -> str:
    start = date_start or ""
    end = date_end or ""
    for band in config["historical_bands"]:
        if str(band["date_start"]) == start and str(band["date_end"]) == end:
            return band["band_name"]
    special = config.get("special_date_bands", {})
    if start in special:
        return special[start]
    return "custom_or_unbanded"


def source_enabled_for_band(config: dict[str, Any], source_type: str, band_name: str) -> bool:
    source_rules = config.get("source_band_support", {}).get(source_type, {})
    enabled = source_rules.get("enabled_bands")
    if not enabled:
        return True
    return band_name in enabled


def source_publicness_guard(config: dict[str, Any], publicness_level: str | None) -> str:
    allowed = set(config.get("allowed_publicness_levels", []))
    if publicness_level in allowed:
        return "ok_public_source"
    return "BLOCKED_NONPUBLIC_SOURCE"


def manual_search_url(
    config: dict[str, Any],
    source_type: str,
    base_url: str | None,
    query: str,
    date_start: str | None = None,
    date_end: str | None = None,
) -> str:
    encoded = quote_plus(query)
    template = base_url if base_url and "{query}" in base_url else None
    template = template or config.get("search_url_templates", {}).get(source_type)
    if not template:
        return base_url or ""
    url = template.format(
        query=encoded,
        date_start=quote_plus(date_start or ""),
        date_end=quote_plus(date_end or ""),
    )
    return url


def ethics_gate(row: dict[str, Any]) -> str:
    if int(row.get("involves_indigenous_knowledge") or 0):
        return (
            "public_metadata_or_public_page_only; exclude restricted, secret/sacred, "
            "community-controlled, unpublished, or non-public material"
        )
    return "public_published_only; verify Australia scope and humanoid relevance"


def location_hint_for(config: dict[str, Any], row: dict[str, Any]) -> tuple[str, str, str]:
    figure = row.get("canonical_name") or row.get("figure")
    hint = config.get("location_hints", {}).get(figure or "")
    if hint:
        return (hint.get("state", ""), hint.get("region", ""), hint.get("precision", ""))
    if row.get("tier") == "tier_1_core" or int(row.get("involves_indigenous_knowledge") or 0):
        return ("AU", "", "Australia scope only; source must provide place or region")
    return ("", "", "location evidence must come from source")


def sources_by_type(conn) -> dict[str, list[dict[str, Any]]]:
    rows = conn.execute(
        """
        SELECT source_id, source_name, source_type, base_url, publicness_level
        FROM sources
        ORDER BY source_type, source_name, source_id
        """
    ).fetchall()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["source_type"]].append(dict(row))
    duplicates = {source_type: rows for source_type, rows in grouped.items() if len(rows) > 1}
    for source_type, rows_for_type in sorted(duplicates.items()):
        names = ", ".join(row["source_name"] for row in rows_for_type)
        LOGGER.warning("Multiple sources share source_type=%s: %s", source_type, names)
    return dict(grouped)


def append_note(note: str | None, extra: str) -> str:
    if note:
        return f"{note} | {extra}"
    return extra


def build_lead_id(*parts: str, max_alias_length: int = 24) -> str:
    cleaned = []
    for index, part in enumerate(parts):
        value = slugify(normalise_alias(part)) if part else "none"
        if index == 3:
            value = value[:max_alias_length]
        cleaned.append(value)
    return ":".join(cleaned)


def planned_query_leads(conn, config: dict[str, Any], forbidden: set[str]) -> list[LeadRow]:
    public_source_types = tuple(config["public_source_types"])
    include_statuses = tuple(config.get("planned_include_statuses", ["include_v1", "control_only"]))
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
          AND (f.include_status IS NULL OR f.include_status IN (%s))
        ORDER BY s.source_type, q.date_start, q.query_id
        """
        % (
            ",".join("?" for _ in public_source_types),
            ",".join("?" for _ in include_statuses),
        ),
        public_source_types + include_statuses,
    ).fetchall()
    leads: list[LeadRow] = []
    round_id = config["round_id"]
    for row in rows:
        row_dict = dict(row)
        query = row["query_string"]
        band_name = date_band_name(config, row["date_start"], row["date_end"])
        if not source_enabled_for_band(config, row["source_type"], band_name):
            continue
        state_hint, region_hint, precision = location_hint_for(config, row_dict)
        bare_forbidden = is_forbidden_bare_query(query, forbidden)
        publicness_guard = source_publicness_guard(config, row["publicness_level"])
        notes = row["notes"] or ""
        if publicness_guard != "ok_public_source":
            notes = append_note(notes, "WARNING: source is not marked as public; filtered unless --keep-blocked is used.")
        leads.append(
            {
                "round_id": round_id,
                "lead_id": f"{round_id}:query:{row['query_id']}",
                "collection_action": "planned_public_query",
                "source_name": row["source_name"],
                "source_type": row["source_type"],
                "source_publicness_level": row["publicness_level"],
                "source_publicness_guard": publicness_guard,
                "figure": row["canonical_name"] or "",
                "include_status": row["include_status"] or "",
                "tier": row["tier"] or "",
                "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                "query_id": row["query_id"],
                "query_string": query,
                "query_type": row["query_type"],
                "date_start": row["date_start"],
                "date_end": row["date_end"],
                "date_band": band_name,
                "expected_noise_level": row["expected_noise_level"],
                "manual_search_url": manual_search_url(
                    config, row["source_type"], row["base_url"], query, row["date_start"], row["date_end"]
                ),
                "high_noise_guard": "BLOCKED_BARE_QUERY" if bare_forbidden else "ok",
                "location_state_hint": state_hint,
                "location_region_hint": region_hint,
                "location_precision_target": precision,
                "ethics_gate": ethics_gate(row_dict),
                "notes": notes,
            }
        )
    return leads


def validation_queue_leads(conn, config: dict[str, Any], forbidden: set[str]) -> list[LeadRow]:
    sources = sources_by_type(conn)
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
    leads: list[LeadRow] = []
    round_id = config["round_id"]
    for row in rows:
        row_dict = dict(row)
        query = f'"{row["alias"]}"'
        state_hint, region_hint, precision = location_hint_for(config, row_dict)
        for band in config["historical_bands"]:
            band_name = band["band_name"]
            for source_type in config["validation_source_types"]:
                if not source_enabled_for_band(config, source_type, band_name):
                    continue
                for source in sources.get(source_type, []):
                    publicness_guard = source_publicness_guard(config, source.get("publicness_level"))
                    lead_id = build_lead_id(
                        round_id,
                        "validation",
                        row["canonical_name"],
                        row["alias"],
                        source_type,
                        band_name,
                    )
                    bare_forbidden = is_forbidden_bare_query(query, forbidden)
                    notes = (
                        "Validation queue lead only. Do not ingest as include_v1 unless "
                        "manually promoted after public-source and ethics review."
                    )
                    if publicness_guard != "ok_public_source":
                        notes = append_note(notes, "WARNING: source is not marked as public; filtered unless --keep-blocked is used.")
                    leads.append(
                        {
                            "round_id": round_id,
                            "lead_id": lead_id,
                            "collection_action": "validation_queue_only",
                            "source_name": source["source_name"],
                            "source_type": source["source_type"],
                            "source_publicness_level": source["publicness_level"],
                            "source_publicness_guard": publicness_guard,
                            "figure": row["canonical_name"],
                            "include_status": row["include_status"],
                            "tier": row["tier"],
                            "involves_indigenous_knowledge": row["involves_indigenous_knowledge"] or 0,
                            "query_id": "",
                            "query_string": query,
                            "query_type": "validation_exact_phrase",
                            "date_start": str(band["date_start"]),
                            "date_end": str(band["date_end"]),
                            "date_band": band_name,
                            "expected_noise_level": "high",
                            "manual_search_url": manual_search_url(
                                config,
                                source["source_type"],
                                source["base_url"],
                                query,
                                str(band["date_start"]),
                                str(band["date_end"]),
                            ),
                            "high_noise_guard": "BLOCKED_BARE_QUERY" if bare_forbidden else "ok",
                            "location_state_hint": state_hint,
                            "location_region_hint": region_hint,
                            "location_precision_target": precision,
                            "ethics_gate": ethics_gate(row_dict),
                            "notes": notes,
                        }
                    )
    return leads


def has_uncertain_locations(location_rows: list[dict[str, Any]]) -> bool:
    if not location_rows:
        return True
    statuses = {row["verification_status"] or "" for row in location_rows}
    types = {row["location_type"] or "" for row in location_rows}
    uncertain_statuses = {"needs_review", "broad_region_only", "verified_country_scope"}
    uncertain_types = {"broad_region", "state_or_territory", "country", "locality_or_article_title"}
    return bool(statuses & uncertain_statuses or types & uncertain_types)


def location_precision(location_rows: list[dict[str, Any]]) -> str:
    statuses = {row["verification_status"] or "" for row in location_rows}
    types = {row["location_type"] or "" for row in location_rows}
    if not location_rows:
        return "unknown"
    if "needs_review" in statuses:
        return "needs_review"
    if "town" in types or "locality" in types:
        best = "verified_place"
    elif "state_or_territory" in types:
        best = "verified_region"
    elif "broad_region" in types:
        best = "broad_region"
    else:
        best = "country_or_unclear"
    if has_uncertain_locations(location_rows) and best not in {"needs_review", "unknown", "country_or_unclear"}:
        return f"mixed_{best}"
    return best


def location_review_rows(conn, round_id: str) -> list[LocationRow]:
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
    output: list[LocationRow] = []
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
            sorted(
                {
                    f"{row['place_name']}: {row['evidence_text']}"
                    for row in locations
                    if row.get("evidence_text")
                }
            )
        )
        locations_json = json.dumps(
            [
                {
                    "place_name": row["place_name"],
                    "region": row["region"],
                    "state_territory": row["state_territory"],
                    "location_type": row["location_type"],
                    "verification_status": row["verification_status"],
                    "evidence_text": row["evidence_text"],
                    "confidence": row["confidence"],
                    "notes": row["notes"],
                }
                for row in locations
            ],
            ensure_ascii=False,
            sort_keys=True,
        )
        precision = location_precision(locations)
        uncertain = has_uncertain_locations(locations)
        output.append(
            {
                "round_id": round_id,
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
                "has_uncertain_locations": "yes" if uncertain else "no",
                "locations_json": locations_json,
                "location_evidence": evidence,
                "needs_location_review": "yes"
                if uncertain or precision.startswith("mixed_") or precision in {"unknown", "needs_review", "country_or_unclear"}
                else "no",
                "notes": "Human review should confirm whether place is setting, publication place, sighting location, or broad discourse region.",
            }
        )
    return output


def blocked_rows(leads: list[LeadRow]) -> list[LeadRow]:
    return [
        row
        for row in leads
        if row["high_noise_guard"] != "ok" or row["source_publicness_guard"] != "ok_public_source"
    ]


def duplicate_lead_ids(leads: list[LeadRow]) -> dict[str, int]:
    counts = Counter(row["lead_id"] for row in leads)
    return {lead_id: count for lead_id, count in counts.items() if count > 1}


def write_report(
    path: Path,
    config: dict[str, Any],
    all_leads: list[LeadRow],
    written_leads: list[LeadRow],
    locations: list[LocationRow],
    blocked: list[LeadRow],
    duplicate_ids: dict[str, int],
    args: argparse.Namespace,
) -> None:
    by_action = Counter(row["collection_action"] for row in written_leads)
    by_source = Counter(row["source_type"] for row in written_leads)
    by_band = Counter(row["date_band"] for row in written_leads)
    location_needs_review = sum(1 for row in locations if row["needs_location_review"] == "yes")
    blocked_by_guard = Counter(
        "publicness" if row["source_publicness_guard"] != "ok_public_source" else "high_noise"
        for row in blocked
    )

    lines = [
        "# Public Collection Round 002 Plan",
        "",
        f"Run id: `{config['round_id']}`",
        f"Created at: `{utc_now_iso()}`",
        "Mode: plan only; no network requests; no records inserted.",
        "",
        "## Execution Context",
        "",
        f"- Script: `{Path(__file__).relative_to(PROJECT_ROOT)}`",
        f"- Config: `{Path(args.config).resolve()}`",
        f"- Noise rules: `{Path(args.noise_rules).resolve()}`",
        f"- DB path: `{Path(args.db).resolve()}`",
        f"- Leads output: `{Path(args.leads_output).resolve()}`",
        f"- Location output: `{Path(args.location_output).resolve()}`",
        f"- Report output: `{Path(args.report).resolve()}`",
        f"- Validation queue included: `{not args.without_validation_queue}`",
        f"- Keep blocked rows: `{args.keep_blocked}`",
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
        "- High-noise bare queries and non-public source rows are blocked by the plan validator.",
        "",
        "## Lead Counts",
        "",
        f"- Candidate lead rows before filtering: {len(all_leads)}",
        f"- Written lead rows: {len(written_leads)}",
        f"- Filtered or blocked rows: {len(blocked)}",
        f"- Duplicate lead IDs detected: {len(duplicate_ids)}",
    ]
    for key, count in sorted(blocked_by_guard.items()):
        lines.append(f"- Blocked by `{key}`: {count}")

    for label, counter in [
        ("By action", by_action),
        ("By source type", by_source),
        ("By date band", by_band),
    ]:
        lines.extend(["", f"### {label}", ""])
        for key, count in sorted(counter.items()):
            lines.append(f"- `{key}`: {count}")

    lines.extend(["", "## Blocked Row Sample", ""])
    if blocked:
        for row in blocked[:25]:
            lines.append(
                f"- `{row['lead_id']}` | guard={row['high_noise_guard']}/{row['source_publicness_guard']} | "
                f"source={row['source_type']} | query={row['query_string']}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Duplicate Lead IDs", ""])
    if duplicate_ids:
        for lead_id, count in sorted(duplicate_ids.items())[:25]:
            lines.append(f"- `{lead_id}`: {count}")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Location Review",
            "",
            f"- Records in location queue: {len(locations)}",
            f"- Records needing location review: {location_needs_review}",
            "",
            "Location fields are evidence fields, not final geocoding truth. The `locations_json` column preserves per-place evidence, confidence, type, and notes for review.",
            "",
            "## Outputs",
            "",
            f"- `{Path(args.leads_output).resolve()}`",
            f"- `{Path(args.location_output).resolve()}`",
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
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Round configuration YAML path")
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
        help="Exit non-zero before writing files if blocked rows are generated",
    )
    parser.add_argument(
        "--keep-blocked",
        action="store_true",
        help="Write blocked rows for audit instead of filtering them from lead CSV output",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()
    setup_logging(args.verbose)

    db_path = Path(args.db)
    if not db_path.exists():
        LOGGER.error("Database not found: %s. Run `make init seed queries` first.", db_path)
        raise SystemExit(1)

    config = load_round_config(args.config)
    forbidden = forbidden_bare_terms(Path(args.noise_rules))
    with connect(db_path) as conn:
        leads = planned_query_leads(conn, config, forbidden)
        if not args.without_validation_queue:
            leads.extend(validation_queue_leads(conn, config, forbidden))
        locations = location_review_rows(conn, config["round_id"])

    blocked = blocked_rows(leads)
    duplicate_ids = duplicate_lead_ids(leads)
    if duplicate_ids:
        LOGGER.warning("Detected %d duplicate lead_id value(s)", len(duplicate_ids))
    if blocked:
        LOGGER.warning("Generated %d blocked row(s)", len(blocked))
    if args.fail_on_blocked and blocked:
        LOGGER.error("Blocked rows found; exiting without writing output files.")
        raise SystemExit(1)

    leads_to_write = leads if args.keep_blocked else [row for row in leads if row not in blocked]
    Path(args.leads_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.location_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.report).parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.leads_output, leads_to_write, LEAD_FIELDS)
    write_csv(args.location_output, locations, LOCATION_FIELDS)
    write_report(Path(args.report), config, leads, leads_to_write, locations, blocked, duplicate_ids, args)

    LOGGER.info("Wrote round 002 lead plan: %s", args.leads_output)
    LOGGER.info("Wrote round 002 location review: %s", args.location_output)
    LOGGER.info("Wrote round 002 report: %s", args.report)


if __name__ == "__main__":
    main()
