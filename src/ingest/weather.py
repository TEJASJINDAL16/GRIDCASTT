"""Open-Meteo weather ingestion.

Three sources, deliberately kept separate:

  fetch_archive()        past weather — ACTUAL observations. History.
  fetch_forecast()       future weather — a PREDICTION. Prediction time.
  fetch_previous_runs()  past FORECASTS — what the forecast said N days before
                         each past target hour. A prediction, not an
                         observation, despite being about the past.

Keeping them apart is what stops leakage: at 9am today we only ever know
the forecast for tomorrow, never tomorrow's actual temperature. Training on
actuals we could not have had would make the backtest lie.

The third is the subtle case, and it sits on the FORECAST side of that line
despite taking a date range the way the archive does. It answers "what did we
believe on 8 September about 11 September", which is information that genuinely
existed at the earlier time — so it is a legitimate training input where
fetch_archive's output is not. It is a separate function rather than a mode of
either other one, so the distinction stays visible at every call site.
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


def fetch_previous_runs(
    lat: float,
    lon: float,
    variables: Iterable[str],
    start: str,
    end: str,
    max_lead_days: int = 7,
    url: str = "https://historical-forecast-api.open-meteo.com/v1/forecast",
    tz: str = "UTC",
) -> pd.DataFrame:
    """What the forecast SAID, 1..max_lead_days before each target hour.

    Returns long format — one row per (target hour, lead_days) — so the shape
    matches the vintage archive rather than the API's wide form.

    `lead_days == 0` is deliberately EXCLUDED. The plain variable is the
    provider's best current estimate for a past hour, which is an analysis and
    not a forecast; including it would be the same INV-1 mistake as the
    negative lead_time rows in the captured archive (5d).
    """
    leads = list(range(1, max_lead_days + 1))
    wanted = [f"{v}_previous_day{d}" for v in variables for d in leads]
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(wanted),
        "timezone": tz,
    }
    log.info("previous runs: %s..%s at (%.4f, %.4f), leads 1-%d",
             start, end, lat, lon, max_lead_days)
    hourly = _get(url, params)["hourly"]

    stamps = pd.to_datetime(pd.Series(hourly["time"]))
    if stamps.dt.tz is None:
        stamps = stamps.dt.tz_localize(tz)
    stamps = stamps.dt.tz_convert("UTC")

    frames = []
    for lead in leads:
        block = {"target_datetime": stamps, "lead_days": lead}
        for var in variables:
            column = f"{var}_previous_day{lead}"
            if column in hourly:
                block[var] = pd.Series(hourly[column], dtype="float64")
        frames.append(pd.DataFrame(block))
    out = pd.concat(frames, ignore_index=True)
    return out.sort_values(["target_datetime", "lead_days"]).reset_index(drop=True)
