"""Daily archive -> settle -> monitor -> gate -> forecast -> publish."""

from __future__ import annotations

import fcntl
import json
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd

from src.backtest.run import load_cached
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.ingest.archive import (
    archive_demand_revisions,
    archive_forecast_vintage,
    archive_observed_weather,
)
from src.models.baselines import SeasonalNaive
from src.monitor.drift import (
    changed_within_bands,
    daily_metrics,
    evaluate_triggers,
    settlement_frontiers,
)
from src.records import digest, write_json


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def forecast_history(root, cfg):
    files = sorted((root / cfg["runtime"]["forecast_dir"]).glob("*.parquet"))
    return (
        pd.concat([pd.read_parquet(p) for p in files], ignore_index=True)
        if files
        else pd.DataFrame()
    )


def score_history(root, cfg):
    files = sorted((root / cfg["runtime"]["score_dir"]).glob("*.json"))
    rows = [row for path in files for row in read_json(path, [])]
    result = pd.DataFrame(rows)
    for col in ["datetime_utc", "issued_at"]:
        if col in result:
            result[col] = pd.to_datetime(result[col], utc=True)
    # Demand often settles before observed weather is released. Fill only the
    # analysis context in memory; never revise frozen actuals or rewrite scores.
    if len(result):
        if "observed_temperature" not in result:
            result["observed_temperature"] = np.nan
        if result.observed_temperature.isna().any():
            paths = [
                root / "data/raw" / f"weather_{zone}.parquet" for zone in cfg["demand"]["all_zones"]
            ]
            weather = [pd.read_parquet(path) for path in paths if path.exists()]
            if weather:
                observed = build_features(pd.concat(weather, ignore_index=True), cfg)[
                    ["zone", "datetime_utc", "temperature"]
                ].rename(columns={"temperature": "available_observed_temperature"})
                result = result.merge(
                    observed, on=["zone", "datetime_utc"], how="left", validate="one_to_one"
                )
                result["observed_temperature"] = result.observed_temperature.fillna(
                    result.available_observed_temperature
                )
                result = result.drop(columns="available_observed_temperature")
    return result


def select_versions(history, cfg):
    if history.empty:
        return history
    first = history.groupby("issue_date").issued_at.transform("min")
    if "first_attempt" in history:
        attempts = pd.to_datetime(history.first_attempt, utc=True)
        first = attempts.groupby(history.issue_date).transform("min").fillna(first)
    allowed = history.issued_at <= first + pd.Timedelta(hours=cfg["failure"]["retry_window_hours"])
    return (
        history.loc[allowed]
        .sort_values("issued_at")
        .drop_duplicates(["zone", "datetime_utc"], keep="last")
    )


def settle(history, actuals, existing, now):
    if history.empty:
        return pd.DataFrame()
    keys = ["zone", "datetime_utc"]
    actuals = actuals.loc[
        (actuals.datetime_utc < now) & ~actuals.is_estimated.fillna(True) & (actuals.demand_mw > 0)
    ]
    # Historical offline runs cannot see revisions first observed later.
    for column in ["observed_at", "updated_at"]:
        if column in actuals:
            available = pd.to_datetime(actuals[column], utc=True, errors="coerce")
            actuals = actuals.loc[available.isna() | (available <= now)]
    joined = history.merge(
        actuals[keys + ["demand_mw", "is_estimated"]], on=keys, validate="one_to_one"
    )
    if len(existing):
        have = pd.MultiIndex.from_frame(existing[keys])
        joined = joined.loc[~pd.MultiIndex.from_frame(joined[keys]).isin(have)]
    joined["settled_at"] = now.isoformat()
    return joined


def weather_for_day(root, cfg, now, target_date):
    frames = [
        pd.read_parquet(p) for p in sorted((root / cfg["archive"]["vintage_dir"]).glob("*.parquet"))
    ]
    if not frames:
        return pd.DataFrame()
    all_rows = pd.concat(frames, ignore_index=True)
    ages = (now - all_rows.issued_at).dt.total_seconds() / 3600
    mask = (
        (ages >= 0)
        & (ages <= cfg["failure"]["max_forecast_vintage_age_hours"])
        & (all_rows.lead_time_hours > 0)
        & (all_rows.target_datetime > now)
        & (
            all_rows.target_datetime.dt.tz_convert(cfg["project"]["timezone"]).dt.date
            == target_date
        )
    )
    selected = []
    for _, zone in all_rows.loc[mask].groupby("zone", observed=True):
        for issued in sorted(zone.issued_at.unique(), reverse=True):
            vintage = zone.loc[zone.issued_at == issued]
            if vintage.target_datetime.nunique() == 24 and vintage.temperature_2m.notna().all():
                selected.append(vintage)
                break
    return (
        pd.concat(selected, ignore_index=True).rename(columns={"target_datetime": "datetime_utc"})
        if selected
        else pd.DataFrame()
    )


def run(root=PROJECT_ROOT, cfg=None, now=None, *, offline=False, retry=False):
    cfg = cfg or load_config()
    now = pd.Timestamp(now or datetime.now(UTC)).tz_convert("UTC")
    local = now.tz_convert(cfg["project"]["timezone"])
    date = local.date().isoformat()
    state_dir = root / "state"
    state_dir.mkdir(exist_ok=True)
    with (state_dir / ".daily.lock").open("w", encoding="utf-8") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_locked(root, cfg, now, date, offline, retry)


def _run_locked(root, cfg, now, date, offline, retry):
    status_path = root / "state/runs" / f"{date}-daily.json"
    previous = read_json(status_path, {})
    earlier = [p for p in sorted((root / "state/runs").glob("*-daily.json")) if p.name[:10] < date]
    last_day = read_json(earlier[-1], {}) if earlier else {}
    failures_before = previous.get("consecutive_failures", last_day.get("consecutive_failures", 0))
    if previous.get("outcome") == "success" or (previous and not retry):
        return previous
    if retry:
        if not previous or not previous.get("retry_needed"):
            return previous
        if now > pd.Timestamp(previous["first_attempt"]) + pd.Timedelta(
            hours=cfg["failure"]["retry_window_hours"]
        ):
            return previous
        if previous.get("consecutive_failures", 0) >= cfg["failure"]["max_consecutive_failures"]:
            return previous
    status = {
        "run_at": now.isoformat(),
        "issue_date": date,
        "first_attempt": previous.get("first_attempt", now.isoformat()),
        "outcome": "failed",
        "alerts": [],
        "steps": [],
        "retry_needed": False,
        "offline": offline,
    }
    status["retry_deadline"] = (
        pd.Timestamp(status["first_attempt"])
        + pd.Timedelta(hours=cfg["failure"]["retry_window_hours"])
    ).isoformat()
    status["max_failures"] = cfg["failure"]["max_consecutive_failures"]
    try:
        status["steps"].append("archive")
        failed_demand = []
        if not offline:
            _, failed_weather = archive_forecast_vintage(cfg, now.to_pydatetime())
            _, failed_observed = archive_observed_weather(cfg)
            _, failed_demand = archive_demand_revisions(cfg, now.to_pydatetime())
            status["archive_failures"] = {
                "weather": failed_weather,
                "observed": failed_observed,
                "demand": failed_demand,
            }
            if failed_observed:
                status["alerts"].append(
                    "observed_weather_capture_failed: " + ", ".join(failed_observed)
                )
        history = select_versions(forecast_history(root, cfg), cfg)
        scores = score_history(root, cfg)
        status["steps"].append("score")
        try:
            demand, weather = load_cached(root, cfg)
        except (ValueError, FileNotFoundError) as exc:
            status["alerts"].append(f"scoring_skipped: {type(exc).__name__}")
            failed_demand = list(cfg["demand"]["all_zones"])
            demand, weather = pd.DataFrame(), pd.DataFrame()
        if failed_demand:
            status["alerts"].append("scoring_skipped")
        elif len(history):
            new = settle(history, demand, scores, now)
            if len(new):
                new["observed_temperature"] = np.nan
                observed = build_features(weather, cfg)[["zone", "datetime_utc", "temperature"]]
                new = new.drop(columns="observed_temperature").merge(
                    observed.rename(columns={"temperature": "observed_temperature"}),
                    on=["zone", "datetime_utc"],
                    how="left",
                )
                path = root / cfg["runtime"]["score_dir"] / f"{date}-{now.strftime('%H%M%S')}.json"
                write_json(path, json.loads(new.to_json(orient="records", date_format="iso")))
                scores = score_history(root, cfg)
            status["scored_rows"] = len(new)
            if not len(new) and not retry:
                status["alerts"].append("no_new_settled_scores")
        metadata_path = root / cfg["runtime"]["model_metadata"]
        metadata = read_json(metadata_path, {})
        status["steps"].append("rolling_metrics")
        if len(history):
            frontiers = settlement_frontiers(history, scores, cfg["demand"]["all_zones"], now)
            past = history.loc[history.datetime_utc < now]
            status["settled_fraction"] = len(scores) / len(past) if len(past) else 0.0
            status["frontiers"] = frontiers
            allowed = []
            for zone, end in frontiers.items():
                if zone != "pooled" and end and len(scores):
                    allowed.append(
                        scores.loc[
                            (scores.zone == zone) & (scores.datetime_utc <= pd.Timestamp(end))
                        ]
                    )
            monitor_rows = pd.concat(allowed, ignore_index=True) if allowed else pd.DataFrame()
        else:
            status["settled_fraction"], monitor_rows = 0.0, pd.DataFrame()
        metrics = daily_metrics(monitor_rows, cfg)
        pooled_end = status.get("frontiers", {}).get("pooled")
        if len(metrics) and pooled_end:
            common = daily_metrics(
                monitor_rows.loc[monitor_rows.datetime_utc <= pd.Timestamp(pooled_end)], cfg
            )
            metrics = pd.concat(
                [metrics.loc[metrics.zone != "pooled"], common.loc[common.zone == "pooled"]],
                ignore_index=True,
            )
        status["steps"].append("triggers")
        drift_path = root / "state/drift/current.json"
        drift_state = read_json(drift_path, {})
        reference_path = root / "data/interim/model_predictions.parquet"
        concept = None
        if len(monitor_rows) and reference_path.exists():
            reference = pd.read_parquet(reference_path).loc[lambda f: f.model == "hybrid"]
            recent = monitor_rows.loc[
                monitor_rows.datetime_utc
                >= monitor_rows.datetime_utc.max()
                - pd.Timedelta(days=cfg["drift"]["rolling_window_days"])
            ]
            concept = {"pooled": changed_within_bands(recent, reference, cfg)}
            for zone in cfg["demand"]["all_zones"]:
                concept[zone] = changed_within_bands(
                    recent.loc[recent.zone == zone], reference.loc[reference.zone == zone], cfg
                )
        watch = None
        if len(monitor_rows) and "model_version" in monitor_rows:
            watch = daily_metrics(
                monitor_rows.loc[monitor_rows.model_version == metadata.get("version")],
                cfg,
                window=cfg["drift"]["post_promotion_watch_days"],
            )
        if not failed_demand:
            drift_state, event = evaluate_triggers(
                metrics,
                cfg,
                drift_state,
                model_sha=metadata.get("backtest_sha"),
                issue_date=date,
                settled_fraction=status["settled_fraction"],
                valid=bool(status.get("scored_rows")),
                concept_drift=concept,
                watch_metrics=watch,
            )
            write_json(drift_path, drift_state)
            write_json(root / "state/drift" / f"{date}.json", event)
        else:
            event = {"action": "scoring_skipped", "conditions": []}
        status["trigger"] = event
        status["steps"].append("promotion")
        if event["action"] == "retrain":
            from src.jobs.train import retrain

            attempt = retrain(
                root,
                cfg,
                demand,
                weather,
                now,
                event,
                frontier=status.get("frontiers", {}).get("pooled"),
            )
            status["retrain_outcome"] = attempt["outcome"]
            if attempt["outcome"] == "failure":
                status["alerts"].append(
                    "retraining_failed: " + attempt.get("error", "unknown error")
                )
            metadata = read_json(metadata_path, {})
        status["steps"].append("forecast")
        # In live operation network calls and training take time. Lead times
        # describe the actual issuance, not the scheduled start of the job.
        if not offline:
            now = pd.Timestamp.now(tz="UTC")
        model_path = root / cfg["runtime"]["model_path"]
        if not metadata.get("approved") or not model_path.exists():
            raise ValueError("no approved champion; run the model selection gate")
        if digest(model_path) != metadata["artifact_sha256"]:
            raise ValueError("champion artifact does not match registry digest")
        model = joblib.load(model_path)
        if model.cfg["features"] != cfg["features"]:
            raise ValueError("feature configuration changed since champion training")
        tomorrow = (now.tz_convert(cfg["project"]["timezone"]) + pd.Timedelta(days=1)).date()
        vintage = weather_for_day(root, cfg, now, tomorrow)
        if vintage.empty:
            status["retry_needed"] = True
            raise ValueError("no usable forecast vintage for tomorrow")
        if vintage.zone.nunique() < len(cfg["demand"]["all_zones"]):
            status["retry_needed"] = True
        features = build_features(vintage.drop(columns=["issued_at", "lead_time_hours"]), cfg)
        features["prediction_mw"] = model.predict(features)
        valid_zones = features.groupby("zone", observed=True).prediction_mw.agg(
            lambda x: len(x) == 24 and np.isfinite(x).all() and (x > 0).all()
        )
        features = features.loc[features.zone.isin(valid_zones.index[valid_zones])].copy()
        if features.zone.nunique() < cfg["failure"]["min_zones_to_publish"]:
            raise ValueError("too few complete zones to publish")
        features["issued_at"], features["issue_date"] = now, date
        features["first_attempt"] = status["first_attempt"]
        features["lead_time_hours"] = (features.datetime_utc - now).dt.total_seconds() / 3600
        features["model_version"] = metadata["version"]
        features["fold"] = 0
        features["flags"] = model.flags(features)
        ages = (
            (now - vintage.groupby("zone", observed=True).issued_at.max()).dt.total_seconds() / 3600
        ).to_dict()
        captured = vintage.groupby("zone", observed=True).issued_at.max()
        fresh = captured >= pd.Timestamp(status["first_attempt"])
        for index, row in features.iterrows():
            flags = list(row["flags"]) + ["placeholder_in_use"]
            if not fresh.get(row.zone, False):
                flags.append(f"stale_weather_{ages[row.zone]:.1f}h")
                status["retry_needed"] = True
            if event.get("low_confidence"):
                flags.append("low_confidence")
            features.at[index, "flags"] = flags
        features["baseline_mw"] = np.nan
        if len(demand) and len(weather):
            base = build_features(weather, cfg, demand=demand)
            features["baseline_mw"] = SeasonalNaive(cfg).fit(base).predict(features).prediction_mw
        path = root / cfg["runtime"]["forecast_dir"] / f"{date}-{now.strftime('%H%M%S%f')}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        features.to_parquet(temporary, index=False)
        temporary.replace(path)
        status["forecast_file"] = str(path.relative_to(root))
        status["zones"] = sorted(features.zone.unique().tolist())
        status["weather_age_hours"] = ages
        status["model_version"] = metadata["version"]
        status["issued_at"] = now.isoformat()
        status["outcome"] = (
            "degraded"
            if status["retry_needed"]
            or status["alerts"]
            or len(valid_zones[valid_zones]) < len(cfg["demand"]["all_zones"])
            else "success"
        )
    except Exception as exc:
        status["alerts"].append(f"{type(exc).__name__}: {exc}")
    finally:
        status["steps"].append("publish")
        status["consecutive_failures"] = failures_before + 1 if status["outcome"] == "failed" else 0
        if status["consecutive_failures"] >= cfg["failure"]["max_consecutive_failures"]:
            status["retry_needed"] = False
            status["alerts"].append("consecutive_failure_limit_reached")
        status["attempt"] = previous.get("attempt", 0) + 1
        attempts = root / "state/run_attempts" / f"{date}-{status['attempt']:03d}.json"
        write_json(attempts, status)
        write_json(status_path, status)
        from src.viz.dashboard import publish

        try:
            publish(root, cfg)
        except Exception as exc:
            status["outcome"] = "failed"
            status["consecutive_failures"] = failures_before + 1
            if status["consecutive_failures"] >= cfg["failure"]["max_consecutive_failures"]:
                status["retry_needed"] = False
                if "consecutive_failure_limit_reached" not in status["alerts"]:
                    status["alerts"].append("consecutive_failure_limit_reached")
            status["alerts"].append(f"publish_failed: {type(exc).__name__}: {exc}")
            write_json(attempts, status)
            write_json(status_path, status)
    return status
