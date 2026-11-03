"""Select and freeze parameters using measured targets before the first fold."""

import copy
import pathlib
import sqlite3
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import optuna
import pandas as pd

from src.backtest.run import load_cached
from src.backtest.splits import issue_times, measured_mask, research_plan
from src.config import PROJECT_ROOT, load_config, update_values
from src.features.build import build_features, trainable_mask
from src.features.forecast_noise import simulate_forecast_weather
from src.models.baselines import SeasonalNaive
from src.models.hybrid import Hybrid
from src.records import track, write_json
from src.tracking import log_run


def main():
    root, cfg = PROJECT_ROOT, load_config()
    demand, weather = load_cached(root, cfg)
    weather = weather.dropna(subset=["temperature_2m"])
    base = build_features(weather, cfg, demand=demand).dropna(
        subset=["temperature", "cooling_degrees"]
    )
    plan = research_plan(root, base, cfg)
    end = plan.folds[0].train_end
    start = end - pd.DateOffset(months=cfg["tuning"]["measured_validation_months"])
    train_end = start - pd.Timedelta(days=cfg["splits"]["purge_gap_days"] + 1)
    weather = weather.loc[weather.datetime_utc < end]
    noisy = simulate_forecast_weather(weather, cfg, stream=0)
    demand = demand.loc[demand.datetime_utc < end]
    eligible_targets = base.loc[trainable_mask(base, cfg) & (base.datetime_utc < train_end)]
    measured = base.loc[
        (base.datetime_utc >= start) & (base.datetime_utc < end) & measured_mask(base)
    ].copy()
    if measured.empty:
        raise ValueError("no measured targets before the first fold; tuning is impossible")
    measured["issued_at"] = issue_times(measured.datetime_utc, cfg)
    naive = (
        SeasonalNaive(cfg).fit(base.loc[base.datetime_utc < end]).predict(measured).prediction_mw
    )
    measured = measured.loc[np.isfinite(naive)].copy()
    denominator = np.abs(measured.demand_mw - naive.loc[measured.index]).sum()
    search = cfg["tuning"]["search"]
    started = time.monotonic()
    budget = cfg["tuning"]["budget_seconds"]

    def objective(trial):
        local = copy.deepcopy(cfg)
        local["train"]["recency_half_life_days"] = trial.suggest_int(
            "recency_half_life_days", *search["recency_half_life_days"]
        )
        local["features"]["temp_breakpoint_c"] = trial.suggest_float(
            "temp_breakpoint_c", *search["temp_breakpoint_c"]
        )
        local["train"]["ridge"]["alpha"] = trial.suggest_float("alpha", *search["alpha"], log=True)
        for key in local["train"]["lightgbm"]:
            bounds = search[key]
            local["train"]["lightgbm"][key] = (
                trial.suggest_int(key, *bounds)
                if key in ["num_leaves", "min_data_in_leaf"]
                else trial.suggest_float(
                    key, *bounds, log=key in ["learning_rate", "lambda_l1", "lambda_l2"]
                )
            )
        train = build_features(noisy, local, demand=eligible_targets)
        test = build_features(noisy, local).merge(
            measured[["zone", "datetime_utc", "demand_mw"]],
            on=["zone", "datetime_utc"],
            validate="one_to_one",
        )
        model = Hybrid(local).fit(train, train_end=train_end)
        trial.set_user_attr("best_iteration", model.best_iteration)
        trial.set_user_attr("refit_iterations", model.iterations)
        prediction = model.predict(test)
        if not np.isfinite(prediction).all():
            raise ValueError("tuning prediction unavailable")
        return float(np.abs(prediction - test.demand_mw).sum() / denominator)

    out = root / "reports/tuning"
    out.mkdir(parents=True, exist_ok=True)
    study = optuna.create_study(
        direction="minimize",
        sampler=optuna.samplers.TPESampler(seed=cfg["train"]["seed"]),
        storage=f"sqlite:///{out / 'study.sqlite3'}",
    )
    study.optimize(objective, n_trials=1)
    first_seconds = time.monotonic() - started
    trial_limit = min(cfg["tuning"]["n_trials"], max(1, int(budget / (first_seconds * 1.5))))
    study.optimize(objective, n_trials=trial_limit - 1, timeout=max(0, budget - first_seconds * 2))
    backup_path = root / "data/interim/tuning_study.sqlite3"
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(out / "study.sqlite3") as source_db,
        sqlite3.connect(backup_path) as backup_db,
    ):
        source_db.backup(backup_db)
    track(root, backup_path)
    selected = study.best_params
    bound_parameters = [k for k, v in selected.items() if v in search[k]]
    if bound_parameters:
        study.trials_dataframe().to_csv(out / "trials.csv", index=False)
        write_json(
            out / "not_identified.json",
            {
                "status": "NOT IDENTIFIED",
                "parameters_at_bound": bound_parameters,
                "selected": selected,
                "best_mase": study.best_value,
            },
        )
        raise SystemExit(
            "Search winner is at a boundary; widen the search before freezing parameters."
        )
    updates = {
        "train.recency_half_life_days": selected["recency_half_life_days"],
        "features.temp_breakpoint_c": selected["temp_breakpoint_c"],
        "train.ridge.alpha": selected["alpha"],
    }
    updates.update({f"train.lightgbm.{k}": selected[k] for k in cfg["train"]["lightgbm"]})
    updates["tuning.n_trials"] = trial_limit
    update_values(updates)
    report = {
        "protocol": "measured validation before first fold; earliest reserved year has no measured targets",
        "validation_start": str(start),
        "validation_end": str(end),
        "train_end": str(train_end),
        "zones": sorted(measured.zone.unique().tolist()),
        "n_rows": len(measured),
        "first_trial_seconds": first_seconds,
        "trial_limit": trial_limit,
        "trials_completed": len(study.trials),
        "seconds": time.monotonic() - started,
        "best_mase": study.best_value,
        "selected": selected,
        "bound_parameters": bound_parameters,
    }
    write_json(out / "result.json", report)
    study.trials_dataframe().to_csv(out / "trials.csv", index=False)
    frozen = load_config()
    matrix = root / "data/interim/tuning_training.parquet"
    build_features(noisy, frozen, demand=eligible_targets).to_parquet(matrix, index=False)
    track(root, matrix)
    log_run(
        root,
        frozen,
        "tuning",
        {"best_mase": study.best_value, "trials": len(study.trials)},
        [out / "result.json"],
        matrix,
    )
    print("Frozen parameters and tuning audit: reports/tuning/result.json")


if __name__ == "__main__":
    main()
