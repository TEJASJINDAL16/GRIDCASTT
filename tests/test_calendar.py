"""Calendar extraction (PLANNING 5e).

The failure this guards against does not raise: taking a weekday or a date from
a UTC timestamp shifts every calendar feature and every holiday lookup by a day,
for the first hour of every forecast, silently.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.ingest.calendar_in import (
    DAY_TYPES,
    calendar_frame,
    day_type,
    is_holiday,
    load_manual_festivals,
    to_ist,
    zone_holidays,
)


def test_ist_conversion_moves_the_date_across_the_target_boundary(cfg):
    """19:00 UTC is 00:30 IST the NEXT day — the whole reason 5e has this rule."""
    utc = pd.Series(pd.to_datetime(["2024-05-01 19:00:00"], utc=True))
    ist = to_ist(utc, cfg)
    assert ist.dt.hour.iloc[0] == 0
    assert ist.dt.minute.iloc[0] == 30
    assert str(ist.dt.date.iloc[0]) == "2024-05-02"        # not 05-01


def test_naive_timestamps_are_refused(cfg):
    naive = pd.Series(pd.to_datetime(["2024-05-01 19:00:00"]))
    with pytest.raises(ValueError, match="timezone-naive"):
        to_ist(naive, cfg)


def test_weekday_differs_between_utc_and_ist_at_the_boundary(cfg):
    """The concrete bug: a Wednesday in UTC that is a Thursday in IST."""
    utc = pd.Series(pd.to_datetime(["2024-05-01 19:00:00"], utc=True))
    assert utc.dt.dayofweek.iloc[0] == 2                    # Wednesday
    assert to_ist(utc, cfg).dt.dayofweek.iloc[0] == 3       # Thursday IST


def test_every_zone_has_a_subdivision_and_returns_holidays(cfg):
    for zone in cfg["demand"]["all_zones"]:
        dates = zone_holidays(zone, [2024], cfg)
        assert len(dates) > 5, f"{zone} returned {len(dates)} holidays for 2024"


def test_unknown_zone_fails_loudly(cfg):
    with pytest.raises(KeyError, match="no holiday subdivision"):
        zone_holidays("IN-XX", [2024], cfg)


def test_republic_day_is_a_holiday_in_every_zone(cfg):
    """A fixed-date national holiday: if this misses, the lookup is broken."""
    dates = pd.Series([pd.Timestamp("2024-01-26").date()] * 5)
    zones = pd.Series(cfg["demand"]["all_zones"])
    assert is_holiday(dates, zones, cfg).all()


def test_holidays_are_zone_specific(cfg):
    """Ganesh Chaturthi is a Maharashtra holiday, so IN-WE and not IN-NO."""
    ganesh = zone_holidays("IN-WE", [2024], cfg) - zone_holidays("IN-NO", [2024], cfg)
    assert ganesh, "IN-WE should carry state holidays IN-NO does not"


def test_manual_festival_file_loads_and_is_honest(cfg):
    """Empty is valid. An invented date would be worse than a known gap."""
    manual = load_manual_festivals(cfg)
    assert list(manual.columns) == ["date", "zone", "name"]


def test_day_type_separates_all_three(cfg):
    weekday = pd.Series([0, 5, 6, 0])
    holiday = pd.Series([False, False, False, True])
    out = pd.Series(day_type(weekday, holiday, cfg))
    assert list(out) == ["weekday", "weekend", "weekend", "holiday"]


def test_holiday_beats_weekend(cfg):
    """A holiday on a Sunday reports as a holiday — the category a reader asks
    about — rather than being hidden inside the weekend bucket."""
    out = pd.Series(day_type(pd.Series([6]), pd.Series([True]), cfg))
    assert out.iloc[0] == "holiday"


def test_calendar_frame_shape_and_dtypes(cfg):
    utc = pd.Series(pd.date_range("2024-05-01", periods=48, freq="h", tz="UTC"))
    zones = pd.Series(["IN-NO"] * 48)
    out = calendar_frame(utc, zones, cfg)
    assert list(out.columns) == ["datetime_ist", "date_ist", "hour_of_day",
                                "day_of_week", "is_holiday", "day_type"]
    assert out["hour_of_day"].between(0, 23).all()
    assert out["day_of_week"].between(0, 6).all()
    assert out["is_holiday"].dtype == bool
    assert set(out["day_type"].cat.categories) == set(DAY_TYPES)


def test_calendar_frame_uses_ist_hours_not_utc(cfg):
    """The first target hour, 19:00 UTC, must come out as IST hour 0."""
    utc = pd.Series(pd.to_datetime(["2024-05-01 19:00:00"], utc=True))
    out = calendar_frame(utc, pd.Series(["IN-NO"]), cfg)
    assert out["hour_of_day"].iloc[0] == 0
