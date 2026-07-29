import csv
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
    spec = importlib.util.spec_from_file_location("infeasibility_robots_mod", scripts / "no_credential_infeasibility_report.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_infeasibility_status_robots_rescue_incomplete_without_rescue_artifacts():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, inferred_year, target_gap_eligible, created_at) VALUES ('r1','run','ep','Source','A','RSS_ATOM','https://example.org/item','Archive item',1935,0,'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, enrichment_attempted, created_at, updated_at) VALUES ('n1','run','Source','A','RSS_ATOM','https://example.org/item','Archive item','RSS_ITEM_DETAIL_REQUIRED',90,'enriched_near_miss',1,'now','now')")
            conn.commit()
        summary = mod.report(db, "run", tmp_path / "missing.md", tmp_path / "checkpoint.md", tmp_path / "out.md")
        assert summary["status"] == "robots_rescue_incomplete"
        assert summary["declare_infeasible"] is False


def test_infeasibility_status_robots_uncertainty_blocked_when_unknown_dominates():
    mod = load()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mod.ROOT = tmp_path
        db = tmp_path / "test.sqlite"
        mod.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, inferred_year, target_gap_eligible, created_at) VALUES ('r1','run','ep','Source','A','RSS_ATOM','https://example.org/item','Archive item',1935,0,'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, enrichment_attempted, created_at, updated_at) VALUES ('n1','run','Source','A','RSS_ATOM','https://example.org/item','Archive item','RSS_ITEM_DETAIL_REQUIRED',90,'enriched_near_miss',1,'now','now')")
            conn.commit()
        structured = tmp_path / "data" / "processed" / "v2" / "autoharvest" / "structured_endpoints"
        review = tmp_path / "data" / "review" / "v2" / "autoharvest" / "structured_endpoints"
        robots_dir = structured / "robots_block_audit"
        robots_dir.mkdir(parents=True, exist_ok=True)
        with (robots_dir / "robots_block_audit.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["robots_status", "url_issue"])
            writer.writeheader()
            writer.writerow({"robots_status": "ROBOTS_UNKNOWN_MISSING_ROBOTS", "url_issue": ""})
        review.mkdir(parents=True, exist_ok=True)
        (review / "existing_metadata_enrichment_candidates.csv").write_text("near_miss_id\nn1\n")
        (structured / "atom_atomm_repair").mkdir(parents=True, exist_ok=True)
        (structured / "atom_atomm_repair" / "atom_atomm_enriched_records.csv").write_text("near_miss_id\n")
        (structured / "rss_inline_enrichment").mkdir(parents=True, exist_ok=True)
        (structured / "rss_inline_enrichment" / "rss_inline_near_misses_remaining.csv").write_text("near_miss_id\n")
        (structured / "allowed_detail_alternatives.csv").write_text("near_miss_id,safe_to_fetch\nn1,false\n")
        summary = mod.report(db, "run", tmp_path / "missing.md", tmp_path / "checkpoint.md", tmp_path / "out.md")
        assert summary["status"] == "robots_uncertainty_blocked"
        assert summary["declare_infeasible"] is False
