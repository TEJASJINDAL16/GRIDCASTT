"""Baseline-only walk-forward evaluation and its reproducible report."""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import platform
from dataclasses import asdict
from datetime import UTC, datetime

import numpy as np
import pandas as pd
import sklearn

from src.backtest.metrics import score, stratified_scores
from src.backtest.splits import issue_times, make_splits, measured_mask
from src.config import get
from src.features.build import build_features, trainable_mask
from src.features.forecast_noise import simulate_forecast_weather
from src.models.baselines import BASELINE_NAMES, HourWeekdayMean, RidgeBaseline, SeasonalNaive
from src.validate import validate_demand, validate_weather

log = logging.getLogger(__name__)


def load_cached(root: pathlib.Path, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the local cache only; evaluation never calls a live API."""
    demand, weather = [], []
    for zone in get(cfg, "demand.all_zones"):
        for name, destination in [("demand", demand), ("weather", weather)]:
            path = root / "data" / "raw" / f"{name}_{zone}.parquet"
            if not path.exists():
                raise FileNotFoundError(f"missing cached input {path}; restore it with dvc pull")
            data = pd.read_parquet(path)
            if name == "demand":
                validate_demand(data, zone, cfg)
            else:
                validate_weather(data, zone, cfg, contiguous=False)
            destination.append(data)
    # Current best-known targets: revision files are observed-time ordered.
    for path in sorted((root / get(cfg, "archive.revision_dir")).glob("*.parquet")):
        demand.append(pd.read_parquet(path).sort_values("observed_at"))
    d = pd.concat(demand, ignore_index=True).drop_duplicates(["zone", "datetime_utc"], keep="last")
    w = pd.concat(weather, ignore_index=True)
    if w.duplicated(["zone", "point_name", "datetime_utc"]).any():
        raise ValueError("duplicate weather rows in cache")
    for zone in get(cfg, "demand.all_zones"):
        validate_demand(d.loc[d.zone == zone], zone, cfg)
    return d, w


def evaluate(demand: pd.DataFrame, weather: pd.DataFrame, cfg: dict) -> dict:
    """Fit once per fold. Daily issue times constrain every naive lookup."""
    if not get(cfg, "forecast_noise.enabled"):
        raise ValueError("baseline evaluation requires the simulated forecast bridge, not perfect weather")
    weather = weather.dropna(subset=["temperature_2m"])
    base = build_features(weather, cfg, demand=demand)
    base = base.dropna(subset=["temperature", "cooling_degrees"])
    plan = make_splits(base, cfg)
    development = base.loc[base.datetime_utc < plan.holdout_start].copy()
    naive = SeasonalNaive(cfg).fit(development)
    predictions, fold_scores, coverage = [], [], []
    for fold in plan.folds:
        train_raw = development.loc[(development.datetime_utc >= fold.train_start)
                                    & (development.datetime_utc < fold.train_end)].reset_index(drop=True)
        allowed = trainable_mask(train_raw, cfg)
        train_targets = train_raw.loc[allowed]
        raw_train_weather = weather.loc[(weather.datetime_utc >= fold.train_start)
                                       & (weather.datetime_utc < fold.train_end)].reset_index(drop=True)
        noisy_train = simulate_forecast_weather(raw_train_weather, cfg, stream=fold.number * 2)
        train = build_features(noisy_train, cfg, demand=train_targets)
        test_actual = development.loc[(development.datetime_utc >= fold.test_start)
                                      & (development.datetime_utc < fold.test_end)].reset_index(drop=True)
        raw_test_weather = weather.loc[(weather.datetime_utc >= fold.test_start)
                                      & (weather.datetime_utc < fold.test_end)].reset_index(drop=True)
        noisy_test = simulate_forecast_weather(raw_test_weather, cfg, stream=fold.number * 2 + 1)
        serving = build_features(noisy_test, cfg)
        daily_counts = serving.groupby(["zone", "date_ist"], observed=True).datetime_utc.transform("nunique")
        serving = serving.loc[daily_counts == 24].reset_index(drop=True)
        # Actuals are attached only AFTER serving features have been built.
        actual_cols = ["datetime_utc", "zone", "demand_mw", "is_estimated", "temperature"]
        serving = serving.merge(test_actual[actual_cols].rename(columns={"temperature": "observed_temperature"}),
                                on=["datetime_utc", "zone"], how="left", validate="one_to_one")
        serving["issued_at"] = issue_times(serving.datetime_utc, cfg)
        serving["lead_time_hours"] = (serving.datetime_utc - serving.issued_at).dt.total_seconds() / 3600
        naive_output = naive.predict(serving)
        fitted = [HourWeekdayMean().fit(train),
                  RidgeBaseline(cfg).fit(train, train_end=fold.train_end),
                  RidgeBaseline(cfg, per_zone=True).fit(train, train_end=fold.train_end)]
        wide = pd.DataFrame({"seasonal_naive": naive_output.prediction_mw,
                             **{name: model.predict(serving) for name, model in zip(BASELINE_NAMES[1:], fitted, strict=True)}})
        measured = measured_mask(serving)
        common = measured & np.isfinite(wide).all(axis=1)
        audit = serving.loc[common].copy()
        audit["fold"] = fold.number
        audit["row_id"] = (fold.number * (len(base) + 1) + audit.index).astype("int64")
        audit["baseline_mw"] = wide.loc[common, "seasonal_naive"]
        audit["baseline_source_datetime"] = naive_output.loc[common, "source_datetime"]
        audit["weather_source"] = "simulated_forecast_bridge"
        audit["flags"] = [["placeholder_in_use"] for _ in range(len(audit))]
        if (audit.baseline_source_datetime > audit.issued_at - pd.Timedelta(days=get(cfg, "splits.purge_gap_days"))).any():
            raise AssertionError("seasonal baseline saw unsettled history")
        for name in BASELINE_NAMES:
            rows = audit.copy()
            rows["model"] = name
            rows["prediction_mw"] = wide.loc[common, name]
            predictions.append(rows)
            fold_scores.append({"fold": fold.number, "model": name, **score(rows, cfg)})
        expected = int((fold.test_end - fold.test_start) / pd.Timedelta(hours=1)) * len(get(cfg, "demand.all_zones"))
        gap_fraction = (expected - len(test_actual)) / expected
        detail = {"fold": fold.number, "test_start": fold.test_start.isoformat(),
                  "test_end": fold.test_end.isoformat(), "train_end": fold.train_end.isoformat(),
                  "training_zones": sorted(train.zone.unique().tolist()), "n_train": len(train),
                  "n_excluded_training": int((~allowed).sum()), "n_expected": expected,
                  "n_forecast": len(serving), "cache_gap_fraction": gap_fraction,
                  "fold_status": "unreliable: cache gaps" if gap_fraction > get(cfg, "failure.max_gap_fraction") else "cache coverage reliable",
                  "n_measured": int(measured.sum()), "n_common": int(common.sum()),
                  "n_measured_without_comparison": int((measured & ~common).sum())}
        for name in BASELINE_NAMES:
            detail[f"n_available_{name}"] = int((measured & np.isfinite(wide[name])).sum())
        coverage.append(detail)
        log.info("fold %02d: %s, train=%d measured=%d compared=%d", fold.number,
                 fold.test_start.tz_convert(get(cfg, "project.timezone")).date(), len(train),
                 measured.sum(), common.sum())
    combined = pd.concat(predictions, ignore_index=True)
    if not len(combined):
        raise ValueError("no common measured baseline evaluation rows")
    return {"plan": plan, "predictions": combined, "fold_scores": pd.DataFrame(fold_scores),
            "coverage": pd.DataFrame(coverage)}


REPORT_COLUMNS = ["model", "n_rows", "mape_pct", "baseline_mape_pct", "mase", "rmsse",
                  "signed_bias_pct", "shortfall_freq_pct", "p95_abs_pct"]


def _table(frame: pd.DataFrame, columns: list[str]) -> str:
    visible = frame[columns].copy()
    if "status" in frame:
        insufficient = frame.status != "reportable"
        for column in columns:
            if column.endswith(("_pct", "_mw")) or column in ["mase", "rmsse", "ramp_mase"]:
                visible[column] = visible[column].astype("object")
                visible.loc[insufficient, column] = "not reportable"
    return visible.fillna("undefined").to_markdown(index=False, floatfmt=".3f")


def write_report(result: dict, cfg: dict, root: pathlib.Path) -> pathlib.Path:
    out = root / get(cfg, "backtest.results_dir")
    out.mkdir(parents=True, exist_ok=True)
    rows, folds, coverage, plan = (result[k] for k in ["predictions", "fold_scores", "coverage", "plan"])
    summary = pd.DataFrame([{"model": name, **score(rows.loc[rows.model == name], cfg)}
                            for name in BASELINE_NAMES])
    strata = stratified_scores(rows, cfg)
    for name, data in [("summary", summary), ("fold_scores", folds), ("coverage", coverage), ("stratified", strata)]:
        data.to_csv(out / f"{name}.csv", index=False)
    prediction_path = root / get(cfg, "backtest.predictions_path")
    prediction_path.parent.mkdir(parents=True, exist_ok=True)
    rows.to_parquet(prediction_path, index=False)
    hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((root / "data/raw").rglob("*.dvc"))}
    source_paths = [*sorted((root / "src").rglob("*.py")), root / "scripts/backtest_baselines.py",
                    root / "config/config.yaml"]
    source_hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in source_paths}
    input_paths = [root / "data/raw" / f"{kind}_{zone}.parquet"
                   for kind in ["demand", "weather"] for zone in get(cfg, "demand.all_zones")]
    input_paths.extend(sorted((root / get(cfg, "archive.revision_dir")).glob("*.parquet")))
    input_hashes = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in input_paths if p.exists()}
    manifest = {"generated_at": datetime.now(UTC).isoformat(), "seed": get(cfg, "train.seed"),
                "versions": {"python": platform.python_version(), "pandas": pd.__version__,
                             "numpy": np.__version__, "sklearn": sklearn.__version__},
                "split_plan": asdict(plan), "input_dvc_pointer_sha256": hashes,
                "input_parquet_sha256": input_hashes,
                "source_sha256": source_hashes, "weather_source": "constant-sigma simulated forecast bridge",
                "holdout_scored": False}
    (out / "manifest.json").write_text(json.dumps(manifest, default=str, indent=2) + "\n", encoding="utf-8")
    baseline = summary.loc[summary.model == "seasonal_naive"].iloc[0]
    mean_folds = folds.groupby("model", sort=False)[["mape_pct", "mase", "rmsse"]].mean().reset_index()
    lead = strata.loc[strata.dimension == "lead_time_hours"]
    lead_min, lead_max = rows.lead_time_hours.min(), rows.lead_time_hours.max()
    lead_diagnostics = []
    for name in BASELINE_NAMES:
        values = lead.loc[lead.model == name].sort_values("segment", key=lambda s: s.astype(float))
        errors = values.mape_pct.to_numpy()
        lead_diagnostics.append({"model": name, "first_lead_mape_pct": errors[0],
                                 "last_lead_mape_pct": errors[-1],
                                 "nondecreasing_steps": int((np.diff(errors) >= 0).sum()),
                                 "total_steps": len(errors) - 1})
    start = plan.folds[0].test_start.tz_convert(get(cfg, "project.timezone")).date()
    end = plan.holdout_start.tz_convert(get(cfg, "project.timezone")).date()
    text = ["# Stage 2: Features and Baseline", "",
            f"Generated {manifest['generated_at']}. Reproduce: `make baseline` (cached data only).", "",
            f"**Number to beat: seasonal-naive MAPE {baseline.mape_pct:.3f}% over {int(baseline.n_rows):,} common measured rows.** "
            "Its out-of-sample MASE and RMSSE are 1.000. The Stage 3 selection criterion is mean fold MASE, with RMSSE co-primary; "
            "the pooled MAPE above is descriptive, not a final holdout result.", "",
            "## Protocol and Limits", "",
            f"{len(plan.folds)} monthly expanding folds: {start} up to {end} (exclusive), IST calendar boundaries. "
            f"The final holdout is {end} through {plan.holdout_end.tz_convert(get(cfg, 'project.timezone')).date()} "
            "(exclusive), and was not scored. A partial newest month is excluded from the split anchor. "
            f"Reserved tuning window: {plan.tuning_start.tz_convert(get(cfg, 'project.timezone')).date()} "
            f"through {plan.tuning_end.tz_convert(get(cfg, 'project.timezone')).date()} (exclusive), IST. "
            "No tuning was run and production hyperparameters remain null.", "",
            "Earlier exploratory analyses examined the full cached history. The holdout is reserved "
            "from this baseline loop; a later final accuracy claim must disclose that earlier exploration "
            "rather than describing the dataset as completely unseen throughout the project.", "",
            "Each learned baseline is fitted once per fold. Training ends at least ten days before the first issue, "
            "slightly earlier than a ten-day gap from the test boundary. The ten-day settlement gap is an unmeasured assumption. "
            "Daily issue time is 10:00 IST on the preceding date. UTC hourly targets map to IST 00:30-23:30, "
            f"with exact leads {lead_min:g}-{lead_max:g} hours. No target interpolation or recursive prediction is used.", "",
            "The seasonal baseline uses the latest measured same-zone/hour/weekday value at least ten days before each "
            "daily issue; it can use eligible history accumulated within a fold. Historical means are per zone/hour/weekday. "
            "Ridge-all and per-zone Ridge use identical engineered features, categorical hour/weekday/zone encodings, "
            f"log targets, fixed alpha={get(cfg, 'baselines.ridge_alpha')}, configured recency weights, and per-zone "
            "Duan smearing estimated on training residuals. These parameters were not selected using test-fold performance.", "",
            "Weather inputs use the configured constant-sigma simulation bridge: per-city/IST-day Gaussian bias "
            f"sigma={get(cfg, 'forecast_noise.day_bias_sigma_c')} C plus hourly wobble "
            f"sigma={get(cfg, 'forecast_noise.hour_wobble_sigma_c')} C. Noise is applied to raw temperature before "
            "cooling-degree transforms in both training and simulated serving. These are assumptions, not measured forecast errors. "
            "This benchmark does not claim historical point-in-time weather accuracy. Recovered forecasts have uncertain "
            "intra-day issue times and are not silently treated as exact 10:00 IST vintages.", "",
            "**Data-generating-process caveat:** folds straddle the MODE_BREAKDOWN-to-measured transition. "
            "Only measured targets are scored, while training allows measured plus MODE_BREAKDOWN. "
            "Early folds consequently score fewer zones. IN-NE has no eligible training history at its first measured "
            "fold; learned models abstain there. All four reported baseline scores use the same measured rows with finite "
            "predictions from every baseline. Expected, measured and excluded rows are reported below. "
            "Incomplete weather days are skipped for that zone; missing actuals are not scored. "
            "A fold above failure.max_gap_fraction is marked unreliable rather than silently removed. "
            "The demand archive contains current revised values; the assumed purge is not a complete historical revision replay.", "",
            "All otherwise eligible observations are retained, including hot hours with sustained demand drops. "
            "No heuristic infers a cause or removes records based on temperature and demand residuals. "
            "Manual festival extensions remain incomplete, and cyclic day-of-year remains an ablation candidate.", "",
            "## Overall Comparison", "", _table(summary, REPORT_COLUMNS), "",
            "Percentage metrics are expressed in percent. MASE=sum(abs(error))/sum(abs(seasonal error)); "
            "RMSSE=sqrt(sum(error^2)/sum(seasonal error^2)), the out-of-sample variants on identical rows. "
            "Zero denominators are undefined, never coerced to zero. Lower is better except signed bias, whose sign "
            "states over/under forecast. Shortfall counts misses below the configured -3% threshold.", "",
            "## Mean Across Folds", "", _table(mean_folds, ["model", "mape_pct", "mase", "rmsse"]), "",
            "## Physical, Peak and Ramp Errors", "",
            _table(summary, ["model", "n_rows", "mae_mw", "rmse_mw", "rmse_mae_ratio", "n_peak_days", "peak_mae_mw", "baseline_peak_mae_mw", "peak_mape_pct", "n_ramps", "ramp_mae_mw", "baseline_ramp_mae_mw", "ramp_mase"]), "",
            "Peak errors use each complete measured zone/day's actual maximum. Incomplete days are excluded "
            "from peak metrics. Ramps compare consecutive hourly deltas within the same fold/zone/day during "
            "the configured IST evening window; they never bridge missing hours or folds. "
            "Pooled MW errors reflect zone magnitude; use per-zone scores below for comparison.", "",
            "## Fold Coverage", "", _table(coverage, list(coverage.columns)), "",
            "## Every Fold", "", _table(folds, ["fold", *REPORT_COLUMNS]), ""]
    for dimension in strata.dimension.unique():
        section = strata.loc[strata.dimension == dimension]
        text.extend([f"## Stratification: {dimension}", "",
                     _table(section, ["segment", "status", *REPORT_COLUMNS]), ""])
    text.extend(["## Lead-Time Investigation", "", pd.DataFrame(lead_diagnostics).to_markdown(index=False, floatfmt=".3f"), "",
                 "Error is not guaranteed to rise monotonically across these leads. This was treated as a suspected "
                 "leak and checked: (1) the saved seasonal source timestamps satisfy the issue-minus-purge cutoff; "
                 "(2) fold training ends before the first issue's cutoff; (3) serving features "
                 "are built without demand, and the target is attached only for scoring; (4) no holdout rows are scored. "
                 "Tests exercise these boundaries, including future-target perturbations. No future-demand input "
                 "was found in those paths.", "",
                 "Two confounders remain: lead time maps one-to-one to hour of day in a fixed daily forecast, "
                 "and the deliberately simple weather-noise bridge has constant sigma, so it cannot reproduce "
                 "lead-dependent weather forecast degradation. Calendar-only baselines do not consume weather at all. "
                 "This investigation permits the Stage 2 benchmark to be recorded, but does not establish production "
                 "forecast skill or validate the assumed sigmas. Recheck with exact captured vintages when coverage permits; "
                 "do not force a rising curve by selecting noise or parameters from these test results.", "",
                 "## Reproducibility", "",
                 "Machine-readable fold, coverage, summary and stratified tables are in `reports/baseline/`. "
                 "All metrics, including the full peak/ramp diagnostics for each stratum, are in stratified.csv. "
                 "Predictions and issue/source timestamps are in the DVC-tracked `data/interim/baseline_predictions.parquet`. "
                 "manifest.json records actual input-file and pointer hashes, source/config hashes, runtime versions, seed and split boundaries. "
                 "Temperature bands use observed temperatures for analysis only; sparse interior bands are merged, "
                 "the hottest band stays separate, and segments below the sufficiency threshold are marked "
                 "insufficient rather than quoted as performance. Absent zone/band cells remain absent.", ""])
    path = root / get(cfg, "backtest.report_path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(text), encoding="utf-8")
    return path
