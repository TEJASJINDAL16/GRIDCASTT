"""Demand-history candidates with issue-time-bounded measured observations."""

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.backtest.splits import measured_mask


class DemandHistory:
    """Retrieve comparable hours before the same availability cutoff as the baseline."""

    def __init__(self, history, cfg):
        self.gap = pd.Timedelta(days=cfg["splits"]["purge_gap_days"])
        self.count = cfg["refinement"]["history_count"]
        self.groups = {}
        measured = history.loc[measured_mask(history)].sort_values("datetime_utc")
        for key, rows in measured.groupby(["zone", "hour_of_day", "day_of_week"], observed=True):
            self.groups[key] = rows.reset_index(drop=True)

    def transform(self, frame):
        out = frame[
            ["temperature", "cooling_degrees", "hour_of_day", "day_of_week", "is_holiday", "zone"]
        ].copy()
        out["baseline_mw"] = np.nan
        out["source_datetime"] = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
        for k in range(self.count):
            out[f"lag_{k}"] = np.nan
        out["temperature_change"] = np.nan
        for key, query in frame.groupby(["zone", "hour_of_day", "day_of_week"], observed=True):
            history = self.groups.get(key)
            if history is None:
                continue
            times = history.datetime_utc.dt.as_unit("ns").astype("int64").to_numpy()
            cutoff = (query.issued_at - self.gap).dt.as_unit("ns").astype("int64").to_numpy()
            index = np.searchsorted(times, cutoff, side="right") - 1
            for k in range(self.count):
                valid = index >= k
                out.loc[query.index[valid], f"lag_{k}"] = history.demand_mw.to_numpy()[
                    index[valid] - k
                ]
            valid = index >= 0
            out.loc[query.index[valid], "source_datetime"] = pd.to_datetime(
                times[index[valid]], utc=True
            )
            out.loc[query.index[valid], "temperature_change"] = (
                query.temperature.to_numpy()[valid] - history.temperature.to_numpy()[index[valid]]
            )
        out["baseline_mw"] = out.lag_0
        for k in range(self.count):
            out[f"ratio_{k}"] = out[f"lag_{k}"] / out.baseline_mw
        out["source_age_days"] = (frame.issued_at - out.source_datetime).dt.total_seconds() / 86400
        if (out.source_datetime > frame.issued_at - self.gap).any():
            raise AssertionError("Demand history crossed the availability cutoff")
        return out


class HistoryResidual:
    """Learn a multiplicative correction to the available seasonal baseline."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.columns = [
            "temperature",
            "cooling_degrees",
            "temperature_change",
            "hour_of_day",
            "day_of_week",
            "is_holiday",
            "zone",
            "source_age_days",
        ] + [f"ratio_{k}" for k in range(1, cfg["refinement"]["history_count"])]

    def fit(self, features, targets):
        valid = features.baseline_mw.gt(0) & targets.gt(0)
        self.model = None
        if valid.sum() >= self.cfg["refinement"]["minimum_training_rows"]:
            self.model = lgb.LGBMRegressor(
                **self.cfg["refinement"]["lightgbm"],
                random_state=self.cfg["train"]["seed"],
                n_jobs=self.cfg["runtime"]["threads"],
                verbosity=-1,
                deterministic=True,
                force_col_wise=True,
            )
            self.model.fit(
                features.loc[valid, self.columns],
                np.log(targets.loc[valid] / features.loc[valid, "baseline_mw"]),
            )
        return self

    def predict(self, features):
        out = features.baseline_mw.copy()
        valid = out.gt(0)
        if self.model is not None:
            out.loc[valid] *= np.exp(self.model.predict(features.loc[valid, self.columns]))
        return out


class AdaptiveHistory:
    """Choose a smoothing window per zone using only earlier measured targets."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.windows = cfg["refinement"]["averaging_windows"]
        self.selected = {}

    def fit(self, features, targets):
        for zone, frame in features.groupby("zone", observed=True):
            valid = frame.baseline_mw.gt(0) & targets.loc[frame.index].gt(0)
            frame = frame.loc[valid]
            if len(frame) < self.cfg["refinement"]["minimum_training_rows"]:
                self.selected[str(zone)] = 1
                continue
            losses = {
                k: (frame[[f"lag_{i}" for i in range(k)]].mean(axis=1) - targets.loc[frame.index])
                .abs()
                .mean()
                for k in self.windows
            }
            self.selected[str(zone)] = min(losses, key=losses.get)
        return self

    def predict(self, features):
        result = features.baseline_mw.copy()
        for zone, frame in features.groupby("zone", observed=True):
            k = self.selected.get(str(zone), 1)
            result.loc[frame.index] = frame[[f"lag_{i}" for i in range(k)]].mean(axis=1)
        return result


class SeasonalAverage:
    """Predict from the latest two eligible comparable observations.

    Refresh the supplied history at each issue; model fitting is unnecessary.
    A single available observation falls back to the original seasonal baseline.
    Missing history produces an explicit missing prediction, never another zone's load.
    """

    def __init__(self, cfg, window=2):
        if window not in cfg["refinement"]["averaging_windows"]:
            raise ValueError("Unknown demand averaging window")
        self.cfg, self.window = cfg, window

    def fit(self, history):
        self.history = DemandHistory(history, self.cfg)
        return self

    def predict(self, frame):
        features = self.history.transform(frame)
        result = features[[f"lag_{k}" for k in range(self.window)]].mean(axis=1)
        return pd.DataFrame({"prediction_mw": result, "source_datetime": features.source_datetime})
