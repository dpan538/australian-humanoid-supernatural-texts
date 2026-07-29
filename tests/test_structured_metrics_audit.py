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
    spec = importlib.util.spec_from_file_location("structured_metrics_audit_mod", scripts / "audit_structured_endpoint_metrics.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_metrics_audit_detects_mismatches_and_unmaterialized_near_misses():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        base = tmp_path / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
        base.mkdir(parents=True)
        run_id = "run"
        (base / "endpoint_discovery_report.md").write_text("- Endpoints discovered: `1`\n- Endpoints rejected: `2`\n", encoding="utf-8")
        (base / "structured_endpoint_query_plan.md").write_text("- Query rows generated: `3`\n", encoding="utf-8")
        (base / f"{run_id}_operator_summary.md").write_text("- Endpoint queries generated: `1`\n- High-quality near misses: `1`\n", encoding="utf-8")
        (base / f"{run_id}_checkpoint.md").write_text("- Queries attempted: `2`\n- Queries queued: `0`\n- Endpoint records seen: `1`\n- Target-gap raw records: `0`\n- High-quality near misses: `1`\n", encoding="utf-8")
        (base / f"{run_id}_structured_endpoint_target_records.csv").write_text("id\n", encoding="utf-8")
        (base / f"{run_id}_structured_endpoint_near_misses.csv").write_text("id\n", encoding="utf-8")
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, endpoint_url, endpoint_type, status, discovered_at) VALUES ('ep','https://example.org','ATOM_AtoM','active','now')")
            for idx, status in enumerate(["attempted", "attempted", "queued"], start=1):
                conn.execute("INSERT INTO noauth_endpoint_queries (endpoint_query_id, run_id, endpoint_id, query_text, status, created_at) VALUES (?,?,?,?,?,?)", (f"q{idx}", run_id, "ep", "ghost", status, "now"))
            conn.execute(
                "INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, endpoint_query_id, source_name, source_tier, endpoint_type, item_url, title, inferred_year, controlled_term_hits, target_gap_eligible, created_at) VALUES ('r1',?,?,?,?,?,?,?,?,?,?,0,'now')",
                (run_id, "ep", "q1", "Museum", "A", "ATOM_AtoM", "https://example.org/item", "Ghost", 1935, "[]"),
            )
            conn.execute("INSERT INTO noauth_endpoint_route_stats (run_id, endpoint_id, endpoint_type, source_name, queries_attempted, records_seen, near_misses, updated_at) VALUES (?,?,?,?,?,?,?,?)", (run_id, "ep", "ATOM_AtoM", "Museum", 5, 5, 4, "now"))
            conn.commit()
        summary = mod.audit(db, run_id, tmp_path / "audit")
        text = (tmp_path / "audit" / "structured_endpoint_metrics_audit.md").read_text(encoding="utf-8")
        csv_text = (tmp_path / "audit" / "structured_endpoint_metrics_audit.csv").read_text(encoding="utf-8")
        assert summary["near_record_level"] == 1
        assert "BUG_NEAR_MISS_NOT_MATERIALIZED" in csv_text
        assert "BUG_ROUTE_STATS_CUMULATIVE_MISMATCH" in csv_text
        assert "BUG_QUERY_COUNT_MISMATCH" in csv_text
        assert "Which count should be canonical?" in text
