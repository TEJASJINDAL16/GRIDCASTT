"""src/validate.py must fail on corrupted data (PLANNING 14).

A validator nobody has seen fail is a validator nobody knows works. Each test
here corrupts one thing and asserts the refusal, which is the unit-test form of
the stage-1 deliverable that runs the same proof against the real pulled files.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.validate import ValidationError, validate_demand, validate_weather

# --- the happy path -------------------------------------------------------

def test_clean_demand_passes(demand_frame, cfg):
    report = validate_demand(demand_frame, "IN-NO", cfg)
    assert report.rows == 168
    assert report.gap_count == 0
    assert report.warnings == []


def test_clean_weather_passes(weather_frame, cfg):
    report = validate_weather(weather_frame, "Delhi", cfg)
    assert report.rows == 168
    assert report.gap_count == 0


# --- schema ---------------------------------------------------------------

@pytest.mark.parametrize("column", ["demand_mw", "is_estimated", "datetime_utc", "zone"])
def test_missing_column_is_refused(demand_frame, cfg, column):
    with pytest.raises(ValidationError, match="missing column"):
        validate_demand(demand_frame.drop(columns=[column]), "IN-NO", cfg)


def test_camel_case_column_is_refused(demand_frame, cfg):
    """PLANNING 11: exactly one camelCase -> snake_case conversion point. A
    frame still carrying isEstimated means that point was bypassed."""
    renamed = demand_frame.rename(columns={"is_estimated": "isEstimated"})
    with pytest.raises(ValidationError, match="missing column"):
        validate_demand(renamed, "IN-NO", cfg)


def test_empty_frame_is_refused(demand_frame, cfg):
    with pytest.raises(ValidationError, match="empty frame"):
        validate_demand(demand_frame.iloc[0:0], "IN-NO", cfg)


# --- timestamps -----------------------------------------------------------

def test_naive_timestamps_are_refused(demand_frame, cfg):
    naive = demand_frame.copy()
    naive["datetime_utc"] = naive["datetime_utc"].dt.tz_localize(None)
    with pytest.raises(ValidationError, match="timezone-naive"):
        validate_demand(naive, "IN-NO", cfg)


def test_non_utc_timestamps_are_refused(demand_frame, cfg):
    shifted = demand_frame.copy()
    shifted["datetime_utc"] = shifted["datetime_utc"].dt.tz_convert("Asia/Kolkata")
    with pytest.raises(ValidationError, match="expected UTC"):
        validate_demand(shifted, "IN-NO", cfg)


def test_duplicate_timestamps_are_refused(demand_frame, cfg):
    doubled = pd.concat([demand_frame, demand_frame.iloc[:3]], ignore_index=True)
    with pytest.raises(ValidationError, match="duplicate"):
        validate_demand(doubled, "IN-NO", cfg)


def test_sub_hourly_granularity_is_refused(demand_frame, cfg):
    finer = demand_frame.copy()
    finer["datetime_utc"] = pd.date_range(
        "2024-05-01", periods=len(finer), freq="30min", tz="UTC")
    with pytest.raises(ValidationError, match="shorter than the expected"):
        validate_demand(finer, "IN-NO", cfg)


# --- ranges ---------------------------------------------------------------

def test_demand_in_gigawatts_is_refused(demand_frame, cfg):
    """A source switching MW to kW, or a decimal shift, is the failure this
    catches — it would otherwise train happily on numbers 1000x wrong."""
    wrong_units = demand_frame.copy()
    wrong_units["demand_mw"] *= 1000
    with pytest.raises(ValidationError, match="outside the plausible range"):
        validate_demand(wrong_units, "IN-NO", cfg)


def test_negative_demand_is_refused(demand_frame, cfg):
    negative = demand_frame.copy()
    negative.loc[5, "demand_mw"] = -100.0
    with pytest.raises(ValidationError, match="outside the plausible range"):
        validate_demand(negative, "IN-NO", cfg)


def test_temperature_in_fahrenheit_is_refused(weather_frame, cfg):
    fahrenheit = weather_frame.copy()
    fahrenheit["temperature_2m"] = fahrenheit["temperature_2m"] * 9 / 5 + 32
    with pytest.raises(ValidationError, match="outside the plausible range"):
        validate_weather(fahrenheit, "Delhi", cfg)


def test_a_real_indian_heatwave_still_passes(weather_frame, cfg):
    """The bounds are loose on purpose. 50 C is a real observation, and a
    validator that rejected it would be doing the exact thing 5f principle 2
    warns about."""
    hot = weather_frame.copy()
    hot.loc[hot.index[:5], "temperature_2m"] = 50.0
    assert validate_weather(hot, "Delhi", cfg).rows == 168


# --- the estimation flag --------------------------------------------------

def test_all_null_estimation_flag_is_refused(demand_frame, cfg):
    blind = demand_frame.copy()
    blind["is_estimated"] = None
    with pytest.raises(ValidationError, match="is_estimated is entirely null"):
        validate_demand(blind, "IN-NO", cfg)


def test_some_null_estimation_flags_warn_but_pass(demand_frame, cfg):
    partial = demand_frame.copy()
    partial["is_estimated"] = partial["is_estimated"].astype("object")
    partial.loc[0:2, "is_estimated"] = None
    report = validate_demand(partial, "IN-NO", cfg)
    assert any("is_estimated" in w for w in report.warnings)


def test_wrong_zone_is_refused(demand_frame, cfg):
    with pytest.raises(ValidationError, match="expected only IN-WE"):
        validate_demand(demand_frame, "IN-WE", cfg)


# --- gaps: reported on history, fatal where contiguity is claimed ---------

def test_gap_in_history_is_reported_not_fatal(demand_frame, cfg):
    """PLANNING 5h: log the gap and exclude those rows."""
    holed = demand_frame.drop(index=range(10, 20)).reset_index(drop=True)
    report = validate_demand(holed, "IN-NO", cfg)
    assert report.gap_count == 1
    assert report.gap_hours == 10
    assert report.largest_gap_hours == 11


def test_gap_is_fatal_when_contiguity_is_claimed(demand_frame, cfg):
    holed = demand_frame.drop(index=range(10, 20)).reset_index(drop=True)
    with pytest.raises(ValidationError, match="must be contiguous"):
        validate_demand(holed, "IN-NO", cfg, contiguous=True)


def test_large_gap_fraction_warns(demand_frame, cfg):
    holed = demand_frame.drop(index=range(10, 60)).reset_index(drop=True)
    report = validate_demand(holed, "IN-NO", cfg)
    assert report.gap_fraction > cfg["validate"]["max_gap_fraction_warn"]
    assert any("gap fraction" in w for w in report.warnings)


def test_all_null_temperature_is_refused(weather_frame, cfg):
    """The bug this test exists for: a fixture whose values silently became NaN
    made a 'clean weather passes' test pass for the wrong reason."""
    blank = weather_frame.copy()
    blank["temperature_2m"] = float("nan")
    with pytest.raises(ValidationError, match="temperature_2m is entirely null"):
        validate_weather(blank, "Delhi", cfg)


def test_all_null_demand_is_refused(demand_frame, cfg):
    blank = demand_frame.copy()
    blank["demand_mw"] = float("nan")
    with pytest.raises(ValidationError, match="demand_mw is entirely null"):
        validate_demand(blank, "IN-NO", cfg)
