"""Text normalisation utilities used by ingestion, matching, and tests."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

try:
    from dateutil import parser as date_parser
except Exception:  # pragma: no cover - dateutil is a declared dependency.
    date_parser = None


WHITESPACE_RE = re.compile(r"\s+")
YEAR_RE = re.compile(r"\b(1[7-9]\d{2}|20\d{2})\b")
SLUG_RE = re.compile(r"[^a-z0-9]+")

REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
}


def canonicalise_whitespace(s: Any) -> str:
    """Collapse repeated whitespace and trim leading/trailing space."""

    if s is None:
        return ""
    return WHITESPACE_RE.sub(" ", str(s)).strip()


def normalise_text(s: Any) -> str:
    """Return a case-folded, Unicode-normalised, whitespace-normalised string."""

    if s is None:
        return ""
    text = unicodedata.normalize("NFKC", str(s))
    for old, new in REPLACEMENTS.items():
        text = text.replace(old, new)
    return canonicalise_whitespace(text.casefold())


def normalise_alias(s: Any) -> str:
    """Normalise an alias for lookup or comparison."""

    return normalise_text(s)


def slugify(s: Any, fallback: str = "item") -> str:
    """Create a conservative ASCII slug suitable for filenames."""

    text = unicodedata.normalize("NFKD", normalise_text(s))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    slug = SLUG_RE.sub("-", text).strip("-")
    return slug or fallback


def parse_year(date_string: Any) -> int | None:
    """Extract a plausible year from a loose date string."""

    if date_string is None:
        return None
    if isinstance(date_string, int):
        return date_string if 1700 <= date_string <= 2100 else None
    text = str(date_string).strip()
    if not text:
        return None
    match = YEAR_RE.search(text)
    if match:
        return int(match.group(1))
    if date_parser is not None:
        try:
            parsed = date_parser.parse(text, fuzzy=True, default=None)
        except Exception:
            return None
        if parsed and 1700 <= parsed.year <= 2100:
            return parsed.year
    return None

