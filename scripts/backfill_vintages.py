"""Recover weather forecast vintages that were never captured.

PLANNING 5d says the vintage gap "cannot be closed retroactively" and that
"every day without archiving is a vintage that can never be recovered". That
was measured to be false on 2026-09-13: Open-Meteo serves, for arbitrary past
dates from 2022 onward, what the forecast said 1 to 7 days before each target
hour, across all eight configured variables.

    make backfill-vintages                                  # configured span
    make backfill-vintages ARGS="--start 2026-09-09 --end 2026-09-12"

WHY THIS IS A SIBLING SCRIPT AND A SEPARATE DIRECTORY

Recovered vintages are NOT written into `data/raw/forecast_vintages/`. They are
a different kind of evidence and mixing them would quietly weaken the captured
set:

  provenance   a third party's retroactive archive, not our own capture
  issue time   unknown within the day; only the lead in DAYS is known, where a
               captured vintage carries the exact issued_at
  horizon      leads stop at 7 days; our own capture stores 16
  model        Open-Meteo's forecast model changed across 2022-2026, so error
               measured on old vintages reflects the model of that era, not
               today's skill

5d's point-in-time-correctness claim rests on the captured set. This archive is
for measuring forecast error by lead time and for training on realistic inputs
— both of which it does honestly, provided nobody mistakes it for the real
thing. Every row carries `source` saying what it is.

The daily archive continues regardless. This closes a historical gap; it does
not remove the reason to capture tomorrow.
"""

import argparse
import logging
import pathlib
import sys
import time
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, get, load_config
from src.ingest.weather import fetch_previous_runs
from src.validate import ValidationError, validate_weather

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill-vintages")

SOURCE = "open_meteo_previous_runs"


def year_spans(start: str, end: str) -> list[tuple[str, str]]:
    """Split an inclusive range into calendar-year pieces.

    Open-Meteo prices a request by the volume it returns, and this asks for
    eight variables at seven leads — 56 series. One multi-year request would be
    rate-limited on its own.
    """
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    spans, cursor = [], first
    while cursor <= last:
        stop = min(date(cursor.year, 12, 31), last)
        spans.append((cursor.isoformat(), stop.isoformat()))
        cursor = date(cursor.year + 1, 1, 1)
    return spans


def main() -> None:
    cfg = load_config()
    weather = get(cfg, "weather")
    points = get(cfg, "weather.points")

    ap = argparse.ArgumentParser()
    ap.add_argument("--zones", nargs="*", default=get(cfg, "demand.all_zones"))
    ap.add_argument("--start", default=get(cfg, "archive.recovery_start"))
    ap.add_argument("--end", default=None, help="default: yesterday")
    ap.add_argument("--max-lead", type=int,
                    default=get(cfg, "archive.recovery_max_lead_days"))
    ap.add_argument("--pause", type=float, default=2.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    end = args.end or (pd.Timestamp.utcnow() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    out_dir = PROJECT_ROOT / get(cfg, "archive.recovered_vintage_dir")
    out_dir.mkdir(parents=True, exist_ok=True)

    summary, failures = [], []
    for span_start, span_end in year_spans(args.start, end):
        label = span_start[:4]
        path = out_dir / f"recovered_{label}.parquet"
        if path.exists() and not args.force:
            log.info("%s: already recovered (%d rows) - use --force to re-pull",
                     label, len(pd.read_parquet(path)))
            continue

        frames = []
        for zone in args.zones:
            if zone not in points:
                log.error("  %s: no weather point configured", zone)
                failures.append(f"{label}/{zone}")
                continue
            point = points[zone]
            try:
                df = fetch_previous_runs(
                    point["lat"], point["lon"], weather["variables"],
                    span_start, span_end, args.max_lead,
                    weather["historical_forecast_url"])
            except Exception as exc:
                log.error("  %s %s: FAILED - %s", label, zone, exc)
                failures.append(f"{label}/{zone}")
                continue

            if df.empty or df["temperature_2m"].isna().all():
                # Recorded as a failure, not merely logged. A zone that
                # silently vanishes leaves an archive that looks complete and
                # is not - the exact failure mode section 9 is about. IN-NE
                # disappeared from the 2024 span this way on the first run,
                # and the script still exited zero.
                log.error("  %s %s: NO DATA SERVED - recorded as a failure",
                          label, zone)
                failures.append(f"{label}/{zone}")
                continue

            df = df.dropna(subset=["temperature_2m"])
            df.insert(1, "zone", zone)
            df.insert(2, "point_name", point["name"])
            df["source"] = SOURCE
            # The lead is known only in days, so the implied issue date is
            # target date minus lead. Deliberately a DATE, not a timestamp:
            # inventing an issue time would make this look like a captured
            # vintage, which is exactly the confusion the separate directory
            # exists to prevent.
            df["issued_date_est"] = (
                df["target_datetime"].dt.tz_convert("UTC").dt.normalize()
                - pd.to_timedelta(df["lead_days"], unit="D")).dt.date

            # Validate the freshest lead as a plain weather frame. It must look
            # like weather before it is allowed onto disk (PLANNING 14).
            probe = (df[df["lead_days"] == df["lead_days"].min()]
                     .rename(columns={"target_datetime": "datetime_utc"})
                     .set_index("datetime_utc"))
            try:
                validate_weather(probe, f"{zone} recovered {label}", cfg,
                                 contiguous=False)
            except ValidationError as exc:
                log.error("  %s %s: REFUSED - %s", label, zone, exc)
                failures.append(f"{label}/{zone}")
                continue

            frames.append(df)
            log.info("  %s %s: %d rows, leads %d-%d, %s..%s",
                     label, zone, len(df), df["lead_days"].min(),
                     df["lead_days"].max(),
                     df["target_datetime"].min().date(),
                     df["target_datetime"].max().date())
            time.sleep(args.pause)

        if not frames:
            continue
        combined = pd.concat(frames, ignore_index=True)
        # MERGE with whatever is already there, never overwrite. Running with
        # --zones for one zone previously replaced the file wholesale and
        # destroyed the other four - a repair that quietly deleted more than
        # it fixed.
        if path.exists():
            combined = pd.concat([pd.read_parquet(path), combined],
                                 ignore_index=True)
        combined = combined.drop_duplicates(
            subset=["zone", "target_datetime", "lead_days"], keep="last")
        combined = combined.sort_values(["zone", "target_datetime", "lead_days"])
        combined.to_parquet(path, index=False)
        present = sorted(combined["zone"].unique())
        absent = [z for z in args.zones if z not in present]
        summary.append({"span": label, "rows": len(combined),
                        "zones": len(present),
                        "missing_zones": ",".join(absent) or "-",
                        "from": combined["target_datetime"].min(),
                        "to": combined["target_datetime"].max()})
        if absent:
            log.error("%s: MISSING ZONES %s", label, absent)
        log.info("%s: wrote %d rows -> %s", label, len(combined), path.name)

    if summary:
        print("\n" + "=" * 78)
        print("RECOVERED VINTAGE SUMMARY")
        print("=" * 78)
        print(pd.DataFrame(summary).to_string(index=False))
        print(f"\nsource = {SOURCE}. These are RECONSTRUCTED vintages, kept")
        print("apart from the captured archive on purpose - see this script's")
        print("docstring for why, and never merge the two without deciding to.")

    if failures:
        log.error("\n%d span/zone pair(s) failed: %s", len(failures), failures)
        sys.exit(1)


if __name__ == "__main__":
    main()
