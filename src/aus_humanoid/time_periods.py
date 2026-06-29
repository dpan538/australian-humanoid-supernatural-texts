"""Shared public-record time period configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from aus_humanoid.utils import PROJECT_ROOT


TIME_PERIODS_PATH = PROJECT_ROOT / "config" / "time_periods.json"
PUBLIC_PERIOD_COUNT = 6


def load_time_period_config(path: str | Path = TIME_PERIODS_PATH) -> dict[str, Any]:
    loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    periods = loaded.get("public_record_periods") or []
    if len(periods) != PUBLIC_PERIOD_COUNT:
        raise ValueError(f"Expected {PUBLIC_PERIOD_COUNT} public record periods in {path}")
    return loaded


def dated_year_bounds(years: Iterable[int | None]) -> tuple[int | None, int | None]:
    dated_years = sorted(year for year in years if isinstance(year, int))
    if not dated_years:
        return None, None
    return dated_years[0], dated_years[-1]


def build_public_date_bands(earliest_year: int | None, latest_year: int | None) -> list[dict[str, Any]]:
    config = load_time_period_config()
    periods = config["public_record_periods"]
    if earliest_year is None or latest_year is None:
        return [
            {
                "id": period["id"],
                "label": period.get("open_display_label") or period.get("label") or period["short_label"],
                "short_label": period["short_label"],
                "start": None,
                "end": None,
                "role": period["context"],
                "context": period["context"],
            }
            for period in periods
        ]

    bands: list[dict[str, Any]] = []
    previous_end: int | None = None
    for index, period in enumerate(periods):
        if period.get("dynamic_start") == "actual_earliest_year":
            start = earliest_year
        else:
            start = int(period["start"])
        if period.get("dynamic_end") == "actual_latest_year":
            end = latest_year
        else:
            end = int(period["end"])

        if previous_end is not None and start != previous_end + 1:
            raise ValueError(f"Configured periods are not contiguous at {period['id']}: {start} after {previous_end}")
        if index == 0 and start != earliest_year:
            raise ValueError("First public period must start at the actual earliest year")
        if index == len(periods) - 1 and end != latest_year:
            raise ValueError("Last public period must end at the actual latest year")
        if end < start:
            raise ValueError(f"Configured period {period['id']} has end before start")

        label = f"{start}-{end}"
        bands.append(
            {
                "id": period["id"],
                "label": label,
                "short_label": period["short_label"],
                "start": start,
                "end": end,
                "role": period["context"],
                "context": period["context"],
                "open_display_label": period.get("open_display_label"),
            }
        )
        previous_end = end
    return bands


def year_to_public_period_id(year: int | None, date_bands: Iterable[dict[str, Any]]) -> str:
    if year is None:
        return "undated"
    for band in date_bands:
        start = band.get("start")
        end = band.get("end")
        if isinstance(start, int) and isinstance(end, int) and start <= year <= end:
            return str(band["id"])
    return "outside_scope"


def attention_windows() -> list[dict[str, Any]]:
    return list(load_time_period_config().get("attention_windows") or [])
