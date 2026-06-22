import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = ROOT / "public" / "data" / "frontend-data.json"


def load_frontend_data():
    return json.loads(FRONTEND_DATA.read_text(encoding="utf-8"))


def test_public_map_has_one_flag_per_eligible_record():
    data = load_frontend_data()
    summary = data["summary"]
    map_flags = data["map_flags"]
    map_points = data["map_points"]
    flag_record_ids = [int(flag["record_id"]) for flag in map_flags]
    point_record_ids = [int(point["record_id"]) for point in map_points]

    assert len(flag_record_ids) == len(set(flag_record_ids))
    assert len(point_record_ids) == len(set(point_record_ids))
    assert set(flag_record_ids) == set(point_record_ids)
    assert summary["map_flag_count"] == len(map_flags)
    assert summary["mapped_record_count"] == len(map_points)
    assert summary["mapped_record_count"] == len(set(flag_record_ids))


def test_frontend_record_ids_are_unique():
    data = load_frontend_data()
    record_ids = [int(record["record_id"]) for record in data["records"]]
    assert len(record_ids) == len(set(record_ids))
