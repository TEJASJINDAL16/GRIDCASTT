"""Shared fixtures.

Synthetic frames here are for exercising the *checks*, never for training or
for any reported number. PLANNING 3: real, public, messy data, never generated.
The distinction is that these frames are test inputs to a validator, not
observations of the world.
"""

from __future__ import annotations

import pathlib
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.config import PROJECT_ROOT, load_config


@pytest.fixture(scope="session")
def cfg() -> dict:
    return load_config()


@pytest.fixture(scope="session")
def project_root() -> pathlib.Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def tracked_files() -> list[pathlib.Path]:
    """Every file git actually tracks, as absolute paths."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [PROJECT_ROOT / p for p in out.split("\0") if p]


@pytest.fixture
def demand_frame() -> pd.DataFrame:
    """A well-formed demand frame, shaped exactly as ingest writes it."""
    stamps = pd.date_range("2024-05-01", periods=168, freq="h", tz="UTC")
    hour = np.arange(168) % 24
    return pd.DataFrame({
        "datetime_utc": stamps,
        "zone": "IN-NO",
        "demand_mw": 50000.0 + 5000.0 * hour / 24.0,
        "production_mw": 51000.0,
        "import_mw": 0.0,
        "export_mw": 0.0,
        "is_estimated": False,
        "estimation_method": None,
        "fossil_free_pct": 20.0,
        "renewable_pct": 15.0,
        "updated_at": stamps,
        "created_at": stamps,
    })


@pytest.fixture
def weather_frame() -> pd.DataFrame:
    """A well-formed weather frame, indexed by UTC timestamp."""
    stamps = pd.date_range("2024-05-01", periods=168, freq="h", tz="UTC")
    hour = np.arange(168) % 24
    return pd.DataFrame(
        {"temperature_2m": 30.0 + 6.0 * hour / 24.0,
         "relative_humidity_2m": np.full(168, 45.0)},
        index=pd.Index(stamps, name="datetime"),
    )
