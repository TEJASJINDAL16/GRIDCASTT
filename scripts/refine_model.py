"""Evaluate demand-history alternatives without consuming the final holdout."""

import copy
import hashlib
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.backtest.metrics import score, stratified_scores
from src.backtest.run import load_cached
from src.backtest.splits import issue_times, measured_mask, research_plan
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.features.forecast_noise import simulate_forecast_weather
from src.jobs.daily import read_json
from src.models.history import AdaptiveHistory, DemandHistory, HistoryResidual
from src.monitor.registry import compare
from src.records import track, write_json


def main():
    root, cfg = PROJECT_ROOT, load_config()
    demand, weather = load_cached(root, cfg)
    plan = research_plan(root, build_features(weather, cfg, demand=demand), cfg)
    # Trim before feature construction: final holdout values cannot enter any fit.
    demand = demand.loc[demand.datetime_utc < plan.holdout_start]
    weather = weather.loc[weather.datetime_utc < plan.holdout_start]
    history = build_features(weather, cfg, demand=demand)
    lookup = DemandHistory(history, cfg)
    training = build_features(
        simulate_forecast_weather(weather.reset_index(drop=True), cfg, stream=901),
        cfg,
        demand=demand,
    )
    training["issued_at"] = issue_times(training.datetime_utc, cfg)
    history_features = lookup.transform(training)
    old = pd.read_parquet(root / "data/interim/model_predictions.parquet")
    cohort = old.loc[old.model == "seasonal_naive"].copy().reset_index(drop=True)
    assert cohort.datetime_utc.max() < plan.holdout_start
    names = [
        "seasonal_naive",
        "history_mean_2",
        "history_mean_4",
        "history_residual",
        "adaptive_history",
    ]
    tuning = read_json(root / "reports/tuning/result.json", {})
    end = pd.Timestamp(tuning["validation_end"])
    start = pd.Timestamp(tuning["validation_start"])
    cutoff = pd.Timestamp(tuning["train_end"])
    mask = measured_mask(training) & (training.datetime_utc < cutoff)
    model = HistoryResidual(cfg).fit(history_features.loc[mask], training.loc[mask, "demand_mw"])
    valid = (
        measured_mask(training)
        & training.datetime_utc.between(start, end, inclusive="left")
        & history_features.baseline_mw.gt(0)
    )
    f = history_features.loc[valid]
    candidates = {
        "seasonal_naive": f.baseline_mw,
        "history_mean_2": f[["lag_0", "lag_1"]].mean(axis=1),
        "history_mean_4": f[[f"lag_{k}" for k in range(4)]].mean(axis=1),
        "history_residual": model.predict(f),
    }
    y = training.loc[valid, "demand_mw"]
    denominator = (y - f.baseline_mw).abs().sum()
    if not np.isfinite(denominator) or denominator <= 0:
        raise ValueError("Validation requires nonzero measured baseline error")
    validation = {
        name: float((y - values).abs().sum() / denominator) for name, values in candidates.items()
    }
    selected = min(validation, key=validation.get)
    destination = root / "reports/refinement"
    destination.mkdir(exist_ok=True)
    write_json(
        destination / "protocol.json",
        {
            "selected_on_pretest_validation": selected,
            "validation_mase": validation,
            "validation_rows": int(valid.sum()),
            "validation_zones": training.loc[valid, "zone"].unique().tolist(),
            "settings": cfg["refinement"],
            "holdout_scored": False,
            "selection_frozen_before_folds": True,
        },
    )
    predictions = []
    choices = []
    for fold in plan.folds:
        train = (
            measured_mask(training)
            & (training.datetime_utc < fold.train_end)
            & (training.datetime_utc >= fold.train_start)
        )
        fitted = HistoryResidual(cfg).fit(
            history_features.loc[train], training.loc[train, "demand_mw"]
        )
        recent = train & (
            training.datetime_utc
            >= fold.train_end - pd.Timedelta(weeks=cfg["refinement"]["adaptive_validation_weeks"])
        )
        adaptive = AdaptiveHistory(cfg).fit(
            history_features.loc[recent], training.loc[recent, "demand_mw"]
        )
        choices.append(
            {"fold": fold.number, "train_end": str(fold.train_end), "windows": adaptive.selected}
        )
        query = cohort.loc[cohort.fold == fold.number].copy()
        features = lookup.transform(query)
        if not np.allclose(features.baseline_mw, query.baseline_mw):
            raise ValueError(
                "Refreshed history changed the baseline; comparison cannot reuse the frozen cohort"
            )
        values = [
            features.baseline_mw,
            features[["lag_0", "lag_1"]].mean(axis=1),
            features[[f"lag_{k}" for k in range(4)]].mean(axis=1),
            fitted.predict(features),
            adaptive.predict(features),
        ]
        for name, value in zip(names, values, strict=True):
            row = query.copy()
            row["model"], row["prediction_mw"] = name, value
            row["history_source_datetime"] = features.source_datetime
            predictions.append(row)
        print(f"Fold {fold.number}: {len(query)} measured comparison rows", flush=True)
    rows = pd.concat(predictions, ignore_index=True)
    folds = pd.DataFrame(
        [
            {"model": name, "fold": number, **score(frame, cfg)}
            for (name, number), frame in rows.groupby(["model", "fold"])
        ]
    )
    summary = pd.DataFrame(
        [{"model": name, **score(frame, cfg)} for name, frame in rows.groupby("model")]
    )
    folds.to_csv(destination / "fold_scores.csv", index=False)
    summary.to_csv(destination / "summary.csv", index=False)
    stratified_scores(rows, cfg).to_csv(destination / "stratified.csv", index=False)
    gate_cfg = copy.deepcopy(cfg)
    gate_cfg["evaluate"]["veto_tolerance"] = read_json(
        root / "reports/model/veto_tolerances.json", {}
    )
    gates = {name: compare(rows, gate_cfg, challenger=name) for name in names[1:]}
    write_json(
        destination / "selection.json",
        {"frozen_candidate": selected, "diagnostic_gates": gates, "production_approved": False},
    )
    prediction_path = root / "data/interim/refinement_predictions.parquet"
    rows.to_parquet(prediction_path, index=False)
    track(root, prediction_path)
    paths = [
        "src/models/history.py",
        "scripts/refine_model.py",
        "config/config.yaml",
        "reports/research_protocol.json",
        "data/interim/model_predictions.parquet.dvc",
        "data/interim/refinement_predictions.parquet.dvc",
    ]
    write_json(
        destination / "manifest.json",
        {
            "sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
            "holdout_evaluated": False,
            "production_approved": False,
            "selection_caveat": "Development comparison; original pretest selection retained in protocol.json.",
        },
    )
    print(folds.groupby("model")[["mase", "rmsse", "mape_pct"]].mean().to_string(), flush=True)
    write_json(destination / "adaptive_choices.json", choices)
    print("Pre-test selection:", selected, validation, flush=True)


if __name__ == "__main__":
    main()
