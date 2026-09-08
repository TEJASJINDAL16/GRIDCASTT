"""Indian calendar: IST conversion, holidays, festivals, day type.

PLANNING 5a and 5e. Three jobs, all of which are one-line mistakes away from
being silently wrong:

  IST conversion   The target window opens at 19:00 UTC, which is 00:30 IST the
                   NEXT day. India is UTC+5:30, so no UTC hour lands on an IST
                   hour boundary. Taking `dayofweek` or a calendar date from a
                   UTC timestamp mislabels the first hour of every forecast and
                   shifts every holiday lookup by a day. Nothing errors.

  holidays         The `holidays` package, with the state subdivision
                   configured per zone, extended by a hand-maintained file for
                   what the package misses (5a).

  day type         weekday / weekend / holiday, for the 5g stratification. A
                   holiday resembles a Sunday, so the three are kept apart.
"""

from __future__ import annotations

import logging
from datetime import date

import holidays
import pandas as pd

from src.config import PROJECT_ROOT, get

log = logging.getLogger(__name__)

DAY_TYPES = ("weekday", "weekend", "holiday")


def to_ist(stamps: pd.Series, cfg: dict) -> pd.Series:
    """Convert UTC timestamps to the project timezone.

    **RULE (5e):** every calendar extraction happens after this call, never
    before. Raises rather than guessing if the input is timezone-naive — a
    naive timestamp is one implicit conversion away from shifting every
    weekday label by 5h30.
    """
    if not pd.api.types.is_datetime64_any_dtype(stamps):
        raise TypeError(f"expected datetimes, got {stamps.dtype}")
    if getattr(stamps.dt, "tz", None) is None:
        raise ValueError(
            "timestamps are timezone-naive; they are stored UTC on ingest "
            "(PLANNING 11) and must arrive that way. Guessing the zone here "
            "is how a 5h30 offset becomes invisible."
        )
    return stamps.dt.tz_convert(get(cfg, "project.timezone"))


def load_manual_festivals(cfg: dict) -> pd.DataFrame:
    """The hand-maintained extension (5a). Empty is a valid, honest state."""
    path = PROJECT_ROOT / get(cfg, "calendar.festivals_file")
    columns = ["date", "zone", "name"]
    if not path.exists():
        log.warning("no festivals file at %s — package holidays only", path)
        return pd.DataFrame(columns=columns)
    df = pd.read_csv(path, comment="#")
    if df.empty:
        return pd.DataFrame(columns=columns)
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing column(s) {missing}")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df[columns]


def zone_holidays(zone: str, years: list[int], cfg: dict) -> set[date]:
    """Every holiday date for a zone: package subdivision plus manual list."""
    subdivisions = get(cfg, "calendar.subdivisions")
    if zone not in subdivisions:
        raise KeyError(
            f"no holiday subdivision configured for zone {zone}; "
            f"add it to calendar.subdivisions (have {sorted(subdivisions)})"
        )
    dates = set(
        holidays.country_holidays("IN", subdiv=subdivisions[zone], years=years)
    )
    manual = load_manual_festivals(cfg)
    if not manual.empty:
        rows = manual[manual["zone"].isin([zone, "ALL"])]
        dates |= {d for d in rows["date"] if d.year in set(years)}
    return dates


def is_holiday(ist_dates: pd.Series, zones: pd.Series, cfg: dict) -> pd.Series:
    """Per-row holiday flag, looked up against each row's own zone."""
    if len(ist_dates) != len(zones):
        raise ValueError("dates and zones must be the same length")
    years = sorted({d.year for d in ist_dates.dropna()})
    flags = pd.Series(False, index=ist_dates.index)
    for zone in zones.dropna().unique():
        mask = zones == zone
        dates = zone_holidays(zone, years, cfg)
        flags.loc[mask] = ist_dates.loc[mask].isin(dates)
    return flags


def day_type(ist_weekday: pd.Series, holiday_flag: pd.Series,
             cfg: dict) -> pd.Series:
    """weekday / weekend / holiday, for the 5g stratification.

    Holiday wins over weekend: a holiday falling on a Sunday is reported as a
    holiday, because that is the category a reader is asking about.
    """
    weekend_days = set(get(cfg, "calendar.weekend_days"))
    out = pd.Series("weekday", index=ist_weekday.index, dtype="object")
    out[ist_weekday.isin(weekend_days)] = "weekend"
    out[holiday_flag.astype(bool)] = "holiday"
    return pd.Categorical(out, categories=list(DAY_TYPES))


def calendar_frame(utc_stamps: pd.Series, zones: pd.Series,
                   cfg: dict) -> pd.DataFrame:
    """Every calendar column the feature builder needs, derived once, in IST."""
    ist = to_ist(utc_stamps, cfg)
    dates = pd.Series(ist.dt.date, index=ist.index)
    holiday = is_holiday(dates, zones, cfg)
    weekday = ist.dt.dayofweek
    return pd.DataFrame({
        "datetime_ist": ist,
        "date_ist": dates,
        "hour_of_day": ist.dt.hour.astype("int16"),
        "day_of_week": weekday.astype("int8"),
        "is_holiday": holiday.astype("bool"),
        "day_type": day_type(weekday, holiday, cfg),
    }, index=ist.index)
