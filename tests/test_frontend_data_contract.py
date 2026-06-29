import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DATA = ROOT / "public" / "data" / "frontend-data.json"
TIME_PERIOD_CONFIG = ROOT / "config" / "time_periods.json"
ACTIVE_FRONTEND_COMPONENTS = [
    ROOT / "components" / "archive-terminal.tsx",
]


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


def main_date_bands(data):
    return [band for band in data["date_bands"] if band["id"] != "undated"]


def test_public_record_date_bands_are_six_contiguous_periods():
    data = load_frontend_data()
    bands = main_date_bands(data)

    assert len(bands) == 6
    for previous, current in zip(bands, bands[1:]):
        assert previous["end"] + 1 == current["start"]
        assert previous["end"] < current["end"]
    assert bands[0]["start"] == data["summary"]["earliest_year"]
    assert bands[-1]["end"] == data["summary"]["latest_year"]


def test_every_dated_public_record_maps_to_one_main_date_band():
    data = load_frontend_data()
    bands = main_date_bands(data)
    band_ids = {band["id"] for band in bands}
    dated_records = [record for record in data["records"] if record.get("year") is not None]

    assert dated_records
    assert all(record["date_band"] in band_ids for record in dated_records)
    for record in dated_records:
        matches = [
            band
            for band in bands
            if band["start"] <= record["year"] <= band["end"] and record["date_band"] == band["id"]
        ]
        assert len(matches) == 1


def test_summary_year_bounds_match_public_records():
    data = load_frontend_data()
    years = [record["year"] for record in data["records"] if record.get("year") is not None]

    assert data["summary"]["earliest_year"] == min(years)
    assert data["summary"]["latest_year"] == max(years)


def test_date_band_counts_reconcile_with_records_and_undated():
    data = load_frontend_data()
    bands = main_date_bands(data)
    dated_records = [record for record in data["records"] if record.get("year") is not None]
    undated_records = [record for record in data["records"] if record.get("year") is None]

    assert sum(int(band["record_count"]) for band in bands) == len(dated_records)
    assert data["summary"].get("dated_record_count") == len(dated_records)
    assert data["summary"].get("undated_record_count") == len(undated_records)
    for band in bands:
        expected = sum(1 for record in dated_records if record["date_band"] == band["id"])
        assert band["record_count"] == expected
        assert band["span_years"] == band["end"] - band["start"] + 1
        assert band["records_per_year"] == expected / band["span_years"]


def test_attention_windows_are_not_public_record_date_bands():
    data = load_frontend_data()
    config = json.loads(TIME_PERIOD_CONFIG.read_text(encoding="utf-8"))
    attention_ids = {window["id"] for window in config["attention_windows"]}
    band_ids = {band["id"] for band in data["date_bands"]}

    assert attention_ids
    assert not attention_ids & band_ids
    assert {window["id"] for window in data.get("attention_windows", [])} == attention_ids


def test_active_frontend_has_no_independent_period_bucket_list():
    forbidden = [
        "MAP_FLAG_GROWTH_BUCKETS",
        "buildDensityPeriodSchemes",
        "periodContainsYear",
        "backsearch_1803_1841",
        "anchor_1842_1875",
        "expansion_1876_1969",
        "modern_1970_1990",
        "modern_1991_2010",
        "contemporary_2011_present",
        "google_trends_2004_present",
        "wikimedia_2015_present",
    ]

    for path in ACTIVE_FRONTEND_COMPONENTS:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text
