"""Pull the full demand history and cache it to disk.

Run once. The cached parquet files are what every later step reads, so the
project keeps working if the API licence lapses or the service changes.

    make backfill                              # all zones, configured start
    make backfill ARGS="--probe-history"       # find the true earliest date first
    make backfill ARGS="--zones IN-NO --force"
"""

import argparse
import logging
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, get, get_api_key, load_config
from src.ingest.electricity_maps import backfill_zone, probe_earliest
from src.validate import ValidationError, validate_demand

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill")


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=get(cfg, "demand.all_zones"))
    # No default date here. PLANNING 4: every tunable lives in config.yaml.
    # The origin also defines `trend` (5e), so it must have exactly one home.
    ap.add_argument("--start", default=None,
                    help="override demand.backfill_start (config is the default)")
    ap.add_argument("--chunk-days", type=int, default=get(cfg, "demand.chunk_days"))
    ap.add_argument("--probe-history", action="store_true",
                    help="binary-search the earliest date each zone serves, then exit")
    ap.add_argument("--force", action="store_true", help="re-pull zones already saved")
    args = ap.parse_args()

    key = get_api_key("EM_API_KEY")
    out_dir = PROJECT_ROOT / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    start = datetime.fromisoformat(
        args.start or get(cfg, "demand.backfill_start")).replace(tzinfo=UTC)

    if args.probe_history:
        # A floor early enough to be safely before any plausible start.
        floor = datetime(2015, 1, 1, tzinfo=UTC)
        log.info("Probing history depth (floor %s). Configured start is %s.",
                 floor.date(), start.date())
        found = {z: probe_earliest(key, z, floor) for z in args.zones}
        print("\n" + "=" * 78)
        print("HISTORY DEPTH")
        print("=" * 78)
        for zone, when in found.items():
            print(f"  {zone:6s}  {when.date() if when else 'no data found'}")
        usable = [w for w in found.values() if w]
        if usable:
            latest_start = max(usable)
            print(f"\n  All five zones have data from: {latest_start.date()}")
            print("  Set demand.backfill_start to that date if it beats the")
            print(f"  configured {start.date()}. `trend` is defined from it (5e),")
            print("  so record the move in the step-0 report.")
        return

    summary, failures = [], []
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
                # Not a warning. An empty pull is indistinguishable from a
                # successful one downstream, and that is how a chunk size above
                # the API's limit produces a backfill that looks complete.
                log.error("%s: NO DATA RETURNED — refusing to write", zone)
                failures.append(zone)
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
        print("\n'measured' = rows with isEstimated == False.")
        print("The estimated rows are NOT all TIME_SLICER_AVERAGE fill-ins: the")
        print("source uses at least three estimation methods, and they are not")
        print("equivalent. See reports/step0_measurements.md before deciding")
        print("which are trainable (INV-3).")

    for zone in args.zones:
        path = out_dir / f"demand_{zone}.parquet"
        if path.exists():
            try:
                validate_demand(pd.read_parquet(path), zone, cfg)
            except ValidationError as exc:
                log.error("%s: cached file FAILS validation — %s", zone, exc)
                failures.append(zone)

    if failures:
        # PLANNING 14: anything 5h calls an alert exits non-zero.
        log.error("\n%d zone(s) failed: %s", len(failures), sorted(set(failures)))
        sys.exit(1)


if __name__ == "__main__":
    main()
