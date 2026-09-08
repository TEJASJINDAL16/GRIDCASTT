"""One test per invariant (PLANNING 9).

Breaking an invariant produces a plausible number that is wrong, with no error
message. These tests are the only thing standing between that and a report.

Stage 1 covers the invariants testable without a model. The rest are marked
skipped with the stage they arrive in, so the gap is visible in the test
summary rather than absent from it. `pytest -rs` lists them.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import re

import pytest

from src.config import PROJECT_ROOT
from src.ingest import weather

SRC = PROJECT_ROOT / "src"


def _python_sources(root: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


# --------------------------------------------------------------------------
# INV-1 — No leakage. Only information available at prediction time may be a
# feature. Enforced structurally: fetch_archive() and fetch_forecast() are
# separate functions in src/ingest/weather.py and must remain so.
# --------------------------------------------------------------------------

def test_inv1_archive_and_forecast_are_separate_functions():
    assert callable(weather.fetch_archive)
    assert callable(weather.fetch_forecast)
    assert weather.fetch_archive is not weather.fetch_forecast


def test_inv1_neither_weather_fetcher_calls_the_other():
    """One delegating to the other would collapse the structural separation."""
    tree = ast.parse((SRC / "ingest" / "weather.py").read_text())
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in ("fetch_archive", "fetch_forecast"):
        called = {
            n.func.id for n in ast.walk(fns[name])
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        }
        assert "fetch_archive" not in called - {name}, f"{name} calls fetch_archive"
        assert "fetch_forecast" not in called - {name}, f"{name} calls fetch_forecast"


def test_inv1_forecast_cannot_be_pointed_at_the_past():
    """fetch_forecast takes no start/end date. If it did, it could serve history
    while looking like a forecast — leakage that reads as a normal call."""
    params = set(inspect.signature(weather.fetch_forecast).parameters)
    assert not ({"start", "end", "start_date", "end_date"} & params), (
        "fetch_forecast accepts a date range; it must only ever return the "
        "forecast as of now"
    )
    assert {"start", "end"} <= set(inspect.signature(weather.fetch_archive).parameters)


def test_inv1_the_two_fetchers_use_different_endpoints(cfg):
    assert cfg["weather"]["archive_url"] != cfg["weather"]["forecast_url"]


def test_inv1_solar_generation_is_not_a_feature(cfg):
    """gen_solar_mw is analysis material only (5e). Tomorrow's solar is not
    known at issue time, so using it would be leakage."""
    linear = cfg["features"]["linear_stage_features"]
    assert not any("solar" in f for f in linear)


# --------------------------------------------------------------------------
# INV-2 — No random train/test split. Walk-forward only.
# --------------------------------------------------------------------------

FORBIDDEN_SPLIT_PATTERNS = [
    (re.compile(r"\btrain_test_split\b"), "sklearn train_test_split"),
    (re.compile(r"\bKFold\b"), "KFold"),
    (re.compile(r"\bShuffleSplit\b"), "ShuffleSplit"),
    (re.compile(r"\bStratifiedKFold\b"), "StratifiedKFold"),
    (re.compile(r"shuffle\s*=\s*True"), "shuffle=True"),
    (re.compile(r"\.sample\s*\(\s*frac\s*="), "DataFrame.sample(frac=...)"),
]


def test_inv2_no_random_splitting_anywhere_in_src():
    offenders = []
    for path in _python_sources(SRC):
        text = path.read_text()
        for pattern, label in FORBIDDEN_SPLIT_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {label}")
    assert not offenders, (
        "random splitting found — a shuffled split trains on the future to "
        f"predict the past (INV-2): {offenders}"
    )


def test_inv2_splits_are_chronological_in_config(cfg):
    splits = cfg["splits"]
    assert splits["fold_step"] == "monthly"
    assert splits["walk_forward_folds"] >= 1
    assert splits["purge_gap_days"] >= 1, (
        "a fold with no purge gap trains on data that would not have existed "
        "at decision time"
    )


# --------------------------------------------------------------------------
# INV-3 — Never train on estimated rows.
# INV-4 — Score only against measured rows.
# --------------------------------------------------------------------------

def test_inv3_training_on_estimated_rows_is_off(cfg):
    assert cfg["quality"]["train_on_estimated"] is False


def test_inv4_scoring_on_estimated_rows_is_off(cfg):
    assert cfg["quality"]["score_on_estimated"] is False


def test_inv3_inv4_ingest_preserves_the_estimation_flag():
    """The flag has to survive ingest or neither invariant can be enforced."""
    from src.validate import DEMAND_REQUIRED_COLUMNS
    assert "is_estimated" in DEMAND_REQUIRED_COLUMNS
    source = (SRC / "ingest" / "electricity_maps.py").read_text()
    assert '"is_estimated"' in source and "isEstimated" in source


# --------------------------------------------------------------------------
# INV-5 — Baseline before claim.
# --------------------------------------------------------------------------

def test_inv5_dashboard_is_configured_to_show_the_baseline(cfg):
    assert cfg["dashboard"]["show_baseline_line"] is True
    assert cfg["evaluate"]["baseline"] == "seasonal_naive"


@pytest.mark.skip(reason="stage 2: needs reports/baseline.md and the metrics module")
def test_inv5_no_reported_error_figure_lacks_its_baseline():
    ...


# --------------------------------------------------------------------------
# INV-6 — Secrets never leave .env.
# --------------------------------------------------------------------------

SECRET_BEARING_PATHS = [".env", ".dvc/config.local", ".dvc/tmp/gdrive-user-credentials.json"]


def test_inv6_secret_files_are_git_ignored(tracked_files, project_root):
    tracked = {p.relative_to(project_root).as_posix() for p in tracked_files}
    for path in SECRET_BEARING_PATHS:
        assert path not in tracked, f"{path} is tracked by git"


def test_inv6_no_secret_value_appears_in_any_tracked_file(tracked_files, project_root):
    """Search every tracked file for the live secret values.

    The values are never printed: the assertion reports filenames only.
    """
    env_path = project_root / ".env"
    if not env_path.exists():
        pytest.skip(".env absent — nothing to leak")

    secrets = set()
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        value = line.partition("=")[2].strip().strip('"').strip("'")
        if len(value) >= 12 and "your-" not in value:
            secrets.add(value)
    if not secrets:
        pytest.skip(".env holds no substantive value")

    offenders = []
    for path in tracked_files:
        try:
            text = path.read_text(errors="ignore")
        except (OSError, UnicodeDecodeError):
            continue
        if any(s in text for s in secrets):
            offenders.append(path.relative_to(project_root).as_posix())
    del secrets  # do not leave the value in a frame pytest might render

    assert not offenders, f"secret value found in tracked file(s): {offenders}"


def test_inv6_only_config_module_reads_secrets():
    """One module reads secrets (PLANNING 8). A second reader is a second place
    a secret can be logged."""
    offenders = []
    for path in _python_sources(SRC):
        if path.name == "config.py":
            continue
        text = path.read_text()
        if "EM_API_KEY" in text or "getenv" in text or "environ" in text:
            offenders.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert not offenders, f"modules reading the environment directly: {offenders}"


def test_inv6_no_secret_is_logged_or_printed():
    """The key is passed to requests as a header value and must never reach a
    log line or stdout."""
    offenders = []
    for path in _python_sources(SRC):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"(log\.\w+|print)\s*\(.*\b(key|token|secret|auth)\b", line, re.I):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}")
    assert not offenders, f"possible secret in a log or print: {offenders}"


# --------------------------------------------------------------------------
# INV-7 — Never select hyperparameters using walk-forward test folds.
# --------------------------------------------------------------------------

def test_inv7_tuning_window_is_reserved_and_separate(cfg):
    assert cfg["splits"]["tuning_window_months"] >= 1
    assert cfg["tuning"]["method"] == "optuna"


def test_inv7_tuned_parameters_are_null_until_the_search_runs(cfg):
    """A tuned parameter with a value before step 10 was chosen by a human
    looking at something. Which something is the question INV-7 asks."""
    assert cfg["train"]["ridge"]["alpha"] is None
    assert all(v is None for v in cfg["train"]["lightgbm"].values())


@pytest.mark.skip(reason="stage 3: needs scripts/tune.py and the fold boundaries")
def test_inv7_optuna_never_sees_a_test_fold():
    ...


# --------------------------------------------------------------------------
# INV-8 — Never train on suppressed-demand hours.
# --------------------------------------------------------------------------

def test_inv8_suppression_settings_exist_and_are_exclusions_not_weights(cfg):
    """5f principle 2: exclude, not downweight. INV-8 admits no partial weight."""
    quality = cfg["quality"]
    assert "suppression_temp_rise_c" in quality
    assert "suppression_demand_delta_pct" in quality
    assert not any("weight" in k for k in quality), (
        "a suppression weight would be a partial exclusion, which INV-8 forbids"
    )


@pytest.mark.skip(reason="stage 2: needs src/features/quality.py")
def test_inv8_suppressed_hours_are_excluded_from_training():
    ...


# --------------------------------------------------------------------------
# INV-9 — One feature definition. Training and serving both call
# features/build.py and nothing else.
# --------------------------------------------------------------------------

def test_inv9_there_is_at_most_one_feature_builder():
    """Two modules defining build_features is how train/serve skew begins."""
    definers = []
    for path in _python_sources(SRC):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "build_features":
                definers.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert len(definers) <= 1, f"more than one feature builder: {definers}"
    if definers:
        assert definers == ["src/features/build.py"], (
            f"the feature builder must live in src/features/build.py, found {definers}"
        )


@pytest.mark.skip(reason="stage 2: the train/serve contract test, once build.py exists")
def test_inv9_training_and_serving_emit_identical_columns():
    ...
