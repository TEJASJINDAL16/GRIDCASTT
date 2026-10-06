"""Four fixed baselines; no production hybrid and no hyperparameter search."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src.backtest.splits import measured_mask
from src.config import get
from src.features.build import FEATURE_COLUMNS, feature_matrix

BASELINE_NAMES = ("seasonal_naive", "hour_weekday_mean", "ridge_all", "per_zone_ridge")
CATEGORICAL = ["hour_of_day", "day_of_week", "zone"]
NUMERIC = [c for c in FEATURE_COLUMNS if c not in CATEGORICAL]


class SeasonalNaive:
    """Most recent measured matching zone/hour/weekday, settled before issue."""

    def __init__(self, cfg: dict):
        self.gap = pd.Timedelta(days=get(cfg, "splits.purge_gap_days"))
        self.history: dict = {}

    def fit(self, history: pd.DataFrame) -> SeasonalNaive:
        measured = history.loc[measured_mask(history)].sort_values("datetime_utc")
        for group, rows in measured.groupby(CATEGORICAL, observed=True):
            self.history[group] = (rows.datetime_utc.dt.as_unit("ns").astype("int64").to_numpy(),
                                   rows.demand_mw.to_numpy())
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        predictions = pd.Series(np.nan, index=frame.index)
        source = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns, UTC]")
        for group, rows in frame.groupby(CATEGORICAL, observed=True):
            if group not in self.history:
                continue
            timestamps, values = self.history[group]
            cutoff = (rows.issued_at - self.gap).dt.as_unit("ns").astype("int64").to_numpy()
            matches = np.searchsorted(timestamps, cutoff, side="right") - 1
            valid = matches >= 0
            idx = rows.index[valid]
            predictions.loc[idx] = values[matches[valid]]
            source.loc[idx] = pd.to_datetime(timestamps[matches[valid]], utc=True)
        return pd.DataFrame({"prediction_mw": predictions, "source_datetime": source})


class HourWeekdayMean:
    """Arithmetic historical mean per zone/hour/weekday; fitted once per fold."""

    def fit(self, frame: pd.DataFrame) -> HourWeekdayMean:
        self.means = frame.groupby(CATEGORICAL, observed=True).demand_mw.mean()
        self.zone_means = frame.groupby("zone", observed=True).demand_mw.mean()
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        index = pd.MultiIndex.from_frame(frame[CATEGORICAL])
        values = self.means.reindex(index).to_numpy()
        fallback = frame.zone.map(self.zone_means).astype("float64").to_numpy()
        return pd.Series(np.where(np.isnan(values), fallback, values), index=frame.index)


class RidgeBaseline:
    """Log-target Ridge with categorical calendar slots and per-zone smearing.

    The per-zone variant changes pooling alone. Missing training zones abstain
    rather than borrowing another zone's demand level without evidence.
    """

    def __init__(self, cfg: dict, *, per_zone: bool = False):
        self.cfg = cfg
        self.per_zone = per_zone
        if per_zone and get(cfg, "baselines.per_zone_model") != "ridge":
            raise ValueError("Stage 2's configured per-zone baseline must be ridge")
        self.models: dict = {}
        self.smearing: dict = {}

    def _fit_one(self, frame: pd.DataFrame, weights: np.ndarray):
        encoder = ColumnTransformer([
            ("calendar", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
            ("numeric", StandardScaler() if get(self.cfg, "train.ridge.standardize") else "passthrough", NUMERIC),
        ])
        model = make_pipeline(encoder, Ridge(alpha=get(self.cfg, "baselines.ridge_alpha"),
                                            fit_intercept=get(self.cfg, "train.ridge.fit_intercept")))
        X = feature_matrix(frame)
        y = np.log(frame.demand_mw.to_numpy())
        model.fit(X, y, ridge__sample_weight=weights)
        residual = y - model.predict(X)
        for zone, indices in frame.groupby("zone", observed=True).indices.items():
            self.smearing[zone] = float(np.mean(np.exp(residual[indices])))
        return model

    def fit(self, frame: pd.DataFrame, *, train_end: pd.Timestamp) -> RidgeBaseline:
        if frame.empty or (frame.demand_mw <= 0).any():
            raise ValueError("Ridge requires positive training targets")
        age = (train_end - frame.datetime_utc).dt.total_seconds().to_numpy() / 86400
        weights = 0.5 ** (age / get(self.cfg, "train.recency_half_life_days"))
        if self.per_zone:
            for zone, indices in frame.groupby("zone", observed=True).indices.items():
                self.models[zone] = self._fit_one(frame.iloc[indices], weights[indices])
        else:
            self.models["pooled"] = self._fit_one(frame, weights)
        return self

    def predict(self, frame: pd.DataFrame) -> pd.Series:
        out = pd.Series(np.nan, index=frame.index)
        for zone, rows in frame.groupby("zone", observed=True):
            if rows.empty or zone not in self.smearing:
                continue
            model = self.models[zone if self.per_zone else "pooled"]
            out.loc[rows.index] = np.exp(model.predict(feature_matrix(rows))) * self.smearing[zone]
        return out
