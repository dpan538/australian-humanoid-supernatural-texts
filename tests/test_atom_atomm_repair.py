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


def test_atom_atomm_repair_flags_navigation_anchor_noise():
    mod = load("atom_repair_mod", "repair_atom_atomm_adapter.py")
    mig = load("mig_atom_repair", "migrate_structured_near_miss_v1.py")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        mig.migrate(db)
        with sqlite3.connect(db) as conn:
            conn.execute("INSERT INTO noauth_endpoint_inventory (endpoint_id, source_name, source_tier, endpoint_url, endpoint_type, domain, status, discovered_at) VALUES ('ep','Western Australian Museum','A','https://museum.wa.gov.au/index.php/informationobject/browse','ATOM_AtoM','museum.wa.gov.au','active','now')")
            conn.execute("INSERT INTO noauth_endpoint_records (endpoint_record_id, run_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, metadata_json, target_gap_eligible, created_at) VALUES ('r1','run','ep','Western Australian Museum','A','ATOM_AtoM','https://museum.wa.gov.au/index.php/informationobject/browse','Skip to Navigation','{\"anchor\":\"Skip to Navigation\"}', 0, 'now')")
            conn.execute("INSERT INTO structured_endpoint_near_misses (near_miss_id, run_id, endpoint_record_id, endpoint_id, source_name, source_tier, endpoint_type, item_url, title, near_miss_type, recoverability_score, recovery_status, detail_url, created_at, updated_at) VALUES ('n1','run','r1','ep','Western Australian Museum','A','ATOM_AtoM','https://museum.wa.gov.au/index.php/informationobject/browse','Skip to Navigation','AtoM_DETAIL_REQUIRED',90,'queued','https://museum.wa.gov.au/index.php/informationobject/browse','now','now')")
            conn.commit()
        summary = mod.repair_atom(db, "run", tmp_path / "atom", True)
        assert summary["diagnosis"]["anchor_navigation_noise"] == 1
        assert summary["target_gap_records"] == 0
        assert "filter accessibility/navigation anchors" in (tmp_path / "atom" / "atom_atomm_adapter_patch_notes.md").read_text()
