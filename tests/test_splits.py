"""Calendar boundaries, information cutoffs, and the reserved holdout."""

import copy

import numpy as np
import pandas as pd
import pytest

from src.backtest.splits import issue_times, make_splits, measured_mask


def history(cfg):
    stamps = pd.date_range("2020-01-01", "2026-09-06 23:00", freq="h", tz="UTC")
    return pd.concat([pd.DataFrame({"datetime_utc": stamps, "zone": zone,
                                   "demand_mw": 1000.0, "is_estimated": False,
                                   "estimation_method": None})
                      for zone in cfg["demand"]["all_zones"]], ignore_index=True)


def test_twelve_folds_end_before_untouched_holdout(cfg):
    plan = make_splits(history(cfg), cfg)
    assert len(plan.folds) == 12
    assert plan.folds[0].test_start.tz_convert("Asia/Kolkata") == pd.Timestamp("2024-09-01", tz="Asia/Kolkata")
    assert plan.holdout_start.tz_convert("Asia/Kolkata") == pd.Timestamp("2025-09-01", tz="Asia/Kolkata")
    assert plan.holdout_end.tz_convert("Asia/Kolkata") == pd.Timestamp("2026-09-01", tz="Asia/Kolkata")
    for i, fold in enumerate(plan.folds):
        assert plan.tuning_end <= fold.train_end < fold.test_start < fold.test_end <= plan.holdout_start
        assert fold.validation_start < fold.train_end
        first_target = pd.Series([fold.test_start.ceil("h")])
        assert fold.train_end <= issue_times(first_target, cfg).iloc[0] - pd.Timedelta(days=10)
        if i:
            assert plan.folds[i - 1].test_end == fold.test_start
            assert fold.train_start == plan.folds[i - 1].train_start


def test_exact_ist_day_has_24_noninterpolated_targets(cfg):
    targets = pd.Series(pd.date_range("2025-03-09 19:00", periods=24, freq="h", tz="UTC"))
    issues = issue_times(targets, cfg)
    assert issues.nunique() == 1
    assert issues.iloc[0] == pd.Timestamp("2025-03-09 04:30", tz="UTC")
    leads = (targets - issues).dt.total_seconds() / 3600
    assert leads.iloc[0] == 14.5
    assert leads.iloc[-1] == 37.5
    assert targets.dt.tz_convert("Asia/Kolkata").dt.date.nunique() == 1


def test_insufficient_history_fails_instead_of_shortening_protocol(cfg):
    short = history(cfg).loc[lambda f: f.datetime_utc > pd.Timestamp("2024-01-01", tz="UTC")]
    with pytest.raises(ValueError, match="insufficient history"):
        make_splits(short, cfg)


def test_missing_zone_cannot_move_shared_boundary(cfg):
    frame = history(cfg).loc[lambda f: f.zone != "IN-NE"]
    with pytest.raises(ValueError, match="every configured zone"):
        make_splits(frame, cfg)


def test_unknown_estimates_and_nonpositive_targets_are_unscorable():
    frame = pd.DataFrame({"is_estimated": [False, True, None, False, False],
                          "demand_mw": [100, 100, 100, 0, np.nan]})
    assert measured_mask(frame).tolist() == [True, False, False, False, False]


def test_no_holdout_values_affect_split_boundaries(cfg):
    frame = history(cfg)
    original = make_splits(frame, cfg)
    frame.loc[frame.datetime_utc >= original.holdout_start, "demand_mw"] *= 1000
    assert make_splits(frame, copy.deepcopy(cfg)) == original
