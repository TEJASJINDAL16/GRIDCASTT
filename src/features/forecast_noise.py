"""The constant-sigma bridge from observed to approximate forecast weather (5d)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import get


def simulate_forecast_weather(weather: pd.DataFrame, cfg: dict,
                              *, stream: int = 0) -> pd.DataFrame:
    """Copy raw weather, adding a city/day bias and hourly temperature wobble.

    Call before build_features, so cooling degrees reflect the perturbed raw
    temperatures. These are assumed errors, not reconstructed real forecasts.
    Sorting makes the draw independent of the caller's row order.
    """
    out = weather.copy()
    if not get(cfg, "forecast_noise.enabled"):
        return out
    sigmas = [get(cfg, "forecast_noise.day_bias_sigma_c"),
              get(cfg, "forecast_noise.hour_wobble_sigma_c")]
    if any(not np.isfinite(s) or s < 0 for s in sigmas):
        raise ValueError("forecast-noise sigmas must be finite and nonnegative")
    required = ["zone", "point_name", "datetime_utc", "temperature_2m"]
    if out[required].isna().any().any():
        raise ValueError("forecast-noise inputs contain nulls")
    ordered = out.sort_values(["zone", "point_name", "datetime_utc"])
    local_date = ordered.datetime_utc.dt.tz_convert(get(cfg, "project.timezone")).dt.date
    groups = pd.MultiIndex.from_arrays([ordered.zone, ordered.point_name, local_date])
    group_ids, unique = pd.factorize(groups)
    rng = np.random.default_rng(np.random.SeedSequence([get(cfg, "train.seed"), stream]))
    bias = rng.normal(0, sigmas[0], len(unique))
    wobble = rng.normal(0, sigmas[1], len(ordered))
    out.loc[ordered.index, "temperature_2m"] = (
        ordered.temperature_2m.to_numpy() + bias[group_ids] + wobble
    )
    return out
