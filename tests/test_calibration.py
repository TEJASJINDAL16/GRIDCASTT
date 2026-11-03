"""Calibration and the live trigger must agree on the events being counted."""

import copy

import pandas as pd

from scripts.calibrate import (
    combined_attempt_starts,
    detection_delay,
    episodes,
    firings,
    refreshed_watch_metrics,
)
from src.jobs.train import prospective_plan
from src.monitor.drift import evaluate_triggers
from tests.test_operations import scores
from tests.test_splits import history


def test_alternating_error_and_bias_do_not_pass_debounce(cfg):
    rows = pd.DataFrame(
        {
            "zone": "IN-NO",
            "date": pd.date_range("2025-01-01", periods=3),
            "error": [8.0, 1.0, 8.0],
            "bias": [1.0, 8.0, 1.0],
            "daily_error": 1.0,
        }
    )
    bounds = {"IN-NO": {"error": 5.0, "bias": 5.0, "daily_error": 100.0}}
    assert not firings(rows, bounds, 3).any()


def test_replay_firing_matches_runtime_before_routing(cfg):
    cfg = copy.deepcopy(cfg)
    cfg["drift"].update(thresholds_derived=True, thresholds_backtest_sha="test", debounce_days=3)
    for metric in cfg["drift"]["thresholds"]:
        cfg["drift"]["thresholds"][metric] = {"pooled": None, "per_zone": {"IN-NO": 5.0}}
    rows = pd.DataFrame(
        {
            "zone": "IN-NO",
            "date": pd.date_range("2025-01-01", periods=10),
            "error": [1.0, 7.0, 8.0, 9.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
            "bias": 1.0,
            "daily_error": [1.0, 8.0, 1.0, 8.0, 1.0, 8.0, 1.0, 1.0, 1.0, 1.0],
        }
    )
    replay = firings(rows, {"IN-NO": {"error": 5.0, "bias": 5.0, "daily_error": 5.0}}, 3)
    for day in range(len(rows)):
        _, event = evaluate_triggers(
            rows.iloc[: day + 1],
            cfg,
            {},
            model_sha="test",
            issue_date=str(rows.date.iloc[day].date()),
            settled_fraction=1.0,
            concept_drift=True,
        )
        assert replay.iloc[day] == (event["action"] == "retrain")


def test_long_breach_is_one_episode_and_cooldown_suppresses_new_clump():
    dates = pd.date_range("2025-01-01", periods=40)
    signal = pd.Series([True] * 18 + [False] * 3 + [True] * 19, index=dates)
    assert episodes(signal, 30) == 2
    assert episodes(signal, 50) == 1


def test_live_folds_use_only_prospective_completed_months(cfg):
    cutoff = pd.Timestamp("2025-03-15", tz="UTC")
    frontier = pd.Timestamp("2026-08-12", tz="UTC")
    plan = prospective_plan(history(cfg), cfg, cutoff, frontier)
    assert len(plan.folds) == 12
    assert plan.folds[0].test_start > cutoff + pd.Timedelta(days=cfg["splits"]["purge_gap_days"])
    assert plan.folds[-1].test_end <= frontier
    assert plan.holdout_start == plan.folds[-1].test_end


def test_recent_champion_has_no_fabricated_comparison(cfg):
    plan = prospective_plan(history(cfg), cfg, "2026-08-01T00:00:00Z", "2026-08-12T00:00:00Z")
    assert not plan.folds


def test_an_existing_alarm_does_not_count_as_detection_of_new_drift():
    days = pd.date_range("2025-01-01", periods=40, tz="UTC")
    assert detection_delay(pd.Series(True, index=days), days[20], 14) is None
    signal = pd.Series([True] * 10 + [False] * 15 + [True] * 15, index=days)
    assert detection_delay(signal, days[20], 14) == 5


def test_watch_calibration_does_not_mix_two_models_to_fill_seven_days(cfg):
    frame = scores(12)
    frame["fold"] = [1] * (6 * 24) + [2] * (6 * 24)
    watch = refreshed_watch_metrics(frame, cfg)
    assert not watch.error.notna().any()


def test_watch_escalation_is_a_second_attempt_inside_a_primary_episode():
    days = pd.date_range("2025-01-01", periods=10)
    primary = pd.Series(True, index=days)
    watch = pd.Series([False] * 3 + [True] * 7, index=days)
    assert combined_attempt_starts(primary, watch, 14).tolist() == [days[0], days[3]]
    assert combined_attempt_starts(primary, primary, 14).tolist() == [days[0]]
