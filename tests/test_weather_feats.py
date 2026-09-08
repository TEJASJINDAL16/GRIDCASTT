"""Weather features (PLANNING 5e).

The rule worth testing is the aggregation order. It is inert as Phase 1 is
configured — one weather point per zone — so nothing in the current pipeline
would catch a regression. These tests would.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.features.weather_feats import (
    aggregate_to_zone,
    cooling_degrees,
    weather_features,
)


def test_ramp_is_zero_below_the_breakpoint(cfg):
    bp = cfg["features"]["temp_breakpoint_c"]
    assert cooling_degrees([bp - 5, bp, bp + 5], bp).tolist() == [0.0, 0.0, 5.0]


def test_ramp_has_no_upper_bound(cfg):
    """It must keep rising past anything seen — that is the extrapolation the
    linear stage exists for (5c)."""
    bp = cfg["features"]["temp_breakpoint_c"]
    assert cooling_degrees([100.0], bp)[0] == pytest.approx(100.0 - bp)


def _two_cities(t_a: float, t_b: float) -> pd.DataFrame:
    stamp = pd.Timestamp("2024-05-01", tz="UTC")
    return pd.DataFrame({
        "datetime_utc": [stamp, stamp],
        "zone": ["IN-XX", "IN-XX"],
        "point_name": ["Delhi", "Shimla"],
        "temperature_2m": [t_a, t_b],
    })


def test_transform_before_average_is_not_the_same_as_after(cfg):
    """PLANNING 5e's worked example, with the measured breakpoint.

    Delhi 40 C and Shimla 20 C. Averaging temperature first gives 30 C and so
    30 - 21.5 = 8.5 cooling degrees. Transforming first gives (18.5 + 0) / 2 =
    9.25. The wrong order understates the ramp, and it understates it most on
    the hottest days.
    """
    bp = cfg["features"]["temp_breakpoint_c"]
    out = weather_features(_two_cities(40.0, 20.0), cfg)
    correct = (cooling_degrees([40.0], bp)[0] + cooling_degrees([20.0], bp)[0]) / 2
    wrong = cooling_degrees([(40.0 + 20.0) / 2], bp)[0]
    assert correct != pytest.approx(wrong)
    assert out["cooling_degrees"].iloc[0] == pytest.approx(correct)
    assert out["cooling_degrees"].iloc[0] > wrong


def test_single_city_aggregation_is_the_identity(cfg):
    """Phase 1's actual configuration: the rule must be inert, not merely
    harmless."""
    stamp = pd.Timestamp("2024-05-01", tz="UTC")
    one = pd.DataFrame({"datetime_utc": [stamp], "zone": ["IN-NO"],
                        "point_name": ["Delhi"], "temperature_2m": [37.0]})
    out = weather_features(one, cfg)
    bp = cfg["features"]["temp_breakpoint_c"]
    assert out["temperature_2m"].iloc[0] == pytest.approx(37.0)
    assert out["cooling_degrees"].iloc[0] == pytest.approx(37.0 - bp)


def test_load_weights_are_applied(cfg):
    weighted = dict(cfg)
    weighted["weather"] = dict(cfg["weather"])
    weighted["weather"]["load_weights"] = {"IN-XX": {"Delhi": 0.9, "Shimla": 0.1}}
    out = weather_features(_two_cities(40.0, 20.0), weighted)
    bp = cfg["features"]["temp_breakpoint_c"]
    expected = 0.9 * (40.0 - bp) + 0.1 * 0.0
    assert out["cooling_degrees"].iloc[0] == pytest.approx(expected)


def test_partial_load_weights_fail_loudly(cfg):
    partial = dict(cfg)
    partial["weather"] = dict(cfg["weather"])
    partial["weather"]["load_weights"] = {"IN-XX": {"Delhi": 1.0}}
    with pytest.raises(KeyError, match="no weight for"):
        weather_features(_two_cities(40.0, 20.0), partial)


def test_aggregation_refuses_untransformed_input(cfg):
    """Calling aggregate before add_city_features is the exact ordering
    mistake the rule forbids, so it must not silently work."""
    with pytest.raises(KeyError, match="cooling_degrees"):
        aggregate_to_zone(_two_cities(40.0, 20.0), cfg)


def test_heating_degrees_is_not_produced(cfg):
    """Deleted in stage 1 — its justification was the U-shape (5e)."""
    out = weather_features(_two_cities(40.0, 10.0), cfg)
    assert not any("heating" in c for c in out.columns)


def test_zones_are_aggregated_independently(cfg):
    stamp = pd.Timestamp("2024-05-01", tz="UTC")
    two = pd.DataFrame({
        "datetime_utc": [stamp] * 2, "zone": ["IN-NO", "IN-SO"],
        "point_name": ["Delhi", "Bengaluru"], "temperature_2m": [40.0, 25.0]})
    out = weather_features(two, cfg).set_index("zone")
    bp = cfg["features"]["temp_breakpoint_c"]
    assert out.loc["IN-NO", "cooling_degrees"] == pytest.approx(40.0 - bp)
    assert out.loc["IN-SO", "cooling_degrees"] == pytest.approx(25.0 - bp)


def test_on_the_real_cached_weather(cfg, project_root):
    """A shape check against a real file, not a fixture."""
    path = project_root / "data" / "raw" / "weather_IN-NO.parquet"
    if not path.exists():
        pytest.skip("weather cache absent")
    raw = pd.read_parquet(path).head(500)
    out = weather_features(raw, cfg)
    assert len(out) == 500
    assert (out["cooling_degrees"] >= 0).all()
    bp = cfg["features"]["temp_breakpoint_c"]
    hot = out[out["temperature_2m"] > bp]
    assert np.allclose(hot["cooling_degrees"], hot["temperature_2m"] - bp)
