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
    "splits.tuning_window_months",
    "splits.min_initial_train_months",
    "splits.early_stopping_weeks",
    "forecast_noise.enabled",
    "forecast_noise.day_bias_sigma_c",
    "forecast_noise.hour_wobble_sigma_c",
    "baselines.ridge_alpha",
    "baselines.per_zone_model",
    "backtest.issue_hour_ist",
    "backtest.report_path",
    "backtest.results_dir",
    "backtest.predictions_path",
    "train.target_transform",
    "train.seed",
    "evaluate.baseline",
    "evaluate.temperature_bands_c",
    "evaluate.min_band_rows",
    "drift.thresholds_derived",
    "drift.rolling_window_days",
    "failure.min_zones_to_publish",
    "dashboard.output_dir",
    "runtime.threads",
    "runtime.max_boost_rounds",
    "runtime.early_stopping_rounds",
    "runtime.model_path",
    "runtime.model_metadata",
    "runtime.forecast_dir",
    "runtime.score_dir",
    "runtime.image_digest",
    "runtime.min_settled_fraction",
    "runtime.threshold_steps",
    "runtime.debounce_candidates",
    "failure.retry_window_hours",
    "failure.max_consecutive_failures",
    "failure.max_forecast_vintage_age_hours",
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
    with open(config_path, encoding="utf-8") as f:
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
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == name:
                found = val.strip().strip('"').strip("'")
                if found:
                    return found

    raise RuntimeError(f"{name} not found. Copy .env.example to .env and add your key.")


def update_values(values: dict, path: pathlib.Path = CONFIG_PATH) -> None:
    """Replace existing YAML values by parser locations, retaining comments."""
    source = path.read_text(encoding="utf-8")
    root = yaml.compose(source)
    edits = []
    for dotted, value in values.items():
        node = root
        for part in dotted.split("."):
            node = next(v for k, v in node.value if k.value == part)
        rendered = (
            yaml.safe_dump(value, default_flow_style=True).strip().removesuffix("...").strip()
        )
        if isinstance(node, (yaml.MappingNode, yaml.SequenceNode)):
            original = source[node.start_mark.index : node.end_mark.index]
            rendered += original[len(original.rstrip()) :]
        edits.append((node.start_mark.index, node.end_mark.index, rendered))
    for start, end, rendered in sorted(edits, reverse=True):
        source = source[:start] + rendered + source[end:]
    path.write_text(source, encoding="utf-8")


def configure_tracking() -> None:
    """Explicitly enable the specified local file store in MLflow 3.16."""
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"


def configure_gdrive_oauth(client_file: pathlib.Path) -> pathlib.Path:
    """Import a downloaded OAuth client locally without exposing its values.

    A fresh credential file avoids reusing a token containing an old secret.
    Neither the client file nor the resulting token may be committed.
    """
    import json
    import tempfile

    from dvc.config import Config

    document = json.loads(client_file.read_text(encoding="utf-8"))
    client = document.get("installed")
    if not isinstance(client, dict):
        raise ValueError("Expected a Google Desktop OAuth client JSON file")
    values = [client.get(name) for name in ("client_id", "client_secret")]
    if any(
        not isinstance(value, str)
        or not value
        or not value.isascii()
        or any(c.isspace() for c in value)
        for value in values
    ):
        raise ValueError("OAuth client ID or secret is missing or malformed")
    temporary = PROJECT_ROOT / ".dvc" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    credentials = (
        pathlib.Path(tempfile.mkdtemp(prefix="oauth-", dir=temporary)) / "credentials.json"
    )
    config = Config(dvc_dir=str(PROJECT_ROOT / ".dvc"))
    with config.edit("local") as local:
        remote = local.setdefault("remote", {}).setdefault("gdrive", {})
        remote["gdrive_client_id"], remote["gdrive_client_secret"] = values
        remote["gdrive_user_credentials_file"] = str(credentials)
    return credentials
