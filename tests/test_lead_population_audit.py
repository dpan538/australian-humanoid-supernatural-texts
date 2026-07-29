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


def insert_lead(conn, lead_id, lead_type, **values):
    row = {
        "lead_id": lead_id,
        "lead_type": lead_type,
        "title": values.get("title", "Ghost lead"),
        "url": values.get("url", ""),
        "route_family": values.get("route_family", ""),
        "source_family": values.get("source_family", ""),
        "source_tier": values.get("source_tier", "A"),
        "target_state": values.get("target_state", "WA"),
        "temporal_signal": values.get("temporal_signal", ""),
        "term_signal": values.get("term_signal", ""),
        "evidence_gap": values.get("evidence_gap", ""),
        "constraint_blocker": values.get("constraint_blocker", ""),
        "priority_bucket": values.get("priority_bucket", ""),
        "lead_score": values.get("lead_score", 0),
        "created_at": "now",
        "updated_at": "now",
    }
    fields = list(row)
    conn.execute(f"INSERT INTO target_gap_leads ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})", tuple(row[field] for field in fields))


def test_lead_population_audit_counts_segments_without_public_mutation():
    mod = load("lead_population_audit_mod", "audit_target_gap_lead_population.py")
    mig = load("lead_population_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE public_records (id TEXT)")
            conn.execute("INSERT INTO public_records VALUES ('keep')")
            insert_lead(conn, "p", "ITEM_DETAIL_REQUIRED_LEAD", temporal_signal="1935", term_signal="ghost", priority_bucket="PRIORITY_LEAD", url="https://example.org/item")
            insert_lead(conn, "r", "SOURCE_ATLAS_ROUTE_LEAD", constraint_blocker="missing_date", evidence_gap="missing_date")
            insert_lead(conn, "b", "ROBOTS_BLOCKED_NEAR_MISS", constraint_blocker="robots_unknown", evidence_gap="robots_unknown")
            insert_lead(conn, "d", "ACCESS_PLATFORM_DECOMPOSITION_LEAD", source_tier="D", evidence_gap="d_class_needs_original", constraint_blocker="d_class_needs_original")
            conn.commit()
        summary = mod.audit(db, tmp_path / "audit")
        with sqlite3.connect(db) as conn:
            public_count = conn.execute("SELECT COUNT(*) FROM public_records").fetchone()[0]
        assert summary["total_leads"] == 4
        assert summary["priority_leads"] == 1
        assert public_count == 1
        text = (tmp_path / "audit" / "lead_population_audit.md").read_text()
        assert "source_route_lead" in text
        assert "robots_permission_lead" in text
        assert "source_chain_remediation_lead" in text
