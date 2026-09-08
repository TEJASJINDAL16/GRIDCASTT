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


def find_breakpoint(temp: pd.Series, y: pd.Series, grid: np.ndarray,
                    cold: bool = False) -> tuple[float, float]:
    """Grid-search the breakpoint that minimises residual sum of squares."""
    t, v = temp.to_numpy(float), y.to_numpy(float)
    fn = _two_segment_rss_cold if cold else _two_segment_rss
    rss = np.array([fn(t, v, b) for b in grid])
    best = int(np.argmin(rss))
    return float(grid[best]), float(rss[best])


def adjust(df: pd.DataFrame) -> pd.Series:
    """log(demand) with zone, hour-of-day and weekday means removed.

    Zone as well as hour and weekday: pooling five zones whose levels differ by
    an order of magnitude, a fit with one intercept is dominated by between-zone
    level rather than by the temperature response. Log makes the SLOPE
    comparable across zones (5c); it does not make the LEVELS equal.
    """
    return df["log_demand"] - df.groupby(
        ["zone", "hour_ist", "weekday_ist"])["log_demand"].transform("mean")


def elbow_table(df: pd.DataFrame, cfg: dict, cold: bool = False) -> pd.DataFrame:
    lo, hi = (5.0, 25.0) if cold else (18.0, 34.0)
    grid = np.arange(lo, hi + 0.01, 0.25)
    rows = []
    for tier in TIERS:
        sub = tier_subset(df, tier)
        if len(sub) < 1000:
            rows.append({"tier": tier, "rows": len(sub), "naive_c": None,
                         "adjusted_c": None, "note": "too few rows"})
            continue
        naive, _ = find_breakpoint(sub["temperature_2m"], sub["log_demand"], grid, cold)
        adj, _ = find_breakpoint(sub["temperature_2m"], adjust(sub), grid, cold)
        rows.append({"tier": tier, "rows": len(sub), "naive_c": naive,
                     "adjusted_c": adj, "note": ""})
    return pd.DataFrame(rows)


def per_zone_elbows(df: pd.DataFrame, tier: str, cold: bool = False) -> pd.DataFrame:
    lo, hi = (5.0, 25.0) if cold else (18.0, 34.0)
    grid = np.arange(lo, hi + 0.01, 0.25)
    sub = tier_subset(df, tier)
    rows = []
    for zone, g in sub.groupby("zone"):
        if len(g) < 1000:
            rows.append({"zone": zone, "rows": len(g), "elbow_c": None})
            continue
        y = g["log_demand"] - g.groupby(["hour_ist", "weekday_ist"])["log_demand"].transform("mean")
        bp, _ = find_breakpoint(g["temperature_2m"], y, grid, cold)
        rows.append({"zone": zone, "rows": len(g), "elbow_c": bp})
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
    cool = elbow_table(df, cfg, cold=False)
    heat = elbow_table(df, cfg, cold=True)
    zone_cool = per_zone_elbows(df, tier, cold=False)
    zone_heat = per_zone_elbows(df, tier, cold=True)
    bands = band_occupancy(df, cfg, tier)
    bands_zone = band_occupancy_by_zone(df, cfg, tier)
    supp, _ = suppression_candidates(df, cfg, tier)
    growth = growth_rates(df, tier)
    hol = holiday_effect(df, tier)
    plots = make_plots(df, cfg, tier, figures)

    spread = None
    if zone_cool["elbow_c"].notna().any():
        spread = float(zone_cool["elbow_c"].max() - zone_cool["elbow_c"].min())

    origin = get(cfg, "demand.backfill_start")
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    cfg_cool = get(cfg, "features.cooling_threshold_c")
    cfg_heat = get(cfg, "features.heating_threshold_c")

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

## The elbow — `features.cooling_threshold_c`

Method, fixed by ruling: two-segment fit on `log(demand)`, breakpoint by
RSS-minimising grid search at 0.25 C resolution, pooled across zones. Run both
ways — naively, and with zone, hour-of-day and weekday means removed first.

A raw scatter conflates the temperature response with the daily cycle: demand
is high at 20:00 and low at 04:00 for reasons unrelated to temperature, and
temperature is itself correlated with hour. The naive number is reported so the
size of that artefact is visible, not because it is the answer.

Config currently holds **{cfg_cool} C**.

{md_table(cool)}

### Per-zone elbows — tier `{tier}`

{md_table(zone_cool)}

Spread across zones: **{f"{spread:.2f} C" if spread is not None else "not computed"}**.
Pooled scalar is confirmed for phase 1 and the config schema does not change;
a spread beyond about 2 C is phase 2 evidence for a per-zone map, not a phase 1
change.

## The cold-side inflection — `features.heating_threshold_c`

Same method, mirrored: `max(0, breakpoint - T)`. Config holds **{cfg_heat} C**.

{md_table(heat)}

### Per-zone, tier `{tier}`

{md_table(zone_heat)}

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
