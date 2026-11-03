"""Settled-hour monitoring, fixed thresholds, watches and cooldowns."""

import numpy as np
import pandas as pd


def clean_scores(frame):
    if frame.empty:
        return frame.copy()
    mask = (
        frame["flags"].map(
            lambda values: not any(str(v).startswith("stale_weather_") for v in values)
        )
        if "flags" in frame
        else pd.Series(True, index=frame.index)
    )
    return frame.loc[mask & ~frame.is_estimated.fillna(True) & (frame.demand_mw > 0)].copy()


def daily_metrics(frame, cfg, window=None):
    frame = clean_scores(frame)
    if frame.empty:
        return pd.DataFrame()
    window = window or cfg["drift"]["rolling_window_days"]
    frame["date"] = frame.datetime_utc.dt.tz_convert(cfg["project"]["timezone"]).dt.normalize()
    frame["bias"] = (frame.prediction_mw - frame.demand_mw) / frame.demand_mw * 100
    frame["error"] = frame.bias.abs()
    frame["baseline_error"] = ((frame.baseline_mw - frame.demand_mw) / frame.demand_mw * 100).abs()
    frame["baseline_bias"] = (frame.baseline_mw - frame.demand_mw) / frame.demand_mw * 100
    output = []
    for zone, part in frame.groupby("zone", observed=True):
        columns = ["error", "bias", "baseline_error", "baseline_bias"]
        hourly = part.set_index("datetime_utc").sort_index()[columns]
        if hourly.index.has_duplicates:
            raise ValueError("monitoring requires one frozen score per zone/hour")
        hourly = hourly.reindex(pd.date_range(hourly.index.min(), hourly.index.max(), freq="h"))
        daily_error = hourly.error.rolling(24, min_periods=24).mean()
        rolled = hourly.rolling(window * 24, min_periods=window * 24).mean()
        rolled["daily_error"] = daily_error
        rolled["n"] = hourly.error.rolling(window * 24, min_periods=1).count()
        rolled["date"] = rolled.index.tz_convert(cfg["project"]["timezone"]).normalize()
        # Keep the final hourly window even at a partial settlement day; a
        # missing interior hour still invalidates the full rolling window.
        days = rolled.groupby("date", sort=True).tail(1).set_index("date")
        days["zone"] = str(zone)
        days["date"] = days.index
        output.append(days.reset_index(drop=True))
    zones = pd.concat(output, ignore_index=True)
    complete = zones.dropna(subset=["error", "bias"])
    pooled = complete.groupby("date")[
        ["error", "bias", "baseline_error", "baseline_bias", "daily_error", "n"]
    ].mean()
    counts = complete.groupby("date").zone.nunique()
    pooled = pooled.loc[counts == len(cfg["demand"]["all_zones"])].copy()
    pooled["zone"], pooled["date"] = "pooled", pooled.index
    return pd.concat([zones, pooled.reset_index(drop=True)], ignore_index=True)


def settlement_frontiers(expected, scores, zones, now):
    """A gap stops the frontier even if later hours have settled."""
    result = {}
    for zone in zones:
        wanted = (
            expected.loc[(expected.zone == zone) & (expected.datetime_utc < now), "datetime_utc"]
            .sort_values()
            .unique()
        )
        if not len(wanted):
            result[zone] = None
            continue
        grid = pd.date_range(
            wanted[0], pd.Timestamp(now).floor("h") - pd.Timedelta(hours=1), freq="h"
        )
        have = scores.loc[scores.zone == zone, "datetime_utc"] if len(scores) else []
        missing = np.flatnonzero(~grid.isin(have))
        stop = int(missing[0]) if len(missing) else len(grid)
        result[zone] = grid[stop - 1].isoformat() if stop else None
    values = list(result.values())
    result["pooled"] = min(values) if all(values) else None
    return result


def threshold_for(cfg, metric, zone):
    values = cfg["drift"]["thresholds"][metric]
    return values["pooled"] if zone == "pooled" else values["per_zone"].get(zone)


def evaluate_triggers(
    metrics,
    cfg,
    state,
    *,
    model_sha,
    issue_date,
    settled_fraction,
    valid=True,
    concept_drift=False,
    watch_metrics=None,
):
    """Pure state transition: calling twice for an issue date is a no-op."""
    if state.get("evaluated_date") == issue_date:
        return state, {"action": "already_evaluated", "conditions": []}
    state = dict(state, evaluated_date=issue_date)
    event = {"action": "monitor", "conditions": [], "date": issue_date}
    if (
        not cfg["drift"]["thresholds_derived"]
        or model_sha != cfg["drift"]["thresholds_backtest_sha"]
    ):
        return state, event | {"action": "disarmed"}
    if not valid or settled_fraction < cfg["runtime"]["min_settled_fraction"]:
        return state, event | {"action": "pipeline_alert"}
    today = pd.Timestamp(issue_date)
    state.setdefault("monitor_started", issue_date)
    last_signal = pd.Timestamp(state.get("last_condition", state["monitor_started"]))
    if (today - last_signal).days >= cfg["drift"]["monitor_alarm_days"]:
        event["monitor_alarm"] = (
            "No conditions have fired; review monitor sensitivity. This does not retrain."
        )
    cooldown = state.get("cooldown_until")
    cooling = bool(cooldown and today < pd.Timestamp(cooldown))
    attempt, structural = False, False
    trigger_zones = set()
    for zone, part in metrics.groupby("zone", observed=True):
        part = part.sort_values("date")
        days = cfg["drift"]["debounce_days"]
        recent = part.tail(days)
        if len(recent) == days and (recent.date.diff().dropna() == pd.Timedelta(days=1)).all():
            for metric, col in [("rolling_error", "error"), ("signed_bias", "bias")]:
                bound = threshold_for(cfg, metric, zone)
                if bound is not None and (recent[col].abs() > bound).all():
                    event["conditions"].append(f"{zone}:{metric}")
                    attempt = True
                    trigger_zones.add(str(zone))
        bound = threshold_for(cfg, "structural_break", zone)
        if zone != "pooled" and bound is not None and part.daily_error.iloc[-1] > bound:
            event["conditions"].append(f"{zone}:structural_break")
            structural = True
            needed, span = cfg["drift"]["structural_break_escalate"]
            escalated = int((part.tail(span).daily_error > bound).sum()) >= needed
            attempt |= escalated
            if escalated:
                trigger_zones.add(str(zone))
    if structural:
        state["watch_opened"] = state.get("watch_opened", issue_date)
        event["low_confidence"] = True
    else:
        state.pop("watch_opened", None)
    watch_fire = False
    if watch_metrics is not None and len(watch_metrics) and cfg["drift"]["watch_threshold"]:
        for zone, part in watch_metrics.groupby("zone", observed=True):
            bound = cfg["drift"]["watch_threshold"].get(str(zone))
            if bound is not None and part.sort_values("date").error.iloc[-1] > bound:
                event["conditions"].append(f"{zone}:post_promotion_watch")
                watch_fire = True
                trigger_zones.add(str(zone))
    new_watch = watch_fire and not state.get("watch_active", False)
    if not attempt:
        state["firing_active"] = False
    if not watch_fire:
        state["watch_active"] = False
    if attempt or watch_fire:
        evidence = (
            [concept_drift.get(zone) for zone in trigger_zones]
            if isinstance(concept_drift, dict)
            else [concept_drift]
        )
        if not any(value is not None and bool(value) for value in evidence) and any(
            value is None for value in evidence
        ):
            event["action"] = "insufficient_band_evidence"
        elif not any(bool(value) for value in evidence):
            event["action"] = "data_drift"
        elif cooling and not new_watch:
            event["action"] = "cooldown"
        elif new_watch or (attempt and not state.get("firing_active", False)):
            event["action"] = "retrain"
            state["firing_active"] = bool(attempt)
            state["watch_active"] = bool(watch_fire)
        else:
            event["action"] = "episode_continues"
    if event["conditions"]:
        state["last_condition"] = issue_date
    return state, event


def finish_attempt(state, outcome, date, cfg):
    days = cfg["drift"][f"cooldown_after_{outcome}_days"]
    return (
        state
        | ({"watch_active": False} if outcome == "promotion" else {})
        | {
            "cooldown_until": (pd.Timestamp(date) + pd.Timedelta(days=days)).date().isoformat(),
            "last_attempt": date,
            "last_outcome": outcome,
        }
    )


def changed_within_bands(recent, reference, cfg):
    """Conservative routing: require deterioration within every populated band."""
    edges = [-np.inf, *cfg["evaluate"]["temperature_bands_c"], np.inf]
    changes, biases = [], []
    for low, high in zip(edges[:-1], edges[1:], strict=True):
        a = recent.loc[recent.observed_temperature.between(low, high, inclusive="left")]
        b = reference.loc[reference.observed_temperature.between(low, high, inclusive="left")]
        minimum = cfg["evaluate"]["insufficient_band_rows"]
        if len(a) < minimum or len(b) < minimum:
            continue
        ae = (a.prediction_mw - a.demand_mw) / a.demand_mw * 100
        be = (b.prediction_mw - b.demand_mw) / b.demand_mw * 100
        changes.append(ae.abs().mean() > be.abs().mean())
        biases.append(np.sign(ae.mean()))
    return bool(all(changes) and abs(sum(biases)) == len(biases)) if changes else None
