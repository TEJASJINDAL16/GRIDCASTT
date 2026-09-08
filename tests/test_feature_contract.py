"""The train/serve feature contract (INV-9, PLANNING 14).

Two feature paths is how train/serve skew gets into a system. When they drift
apart the model is served inputs subtly unlike the ones it learned from, and
nothing errors — the forecast is simply wrong, plausibly.

This is the test section 14 names as the substitute for a feature store. The
property a feature store exists to provide is delivered by INV-9's single
module plus this assertion.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.build import (
    CONTEXT_COLUMNS,
    FEATURE_COLUMNS,
    FEATURE_DTYPES,
    LINEAR_COLUMNS,
    TARGET_COLUMN,
    build_features,
    feature_matrix,
    trainable_mask,
)


@pytest.fixture
def training_inputs(cfg):
    """Observed weather plus a demand target — the training path."""
    stamps = pd.date_range("2024-05-01", periods=72, freq="h", tz="UTC")
    weather = pd.DataFrame({
        "datetime_utc": np.tile(stamps, 2),
        "zone": ["IN-NO"] * 72 + ["IN-SO"] * 72,
        "point_name": ["Delhi"] * 72 + ["Bengaluru"] * 72,
        "temperature_2m": np.concatenate([
            30 + 8 * np.sin(np.arange(72) / 24 * 2 * np.pi),
            24 + 4 * np.sin(np.arange(72) / 24 * 2 * np.pi)]),
    })
    demand = pd.DataFrame({
        "datetime_utc": np.tile(stamps, 2),
        "zone": ["IN-NO"] * 72 + ["IN-SO"] * 72,
        "demand_mw": np.concatenate([np.full(72, 55000.0), np.full(72, 38000.0)]),
        "is_estimated": [False] * 144,
        "estimation_method": [None] * 144,
    })
    return weather, demand


@pytest.fixture
def serving_inputs(cfg):
    """Forecast weather, no target — the serving path.

    One zone only, and a different column set, because that is what a real
    serving call looks like: 24 hours for the zones that responded.
    """
    stamps = pd.date_range("2026-09-10", periods=24, freq="h", tz="UTC")
    return pd.DataFrame({
        "datetime_utc": stamps,
        "zone": ["IN-NO"] * 24,
        "point_name": ["Delhi"] * 24,
        "temperature_2m": 32 + 6 * np.sin(np.arange(24) / 24 * 2 * np.pi),
        "relative_humidity_2m": np.full(24, 55.0),      # extra column, ignored
    })


# --- the contract itself ---------------------------------------------------

def test_column_names_and_order_are_identical(cfg, training_inputs, serving_inputs):
    weather, demand = training_inputs
    train = feature_matrix(build_features(weather, cfg, demand))
    serve = feature_matrix(build_features(serving_inputs, cfg))
    assert list(train.columns) == list(serve.columns) == FEATURE_COLUMNS


def test_dtypes_are_identical(cfg, training_inputs, serving_inputs):
    weather, demand = training_inputs
    train = feature_matrix(build_features(weather, cfg, demand))
    serve = feature_matrix(build_features(serving_inputs, cfg))
    assert train.dtypes.astype(str).to_dict() == serve.dtypes.astype(str).to_dict()
    assert train.dtypes.astype(str).to_dict() == {
        k: str(pd.Series(dtype=v).dtype) for k, v in FEATURE_DTYPES.items()}


def test_zone_categories_match_even_when_serving_one_zone(cfg, training_inputs,
                                                          serving_inputs):
    """The subtle one. Serving covers a single zone; if its categorical were
    inferred from the rows present, LightGBM's integer codes would mean
    different zones on the two paths, silently."""
    weather, demand = training_inputs
    train = feature_matrix(build_features(weather, cfg, demand))
    serve = feature_matrix(build_features(serving_inputs, cfg))
    assert serve["zone"].nunique() == 1
    assert list(train["zone"].cat.categories) == list(serve["zone"].cat.categories)
    assert list(serve["zone"].cat.categories) == list(cfg["demand"]["all_zones"])


def test_the_target_is_not_a_feature(cfg, training_inputs):
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand)
    assert TARGET_COLUMN in built.columns
    assert TARGET_COLUMN not in FEATURE_COLUMNS
    assert TARGET_COLUMN not in feature_matrix(built).columns


def test_serving_produces_no_target(cfg, serving_inputs):
    built = build_features(serving_inputs, cfg)
    assert TARGET_COLUMN not in built.columns


def test_context_columns_are_present_but_not_features(cfg, training_inputs):
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand)
    for col in CONTEXT_COLUMNS:
        assert col in built.columns
        assert col not in FEATURE_COLUMNS


def test_linear_columns_are_a_subset_of_the_contract():
    """5c: the Ridge stage sees three features; LightGBM sees everything."""
    assert set(LINEAR_COLUMNS) <= set(FEATURE_COLUMNS)
    assert LINEAR_COLUMNS == ["temperature", "cooling_degrees", "trend"]


def test_no_heating_degrees_anywhere():
    assert not any("heating" in c for c in FEATURE_COLUMNS)


def test_day_of_year_is_not_in_the_core_set():
    """It is a stage 3 ablation candidate, deliberately not core (5e)."""
    assert not any("day_of_year" in c or "doy" in c for c in FEATURE_COLUMNS)


# --- feature correctness ---------------------------------------------------

def test_hours_are_ist_not_utc(cfg, training_inputs):
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand)
    row = built[built["datetime_utc"] == pd.Timestamp("2024-05-01 19:00", tz="UTC")]
    assert (row["hour_of_day"] == 0).all()


def test_trend_is_days_since_the_configured_origin(cfg, training_inputs):
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand)
    origin = pd.Timestamp(cfg["demand"]["backfill_start"]).date()
    first = built.iloc[0]
    assert first["trend"] == pytest.approx((first["date_ist"] - origin).days)


def test_trend_is_identical_across_zones_at_the_same_instant(cfg, training_inputs):
    """It is a time feature, not a zone feature."""
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand)
    per_stamp = built.groupby("datetime_utc")["trend"].nunique()
    assert (per_stamp == 1).all()


# --- INV-3 filtering -------------------------------------------------------

def test_trainable_mask_refuses_to_guess_without_the_method_column(cfg,
                                                                  training_inputs):
    weather, demand = training_inputs
    built = build_features(weather, cfg, demand).drop(columns=["estimation_method"])
    with pytest.raises(KeyError, match="INV-3 cannot be enforced"):
        trainable_mask(built, cfg)


def test_trainable_mask_excludes_disallowed_methods(cfg, training_inputs):
    weather, demand = training_inputs
    demand = demand.copy()
    demand.loc[:10, "estimation_method"] = "TIME_SLICER_AVERAGE"
    demand.loc[:10, "is_estimated"] = True
    built = build_features(weather, cfg, demand)
    mask = trainable_mask(built, cfg)
    excluded = built[~mask]
    assert (excluded["estimation_method"] == "TIME_SLICER_AVERAGE").any()
    assert "TIME_SLICER_AVERAGE" not in set(built[mask]["estimation_method"].dropna())


def test_trainable_mask_honours_per_zone_starts(cfg):
    """IN-NE and IN-EA carry later starts from the stage 1 relationship test."""
    starts = cfg["quality"]["trainable_from"]
    assert starts, "per-zone starts must be configured"
    zone = next(iter(starts))
    cutoff = pd.Timestamp(starts[zone], tz="UTC")
    early = cutoff - pd.Timedelta(days=30)
    weather = pd.DataFrame({
        "datetime_utc": [early, cutoff], "zone": [zone, zone],
        "point_name": ["x", "x"], "temperature_2m": [30.0, 30.0]})
    demand = pd.DataFrame({
        "datetime_utc": [early, cutoff], "zone": [zone, zone],
        "demand_mw": [1000.0, 1000.0], "is_estimated": [False, False],
        "estimation_method": [None, None]})
    built = build_features(weather, cfg, demand)
    mask = trainable_mask(built, cfg)
    assert not mask.iloc[0], f"{zone} row before its start must be excluded"
    assert mask.iloc[1]


def test_trainable_mask_drops_null_and_nonpositive_targets(cfg, training_inputs):
    weather, demand = training_inputs
    demand = demand.copy()
    demand.loc[0, "demand_mw"] = np.nan
    demand.loc[1, "demand_mw"] = 0.0
    built = build_features(weather, cfg, demand)
    mask = trainable_mask(built, cfg)
    assert not mask.iloc[0] and not mask.iloc[1]


# --- against the real cache ------------------------------------------------

def test_builds_from_the_real_cache(cfg, project_root):
    dpath = project_root / "data" / "raw" / "demand_IN-NO.parquet"
    wpath = project_root / "data" / "raw" / "weather_IN-NO.parquet"
    if not dpath.exists() or not wpath.exists():
        pytest.skip("cache absent")
    demand = pd.read_parquet(dpath).tail(2000)
    weather = pd.read_parquet(wpath).tail(2000)
    built = build_features(weather, cfg, demand)
    assert len(built) > 1000
    assert list(feature_matrix(built).columns) == FEATURE_COLUMNS
    assert built[FEATURE_COLUMNS].notna().all().all()
    assert trainable_mask(built, cfg).any()
