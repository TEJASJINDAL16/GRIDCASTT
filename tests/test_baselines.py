"""The seasonal baseline obeys availability, not simply last week's date."""

import numpy as np
import pandas as pd

from src.models.baselines import HourWeekdayMean, RidgeBaseline, SeasonalNaive


def same_slot():
    dates = pd.date_range("2025-01-06 13:00", periods=6, freq="7D", tz="UTC")
    return pd.DataFrame({"datetime_utc": dates, "zone": "IN-NO", "hour_of_day": 18,
                         "day_of_week": 0, "demand_mw": np.arange(6) * 1000 + 1000.0,
                         "is_estimated": False})


def test_naive_reaches_back_past_unsettled_and_estimated_rows(cfg):
    history = same_slot()
    history.loc[3, "is_estimated"] = True
    target = history.iloc[[5]].assign(issued_at=pd.Timestamp("2025-02-09 04:30", tz="UTC"))
    prediction = SeasonalNaive(cfg).fit(history).predict(target)
    assert prediction.prediction_mw.iloc[0] == 3000
    assert prediction.source_datetime.iloc[0] == history.datetime_utc.iloc[2]


def test_naive_prediction_cannot_change_when_future_demand_changes(cfg):
    history = same_slot()
    target = history.iloc[[5]].assign(issued_at=pd.Timestamp("2025-02-09 04:30", tz="UTC"))
    first = SeasonalNaive(cfg).fit(history).predict(target)
    history.loc[history.datetime_utc >= target.issued_at.iloc[0] - pd.Timedelta(days=10), "demand_mw"] = 999999
    pd.testing.assert_frame_equal(first, SeasonalNaive(cfg).fit(history).predict(target))


def test_naive_handles_microsecond_and_nanosecond_timestamps_identically(cfg):
    history = same_slot()
    target = history.iloc[[5]].assign(issued_at=pd.Timestamp("2025-02-09 04:30", tz="UTC"))
    ns = SeasonalNaive(cfg).fit(history).predict(target)
    history["datetime_utc"] = history.datetime_utc.dt.as_unit("us")
    target["issued_at"] = target.issued_at.dt.as_unit("ns")
    pd.testing.assert_frame_equal(ns, SeasonalNaive(cfg).fit(history).predict(target))


def test_missing_baseline_slot_abstains_instead_of_using_future(cfg):
    target = same_slot().iloc[[0]].assign(issued_at=pd.Timestamp("2025-01-05", tz="UTC"))
    assert SeasonalNaive(cfg).fit(same_slot()).predict(target).prediction_mw.isna().all()


def training_frame():
    n = 200
    return pd.DataFrame({"datetime_utc": pd.date_range("2025-01-01", periods=n, freq="h", tz="UTC"),
                         "hour_of_day": np.arange(n) % 24, "day_of_week": np.arange(n) % 7,
                         "zone": "IN-NO", "is_holiday": False, "temperature": 30.,
                         "cooling_degrees": 8.5, "trend": np.arange(n) / 24,
                         "demand_mw": 1000.})


def test_all_learned_baselines_abstain_on_zones_without_training(cfg):
    training = training_frame()
    unseen = training.iloc[:2].assign(zone="IN-NE")
    assert HourWeekdayMean().fit(training).predict(unseen).isna().all()
    for separate in [False, True]:
        model = RidgeBaseline(cfg, per_zone=separate).fit(training, train_end=training.datetime_utc.max())
        assert model.predict(unseen).isna().all()
        np.testing.assert_allclose(model.predict(training.iloc[:5]), 1000, rtol=1e-8)


def test_hour_weekday_mean_uses_same_zone_slot():
    frame = training_frame()
    frame.loc[(frame.hour_of_day == 0) & (frame.day_of_week == 0), "demand_mw"] = 2000.
    prediction = HourWeekdayMean().fit(frame).predict(frame.iloc[[0]])
    assert prediction.iloc[0] == 2000.
