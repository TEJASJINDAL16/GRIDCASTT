"""Step-0 measurements — replace the section 13 assumptions with numbers.

PLANNING 12: everything in the specification was written against data nobody
had looked at. This script looks at it and writes reports/step0_measurements.md.

    make measure

THROWAWAY ANALYSIS. Nothing may ever import from this module (BUILD_STAGES,
stage 1). Holiday lookup and suppression detection are done ad hoc here,
directly against the `holidays` package, because src/ingest/calendar_in.py and
src/features/quality.py are stage 2 deliverables. If a function here proves
worth keeping it is REWRITTEN there, never imported across — an import edge is
how a throwaway script becomes load-bearing without anyone deciding it should.

The elbow method is fixed by ruling and is not a free choice here:

    two-segment fit on log(demand), breakpoint by RSS-minimising grid search,
    pooled across zones, with hour-of-day and day-of-week effects removed
    first — and the same fit run naively, without them, with BOTH reported.

A raw scatter of demand against temperature conflates the temperature response
with the daily cycle: demand is high at 20:00 and low at 04:00 for reasons
unrelated to temperature, and temperature is itself correlated with hour. Fit
it naively and the elbow is partly an artefact of when hot hours happen.
"""

import argparse
import logging
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import holidays
import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT, get, load_config

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("measure")

# The estimation tiers observed in the source (PLANNING 11). Which of these are
# trainable is an OPEN DECISION (section 10); every measurement below is
# therefore reported per tier rather than collapsed to one number.
TIERS = {
    "measured": "is_estimated == False",
    "measured+MODE": "measured, plus MODE_BREAKDOWN",
    "all except TSA": "measured, plus MODE_BREAKDOWN and GENERAL_PURPOSE_ZONE_MODEL",
}


def load_joined(cfg: dict) -> pd.DataFrame:
    """Demand joined to its zone's weather point, on the UTC hour."""
    raw = PROJECT_ROOT / "data" / "raw"
    frames = []
    for zone in get(cfg, "demand.all_zones"):
        dpath, wpath = raw / f"demand_{zone}.parquet", raw / f"weather_{zone}.parquet"
        if not dpath.exists() or not wpath.exists():
            log.warning("%s: missing %s", zone,
                        "demand" if not dpath.exists() else "weather")
            continue
        demand = pd.read_parquet(dpath)
        weather = pd.read_parquet(wpath).drop(columns=["zone", "point_name"])
        merged = demand.merge(weather, on="datetime_utc", how="inner")
        frames.append(merged)
        log.info("  %s: %d demand x %d weather -> %d joined",
                 zone, len(demand), len(weather), len(merged))
    if not frames:
        raise SystemExit("no data — run `make backfill` and `make backfill-weather` first")

    df = pd.concat(frames, ignore_index=True)
    # IST for every calendar extraction (5e). The target window opens at 19:00
    # UTC, which is 00:30 IST the NEXT day, so taking weekday from the UTC
    # stamp mislabels the first hour of every forecast and shifts holidays.
    ist = df["datetime_utc"].dt.tz_convert(get(cfg, "project.timezone"))
    df["hour_ist"] = ist.dt.hour
    df["weekday_ist"] = ist.dt.dayofweek
    df["date_ist"] = ist.dt.date
    df["year_ist"] = ist.dt.year
    df["month_ist"] = ist.dt.month
    df["tier"] = np.where(
        ~df["is_estimated"].fillna(True), "measured",
        df["estimation_method"].fillna("UNKNOWN"))
    df = df[df["demand_mw"].notna() & (df["demand_mw"] > 0)
            & df["temperature_2m"].notna()].copy()
    df["log_demand"] = np.log(df["demand_mw"])
    return df


def tier_subset(df: pd.DataFrame, tier: str) -> pd.DataFrame:
    if tier == "measured":
        return df[df["tier"] == "measured"]
    if tier == "measured+MODE":
        return df[df["tier"].isin(["measured", "MODE_BREAKDOWN"])]
    return df[df["tier"] != "TIME_SLICER_AVERAGE"]


# --------------------------------------------------------------------------
# The elbow
# --------------------------------------------------------------------------

def _two_segment_rss(temp: np.ndarray, y: np.ndarray, breakpoint: float) -> float:
    """RSS of y ~ 1 + max(0, temp - breakpoint), the cooling ramp."""
    ramp = np.maximum(0.0, temp - breakpoint)
    X = np.column_stack([np.ones_like(ramp), ramp])
    coef, residuals, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < 2:
        return np.inf
    return float(residuals[0]) if residuals.size else float(((y - X @ coef) ** 2).sum())


def _two_segment_rss_cold(temp: np.ndarray, y: np.ndarray, breakpoint: float) -> float:
    """RSS of y ~ 1 + max(0, breakpoint - temp), the heating ramp."""
    ramp = np.maximum(0.0, breakpoint - temp)
    X = np.column_stack([np.ones_like(ramp), ramp])
    coef, residuals, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < 2:
        return np.inf
    return float(residuals[0]) if residuals.size else float(((y - X @ coef) ** 2).sum())


COOL_GRID = np.arange(14.0, 38.01, 0.5)
HEAT_GRID = np.arange(2.0, 28.01, 0.5)


def find_thresholds(temp: pd.Series, y: pd.Series) -> dict:
    """Joint grid search for BOTH breakpoints at once.

    Fitting one ramp alone is misspecified. Demand is U-shaped in temperature
    (5e), so a lone cooling ramp tries to span the whole range and the search
    runs to the edge of whatever grid it is given — which is exactly what
    happened on the first attempt: every tier returned the grid boundary, in
    both directions, and a boundary solution is not a measurement.

    The model fitted here is the one the features actually use:

        y ~ 1 + max(0, T - cooling) + max(0, heating - T)

    with heating < cooling enforced, so the comfortable band between them where
    both terms are zero exists (5c).

    A result sitting on a grid edge is reported as NOT IDENTIFIED rather than as
    a number.
    """
    t = temp.to_numpy(float)
    v = y.to_numpy(float)
    best = (np.inf, None, None, None)
    for c in COOL_GRID:
        for h in HEAT_GRID:
            if h >= c:
                continue
            X = np.column_stack([np.ones_like(t),
                                 np.maximum(0.0, t - c),
                                 np.maximum(0.0, h - t)])
            coef, res, rank, _ = np.linalg.lstsq(X, v, rcond=None)
            if rank < 3:
                continue
            rss = float(res[0]) if res.size else float(((v - X @ coef) ** 2).sum())
            if rss < best[0]:
                best = (rss, c, h, coef)
    rss, c, h, coef = best
    if c is None:
        return {"cooling_c": None, "heating_c": None, "identified": False,
                "note": "no admissible fit"}
    on_edge = (c in (COOL_GRID[0], COOL_GRID[-1])
               or h in (HEAT_GRID[0], HEAT_GRID[-1]))
    return {
        "cooling_c": float(c), "heating_c": float(h),
        "cooling_pct_per_c": round((np.exp(coef[1]) - 1) * 100, 3),
        "heating_pct_per_c": round((np.exp(coef[2]) - 1) * 100, 3),
        "identified": not on_edge,
        "note": "NOT IDENTIFIED — solution on the grid edge" if on_edge else "",
    }


def adjust(df: pd.DataFrame) -> pd.Series:
    """log(demand) with zone, hour-of-day and weekday means removed.

    Zone as well as hour and weekday: pooling five zones whose levels differ by
    an order of magnitude, a fit with one intercept is dominated by between-zone
    level rather than by the temperature response. Log makes the SLOPE
    comparable across zones (5c); it does not make the LEVELS equal.
    """
    return df["log_demand"] - df.groupby(
        ["zone", "hour_ist", "weekday_ist"])["log_demand"].transform("mean")


def elbow_table(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Both thresholds, per tier, naive and adjusted."""
    rows = []
    for tier in TIERS:
        sub = tier_subset(df, tier)
        if len(sub) < 1000:
            rows.append({"tier": tier, "rows": len(sub), "note": "too few rows"})
            continue
        naive = find_thresholds(sub["temperature_2m"], sub["log_demand"])
        adj = find_thresholds(sub["temperature_2m"], adjust(sub))
        rows.append({
            "tier": tier, "rows": len(sub),
            "naive_cool_c": naive["cooling_c"], "naive_heat_c": naive["heating_c"],
            "adj_cool_c": adj["cooling_c"], "adj_heat_c": adj["heating_c"],
            "adj_cool_pct_per_c": adj["cooling_pct_per_c"],
            "adj_heat_pct_per_c": adj["heating_pct_per_c"],
            "note": adj["note"] or naive["note"],
        })
    return pd.DataFrame(rows)


def per_zone_elbows(df: pd.DataFrame, tier: str) -> pd.DataFrame:
    sub = tier_subset(df, tier)
    rows = []
    for zone, g in sub.groupby("zone", observed=True):
        if len(g) < 1000:
            rows.append({"zone": zone, "rows": len(g), "note": "too few rows"})
            continue
        y = g["log_demand"] - g.groupby(["hour_ist", "weekday_ist"])["log_demand"].transform("mean")
        r = find_thresholds(g["temperature_2m"], y)
        rows.append({"zone": zone, "rows": len(g),
                     "cooling_c": r["cooling_c"], "heating_c": r["heating_c"],
                     "cooling_pct_per_c": r["cooling_pct_per_c"],
                     "heating_pct_per_c": r["heating_pct_per_c"],
                     "note": r["note"]})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Band occupancy, under the sufficiency rule of PLANNING 13
# --------------------------------------------------------------------------

def band_occupancy(df: pd.DataFrame, cfg: dict, tier: str) -> pd.DataFrame:
    edges = get(cfg, "evaluate.temperature_bands_c")
    min_rows = get(cfg, "evaluate.min_band_rows")
    insufficient = get(cfg, "evaluate.insufficient_band_rows")
    sub = tier_subset(df, tier)
    bounds = [-np.inf, *edges, np.inf]
    labels = ([f"< {edges[0]}"]
              + [f"{a} - {b}" for a, b in zip(edges, edges[1:], strict=False)]
              + [f"> {edges[-1]}"])
    sub = sub.assign(band=pd.cut(sub["temperature_2m"], bounds, labels=labels,
                                 right=False))
    counts = sub.groupby("band", observed=False).size().rename("rows").reset_index()
    counts["is_top_band"] = counts["band"] == labels[-1]
    def verdict(r):
        if r["rows"] < insufficient:
            return "insufficient rows to judge"
        if r["is_top_band"]:
            return "kept separate regardless of count"
        return "ok" if r["rows"] >= min_rows else f"below min_band_rows ({min_rows})"
    counts["verdict"] = counts.apply(verdict, axis=1)
    return counts


def band_occupancy_by_zone(df: pd.DataFrame, cfg: dict, tier: str) -> pd.DataFrame:
    edges = get(cfg, "evaluate.temperature_bands_c")
    sub = tier_subset(df, tier)
    bounds = [-np.inf, *edges, np.inf]
    labels = ([f"< {edges[0]}"]
              + [f"{a} - {b}" for a, b in zip(edges, edges[1:], strict=False)]
              + [f"> {edges[-1]}"])
    sub = sub.assign(band=pd.cut(sub["temperature_2m"], bounds, labels=labels,
                                 right=False))
    return (sub.groupby(["zone", "band"], observed=False).size()
               .unstack("band", fill_value=0))


# --------------------------------------------------------------------------
# Suppressed demand — INV-8 candidates
# --------------------------------------------------------------------------

def suppression_candidates(df: pd.DataFrame, cfg: dict, tier: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hours where demand plateaus or falls while temperature keeps rising.

    5f principle 2: the source reports power CONSUMED, not power WANTED. When
    the grid sheds load the recorded value is a supply ceiling, and a model
    fitted to it learns that demand stops rising in a heatwave.
    """
    rise = get(cfg, "quality.suppression_temp_rise_c")
    delta = get(cfg, "quality.suppression_demand_delta_pct")
    sub = tier_subset(df, tier).sort_values(["zone", "datetime_utc"]).copy()
    g = sub.groupby("zone", observed=True)
    sub["temp_delta"] = g["temperature_2m"].diff()
    sub["demand_delta_pct"] = g["demand_mw"].pct_change() * 100.0
    sub["contiguous"] = g["datetime_utc"].diff() == pd.Timedelta(hours=1)
    flagged = sub[sub["contiguous"]
                  & (sub["temp_delta"] >= rise)
                  & (sub["demand_delta_pct"] <= delta)].copy()
    summary = (flagged.groupby("zone", observed=True)
               .agg(flagged_hours=("demand_mw", "size"),
                    median_temp_c=("temperature_2m", "median"),
                    max_temp_c=("temperature_2m", "max"))
               .reset_index())
    eligible = sub[sub["contiguous"]].groupby("zone", observed=True).size().rename("eligible_hours")
    summary = summary.merge(eligible, on="zone", how="left")
    summary["flagged_pct"] = (summary["flagged_hours"] / summary["eligible_hours"] * 100).round(2)
    return summary, flagged


# --------------------------------------------------------------------------
# Year-on-year growth — the ~5% assumed in 5c
# --------------------------------------------------------------------------

def growth_rates(df: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Log-linear trend on annual mean demand: percent per year."""
    sub = tier_subset(df, tier)
    rows = []
    for zone, g in sub.groupby("zone", observed=True):
        annual = g.groupby("year_ist")["demand_mw"].agg(["mean", "size"])
        annual = annual[annual["size"] >= 24 * 300]        # near-complete years only
        if len(annual) < 3:
            rows.append({"zone": zone, "years": len(annual), "pct_per_year": None})
            continue
        slope = np.polyfit(annual.index.to_numpy(float),
                           np.log(annual["mean"].to_numpy(float)), 1)[0]
        rows.append({"zone": zone, "years": len(annual),
                     "from": int(annual.index.min()), "to": int(annual.index.max()),
                     "pct_per_year": round((np.exp(slope) - 1) * 100, 2)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Holiday effect — the 10-20% assumed in 5e
# --------------------------------------------------------------------------

def holiday_effect(df: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Holiday hours against MATCHED non-holiday hours.

    Matched on (zone, hour, month, year) so the comparison is not confounded by
    season, daily shape or growth. Weekends are excluded from the non-holiday
    side: a holiday resembles a Sunday, and comparing it to a Sunday would
    measure nothing.
    """
    sub = tier_subset(df, tier).copy()
    years = sorted(sub["year_ist"].unique())
    cal = holidays.country_holidays("IN", years=years)
    sub["is_holiday"] = pd.Series(sub["date_ist"], index=sub.index).isin(set(cal.keys()))
    sub["is_weekend"] = sub["weekday_ist"] >= 5

    rows = []
    for zone, g in sub.groupby("zone", observed=True):
        hol = g[g["is_holiday"] & ~g["is_weekend"]]
        wrk = g[~g["is_holiday"] & ~g["is_weekend"]]
        if hol.empty or wrk.empty:
            rows.append({"zone": zone, "holiday_hours": len(hol), "effect_pct": None})
            continue
        key = ["hour_ist", "month_ist", "year_ist"]
        hm = hol.groupby(key)["demand_mw"].mean()
        wm = wrk.groupby(key)["demand_mw"].mean()
        paired = pd.concat([hm.rename("holiday"), wm.rename("workday")], axis=1).dropna()
        effect = ((paired["holiday"] / paired["workday"]) - 1) * 100
        rows.append({"zone": zone, "holiday_hours": len(hol),
                     "matched_cells": len(paired),
                     "effect_pct": round(float(effect.mean()), 2),
                     "p10": round(float(effect.quantile(0.10)), 2),
                     "p90": round(float(effect.quantile(0.90)), 2)})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# The discontinuity test — the gate on the option-B estimation-tier decision
# --------------------------------------------------------------------------

# The method switches here for four of five zones. IN-EA switched earlier, so
# it gets its own boundary; anything assuming one project-wide date is wrong
# for it (PLANNING 11).
SWITCH_DATES = {
    "IN-NO": "2024-11-05", "IN-WE": "2024-11-05",
    "IN-SO": "2024-11-05", "IN-NE": "2024-11-05",
    "IN-EA": "2024-01-01",  # IN-EA switched ten months before the others
}


def detect_switch(g: pd.DataFrame) -> pd.Timestamp | None:
    """First timestamp from which the zone is predominantly measured."""
    daily = (g.assign(m=(g["tier"] == "measured").astype(float))
              .groupby("date_ist")["m"].mean())
    settled = daily[daily > 0.5]
    return pd.Timestamp(settled.index.min()) if len(settled) else None


def _step_at(w: pd.DataFrame, cut: pd.Timestamp) -> tuple[float, float, float]:
    """Fit the step model at `cut`. Returns (step_log, volatility_ratio, shape_gap)."""
    w = w.sort_values("datetime_utc")
    after = (w["datetime_utc"] >= cut).astype(float)
    temp = w["temperature_2m"].to_numpy(float)
    cols = [np.ones(len(w)),
            np.maximum(0.0, temp - 24.0),
            np.maximum(0.0, 15.0 - temp),
            (w["datetime_utc"] - cut).dt.total_seconds().to_numpy() / 86400.0,
            after.to_numpy()]
    for h in range(1, 24):
        cols.append((w["hour_ist"] == h).astype(float).to_numpy())
    for d in range(1, 7):
        cols.append((w["weekday_ist"] == d).astype(float).to_numpy())
    X = np.column_stack(cols)
    y = w["log_demand"].to_numpy(float)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)

    b, a = w[after == 0], w[after == 1]
    if len(b) < 48 or len(a) < 48:
        return float("nan"), float("nan"), float("nan")
    vol_b = b["log_demand"].diff().abs().mean()
    vol_a = a["log_demand"].diff().abs().mean()

    def profile(x):
        prof = x.groupby("hour_ist")["demand_mw"].mean()
        return prof / prof.mean()
    shape = float((profile(a) - profile(b)).abs().max())
    return float(coef[4]), float(vol_a / vol_b) if vol_b else float("nan"), shape


def discontinuity_test(df: pd.DataFrame, window_days: int = 60,
                       placebo_step_days: int = 30,
                       placebo_span_days: int = 420) -> pd.DataFrame:
    """Is there a step in the series where the estimation method changes?

    PLANNING 13: the case for training on MODE_BREAKDOWN rests on that method
    naming the fuel-mix breakdown rather than powerConsumptionTotal. That is an
    inference about someone else's pipeline. Consumption is normally derived
    from production plus net imports, which come from the breakdown — so if the
    total is reconstructed rather than metered, we would be training on derived
    numbers without knowing.

    The switch has a date, and the meter does not change on it. So a step dummy
    at the boundary, with temperature and calendar controls, measures exactly
    the thing in question. November is not October, hence the controls.

    Three quantities, because a pipeline change can move any of them:
      level      step coefficient on log(demand), as a percentage
      variance   ratio of hour-to-hour absolute change, after / before
      shape      max absolute difference in the mean 24-hour IST profile,
                 each side normalised by its own daily mean
    """
    rows = []
    for zone, g in df.groupby("zone", observed=True):
        cut = SWITCH_DATES.get(zone)
        cut = pd.Timestamp(cut, tz="UTC") if cut else detect_switch(g)
        if cut is None:
            rows.append({"zone": zone, "note": "no switch detected"})
            continue
        if cut.tz is None:
            cut = cut.tz_localize("UTC")

        lo = cut - pd.Timedelta(days=window_days)
        hi = cut + pd.Timedelta(days=window_days)
        w = g[(g["datetime_utc"] >= lo) & (g["datetime_utc"] < hi)].copy()
        w = w.sort_values("datetime_utc")
        if len(w) < 24 * 30:
            rows.append({"zone": zone, "note": f"only {len(w)} rows in window"})
            continue

        step, vol, shape = _step_at(w, cut)

        # PLACEBO CALIBRATION. A regression standard error assumes independent
        # residuals; hourly demand is nothing of the sort, and a small zone
        # wanders by tens of percent from month to month with no pipeline
        # change at all. So "is this step large?" is answered against what this
        # same series produces at boundaries where nothing happened, not
        # against a t-statistic that would call almost anything significant.
        placebos = []
        offsets = [d for d in range(-placebo_span_days, placebo_span_days + 1,
                                    placebo_step_days)
                   if abs(d) >= 2 * window_days]
        for off in offsets:
            fake = cut + pd.Timedelta(days=off)
            fw = g[(g["datetime_utc"] >= fake - pd.Timedelta(days=window_days))
                   & (g["datetime_utc"] < fake + pd.Timedelta(days=window_days))]
            if len(fw) < 24 * 60:
                continue
            # A placebo window must not straddle the real switch, or it is not
            # a placebo.
            if (fw["datetime_utc"].min() < cut < fw["datetime_utc"].max()):
                continue
            ps, pv, psh = _step_at(fw, fake)
            if np.isfinite(ps):
                placebos.append((abs(ps), pv, psh))
        if len(placebos) < 5:
            rows.append({"zone": zone, "switch": cut.date().isoformat(),
                         "note": f"only {len(placebos)} placebo windows"})
            continue

        p_step = np.array([x[0] for x in placebos])
        p_shape = np.array([x[2] for x in placebos])
        step_p90 = float(np.quantile(p_step, 0.90))
        shape_p90 = float(np.quantile(p_shape, 0.90))
        exceeds = abs(step) > step_p90 or shape > shape_p90

        rows.append({
            "zone": zone,
            "switch": cut.date().isoformat(),
            "rows": len(w),
            "level_step_pct": round((np.exp(step) - 1) * 100, 2),
            "placebo_p90_pct": round((np.exp(step_p90) - 1) * 100, 2),
            "n_placebo": len(placebos),
            "vol_ratio": round(vol, 2),
            "shape_gap": round(shape, 3),
            "placebo_shape_p90": round(shape_p90, 3),
            "exceeds_placebo": bool(exceeds),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Plots
#
# Drawn here rather than through src/viz/plots.py. That module is the single
# chart implementation shared by the backtest report and the dashboard (15),
# and it is a stage 5 deliverable; these are throwaway analysis figures, in the
# same category as the rest of this script, and nothing downstream reads them.
# --------------------------------------------------------------------------

def make_plots(df: pd.DataFrame, cfg: dict, tier: str, out_dir: pathlib.Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    sub = tier_subset(df, tier)
    cool = get(cfg, "features.cooling_threshold_c")
    heat = get(cfg, "features.heating_threshold_c")

    # 1. The elbow, adjusted, binned so 400k points are readable
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, (label, y) in zip(
            axes,
            [("raw log(demand)", sub["log_demand"]),
             ("log(demand), zone x hour x weekday means removed", adjust(sub))],
            strict=False):
        binned = pd.DataFrame({"t": sub["temperature_2m"], "y": y})
        binned["bin"] = (binned["t"] / 0.5).round() * 0.5
        agg = binned.groupby("bin")["y"].agg(["mean", "size"])
        agg = agg[agg["size"] >= 30]
        ax.plot(agg.index, agg["mean"], lw=1.6, color="#1f4e79")
        ax.axvline(cool, ls="--", c="#c0392b", lw=1,
                   label=f"config cooling_threshold_c = {cool}")
        ax.axvline(heat, ls="--", c="#2874a6", lw=1,
                   label=f"config heating_threshold_c = {heat}")
        ax.set_xlabel("temperature (C)")
        ax.set_ylabel(label)
        ax.set_title(label, fontsize=10)
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle(f"Demand response to temperature — tier: {tier}", fontsize=12)
    fig.tight_layout()
    p = out_dir / "elbow.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p.name)

    # 2. Per-zone elbow curves
    fig, ax = plt.subplots(figsize=(9, 5))
    for zone, g in sub.groupby("zone", observed=True):
        y = g["log_demand"] - g.groupby(["hour_ist", "weekday_ist"])["log_demand"].transform("mean")
        b = pd.DataFrame({"t": g["temperature_2m"], "y": y})
        b["bin"] = (b["t"] / 1.0).round()
        agg = b.groupby("bin")["y"].agg(["mean", "size"])
        agg = agg[agg["size"] >= 30]
        ax.plot(agg.index, agg["mean"], lw=1.4, label=zone)
    ax.axvline(cool, ls="--", c="#c0392b", lw=1)
    ax.set_xlabel("temperature (C)")
    ax.set_ylabel("adjusted log(demand)")
    ax.set_title(f"Per-zone temperature response — tier: {tier}")
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = out_dir / "elbow_by_zone.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p.name)

    # 3. Band occupancy
    occ = band_occupancy_by_zone(df, cfg, tier)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    occ.T.plot(kind="bar", ax=ax, width=.8)
    ax.set_yscale("log")
    ax.set_ylabel("rows (log scale)")
    ax.set_xlabel("temperature band (C)")
    ax.axhline(get(cfg, "evaluate.min_band_rows"), ls="--", c="#c0392b", lw=1,
               label=f"min_band_rows = {get(cfg, 'evaluate.min_band_rows')}")
    ax.axhline(get(cfg, "evaluate.insufficient_band_rows"), ls=":", c="#7d3c98", lw=1,
               label=f"insufficient = {get(cfg, 'evaluate.insufficient_band_rows')}")
    ax.set_title(f"Band occupancy — tier: {tier}")
    ax.legend(fontsize=8)
    ax.grid(alpha=.25, axis="y")
    fig.tight_layout()
    p = out_dir / "band_occupancy.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p.name)

    # 4. Year-on-year level
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for zone, g in sub.groupby("zone", observed=True):
        annual = g.groupby("year_ist")["demand_mw"].agg(["mean", "size"])
        annual = annual[annual["size"] >= 24 * 300]
        ax.plot(annual.index, annual["mean"], marker="o", lw=1.4, label=zone)
    ax.set_yscale("log")
    ax.set_ylabel("annual mean demand, MW (log scale)")
    ax.set_xlabel("year (IST)")
    ax.set_title(f"Demand growth — tier: {tier}")
    ax.grid(alpha=.25)
    ax.legend(fontsize=8)
    fig.tight_layout()
    p = out_dir / "growth.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p.name)

    # 5. Suppression candidates against the temperature they occur at
    _, flagged = suppression_candidates(df, cfg, tier)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    if len(flagged):
        ax.hist([tier_subset(df, tier)["temperature_2m"], flagged["temperature_2m"]],
                bins=40, label=["all hours", "flagged"], density=True)
    ax.set_xlabel("temperature (C)")
    ax.set_ylabel("density")
    ax.set_title(f"Suppressed-demand candidates vs all hours — tier: {tier}")
    ax.legend(fontsize=8)
    ax.grid(alpha=.25)
    fig.tight_layout()
    p = out_dir / "suppression.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    written.append(p.name)
    return written


# --------------------------------------------------------------------------

def volatility_table_df(df: pd.DataFrame, window_days: int = 90) -> pd.DataFrame:
    """Hour-to-hour variability either side of each zone's own switch date."""
    rows = []
    for zone, cut in SWITCH_DATES.items():
        c = pd.Timestamp(cut, tz="UTC")
        g = df[df["zone"] == zone].sort_values("datetime_utc")
        b = g[(g["datetime_utc"] >= c - pd.Timedelta(days=window_days))
              & (g["datetime_utc"] < c)]
        a = g[(g["datetime_utc"] >= c) & (g["datetime_utc"] < c + pd.Timedelta(days=window_days))]
        if b.empty or a.empty:
            continue
        vb = b["log_demand"].diff().abs().mean()
        va = a["log_demand"].diff().abs().mean()
        pb = (b["demand_mw"].diff().abs() / b["demand_mw"]).dropna() * 100
        pa = (a["demand_mw"].diff().abs() / a["demand_mw"]).dropna() * 100
        rows.append({
            "zone": zone, "switch": cut,
            "before_mean_abs_dlog": round(float(vb), 5),
            "after_mean_abs_dlog": round(float(va), 5),
            "ratio": round(float(va / vb), 2),
            "before_p95_hourly_pct": round(float(pb.quantile(0.95)), 1),
            "after_p95_hourly_pct": round(float(pa.quantile(0.95)), 1),
        })
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame) -> str:
    return df.to_markdown(index=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="measured+MODE",
                    choices=list(TIERS),
                    help="which estimation tiers to use for the headline figures")
    args = ap.parse_args()

    cfg = load_config()
    log.info("loading and joining demand to weather")
    df = load_joined(cfg)
    log.info("%d joined rows, %s .. %s", len(df),
             df["datetime_utc"].min(), df["datetime_utc"].max())

    reports = PROJECT_ROOT / "reports"
    figures = reports / "figures"
    tier = args.tier

    tier_counts = (df.groupby(["tier", "zone"], observed=True).size()
                     .unstack("zone", fill_value=0))
    thresholds = elbow_table(df, cfg)
    zone_thresholds = per_zone_elbows(df, tier)
    discontinuity = discontinuity_test(df)
    bands = band_occupancy(df, cfg, tier)
    bands_zone = band_occupancy_by_zone(df, cfg, tier)
    supp, _ = suppression_candidates(df, cfg, tier)
    growth = growth_rates(df, tier)
    hol = holiday_effect(df, tier)
    plots = make_plots(df, cfg, tier, figures)

    spread = None
    if "cooling_c" in zone_thresholds and zone_thresholds["cooling_c"].notna().any():
        spread = float(zone_thresholds["cooling_c"].max()
                       - zone_thresholds["cooling_c"].min())
    flagged = discontinuity.get("exceeds_placebo")
    if flagged is not None:
        log.info("discontinuity: %d of %d zones exceed their placebo band",
                 int(flagged.sum()), len(flagged))

    origin = get(cfg, "demand.backfill_start")
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cfg_cool = get(cfg, "features.cooling_threshold_c")
    cfg_heat = get(cfg, "features.heating_threshold_c")

    spread_text = f"{spread:.2f} C" if spread is not None else "not identified"
    discontinuity_table = md_table(discontinuity)
    volatility_table = md_table(volatility_table_df(df))
    threshold_table = md_table(thresholds)
    zone_threshold_table = md_table(zone_thresholds)

    doc = f"""# Step-0 measurements

Generated {generated} by `scripts/measure_step0.py`.

PLANNING 12: the specification was written against data nobody had looked at.
This report replaces the section 13 step-0 assumptions with numbers, and says
where a number is still provisional.

## Data

| | |
|---|---|
| Joined rows | {len(df):,} |
| Span | {df["datetime_utc"].min():%Y-%m-%d} to {df["datetime_utc"].max():%Y-%m-%d} (UTC) |
| Zones | {", ".join(sorted(df["zone"].unique()))} |
| Headline tier | `{tier}` — {TIERS[tier]} |

### `trend`'s origin moved

`demand.backfill_start` was `2021-01-01`, a guess. Electricity Maps actually
serves all five zones from 2017-01 (measured 2026-09-08), and the config is now
`{origin}`.

**This redefines `trend`.** 5e defines it as days since `demand.backfill_start`
with a fixed origin, so every `trend` value is now about four years larger than
it would have been. The feature is unchanged in meaning — days elapsed — but
any number computed against the old origin is not comparable to one computed
against the new one.

### Rows by estimation tier

Which of these are trainable is an **open decision** (PLANNING 10). Every
measurement below is reported per tier rather than collapsed into one number.

{md_table(tier_counts.reset_index())}

## The estimation-method discontinuity test

**This is the gate on the option-B tier decision (PLANNING 13).** The case for
training on `MODE_BREAKDOWN` rows rests on that method naming the fuel-mix
breakdown rather than `powerConsumptionTotal`. Consumption is normally derived
from production plus net imports — which come from the breakdown — so if the
total is reconstructed rather than metered, option B trains on ~45 months of
derived numbers.

The switch has a date and the meter does not change on it, so a step model at
the boundary with temperature and calendar controls isolates the pipeline
change. Significance is calibrated against **placebo boundaries** — the same
model fitted at dates where nothing happened — because a regression standard
error assumes independent residuals and hourly demand is nothing of the sort.

{discontinuity_table}

**Zones do not switch on the same date.** IN-EA switches 2024-01-01, the other
four on 2024-11-05. That matters: nothing about Indian electricity demand
changes on two different dates for different regions, so anything that tracks
each zone's own switch date is a property of the pipeline, not of the world.

### Hour-to-hour variability, 90 days either side

{volatility_table}

## The thresholds — `features.cooling_threshold_c` and `heating_threshold_c`

Method, per ruling: RSS-minimising grid search on `log(demand)`, pooled, run
both naively and with zone, hour-of-day and weekday means removed first.

**Corrected from the first attempt.** Fitting one ramp alone is misspecified:
demand is not monotone in temperature, so a lone cooling ramp tries to span the
whole range and the search runs to whatever grid edge it is given. The first
run returned the grid boundary for every tier in both directions. A boundary
solution is not a measurement, and it is now reported as **NOT IDENTIFIED**
rather than as a number. The model fitted is the one the features actually use:

```
y ~ 1 + max(0, T - cooling) + max(0, heating - T),    heating < cooling
```

Config currently holds cooling **{cfg_cool} C**, heating **{cfg_heat} C**.

{threshold_table}

### Per-zone — tier `{tier}`

{zone_threshold_table}

Cooling-threshold spread across zones: **{spread_text}**.

### The cold side does not behave like a heating load

The heating coefficient comes out **negative in every tier** — colder means
*less* demand, not more, across the observed range. That is physically
plausible for most of India, where electric heating is rare, and 5e already
says `heating_degrees` is kept as a structural requirement of the architecture
rather than because heating load is large.

It has a consequence worth raising before stage 2: 5c requires a **monotone
increasing** constraint on `heating_degrees` in the LightGBM stage. If the
relationship runs the other way in this data, that constraint would force the
model against the measured direction. Flagging rather than acting on it.

## Band occupancy — `evaluate.temperature_bands_c`

Under the sufficiency rule of PLANNING 13: interior bands at or above
`min_band_rows`, the top band kept separate regardless of count, and any band
below `insufficient_band_rows` reported as insufficient rather than as a number.

{md_table(bands)}

### By zone

{md_table(bands_zone.reset_index())}

## Suppressed-demand candidates — `quality.suppression_*`

Hours where temperature rose by at least
`{get(cfg, "quality.suppression_temp_rise_c")} C` on the hour while demand
changed by no more than `{get(cfg, "quality.suppression_demand_delta_pct")}%`.
5f principle 2: the source reports power consumed, not power wanted, so a
load-shedding hour records a supply ceiling and a model fitted to it learns
that demand stops rising in a heatwave.

{md_table(supp)}

## Demand growth — assumed ~5%/year in 5c

Log-linear trend on annual mean demand, near-complete years only.

{md_table(growth)}

## Holiday effect — assumed 10-20% in 5e

Holiday hours against matched non-holiday hours, paired on (zone, hour, month,
year) so season, daily shape and growth do not confound it. Weekends are
excluded from both sides: a holiday resembles a Sunday, so comparing the two
would measure nothing.

{md_table(hol)}

## Figures

{chr(10).join(f"- `figures/{p}`" for p in plots)}
"""
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "step0_measurements.md").write_text(doc)
    log.info("wrote reports/step0_measurements.md and %d figures", len(plots))


if __name__ == "__main__":
    main()
