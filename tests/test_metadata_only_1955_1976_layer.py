import csv
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


def insert(conn, lead_id, **values):
    row = {
        "lead_id": lead_id,
        "lead_type": "ITEM_DETAIL_REQUIRED_LEAD",
        "title": values.get("title", "Lead"),
        "url": values.get("url", "https://example.org/item"),
        "source_tier": values.get("source_tier", "A"),
        "route_family": values.get("route_family", "state_library_catalogue"),
        "target_state": values.get("target_state", "WA"),
        "target_locality": values.get("target_locality", "Albany"),
        "inferred_year": values.get("inferred_year", 1964),
        "temporal_signal": values.get("temporal_signal", "1964"),
        "term_signal": values.get("term_signal", ""),
        "constraint_blocker": values.get("constraint_blocker", ""),
        "evidence_gap": values.get("evidence_gap", ""),
        "ethics_status": values.get("ethics_status", ""),
        "created_at": "now",
        "updated_at": "now",
    }
    fields = list(row)
    conn.execute(f"INSERT INTO target_gap_leads ({', '.join(fields)}) VALUES ({', '.join(['?'] * len(fields))})", tuple(row[field] for field in fields))


def test_metadata_only_1955_1976_classifications_and_sensitive_exclusion():
    mod = load("metadata_layer_mod", "build_metadata_only_1955_1976_layer.py")
    mig = load("metadata_layer_migrate", "migrate_target_gap_leads_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            insert(conn, "strong", term_signal="ghost")
            insert(conn, "route", url="", term_signal="")
            insert(conn, "robots", term_signal="yowie", constraint_blocker="robots_unknown", evidence_gap="robots_unknown")
            insert(conn, "sensitive", term_signal="ghost", ethics_status="sensitive")
            conn.commit()
        summary = mod.build_layer(db, tmp_path / "metadata", True)
        with (tmp_path / "metadata" / "metadata_only_1955_1976_leads.csv").open() as handle:
            rows = {row["lead_id"]: row["metadata_only_classification"] for row in csv.DictReader(handle)}
        assert summary["metadata_only_leads"] == 3
        assert rows["strong"] == "METADATA_ONLY_STRONG"
        assert rows["route"] == "METADATA_ONLY_ROUTE_LEAD"
        assert rows["robots"] == "METADATA_ONLY_ROBOTS_BLOCKED"
        assert "sensitive" not in rows
