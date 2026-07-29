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


def insert_lead(conn, lead_id, **values):
    fields = ["lead_id", "lead_type", "title", "url", "source_tier", "target_state", "route_family", "temporal_signal", "term_signal", "evidence_gap", "constraint_blocker", "ethics_status", "created_at", "updated_at"]
    row = {field: "" for field in fields}
    row.update({"lead_id": lead_id, "lead_type": "ITEM_DETAIL_REQUIRED_LEAD", "created_at": "now", "updated_at": "now"})
    row.update(values)
    conn.execute(f"INSERT INTO target_gap_leads ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})", tuple(row[field] for field in fields))


def test_lead_scoring_buckets_and_penalties():
    mod = load("score_leads_mod", "score_target_gap_leads.py")
    mig = load("lead_migrate_score", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            insert_lead(conn, "high", title="Ghost 1935", url="https://example.org/item", source_tier="A", target_state="WA", route_family="state_library_catalogue", temporal_signal="1935", term_signal="ghost")
            insert_lead(conn, "robot", title="Robots", url="https://example.org/item", source_tier="A", temporal_signal="1935", term_signal="ghost", evidence_gap="robots_denied", constraint_blocker="robots_denied")
            insert_lead(conn, "dclass", title="D", url="https://example.org/item", source_tier="D", temporal_signal="1935", term_signal="ghost", evidence_gap="d_class_needs_original", constraint_blocker="d_class_needs_original")
            insert_lead(conn, "sens", title="Sensitive", url="https://example.org/item", source_tier="A", temporal_signal="1935", term_signal="ghost", ethics_status="sensitive")
            insert_lead(conn, "qld", title="Ghost 1935", url="https://example.org/qld", target_state="QLD", temporal_signal="1935", term_signal="ghost")
            conn.commit()
        summary = mod.score(db, tmp_path / "score.md", True)
        with sqlite3.connect(db) as conn:
            rows = {row[0]: (row[1], row[2]) for row in conn.execute("SELECT lead_id, lead_score, priority_bucket FROM target_gap_leads").fetchall()}
        assert rows["high"][1] == "PRIORITY_LEAD"
        assert rows["robot"][1] == "BLOCKED_ROBOTS"
        assert rows["dclass"][0] < rows["high"][0]
        assert rows["sens"][1] == "SENSITIVE_HOLD"
        assert rows["high"][0] > rows["qld"][0]
        assert summary["priority_leads"] >= 1
