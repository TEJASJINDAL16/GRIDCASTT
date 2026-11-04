"""Demand history must respect the same issue cutoff as the baseline."""

import numpy as np
import pandas as pd

from src.models.history import DemandHistory


def test_future_values_and_estimates_cannot_change_history():
    dates = pd.to_datetime(["2024-01-01", "2024-01-08", "2024-01-15", "2024-01-22"], utc=True)
    history = pd.DataFrame(
        {
            "datetime_utc": dates,
            "zone": "IN-NO",
            "hour_of_day": 0,
            "day_of_week": 0,
            "demand_mw": [100.0, 110.0, 999.0, 888.0],
            "temperature": 20.0,
            "is_estimated": [False, False, True, False],
        }
    )
    query = pd.DataFrame(
        {
            "datetime_utc": pd.to_datetime(["2024-01-23"], utc=True),
            "issued_at": pd.to_datetime(["2024-01-22"], utc=True),
            "zone": "IN-NO",
            "hour_of_day": 0,
            "day_of_week": 0,
            "is_holiday": False,
            "temperature": 25.0,
            "cooling_degrees": 0.0,
        }
    )
    cfg = {"splits": {"purge_gap_days": 10}, "refinement": {"history_count": 4}}
    expected = DemandHistory(history, cfg).transform(query)
    assert expected.baseline_mw.iloc[0] == 110
    assert expected.lag_1.iloc[0] == 100
    assert expected.temperature_change.iloc[0] == 5
    history.loc[history.datetime_utc > pd.Timestamp("2024-01-12", tz="UTC"), "demand_mw"] = 1e9
    pd.testing.assert_frame_equal(expected, DemandHistory(history, cfg).transform(query))
    query["issued_at"] = pd.Timestamp("2023-12-31", tz="UTC")
    assert np.isnan(DemandHistory(history, cfg).transform(query).baseline_mw.iloc[0])


def test_adaptive_choice_uses_provided_training_targets_only():
    from src.models.history import AdaptiveHistory

    cfg = {"refinement": {"averaging_windows": [1, 2, 4], "minimum_training_rows": 2}}
    features = pd.DataFrame(
        {
            "zone": ["IN-NO"] * 3,
            "baseline_mw": [100.0] * 3,
            "lag_0": [100.0] * 3,
            "lag_1": [80.0] * 3,
            "lag_2": [20.0] * 3,
            "lag_3": [20.0] * 3,
        }
    )
    model = AdaptiveHistory(cfg).fit(features, pd.Series([90.0] * 3))
    assert model.selected == {"IN-NO": 2}
    assert model.predict(features).eq(90).all()
    unknown = features.assign(zone="IN-NE")
    assert model.predict(unknown).eq(100).all()
