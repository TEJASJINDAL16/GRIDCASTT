"""Offline daily integration: real feature builder, model interface and files."""

import copy

import joblib
import numpy as np
import pandas as pd

from src.jobs.daily import forecast_history, run
from src.records import digest, write_json
from tests.test_backtest import small_inputs


class FixedModel:
    def __init__(self, cfg):
        self.cfg = cfg

    def predict(self, frame):
        return np.where(frame.zone == "IN-NO", 10000.0, 5000.0)

    def flags(self, frame):
        return [[] for _ in range(len(frame))]


def prepare(tmp_path, cfg, monkeypatch):
    cfg, demand, weather = small_inputs(copy.deepcopy(cfg))
    cfg["drift"]["thresholds_derived"] = False
    now = pd.Timestamp("2024-04-10 04:30", tz="UTC")
    target = pd.date_range("2024-04-10 19:00", periods=24, freq="h", tz="UTC")
    vintage = (
        weather.loc[weather.datetime_utc.isin(target)]
        .rename(columns={"datetime_utc": "target_datetime"})
        .copy()
    )
    vintage["issued_at"] = now
    vintage["lead_time_hours"] = (vintage.target_datetime - now).dt.total_seconds() / 3600
    directory = tmp_path / cfg["archive"]["vintage_dir"]
    directory.mkdir(parents=True)
    vintage.to_parquet(directory / "v.parquet", index=False)
    path = tmp_path / cfg["runtime"]["model_path"]
    path.parent.mkdir()
    joblib.dump(FixedModel(cfg), path)
    write_json(
        tmp_path / cfg["runtime"]["model_metadata"],
        {
            "approved": True,
            "artifact_sha256": digest(path),
            "version": "fixture",
            "backtest_sha": "fixture",
        },
    )
    monkeypatch.setattr("src.jobs.daily.load_cached", lambda root, cfg: (demand, weather))
    return cfg, now


def test_daily_is_idempotent_and_generates_complete_dashboard(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    first = run(tmp_path, cfg, now, offline=True)
    assert first["outcome"] == "success", first
    assert first["steps"] == [
        "archive",
        "score",
        "rolling_metrics",
        "triggers",
        "promotion",
        "forecast",
        "publish",
    ]
    assert run(tmp_path, cfg, now, offline=True) == first
    history = forecast_history(tmp_path, cfg)
    assert history.groupby("zone", observed=True).size().tolist() == [24, 24]
    assert history.lead_time_hours.min() == 14.5
    assert len(list((tmp_path / cfg["runtime"]["forecast_dir"]).glob("*.parquet"))) == 1
    page = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert "Pending measured actuals" in page and "Electricity Maps" in page
    assert (tmp_path / "docs/assets/IN-NO-today.svg").exists()


def test_demand_cache_failure_does_not_prevent_weather_forecast(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)

    def unavailable(root, cfg):
        raise FileNotFoundError("demand cache missing")

    monkeypatch.setattr("src.jobs.daily.load_cached", unavailable)
    status = run(tmp_path, cfg, now, offline=True)
    assert status["outcome"] == "degraded", status
    assert "forecast_file" in status
    assert status["alerts"]


def test_no_champion_records_failure_and_still_publishes(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    (tmp_path / cfg["runtime"]["model_path"]).unlink()
    status = run(tmp_path, cfg, now, offline=True)
    assert status["outcome"] == "failed"
    assert (tmp_path / "docs/index.html").exists()
    assert not list((tmp_path / cfg["runtime"]["forecast_dir"]).glob("*.parquet"))


def test_partial_weather_retries_and_preserves_attempts(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    path = tmp_path / cfg["archive"]["vintage_dir"] / "v.parquet"
    complete = pd.read_parquet(path)
    complete.loc[complete.zone == "IN-NO"].to_parquet(path, index=False)
    first = run(tmp_path, cfg, now, offline=True)
    assert first["outcome"] == "degraded" and first["retry_needed"]
    complete.to_parquet(path, index=False)
    second = run(tmp_path, cfg, now + pd.Timedelta(minutes=15), offline=True, retry=True)
    assert second["outcome"] == "success", second
    assert second["attempt"] == 2
    assert len(list((tmp_path / "state/run_attempts").glob("*.json"))) == 2


def test_publisher_failure_is_recorded(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)

    def broken(*args):
        raise OSError("disk full")

    monkeypatch.setattr("src.viz.dashboard.publish", broken)
    result = run(tmp_path, cfg, now, offline=True)
    assert result["outcome"] == "failed"
    assert any("publish_failed" in message for message in result["alerts"])


def test_settled_dashboard_has_comparators_and_lead_bins(tmp_path, cfg, monkeypatch):
    from src.viz.dashboard import publish

    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    assert run(tmp_path, cfg, now, offline=True)["outcome"] == "success"
    original = forecast_history(tmp_path, cfg)
    frames = []
    for day in range(40):
        frame = original.copy()
        frame["datetime_utc"] += pd.Timedelta(days=day)
        frame["date_ist"] = frame.datetime_utc.dt.tz_convert("Asia/Kolkata").dt.date
        frame["demand_mw"] = frame.prediction_mw * 0.99
        frame["is_estimated"] = False
        frame["observed_temperature"] = frame.temperature
        frames.append(frame)
    scores = pd.concat(frames, ignore_index=True)
    import json

    write_json(
        tmp_path / cfg["runtime"]["score_dir"] / "fixture.json",
        json.loads(scores.to_json(orient="records", date_format="iso")),
    )
    publish(tmp_path, cfg)
    page = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert "Shortfall hours" in page and "Baseline" in page
    assert (tmp_path / "docs/assets/IN-NO-lead_hour.svg").exists()
    assert (tmp_path / "docs/assets/IN-NO-rolling_error.svg").exists()
    assert (tmp_path / "docs/assets/IN-NO-signed_bias.svg").exists()


def test_missing_zone_does_not_show_yesterdays_forecast_as_current(tmp_path, cfg, monkeypatch):
    from src.viz.dashboard import publish

    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    run(tmp_path, cfg, now, offline=True)
    newer = forecast_history(tmp_path, cfg).loc[lambda f: f.zone == "IN-NO"].copy()
    newer["datetime_utc"] += pd.Timedelta(days=1)
    newer["issued_at"] += pd.Timedelta(days=1)
    newer["first_attempt"] = (now + pd.Timedelta(days=1)).isoformat()
    newer["issue_date"] = "2024-04-11"
    newer.to_parquet(tmp_path / cfg["runtime"]["forecast_dir"] / "newer.parquet", index=False)
    publish(tmp_path, cfg)
    page = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    zone = next(z for z in cfg["demand"]["all_zones"] if z != "IN-NO")
    missing = page.split(f'data-zone="{zone}"')[1].split("</article>")[0]
    assert "Unavailable for the latest issue" in missing
    assert f"{zone}-today.svg" not in missing


def test_failure_count_survives_the_change_of_date(tmp_path, cfg, monkeypatch):
    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    (tmp_path / cfg["runtime"]["model_path"]).unlink()
    for day in range(3):
        status = run(tmp_path, cfg, now + pd.Timedelta(days=day), offline=True)
        assert status["consecutive_failures"] == day + 1
    assert "consecutive_failure_limit_reached" in status["alerts"]
    assert not status["retry_needed"]


def test_stale_input_errors_are_reported_separately(tmp_path, cfg, monkeypatch):
    import json

    from src.viz.dashboard import publish

    cfg, now = prepare(tmp_path, cfg, monkeypatch)
    run(tmp_path, cfg, now, offline=True)
    rows = forecast_history(tmp_path, cfg)
    rows["flags"] = [["stale_weather_24h"] for _ in range(len(rows))]
    rows["demand_mw"] = rows.prediction_mw * 0.99
    rows["is_estimated"] = False
    rows["observed_temperature"] = rows.temperature
    write_json(
        tmp_path / cfg["runtime"]["score_dir"] / "stale.json",
        json.loads(rows.to_json(orient="records", date_format="iso")),
    )
    publish(tmp_path, cfg)
    page = (tmp_path / "docs/index.html").read_text(encoding="utf-8")
    assert "Measured actuals are recorded" in page
    assert "Input-degraded hours excluded from headline accuracy: 24" in page
    assert "Separate degraded-input MAPE: model" in page and "baseline" in page
