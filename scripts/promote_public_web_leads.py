#!/usr/bin/env python3
"""Promote reviewed public-web sitemap leads into V2 display candidates.

This is a deliberately source-tiered bridge between broad discovery and the
accepted display corpus. It accepts public institutional, archive, local-history,
and reputable public-source pages when they contain a person-form supernatural
signal. Tourism-only pages are preserved as leads unless explicitly overridden
by a stronger source class in the domain policy.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from aus_humanoid.db import DEFAULT_DB_PATH, connect
from aus_humanoid.normalise import canonicalise_whitespace
from aus_humanoid.utils import PROJECT_ROOT, utc_now_iso
from collect_v2_batch import ensure_candidate_geo_columns, insert_candidate


ARCHIVE_FIRST_DOMAIN_POLICY = {
    "nationaltrust.org.au": ("National Trust Australia", "institutional_web", "B"),
    "portarthur.org.au": ("Port Arthur Historic Site", "institutional_web", "B"),
    "fremantleprison.com.au": ("Fremantle Prison", "institutional_web", "B"),
    "oldmelbournegaol.com.au": ("Old Melbourne Gaol", "institutional_web", "B"),
    "adelaidegaol.sa.gov.au": ("Adelaide Gaol", "institutional_web", "B"),
    "sovereignhill.com.au": ("Sovereign Hill", "institutional_web", "B"),
    "migrationmuseum.com.au": ("Migration Museum", "institutional_web", "B"),
    "history.sa.gov.au": ("History Trust of South Australia", "institutional_web", "B"),
    "wamuseum.com.au": ("Western Australian Museum", "institutional_web", "B"),
    "museum.wa.gov.au": ("Western Australian Museum", "institutional_web", "B"),
    "magnt.net.au": ("Museum and Art Gallery of the Northern Territory", "institutional_web", "B"),
    "libraries.tas.gov.au": ("Libraries Tasmania", "institutional_web", "B"),
    "narrynah.com.au": ("Narryna Heritage Museum", "institutional_web", "B"),
    "qvmag.tas.gov.au": ("Queen Victoria Museum and Art Gallery", "institutional_web", "B"),
    "sl.nsw.gov.au": ("State Library of New South Wales", "institutional_web", "B"),
    "slv.vic.gov.au": ("State Library Victoria", "institutional_web", "B"),
    "slq.qld.gov.au": ("State Library of Queensland", "institutional_web", "B"),
    "slsa.sa.gov.au": ("State Library of South Australia", "institutional_web", "B"),
    "slwa.wa.gov.au": ("State Library of Western Australia", "institutional_web", "B"),
    "ntl.nt.gov.au": ("Northern Territory Library", "institutional_web", "B"),
    "nla.gov.au": ("National Library of Australia", "institutional_web", "A"),
    "trove.nla.gov.au": ("Trove", "trove_newspaper", "A"),
}

DISCOVERY_ONLY_HOST_FRAGMENTS = (
    "visitvictoria.com",
    "westernaustralia.com",
    "southaustralia.com",
    "northernterritory.com",
    "discovertasmania.com",
    "visitcanberra.com",
    "tripadvisor.",
    "timeout.",
)

PLACE_CATALOGUE = [
    ("Port Arthur Historic Site, Tasmania", "TAS", -43.147019, 147.851265, ("port arthur",)),
    ("Fremantle Prison, Western Australia", "WA", -32.0558, 115.7536, ("fremantle prison",)),
    ("Old Melbourne Gaol, Victoria", "VIC", -37.8078, 144.9653, ("old melbourne gaol",)),
    ("Adelaide Gaol, South Australia", "SA", -34.9157, 138.5889, ("adelaide gaol",)),
    ("Hobart Convict Penitentiary, Tasmania", "TAS", -42.8796, 147.3275, ("hobart convict penitentiary", "hobart penitentiary")),
    ("Narryna Heritage Museum, Battery Point, Tasmania", "TAS", -42.8897, 147.3316, ("narryna",)),
    ("Sovereign Hill, Ballarat, Victoria", "VIC", -37.579, 143.867, ("sovereign hill",)),
    ("Migration Museum, Adelaide, South Australia", "SA", -34.9217, 138.6048, ("migration museum",)),
    ("Western Australian Museum Boola Bardip, Perth, Western Australia", "WA", -31.9506, 115.8615, ("boola bardip", "wa museum")),
    ("Museum and Art Gallery of the Northern Territory, Darwin", "NT", -12.4381, 130.8339, ("magnt", "museum and art gallery of the northern territory")),
    ("Queen Victoria Museum and Art Gallery, Launceston", "TAS", -41.4332, 147.1374, ("qvmag", "queen victoria museum")),
]

STATE_HINTS = {
    "western australia": "WA",
    "wa": "WA",
    "northern territory": "NT",
    "nt": "NT",
    "south australia": "SA",
    "sa": "SA",
    "queensland": "QLD",
    "qld": "QLD",
    "new south wales": "NSW",
    "nsw": "NSW",
    "victoria": "VIC",
    "vic": "VIC",
    "tasmania": "TAS",
    "tas": "TAS",
    "australian capital territory": "ACT",
    "act": "ACT",
}

LABEL_PATTERNS = [
    ("apparition", "apparition_account", "human-like apparition"),
    ("ghost", "ghost_legend", "human-like ghost or apparition"),
    ("haunt", "ghost_legend", "human-like ghost or apparition"),
    ("hairy man", "encounter_account", "hairy humanoid description"),
    ("wild man", "encounter_account", "wild/hairy humanoid description"),
    ("mimih", "spirit_person_narrative", "public spirit-person narrative"),
    ("mimi", "spirit_person_narrative", "public spirit-person narrative"),
    ("wandjina", "traditional_narrative", "public traditional narrative or public retelling"),
    ("quinkan", "traditional_narrative", "public traditional narrative or public retelling"),
    ("nargun", "spirit_person_narrative", "public spirit-person narrative"),
    ("garkain", "spirit_person_narrative", "public spirit-person narrative"),
    ("mamu", "spirit_person_narrative", "public spirit-person narrative"),
    ("pangkarlangu", "giant_or_ogre_narrative", "public giant/spirit-person narrative"),
]

WEAK_ONLY_LABELS = {"Public person-form supernatural narrative"}
SUBSTANTIVE_TITLE_TERMS = (
    "ghost",
    "ghostly",
    "haunt",
    "haunted",
    "apparition",
    "paranormal",
    "afterlife",
    "hairy man",
    "wild man",
    "mimih",
    "mimi spirit",
    "wandjina",
    "quinkan",
    "nargun",
    "garkain",
    "mamu",
    "pangkarlangu",
)


@dataclass(frozen=True)
class DomainPolicy:
    source_name: str
    source_type: str
    source_tier: str
    discovery_only: bool


def host_for(url: str) -> str:
    return urlsplit(url).netloc.lower().removeprefix("www.")


def policy_for(url: str) -> DomainPolicy:
    host = host_for(url)
    for fragment in DISCOVERY_ONLY_HOST_FRAGMENTS:
        if fragment in host:
            return DomainPolicy(host, "tourism_discovery", "E", True)
    for domain, (name, source_type, tier) in ARCHIVE_FIRST_DOMAIN_POLICY.items():
        if host == domain or host.endswith("." + domain):
            return DomainPolicy(name, source_type, tier, False)
    return DomainPolicy(host or "Public web", "modern_web", "C", False)


def infer_label(text: str) -> tuple[str, str, str]:
    lowered = text.lower()
    for term, narrative_type, humanoid_basis in LABEL_PATTERNS:
        if re.search(rf"\b{re.escape(term)}\b", lowered):
            label = "Ghost" if term == "haunt" else term.title()
            return label, narrative_type, humanoid_basis
    return "Public person-form supernatural narrative", "local_legend", "human-like figure or person-form narrative"


def infer_place(text: str) -> tuple[str, str | None, float | None, float | None, str, str]:
    lowered = text.lower()
    for place, state, lat, lon, aliases in PLACE_CATALOGUE:
        if any(alias in lowered for alias in aliases):
            return place, state, lat, lon, "exact_site", "verified_institutional_coordinate"
    for hint, state in STATE_HINTS.items():
        if re.search(rf"\b{re.escape(hint)}\b", lowered):
            return state, state, None, None, "state_or_territory", "verified_region"
    return "", None, None, None, "unmapped", "needs_review"


def evidence_summary(title: str, snippet: str, label: str, place: str) -> str:
    base = f"The public source page is a review candidate for a {label} record"
    if place:
        base += f" associated with {place}"
    body = canonicalise_whitespace(snippet)
    if body:
        return f"{base}. Public page excerpt: {body[:420]}"
    return f"{base}. No full-text reproduction is asserted; the page should be reviewed against its public source before analysis."


def source_date_text(row: dict[str, str]) -> str:
    generated = (row.get("generated_at") or utc_now_iso())[:10]
    return f"undated public page, accessed {generated}"


def row_to_candidate(row: dict[str, str], run_id: str, strict_geo_only: bool) -> dict[str, object]:
    url = canonicalise_whitespace(row.get("url"))
    title = canonicalise_whitespace(row.get("title") or url)
    snippet = canonicalise_whitespace(row.get("snippet"))
    text = " ".join([title, row.get("matched_terms") or "", row.get("supernatural_terms") or "", row.get("person_form_terms") or "", snippet])
    policy = policy_for(url)
    label, narrative_type, humanoid_basis = infer_label(text)
    place, state, lat, lon, precision, verification = infer_place(text)
    weak_only = label in WEAK_ONLY_LABELS
    title_signal = any(term in title.lower() for term in SUBSTANTIVE_TITLE_TERMS)
    accepted = row.get("lead_status") == "review_candidate" and not policy.discovery_only and not weak_only and title_signal
    if strict_geo_only and (lat is None or lon is None):
        accepted = False
    status = "accepted" if accepted else "lead_only"
    reason = "" if accepted else (
        "tourism_discovery_only"
        if policy.discovery_only
        else "weak_or_ambiguous_supernatural_term_requires_manual_review"
        if weak_only
        else "supernatural_term_only_in_navigation_or_page_boilerplate"
        if not title_signal
        else "requires_location_or_source_review"
    )
    sensitivity = "medium" if label.lower() in {"mimih", "mimi", "wandjina", "quinkan", "nargun", "garkain", "mamu", "pangkarlangu"} else "low"
    ethics = "caution_indigenous_knowledge" if sensitivity == "medium" else "ok_public"
    external_id = "public-web:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    return {
        "run_id": run_id,
        "candidate_status": status,
        "source_name": policy.source_name,
        "source_type": policy.source_type,
        "source_tier": policy.source_tier,
        "title": title,
        "publication_or_organisation": policy.source_name,
        "publication_date_text": source_date_text(row),
        "access_date": (row.get("generated_at") or utc_now_iso())[:10],
        "url": url,
        "canonical_url": url,
        "external_id": external_id,
        "publicness_status": "public_page",
        "rights_access_status": "public web page; no full reproduction asserted",
        "narrative_type": narrative_type,
        "secondary_role": "heritage_discourse" if policy.source_tier in {"B", "C"} else "source_pointer",
        "australian_relation": "Australian public source or Australian place association",
        "humanoid_basis": humanoid_basis,
        "source_label": label,
        "location_text": place,
        "location_role": "legend_associated_place" if place else "uncertain_or_broad_location",
        "latitude": lat,
        "longitude": lon,
        "location_precision": precision,
        "geocode_source": "script_known_public_place_catalogue" if lat is not None else "state_or_unmapped_from_public_page",
        "geocode_verification_status": verification,
        "coordinate_evidence_note": f"Place inferred from public page title/snippet; state hint={state or 'unmapped'}",
        "duplicate_check_status": "canonical_url_checked",
        "quality_class": policy.source_tier if policy.source_tier in {"A", "B", "C"} else "C",
        "ethics_review_status": ethics,
        "cultural_sensitivity": sensitivity,
        "acceptance_decision": "accepted" if accepted else "not_accepted",
        "rejection_reason": reason,
        "evidence_summary": evidence_summary(title, snippet, label, place),
        "raw_metadata_json": {"source_lead": row, "promotion_policy": policy.__dict__},
    }


def promote(path: Path, run_id: str, strict_geo_only: bool, limit: int | None) -> dict[str, int]:
    counts: dict[str, int] = {"accepted": 0, "lead_only": 0, "duplicate": 0, "rejected": 0}
    with connect(DEFAULT_DB_PATH) as conn:
        ensure_candidate_geo_columns(conn)
        with path.open("r", encoding="utf-8", newline="") as handle:
            for idx, row in enumerate(csv.DictReader(handle)):
                if limit is not None and idx >= limit:
                    break
                candidate = row_to_candidate(row, run_id, strict_geo_only)
                status = insert_candidate(conn, candidate, strict_geo_only=strict_geo_only)
                counts[status] = counts.get(status, 0) + 1
        conn.commit()
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="CSV from discover_public_web_sitemap.py")
    parser.add_argument("--run-id", default="v2_public_web_lead_promotion")
    parser.add_argument("--strict-geo-only", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", default=str(PROJECT_ROOT / "data" / "processed" / "v2" / "public_web_lead_promotion.md"))
    args = parser.parse_args()
    counts = promote(Path(args.input), args.run_id, args.strict_geo_only, args.limit)
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "\n".join(
            [
                "# Public Web Lead Promotion",
                "",
                f"- Generated: `{utc_now_iso()}`",
                f"- Input: `{args.input}`",
                f"- Run id: `{args.run_id}`",
                f"- Strict geo only: `{args.strict_geo_only}`",
                "",
                "## Counts",
                *[f"- {key}: {value}" for key, value in sorted(counts.items())],
                "",
                "## Source Policy",
                "- Tourism-only pages are preserved as discovery leads, not accepted records.",
                "- Accepted records require non-tourism public-source policy, substantive person-form signal, stable URL/title, and evidence summary.",
                "- Strict map eligibility requires a known concrete place coordinate.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(counts, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
