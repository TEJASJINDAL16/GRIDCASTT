"""Electricity Maps — data verification probe.

Answers what the dashboard cannot tell us:
  1. Does load / power-consumption data actually come back for Indian zones?
  2. How far back does the history go?
  3. Is the data measured or estimated?
  4. What are the rate limits?

Run:  python3 scripts/verify_em.py      (reads the key from .env)
Paste the entire output back into the chat.
"""

import json
import pathlib
import sys
from datetime import UTC, datetime, timedelta

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import requests

from src.config import get_api_key, load_config

KEY = get_api_key("EM_API_KEY")
ZONE = load_config()["demand"]["primary_zone"]

BASES = ["https://api.electricitymap.org/v3",
         "https://api.electricitymaps.com/v3",
         "https://api.electricitymaps.com/v1"]

PATHS = ["/power-consumption-breakdown/latest",
         "/power-breakdown/latest",
         "/total-load/latest",
         "/net-load/latest",
         "/electricity-mix/latest"]

AUTH = [("auth-token", lambda k: {"auth-token": k}),
        ("X-BLOBR-KEY", lambda k: {"X-BLOBR-KEY": k}),
        ("Bearer", lambda k: {"Authorization": f"Bearer {k}"})]

L = "-" * 74


def limits(r):
    hits = {k: v for k, v in r.headers.items()
            if any(t in k.lower() for t in ("ratelimit", "rate-limit", "quota", "remaining"))}
    for k, v in hits.items():
        print(f"     {k}: {v}")


def probe():
    print(L)
    print("STEP 1 - find a working endpoint")
    print(L)
    for base in BASES:
        for path in PATHS:
            for name, build in AUTH:
                try:
                    r = requests.get(base + path, headers=build(KEY),
                                     params={"zone": ZONE}, timeout=25)
                except Exception:
                    continue
                if r.status_code == 200:
                    print(f"  OK   {path}  [{name}]")
                    print(f"       base = {base}")
                    limits(r)
                    return base, path, build, r
                if r.status_code in (401, 403):
                    print(f"  {r.status_code}  {path}  [{name}]")
    return None, None, None, None


def main():
    print(f"\nZone: {ZONE}\n")
    base, path, build, resp = probe()
    if not base:
        print("\nNo working combination. Open the API reference while logged in")
        print("and send: base URL, the load/power path, and the auth header name.")
        return

    print("\n" + L)
    print("STEP 2 - raw response shape")
    print(L)
    print("Looking for: a value in MW, and any estimation flag.\n")
    print(json.dumps(resp.json(), indent=2)[:3000])

    print("\n" + L)
    print("STEP 3 - how far back does history go?")
    print(L)
    past = path.replace("/latest", "/past")
    hist = path.replace("/latest", "/history")
    for days in [1, 7, 30, 90, 180, 365, 730, 1095, 1460]:
        when = datetime.now(UTC) - timedelta(days=days)
        hit = False
        for p in (past, hist):
            try:
                r = requests.get(base + p, headers=build(KEY),
                                 params={"zone": ZONE,
                                         "datetime": when.strftime("%Y-%m-%dT%H:00:00Z")},
                                 timeout=25)
                if r.status_code == 200 and r.text.strip() not in ("", "{}", "[]"):
                    print(f"  OK   {days:5d} days back ({when:%Y-%m-%d})  via {p}")
                    hit = True
                    break
            except Exception:
                pass
        if not hit:
            print(f"  --   {days:5d} days back ({when:%Y-%m-%d})  no data")
            break

    print("\n" + L)
    print("STEP 4 - hourly range in one call?")
    print(L)
    rng = path.replace("/latest", "/past-range")
    end = datetime.now(UTC) - timedelta(days=2)
    start = end - timedelta(days=7)
    try:
        r = requests.get(base + rng, headers=build(KEY),
                         params={"zone": ZONE,
                                 "start": start.strftime("%Y-%m-%dT00:00:00Z"),
                                 "end": end.strftime("%Y-%m-%dT00:00:00Z"),
                                 "temporalGranularity": "hourly"}, timeout=60)
        print(f"  status {r.status_code}  ({rng})")
        if r.status_code == 200:
            body = r.json()
            rows = body.get("data", body if isinstance(body, list) else [])
            print(f"  rows for a 7-day window: {len(rows)}  (expect ~168 if hourly)")
            limits(r)
            if rows:
                print("\n  first row:")
                print(json.dumps(rows[0], indent=2)[:1200])
        else:
            print(f"  body: {r.text[:400]}")
    except Exception as e:
        print(f"  failed: {e}")

    print("\n" + L)
    print("Done - paste all of the above back.")
    print(L)


if __name__ == "__main__":
    main()
