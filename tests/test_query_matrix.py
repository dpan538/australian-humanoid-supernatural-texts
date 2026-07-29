import importlib.util
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generates_queries_for_every_time_band_state_and_term_family():
    builder = load_module("build_gap_query_matrix")
    common = load_module("collection_expansion_common")
    matrix = yaml.safe_load((ROOT / "config" / "query_matrix_1926_1976.yml").read_text())
    registry = common.load_registry(ROOT / "config" / "source_registry.yml")
    targets = yaml.safe_load((ROOT / "config" / "collection_targets.yml").read_text())
    rows = builder.build_queries(matrix, registry, targets)
    assert rows
    assert {row["time_band"] for row in rows} == {band["id"] for band in matrix["time_bands"]}
    assert {row["target_state"] for row in rows} >= set(matrix["states"])
    assert {row["term_family"] for row in rows} >= {"humanoid_hairy", "apparition_ghost", "named_local_legend"}


def test_priority_states_come_before_nsw_qld_vic():
    builder = load_module("build_gap_query_matrix")
    common = load_module("collection_expansion_common")
    matrix = yaml.safe_load((ROOT / "config" / "query_matrix_1926_1976.yml").read_text())
    registry = common.load_registry(ROOT / "config" / "source_registry.yml")
    targets = yaml.safe_load((ROOT / "config" / "collection_targets.yml").read_text())
    rows = builder.build_queries(matrix, registry, targets)
    first_states = []
    for row in rows:
        if row["target_state"] not in first_states:
            first_states.append(row["target_state"])
    assert first_states[:5] == ["ACT", "NT", "SA", "TAS", "WA"]
    assert all(first_states.index(state) < first_states.index("NSW") for state in ["ACT", "NT", "SA", "TAS", "WA"])


def test_multi_word_terms_are_quoted():
    common = load_module("collection_expansion_common")
    query = common.make_query("haunted hotel", "Kalgoorlie", "WA", 1940, 1954, trove=True)
    assert '"haunted hotel"' in query
    assert "Kalgoorlie" in query
    assert "date:[1940-01-01T00:00:00Z TO 1954-12-31T23:59:59Z]" in query


def test_sensitive_term_families_get_manual_sensitive_review():
    builder = load_module("build_gap_query_matrix")
    common = load_module("collection_expansion_common")
    matrix = yaml.safe_load((ROOT / "config" / "query_matrix_1926_1976.yml").read_text())
    registry = common.load_registry(ROOT / "config" / "source_registry.yml")
    targets = yaml.safe_load((ROOT / "config" / "collection_targets.yml").read_text())
    rows = builder.build_queries(matrix, registry, targets)
    sensitive_rows = [row for row in rows if row["term_family"] == "named_local_legend"]
    assert sensitive_rows
    assert {row["review_mode"] for row in sensitive_rows} == {"manual_sensitive_review"}
