"""Open-Meteo weather ingestion.

Two sources, deliberately kept separate:

  fetch_archive()   past weather — ACTUAL observations. Used to build history.
  fetch_forecast()  future weather — a PREDICTION. Used at prediction time.

Keeping them apart is what stops leakage: at 9am today we only ever know
the forecast for tomorrow, never tomorrow's actual temperature. Training on
actuals we could not have had would make the backtest lie.
"""

import logging
from collections.abc import Iterable

import pandas as pd
import requests

log = logging.getLogger(__name__)

_TIMEOUT = 60


def _get(url: str, params: dict) -> dict:
    resp = requests.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _to_frame(payload: dict, tz: str) -> pd.DataFrame:
    hourly = payload["hourly"]
    df = pd.DataFrame(hourly)
    df["time"] = pd.to_datetime(df["time"])
    df = df.rename(columns={"time": "datetime"}).set_index("datetime").sort_index()
    df.attrs["timezone"] = tz
    df.attrs["elevation"] = payload.get("elevation")
    return df


def fetch_archive(
    lat: float,
    lon: float,
    start: str,
    end: str,
    variables: Iterable[str],
    url: str = "https://archive-api.open-meteo.com/v1/archive",
    tz: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Hourly OBSERVED weather between two dates (YYYY-MM-DD, inclusive)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(variables),
        "timezone": tz,
    }
    log.info("archive: %s..%s at (%.4f, %.4f)", start, end, lat, lon)
    return _to_frame(_get(url, params), tz)


def fetch_forecast(
    lat: float,
    lon: float,
    variables: Iterable[str],
    days: int = 7,
    url: str = "https://api.open-meteo.com/v1/forecast",
    tz: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Hourly FORECAST weather for the next `days` days."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(variables),
        "forecast_days": days,
        "timezone": tz,
    }
    log.info("forecast: %d days at (%.4f, %.4f)", days, lat, lon)
    return _to_frame(_get(url, params), tz)
