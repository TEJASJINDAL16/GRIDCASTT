"""Open-Meteo weather ingestion.

Two sources, deliberately kept separate:

  fetch_archive()   past weather — ACTUAL observations. Used to build history.
  fetch_forecast()  future weather — a PREDICTION. Used at prediction time.

Keeping them apart is what stops leakage: at 9am today we only ever know
the forecast for tomorrow, never tomorrow's actual temperature. Training on
actuals we could not have had would make the backtest lie.
"""

import logging
import time
from collections.abc import Iterable

import pandas as pd
import requests

log = logging.getLogger(__name__)

_TIMEOUT = 60


def _get(url: str, params: dict, retries: int = 5) -> dict:
    """GET with backoff on rate limiting and transient server errors.

    Open-Meteo prices a request by how much data it returns, not by the count,
    so a multi-year pull over eight variables can exhaust the allowance in a
    handful of calls and answer 429. Backing off and retrying is the difference
    between a backfill that completes and one that stops three zones in.
    """
    delay = 5.0
    for attempt in range(retries):
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = float(resp.headers.get("Retry-After", delay))
            log.warning("open-meteo %s, retrying in %.0fs (attempt %d/%d)",
                        resp.status_code, wait, attempt + 1, retries)
            time.sleep(wait)
            delay *= 2
            continue
        resp.raise_for_status()          # 4xx that retrying will not fix
    resp.raise_for_status()
    raise RuntimeError("unreachable")


def _to_frame(payload: dict, tz: str) -> pd.DataFrame:
    """Parse an Open-Meteo response into a UTC-indexed frame.

    Open-Meteo returns naive local-time strings in whatever timezone was asked
    for. Storing those unchanged is how a half-hour offset becomes invisible:
    India is UTC+5:30, so a naive IST stamp read as UTC mislabels the weekday
    on the first hour of every forecast day and shifts every holiday lookup
    (5e). Everything is stored UTC and converted to IST downstream, once.
    """
    df = pd.DataFrame(payload["hourly"])
    stamps = pd.to_datetime(df["time"])
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize(tz)
    df["time"] = stamps.dt.tz_convert("UTC")
    df = df.rename(columns={"time": "datetime_utc"}).set_index("datetime_utc").sort_index()
    df.attrs["requested_timezone"] = tz
    df.attrs["elevation"] = payload.get("elevation")
    return df


def fetch_archive(
    lat: float,
    lon: float,
    start: str,
    end: str,
    variables: Iterable[str],
    url: str = "https://archive-api.open-meteo.com/v1/archive",
    tz: str = "UTC",
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
    tz: str = "UTC",
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
