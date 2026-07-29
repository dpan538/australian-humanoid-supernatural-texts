#!/usr/bin/env python3
"""Score whether a no-auth candidate represents an item-level record."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

DIRECTORY_INDICATORS = {
    "search results",
    "browse",
    "all records",
    "affiliate",
    "directory",
    "list of",
    "collection",
    "catalogue search",
    "pagination",
    "page 1 of",
    "results found",
}

ITEM_HINTS = {
    "record",
    "item",
    "article",
    "finding aid",
    "accession",
    "call number",
    "object",
    "catalogue",
    "date",
    "title",
    "description",
    "pdf",
}

ITEM_FORMATS = {
    "CATALOGUE_ITEM",
    "SERIAL_ISSUE_ITEM",
    "ARTICLE_PAGE",
    "PDF_ISSUE",
    "HERITAGE_PLACE_PAGE",
    "BROADCAST_ITEM",
    "ARCHIVE_FINDING_AID_ITEM",
    "DIRECTORY_PAGE",
    "SEARCH_RESULT_PAGE",
}


def _slug_score(url: str, title: str) -> float:
    path = urlparse(url or "").path.lower()
    title_tokens = [token for token in re.split(r"[^a-z0-9]+", (title or "").lower()) if len(token) > 3]
    if any(token in path for token in title_tokens[:6]):
        return 0.2
    if re.search(r"/(record|item|article|object|catalogue|collection)/[^/]+", path):
        return 0.15
    if path.lower().endswith(".pdf"):
        return 0.2
    return 0.0


def item_level_confidence(candidate: dict, page_text: str = "", metadata: dict | None = None) -> tuple[float, list[str]]:
    metadata = metadata or {}
    text = " ".join(
        [
            str(candidate.get("title") or ""),
            str(candidate.get("snippet") or ""),
            page_text or "",
            " ".join(f"{key} {value}" for key, value in metadata.items() if value is not None),
        ]
    )
    lower = text.lower()
    reasons: list[str] = []
    score = 0.0
    if candidate.get("url") or metadata.get("url"):
        score += 0.15
        reasons.append("stable_url")
    if candidate.get("title"):
        score += 0.15
        reasons.append("title_present")
    if re.search(r"\b(18\d{2}|19\d{2}|20\d{2}|1930s|1940s|1950s|1960s|1970s)\b", text, re.I):
        score += 0.2
        reasons.append("date_present")
    if any(term in lower for term in ITEM_HINTS):
        score += 0.15
        reasons.append("item_metadata_hint")
    if any(term in lower for term in ["ghost", "apparition", "haunted", "phantom", "yowie", "bunyip", "min min", "local legend"]):
        score += 0.15
        reasons.append("controlled_term_present")
    score += _slug_score(str(candidate.get("url") or metadata.get("url") or ""), str(candidate.get("title") or metadata.get("title") or ""))
    directory_hits = [term for term in DIRECTORY_INDICATORS if term in lower]
    link_count = int(metadata.get("link_count") or 0)
    if directory_hits:
        score -= 0.35
        reasons.append("directory_indicator:" + ",".join(sorted(directory_hits)[:3]))
    if link_count >= 80 and not metadata.get("jsonld"):
        score -= 0.2
        reasons.append("many_links_without_item_metadata")
    return round(max(0.0, min(1.0, score)), 2), reasons


def classify_item_format(candidate: dict, page_text: str = "", metadata: dict | None = None) -> tuple[str, float, list[str]]:
    metadata = metadata or {}
    url = str(candidate.get("url") or metadata.get("url") or "").lower()
    title = str(candidate.get("title") or metadata.get("title") or "")
    text = " ".join([title, str(candidate.get("snippet") or ""), page_text or "", str(metadata)]).lower()
    reasons: list[str] = []
    if any(token in text for token in ["search results", "results found", "catalogue search"]) or "/search" in url:
        return "SEARCH_RESULT_PAGE", 0.9, ["search_result_indicator"]
    if any(token in text for token in ["browse", "all records", "affiliate", "directory", "list of", "collection landing"]):
        return "DIRECTORY_PAGE", 0.85, ["directory_indicator"]
    if url.endswith(".pdf"):
        if any(token in text for token in ["newsletter", "journal", "bulletin", "vol.", "volume", "issue", "no."]):
            return "PDF_ISSUE", 0.9, ["pdf_serial_issue"]
        return "PDF_ISSUE", 0.75, ["pdf_stable_url"]
    if any(token in text for token in ["newsletter", "journal", "bulletin", "vol.", "volume", "issue", "no."]):
        return "SERIAL_ISSUE_ITEM", 0.85, ["serial_issue_terms"]
    if any(token in text for token in ["broadcast", "radio", "television", "episode", "segment", "audiovisual", "abc"]):
        return "BROADCAST_ITEM", 0.8, ["broadcast_metadata_terms"]
    if any(token in text for token in ["finding aid", "series", "accession", "archive item", "archival description"]):
        return "ARCHIVE_FINDING_AID_ITEM", 0.8, ["archive_finding_aid_terms"]
    if any(token in text for token in ["catalogue item", "call number", "object record", "collection item"]) or "/item/" in url or "/record/" in url:
        return "CATALOGUE_ITEM", 0.8, ["catalogue_item_terms"]
    if any(token in text for token in ["heritage register", "heritage place", "listed place"]):
        return "HERITAGE_PLACE_PAGE", 0.7, ["heritage_place_terms"]
    if any(token in text for token in ["article", "story", "history", "local studies"]):
        return "ARTICLE_PAGE", 0.65, ["article_page_terms"]
    return "DIRECTORY_PAGE", 0.4, ["unknown_item_format"]


def is_item_level(candidate: dict, page_text: str = "", metadata: dict | None = None, threshold: float = 0.7) -> bool:
    score, _reasons = item_level_confidence(candidate, page_text, metadata)
    return score >= threshold


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-json", required=True)
    parser.add_argument("--page-text", default="")
    args = parser.parse_args()
    candidate = json.loads(Path(args.candidate_json).read_text(encoding="utf-8"))
    score, reasons = item_level_confidence(candidate, args.page_text)
    print(json.dumps({"item_level_confidence": score, "reasons": reasons, "is_item_level": score >= 0.7}, indent=2))


if __name__ == "__main__":
    main()
