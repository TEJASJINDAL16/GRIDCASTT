"""Replay threshold/debounce candidates and measure alarm episodes and delay."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.config import PROJECT_ROOT, load_config, update_values
from src.monitor.drift import daily_metrics
from src.monitor.registry import compare, derive_tolerances
from src.records import pins, write_json


def firings(metrics, thresholds, debounce, *, watch=False):
    events = []
    for zone, part in metrics.groupby("zone", observed=True):
        part = part.sort_values("date").set_index("date")
        part = part.reindex(pd.date_range(part.index.min(), part.index.max(), freq="D"))
        bounds = thresholds[str(zone)]
        error = (part.error > bounds["error"]).astype(int)
        if watch:
            events.append(error.astype(bool).rename(str(zone)))
            continue
        bias = (part.bias.abs() > bounds["bias"]).astype(int)
        rolling = error.rolling(debounce, min_periods=debounce).sum().eq(debounce) | bias.rolling(
            debounce, min_periods=debounce
        ).sum().eq(debounce)
        broken = (part.daily_error > bounds["daily_error"]) & (str(zone) != "pooled")
        structural = broken & (broken.astype(int).rolling(7, min_periods=1).sum() >= 3)
        events.append((rolling | structural).rename(str(zone)))
    return pd.concat(events, axis=1).fillna(False).any(axis=1)


def episode_starts(series, cooldown):
    active, next_allowed, starts = False, series.index.min(), []
    for date, firing in series.items():
        if not firing:
            active = False
        elif not active and date >= next_allowed:
            starts.append(date)
            active = True
            next_allowed = date + pd.Timedelta(days=cooldown)
    return pd.DatetimeIndex(starts, tz=series.index.tz)


def episodes(series, cooldown):
    return len(episode_starts(series, cooldown))


def detection_delay(signal, start, cooldown):
    starts = episode_starts(signal, cooldown)
    after = starts[starts >= start.normalize()]
    return int((after[0] - start.normalize()).days) if len(after) else None


def refreshed_watch_metrics(rows, cfg):
    # Every fold is a new fitted model. A champion-only window cannot borrow
    # predictions from the preceding fold to fill its first seven days.
    parts = [
        daily_metrics(part, cfg, window=cfg["drift"]["post_promotion_watch_days"])
        for _, part in rows.groupby("fold")
    ]
    return pd.concat(parts, ignore_index=True)


def combined_attempt_starts(primary, watch, cooldown):
    """Count watch escalations inside cooldown without counting overlaps twice."""
    signals = pd.concat([primary.rename("primary"), watch.rename("watch")], axis=1).fillna(False)
    active, watch_active, until, starts = False, False, signals.index.min(), []
    for date, row in signals.iterrows():
        active = active and bool(row.primary)
        watch_active = watch_active and bool(row.watch)
        new_watch = bool(row.watch) and not watch_active
        if (new_watch or (row.primary and not active)) and (date >= until or new_watch):
            starts.append(date)
            active, watch_active = bool(row.primary), bool(row.watch)
            until = date + pd.Timedelta(days=cooldown)
    return pd.DatetimeIndex(starts, tz=signals.index.tz)


def main():
    root, cfg = PROJECT_ROOT, load_config()
    out = root / "reports/calibration"
    out.mkdir(parents=True, exist_ok=True)
    scale_low, scale_high = cfg["runtime"]["threshold_scale_bounds"]
    source = root / "data/interim/model_predictions.parquet"
    all_rows = pd.read_parquet(source)
    rows = all_rows.loc[all_rows.model == "hybrid"].copy()
    metrics = daily_metrics(rows, cfg)
    complete = metrics.dropna(subset=["error", "bias"])
    if complete.empty:
        raise ValueError("no complete monitoring windows for calibration")
    maxima = complete.groupby("zone", observed=True)[["error", "bias", "daily_error"]].agg(
        lambda x: x.abs().max()
    )
    start = rows.datetime_utc.min() + (rows.datetime_utc.max() - rows.datetime_utc.min()) / 2
    injected = {}
    for shift in cfg["drift"]["injected_drift_pct"]:
        changed = rows.copy()
        changed.loc[changed.datetime_utc >= start, "prediction_mw"] *= 1 + shift / 100
        injected[shift] = daily_metrics(changed, cfg)
    span = (metrics.date.max() - metrics.date.min()).days + 1
    records = []
    for scale in np.linspace(scale_low, scale_high, cfg["runtime"]["threshold_steps"]):
        thresholds = (maxima * scale).to_dict("index")
        for debounce in cfg["runtime"]["debounce_candidates"]:
            signal = firings(metrics, thresholds, debounce)
            count = episodes(signal, cfg["drift"]["cooldown_after_rejection_days"])
            record = {
                "scale": float(scale),
                "debounce": debounce,
                "episodes": count,
                "episodes_per_year": count * 365.25 / span,
            }
            for shift, frame in injected.items():
                hit = firings(frame, thresholds, debounce)
                record[f"delay_{shift}_days"] = detection_delay(
                    hit, start, cfg["drift"]["cooldown_after_rejection_days"]
                )
            records.append(record)
    table = pd.DataFrame(records)
    feasible = table.loc[
        table.episodes_per_year <= cfg["drift"]["false_alarm_budget_per_year"]
    ].copy()
    if feasible.empty:
        raise ValueError("no threshold combination meets the alarm budget; widen the sweep")
    delays = [c for c in table if c.startswith("delay_")]
    feasible["mean_delay"] = feasible[delays].fillna(span).mean(axis=1)
    best = feasible.sort_values(
        ["mean_delay", delays[0], "scale", "debounce"], na_position="last"
    ).iloc[0]
    bounds = (maxima * best.scale).to_dict("index")
    thresholds = {}
    for metric, column in [
        ("rolling_error", "error"),
        ("signed_bias", "bias"),
        ("structural_break", "daily_error"),
    ]:
        thresholds[metric] = {
            "pooled": bounds.get("pooled", {}).get(column),
            "per_zone": {z: b[column] for z, b in bounds.items() if z != "pooled"},
        }
    watch = refreshed_watch_metrics(rows, cfg)
    # Same episode-budget sweep for the separate seven-day watch.
    watch_max = watch.groupby("zone", observed=True)[["error", "bias", "daily_error"]].agg(
        lambda x: x.abs().max()
    )
    watch_records = []
    selected_signal = firings(metrics, bounds, int(best.debounce))
    injected_watch = {}
    for shift in cfg["drift"]["injected_drift_pct"]:
        changed = rows.copy()
        changed.loc[changed.datetime_utc >= start, "prediction_mw"] *= 1 + shift / 100
        injected_watch[shift] = refreshed_watch_metrics(changed, cfg)
    for scale in np.linspace(scale_low, scale_high, cfg["runtime"]["threshold_steps"]):
        watch_bounds = (watch_max * scale).to_dict("index")
        signal = firings(watch, watch_bounds, 1, watch=True)
        rate = episodes(signal, cfg["drift"]["cooldown_after_rejection_days"]) * 365.25 / span
        combined_rate = (
            len(
                combined_attempt_starts(
                    selected_signal, signal, cfg["drift"]["cooldown_after_rejection_days"]
                )
            )
            * 365.25
            / span
        )
        record = {
            "scale": float(scale),
            "episodes_per_year": rate,
            "combined_episodes_per_year": combined_rate,
        }
        for shift, frame in injected_watch.items():
            hit = firings(frame, watch_bounds, 1, watch=True)
            record[f"delay_{shift}_days"] = detection_delay(
                hit, start, cfg["drift"]["cooldown_after_rejection_days"]
            )
        watch_records.append(record)
    watch_table = pd.DataFrame(watch_records)
    watch_feasible = watch_table.loc[
        (watch_table.episodes_per_year <= cfg["drift"]["false_alarm_budget_per_year"])
        & (watch_table.combined_episodes_per_year <= cfg["drift"]["false_alarm_budget_per_year"])
    ].copy()
    watch_feasible["mean_delay"] = watch_feasible[delays].fillna(span).mean(axis=1)
    watch_scale = (
        watch_feasible.sort_values(["mean_delay", delays[0], "scale"], na_position="last")
        .iloc[0]
        .scale
    )
    if any(
        np.isclose(value, bound)
        for value in [best.scale, watch_scale]
        for bound in [scale_low, scale_high]
    ):
        table.to_csv(out / "sweep.csv", index=False)
        watch_table.to_csv(out / "watch_sweep.csv", index=False)
        write_json(
            out / "not_identified.json",
            {
                "status": "NOT IDENTIFIED",
                "scale": float(best.scale),
                "watch_scale": float(watch_scale),
            },
        )
        update_values({"drift.thresholds_derived": False})
        raise ValueError(
            "threshold selection reached a sweep boundary; widen threshold_scale_bounds"
        )
    tolerance = derive_tolerances(rows, cfg)
    metadata = pins(root, cfg, source)
    updates = {
        "drift.thresholds": thresholds,
        "drift.debounce_days": int(best.debounce),
        "drift.watch_threshold": (watch_max.error * watch_scale).to_dict(),
        "drift.thresholds_derived": True,
        "drift.thresholds_backtest_sha": metadata["git_sha"],
        **{f"evaluate.veto_tolerance.{k}": v for k, v in tolerance.items()},
    }
    update_values(updates)
    cfg = load_config()
    table.to_csv(out / "sweep.csv", index=False)
    pd.DataFrame(watch_records).to_csv(out / "watch_sweep.csv", index=False)
    decision = compare(all_rows, cfg)
    write_json(out / "selection.json", decision)
    write_json(
        out / "result.json",
        {
            "pins": metadata,
            "selected": {k: None if pd.isna(v) else v for k, v in best.items()},
            "thresholds": thresholds,
            "tolerances": tolerance,
            "calibration_rows": len(rows),
            "complete_daily_windows_by_zone": complete.groupby("zone", observed=True)
            .size()
            .to_dict(),
            "complete_watch_windows_by_zone": watch.dropna(subset=["error"])
            .groupby("zone", observed=True)
            .size()
            .to_dict(),
            "replay_span_days": span,
            "watch_selected_scale": float(watch_scale),
            "settlement_frontier_replay": False,
            "provisionally_optimistic": True,
        },
    )
    (root / "reports/threshold_derivation.md").write_text(
        "# Threshold Replay\n\nFully settled, refreshed-fold replay. Thresholds are provisionally optimistic: "
        "historical first-settlement coverage is insufficient. Delay figures omit settlement lag.\n\n"
        + f"Measured target rows: {len(rows):,}. Replay span: {span} days. Complete daily windows (overlapping, not independent): "
        + str(complete.groupby("zone", observed=True).size().to_dict())
        + ".\n\n"
        + best.to_frame("selected").to_markdown()
        + "\n\nAll candidates: calibration/sweep.csv. "
        "Seven-day watch candidates: calibration/watch_sweep.csv. Veto tolerances use one sample standard "
        "deviation across folds; a missing top-band tolerance prevents promotion.\n\n"
        + f"Model passes selection gate: {decision['promote']}. Reasons: {decision['reasons']}.\n",
        encoding="utf-8",
    )
    print(decision)


if __name__ == "__main__":
    main()
