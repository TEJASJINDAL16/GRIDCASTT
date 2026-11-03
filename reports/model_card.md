# Gridcast Model Card

Day-ahead hourly consumption in MW for five Indian zones. Academic, non-commercial use; demand data from Electricity Maps.

## Model and Evidence

Ridge on temperature, cooling degrees and trend, plus LightGBM residuals; log target and per-zone Duan smearing. No demand lags or inferred-cause filtering.

Deployment approved by development selection gate: False. Reasons: ['mean fold mase did not improve/hold', 'mean fold rmsse did not improve/hold'].

Tuning uses measured Eastern-zone targets before the first test fold. The originally reserved early year contained no measured targets. This limits cross-zone tuning evidence.

Development folds cross the MODE_BREAKDOWN-to-measured transition. Forecast weather is a constant-sigma simulation bridge; results do not establish exact historical forecast-vintage skill.

## Model Results

Out-of-sample MASE/RMSSE on identical measured rows; seasonal-naive denominator.

| model             |   n_rows |   mape_pct |    mase |   rmsse |   signed_bias_pct |
|:------------------|---------:|-----------:|--------:|--------:|------------------:|
| seasonal_naive    |    35033 |    11.7889 | 1       | 1       |          0.376355 |
| hour_weekday_mean |    35033 |    19.4056 | 2.11783 | 2.0995  |         -6.35426  |
| ridge_all         |    35033 |    19.8619 | 1.83069 | 1.70424 |          4.45741  |
| per_zone_ridge    |    35033 |    27.8298 | 1.80959 | 1.73552 |         16.3341   |
| hybrid            |    35033 |    14.1135 | 1.26219 | 1.32035 |         -0.643771 |

### Temperature-band limits

| segment      | model          |   n_rows | status     | mape_pct              | signed_bias_pct       |
|:-------------|:---------------|---------:|:-----------|:----------------------|:----------------------|
| < 20 C       | seasonal_naive |     5584 | reportable | 17.286687129949293    | -0.0338838568993498   |
| < 20 C       | hybrid         |     5584 | reportable | 20.24861000675105     | -5.601560841245579    |
| 20 to < 30 C | seasonal_naive |    22857 | reportable | 10.60085611944327     | 0.2523865285775383    |
| 20 to < 30 C | hybrid         |    22857 | reportable | 13.1749561163515      | -0.3919251013689536   |
| 30 to < 45 C | seasonal_naive |     6592 | reportable | 11.251155679283237    | 1.1537115660976562    |
| 30 to < 45 C | hybrid         |     6592 | reportable | 12.171059605827384    | 2.682665034052093     |
| >= 45 C      | seasonal_naive |        0 | absent     | insufficient / absent | insufficient / absent |
| >= 45 C      | hybrid         |        0 | absent     | insufficient / absent | insufficient / absent |

## Training Ranges

Final development fold ranges; no approved production artifact exists.
| zone   | feature         |      min |     max |
|:-------|:----------------|---------:|--------:|
| IN-NO  | temperature     |  2.02848 | 47.8071 |
| IN-NO  | cooling_degrees |  0       | 22.718  |
| IN-WE  | temperature     | 13.0647  | 41.2391 |
| IN-WE  | cooling_degrees |  0       | 16.15   |
| IN-SO  | temperature     | 10.8463  | 42.3403 |
| IN-SO  | cooling_degrees |  0       | 17.2512 |
| IN-EA  | temperature     |  8.61848 | 43.8642 |
| IN-EA  | cooling_degrees |  0       | 18.7751 |
| IN-NE  | temperature     |  8.9717  | 39.0644 |
| IN-NE  | cooling_degrees |  0       | 13.9753 |

## Remaining Assumptions

Ten-day settlement purge; weather-noise sigmas 1.2 C daily and 0.5 C hourly; maximum vintage age 72 hours. Exact captured-vintage and first-settlement history is too short to replace these honestly. Thresholds use fully settled replay and remain provisionally optimistic. Cooldown lengths are policy defaults; a frozen-champion decay study remains required to validate them.

Manual festival coverage remains limited to the configured external calendar; no dates are invented. Sparse hottest bands are shown as insufficient, never as established performance.

Earlier exploratory analysis inspected the eventual holdout history. The final scoring run is reserved, but the project cannot claim the entire dataset was unseen throughout development.

## Reproducibility

{}

Decision and metrics to three decimal places are the target; not bit-identical floating-point artifacts. A null image digest means the container pin is not yet verified.
