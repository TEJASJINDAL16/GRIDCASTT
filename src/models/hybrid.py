"""A linear temperature/trend forecast plus a tree correction, in log MW."""

from __future__ import annotations

import math

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from src.config import get
from src.features.build import FEATURE_COLUMNS, trainable_mask


class Hybrid:
    def __init__(self, cfg: dict, *, excluded: tuple[str, ...] = ()):
        self.cfg = cfg
        self.columns = [c for c in FEATURE_COLUMNS if c not in excluded]
        if cfg["features"].get("candidate_day_of_year", False):
            self.columns += ["day_of_year_sin", "day_of_year_cos"]
        self.linear_columns = [
            c for c in get(cfg, "features.linear_stage_features") if c not in excluded
        ]

    def _weights(self, frame):
        days = (self.train_end - frame.datetime_utc).dt.total_seconds().to_numpy() / 86400
        return 0.5 ** (days / get(self.cfg, "train.recency_half_life_days"))

    def _linear_input(self, frame):
        values = frame[self.linear_columns].astype(float).copy()
        if get(self.cfg, "features.clamp_linear_below"):
            values = values.clip(lower=self.minimum, axis=1)
        return values

    def _fit_linear(self, frame):
        self.minimum = frame[self.linear_columns].min()
        self.linear = make_pipeline(
            StandardScaler() if get(self.cfg, "train.ridge.standardize") else "passthrough",
            Ridge(
                alpha=get(self.cfg, "train.ridge.alpha"),
                fit_intercept=get(self.cfg, "train.ridge.fit_intercept"),
            ),
        )
        self.linear.fit(
            self._linear_input(frame),
            np.log(frame.demand_mw),
            ridge__sample_weight=self._weights(frame),
        )

    def _tree(self, iterations):
        params = dict(get(self.cfg, "train.lightgbm"))
        if any(v is None for v in params.values()):
            raise ValueError("hybrid parameters are not frozen; run tuning first")
        return lgb.LGBMRegressor(
            **params,
            objective="regression",
            n_estimators=iterations,
            random_state=get(self.cfg, "train.seed"),
            n_jobs=get(self.cfg, "runtime.threads"),
            verbosity=-1,
            bagging_freq=1,
            deterministic=True,
            force_col_wise=True,
            monotone_constraints=[
                int(c in get(self.cfg, "features.monotone_increasing")) for c in self.columns
            ],
        )

    def fit(self, frame: pd.DataFrame, *, train_end: pd.Timestamp):
        self.train_end = pd.Timestamp(train_end)
        frame = frame.loc[trainable_mask(frame, self.cfg)].sort_values("datetime_utc").copy()
        if frame.empty or (frame.datetime_utc >= self.train_end).any():
            raise ValueError("training requires eligible rows strictly before train_end")
        boundary = self.train_end - pd.Timedelta(weeks=get(self.cfg, "splits.early_stopping_weeks"))
        early, validation = (
            frame.loc[frame.datetime_utc < boundary],
            frame.loc[frame.datetime_utc >= boundary],
        )
        if early.empty or validation.empty:
            raise ValueError("insufficient chronological history for early stopping")
        self._fit_linear(early)
        tree = self._tree(get(self.cfg, "runtime.max_boost_rounds"))
        tree.fit(
            early[self.columns],
            np.log(early.demand_mw) - self.linear.predict(self._linear_input(early)),
            sample_weight=self._weights(early),
            eval_set=[
                (
                    validation[self.columns],
                    np.log(validation.demand_mw)
                    - self.linear.predict(self._linear_input(validation)),
                )
            ],
            eval_sample_weight=[self._weights(validation)],
            callbacks=[
                lgb.early_stopping(get(self.cfg, "runtime.early_stopping_rounds"), verbose=False)
            ],
        )
        self.best_iteration = tree.best_iteration_
        if self.best_iteration >= get(self.cfg, "runtime.max_boost_rounds"):
            raise ValueError(
                "early stopping reached the iteration ceiling; the count is not identified. "
                "Widen runtime.max_boost_rounds before accepting this fit."
            )
        self.iterations = math.ceil(self.best_iteration * len(frame) / len(early))
        self._fit_linear(frame)
        self.tree = self._tree(self.iterations)
        residual = np.log(frame.demand_mw) - self.linear.predict(self._linear_input(frame))
        self.tree.fit(frame[self.columns], residual, sample_weight=self._weights(frame))
        residual -= self.tree.predict(frame[self.columns])
        self.smearing = np.exp(residual).groupby(frame.zone, observed=True).mean().to_dict()
        self.loss_by_zone = (
            residual.pow(2)
            .groupby(frame.zone, observed=True)
            .agg(["sum", "mean", "size"])
            .to_dict("index")
        )
        checks = get(self.cfg, "features.extrapolation_check")
        self.ranges = {
            str(zone): rows[checks].agg(["min", "max"]).to_dict()
            for zone, rows in frame.groupby("zone", observed=True)
        }
        return self

    def predict(self, frame):
        log_mw = self.linear.predict(self._linear_input(frame)) + self.tree.predict(
            frame[self.columns]
        )
        smear = frame.zone.map(self.smearing).astype(float)
        return pd.Series(np.exp(log_mw) * smear.to_numpy(), index=frame.index)

    def flags(self, frame):
        result = []
        for _, row in frame.iterrows():
            limits = self.ranges.get(str(row.zone), {})
            outside = any(row[c] < limits[c]["min"] or row[c] > limits[c]["max"] for c in limits)
            result.append(["extrapolating"] if outside else [])
        return result
