# Execution Handoff — 2026-11-04

Original project: `/Users/tejasjindal/Projects/gridcast-clean`. Implementation and evidence are copied there. The worktree retains the frozen research input snapshot.

The local Phase 1 software is implemented and checked. **The project is not release-complete.** The corrected hybrid fails the required model-quality gate. Holdout evaluation, production bootstrap, GHCR/Pages publication and three real consecutive successful days remain gated. Later quantile/regional experiments have not been substituted for Phase 1.

## What was built and verified

- Validated ingestion, archive capture, gap repair, the shared feature builder and four baselines.
- Pooled Ridge + LightGBM hybrid, recency weighting, chronological early stopping/refit, per-zone smearing and extrapolation flags.
- A 100-trial reserved-window study (45 minutes), frozen parameters, a convergence correction and the twelve-fold backtest of record.
- Seven feature removals, the seasonal candidate, earlier Eastern data, and the reduced estimation-tier comparison, all with counts.
- Complete-hour metrics, immutable scores, late observed-weather context, per-zone routing, watches, episode/cooldown accounting, prospective comparisons and explicit rejection/failure records.
- Locked/idempotent daily execution, recovery/version handling, separate stale-input error reporting and the static seven-block dashboard.
- Workflow files which preserve capture before deployment and on remote failure, prevent unsafe pointer publication and test an image before publishing it.

The real-data offline control produced 120 forecasts across five zones and completed all seven steps. Repeating it was identical. Approval was simulated only in its temporary fixture; no production registry was approved. Local tests: 192 passed, one environment skip. Container tests: 191 passed, two environment skips. Linux reproduced all 60 fold/model comparisons to three decimals and the same rejection decision. The source files and meaningful regression checks are listed below.

## Measured outcomes and release blockers

The corrected hybrid has mean-fold MASE **1.250** and RMSSE **1.247**, against seasonal naive **1.000** for both. On **35,033** common measured rows its MAPE is **14.114%**, versus baseline **11.789%**. Every tested alternative remains above MASE one. The numerical iteration-cap bug is fixed; the failed statistical gate is retained. The final holdout is still unscored, and its command refuses the failed development gate.

The replay selected zero healthy alarm episodes over 365 days (budget two/year), with detection delays 30/23/18 days for injected 2/5/10-percent shifts, excluding settlement lag. The recovery stress case exercised one counterfactual promotion and 28 cooldown days. These replay results are provisionally optimistic because first-settlement history is insufficient. They are not live operational results.

Original-project data now spans 2017 onward: demand through **2026-11-03 18:00 UTC**, measured demand through **2026-11-02 18:00 UTC**, and observed weather through **2026-10-27 23:00 UTC**, with no hourly gaps in that weather span. See data_inventory.md. Forecast captures and revisions are locally DVC-cached; pointer files were updated without Git staging.

The public [November 3 archive job](https://github.com/TEJASJINDAL16/GRIDCASTT/actions/runs/41633363715/job/125908272804) failed at remote configuration and upload (both exit 255). Detailed logs require sign-in. Local Drive authentication independently returns `invalid_grant`; this does not establish the exact configuration-step cause. Renewal/verification of existing Drive credentials and repository secrets is still needed.

AGENTS.md reserves Git/GitHub changes to the owner: “Never stage anything” and “The owner reviews the working tree, stages, commits and pushes.” No Git writes, API calls, token access, repository-setting changes or publication were performed. The public run page was read as HTML. Source fixes are local. Remote DVC upload must succeed before publishing new bulk-data pointers. GitHub Pages, a published image reference and three real successful daily dates have not been claimed.

## Suggested commit groups for the final owner review

1. **Preserve daily capture when Drive configuration or persistence fails.** Archive workflow, deployment readiness preflight, shared capture module/wrapper, catch-up script and Docker context exclusions. Evidence: successful local five-zone capture/repair and public failure annotations.
2. **Implement and evaluate the frozen hybrid with guarded research dates.** Models, features, backtest/splits, tuning, registry, tracking/records, shared charts, configuration, festival extension and their tests. Include the measured failed gate and study/model/ablation evidence. No claim of improved skill.
3. **Add the monitored daily loop and recovery replay.** Drift, jobs, calibration/replay/daily/retry scripts, failure tests and their evidence. The candidate remains unapproved.
4. **Publish the local dashboard, deployment wiring and honest completion audit.** Dashboard, report/card/audit scripts, image/daily/retry workflows, docs, Makefile, README and handoff/protocol evidence. Deployment remains pending.

These are logical groups for one final review; shared integration files must accompany the dependent code. DVC pointers and generated ignore entries belong with their artifacts only after remote upload is verified. No owner-created project file was deleted; superseded capped experiments are retained under `*_initial_capped`. Tool-managed caches and temporary test files are excluded from the inventory.

## Source and configuration inventory

| File | Action | Change |
|---|---|---|
| `.dockerignore` | modify | Exclude local credentials, model binaries and experiment databases from image context. |
| `.github/workflows/archive.yml` | modify | Retain scheduled capture until safe handover; preserve captures on remote failure; strict restore and conditional pointer publication. |
| `.github/workflows/daily.yml` | create | Run the seven-step job in a pinned published image with durable-state and capture fallbacks. |
| `.github/workflows/image.yml` | create | Test an image before GHCR publication and emit its immutable reference. |
| `.github/workflows/retry.yml` | create | Schedule eligible weather retries through the shared workflow. |
| `.gitignore` | modify | Ignore temporary locks/databases and DVC-managed MLflow output. |
| `Makefile` | modify | Expose every research, daily, repair, report and verification entry point. |
| `PLANNING.md` | modify | Record autonomous completion authorization and the measured pre-test tuning amendment. |
| `README.md` | modify | Describe delivered components, measured failed gate, recovery steps, frozen research dates and rejected tools. |
| `config/config.yaml` | modify | Freeze measured tuning parameters, convergence settings and replay-derived monitor/veto values; retain explicit assumptions. |
| `data/external/festivals_in.csv` | modify | Add verified 2024/2025 West Bengal festival dates; preserve unverified-year gaps. |
| `scripts/ablate.py` | create | Measure all feature removals, seasonal candidate and estimation-policy comparisons with row counts. |
| `scripts/archive_daily.py` | modify | Use the reusable capture module and retain the existing archive CLI/status contract. |
| `scripts/audit.py` | create | Report evidence-backed completion and leave unmet quality/deployment gates false. |
| `scripts/backtest_baselines.py` | modify | Reuse protected research dates for the four-comparator benchmark. |
| `scripts/backtest_model.py` | create | Run frozen research comparison and write explicit selection/veto evidence. |
| `scripts/calibrate.py` | create | Sweep episode budgets and genuine detection delays; keep champion watches separate and reject boundary selections. |
| `scripts/catch_up.py` | create | Merge a missing data range without discarding old history; retain actual retrieval timestamps. |
| `scripts/daily.py` | create | Expose the daily/retry/offline command and propagate failures. |
| `scripts/deployment_ready.py` | create | Keep capture active until an approved champion has a valid published image pin. |
| `scripts/diagnose_linear.py` | create | Reproduce a reserved-validation zone-centering diagnostic; no production architecture change. |
| `scripts/holdout.py` | create | Refuse failed/incomplete development gates and repeated final evaluation. |
| `scripts/model_card.py` | create | Publish measured results, per-band limits, actual fitted ranges and remaining assumptions. |
| `scripts/replay.py` | create | Exercise routing, recovery selection and cooldowns on labelled counterfactual real-data replay. |
| `scripts/report.py` | create | Build the static dashboard from stored evidence. |
| `scripts/retry_due.py` | create | Check recorded retry deadlines without installing dependencies. |
| `scripts/train.py` | create | Guard bootstrap against overwriting a champion or using an unevaluated holdout. |
| `scripts/tune.py` | create | Run bounded reserved-window Optuna search, reject boundary winners and save matrix/database snapshots in DVC. |
| `src/backtest/run.py` | modify | Compare hybrid with all baselines; save fitted ranges/counts, same-row metrics and fingerprints. |
| `src/backtest/splits.py` | modify | Persist initial data-derived research boundaries so cache refreshes cannot move the holdout. |
| `src/config.py` | modify | Validate new required settings, atomically update measured YAML values and configure file-backed tracking. |
| `src/features/build.py` | modify | Keep the seven-feature contract and support an explicitly disabled seasonal ablation candidate. |
| `src/ingest/archive.py` | create | Share validated, atomic weather/vintage/revision capture and resume after outages. |
| `src/jobs/daily.py` | create | Implement locked/idempotent daily flow, frozen scores, late weather context, per-zone routing and retry histories. |
| `src/jobs/train.py` | create | Validate training matrices, require prospective comparison and a settlement frontier, preserve champion and record every outcome. |
| `src/models/hybrid.py` | create | Implement weighted Ridge plus LightGBM log residuals, smearing, extrapolation and convergence refusal. |
| `src/monitor/drift.py` | create | Implement complete-hour windows, per-zone/frontier metrics, evidence-aware routing, structural watches and cooldowns. |
| `src/monitor/registry.py` | create | Implement common-cohort MASE/RMSSE/veto decisions and measured fold-spread tolerances. |
| `src/records.py` | create | Write atomic evidence, source/data/settings pins and local DVC pointers. |
| `src/tracking.py` | create | Record local MLflow runs and relocate artifact paths after restoring into another checkout. |
| `src/viz/dashboard.py` | create | Render all dashboard blocks, absent zones, pending actuals, separate stale-input errors and development lead-time evidence. |
| `src/viz/plots.py` | create | Share static SVG chart functions with baselines, counts, pending regions and IST axes. |
| `tests/test_calibration.py` | create | Add regression/invariant coverage for calibration. |
| `tests/test_daily.py` | create | Add regression/invariant coverage for daily. |
| `tests/test_forecast_noise.py` | modify | Check cooling degrees against the tuned breakpoint instead of a hardcoded constant. |
| `tests/test_hybrid.py` | create | Add regression/invariant coverage for hybrid. |
| `tests/test_invariants.py` | modify | Require study evidence and non-boundary values for frozen parameters. |
| `tests/test_operations.py` | create | Add regression/invariant coverage for operations. |
| `tests/test_splits.py` | modify | Prevent cache refreshes and implicit configuration edits from moving the reserved research period. |
| `tests/test_tracking.py` | create | Add regression/invariant coverage for tracking. |
| `tests/test_training.py` | create | Reject invalid matrices, champion overwrites and final-holdout use after a failed development gate. |
| `tests/test_weather_feats.py` | modify | Preserve the zero floor below the tuned breakpoint in zone aggregation checks. |

## Generated report inventory

| File | Change |
|---|---|
| `reports/ablation/add_cyclic_day_of_year.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/include_earlier_east.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/manifest.json` | Source, input, environment and split provenance. |
| `reports/ablation/measured_only.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/mixed_same_three_folds.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/summary.csv` | Measured comparison summary, with baseline context and row counts in the associated report. |
| `reports/ablation/without_cooling_degrees.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_day_of_week.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_hour_of_day.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_is_holiday.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_temperature.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_trend.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation/without_zone.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation-execution-corrected.log` | Local execution log for the named verification or experiment. |
| `reports/ablation-execution.log` | Local execution log for the named verification or experiment. |
| `reports/ablation.md` | Generated evidence for ablation. |
| `reports/ablation_initial_capped/add_cyclic_day_of_year.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/include_earlier_east.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/manifest.json` | Source, input, environment and split provenance. |
| `reports/ablation_initial_capped/measured_only.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/mixed_same_three_folds.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/summary.csv` | Measured comparison summary, with baseline context and row counts in the associated report. |
| `reports/ablation_initial_capped/without_cooling_degrees.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_day_of_week.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_hour_of_day.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_is_holiday.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_temperature.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_trend.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped/without_zone.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/ablation_initial_capped.md` | Generated evidence for ablation initial capped. |
| `reports/archive_inventory.json` | Generated evidence for archive inventory. |
| `reports/calibration/result.json` | Generated evidence for result. |
| `reports/calibration/selection.json` | Explicit promotion decision and primary/co-primary/veto evidence. |
| `reports/calibration/sweep.csv` | Generated evidence for sweep. |
| `reports/calibration/watch_sweep.csv` | Generated evidence for watch sweep. |
| `reports/completion.json` | Generated evidence for completion. |
| `reports/completion.md` | Generated evidence for completion. |
| `reports/data_inventory.csv` | Generated evidence for data inventory. |
| `reports/data_inventory.md` | Generated evidence for data inventory. |
| `reports/deployment.json` | Generated evidence for deployment. |
| `reports/github_archive_status.json` | Generated evidence for github archive status. |
| `reports/github_archive_status.md` | Generated evidence for github archive status. |
| `reports/implementation_decisions.md` | Generated evidence for implementation decisions. |
| `reports/implementation_files.json` | Generated evidence for implementation files. |
| `reports/iteration_convergence.json` | Generated evidence for iteration convergence. |
| `reports/linear_diagnostic.csv` | Generated evidence for linear diagnostic. |
| `reports/linear_validation_diagnostic.json` | Generated evidence for linear validation diagnostic. |
| `reports/model/comparison.svg` | Measured baseline comparison figure with row counts. |
| `reports/model/coverage.csv` | Expected, eligible, available and compared cohorts. |
| `reports/model/fits.json` | Actual early-stopping/refit counts and training ranges by fold. |
| `reports/model/fold_scores.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/model/manifest.json` | Source, input, environment and split provenance. |
| `reports/model/selection.json` | Explicit promotion decision and primary/co-primary/veto evidence. |
| `reports/model/stratified.csv` | Error breakdowns, baseline figures, sufficiency labels and counts. |
| `reports/model/summary.csv` | Measured comparison summary, with baseline context and row counts in the associated report. |
| `reports/model/veto_tolerances.json` | Generated evidence for veto tolerances. |
| `reports/model-execution.log` | Local execution log for the named verification or experiment. |
| `reports/model.md` | Generated evidence for model. |
| `reports/model_card.md` | Generated evidence for model card. |
| `reports/model_gate_status.md` | Generated evidence for model gate status. |
| `reports/model_initial_capped/comparison.svg` | Measured baseline comparison figure with row counts. |
| `reports/model_initial_capped/coverage.csv` | Expected, eligible, available and compared cohorts. |
| `reports/model_initial_capped/fold_scores.csv` | Per-fold model/comparator scores and measured row counts. |
| `reports/model_initial_capped/manifest.json` | Source, input, environment and split provenance. |
| `reports/model_initial_capped/stratified.csv` | Error breakdowns, baseline figures, sufficiency labels and counts. |
| `reports/model_initial_capped/summary.csv` | Measured comparison summary, with baseline context and row counts in the associated report. |
| `reports/model_initial_capped.md` | Generated evidence for model initial capped. |
| `reports/replay/events.json` | Generated evidence for events. |
| `reports/replay/summary.json` | Generated evidence for summary. |
| `reports/replay-execution.log` | Local execution log for the named verification or experiment. |
| `reports/replay.md` | Generated evidence for replay. |
| `reports/research_protocol.json` | Generated evidence for research protocol. |
| `reports/threshold_derivation.md` | Generated evidence for threshold derivation. |
| `reports/tuning/result.json` | Generated evidence for result. |
| `reports/tuning/study.sqlite3` | Local Optuna working store; consistent DVC snapshot also retained. |
| `reports/tuning/trials.csv` | Generated evidence for trials. |
| `reports/verification/container-tests.xml` | Machine-readable test outcomes; environment-only skips are recorded. |
| `reports/verification/dashboard.json` | Generated evidence for dashboard. |
| `reports/verification/local-tests.xml` | Machine-readable test outcomes; environment-only skips are recorded. |
| `reports/verification/real_offline_flow.json` | Generated evidence for real offline flow. |
| `reports/verification/reproducibility.json` | Generated evidence for reproducibility. |
| `reports/execution_handoff.md` | This complete inventory, outcomes, boundaries and proposed commit groups. |

## Raw data and state inventory (original project)

| File | Action | Change |
|---|---|---|
| `data/raw/weather_IN-NO.parquet` | modify | Merge validated observed-weather repair through 2026-10-27 UTC. |
| `data/raw/weather_IN-NO.parquet.dvc` | modify | Update the local DVC pointer for repaired observations. |
| `data/raw/weather_IN-WE.parquet` | modify | Merge validated observed-weather repair through 2026-10-27 UTC. |
| `data/raw/weather_IN-WE.parquet.dvc` | modify | Update the local DVC pointer for repaired observations. |
| `data/raw/weather_IN-SO.parquet` | modify | Merge validated observed-weather repair through 2026-10-27 UTC. |
| `data/raw/weather_IN-SO.parquet.dvc` | modify | Update the local DVC pointer for repaired observations. |
| `data/raw/weather_IN-EA.parquet` | modify | Merge validated observed-weather repair through 2026-10-27 UTC. |
| `data/raw/weather_IN-EA.parquet.dvc` | modify | Update the local DVC pointer for repaired observations. |
| `data/raw/weather_IN-NE.parquet` | modify | Merge validated observed-weather repair through 2026-10-27 UTC. |
| `data/raw/weather_IN-NE.parquet.dvc` | modify | Update the local DVC pointer for repaired observations. |
| `data/raw/forecast_vintages/2026-11-03.parquet` | create | Capture the current full weather forecast for all five zones. |
| `data/raw/demand_revisions/2026-11-03.parquet` | create | Capture currently observed demand revisions with real observation timestamps. |
| `data/raw/demand_revisions/2026-11-03-catchup.parquet` | create | Merge the missing demand interval through November 3 without inventing past availability. |
| `data/raw/forecast_vintages.dvc` | modify | Update the locally cached vintage-directory pointer. |
| `data/raw/demand_revisions.dvc` | modify | Update the locally cached demand-revision pointer. |
| `state/runs/2026-11-03-archive.jsonl` | create | Append the successful local capture status. |

## Derived data, tracking and dashboard inventory

| File | Action | Change |
|---|---|---|
| `data/interim/model_predictions.parquet` | create | DVC-cached real-data prediction, matrix or study artifact. |
| `data/interim/model_predictions.parquet.dvc` | create | Local DVC pointer; remote persistence is pending. |
| `data/interim/model_initial_capped_predictions.parquet` | create | DVC-cached real-data prediction, matrix or study artifact. |
| `data/interim/model_initial_capped_predictions.parquet.dvc` | create | Local DVC pointer; remote persistence is pending. |
| `data/interim/tuning_training.parquet` | create | DVC-cached real-data prediction, matrix or study artifact. |
| `data/interim/tuning_training.parquet.dvc` | create | Local DVC pointer; remote persistence is pending. |
| `data/interim/tuning_study.sqlite3` | create | DVC-cached real-data prediction, matrix or study artifact. |
| `data/interim/tuning_study.sqlite3.dvc` | create | Local DVC pointer; remote persistence is pending. |
| `data/interim/repro_linux/model_predictions.parquet` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/comparison.svg` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/coverage.csv` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/fits.json` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/fold_scores.csv` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/manifest.json` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/stratified.csv` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model/summary.csv` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux/reports/model.md` | create | DVC-cached Linux reproduction output. |
| `data/interim/repro_linux.dvc` | create | Pointer for the Linux reproduction dataset. |
| `data/interim/.gitignore` | modify | DVC-generated exclusions for derived artifacts. |
| `mlruns.dvc` | create | Pointer for local file-backed experiment tracking. |
| `mlruns/0/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/artifacts/model.md` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/metrics/mape_pct` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/metrics/mase` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/metrics/rmsse` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/breakpoint` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/half_life` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_bagging_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_feature_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_lambda_l1` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_lambda_l2` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_learning_rate` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_min_data_in_leaf` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/lightgbm_num_leaves` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/params/ridge_alpha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/config_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/data_dvc_md5` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/data_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/dvc_pointer_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/git_sha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/image_digest` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.runName` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.source.git.commit` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.source.git.repoURL` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.source.name` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.source.type` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/mlflow.user` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/seed` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/38cc145f0b114a268f6f30aef6c84220/tags/source_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/artifacts/result.json` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/metrics/best_mase` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/metrics/trials` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/breakpoint` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/half_life` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_bagging_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_feature_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_lambda_l1` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_lambda_l2` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_learning_rate` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_min_data_in_leaf` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/lightgbm_num_leaves` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/params/ridge_alpha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/config_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/data_dvc_md5` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/data_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/dvc_pointer_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/git_sha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/image_digest` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/mlflow.runName` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/mlflow.source.name` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/mlflow.source.type` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/mlflow.user` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/seed` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/9f56124c00cd4d0e8b96cf30814d8444/tags/source_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/metrics/checks` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/params/breakpoint` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/params/half_life` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/params/ridge_alpha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/config_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/data_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/git_sha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/image_digest` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/mlflow.runName` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/mlflow.source.name` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/mlflow.source.type` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/mlflow.user` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/seed` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/b83b8a1667ec434297463ce8643fefa0/tags/source_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/artifacts/model.md` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/metrics/mape_pct` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/metrics/mase` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/metrics/rmsse` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/breakpoint` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/half_life` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_bagging_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_feature_fraction` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_lambda_l1` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_lambda_l2` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_learning_rate` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_min_data_in_leaf` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/lightgbm_num_leaves` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/params/ridge_alpha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/config_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/data_dvc_md5` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/data_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/dvc_pointer_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/git_sha` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/image_digest` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.runName` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.source.git.commit` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.source.git.repoURL` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.source.name` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.source.type` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/mlflow.user` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/seed` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/f2ec8ec064b149eca3f854db956af3aa/tags/source_sha256` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `mlruns/770393588822119021/meta.yaml` | create | DVC-managed experiment metadata, parameters, metrics or artifact. |
| `docs/assets/development-lead.svg` | create | Static dashboard HTML or measured development SVG. |
| `docs/index.html` | create | Static dashboard HTML or measured development SVG. |
