"""Reserved tuning, monthly expanding folds, and an untouched final holdout."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.config import get
from src.features.build import trainable_mask


@dataclass(frozen=True)
class Fold:
    number: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


@dataclass(frozen=True)
class SplitPlan:
    tuning_start: pd.Timestamp
    tuning_end: pd.Timestamp
    holdout_start: pd.Timestamp
    holdout_end: pd.Timestamp
    folds: tuple[Fold, ...]


def issue_times(targets: pd.Series, cfg: dict) -> pd.Series:
    """10:00 IST on the day before each target's IST calendar day."""
    local = targets.dt.tz_convert(get(cfg, "project.timezone"))
    return (local.dt.normalize() - pd.Timedelta(days=1)
            + pd.Timedelta(hours=get(cfg, "backtest.issue_hour_ist"))).dt.tz_convert("UTC")


def make_splits(frame: pd.DataFrame, cfg: dict) -> SplitPlan:
    """Anchor to the latest complete common calendar month, never a partial tail.

    Only timestamps and the already-frozen estimation policy define boundaries.
    Holdout targets are not inspected or scored.
    """
    tz = get(cfg, "project.timezone")
    zones = get(cfg, "demand.all_zones")
    latest = frame.groupby("zone", observed=True).datetime_utc.max().reindex(zones)
    if latest.isna().any():
        raise ValueError("split plan requires coverage in every configured zone")
    end = (latest.min() + pd.Timedelta(hours=1)).tz_convert(tz)
    end = pd.Timestamp(year=end.year, month=end.month, day=1, tz=tz)
    holdout_start = end - pd.DateOffset(months=get(cfg, "splits.holdout_months"))
    first_test = holdout_start - pd.DateOffset(months=get(cfg, "splits.walk_forward_folds"))
    eligible = frame.loc[trainable_mask(frame, cfg), "datetime_utc"]
    if eligible.empty:
        raise ValueError("no eligible training history")
    start = eligible.min().tz_convert(tz)
    start = pd.Timestamp(year=start.year, month=start.month, day=1, tz=tz)
    tuning_end = start + pd.DateOffset(months=get(cfg, "splits.tuning_window_months"))
    minimum = tuning_end + pd.DateOffset(months=get(cfg, "splits.min_initial_train_months"))
    if first_test < minimum:
        raise ValueError("insufficient history for tuning, initial training, folds and holdout")
    folds = []
    for i in range(get(cfg, "splits.walk_forward_folds")):
        test_start = first_test + pd.DateOffset(months=i)
        test_end = test_start + pd.DateOffset(months=1)
        first_issue = test_start - pd.Timedelta(days=1) + pd.Timedelta(
            hours=get(cfg, "backtest.issue_hour_ist"))
        train_end = first_issue - pd.Timedelta(days=get(cfg, "splits.purge_gap_days"))
        folds.append(Fold(i + 1, start.tz_convert("UTC"), train_end.tz_convert("UTC"),
                          (train_end - pd.Timedelta(weeks=get(cfg, "splits.early_stopping_weeks"))).tz_convert("UTC"),
                          test_start.tz_convert("UTC"), test_end.tz_convert("UTC")))
    return SplitPlan(start.tz_convert("UTC"), tuning_end.tz_convert("UTC"),
                     holdout_start.tz_convert("UTC"), end.tz_convert("UTC"), tuple(folds))


def measured_mask(frame: pd.DataFrame) -> pd.Series:
    """Unknown flags are unscorable, as are nonpositive or missing targets."""
    return (~frame.is_estimated.fillna(True).astype(bool)
            & frame.demand_mw.notna() & (frame.demand_mw > 0))
