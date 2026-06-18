from aus_humanoid.normalise import (
    canonicalise_whitespace,
    normalise_alias,
    normalise_text,
    parse_year,
    slugify,
)


def test_canonicalise_whitespace_collapses_runs():
    assert canonicalise_whitespace("  Yowie\n\n  Bay\tnoise  ") == "Yowie Bay noise"


def test_normalise_text_casefolds_and_replaces_quotes():
    assert normalise_text("  \u201cHairy Man\u201d  ") == '"hairy man"'


def test_normalise_alias_matches_text_normalisation():
    assert normalise_alias("YARA-MA-YHA-WHO") == "yara-ma-yha-who"


def test_slugify_is_ascii_and_stable():
    assert slugify("Hairy Man of the Wood!") == "hairy-man-of-the-wood"


def test_parse_year_from_loose_dates():
    assert parse_year("12 March 1897") == 1897
    assert parse_year("c. 1974") == 1974
    assert parse_year("") is None

