"""THE feature builder. Training and serving both call this, and nothing else.

**INV-9.** A second implementation drifts from the first, and the model is then
served inputs subtly unlike the ones it learned from, with nothing erroring.
Enforced by the contract test in CI.

The two paths differ in exactly one way, and it is not a feature:

    training   observed weather (archive API) + a demand target
    serving    forecast weather (forecast API) + no target

Both produce `FEATURE_COLUMNS`, in that order, with those dtypes. The target is
attached alongside when it exists; it is never part of the feature contract.

The core set is 5e's, unchanged: hour_of_day, day_of_week, is_holiday,
temperature, cooling_degrees, trend, zone. Everything else — day-of-year,
humidity, rolling temperatures, the rest — is an ablation candidate and does
not belong here until it has earned its place.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.config import get
from src.features.weather_feats import TEMP_COLUMN, weather_features
from src.ingest.calendar_in import calendar_frame

log = logging.getLogger(__name__)

# The contract. Order is part of it.
FEATURE_COLUMNS = [
    "hour_of_day",
    "day_of_week",
    "is_holiday",
    "temperature",
    "cooling_degrees",
    "trend",
    "zone",
]

# Consumed by the Ridge stage. A subset of the above, per 5c.
LINEAR_COLUMNS = ["temperature", "cooling_degrees", "trend"]

FEATURE_DTYPES = {
    "hour_of_day": "int16",
    "day_of_week": "int8",
    "is_holiday": "bool",
    "temperature": "float64",
    "cooling_degrees": "float64",
    "trend": "float64",
    "zone": "category",
}

TARGET_COLUMN = "demand_mw"
# Carried alongside the features for scoring and stratification. Never inputs.
CONTEXT_COLUMNS = ["datetime_utc", "datetime_ist", "date_ist", "day_type"]


def _trend_days(ist_dates: pd.Series, cfg: dict) -> pd.Series:
    """Days since `demand.backfill_start`, fixed origin.

    **RULE (5e):** the origin never moves once training has begun. Every
    LightGBM split on `trend` is an absolute number, so shifting the origin
    leaves a tree splitting at a value that now means a different date, with
    nothing erroring.
    """
    origin = pd.Timestamp(get(cfg, "demand.backfill_start")).date()
    return pd.Series(
        [(d - origin).days for d in ist_dates], index=ist_dates.index, dtype="float64"
    )


def _zone_categorical(zones: pd.Series, cfg: dict) -> pd.Categorical:
    """Zone as a native categorical with the FULL, config-ordered category set.

    Not inferred from the rows present. A serving call covering one zone must
    still produce the same categories in the same order as training, or
    LightGBM's categorical codes mean different things on the two paths — which
    is INV-9's failure exactly, and it does not raise.
    """
    return pd.Categorical(zones, categories=list(get(cfg, "demand.all_zones")))


def build_features(
    weather: pd.DataFrame,
    cfg: dict,
    demand: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Raw inputs to a feature matrix. The only path (INV-9).

    `weather` is per-city rows carrying datetime_utc, zone, point_name and
    temperature_2m — from the archive API for training, the forecast API for
    serving. `demand` attaches the target and is omitted when serving.
    """
    zonal = weather_features(weather, cfg)

    if demand is not None:
        keep = [c for c in ("datetime_utc", "zone", TARGET_COLUMN, "is_estimated",
                            "estimation_method") if c in demand.columns]
        zonal = zonal.merge(demand[keep], on=["datetime_utc", "zone"], how="inner")

    calendar = calendar_frame(zonal["datetime_utc"], zonal["zone"], cfg)

    out = pd.DataFrame(index=zonal.index)
    out["hour_of_day"] = calendar["hour_of_day"]
    out["day_of_week"] = calendar["day_of_week"]
    out["is_holiday"] = calendar["is_holiday"]
    out["temperature"] = zonal[TEMP_COLUMN].astype("float64")
    out["cooling_degrees"] = zonal["cooling_degrees"].astype("float64")
    out["trend"] = _trend_days(calendar["date_ist"], cfg)
    out["zone"] = _zone_categorical(zonal["zone"], cfg)

    out = out[FEATURE_COLUMNS].astype(FEATURE_DTYPES)

    out["datetime_utc"] = zonal["datetime_utc"].to_numpy()
    out["datetime_ist"] = calendar["datetime_ist"].to_numpy()
    out["date_ist"] = calendar["date_ist"].to_numpy()
    out["day_type"] = calendar["day_type"]

    if demand is not None:
        out[TARGET_COLUMN] = zonal[TARGET_COLUMN].to_numpy()
        for col in ("is_estimated", "estimation_method"):
            if col in zonal.columns:
                out[col] = zonal[col].to_numpy()

    return out.reset_index(drop=True)


def feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Just the features, in contract order. What a model is ever handed."""
    return frame[FEATURE_COLUMNS]


def trainable_mask(frame: pd.DataFrame, cfg: dict) -> pd.Series:
    """Rows INV-3 permits training on.

    Two filters, both from config so the decision is versioned rather than
    buried in code:

      `quality.trainable_estimation_methods`  the allowlist. The bare
          is_estimated flag is not sufficient — the source uses three
          estimation methods and they are not equivalent (11).

      `quality.trainable_from`  per-zone start dates, from the stage 1
          relationship test: the temperature slope moves across the estimation
          switch in IN-NE and IN-EA by more than those zones' placebo bands.

    5c requires this to run BEFORE splitting, never after.
    """
    allowed = set(get(cfg, "quality.trainable_estimation_methods"))
    if "estimation_method" not in frame.columns:
        raise KeyError(
            "estimation_method is absent, so INV-3 cannot be enforced. "
            "Refusing to guess that every row is trainable."
        )

    method = frame["estimation_method"]
    measured = method.isna()
    if "is_estimated" in frame.columns:
        measured = measured & ~frame["is_estimated"].fillna(True).astype(bool)

    ok = measured if "MEASURED" in allowed else pd.Series(False, index=frame.index)
    ok = ok | method.isin(allowed - {"MEASURED"})

    for zone, start in (get(cfg, "quality.trainable_from") or {}).items():
        cutoff = pd.Timestamp(start, tz="UTC")
        ok &= ~((frame["zone"] == zone) & (frame["datetime_utc"] < cutoff))

    ok &= frame[TARGET_COLUMN].notna() & (frame[TARGET_COLUMN] > 0)
    return ok
