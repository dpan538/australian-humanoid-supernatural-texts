import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("temporal_evidence_test", scripts / "lib/temporal_evidence.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_exact_year_near_ghost_passes_and_1984_fails():
    t = load()
    ev = t.classify_temporal_evidence("In 1956 a ghost was reported near the hotel.", ["ghost"], [])
    assert ev.extracted_year == 1956
    assert ev.confidence >= 0.7
    bad = t.classify_temporal_evidence("In 1984 a ghost was reported near the hotel.", ["ghost"], [])
    assert bad.confidence == 0


def test_decade_near_haunted_hotel_passes_and_vague_century_fails():
    t = load()
    ev = t.classify_temporal_evidence("A 1960s haunted hotel story from Port Adelaide.", ["haunted hotel"], ["Port Adelaide"])
    assert ev.evidence_type == "decade_near_term"
    assert ev.coverage_start_year == 1960
    bad = t.classify_temporal_evidence("A 20th century haunted hotel story.", ["haunted hotel"], [])
    assert bad.confidence == 0


def test_query_plan_year_alone_and_modern_page_date_do_not_count():
    t = load()
    ev = t.best_temporal_evidence("Query target 1960 Kalgoorlie local history", {"date_published": "2024-01-01", "title": "Search"}, ["ghost"], [])
    assert ev.confidence == 0
    item = t.best_temporal_evidence("Ghost article", {"item_date": "1959", "title": "Ghost article"}, ["ghost"], [])
    assert item.extracted_year == 1959
