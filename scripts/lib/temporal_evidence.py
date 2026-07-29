from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

TARGET_START = 1926
TARGET_END = 1976

YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b")
DECADE_RE = re.compile(r"\b(1930s|1940s|1950s|1960s|1970s)\b", re.IGNORECASE)
RANGE_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\s*[-–]\s*(18\d{2}|19\d{2}|20\d{2})\b")
VAGUE_RE = re.compile(r"\b(20th century|twentieth century|post[- ]war|postwar)\b", re.IGNORECASE)


@dataclass
class TemporalEvidence:
    evidence_type: str = ""
    evidence_text: str = ""
    extracted_year: int | None = None
    coverage_start_year: int | None = None
    coverage_end_year: int | None = None
    term_nearby: str = ""
    locality_nearby: str = ""
    confidence: float = 0.0
    reason: str = ""
    target_date_basis: str = "none"

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_type": self.evidence_type,
            "evidence_text": self.evidence_text,
            "extracted_year": self.extracted_year,
            "coverage_start_year": self.coverage_start_year,
            "coverage_end_year": self.coverage_end_year,
            "term_nearby": self.term_nearby,
            "locality_nearby": self.locality_nearby,
            "confidence": self.confidence,
            "reason": self.reason,
            "target_date_basis": self.target_date_basis,
        }


def extract_years(text: str) -> list[int]:
    return sorted({int(match.group(1)) for match in YEAR_RE.finditer(text or "") if 1800 <= int(match.group(1)) <= 2030})


def extract_decades(text: str) -> list[tuple[str, int, int, tuple[int, int]]]:
    out: list[tuple[str, int, int, tuple[int, int]]] = []
    for match in DECADE_RE.finditer(text or ""):
        start = int(match.group(1)[:4])
        out.append((match.group(1), start, start + 9, match.span()))
    return out


def extract_year_ranges(text: str) -> list[tuple[int, int, str, tuple[int, int]]]:
    out: list[tuple[int, int, str, tuple[int, int]]] = []
    for match in RANGE_RE.finditer(text or ""):
        start = int(match.group(1))
        end = int(match.group(2))
        if start <= end:
            out.append((start, end, match.group(0), match.span()))
    return out


def year_in_target_range(year: int, start: int = TARGET_START, end: int = TARGET_END) -> bool:
    return start <= int(year) <= end


def range_overlaps_target(start: int, end: int, target_start: int = TARGET_START, target_end: int = TARGET_END) -> bool:
    return int(start) <= target_end and int(end) >= target_start


def _nearby_token(text: str, span: tuple[int, int], tokens: list[str], max_distance: int) -> str:
    lower = (text or "").lower()
    center = span[0]
    best = ""
    best_distance = max_distance + 1
    for token in tokens:
        needle = str(token or "").strip().lower()
        if not needle:
            continue
        for match in re.finditer(re.escape(needle), lower):
            distance = min(abs(match.start() - center), abs(match.end() - center))
            if distance <= max_distance and distance < best_distance:
                best = token
                best_distance = distance
    return best


def year_near_term(text: str, year_text: str, terms: list[str], max_distance: int = 350) -> bool:
    match = re.search(re.escape(str(year_text)), text or "", flags=re.IGNORECASE)
    if not match:
        return False
    return bool(_nearby_token(text, match.span(), terms, max_distance))


def score_temporal_confidence(evidence: TemporalEvidence) -> float:
    if not evidence.evidence_type:
        return 0.0
    score = 0.45
    if evidence.evidence_type in {"source_publication_year", "record_publication_date", "narrative_year", "narrative_date", "collection_item_date"}:
        score += 0.35
    elif evidence.evidence_type == "coverage_year_range":
        score += 0.25
    elif evidence.evidence_type == "decade_near_term":
        score += 0.20
    if evidence.term_nearby:
        score += 0.15
    if evidence.locality_nearby:
        score += 0.05
    return round(min(score, 1.0), 2)


def classify_temporal_evidence(text: str, terms: list[str], localities: list[str], max_distance: int = 350) -> TemporalEvidence:
    if not text or VAGUE_RE.search(text):
        return TemporalEvidence(reason="no_explicit_target_temporal_evidence")
    for start, end, raw, span in extract_year_ranges(text):
        if range_overlaps_target(start, end):
            term = _nearby_token(text, span, terms, max_distance)
            locality = _nearby_token(text, span, localities, max_distance)
            if term:
                ev = TemporalEvidence("coverage_year_range", raw, None, start, end, term, locality)
                ev.target_date_basis = "collection_coverage_date"
                ev.confidence = score_temporal_confidence(ev)
                return ev
    for raw, start, end, span in extract_decades(text):
        if range_overlaps_target(start, end):
            term = _nearby_token(text, span, terms, max_distance)
            locality = _nearby_token(text, span, localities, max_distance)
            if term:
                ev = TemporalEvidence("decade_near_term", raw, None, start, min(end, TARGET_END), term, locality)
                ev.target_date_basis = "narrative_date"
                ev.confidence = score_temporal_confidence(ev)
                return ev
    for match in YEAR_RE.finditer(text):
        year = int(match.group(1))
        if not year_in_target_range(year):
            continue
        term = _nearby_token(text, match.span(), terms, max_distance)
        locality = _nearby_token(text, match.span(), localities, max_distance)
        if term:
            ev = TemporalEvidence("narrative_year", match.group(1), year, year, year, term, locality)
            ev.target_date_basis = "narrative_date"
            ev.confidence = score_temporal_confidence(ev)
            return ev
    return TemporalEvidence(reason="no_target_year_near_controlled_term")


def _metadata_text(metadata: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in [
        "publication_year",
        "source_publication_year",
        "item_date",
        "coverage",
        "title",
        "name",
        "headline",
        "description",
        "record_publication_date",
        "record_publication_year",
        "coverage_start_year",
        "coverage_end_year",
        "narrative_date_text",
        "collection_coverage_date_text",
    ]:
        value = metadata.get(key)
        if value is not None:
            parts.append(str(value))
    return " ".join(parts)


def classify_target_date_basis(text: str, metadata: dict[str, Any] | None, terms: list[str], localities: list[str]) -> TemporalEvidence:
    metadata = metadata or {}
    publication_keys = ["record_publication_year", "record_publication_date", "source_publication_year", "publication_year", "item_date"]
    if str(metadata.get("date_is_record_publication") or "").lower() in {"1", "true", "yes"}:
        publication_keys.extend(["date", "date_published", "published"])
    for key in publication_keys:
        value = metadata.get(key)
        if value is None:
            continue
        years = extract_years(str(value))
        for year in years:
            if year_in_target_range(year):
                term_text = " ".join([str(metadata.get("title") or ""), str(metadata.get("name") or ""), str(metadata.get("description") or ""), text or ""])
                term = _nearby_token(term_text, (0, 0), terms, 100000) or _nearby_token(text or "", (0, 0), terms, 100000)
                ev = TemporalEvidence("record_publication_date", str(value), year, year, year, term, _nearby_token(term_text, (0, 0), localities, 100000))
                ev.target_date_basis = "record_publication_date"
                ev.confidence = score_temporal_confidence(ev)
                return ev
    coverage_text = " ".join(str(metadata.get(key) or "") for key in ["collection_coverage_date_text", "coverage", "coverage_start_year", "coverage_end_year"])
    coverage_ev = classify_temporal_evidence(coverage_text, terms, localities)
    if coverage_ev.confidence >= 0.7:
        coverage_ev.evidence_type = "coverage_year_range" if coverage_ev.coverage_start_year != coverage_ev.coverage_end_year else "collection_item_date"
        coverage_ev.target_date_basis = "collection_coverage_date"
        coverage_ev.confidence = max(coverage_ev.confidence, 0.8)
        return coverage_ev
    narrative_text = " ".join([str(metadata.get("narrative_date_text") or ""), text or ""])
    narrative_ev = classify_temporal_evidence(narrative_text, terms, localities)
    if narrative_ev.confidence >= 0.7:
        narrative_ev.evidence_type = "narrative_date" if narrative_ev.evidence_type == "narrative_year" else narrative_ev.evidence_type
        narrative_ev.target_date_basis = "narrative_date"
        return narrative_ev
    return TemporalEvidence(reason="no_explicit_target_temporal_evidence", target_date_basis="none")


def best_temporal_evidence(text: str, metadata: dict[str, Any] | None, terms: list[str], localities: list[str]) -> TemporalEvidence:
    metadata = metadata or {}
    basis_ev = classify_target_date_basis(text, metadata, terms, localities)
    if basis_ev.confidence >= 0.7:
        return basis_ev
    meta_text = _metadata_text(metadata)
    # Modern page publication dates are intentionally ignored unless the caller
    # mapped them into record_publication_* metadata or set date_is_record_publication.
    meta_ev = classify_temporal_evidence(meta_text, terms, localities)
    if meta_ev.confidence >= 0.7:
        if meta_ev.evidence_type == "narrative_year":
            meta_ev.evidence_type = "collection_item_date"
        meta_ev.confidence = max(meta_ev.confidence, 0.8)
        return meta_ev
    return classify_temporal_evidence(text or "", terms, localities)
