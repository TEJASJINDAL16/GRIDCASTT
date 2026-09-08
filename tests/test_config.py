"""Configuration integrity (PLANNING 4, 5h).

Every tunable lives in config/config.yaml, and a missing required key fails
fast rather than being defaulted. A defaulted key is a decision nobody made,
taken silently, that then appears as a number in a report.
"""

from __future__ import annotations

import pathlib

import pytest
import yaml

from src.config import REQUIRED_KEYS, ConfigError, get, load_config

PLANNING_ZONES = ["IN-NO", "IN-WE", "IN-SO", "IN-EA", "IN-NE"]


def test_every_required_key_resolves(cfg):
    for path in REQUIRED_KEYS:
        get(cfg, path)


def test_missing_required_key_fails_fast(tmp_path):
    thin = tmp_path / "config.yaml"
    thin.write_text(yaml.safe_dump({"project": {"timezone": "Asia/Kolkata"}}))
    with pytest.raises(ConfigError, match="required config key"):
        load_config(thin)


def test_missing_config_file_fails_fast(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "absent.yaml")


def test_get_names_the_path_that_failed(cfg):
    with pytest.raises(ConfigError, match="features.nonexistent"):
        get(cfg, "features.nonexistent")


# --- the zone list has to agree with PLANNING 5a ---------------------------

def test_all_five_zones_are_configured(cfg):
    assert cfg["demand"]["all_zones"] == PLANNING_ZONES


def test_every_zone_has_a_weather_point(cfg):
    points = cfg["weather"]["points"]
    assert set(points) == set(cfg["demand"]["all_zones"])
    for zone, point in points.items():
        assert -90 <= point["lat"] <= 90 and -180 <= point["lon"] <= 180, zone


def test_the_target_field_is_the_one_the_probe_confirmed(cfg):
    assert cfg["demand"]["target_field"] == "powerConsumptionTotal"


# --- the monitor must not fire on underived thresholds (PLANNING 6) --------

def test_monitor_is_disarmed_while_thresholds_are_underived(cfg):
    """A half-configured system making an arbitrary decision on day one is the
    silent failure of section 9 in its purest form."""
    drift = cfg["drift"]
    if not drift["thresholds_derived"]:
        assert drift["thresholds_backtest_sha"] is None
        assert drift["thresholds"]["rolling_error"]["pooled"] is None
        assert drift["thresholds"]["signed_bias"]["pooled"] is None
        assert drift["watch_threshold"] is None


def test_threshold_sha_and_derived_flag_move_together(cfg):
    drift = cfg["drift"]
    assert drift["thresholds_derived"] is (drift["thresholds_backtest_sha"] is not None)


# --- band sufficiency (PLANNING 13) ---------------------------------------

def test_band_thresholds_are_ordered(cfg):
    ev = cfg["evaluate"]
    assert ev["insufficient_band_rows"] < ev["min_band_rows"]
    assert ev["temperature_bands_c"] == sorted(ev["temperature_bands_c"])


# --- no magic numbers: config is the only place tunables live -------------

def test_config_yaml_has_no_duplicate_keys():
    """PyYAML silently keeps the last of a duplicated key, so a stray paste
    changes a value with nothing to show for it."""
    text = pathlib.Path("config/config.yaml").read_text()

    class StrictLoader(yaml.SafeLoader):
        pass

    def no_duplicates(loader, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise AssertionError(f"duplicate key in config.yaml: {key}")
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_duplicates)
    yaml.load(text, StrictLoader)


def test_target_is_log_with_retransformation_correction(cfg):
    """5c: train on log(demand); correct the retransformation bias with Duan
    smearing. exp(mean(log x)) understates mean(x), silently and always low."""
    train = cfg["train"]
    assert train["target_transform"] == "log"
    assert train["correct_retransformation_bias"] is True
    assert train["retransformation"] == "duan_smearing"


def test_the_backfill_origin_is_not_duplicated_in_code(cfg):
    """PLANNING 4: no magic numbers in code.

    demand.backfill_start is also the origin of `trend` (5e), so a second copy
    in a script is not merely untidy — it is a feature definition that can
    silently disagree with the one in config.
    """
    origin = str(cfg["demand"]["backfill_start"])
    offenders = []
    for folder in ("src", "scripts"):
        for path in pathlib.Path(folder).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if origin in path.read_text():
                offenders.append(path.as_posix())
    assert not offenders, (
        f"demand.backfill_start ({origin}) is hardcoded in {offenders}; "
        "config/config.yaml is its only home"
    )
