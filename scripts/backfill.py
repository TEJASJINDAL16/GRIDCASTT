"""Pull the full demand history and cache it to disk.

Run once. The cached parquet files are what every later step reads, so the
project keeps working if the API licence lapses or the service changes.

    make backfill                    # all zones, from the configured start
    make backfill ARGS="--zones IN-NO --force"
"""

import argparse
import logging
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import PROJECT_ROOT, get_api_key, load_config
from src.ingest.electricity_maps import backfill_zone

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill")


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=cfg["demand"]["all_zones"])
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--chunk-days", type=int, default=30)
    ap.add_argument("--force", action="store_true", help="re-pull zones already saved")
    args = ap.parse_args()

    key = get_api_key("EM_API_KEY")
    out_dir = PROJECT_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)

    summary = []
    for zone in args.zones:
        path = out_dir / f"demand_{zone}.parquet"
        if path.exists() and not args.force:
            df = pd.read_parquet(path)
            log.info("%s: already cached (%d rows) - use --force to re-pull",
                     zone, len(df))
        else:
            log.info("\n=== %s : %s -> now ===", zone, start.date())
            df = backfill_zone(key, zone, start, chunk_days=args.chunk_days)
            if df.empty:
                log.warning("%s: no data returned", zone)
                continue
            df.to_parquet(path, index=False)
            log.info("%s: wrote %d rows -> %s", zone, len(df), path.name)

        measured = (~df["is_estimated"].fillna(True)).sum()
        summary.append({
            "zone": zone,
            "rows": len(df),
            "from": df["datetime_utc"].min(),
            "to": df["datetime_utc"].max(),
            "measured": measured,
            "measured_pct": round(measured / len(df) * 100, 1),
            "mean_mw": round(df["demand_mw"].mean()),
            "max_mw": round(df["demand_mw"].max()),
        })

    if summary:
        print("\n" + "=" * 78)
        print("BACKFILL SUMMARY")
        print("=" * 78)
        print(pd.DataFrame(summary).to_string(index=False))
        print("\n'measured' = rows with isEstimated == False. Only these are")
        print("safe to train on; the rest are TIME_SLICER_AVERAGE fill-ins.")


if __name__ == "__main__":
    main()
