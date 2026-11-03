"""Merge a missing date range into local caches without replacing old history.

Run only after the frozen research evaluations are recorded: changing inputs
beforehand would move the split anchor. New revision observations are stamped
with today's observation time, never presented as historical vintages.
"""

import argparse
import pathlib
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, get_api_key, load_config
from src.ingest.archive import _known_state, _merge_parquet
from src.ingest.electricity_maps import fetch_range
from src.ingest.weather import fetch_archive
from src.validate import validate_demand, validate_weather


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="first missing UTC date, YYYY-MM-DD")
    args = parser.parse_args()
    cfg = load_config()
    start = datetime.fromisoformat(args.start).replace(tzinfo=UTC)
    now = datetime.now(UTC)
    weather_end = now - timedelta(days=cfg["archive"]["observed_lag_days"])
    key = get_api_key()
    known = _known_state(cfg, cfg["demand"]["all_zones"])
    prior_keys = pd.MultiIndex.from_frame(known[["zone", "datetime_utc"]])
    failed = []
    for zone in cfg["demand"]["all_zones"]:
        try:
            cursor, rows = start, []
            while cursor < now:
                end = min(cursor + timedelta(days=cfg["demand"]["chunk_days"]), now)
                chunk = fetch_range(key, zone, cursor, end)
                if not chunk:
                    raise ValueError("empty demand range; refusing an incomplete repair")
                rows.extend(chunk)
                cursor = end
            demand = pd.DataFrame(rows)
            for col in ["datetime_utc", "updated_at", "created_at"]:
                demand[col] = pd.to_datetime(demand[col], utc=True, errors="coerce")
            validate_demand(demand, zone, cfg)
            demand["observed_at"] = now
            demand["first_sight"] = ~pd.MultiIndex.from_frame(
                demand[["zone", "datetime_utc"]]
            ).isin(prior_keys)
            # Preserve the actual retrieval time in the revision archive.
            revision = (
                PROJECT_ROOT / cfg["archive"]["revision_dir"] / f"{now:%Y-%m-%d}-catchup.parquet"
            )
            _merge_parquet(revision, demand, ["zone", "datetime_utc", "observed_at"])
            point, weather = cfg["weather"]["points"][zone], cfg["weather"]
            observed = fetch_archive(
                point["lat"],
                point["lon"],
                start.date().isoformat(),
                weather_end.date().isoformat(),
                weather["variables"],
                weather["archive_url"],
            )
            validate_weather(observed, zone, cfg)
            observed = observed.reset_index().assign(zone=zone, point_name=point["name"])
            _merge_parquet(
                PROJECT_ROOT / "data/raw" / f"weather_{zone}.parquet",
                observed,
                ["zone", "datetime_utc"],
            )
            print(
                f"{zone}: captured {len(demand)} demand and {len(observed)} observed-weather rows",
                flush=True,
            )
        except Exception as exc:
            failed.append(zone)
            print(f"{zone}: catch-up failed ({type(exc).__name__})", flush=True)
    if failed:
        raise SystemExit(f"Catch-up incomplete: {failed}")


if __name__ == "__main__":
    main()
