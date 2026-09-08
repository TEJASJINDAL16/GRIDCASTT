"""Weather-derived features: the temperature ramp, and zone aggregation.

PLANNING 5e. Two rules, and the second is the one that bites.

  **RULE** `cooling_degrees = max(0, T - features.temp_breakpoint_c)`.

  **RULE** Compute `cooling_degrees` PER CITY, then aggregate to the zone,
  load-weighted. Never average temperature first and transform after.

The second is inert as Phase 1 is configured — one weather point per zone, so
there is nothing to aggregate — and it is implemented properly anyway, because
it stops being inert the moment a second city is added and retrofitting it then
would silently change every temperature feature in the project.

Why it matters: `max(0, .)` is nonlinear, so the transform of the average is
not the average of the transforms. With the breakpoint at 21.5, Delhi at 40 C
and Shimla at 20 C average to 30 C, giving 8.5 cooling degrees; the correct
equal-weighted answer is 9.25, and higher still once Delhi's far larger load is
weighted in. The error is largest on the hottest days, which is exactly where
it matters most.

`heating_degrees` is deliberately absent. See 5e — the U-shape it rested on was
disproved in stage 1.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import get

log = logging.getLogger(__name__)

TEMP_COLUMN = "temperature_2m"


def cooling_degrees(temperature: pd.Series | np.ndarray,
                    breakpoint_c: float) -> np.ndarray:
    """`max(0, T - breakpoint)`, the ramp that steepens the slope above it.

    Not an elbow above which cooling begins: demand rises with temperature
    across the whole observed range, and this is where an already-positive
    slope steepens (13). The name is historical; the shape is measured.
    """
    return np.maximum(0.0, np.asarray(temperature, dtype=float) - breakpoint_c)


def _weights_for(zone: str, cities: list[str], cfg: dict) -> np.ndarray:
    """Load weights for a zone's cities. Absent means equal."""
    configured = get(cfg, "weather.load_weights") or {}
    zone_weights = configured.get(zone) or {}
    if not zone_weights:
        return np.full(len(cities), 1.0 / len(cities))
    missing = [c for c in cities if c not in zone_weights]
    if missing:
        raise KeyError(
            f"weather.load_weights[{zone}] has no weight for {missing}. "
            "Partial weights would silently fall back to equal weighting for "
            "the rest, which is not a decision anyone made."
        )
    w = np.array([float(zone_weights[c]) for c in cities])
    if w.sum() <= 0:
        raise ValueError(f"weather.load_weights[{zone}] sums to {w.sum()}")
    return w / w.sum()


def add_city_features(weather: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per-city derived columns. Must run BEFORE any aggregation."""
    if TEMP_COLUMN not in weather.columns:
        raise KeyError(f"weather frame has no {TEMP_COLUMN} column")
    out = weather.copy()
    out["cooling_degrees"] = cooling_degrees(
        out[TEMP_COLUMN], get(cfg, "features.temp_breakpoint_c"))
    return out


def aggregate_to_zone(city_features: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Load-weighted average of already-transformed per-city columns.

    Averages `cooling_degrees` itself, never re-deriving it from an averaged
    temperature. `temperature` is averaged too, because the tree uses raw
    temperature and a zone needs one value for it — but the ramp does not come
    from that average.
    """
    required = {"datetime_utc", "zone", "point_name", TEMP_COLUMN, "cooling_degrees"}
    missing = required - set(city_features.columns)
    if missing:
        raise KeyError(f"cannot aggregate, missing {sorted(missing)}")

    frames = []
    for zone, g in city_features.groupby("zone", observed=True):
        cities = sorted(g["point_name"].unique())
        weights = dict(zip(cities, _weights_for(zone, cities, cfg), strict=True))
        if len(cities) > 1:
            log.info("zone %s: aggregating %d cities with weights %s",
                     zone, len(cities), weights)
        g = g.assign(_w=g["point_name"].map(weights))
        g["_wt"] = g[TEMP_COLUMN] * g["_w"]
        g["_wc"] = g["cooling_degrees"] * g["_w"]
        agg = g.groupby("datetime_utc", observed=True).agg(
            _wt=("_wt", "sum"), _wc=("_wc", "sum"), _w=("_w", "sum"))
        out = pd.DataFrame({
            "datetime_utc": agg.index,
            "zone": zone,
            TEMP_COLUMN: (agg["_wt"] / agg["_w"]).to_numpy(),
            "cooling_degrees": (agg["_wc"] / agg["_w"]).to_numpy(),
        })
        frames.append(out)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["zone", "datetime_utc"]).reset_index(drop=True)


def weather_features(weather: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per-city transform, then zone aggregation — in that order, always."""
    return aggregate_to_zone(add_city_features(weather, cfg), cfg)
