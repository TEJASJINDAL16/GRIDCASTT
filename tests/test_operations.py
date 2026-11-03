"""Settlement, replay and promotion failure cases."""

import copy

import numpy as np
import pandas as pd

from src.jobs.daily import score_history, select_versions, settle, weather_for_day
from src.monitor.drift import daily_metrics, evaluate_triggers, finish_attempt, settlement_frontiers
from src.monitor.registry import compare


def scores(days=40):
    stamps = pd.date_range("2025-01-01 19:00", periods=24 * days, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "datetime_utc": stamps,
            "zone": "IN-NO",
            "prediction_mw": 110.0,
            "baseline_mw": 120.0,
            "demand_mw": 100.0,
            "is_estimated": False,
            "flags": [[] for _ in stamps],
        }
    )


def test_unsettled_hour_stops_frontier_and_missing_day_stops_window(cfg):
    frame = scores()
    now = frame.datetime_utc.max() + pd.Timedelta(hours=1)
    settled = frame.drop(index=10)
    frontier = settlement_frontiers(frame, settled, ["IN-NO"], now)
    assert pd.Timestamp(frontier["IN-NO"]) == frame.datetime_utc.iloc[9]
    assert not daily_metrics(settled.head(24 * 30), cfg).error.notna().any()


def test_partial_frontier_day_uses_complete_trailing_hours(cfg):
    frame = scores().iloc[: 24 * 30 + 7]
    metrics = daily_metrics(frame, cfg)
    latest = metrics.loc[metrics.zone == "IN-NO"].iloc[-1]
    assert latest.n == 720
    assert latest.error == 10.0


def test_late_observed_weather_fills_context_without_rewriting_frozen_scores(tmp_path, cfg):
    from src.records import write_json

    stamp = pd.Timestamp("2025-01-01 19:00", tz="UTC")
    path = tmp_path / cfg["runtime"]["score_dir"] / "frozen.json"
    write_json(
        path,
        [
            {
                "zone": "IN-NO",
                "datetime_utc": stamp.isoformat(),
                "demand_mw": 100.0,
                "prediction_mw": 110.0,
                "baseline_mw": 120.0,
                "temperature": 29.0,
                "observed_temperature": None,
                "is_estimated": False,
                "flags": [],
            }
        ],
    )
    original = path.read_bytes()
    assert score_history(tmp_path, cfg).observed_temperature.isna().all()
    weather = pd.DataFrame(
        {
            "zone": ["IN-NO"],
            "datetime_utc": [stamp],
            "point_name": [cfg["weather"]["points"]["IN-NO"]["name"]],
            "temperature_2m": [33.0],
        }
    )
    raw = tmp_path / "data/raw/weather_IN-NO.parquet"
    raw.parent.mkdir(parents=True)
    weather.to_parquet(raw, index=False)
    enriched = score_history(tmp_path, cfg)
    assert enriched.observed_temperature.iloc[0] == 33.0
    assert enriched.temperature.iloc[0] == 29.0
    assert enriched.demand_mw.iloc[0] == 100.0
    assert path.read_bytes() == original


def test_frozen_scores_and_retry_version_cutoff(cfg):
    frame = scores(1)
    issue = pd.Timestamp("2025-01-01 04:30", tz="UTC")
    forecasts = frame.drop(columns=["demand_mw", "is_estimated"]).assign(
        issued_at=issue, issue_date="2025-01-01"
    )
    newer = forecasts.assign(issued_at=issue + pd.Timedelta(hours=1), prediction_mw=105.0)
    too_late = forecasts.assign(issued_at=issue + pd.Timedelta(hours=5), prediction_mw=1.0)
    selected = select_versions(pd.concat([forecasts, newer, too_late]), cfg)
    assert (selected.prediction_mw == 105).all()
    now = frame.datetime_utc.max() + pd.Timedelta(days=1)
    once = settle(selected, frame, pd.DataFrame(), now)
    assert len(once) == 24
    assert settle(selected, frame.assign(demand_mw=999.0), once, now).empty
    future_revision = frame.assign(observed_at=now + pd.Timedelta(days=1))
    assert settle(selected, future_revision, pd.DataFrame(), now).empty
    # A missing initial publication must not extend the true retry deadline.
    late_first = newer.assign(first_attempt=issue)
    late_version = too_late.assign(first_attempt=issue)
    chosen = select_versions(pd.concat([late_first, late_version], ignore_index=True), cfg)
    assert (chosen.prediction_mw == 105).all()


def test_stale_scores_do_not_enter_monitor_but_placeholders_do(cfg):
    frame = scores()
    frame["flags"] = [["placeholder_in_use"] for _ in range(len(frame))]
    assert daily_metrics(frame, cfg).error.notna().any()
    frame["flags"] = [["stale_weather_24h"] for _ in range(len(frame))]
    assert daily_metrics(frame, cfg).empty


def test_monitor_disarm_cooldown_and_idempotency(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["drift"].update(thresholds_derived=True, thresholds_backtest_sha="record", debounce_days=3)
    for name in cfg["drift"]["thresholds"]:
        cfg["drift"]["thresholds"][name] = {
            "pooled": 5.0,
            "per_zone": {"IN-NO": 5.0 if name != "structural_break" else 100.0},
        }
    metrics = daily_metrics(scores(), cfg)
    args = dict(
        model_sha="wrong", issue_date="2025-03-01", settled_fraction=1.0, concept_drift=True
    )
    _, event = evaluate_triggers(metrics, cfg, {}, **args)
    assert event["action"] == "disarmed"
    args["model_sha"] = "record"
    state, event = evaluate_triggers(metrics, cfg, {}, **args)
    assert event["action"] == "retrain"
    _, event = evaluate_triggers(metrics, cfg, state, **args)
    assert event["action"] == "already_evaluated"
    cooling = finish_attempt({}, "failure", "2025-02-28", cfg)
    _, event = evaluate_triggers(metrics, cfg, cooling, **args)
    assert event["action"] == "cooldown"
    _, event = evaluate_triggers(metrics, cfg, {}, **(args | {"concept_drift": False}))
    assert event["action"] == "data_drift"
    _, event = evaluate_triggers(
        metrics, cfg, {}, **(args | {"concept_drift": {"IN-NO": False, "IN-NE": True}})
    )
    assert event["action"] == "data_drift"
    _, event = evaluate_triggers(metrics, cfg, {}, **(args | {"concept_drift": {"IN-NO": True}}))
    assert event["action"] == "retrain"
    _, event = evaluate_triggers(metrics, cfg, {}, **(args | {"concept_drift": {"IN-NO": None}}))
    assert event["action"] == "insufficient_band_evidence"


def test_bad_model_and_mismatched_cohorts_cannot_promote(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["evaluate"]["veto_tolerance"] = dict.fromkeys(cfg["evaluate"]["veto_tolerance"], 0.1)
    frame = scores().assign(fold=1, observed_temperature=25.0)
    baseline = frame.assign(model="seasonal_naive", prediction_mw=frame.baseline_mw)
    bad = frame.assign(model="hybrid", prediction_mw=500.0)
    assert not compare(pd.concat([bad, baseline], ignore_index=True), cfg)["promote"]
    assert not compare(pd.concat([bad.iloc[1:], baseline], ignore_index=True), cfg)["promote"]


def test_seven_day_watch_can_escalate_once_inside_cooldown(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["drift"].update(
        thresholds_derived=True, thresholds_backtest_sha="record", watch_threshold={"IN-NO": 5.0}
    )
    metrics = daily_metrics(scores(), cfg)
    state = finish_attempt({}, "promotion", "2025-02-28", cfg)
    args = dict(
        model_sha="record",
        issue_date="2025-03-01",
        settled_fraction=1.0,
        concept_drift=True,
        watch_metrics=metrics,
    )
    state, event = evaluate_triggers(metrics, cfg, state, **args)
    assert event["action"] == "retrain"
    state = finish_attempt(state, "rejection", "2025-03-01", cfg)
    _, event = evaluate_triggers(metrics, cfg, state, **(args | {"issue_date": "2025-03-02"}))
    assert event["action"] == "cooldown"


def test_vintage_must_be_past_complete_and_positive_lead(tmp_path, cfg):
    now = pd.Timestamp("2025-01-01 04:30", tz="UTC")
    target = pd.date_range("2025-01-01 19:00", periods=24, freq="h", tz="UTC")
    vintage = pd.DataFrame(
        {
            "issued_at": now - pd.Timedelta(days=1),
            "target_datetime": target,
            "zone": "IN-NO",
            "temperature_2m": 30.0,
            "lead_time_hours": 48.0,
        }
    )
    future = vintage.assign(issued_at=now + pd.Timedelta(hours=1), temperature_2m=55.0)
    path = tmp_path / cfg["archive"]["vintage_dir"]
    path.mkdir(parents=True)
    pd.concat([vintage, future], ignore_index=True).to_parquet(path / "v.parquet")
    chosen = weather_for_day(tmp_path, cfg, now, pd.Timestamp("2025-01-02").date())
    assert len(chosen) == 24 and np.all(chosen.temperature_2m == 30.0)
