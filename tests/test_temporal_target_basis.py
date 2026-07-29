import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("temporal_basis_test", scripts / "lib/temporal_evidence.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_record_publication_narrative_and_coverage_basis_qualify():
    t = load()
    record = t.best_temporal_evidence("ghost article", {"record_publication_year": "1964", "title": "ghost article"}, ["ghost"], [])
    narrative = t.best_temporal_evidence("The ghost was reported in 1964.", {"title": "modern page"}, ["ghost"], [])
    coverage = t.best_temporal_evidence("Ghost stories", {"collection_coverage_date_text": "1955-1969", "title": "Ghost stories"}, ["ghost"], [])
    assert record.target_date_basis == "record_publication_date"
    assert narrative.target_date_basis == "narrative_date"
    assert coverage.target_date_basis == "collection_coverage_date"


def test_modern_page_date_and_query_date_do_not_qualify():
    t = load()
    modern = t.best_temporal_evidence("museum page about a ghost", {"date_published": "2024", "title": "ghost"}, ["ghost"], [])
    query = t.best_temporal_evidence("query 1964 target state", {"title": "search"}, ["ghost"], [])
    assert modern.confidence == 0
    assert query.confidence == 0
