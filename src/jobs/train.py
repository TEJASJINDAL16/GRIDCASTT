"""Fit artifacts and record every accepted, rejected or failed attempt."""

import json
import time
from dataclasses import replace

import joblib
import numpy as np
import pandas as pd

from src.backtest.run import evaluate
from src.backtest.splits import Fold, make_splits
from src.features.build import build_features, trainable_mask
from src.features.forecast_noise import simulate_forecast_weather
from src.models.hybrid import Hybrid
from src.monitor.drift import finish_attempt
from src.monitor.registry import compare
from src.records import digest, pins, track, write_json
from src.tracking import log_run


def fit_artifact(root, cfg, demand, weather, now, *, approved, name="champion", frontier=None):
    weather = weather.dropna(subset=["temperature_2m"])
    frame = build_features(weather, cfg, demand=demand)
    cutoff = min(
        pd.Timestamp(now) - pd.Timedelta(days=cfg["splits"]["purge_gap_days"]),
        frame.datetime_utc.max() + pd.Timedelta(hours=1),
    )
    if frontier is not None:
        cutoff = min(cutoff, pd.Timestamp(frontier) + pd.Timedelta(hours=1))
    targets = frame.loc[trainable_mask(frame, cfg) & (frame.datetime_utc < cutoff)]
    noisy = simulate_forecast_weather(
        weather.loc[weather.datetime_utc < cutoff], cfg, stream=cfg["train"]["seed"]
    )
    train = build_features(noisy, cfg, demand=targets)
    model = Hybrid(cfg)
    numeric = [c for c in model.columns if c != "zone"] + ["demand_mw"]
    if train.empty or not np.isfinite(train[numeric].to_numpy(dtype=float)).all():
        raise ValueError("refusing to write a training matrix with missing or non-finite values")
    matrix = root / "data/interim" / f"{name}_training.parquet"
    matrix.parent.mkdir(parents=True, exist_ok=True)
    train.to_parquet(matrix, index=False)
    began = time.monotonic()
    model.fit(train, train_end=cutoff)
    directory = root / "models"
    directory.mkdir(exist_ok=True)
    path = directory / f"{name}.joblib"
    temporary = directory / f".{name}.tmp"
    joblib.dump(model, temporary)
    temporary.replace(path)
    track(root, matrix, path)
    metadata = {
        "approved": approved,
        "version": digest(path)[:16],
        "artifact_sha256": digest(path),
        "backtest_sha": cfg["drift"]["thresholds_backtest_sha"],
        "trained_at": pd.Timestamp(now).isoformat(),
        "train_end": cutoff.isoformat(),
        "newest_training_row": train.datetime_utc.max().isoformat(),
        "ranges": model.ranges,
        "loss_by_zone": model.loss_by_zone,
        "best_iteration": model.best_iteration,
        "refit_iterations": model.iterations,
        "pins": pins(root, cfg, matrix),
        "duration_seconds": time.monotonic() - began,
    }
    write_json(directory / f"{name}.json", metadata)
    return metadata


def prospective_plan(base, cfg, champion_end, frontier):
    """Complete monthly folds which the deployed champion never trained on.

    The final research holdout is already scored before deployment. It must
    not reserve a new twelve-month holdout on every live retrain.
    """
    original = make_splits(base, cfg)
    tz = cfg["project"]["timezone"]
    earliest = (
        pd.Timestamp(champion_end) + pd.Timedelta(days=cfg["splits"]["purge_gap_days"])
    ).tz_convert(tz)
    start = pd.Timestamp(year=earliest.year, month=earliest.month, day=1, tz=tz)
    if start < earliest:
        start += pd.DateOffset(months=1)
    last = (pd.Timestamp(frontier) + pd.Timedelta(hours=1)).tz_convert(tz)
    end = pd.Timestamp(year=last.year, month=last.month, day=1, tz=tz)
    start = max(start, end - pd.DateOffset(months=cfg["splits"]["walk_forward_folds"]))
    folds = []
    while start < end:
        cutoff = (
            start
            - pd.Timedelta(days=1 + cfg["splits"]["purge_gap_days"])
            + pd.Timedelta(hours=cfg["backtest"]["issue_hour_ist"])
        )
        stop = start + pd.DateOffset(months=1)
        folds.append(
            Fold(
                len(folds) + 1,
                original.folds[0].train_start,
                cutoff.tz_convert("UTC"),
                (cutoff - pd.Timedelta(weeks=cfg["splits"]["early_stopping_weeks"])).tz_convert(
                    "UTC"
                ),
                start.tz_convert("UTC"),
                stop.tz_convert("UTC"),
            )
        )
        start = stop
    return replace(
        original,
        folds=tuple(folds),
        holdout_start=end.tz_convert("UTC"),
        holdout_end=end.tz_convert("UTC"),
    )


def retrain(root, cfg, demand, weather, now, trigger, *, frontier=None):
    """Require prospective evaluation dates after the incumbent was trained."""
    date = pd.Timestamp(now).date().isoformat()
    record = {"trigger": trigger, "pins": pins(root, cfg), "outcome": "failure", "date": date}
    try:
        metadata = json.loads((root / cfg["runtime"]["model_metadata"]).read_text(encoding="utf-8"))
        champion = joblib.load(root / cfg["runtime"]["model_path"])
        if champion.cfg["train"] != cfg["train"] or champion.cfg["features"] != cfg["features"]:
            raise ValueError(
                "a live retrain cannot change the champion's parameters or feature contract"
            )
        base = build_features(weather, cfg, demand=demand)
        if frontier is None:
            raise ValueError("retraining requires a pooled settlement frontier")
        plan = prospective_plan(base, cfg, metadata["train_end"], frontier)
        record["evaluation_folds"] = len(plan.folds)
        record["settlement_frontier"] = frontier
        if not plan.folds:
            record.update(
                outcome="rejection",
                reasons=["no prospective measured folds after champion training cutoff"],
            )
        else:
            result = evaluate(demand, weather, cfg, hybrid=True, plan=plan)
            challenger = result["predictions"].loc[lambda f: f.model == "hybrid"].copy()
            incumbent = challenger.copy()
            incumbent["prediction_mw"] = champion.predict(incumbent)
            incumbent["model"] = "champion"
            decision = compare(
                pd.concat([challenger, incumbent], ignore_index=True), cfg, champion="champion"
            )
            record["decision"] = decision
            if decision["promote"]:
                candidate = fit_artifact(
                    root,
                    cfg,
                    demand,
                    weather,
                    now,
                    approved=True,
                    name="candidate",
                    frontier=frontier,
                )
                # The metadata digest detects interruption between these two atomic replacements.
                (root / "models/candidate.joblib").replace(root / cfg["runtime"]["model_path"])
                track(root, root / cfg["runtime"]["model_path"])
                write_json(root / cfg["runtime"]["model_metadata"], candidate)
                record.update(outcome="promotion", model=candidate)
            else:
                record["outcome"] = "rejection"
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    path = root / "state/promotions" / f"{date}.json"
    write_json(path, record)
    drift_path = root / "state/drift/current.json"
    state = json.loads(drift_path.read_text(encoding="utf-8")) if drift_path.exists() else {}
    write_json(drift_path, finish_attempt(state, record["outcome"], date, cfg))
    log_run(root, cfg, f"retrain-{record['outcome']}", {}, [path])
    return record
