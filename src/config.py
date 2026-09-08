"""Configuration and secrets — the only module that reads either.

PLANNING 8 puts every tunable in config/config.yaml and every secret in .env,
and makes this the single reader of both. One reader is what keeps INV-6
checkable: there is exactly one place a secret can be mishandled.

PLANNING 5h requires a missing required key to fail fast at startup rather than
be filled with a default. A defaulted key is a decision nobody made, taken
silently, that then shows up as a number in a report.
"""

from __future__ import annotations

import os
import pathlib
from typing import Any

import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

# Dotted paths that must exist for any entry point to be safe to run. Not the
# whole file — the keys whose absence would otherwise be papered over with a
# default and silently change a result.
REQUIRED_KEYS = [
    "project.timezone",
    "demand.all_zones",
    "demand.backfill_start",
    "demand.target_field",
    "weather.archive_url",
    "weather.forecast_url",
    "weather.variables",
    "weather.points",
    "features.temp_breakpoint_c",
    "features.linear_stage_features",
    "features.monotone_increasing",
    "features.clamp_linear_below",
    "quality.trainable_estimation_methods",
    "quality.train_on_estimated",
    "quality.score_on_estimated",
    "validate.demand_mw_min",
    "validate.demand_mw_max",
    "validate.temperature_c_min",
    "validate.temperature_c_max",
    "validate.expected_freq_hours",
    "splits.purge_gap_days",
    "splits.walk_forward_folds",
    "splits.holdout_months",
    "train.target_transform",
    "train.seed",
    "evaluate.baseline",
    "evaluate.temperature_bands_c",
    "evaluate.min_band_rows",
    "drift.thresholds_derived",
    "drift.rolling_window_days",
    "failure.min_zones_to_publish",
    "dashboard.output_dir",
]


class ConfigError(Exception):
    """The configuration is unusable. Do not continue with a default."""


def get(cfg: dict, path: str) -> Any:
    """Read a dotted path, raising rather than defaulting.

    `cfg["drift"]["thresholds"]["rolling_error"]` raises KeyError with no
    context; this says which path failed and where to look.
    """
    node: Any = cfg
    walked: list[str] = []
    for part in path.split("."):
        walked.append(part)
        if not isinstance(node, dict) or part not in node:
            raise ConfigError(
                f"missing required config key '{path}' "
                f"(resolved as far as '{'.'.join(walked[:-1]) or '<root>'}'). "
                f"Add it to {CONFIG_PATH.relative_to(PROJECT_ROOT)}; "
                "do not substitute a default (PLANNING 5h)."
            )
        node = node[part]
    return node


def _check_required(cfg: dict) -> None:
    missing = []
    for path in REQUIRED_KEYS:
        try:
            get(cfg, path)
        except ConfigError:
            missing.append(path)
    if missing:
        raise ConfigError(
            f"{len(missing)} required config key(s) missing: {missing}. "
            "Failing fast rather than defaulting (PLANNING 5h)."
        )


def load_config(path: pathlib.Path | None = None, check: bool = True) -> dict:
    """Parse config/config.yaml. Fails fast if a required key is absent."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        raise ConfigError(f"config file not found: {config_path}")
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ConfigError(f"config file did not parse to a mapping: {config_path}")
    if check:
        _check_required(cfg)
    return cfg


def get_api_key(name: str = "EM_API_KEY") -> str:
    """Read a secret from the environment, falling back to a local .env file.

    INV-6: the value returned here goes into a request header and nowhere else.
    Never log it, never print it, never write it to a file.
    """
    value = os.environ.get(name, "").strip()
    if value:
        return value

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == name:
                found = val.strip().strip('"').strip("'")
                if found:
                    return found

    raise RuntimeError(
        f"{name} not found. Copy .env.example to .env and add your key."
    )
