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
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT, load_config
from src.ingest.archive import (
    archive_demand_revisions,
    archive_forecast_vintage,
    archive_observed_weather,
    log,
)


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
    with record.open("a", encoding="utf-8") as f:
        f.write(json.dumps(status, default=str) + "\n")
    log.info("status: %s -> %s", status["outcome"], record.name)

    if failed_any:
        # 14: anything 5h calls an alert exits non-zero. A missed vintage is
        # permanent data loss, so it must not exit quietly.
        log.error("one or more parts failed: %s", status["failed_zones"])
        sys.exit(1)


if __name__ == "__main__":
    main()
