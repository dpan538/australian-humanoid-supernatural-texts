import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, rel):
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(name, scripts / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_clusters_by_route_robots_dclass_and_metadata():
    mod = load("cluster_leads_mod", "cluster_target_gap_leads.py")
    mig = load("lead_migrate_cluster", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            rows = [
                ("l1", "ITEM_DETAIL_REQUIRED_LEAD", "https://example.org/a", "A", "WA", "state_library_catalogue", "robots_unknown", "robots_unknown", 80),
                ("l2", "ACCESS_PLATFORM_DECOMPOSITION_LEAD", "https://archive.example/a", "D", "WA", "access", "d_class_needs_original", "d_class_needs_original", 50),
                ("l3", "METADATA_ONLY_1955_1976_LEAD", "https://meta.example/a", "A", "SA", "broadcast_catalogue", "missing_term", "", 70),
            ]
            for row in rows:
                conn.execute("INSERT INTO target_gap_leads (lead_id, lead_type, url, source_tier, target_state, route_family, evidence_gap, constraint_blocker, lead_score, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,'now','now')", row)
            conn.commit()
        summary = mod.cluster(db, tmp_path / "clusters.md", True)
        assert summary["clusters"] >= 3
        assert (tmp_path / "top_route_clusters.csv").exists()
        assert (tmp_path / "top_robots_blocked_clusters.csv").exists()
        assert (tmp_path / "top_d_class_clusters.csv").exists()
        assert (tmp_path / "top_metadata_only_1955_1976_clusters.csv").exists()
