"""Check a zone-composition correction on reserved pre-test targets only.

The correction still uses the same three linear features. Training-only zone
centering estimates slopes within zones so changes in their sample proportions
cannot masquerade as a time trend. The residual tree still carries zone levels.
This diagnostic does not modify production parameters or touch the holdout.
"""

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.backtest.run import load_cached
from src.backtest.splits import issue_times, measured_mask
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.features.forecast_noise import simulate_forecast_weather
from src.models.baselines import SeasonalNaive
from src.models.hybrid import Hybrid
from src.records import write_json


class ZoneCenteredHybrid(Hybrid):
    def _fit_linear(self, frame):
        super()._fit_linear(frame)
        x = self._linear_input(frame)
        y = np.log(frame.demand_mw)
        weights = pd.Series(self._weights(frame), index=frame.index)
        zone_weight = weights.groupby(frame.zone, observed=True).sum()
        x_mean = (
            x.mul(weights, axis=0).groupby(frame.zone, observed=True).sum().div(zone_weight, axis=0)
        )
        y_mean = y.mul(weights).groupby(frame.zone, observed=True).sum() / zone_weight
        centered_x = x - x_mean.reindex(frame.zone.to_numpy()).set_axis(x.index)
        centered_y = y - frame.zone.map(y_mean).astype(float)
        self.linear.fit(centered_x, centered_y, ridge__sample_weight=weights.to_numpy())
        # Restore an overall level; serving continues to accept the raw inputs.
        shift = np.average(y - self.linear.predict(x), weights=weights)
        self.linear.named_steps["ridge"].intercept_ += shift


def main():
    root, cfg = PROJECT_ROOT, load_config()
    study = json.loads((root / "reports/tuning/result.json").read_text(encoding="utf-8"))
    cutoff = pd.Timestamp(study["train_end"])
    end, start = pd.Timestamp(study["validation_end"]), pd.Timestamp(study["validation_start"])
    demand, weather = load_cached(root, cfg)
    actual = build_features(weather.loc[weather.datetime_utc < end], cfg, demand=demand)
    measured = actual.loc[(actual.datetime_utc >= start) & measured_mask(actual)].copy()
    measured["issued_at"] = issue_times(measured.datetime_utc, cfg)
    naive = SeasonalNaive(cfg).fit(actual).predict(measured).prediction_mw
    measured = measured.loc[np.isfinite(naive)]
    denominator = np.abs(measured.demand_mw - naive.loc[measured.index]).sum()
    noisy = simulate_forecast_weather(weather.loc[weather.datetime_utc < end], cfg, stream=0)
    test = build_features(noisy, cfg).merge(
        measured[["zone", "datetime_utc", "demand_mw"]],
        on=["zone", "datetime_utc"],
        validate="one_to_one",
    )
    train = pd.read_parquet(root / "data/interim/tuning_training.parquet")
    model = ZoneCenteredHybrid(cfg).fit(train, train_end=cutoff)
    prediction = model.predict(test)
    assert np.isfinite(prediction).all()
    result = {
        "validation_start": str(start),
        "validation_end": str(end),
        "n_rows": len(test),
        "zones": sorted(test.zone.unique().tolist()),
        "current_mase": study.get("iteration_convergence_correction", {}).get(
            "selected_validation_mase_after_convergence", study["best_mase"]
        ),
        "zone_centered_mase": float(np.abs(prediction - test.demand_mw).sum() / denominator),
        "uses_test_folds": False,
        "uses_holdout": False,
        "best_iteration": model.best_iteration,
        "refit_iterations": model.iterations,
    }
    write_json(root / "reports/linear_validation_diagnostic.json", result)
    print(result)


if __name__ == "__main__":
    main()
