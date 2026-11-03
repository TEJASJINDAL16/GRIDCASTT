"""Synthetic fixtures verify math and time isolation, never project accuracy."""

import copy

import numpy as np
import pandas as pd
import pytest

from src.features.build import build_features
from src.models.hybrid import Hybrid
from tests.test_backtest import small_inputs


@pytest.fixture
def trained(cfg):
    cfg, demand, weather = small_inputs(cfg)
    cfg["splits"]["early_stopping_weeks"] = 2
    cfg["train"]["ridge"]["alpha"] = 1.0
    cfg["train"]["lightgbm"] = dict(
        num_leaves=15,
        learning_rate=0.1,
        min_data_in_leaf=20,
        feature_fraction=1.0,
        bagging_fraction=1.0,
        lambda_l1=0.0,
        lambda_l2=0.0,
    )
    cfg["runtime"]["max_boost_rounds"] = 500
    cfg["runtime"]["early_stopping_rounds"] = 5
    frame = build_features(weather, cfg, demand=demand)
    end = pd.Timestamp("2024-04-01", tz="UTC")
    train = frame.loc[frame.datetime_utc < end]
    model = Hybrid(cfg).fit(train, train_end=end)
    return cfg, model, train, frame.loc[frame.datetime_utc >= end]


def test_hybrid_smearing_is_applied_once_and_per_zone(trained):
    _, model, train, test = trained
    raw = model.linear.predict(model._linear_input(train)) + model.tree.predict(
        train[model.columns]
    )
    residual = np.log(train.demand_mw) - raw
    for zone, part in train.groupby("zone", observed=True):
        assert model.smearing[zone] == pytest.approx(np.exp(residual.loc[part.index]).mean())
    assert np.isfinite(model.predict(test)).all()
    assert model.iterations >= model.best_iteration


def test_hybrid_clamps_low_input_and_flags_high_weather(trained):
    _, model, train, test = trained
    changed = test.head(2).copy()
    changed["temperature"] = [-40.0, 60.0]
    values = model._linear_input(changed)
    assert values.temperature.iloc[0] == train.temperature.min()
    assert values.temperature.iloc[1] == 60.0
    assert model.flags(changed) == [["extrapolating"], ["extrapolating"]]
    assert model.tree.get_params()["monotone_constraints"] == [0, 0, 0, 0, 1, 0, 0]


def test_hybrid_refuses_future_targets(trained):
    cfg, _, train, test = trained
    with pytest.raises(ValueError, match="strictly before"):
        Hybrid(copy.deepcopy(cfg)).fit(pd.concat([train, test]), train_end=test.datetime_utc.min())


def test_iteration_ceiling_is_not_mistaken_for_early_stopping(trained):
    cfg, _, train, test = trained
    local = copy.deepcopy(cfg)
    local["runtime"]["max_boost_rounds"] = 1
    with pytest.raises(ValueError, match="count is not identified"):
        Hybrid(local).fit(train, train_end=test.datetime_utc.min())
