"""Archive today's weather forecast vintage, observed weather, and demand revisions.

PLANNING 5d, step 0c. This is the piece that cannot be caught up later.

Open-Meteo serves observed history and the CURRENT forecast, but not what the
forecast said on a past date. So training uses observed weather while
production is served a forecast: the model trains on perfect temperature and is
deployed on approximate temperature, and learns to trust it more than it
should. That gap cannot be closed retroactively. Every day without archiving is
a vintage that can never be recovered.

Three things, all cheap, only the first irreplaceable:

  1  the full weather forecast horizon, against the time it was issued
  2  observed weather for recent days, as the archive API releases them
  3  any change to a recent demand row's value, is_estimated or updated_at

(3) is what turns splits.purge_gap_days from an assumption inferred from a
single observed row into a measurement (13).

    make archive

Idempotent (5h). Re-running for the same day does not double-write: vintages
dedupe on (issued_at, location, target_datetime), revisions on the full row
identity, observed weather on (zone, datetime_utc).

WARNING FOR ANY FUTURE CONSUMER OF THE VINTAGE ARCHIVE
------------------------------------------------------
Open-Meteo's forecast endpoint returns the current day from 00:00, so the
earliest rows of every vintage describe hours that had ALREADY ELAPSED when the
forecast was issued. They carry a negative `lead_time_hours`. They are stored
because 5d says to store the whole horizon the API returns, and because they
cost nothing.

They are not forecasts. Training on them would be using information from at or
after the target time, which is exactly what INV-1 forbids. Any consumer must
filter on `lead_time_hours` — the column exists so the filter is trivial and
so the decision to include a row is always explicit rather than accidental.
"""

import argparse
import json
import logging
import pathlib
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, get, get_api_key, load_config
from src.ingest.electricity_maps import fetch_range
from src.ingest.weather import fetch_archive, fetch_forecast
from src.validate import validate_weather

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
    combined.to_parquet(path, index=False)
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
            df = fetch_archive(point["lat"], point["lon"],
                               f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}",
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
    out = (PROJECT_ROOT / get(cfg, "archive.revision_dir")
           / f"{observed_at:%Y-%m-%d}.parquet")

    key = get_api_key("EM_API_KEY")
    end = datetime.now(UTC)
    start = end - timedelta(days=lookback)
    baseline = _known_state(cfg, zones)

    frames, failed = [], []
    for zone in zones:
        try:
            rows = fetch_range(key, zone, start, end)
        except Exception as exc:
            log.error("  revisions %s: FAILED — %s", zone, exc)
            failed.append(zone)
            continue
        if not rows:
            log.warning("  revisions %s: no rows returned", zone)
            failed.append(zone)
            continue

        df = pd.DataFrame(rows)
        for col in ("datetime_utc", "updated_at", "created_at"):
            df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")

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
        return 0, failed

    added = _merge_parquet(out, pd.concat(frames, ignore_index=True),
                           key=REVISION_KEY + REVISION_TRACKED)
    log.info("  revisions: %d row(s) -> %s", added, out.name)
    return added, failed


# --------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-vintage", action="store_true")
    ap.add_argument("--skip-observed", action="store_true")
    ap.add_argument("--skip-revisions", action="store_true")
    args = ap.parse_args()

    run_at = datetime.now(UTC)
    log.info("archive run at %s", run_at.isoformat(timespec="seconds"))

    status: dict = {
        "run_at": run_at.isoformat(),
        "job": "archive_daily",
        "parts": {},
        "failed_zones": {},
    }

    if not args.skip_vintage:
        log.info("1. weather forecast vintage")
        rows, failed = archive_forecast_vintage(cfg, run_at)
        status["parts"]["forecast_vintage"] = rows
        status["failed_zones"]["forecast_vintage"] = failed

    if not args.skip_observed:
        log.info("2. observed weather")
        rows, failed = archive_observed_weather(cfg)
        status["parts"]["observed_weather"] = rows
        status["failed_zones"]["observed_weather"] = failed

    if not args.skip_revisions:
        log.info("3. demand revisions")
        rows, failed = archive_demand_revisions(cfg, run_at)
        status["parts"]["demand_revisions"] = rows
        status["failed_zones"]["demand_revisions"] = failed

    failed_any = any(status["failed_zones"].values())
    status["outcome"] = "degraded" if failed_any else "success"

    # PLANNING 5h: every run writes a status record whether or not it produced
    # anything. A job that fails silently is indistinguishable from one that is
    # not scheduled.
    state = PROJECT_ROOT / "state" / "runs"
    state.mkdir(parents=True, exist_ok=True)
    record = state / f"{run_at:%Y-%m-%d}-archive.jsonl"
    with record.open("a") as f:
        f.write(json.dumps(status, default=str) + "\n")
    log.info("status: %s -> %s", status["outcome"], record.name)

    if failed_any:
        # 14: anything 5h calls an alert exits non-zero. A missed vintage is
        # permanent data loss, so it must not exit quietly.
        log.error("one or more parts failed: %s", status["failed_zones"])
        sys.exit(1)


if __name__ == "__main__":
    main()
