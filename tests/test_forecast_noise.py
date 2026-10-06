"""Weather perturbations happen before transforms and never change targets."""

import copy

import numpy as np
import pandas as pd
import pytest

from src.features.build import build_features, feature_matrix
from src.features.forecast_noise import simulate_forecast_weather


def raw_weather():
    return pd.DataFrame({"datetime_utc": pd.date_range("2025-05-01", periods=72, freq="h", tz="UTC"),
                         "zone": "IN-NO", "point_name": "Delhi", "temperature_2m": 21.5})


def test_noise_is_deterministic_order_independent_and_does_not_mutate(cfg):
    raw = raw_weather()
    snapshot = raw.copy()
    first = simulate_forecast_weather(raw, cfg, stream=3)
    second = simulate_forecast_weather(raw.iloc[::-1], cfg, stream=3).sort_index()
    pd.testing.assert_frame_equal(first, second)
    pd.testing.assert_frame_equal(raw, snapshot)
    assert not first.temperature_2m.equals(raw.temperature_2m)
    assert not first.temperature_2m.equals(simulate_forecast_weather(raw, cfg, stream=4).temperature_2m)


def test_bias_is_shared_within_city_ist_day(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["forecast_noise"]["hour_wobble_sigma_c"] = 0
    raw = raw_weather()
    result = simulate_forecast_weather(raw, cfg)
    days = result.datetime_utc.dt.tz_convert("Asia/Kolkata").dt.date
    assert (result.groupby(days).temperature_2m.nunique() == 1).all()


def test_cooling_degrees_are_recomputed_and_feature_contract_is_preserved(cfg):
    noisy = simulate_forecast_weather(raw_weather(), cfg)
    demand = noisy[["datetime_utc", "zone"]].assign(demand_mw=1000.0, is_estimated=False,
                                                    estimation_method=None)
    train = build_features(noisy, cfg, demand=demand)
    serving = build_features(noisy, cfg)
    np.testing.assert_allclose(train.cooling_degrees, np.maximum(0, noisy.temperature_2m - 21.5))
    pd.testing.assert_frame_equal(feature_matrix(train), feature_matrix(serving))
    assert train.demand_mw.eq(1000).all()


def test_invalid_noise_sigma_is_rejected(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["forecast_noise"]["day_bias_sigma_c"] = -1
    with pytest.raises(ValueError, match="nonnegative"):
        simulate_forecast_weather(raw_weather(), cfg)
