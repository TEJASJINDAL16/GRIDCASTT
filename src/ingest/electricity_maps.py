"""Electricity Maps ingestion.

Confirmed API shape (probed 2026-09-03):
    base    https://api.electricitymap.org/v3
    auth    header  auth-token: <key>
    range   GET /power-breakdown/past-range?zone=&start=&end=
    target  powerConsumptionTotal  (MW)

Two things about this source drive the design here:

1. Rows carry `isEstimated`. When real meter data has not arrived, the value is
   filled with a TIME_SLICER_AVERAGE - literally a historical average for that
   time slice. Training on those teaches the model to reproduce an average, so
   they are kept but flagged, and filtered out at training time.

2. Rows are REVISED. A row published as an estimate is overwritten with the
   measured value days later (visible as updatedAt > createdAt). So `isEstimated`
   and `updatedAt` are stored, not discarded - without them you cannot tell what
   the data looked like at the moment a forecast was made.
"""

import logging
import time
from datetime import UTC, datetime, timedelta

import pandas as pd
import requests

log = logging.getLogger(__name__)

BASE = "https://api.electricitymap.org/v3"
RANGE_PATH = "/power-breakdown/past-range"

# Fuel columns are kept for the solar / duck-curve analysis later.
_FUELS = ["nuclear", "geothermal", "biomass", "coal", "wind", "solar",
          "hydro", "gas", "oil", "unknown"]


def _flatten(row: dict, zone: str) -> dict:
    """One API row -> one flat record."""
    cons = row.get("powerConsumptionBreakdown") or {}
    out = {
        "datetime_utc": row.get("datetime"),
        "zone": zone,
        "demand_mw": row.get("powerConsumptionTotal"),
        "production_mw": row.get("powerProductionTotal"),
        "import_mw": row.get("powerImportTotal"),
        "export_mw": row.get("powerExportTotal"),
        "is_estimated": row.get("isEstimated"),
        "estimation_method": row.get("estimationMethod"),
        "fossil_free_pct": row.get("fossilFreePercentage"),
        "renewable_pct": row.get("renewablePercentage"),
        "updated_at": row.get("updatedAt"),
        "created_at": row.get("createdAt"),
    }
    for fuel in _FUELS:
        out[f"gen_{fuel}_mw"] = cons.get(fuel)
    return out


def fetch_range(
    key: str,
    zone: str,
    start: datetime,
    end: datetime,
    session: requests.Session | None = None,
    retries: int = 4,
) -> list[dict]:
    """Fetch one [start, end) window. Retries with backoff on transient failure."""
    sess = session or requests.Session()
    params = {
        "zone": zone,
        "start": start.strftime("%Y-%m-%dT%H:00:00Z"),
        "end": end.strftime("%Y-%m-%dT%H:00:00Z"),
    }
    delay = 2.0
    for attempt in range(retries):
        try:
            r = sess.get(BASE + RANGE_PATH, headers={"auth-token": key},
                         params=params, timeout=90)
            if r.status_code == 200:
                body = r.json()
                rows = body.get("data", body if isinstance(body, list) else [])
                return [_flatten(x, zone) for x in rows]
            if r.status_code == 429:            # rate limited - wait longer
                log.warning("rate limited, sleeping %.0fs", delay * 4)
                time.sleep(delay * 4)
            elif 400 <= r.status_code < 500:    # our fault, retrying won't help
                log.error("%s %s -> %s", zone, params["start"][:10], r.text[:200])
                return []
        except Exception as e:
            log.warning("attempt %d failed for %s %s: %s",
                        attempt + 1, zone, params["start"][:10], e)
        time.sleep(delay)
        delay *= 2
    log.error("gave up on %s %s", zone, params["start"][:10])
    return []


def probe_earliest(
    key: str,
    zone: str,
    floor: datetime,
    session: requests.Session | None = None,
    window_days: int = 7,
) -> datetime | None:
    """Binary-search the earliest date this zone actually serves.

    PLANNING 11 recorded "at least 4 years; probe did not reach the limit",
    which is a lower bound, not a finding. `trend` is defined as days since
    demand.backfill_start (5e), so a guessed origin is a feature definition
    built on a guess — and more history is more folds and a longer holdout.

    Costs about log2(days) requests: a dozen, not a backfill.
    """
    sess = session or requests.Session()
    today = datetime.now(UTC)

    def has_data(when: datetime) -> bool:
        return bool(fetch_range(key, zone, when, when + timedelta(days=window_days), sess))

    if not has_data(floor):
        lo, hi = floor, today            # data starts somewhere after the floor
    else:
        log.info("  %s: data exists at the floor %s — the true start is earlier",
                 zone, floor.date())
        return floor

    # Invariant: lo has no data, hi has data. Narrow to a day.
    if not has_data(hi - timedelta(days=window_days * 2)):
        log.warning("  %s: no data anywhere in [%s, now]", zone, floor.date())
        return None

    while (hi - lo).days > window_days:
        mid = lo + (hi - lo) / 2
        if has_data(mid):
            hi = mid
        else:
            lo = mid
        time.sleep(0.3)

    log.info("  %s: earliest data around %s", zone, hi.date())
    return hi


def backfill_zone(
    key: str,
    zone: str,
    start: datetime,
    end: datetime | None = None,
    chunk_days: int = 9,        # the endpoint refuses more than 10 (demand.chunk_days)
    pause: float = 0.4,
) -> pd.DataFrame:
    """Pull a zone's full history in chunks and return it as one DataFrame."""
    end = end or datetime.now(UTC)
    sess = requests.Session()
    frames, cursor, empty_streak = [], start, 0

    while cursor < end:
        stop = min(cursor + timedelta(days=chunk_days), end)
        rows = fetch_range(key, zone, cursor, stop, sess)
        if rows:
            frames.append(pd.DataFrame(rows))
            empty_streak = 0
            log.info("  %s  %s..%s  %4d rows",
                     zone, cursor.date(), stop.date(), len(rows))
        else:
            empty_streak += 1
            log.info("  %s  %s..%s  empty", zone, cursor.date(), stop.date())
            # Six empty months in a row means we are before the data starts.
            if empty_streak >= 6 and not frames:
                log.info("  %s: no data this far back, skipping ahead", zone)
        cursor = stop
        time.sleep(pause)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)
    df["datetime_utc"] = pd.to_datetime(df["datetime_utc"], utc=True)
    df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True, errors="coerce")
    df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
    df = (df.drop_duplicates(subset=["zone", "datetime_utc"], keep="last")
            .sort_values("datetime_utc")
            .reset_index(drop=True))
    return df
