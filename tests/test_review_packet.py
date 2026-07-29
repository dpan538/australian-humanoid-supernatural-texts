import csv
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_packet():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "make_review_packet.py"
    spec = importlib.util.spec_from_file_location("make_review_packet", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_review_packet_writes_expected_files_and_fields():
    packet = load_packet()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db_path = tmp_path / "test.sqlite"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                CREATE TABLE collection_candidates (
                    candidate_id TEXT, run_id TEXT, target_state TEXT, time_band TEXT,
                    source_name TEXT, term_family TEXT, title TEXT, date_published TEXT,
                    publication TEXT, url TEXT, snippet TEXT, query_string TEXT,
                    evidence_or_discovery TEXT, source_tier TEXT, mappability_hint TEXT,
                    duplicate_key TEXT, review_status TEXT, source_stated_place_text TEXT,
                    location_role TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO collection_candidates VALUES (
                    'cand_1', 'run_1', 'WA', '1940_1954', 'Trove', 'apparition_ghost',
                    'Ghost story', '1941', 'Test Paper', 'https://example.test',
                    'snippet', 'ghost AND Perth', 'evidence_possible', 'A',
                    'medium', 'dup', 'needs_review', 'Perth', ''
                )
                """
            )
            conn.commit()
        finally:
            conn.close()
        out_dir = tmp_path / "packet"
        summary = packet.make_packet(db_path, "run_1", out_dir, 10)
        assert summary["candidates"] == 1
        for name in ["candidate_review.csv", "candidate_review.md", "source_chain_review.csv", "geocode_review.csv", "summary.md"]:
            assert (out_dir / name).exists()
        with (out_dir / "candidate_review.csv").open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            assert "accepted_evidence_source_name" in reader.fieldnames
            assert "reviewer_notes" in reader.fieldnames
