"""One final holdout evaluation after development artifacts are complete."""

import pathlib
import sys
from dataclasses import replace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.backtest.run import evaluate, load_cached, write_report
from src.backtest.splits import Fold, research_plan
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.jobs.daily import read_json
from src.records import pins, track, write_json
from src.tracking import log_run


def main():
    root, cfg = PROJECT_ROOT, load_config()
    marker = root / "reports/holdout/evaluation.json"
    if marker.exists():
        raise SystemExit(
            "Holdout already evaluated; use the saved report. No repeated selection on holdout."
        )
    decision = read_json(
        root / "reports/calibration/selection.json",
        read_json(root / "reports/model/selection.json", {}),
    )
    if not decision.get("promote", False):
        raise SystemExit(
            "Development model gate failed or is incomplete; final holdout stays reserved."
        )
    for path in [
        "reports/model.md",
        "reports/ablation.md",
        "reports/threshold_derivation.md",
        "docs/index.html",
    ]:
        if not (root / path).exists():
            raise SystemExit(f"development incomplete: {path}")
    demand, weather = load_cached(root, cfg)
    original = research_plan(root, build_features(weather, cfg, demand=demand), cfg)
    folds = []
    for i in range(cfg["splits"]["holdout_months"]):
        start = original.holdout_start.tz_convert(cfg["project"]["timezone"]) + pd.DateOffset(
            months=i
        )
        issue = start - pd.Timedelta(days=1) + pd.Timedelta(hours=cfg["backtest"]["issue_hour_ist"])
        end = issue - pd.Timedelta(days=cfg["splits"]["purge_gap_days"])
        folds.append(
            Fold(
                i + 1,
                original.folds[0].train_start,
                end.tz_convert("UTC"),
                (end - pd.Timedelta(weeks=cfg["splits"]["early_stopping_weeks"])).tz_convert("UTC"),
                start.tz_convert("UTC"),
                (start + pd.DateOffset(months=1)).tz_convert("UTC"),
            )
        )
    plan = replace(original, folds=tuple(folds), holdout_start=original.holdout_end)
    cfg["backtest"].update(
        report_path="reports/holdout.md",
        results_dir="reports/holdout",
        predictions_path="data/interim/holdout_predictions.parquet",
    )
    result = evaluate(demand, weather, cfg, hybrid=True, plan=plan)
    report = write_report(result, cfg, root)
    write_json(
        marker,
        {
            "pins": pins(root, cfg),
            "start": str(original.holdout_start),
            "end": str(original.holdout_end),
            "protocol": "frozen parameters; monthly expanding refits; evaluated once",
            "report": str(report.relative_to(root)),
        },
    )
    track(root, root / cfg["backtest"]["predictions_path"])
    metrics = (
        result["fold_scores"]
        .loc[lambda x: x.model == "hybrid"][["mase", "rmsse", "mape_pct"]]
        .mean()
        .to_dict()
    )
    log_run(
        root,
        cfg,
        "final-holdout",
        metrics,
        [marker, report],
        root / cfg["backtest"]["predictions_path"],
    )


if __name__ == "__main__":
    main()
