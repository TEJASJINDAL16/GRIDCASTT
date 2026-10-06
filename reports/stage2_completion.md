# Stage 2 Local Handoff

Implemented 2026-10-06 in the existing project, preserving its newer local
feature and vintage-recovery work. No Git commit or GitHub change
is made by this handoff.

## Delivered

- Constant-sigma raw-temperature perturbations before degree transforms.
- Reserved early tuning window, twelve monthly expanding folds, purge and
  validation boundaries, and an unscored twelve-month holdout.
- Seasonal naive, hour/weekday historical mean, pooled Ridge-all and per-zone
  Ridge with fixed baseline parameters, log targets and per-zone Duan smearing.
- Same-row out-of-sample MASE/RMSSE, MAPE, physical errors, signed bias,
  shortfall frequency, P95, actual-peak and contiguous evening-ramp metrics.
- Full comparison by temperature, hour, zone, day type, lead time, zone/temperature
  and trailing time windows; explicit row counts, unavailable cells and coverage.
- Baseline report, prediction audit records, data/source fingerprints and
  a written lead-time investigation. `make baseline` repeats the real-data run.

## Verification and Limits

The complete cached-data run covers twelve monthly folds from September 2024
through August 2025. See `baseline.md` and `baseline/summary.csv` for the number
to beat; these are development benchmark results, not holdout or production
forecast accuracy. All four models use an identical measured comparison cohort.

The final September 2025-August 2026 holdout was not scored. Tests verify that
changing holdout targets cannot change any development prediction and that
later fold targets cannot change earlier fold predictions. Other tests check
the issue-relative seasonal lookup, timestamp units, missing-hour handling,
training/serving feature agreement, metric formulas and peak/ramp context.

Earlier exploratory analyses already examined the full cached history.
The holdout is excluded from this baseline pipeline, but a later final
accuracy claim must disclose that earlier exploration; it is not a completely
unseen dataset throughout the project's history.

Full worktree verification after the eligibility revision: 157 tests passed,
one secret-value scan skipped because this worktree has no `.env`; Ruff passes.
No secret files were copied.
The shared feature contract and every INV-1 through INV-9 have passing checks.
Original-project verification after copying the eligibility revision: 158 tests
passed with no skips; Ruff passes. All 33 source/config/input hashes in the
regenerated manifest match the original project; the holdout remains unscored.
The refreshed seasonal benchmark is 11.789% MAPE on 35,033 common measured rows.
The comparison cohort grew after removing the linked minimum-history gate, so
the prior headline is not a same-row comparison of filtering performance.

The prediction artifact is tracked in DVC and cached in both local checkouts.
An earlier Google Drive upload attempt failed with token-refresh
`invalid_grant`. Remote backup is pending reauthorization of the existing DVC
Google OAuth credentials, followed by
`dvc push data/interim/baseline_predictions.parquet.dvc`. No credential values
were inspected or copied, and no Git staging, commit or push was performed.
The regenerated artifact is cached locally; remote upload was not retried
during the eligibility revision because the authorization issue remains.

Owner decision 2026-10-06: remove inferred-suppression filtering and its linked
minimum-history restriction. Hot-period demand drops remain in training when
otherwise eligible. The detector, thresholds and report are removed; revised
INV-8 and end-to-end retention tests enforce this policy. Basic validity and
estimation-method checks remain. Baseline results are regenerated accordingly.

Weather-noise sigmas and the ten-day purge are still labelled assumptions.
The historical weather bridge has constant sigma, and lead time is confounded
with hour of day. The report investigates non-monotonic lead error without
claiming an empirical forecast degradation curve. Forecast recovery is kept
separate because its intra-day issue time is unknown.

The Stage 2 work-order table still mentions heating degrees; PLANNING 5e
explicitly deletes them after measurement. This discrepancy is recorded here;
the implementation retains the existing seven-feature contract and no heating
term. Manual festival extensions remain incomplete. No production hybrid,
tuning, monitoring or daily forecasting job is introduced in Stage 2.

## Files Created or Updated

| File | Change |
|---|---|
| `src/features/forecast_noise.py` | Deterministic daily bias and hourly temperature noise |
| `src/backtest/splits.py` | Tuning, fold, validation, purge, issue and holdout boundaries |
| `src/models/baselines.py` | Four fixed baseline implementations |
| `src/backtest/metrics.py` | Scalar and stratified metrics; complete-day peak and contiguous-ramp context |
| `src/backtest/run.py` | Cache validation, fold-local filtering, baseline evaluation and report generation |
| `scripts/backtest_baselines.py` | Cached-data command entry point |
| `config/config.yaml` | Separate fixed baseline and backtest settings; production tuning keys stay null |
| `src/config.py` | Required-key validation for the new settings |
| `Makefile` | `baseline` target and complete phony target declarations |
| `tests/test_forecast_noise.py` | Reproducibility, daily bias and transform/contract tests |
| `tests/test_splits.py` | Calendar, purge, tuning and holdout checks |
| `tests/test_baselines.py` | Seasonal availability, timestamp units and learned-baseline abstention checks |
| `tests/test_metrics.py` | Hand-calculated scaled metrics, invalid targets, sparse bands and peak/ramp context |
| `tests/test_backtest.py` | Complete loop, future-data isolation, missing-day handling and report checks |
| `tests/test_invariants.py` | Replaces Stage 2/3 placeholder skips with actual baseline/tuning-boundary checks |
| `README.md` | Current implementation status, baseline command and corrected planned feature list |
| `BUILD_STAGES.md` | Local exit-gate evidence and the revised owner eligibility policy |
| `reports/baseline.md` | Full real-data comparison and limitations |
| `reports/baseline/summary.csv` | Overall comparison with baseline denominators and daily/ramp counts |
| `reports/baseline/fold_scores.csv` | All four comparators on all twelve folds |
| `reports/baseline/coverage.csv` | Expected, forecastable, measured, compared and unavailable rows by fold |
| `reports/baseline/stratified.csv` | All reporting metrics and counts across every dimension |
| `reports/baseline/manifest.json` | Runtime versions, seed, split boundaries and actual-input/source hashes |
| `data/interim/baseline_predictions.parquet` | Predictions, issue times, source timestamps and assumption flags |
| `data/interim/baseline_predictions.parquet.dvc` | Local DVC artifact pointer |
| `data/interim/.gitignore` | DVC-generated exclusion for the prediction artifact |
| `reports/stage2_completion.md` | This handoff and file inventory |

## Proposed Commit Message

Implement Stage 2's baseline-only walk-forward benchmark and weather-noise
bridge. Add calendar/purge/holdout boundaries, four frozen comparators,
same-row scaled metrics, coverage-aware stratification and the reproducible
baseline report. Enforce issue-relative seasonal lookups with future-target
isolation tests and retain eligible hot-period demand drops without inferred
causes. Disclose the weather/purge assumptions rather than claiming they are
measured results.


## Eligibility Revision File Inventory

- Deleted: `src/features/quality.py`, `tests/test_quality.py`,
  `reports/quality_suppression.md`, `reports/figures/suppression.png`.
- `src/features/build.py`, `src/backtest/run.py`, `src/backtest/splits.py`:
  remove detector imports, exclusion wrapper, minimum-history gate and report claims.
- `src/config.py`, `config/config.yaml`: remove heuristic threshold requirements.
- `scripts/measure_step0.py`, `reports/step0_measurements.md`:
  remove speculative candidate analysis and its figure/report generation.
- `tests/test_invariants.py`, `tests/test_backtest.py`: cover retention of eligible
  hot-period drops and short per-zone history, while preserving validity checks.
- `PLANNING.md`, `BUILD_STAGES.md`, `AGENTS.md`, `README.md`, this handoff:
  record the revised policy so later work cannot restore the heuristic.
- `reports/baseline.md`, `reports/baseline/*.csv`,
  `reports/baseline/manifest.json`, prediction parquet and its DVC pointer:
  regenerated for the changed training cohort.

Proposed revision commit message: Remove speculative demand-suppression filtering
at the owner's request; retain eligible observations, revise INV-8 and regenerate
the baseline with regression coverage for hot-period drops and short history.
