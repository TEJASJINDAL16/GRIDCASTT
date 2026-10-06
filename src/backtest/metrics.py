"""Measured-target metrics with same-row seasonal denominators (5g)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import get


def _ratio(numerator: float, denominator: float) -> float | None:
    return float(numerator / denominator) if denominator > 0 else None


def with_error_context(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Compute peak/ramp membership before stratifying by the current hour.

    A ramp at 18:30 needs the preceding 17:30 even when the reporting segment
    is just hour 18. An actual daily peak likewise must not move when filtered.
    """
    ordered = frame.sort_values(["fold", "zone", "datetime_utc"]).copy()
    daily_keys = ["fold", "zone", "date_ist"]
    if "model" in ordered:
        daily_keys.append("model")
    groups = ordered.groupby(daily_keys, observed=True)
    complete = groups.datetime_utc.transform("nunique").eq(24) & groups.datetime_utc.transform("size").eq(24)
    ordered["is_actual_peak"] = False
    complete_rows = ordered.loc[complete]
    if len(complete_rows):
        peak_indices = complete_rows.groupby(daily_keys, observed=True).demand_mw.idxmax()
        ordered.loc[peak_indices, "is_actual_peak"] = True
    contiguous = groups.datetime_utc.diff().eq(pd.Timedelta(hours=1))
    ramp_rows = contiguous & ordered.hour_of_day.isin(get(cfg, "evaluate.ramp_window_hours_ist"))
    actual_delta = groups.demand_mw.diff()
    ordered["ramp_error_mw"] = (actual_delta - groups.prediction_mw.diff()).abs().where(ramp_rows)
    ordered["baseline_ramp_error_mw"] = (actual_delta - groups.baseline_mw.diff()).abs().where(ramp_rows)
    return ordered.reindex(frame.index)


def score(frame: pd.DataFrame, cfg: dict) -> dict:
    """No implicit row dropping: callers must supply the measured common cohort."""
    n = len(frame)
    result = {"n_rows": n}
    names = ["mape_pct", "mae_mw", "rmse_mw", "mase", "rmsse", "signed_bias_pct",
             "shortfall_freq_pct", "p95_abs_pct", "rmse_mae_ratio", "baseline_mape_pct",
             "peak_mae_mw", "peak_mape_pct", "baseline_peak_mae_mw",
             "ramp_mae_mw", "baseline_ramp_mae_mw", "ramp_mase"]
    if not n:
        return result | dict.fromkeys(names) | {"n_peak_days": 0, "n_ramps": 0}
    if "is_estimated" in frame and frame.is_estimated.fillna(True).any():
        raise ValueError("cannot score estimated or unknown targets (INV-4)")
    y, p, b = (frame[c].to_numpy(dtype=float) for c in
               ["demand_mw", "prediction_mw", "baseline_mw"])
    if not np.isfinite(np.column_stack([y, p, b])).all() or (y <= 0).any():
        raise ValueError("metrics require finite values and positive actual demand")
    error, baseline_error = p - y, b - y
    absolute = np.abs(error)
    percent = error / y * 100
    mae = float(absolute.mean())
    rmse = float(np.sqrt(np.mean(error ** 2)))
    squared_ratio = _ratio(np.sum(error ** 2), np.sum(baseline_error ** 2))
    result |= {
        "mape_pct": float(np.abs(percent).mean()), "mae_mw": mae, "rmse_mw": rmse,
        "mase": _ratio(absolute.sum(), np.abs(baseline_error).sum()),
        "rmsse": float(np.sqrt(squared_ratio)) if squared_ratio is not None else None,
        "signed_bias_pct": float(percent.mean()),
        "shortfall_freq_pct": float((percent < -get(cfg, "evaluate.shortfall_threshold_pct")).mean() * 100),
        "p95_abs_pct": float(np.percentile(np.abs(percent), get(cfg, "evaluate.tail_percentile"))),
        "rmse_mae_ratio": _ratio(rmse, mae),
        "baseline_mape_pct": float((np.abs(baseline_error) / y * 100).mean()),
    }
    daily_keys = ["fold", "zone", "date_ist"]
    if not set(daily_keys + ["datetime_utc", "hour_of_day"]) <= set(frame.columns):
        return result | dict.fromkeys(names[10:]) | {"n_peak_days": 0, "n_ramps": 0}
    context = frame if "is_actual_peak" in frame else with_error_context(frame, cfg)
    peaks = context.loc[context.is_actual_peak]
    if len(peaks):
        peak_error = (peaks.prediction_mw - peaks.demand_mw).abs()
        result |= {"n_peak_days": len(peaks), "peak_mae_mw": float(peak_error.mean()),
                   "peak_mape_pct": float((peak_error / peaks.demand_mw * 100).mean()),
                   "baseline_peak_mae_mw": float((peaks.baseline_mw - peaks.demand_mw).abs().mean())}
    else:
        result |= {"n_peak_days": 0, "peak_mae_mw": None, "peak_mape_pct": None,
                   "baseline_peak_mae_mw": None}
    ramps = context.ramp_error_mw.dropna()
    baseline_ramps = context.baseline_ramp_error_mw.dropna()
    result |= {"n_ramps": len(ramps), "ramp_mae_mw": float(ramps.mean()) if len(ramps) else None,
               "baseline_ramp_mae_mw": float(baseline_ramps.mean()) if len(ramps) else None,
               "ramp_mase": _ratio(ramps.sum(), baseline_ramps.sum())}
    return result


def temperature_bands(temperature: pd.Series, cfg: dict) -> tuple[pd.Series, list[str]]:
    """Merge sparse interior bands; keep the top band even when it is empty."""
    boundaries = [-np.inf, *get(cfg, "evaluate.temperature_bands_c"), np.inf]
    codes = pd.cut(temperature, boundaries, right=False, labels=False)
    counts = codes.value_counts().to_dict()
    blocks = [[i] for i in range(len(boundaries) - 1)]
    top = blocks.pop()
    minimum = get(cfg, "evaluate.min_band_rows")
    i = 0
    while len(blocks) > 1 and i < len(blocks):
        count = sum(counts.get(j, 0) for j in blocks[i])
        if count >= minimum:
            i += 1
        elif i < len(blocks) - 1:
            blocks[i:i + 2] = [blocks[i] + blocks[i + 1]]
        else:
            blocks[i - 1:i + 1] = [blocks[i - 1] + blocks[i]]
            i -= 1
    blocks.append(top)
    labels, mapping = [], {}
    for block in blocks:
        low, high = boundaries[min(block)], boundaries[max(block) + 1]
        label = (f"< {high:g} C" if np.isneginf(low) else
                 f">= {low:g} C" if np.isposinf(high) else f"{low:g} to < {high:g} C")
        labels.append(label)
        mapping.update(dict.fromkeys(block, label))
    return codes.map(mapping), labels


def stratified_scores(predictions: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """All reporting dimensions, including absent zone/temperature cells."""
    predictions = with_error_context(predictions, cfg)
    cohort = predictions.loc[predictions.model == "seasonal_naive"]
    _, labels = temperature_bands(cohort.observed_temperature, cfg)
    band_map, _ = temperature_bands(cohort.observed_temperature, cfg)
    row_bands = pd.Series(band_map.to_numpy(), index=cohort.row_id)
    frame = predictions.copy()
    frame["temperature_band"] = frame.row_id.map(row_bands)
    records = []
    for dimension in ["temperature_band", "hour_of_day", "zone", "day_type", "lead_time_hours"]:
        categories = (labels if dimension == "temperature_band" else
                      get(cfg, "demand.all_zones") if dimension == "zone" else
                      sorted(frame[dimension].unique()))
        for category in categories:
            for model in frame.model.unique():
                rows = frame.loc[(frame[dimension] == category) & (frame.model == model)]
                stats = score(rows, cfg)
                records.append({"dimension": dimension, "segment": str(category), "model": model,
                                "status": "absent" if not len(rows) else
                                "insufficient rows to judge" if dimension == "temperature_band"
                                and len(rows) < get(cfg, "evaluate.insufficient_band_rows") else "reportable",
                                **stats})
    for zone in get(cfg, "demand.all_zones"):
        for band in labels:
            for model in frame.model.unique():
                rows = frame.loc[(frame.zone == zone) & (frame.temperature_band == band)
                                 & (frame.model == model)]
                records.append({"dimension": "zone_temperature_band", "segment": f"{zone}: {band}",
                                "model": model, "status": "absent" if not len(rows) else
                                "insufficient rows to judge" if len(rows) < get(cfg, "evaluate.insufficient_band_rows")
                                else "reportable", **score(rows, cfg)})
    # A fixed 30-day trailing backtest view, sampled at each fold's last day.
    for end in sorted(frame.date_ist.unique()):
        if end != pd.Timestamp(end).date().replace(day=pd.Timestamp(end).days_in_month):
            continue
        start = end - pd.Timedelta(days=get(cfg, "drift.rolling_window_days") - 1)
        for model in frame.model.unique():
            rows = frame.loc[(frame.model == model) & (frame.date_ist >= start) & (frame.date_ist <= end)]
            records.append({"dimension": "time_rolling", "segment": str(end), "model": model,
                            "status": "reportable", **score(rows, cfg)})
    return pd.DataFrame(records)
