"""Full metrics for the frozen two-observation demand-history candidate."""

import argparse
import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from src.backtest.metrics import score, stratified_scores
from src.backtest.run import load_cached
from src.backtest.splits import issue_times, measured_mask, research_plan
from src.config import PROJECT_ROOT, load_config
from src.features.build import build_features
from src.jobs.daily import read_json
from src.models.baselines import SeasonalNaive
from src.models.history import SeasonalAverage
from src.monitor.registry import compare
from src.records import track, write_json

CANDIDATE = "history_mean_2"


def tables(rows, cfg, destination):
    destination.mkdir(parents=True, exist_ok=True)
    summary = pd.DataFrame(
        [{"model": name, **score(frame, cfg)} for name, frame in rows.groupby("model")]
    )
    folds = pd.DataFrame(
        [
            {"model": name, "fold": number, **score(frame, cfg)}
            for (name, number), frame in rows.groupby(["model", "fold"])
        ]
    )
    summary.to_csv(destination / "summary.csv", index=False)
    folds.to_csv(destination / "fold_scores.csv", index=False)
    stratified = stratified_scores(rows, cfg)
    stratified.to_csv(destination / "stratified.csv", index=False)
    for name in [
        "zone",
        "temperature_band",
        "hour_of_day",
        "day_type",
        "lead_time_hours",
        "zone_temperature_band",
        "time_rolling",
    ]:
        stratified.loc[stratified.dimension == name].to_csv(
            destination / f"{name}.csv", index=False
        )
    decision = compare(rows, cfg, challenger=CANDIDATE)
    write_json(destination / "comparison.json", decision)
    columns = [
        "model",
        "n_rows",
        "mape_pct",
        "mae_mw",
        "rmse_mw",
        "mase",
        "rmsse",
        "signed_bias_pct",
        "shortfall_freq_pct",
        "p95_abs_pct",
        "n_peak_days",
        "peak_mae_mw",
        "n_ramps",
        "ramp_mae_mw",
        "ramp_mase",
    ]
    zone = stratified.loc[stratified.dimension == "zone", ["segment", *columns]]
    text = "# Frozen demand-history model evaluation\n\n"
    text += (
        "Final reserved-year evaluation. The candidate was fixed before scoring.\n\n"
        if destination.name == "holdout_history"
        else "Development metrics; model selection has examined this period.\n\n"
    )
    text += "The candidate averages the latest two eligible same-zone, IST-hour and weekday measured values at least ten days before issue. It falls back to one when only one exists. No demand from after the issue cutoff enters the predictor.\n\n"
    text += (
        "## Overall metrics\n\n"
        + summary[columns].to_markdown(index=False, floatfmt=".4f")
        + "\n\n"
    )
    text += (
        "## Mean of monthly scores\n\n"
        + folds.groupby("model")[["mase", "rmsse", "mape_pct"]].mean().to_markdown(floatfmt=".4f")
        + "\n\n"
    )
    text += "## Regional metrics\n\n" + zone.to_markdown(index=False, floatfmt=".4f") + "\n\n"
    text += (
        "## Monthly metrics\n\n"
        + folds[["fold", *columns]].to_markdown(index=False, floatfmt=".4f")
        + "\n\n"
    )
    text += "## Interpretation and limits\n\nLower is better for errors; signed bias is positive for overforecast and negative for underforecast. Shortfall frequency counts forecasts more than the configured 3% below actual demand. MASE and RMSSE use the out-of-sample seasonal baseline denominator on identical rows. Mean-month and pooled metrics use different weighting. Peak metrics require complete measured zone-days; ramps never bridge missing hours. CSV breakdowns include sample counts, and sparse temperature bands are explicitly marked insufficient.\n\n"
    text += "The demand availability gap remains an assumption; revised historical values do not recreate the original publication state. Historical analyses have previously explored the cached dataset; this year was reserved from forecast selection, not completely unseen throughout the project. This candidate uses no forecast weather values; temperature is observed analysis context only. No production champion is approved by this report. Demand-dependent serving, monitor recalibration, deployment and live acceptance remain separate requirements.\n\n"
    text += (
        "Diagnostic comparison result: "
        + ("PASS" if decision["promote"] else "FAIL")
        + ". Reasons: "
        + str(decision["reasons"])
        + ".\n"
    )
    (destination / "report.md").write_text(text, encoding="utf-8")
    return summary, decision


def final_holdout(root, cfg):
    marker = root / "reports/holdout/evaluation.json"
    if marker.exists():
        print("Holdout already claimed/evaluated. Use the saved report; it will not be rescored.")
        return
    development = read_json(root / "reports/refinement/selection.json", {})
    if not development.get("diagnostic_gates", {}).get(CANDIDATE, {}).get("promote"):
        raise ValueError("The fixed history candidate must pass its development comparison")
    protocol = {
        "candidate": CANDIDATE,
        "window": 2,
        "frozen_at": datetime.now(UTC).isoformat(),
        "status": "started",
        "holdout_evaluated": False,
        "selection_disclosure": "Two-observation candidate selected after examining development folds; early Eastern-only validation preferred four.",
        "purge_gap_days": cfg["splits"]["purge_gap_days"],
        "source_sha256": {
            p: hashlib.sha256((root / p).read_bytes()).hexdigest()
            for p in ["src/models/history.py", "scripts/evaluate_history.py", "config/config.yaml"]
        },
    }
    marker.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive claim before any reserved-period target is scored.
    with marker.open("x", encoding="utf-8") as stream:
        json.dump(protocol, stream, indent=2)
    demand, weather = load_cached(root, cfg)
    history = build_features(weather, cfg, demand=demand)
    plan = research_plan(root, history, cfg)
    history = history.loc[history.datetime_utc < plan.holdout_end]
    queries = (
        history.loc[
            (history.datetime_utc >= plan.holdout_start) & (history.datetime_utc < plan.holdout_end)
        ]
        .copy()
        .reset_index(drop=True)
    )
    queries["issued_at"] = issue_times(queries.datetime_utc, cfg)
    queries["lead_time_hours"] = (
        queries.datetime_utc - queries.issued_at
    ).dt.total_seconds() / 3600
    queries["observed_temperature"] = queries.temperature
    queries["fold"] = (
        (
            queries.datetime_ist.dt.year
            - plan.holdout_start.tz_convert(cfg["project"]["timezone"]).year
        )
        * 12
        + queries.datetime_ist.dt.month
        - plan.holdout_start.tz_convert(cfg["project"]["timezone"]).month
        + 1
    )
    queries["row_id"] = np.arange(len(queries))
    naive = SeasonalNaive(cfg).fit(history).predict(queries)
    candidate = SeasonalAverage(cfg, window=2).fit(history).predict(queries)
    if not naive.source_datetime.equals(candidate.source_datetime):
        raise ValueError("Candidate and baseline disagree on their latest available source")
    common = (
        measured_mask(queries)
        & np.isfinite(naive.prediction_mw)
        & np.isfinite(candidate.prediction_mw)
    )
    count = queries.groupby(["zone", "date_ist"], observed=True).datetime_utc.transform("nunique")
    common &= count.eq(24)
    queries["baseline_mw"] = naive.prediction_mw
    predictions = []
    for name, values in [
        ("seasonal_naive", naive.prediction_mw),
        (CANDIDATE, candidate.prediction_mw),
    ]:
        rows = queries.loc[common].copy()
        rows["model"], rows["prediction_mw"] = name, values.loc[common]
        rows["history_source_datetime"] = candidate.source_datetime.loc[common]
        predictions.append(rows)
    combined = pd.concat(predictions, ignore_index=True)
    out = root / "reports/holdout_history"
    summary, decision = tables(combined, cfg, out)
    artifact = root / "data/interim/holdout_history_predictions.parquet"
    combined.to_parquet(artifact, index=False)
    track(root, artifact)
    coverage = {
        "start": str(plan.holdout_start),
        "end_exclusive": str(plan.holdout_end),
        "expected_rows": int((plan.holdout_end - plan.holdout_start) / pd.Timedelta(hours=1))
        * len(cfg["demand"]["all_zones"]),
        "available_feature_rows": len(queries),
        "measured_common_rows": int(common.sum()),
        "unmeasured_rows": int((~measured_mask(queries)).sum()),
        "missing_history_rows": int(
            (naive.prediction_mw.isna() | candidate.prediction_mw.isna()).sum()
        ),
    }
    write_json(out / "coverage.json", coverage)
    protocol.update(
        status="complete",
        holdout_evaluated=True,
        completed_at=datetime.now(UTC).isoformat(),
        report="reports/holdout_history/report.md",
        coverage=coverage,
        diagnostic_pass=decision["promote"],
        production_approved=False,
    )
    write_json(marker, protocol)
    print(summary.to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--final-holdout", action="store_true")
    args = parser.parse_args()
    root, cfg = PROJECT_ROOT, load_config()
    cfg["evaluate"]["veto_tolerance"] = read_json(root / "reports/model/veto_tolerances.json", {})
    if args.final_holdout:
        final_holdout(root, cfg)
    else:
        rows = pd.read_parquet(root / "data/interim/refinement_predictions.parquet")
        selected = rows.loc[rows.model.isin(["seasonal_naive", CANDIDATE])].copy()
        tables(selected, cfg, root / "reports/refinement_metrics")
        print("Full development metrics written to reports/refinement_metrics/report.md")


if __name__ == "__main__":
    main()
