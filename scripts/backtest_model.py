"""Frozen hybrid versus every baseline on the development folds."""

import copy
import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.backtest.run import evaluate, load_cached, write_report
from src.backtest.splits import research_plan
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.monitor.registry import compare, derive_tolerances
from src.records import track, write_json
from src.tracking import log_run


def model_config(cfg):
    cfg["backtest"].update(
        report_path="reports/model.md",
        results_dir="reports/model",
        predictions_path="data/interim/model_predictions.parquet",
    )
    return cfg


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = model_config(load_config())
    demand, weather = load_cached(PROJECT_ROOT, cfg)
    plan = research_plan(PROJECT_ROOT, build_features(weather, cfg, demand=demand), cfg)
    result = evaluate(demand, weather, cfg, hybrid=True, plan=plan)
    path = write_report(result, cfg, PROJECT_ROOT)
    measured = result["predictions"].loc[lambda f: f.model == "hybrid"]
    tolerances = derive_tolerances(measured, cfg)
    gate_cfg = copy.deepcopy(cfg)
    gate_cfg["evaluate"]["veto_tolerance"] = tolerances
    write_json(PROJECT_ROOT / "reports/model/veto_tolerances.json", tolerances)
    write_json(
        PROJECT_ROOT / "reports/model/selection.json", compare(result["predictions"], gate_cfg)
    )
    track(PROJECT_ROOT, PROJECT_ROOT / cfg["backtest"]["predictions_path"])
    metrics = (
        result["fold_scores"]
        .loc[lambda x: x.model == "hybrid"][["mase", "rmsse", "mape_pct"]]
        .mean()
        .to_dict()
    )
    log_run(
        PROJECT_ROOT,
        cfg,
        "backtest-of-record",
        metrics,
        [path],
        PROJECT_ROOT / cfg["backtest"]["predictions_path"],
    )
    print(metrics)


if __name__ == "__main__":
    main()
