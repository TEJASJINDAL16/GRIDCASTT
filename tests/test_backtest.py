"""End-to-end fold isolation; generated data here is only a test fixture."""

import copy

import numpy as np
import pandas as pd
import pytest

from src.backtest.run import evaluate, write_report
from src.models.baselines import BASELINE_NAMES


def small_inputs(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["demand"]["all_zones"] = ["IN-NO", "IN-WE"]
    cfg["splits"].update(tuning_window_months=1, min_initial_train_months=1,
                          walk_forward_folds=2, holdout_months=1)
    cfg["quality"]["trainable_from"] = {}
    stamps = pd.date_range("2024-01-01", "2024-06-01", freq="h", tz="UTC", inclusive="left")
    weather = pd.concat([pd.DataFrame({"datetime_utc": stamps, "zone": zone, "point_name": name,
                                       "temperature_2m": 25. + np.sin(np.arange(len(stamps)) / 24)})
                         for zone, name in [("IN-NO", "Delhi"), ("IN-WE", "Mumbai")]], ignore_index=True)
    demand = weather[["datetime_utc", "zone"]].copy()
    demand["demand_mw"] = np.where(demand.zone == "IN-NO", 10000., 5000.) * (
        1 + .05 * np.sin(np.arange(len(demand)) / 24))
    demand["is_estimated"] = False
    demand["estimation_method"] = None
    return cfg, demand, weather


@pytest.fixture(scope="module")
def evaluated(cfg):
    local, demand, weather = small_inputs(cfg)
    return local, demand, weather, evaluate(demand, weather, local)


def test_every_baseline_scores_identical_rows_and_never_holdout(evaluated):
    cfg, _, _, result = evaluated
    frame = result["predictions"]
    assert set(frame.model) == set(BASELINE_NAMES)
    assert frame.groupby("model").size().nunique() == 1
    assert frame.datetime_utc.max() < result["plan"].holdout_start
    assert not frame.is_estimated.any()
    cutoff = frame.issued_at - pd.Timedelta(days=cfg["splits"]["purge_gap_days"])
    assert (frame.baseline_source_datetime <= cutoff).all()
    assert frame.lead_time_hours.min() == 14.5
    assert frame.lead_time_hours.max() == 37.5


def test_future_holdout_targets_cannot_change_any_prediction(evaluated):
    cfg, demand, weather, first = evaluated
    changed = demand.copy()
    changed.loc[changed.datetime_utc >= first["plan"].holdout_start, "demand_mw"] *= 1000
    second = evaluate(changed, weather, cfg)
    pd.testing.assert_frame_equal(first["predictions"], second["predictions"])
    pd.testing.assert_frame_equal(first["fold_scores"], second["fold_scores"])


def test_later_fold_targets_cannot_change_earlier_fold_predictions(evaluated):
    cfg, demand, weather, first = evaluated
    changed = demand.copy()
    changed.loc[changed.datetime_utc >= first["plan"].folds[0].test_end, "demand_mw"] *= 10
    second = evaluate(changed, weather, cfg)
    original_rows = first["predictions"].loc[lambda f: f.fold == 1].reset_index(drop=True)
    changed_rows = second["predictions"].loc[lambda f: f.fold == 1].reset_index(drop=True)
    pd.testing.assert_frame_equal(original_rows, changed_rows)


def test_perfect_observed_weather_cannot_silently_be_scored(evaluated):
    cfg, demand, weather, _ = evaluated
    cfg = copy.deepcopy(cfg)
    cfg["forecast_noise"]["enabled"] = False
    with pytest.raises(ValueError, match="not perfect weather"):
        evaluate(demand, weather, cfg)


def test_hot_drop_and_short_zone_history_reach_model_training(evaluated, monkeypatch):
    from src.models.baselines import HourWeekdayMean

    cfg, demand, weather, original = evaluated
    demand, weather = demand.copy(), weather.copy()
    first = original["plan"].folds[0]
    recent_start = first.train_end - pd.Timedelta(hours=600)
    earlier = (demand.zone == "IN-NO") & (demand.datetime_utc < recent_start)
    demand.loc[earlier, "is_estimated"] = True
    demand.loc[earlier, "estimation_method"] = "TIME_SLICER_AVERAGE"
    episode = pd.date_range(recent_start.ceil("h"), periods=4, freq="h")
    drop = (demand.zone == "IN-NO") & demand.datetime_utc.isin(episode)
    demand.loc[drop, "demand_mw"] = 1000.
    weather.loc[(weather.zone == "IN-NO") & weather.datetime_utc.isin(episode), "temperature_2m"] = 48.
    fitted_frames = []
    fit = HourWeekdayMean.fit

    def capture_fit(model, frame):
        fitted_frames.append(frame.copy())
        return fit(model, frame)

    monkeypatch.setattr(HourWeekdayMean, "fit", capture_fit)
    result = evaluate(demand, weather, cfg)
    zone = fitted_frames[0].loc[lambda f: f.zone == "IN-NO"]
    assert len(zone) == 600
    retained = zone.loc[zone.datetime_utc.isin(episode)]
    assert len(retained) == 4
    assert (retained.demand_mw == 1000.).all()
    assert (retained.temperature > 40.).all()
    assert not zone.is_estimated.any()
    assert "IN-NO" in result["coverage"].iloc[0].training_zones


def test_missing_weather_hour_skips_whole_zone_day_and_reports_gap(evaluated):
    cfg, demand, weather, original = evaluated
    missing = original["plan"].folds[0].test_start.ceil("h")
    weather = weather.loc[~((weather.zone == "IN-NO") & (weather.datetime_utc == missing))]
    result = evaluate(demand, weather, cfg)
    date = missing.tz_convert("Asia/Kolkata").date()
    rows = result["predictions"]
    assert rows.loc[(rows.zone == "IN-NO") & (rows.date_ist == date)].empty
    assert not rows.loc[(rows.zone == "IN-WE") & (rows.date_ist == date)].empty
    first = result["coverage"].iloc[0]
    assert first.n_expected - first.n_forecast == 24
    assert first.cache_gap_fraction > 0


def test_report_has_comparison_counts_and_discloses_simulation(evaluated, tmp_path):
    cfg, _, _, result = evaluated
    # write_report hashes source files as well as data; use the real sources.
    from src.config import PROJECT_ROOT
    for folder in ["src", "scripts", "config", "data"]:
        (tmp_path / folder).symlink_to(PROJECT_ROOT / folder, target_is_directory=True)
    cfg = copy.deepcopy(cfg)
    cfg["backtest"]["predictions_path"] = "outputs/test_predictions.parquet"
    report = write_report(result, cfg, tmp_path)
    text = report.read_text(encoding="utf-8")
    assert "Number to beat" in text
    assert "out-of-sample" in text and "assumptions" in text
    assert "Lead-Time Investigation" in text
    for name in BASELINE_NAMES:
        assert name in text
    for dimension in ["temperature_band", "hour_of_day", "zone", "day_type", "lead_time_hours", "time_rolling"]:
        assert f"Stratification: {dimension}" in text
    stats = pd.read_csv(tmp_path / "reports/baseline/stratified.csv")
    assert {"n_rows", "baseline_mape_pct", "mase", "rmsse"} <= set(stats.columns)
