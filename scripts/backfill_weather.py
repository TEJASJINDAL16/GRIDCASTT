"""Pull and cache observed weather history for every zone point.

Run once, alongside `make backfill`. PLANNING 5a requires all three sources
cached to disk and treated as the source of truth for training, backtesting and
reporting; `make weather` only probes Open-Meteo and writes nothing, and
`make backfill` covers demand alone, so nothing built this cache.

    make backfill-weather                          # all zones, configured span
    make backfill-weather ARGS="--zones IN-NO"
    make backfill-weather ARGS="--force"

This script is a SIBLING of backfill.py and of archive_daily.py, not a mode of
either. It touches fetch_archive only. INV-1 is enforced structurally by
keeping the archive and forecast paths apart, and that separation is worth
keeping visible at the script level too: nothing here can reach a forecast, so
nothing here can leak one into training data.
"""

import argparse
import logging
import pathlib
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, get, load_config
from src.ingest.weather import fetch_archive
from src.validate import ValidationError, validate_weather

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill-weather")


def main() -> None:
    cfg = load_config()
    weather = get(cfg, "weather")
    points = get(cfg, "weather.points")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=get(cfg, "demand.all_zones"))
    ap.add_argument("--start", default=None,
                    help="override demand.backfill_start (config is the default)")
    ap.add_argument("--end", default=None, help="default: the archive's newest day")
    ap.add_argument("--force", action="store_true", help="re-pull zones already saved")
    args = ap.parse_args()

    start = args.start or str(get(cfg, "demand.backfill_start"))
    # The archive API lags real time; ask only for days it has released.
    lag = get(cfg, "archive.observed_lag_days")
    end = args.end or (datetime.now(UTC) - timedelta(days=lag)).strftime("%Y-%m-%d")

    out_dir = PROJECT_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary, failures = [], []
    for zone in args.zones:
        if zone not in points:
            log.error("%s: no weather point configured — skipping", zone)
            failures.append(zone)
            continue

        point = points[zone]
        path = out_dir / f"weather_{zone}.parquet"

        if path.exists() and not args.force:
            df = pd.read_parquet(path)
            log.info("%s: already cached (%d rows) — use --force to re-pull",
                     zone, len(df))
        else:
            log.info("\n=== %s (%s) : %s -> %s ===",
                     zone, point["name"], start, end)
            df = fetch_archive(point["lat"], point["lon"], start, end,
                               weather["variables"], weather["archive_url"])
            df = df.reset_index()
            df.insert(1, "zone", zone)
            df.insert(2, "point_name", point["name"])

            # Validate BEFORE writing. PLANNING 14: fail loudly and refuse to
            # write. A frame that reaches disk is one every later step trusts.
            try:
                validate_weather(df.set_index("datetime_utc"), zone, cfg)
            except ValidationError as exc:
                log.error("%s: REFUSED — %s", zone, exc)
                failures.append(zone)
                continue

            df.to_parquet(path, index=False)
            log.info("%s: wrote %d rows -> %s", zone, len(df), path.name)

        temp = df["temperature_2m"]
        summary.append({
            "zone": zone,
            "point": df["point_name"].iloc[0],
            "rows": len(df),
            "from": df["datetime_utc"].min(),
            "to": df["datetime_utc"].max(),
            "temp_min_c": round(float(temp.min()), 1),
            "temp_mean_c": round(float(temp.mean()), 1),
            "temp_max_c": round(float(temp.max()), 1),
            "null_temp": int(temp.isna().sum()),
        })

    if summary:
        print("\n" + "=" * 78)
        print("WEATHER BACKFILL SUMMARY")
        print("=" * 78)
        print(pd.DataFrame(summary).to_string(index=False))
        print("\nTimestamps are UTC. Conversion to IST happens once, downstream,")
        print("when calendar features are extracted (5e).")

    if failures:
        # PLANNING 14: anything 5h calls an alert exits non-zero.
        log.error("\n%d zone(s) failed: %s", len(failures), failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
