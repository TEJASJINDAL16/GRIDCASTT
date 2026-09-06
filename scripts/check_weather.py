"""Verify the Open-Meteo side end to end. Needs no API key."""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd
from src.config import load_config
from src.ingest.weather import fetch_archive, fetch_forecast

cfg = load_config()
w = cfg["weather"]
pt = w["points"]["IN-NO"]
line = "-" * 70

print(line); print(f"ARCHIVE (observed) — {pt['name']}"); print(line)
hist = fetch_archive(pt["lat"], pt["lon"], "2024-05-01", "2024-05-31",
                     w["variables"], w["archive_url"], cfg["project"]["timezone"])
print(f"rows: {len(hist)}   (31 days x 24h = 744 expected)")
print(f"span: {hist.index.min()}  ->  {hist.index.max()}")
print(f"nulls: {hist.isna().sum().sum()}")
print(hist.head(3).to_string())
print(f"\nMay 2024 Delhi temp: min {hist.temperature_2m.min():.1f}C  "
      f"mean {hist.temperature_2m.mean():.1f}C  max {hist.temperature_2m.max():.1f}C")

print("\n" + line); print("HOW FAR BACK DOES THE ARCHIVE GO?"); print(line)
for year in [2015, 2018, 2020, 2021, 2022]:
    try:
        t = fetch_archive(pt["lat"], pt["lon"], f"{year}-06-01", f"{year}-06-02",
                          ["temperature_2m"], w["archive_url"], cfg["project"]["timezone"])
        ok = t.temperature_2m.notna().sum()
        print(f"  {year}: {len(t)} rows, {ok} non-null  {'OK' if ok else 'EMPTY'}")
    except Exception as e:
        print(f"  {year}: FAILED {e}")

print("\n" + line); print("FORECAST (prediction)"); print(line)
fc = fetch_forecast(pt["lat"], pt["lon"], w["variables"], 7,
                    w["forecast_url"], cfg["project"]["timezone"])
print(f"rows: {len(fc)}   span: {fc.index.min()} -> {fc.index.max()}")
print(fc.head(3).to_string())

print("\n" + line); print("DAILY SHAPE (May 2024 avg temp by hour)"); print(line)
by_hour = hist.groupby(hist.index.hour).temperature_2m.mean()
lo, hi = by_hour.min(), by_hour.max()
for h, v in by_hour.items():
    bar = "#" * int((v - lo) / (hi - lo) * 46)
    print(f"  {h:02d}:00  {v:5.1f}C  {bar}")
