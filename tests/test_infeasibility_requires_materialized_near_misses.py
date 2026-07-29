import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location("infeasibility_materialized_mod", scripts / "no_credential_infeasibility_report.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def add_structured_near_record(conn, run_id):
    conn.execute(
        """
        INSERT INTO noauth_endpoint_records (
            endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type,
            item_url, title, inferred_year, controlled_term_hits, target_gap_eligible, created_at
        )
        VALUES ('r1', ?, 'ep', 'Source', 'A', 'RSS_ATOM', 'https://example.org/item', 'Archive item', 1935, '[]', 0, 'now')
        """,
        (run_id,),
    )


def test_status_observability_incomplete_when_reported_near_misses_not_materialized():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        run_id = "run"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            add_structured_near_record(conn, run_id)
            conn.commit()
        summary = mod.report(db, run_id, tmp_path / "missing.md", tmp_path / "checkpoint.md", tmp_path / "out.md")
        text = (tmp_path / "out.md").read_text(encoding="utf-8")
        assert summary["status"] == "observability_incomplete"
        assert summary["declare_infeasible"] is False
        assert "observability_incomplete" in text


def test_infeasibility_requires_robots_rescue_after_enrichment_attempted():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        run_id = "run"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            add_structured_near_record(conn, run_id)
            conn.execute(
                """
                INSERT INTO structured_endpoint_near_misses (
                    near_miss_id, run_id, source_name, source_tier, endpoint_type,
                    item_url, title, near_miss_type, recoverability_score,
                    recovery_status, enrichment_attempted, created_at, updated_at
                )
                VALUES ('n1', ?, 'Source', 'A', 'RSS_ATOM', 'https://example.org/item',
                        'Archive item', 'RSS_ITEM_DETAIL_REQUIRED', 90, 'enriched_near_miss', 1, 'now', 'now')
                """,
                (run_id,),
            )
            conn.execute(
                """
                INSERT INTO structured_endpoint_enriched_records (
                    enriched_record_id, run_id, near_miss_id, source_name, source_tier,
                    endpoint_type, item_url, title, target_gap_eligible, created_at
                )
                VALUES ('e1', ?, 'n1', 'Source', 'A', 'RSS_ATOM', 'https://example.org/item',
                        'Archive item', 0, 'now')
                """,
                (run_id,),
            )
            conn.commit()
        summary = mod.report(db, run_id, tmp_path / "missing.md", tmp_path / "checkpoint.md", tmp_path / "out.md")
        assert summary["status"] == "robots_rescue_incomplete"
        assert summary["declare_infeasible"] is False
