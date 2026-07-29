import csv
import importlib.util
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_reconcile():
    scripts = ROOT / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "reconcile_canonical_counts.py"
    spec = importlib.util.spec_from_file_location("reconcile_canonical_counts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_partition_explains_frontend_internal_difference():
    reconcile = load_reconcile()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        db = tmp_path / "test.sqlite"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE legacy_record_mappings (legacy_record_id TEXT, narrative_id TEXT)")
        conn.execute("CREATE TABLE narrative_units (narrative_id TEXT, display_mode TEXT, analysis_status TEXT, narrative_status TEXT)")
        conn.execute("CREATE TABLE geocode_review_queue (narrative_unit_id TEXT)")
        for i in range(1, 8):
            conn.execute("INSERT INTO legacy_record_mappings VALUES (?, ?)", (str(i), str(i)))
            mode = "suppressed" if i == 7 else "full"
            conn.execute("INSERT INTO narrative_units VALUES (?, ?, '', '')", (str(i), mode))
        conn.execute("INSERT INTO geocode_review_queue VALUES ('6')")
        conn.commit()
        conn.close()
        exports = tmp_path / "exports"
        exports.mkdir()
        fields = ["narrative_location_id", "narrative_id", "location_id", "location_role", "location_precision", "latitude", "longitude", "review_status"]
        with (exports / "narrative_locations_review.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for i in range(1, 8):
                writer.writerow(
                    {
                        "narrative_location_id": str(i),
                        "narrative_id": str(i),
                        "location_id": str(i),
                        "location_role": "reported_place",
                        "location_precision": "locality",
                        "latitude": -30.0,
                        "longitude": 120.0 + i,
                        "review_status": "reviewed",
                    }
                )
        frontend = [{"record_id": str(i), "latitude": -30.0, "longitude": 120.0 + i} for i in range(1, 4)]
        partitions = reconcile.partition_mapped_like(db, exports, frontend)
        counts = {row["partition_label"]: 0 for row in partitions}
        for row in partitions:
            counts[row["partition_label"]] += 1
        assert counts["FRONTEND_PUBLIC_MAP"] == 3
        assert counts["INTERNAL_LOCATION_ROW"] == 2
        assert counts["GEOCODE_REVIEW_ROW"] == 1
        assert counts["SUPPRESSED_LOCATION_ROW"] == 1
        resolved, _ = reconcile.conflict_resolved(3, 7, partitions, {"frontend_map_file": "public/data/frontend-data.json"})
        assert resolved is True
