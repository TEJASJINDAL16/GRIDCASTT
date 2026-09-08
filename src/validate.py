"""Ingest validation — plain assertions, no framework (PLANNING 14).

Both APIs can change shape silently. A renamed column or a unit change does not
raise; it produces a plausible wrong forecast. That is section 9's philosophy
applied to ingest: the failure mode worth engineering against is the one that
does not announce itself.

So every ingest passes through here before anything is written to disk, and a
hard failure refuses the write rather than degrading.

Two severities, and the split is deliberate:

  HARD   missing columns, duplicate timestamps, naive or non-UTC timestamps,
         values outside a physically plausible range, `is_estimated` absent,
         an empty frame. These mean the source changed shape or the conversion
         point (11) broke. Raise, refuse to write.

  SOFT   gaps in the time index. PLANNING 5h says to log a gap and exclude
         those rows, not to fail - a multi-year cached history legitimately
         has holes. Reported in the returned ValidationReport and logged
         loudly. A window that is supposed to be contiguous is a different
         claim: callers pass contiguous=True and gaps become hard there.

Column names are snake_case throughout. Section 11 puts exactly one camelCase
conversion point in src/ingest/; asserting the snake_case form here is what
makes a second, undeclared conversion point fail fast.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd

log = logging.getLogger(__name__)

# Written on ingest by src/ingest/electricity_maps.py::_flatten.
DEMAND_REQUIRED_COLUMNS = [
    "datetime_utc",
    "zone",
    "demand_mw",
    "is_estimated",
    "updated_at",
    "created_at",
]

# Open-Meteo returns whatever `hourly` variables were asked for; only the
# index and temperature are structurally required.
WEATHER_REQUIRED_COLUMNS = ["temperature_2m"]


class ValidationError(Exception):
    """An ingest failed validation. The caller must not write."""


@dataclass
class ValidationReport:
    """What passed, and what was odd but not fatal."""

    source: str
    label: str
    rows: int
    span: tuple[pd.Timestamp, pd.Timestamp] | None = None
    gap_hours: int = 0
    gap_count: int = 0
    largest_gap_hours: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def gap_fraction(self) -> float:
        expected = self.rows + self.gap_hours
        return self.gap_hours / expected if expected else 0.0

    def log(self) -> None:
        log.info(
            "validate %s/%s: %d rows, %s..%s, %d gaps (%d hours, largest %dh, %.2f%%)",
            self.source, self.label, self.rows,
            self.span[0] if self.span else "-", self.span[1] if self.span else "-",
            self.gap_count, self.gap_hours, self.largest_gap_hours,
            self.gap_fraction * 100,
        )
        for w in self.warnings:
            log.warning("validate %s/%s: %s", self.source, self.label, w)


def _fail(source: str, label: str, message: str) -> None:
    raise ValidationError(f"{source}/{label}: {message}")


def _check_columns(df: pd.DataFrame, required: list[str], source: str, label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        _fail(source, label,
              f"missing column(s) {missing}. Present: {sorted(df.columns)}. "
              "The API shape changed, or the snake_case conversion in "
              "src/ingest/ was bypassed (see PLANNING 11).")


def _check_utc(series: pd.Series, source: str, label: str, what: str) -> None:
    if not pd.api.types.is_datetime64_any_dtype(series):
        _fail(source, label, f"{what} is not a datetime column (dtype {series.dtype})")
    tz = getattr(series.dt, "tz", None)
    if tz is None:
        _fail(source, label,
              f"{what} is timezone-naive. Timestamps are UTC on the wire (11); "
              "a naive column is one implicit conversion away from silently "
              "shifting every calendar feature by 5h30 (5e).")
    if str(tz) not in ("UTC", "utc"):
        _fail(source, label, f"{what} carries timezone {tz}, expected UTC")


def _check_range(
    series: pd.Series, lo: float, hi: float, source: str, label: str, what: str
) -> None:
    finite = series.dropna()
    if finite.empty:
        return
    below, above = finite[finite < lo], finite[finite > hi]
    if len(below) or len(above):
        _fail(source, label,
              f"{what} outside the plausible range [{lo}, {hi}]: "
              f"{len(below)} below (min {finite.min()}), "
              f"{len(above)} above (max {finite.max()}). "
              "These bounds are loose by design — breaching one means a unit "
              "change or a renamed field, not an extreme observation.")


def _check_gaps(
    index: pd.Series, freq_hours: int, source: str, label: str,
    report: ValidationReport, contiguous: bool,
) -> None:
    if len(index) < 2:
        return
    ordered = index.sort_values()
    deltas = ordered.diff().dropna()
    step = pd.Timedelta(hours=freq_hours)

    finer = deltas[deltas < step]
    if len(finer):
        _fail(source, label,
              f"{len(finer)} interval(s) shorter than the expected {freq_hours}h "
              f"(smallest {finer.min()}). Granularity is not what config says.")

    gaps = deltas[deltas > step]
    missing = int(((gaps - step) / step).sum()) if len(gaps) else 0
    report.gap_count = len(gaps)
    report.gap_hours = missing * freq_hours
    report.largest_gap_hours = (
        int(gaps.max().total_seconds() // 3600) if len(gaps) else 0
    )

    if contiguous and len(gaps):
        _fail(source, label,
              f"{len(gaps)} gap(s) totalling {missing} missing row(s) in a window "
              "that must be contiguous")


def validate_demand(
    df: pd.DataFrame,
    zone: str,
    cfg: dict,
    contiguous: bool = False,
) -> ValidationReport:
    """Check a demand frame. Raises ValidationError; the caller must not write."""
    source, v = "demand", cfg["validate"]
    report = ValidationReport(source=source, label=zone, rows=len(df))

    if df.empty:
        _fail(source, zone, "empty frame — the API returned nothing")

    _check_columns(df, DEMAND_REQUIRED_COLUMNS, source, zone)
    _check_utc(df["datetime_utc"], source, zone, "datetime_utc")

    dupes = df.duplicated(subset=["zone", "datetime_utc"]).sum()
    if dupes:
        _fail(source, zone,
              f"{dupes} duplicate (zone, datetime_utc) row(s). A duplicated "
              "hour double-counts in every mean and every fold.")

    zones = set(df["zone"].dropna().unique())
    if zones != {zone}:
        _fail(source, zone, f"frame contains zones {sorted(zones)}, expected only {zone}")

    _check_range(df["demand_mw"], v["demand_mw_min"], v["demand_mw_max"],
                 source, zone, "demand_mw")

    if df["is_estimated"].isna().all():
        _fail(source, zone,
              "is_estimated is entirely null. INV-3 and INV-4 both depend on it; "
              "without it there is no way to tell a measurement from a "
              "TIME_SLICER_AVERAGE fill-in.")

    if df["demand_mw"].isna().all():
        _fail(source, zone,
              "demand_mw is entirely null. This is the target variable; a "
              "column of nulls is a failed pull wearing the shape of a "
              "successful one.")

    null_demand = int(df["demand_mw"].isna().sum())
    if null_demand:
        report.warnings.append(
            f"{null_demand} row(s) with null demand_mw — excluded downstream")

    null_flag = int(df["is_estimated"].isna().sum())
    if null_flag:
        report.warnings.append(
            f"{null_flag} row(s) with null is_estimated — treated as estimated "
            "(INV-3 fails safe)")

    _check_gaps(df["datetime_utc"], v["expected_freq_hours"], source, zone,
                report, contiguous)

    report.span = (df["datetime_utc"].min(), df["datetime_utc"].max())
    if report.gap_fraction > v["max_gap_fraction_warn"]:
        report.warnings.append(
            f"gap fraction {report.gap_fraction:.2%} exceeds "
            f"max_gap_fraction_warn ({v['max_gap_fraction_warn']:.2%})")

    report.log()
    return report


def validate_weather(
    df: pd.DataFrame,
    label: str,
    cfg: dict,
    contiguous: bool = True,
) -> ValidationReport:
    """Check a weather frame, indexed by datetime.

    Contiguous by default: unlike demand history, a weather pull covers a range
    the API is expected to serve completely, so a hole means a failed request
    rather than a hole in the world.
    """
    source, v = "weather", cfg["validate"]
    report = ValidationReport(source=source, label=label, rows=len(df))

    if df.empty:
        _fail(source, label, "empty frame — the API returned nothing")

    _check_columns(df, WEATHER_REQUIRED_COLUMNS, source, label)

    if "datetime_utc" in df.columns:
        stamps = df["datetime_utc"]
    else:
        stamps = pd.Series(df.index, name="datetime_utc")
    _check_utc(stamps, source, label, "the time index")

    dupes = stamps.duplicated().sum()
    if dupes:
        _fail(source, label, f"{dupes} duplicate timestamp(s)")

    _check_range(df["temperature_2m"], v["temperature_c_min"], v["temperature_c_max"],
                 source, label, "temperature_2m")

    if df["temperature_2m"].isna().all():
        _fail(source, label,
              "temperature_2m is entirely null. Temperature is the dominant "
              "driver (5e); a column of nulls is a failed pull wearing the "
              "shape of a successful one.")

    null_temp = int(df["temperature_2m"].isna().sum())
    if null_temp:
        report.warnings.append(f"{null_temp} row(s) with null temperature_2m")

    _check_gaps(stamps, v["expected_freq_hours"], source, label, report, contiguous)

    report.span = (stamps.min(), stamps.max())
    report.log()
    return report
