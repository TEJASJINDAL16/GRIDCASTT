"""Reusable vintage, observation and revision capture for archive/daily jobs."""

import logging
import pathlib
from datetime import UTC, datetime, timedelta

import pandas as pd

from src.config import PROJECT_ROOT, get, get_api_key
from src.ingest.electricity_maps import fetch_range
from src.ingest.weather import fetch_archive, fetch_forecast
from src.validate import validate_demand, validate_weather

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("archive")

REVISION_KEY = ["zone", "datetime_utc"]
REVISION_TRACKED = ["demand_mw", "is_estimated", "updated_at"]


def _merge_parquet(path: pathlib.Path, new: pd.DataFrame, key: list[str]) -> int:
    """Append to a parquet file, dropping rows already present. Returns rows added."""
    path.parent.mkdir(parents=True, exist_ok=True)
    combined = (pd.concat([pd.read_parquet(path), new], ignore_index=True)
                if path.exists() else new)
    before = len(combined)
    combined = combined.drop_duplicates(subset=key, keep="last")
    temporary = path.with_suffix(".tmp.parquet")
    combined.to_parquet(temporary, index=False)
    temporary.replace(path)
    return len(combined) - (before - len(new))


# --------------------------------------------------------------------------
# 1. Weather forecast vintages — the unrecoverable one
# --------------------------------------------------------------------------

def archive_forecast_vintage(cfg: dict, issued_at: datetime) -> tuple[int, list[str]]:
    weather, points = get(cfg, "weather"), get(cfg, "weather.points")
    horizon = get(cfg, "archive.forecast_days")
    out = PROJECT_ROOT / get(cfg, "archive.vintage_dir") / f"{issued_at:%Y-%m-%d}.parquet"

    frames, failed = [], []
    for zone, point in points.items():
        try:
            df = fetch_forecast(point["lat"], point["lon"], weather["variables"],
                                horizon, weather["forecast_url"])
            validate_weather(df, zone, cfg)
        except Exception as exc:
            log.error("  vintage %s: FAILED — %s", zone, exc)
            failed.append(zone)
            continue

        df = df.reset_index().rename(columns={"datetime_utc": "target_datetime"})
        df.insert(0, "issued_at", issued_at)
        df.insert(2, "zone", zone)
        df.insert(3, "point_name", point["name"])
        # Lead time from the ACTUAL issue time, never a nominal one (5h): a
        # forecast re-issued later has a shorter horizon and is a slightly
        # easier problem, and the lead-time stratification must see that.
        df["lead_time_hours"] = (
            (df["target_datetime"] - issued_at).dt.total_seconds() / 3600.0)
        frames.append(df)
        log.info("  vintage %s: %d rows, lead %d..%dh", zone, len(df),
                 df["lead_time_hours"].min(), df["lead_time_hours"].max())

    if not frames:
        return 0, failed

    added = _merge_parquet(out, pd.concat(frames, ignore_index=True),
                           key=["issued_at", "zone", "target_datetime"])
    log.info("  vintage: %d row(s) -> %s", added, out.name)
    return added, failed


# --------------------------------------------------------------------------
# 2. Observed weather — extend history as the archive releases it
# --------------------------------------------------------------------------

def archive_observed_weather(cfg: dict) -> tuple[int, list[str]]:
    weather, points = get(cfg, "weather"), get(cfg, "weather.points")
    lag = get(cfg, "archive.observed_lag_days")
    raw = PROJECT_ROOT / "data" / "raw"

    end = datetime.now(UTC) - timedelta(days=lag)
    start = end - timedelta(days=get(cfg, "archive.revision_lookback_days"))

    total, failed = 0, []
    for zone, point in points.items():
        path = raw / f"weather_{zone}.parquet"
        if not path.exists():
            log.info("  observed %s: no cache yet — run `make backfill-weather` first",
                     zone)
            continue
        try:
            cached = pd.read_parquet(path, columns=["datetime_utc"])
            # Resume after an outage rather than permanently leaving a gap
            # whenever the downtime exceeds the usual revision window.
            zone_start = min(start, cached.datetime_utc.max().to_pydatetime())
            df = fetch_archive(point["lat"], point["lon"],
                               f"{zone_start:%Y-%m-%d}", f"{end:%Y-%m-%d}",
                               weather["variables"], weather["archive_url"])
            validate_weather(df, zone, cfg)
        except Exception as exc:            # includes ValidationError
            log.error("  observed %s: FAILED — %s", zone, exc)
            failed.append(zone)
            continue

        df = df.reset_index()
        df.insert(1, "zone", zone)
        df.insert(2, "point_name", point["name"])
        added = _merge_parquet(path, df, key=["zone", "datetime_utc"])
        total += added
        log.info("  observed %s: %d new row(s)", zone, added)
    return total, failed


# --------------------------------------------------------------------------
# 3. Demand revisions — what turns purge_gap_days into a measurement
# --------------------------------------------------------------------------

def _known_state(cfg: dict, zones: list[str]) -> pd.DataFrame:
    """The newest state we have recorded for each (zone, datetime_utc)."""
    raw = PROJECT_ROOT / "data" / "raw"
    frames = []
    for zone in zones:
        path = raw / f"demand_{zone}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path)[REVISION_KEY + REVISION_TRACKED])
    revision_dir = PROJECT_ROOT / get(cfg, "archive.revision_dir")
    if revision_dir.exists():
        for path in sorted(revision_dir.glob("*.parquet")):
            frames.append(pd.read_parquet(path)[REVISION_KEY + REVISION_TRACKED])
    if not frames:
        return pd.DataFrame(columns=REVISION_KEY + REVISION_TRACKED)
    return (pd.concat(frames, ignore_index=True)
              .drop_duplicates(subset=REVISION_KEY, keep="last"))


def archive_demand_revisions(cfg: dict, observed_at: datetime) -> tuple[int, list[str]]:
    zones = get(cfg, "demand.all_zones")
    lookback = get(cfg, "archive.revision_lookback_days")
    revision_dir = PROJECT_ROOT / get(cfg, "archive.revision_dir")
    # Created unconditionally. The directory is DVC-tracked, and `dvc add` on a
    # path that does not exist fails the step - which would discard the weather
    # vintage collected moments earlier.
    revision_dir.mkdir(parents=True, exist_ok=True)
    out = revision_dir / f"{observed_at:%Y-%m-%d}.parquet"

    # PLANNING 5h puts "demand API down" in the DEGRADE column: issue the
    # forecast normally, skip scoring only. The same holds here - a demand
    # failure must not take the weather archive down with it. This read was
    # unguarded, and it cost five days of vintages: the key was absent, the
    # RuntimeError propagated, the step failed, and `dvc push` never ran even
    # though 1,920 rows of vintage had already been written.
    try:
        key = get_api_key()
    except Exception as exc:
        log.error("  revisions: credentials unavailable (%s)", type(exc).__name__)
        return 0, list(zones)

    end = datetime.now(UTC)
    start = end - timedelta(days=lookback)
    baseline = _known_state(cfg, zones)

    # The past-range endpoint refuses more than 10 days of hourly data per
    # call, and fetch_range treats the 4xx as unrecoverable and returns no
    # rows. This asked for 21 days in one call, so demand revisions had NEVER
    # been written - on the runner or locally. Two section 13 placeholders,
    # splits.purge_gap_days and drift.settlement_lag_days, are measurable only
    # from this archive, so they could never have been replaced either.
    chunk = timedelta(days=get(cfg, "demand.chunk_days"))

    def fetch_window(zone: str) -> list[dict]:
        rows, cursor = [], start
        while cursor < end:
            stop = min(cursor + chunk, end)
            rows += fetch_range(key, zone, cursor, stop)
            cursor = stop
        return rows

    frames, failed = [], []
    for zone in zones:
        try:
            rows = fetch_window(zone)
        except Exception as exc:
            log.error("  revisions %s: FAILED - %s", zone, exc)
            failed.append(zone)
            continue
        if not rows:
            log.warning("  revisions %s: no rows returned", zone)
            failed.append(zone)
            continue

        df = pd.DataFrame(rows)
        for col in ("datetime_utc", "updated_at", "created_at"):
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
        try:
            validate_demand(df, zone, cfg)
        except Exception as exc:
            log.error("  revisions %s: validation failed (%s)", zone, type(exc).__name__)
            failed.append(zone)
            continue

        prior = baseline[baseline["zone"] == zone]
        merged = df.merge(prior, on=REVISION_KEY, how="left",
                          suffixes=("", "_prior"), indicator=True)

        first_sight = merged["_merge"] == "left_only"
        changed = pd.Series(False, index=merged.index)
        for col in REVISION_TRACKED:
            differs = merged[col] != merged[f"{col}_prior"]
            both_null = merged[col].isna() & merged[f"{col}_prior"].isna()
            changed |= differs & ~both_null

        interesting = merged[first_sight | changed].copy()
        if interesting.empty:
            log.info("  revisions %s: nothing changed", zone)
            continue

        interesting["observed_at"] = observed_at
        interesting["first_sight"] = first_sight[interesting.index]
        for col in REVISION_TRACKED:
            interesting = interesting.rename(columns={f"{col}_prior": f"prior_{col}"})
        interesting = interesting.drop(columns=["_merge"])
        frames.append(interesting)

        flips = int((~interesting["first_sight"]
                     & (interesting["is_estimated"] == False)          # noqa: E712
                     & (interesting["prior_is_estimated"] == True)).sum())  # noqa: E712
        log.info("  revisions %s: %d changed (%d new, %d settled to measured)",
                 zone, len(interesting), int(interesting["first_sight"].sum()), flips)

    if not frames:
        log.info("  revisions: nothing changed in the lookback window")
        return 0, failed

    added = _merge_parquet(out, pd.concat(frames, ignore_index=True),
                           key=REVISION_KEY + REVISION_TRACKED)
    log.info("  revisions: %d row(s) -> %s", added, out.name)
    return added, failed


# --------------------------------------------------------------------------


