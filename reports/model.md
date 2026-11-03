# Stage 3: Frozen Model Comparison

Generated 2026-11-03T19:57:38.893748+00:00. Command: `make model` (cached data only; holdout guarded against repeat evaluation).

**Number to beat: seasonal-naive MAPE 11.789% over 35,033 common measured rows.** Its out-of-sample MASE and RMSSE are 1.000. The Stage 3 selection criterion is mean fold MASE, with RMSSE co-primary; the pooled MAPE above is descriptive, not a final holdout result.

## Protocol and Limits

12 monthly expanding folds: 2024-09-01 up to 2025-09-01 (exclusive), IST calendar boundaries. The final holdout is 2025-09-01 through 2026-09-01 (exclusive), and was not scored. A partial newest month is excluded from the split anchor. Reserved tuning window: 2020-01-01 through 2021-01-01 (exclusive), IST. Hybrid parameters were frozen by the pre-test measured-target study in reports/tuning/result.json. That validation period replaces the original early tuning year, which has no measured targets. Only IN-EA contributes measured tuning targets; cross-zone tuning evidence is limited.

Earlier exploratory analyses examined the full cached history. The holdout is reserved from this baseline loop; a later final accuracy claim must disclose that earlier exploration rather than describing the dataset as completely unseen throughout the project.

Each learned baseline is fitted once per fold. Training ends at least ten days before the first issue, slightly earlier than a ten-day gap from the test boundary. The ten-day settlement gap is an unmeasured assumption. Daily issue time is 10:00 IST on the preceding date. UTC hourly targets map to IST 00:30-23:30, with exact leads 14.5-37.5 hours. No target interpolation or recursive prediction is used.

The seasonal baseline uses the latest measured same-zone/hour/weekday value at least ten days before each daily issue; it can use eligible history accumulated within a fold. Historical means are per zone/hour/weekday. Ridge-all and per-zone Ridge use identical engineered features, categorical hour/weekday/zone encodings, log targets, fixed alpha=1.0, configured recency weights, and per-zone Duan smearing estimated on training residuals. These parameters were not selected using test-fold performance.

Weather inputs use the configured constant-sigma simulation bridge: per-city/IST-day Gaussian bias sigma=1.2 C plus hourly wobble sigma=0.5 C. Noise is applied to raw temperature before cooling-degree transforms in both training and simulated serving. These are assumptions, not measured forecast errors. This model comparison does not claim historical point-in-time weather accuracy. Recovered forecasts have uncertain intra-day issue times and are not silently treated as exact 10:00 IST vintages.

**Data-generating-process caveat:** folds straddle the MODE_BREAKDOWN-to-measured transition. Only measured targets are scored, while training allows measured plus MODE_BREAKDOWN. Early folds consequently score fewer zones. IN-NE has no eligible training history at its first measured fold; learned models abstain there. All four reported baseline scores use the same measured rows with finite predictions from every baseline. Expected, measured and excluded rows are reported below. Incomplete weather days are skipped for that zone; missing actuals are not scored. A fold above failure.max_gap_fraction is marked unreliable rather than silently removed. The demand archive contains current revised values; the assumed purge is not a complete historical revision replay.

All otherwise eligible observations are retained, including hot hours with sustained demand drops. No heuristic infers a cause or removes records based on temperature and demand residuals. Manual festival extensions remain incomplete, and cyclic day-of-year remains an ablation candidate.

## Overall Comparison

| model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| seasonal_naive    |    35033 |     11.789 |              11.789 |  1.000 |   1.000 |             0.376 |               40.565 |        34.849 |
| hour_weekday_mean |    35033 |     19.406 |              11.789 |  2.118 |   2.099 |            -6.354 |               61.011 |        45.461 |
| ridge_all         |    35033 |     19.862 |              11.789 |  1.831 |   1.704 |             4.457 |               45.297 |        57.066 |
| per_zone_ridge    |    35033 |     27.830 |              11.789 |  1.810 |   1.736 |            16.334 |               35.121 |        74.595 |
| hybrid            |    35033 |     14.114 |              11.789 |  1.262 |   1.320 |            -0.644 |               47.752 |        39.780 |

Percentage metrics are expressed in percent. MASE=sum(abs(error))/sum(abs(seasonal error)); RMSSE=sqrt(sum(error^2)/sum(seasonal error^2)), the out-of-sample variants on identical rows. Zero denominators are undefined, never coerced to zero. Lower is better except signed bias, whose sign states over/under forecast. Shortfall counts misses below the configured -3% threshold.

## Mean Across Folds

| model             |   mape_pct |   mase |   rmsse |
|:------------------|-----------:|-------:|--------:|
| seasonal_naive    |     12.571 |  1.000 |   1.000 |
| hour_weekday_mean |     18.542 |  2.181 |   2.165 |
| ridge_all         |     19.706 |  1.926 |   1.832 |
| per_zone_ridge    |     25.759 |  1.862 |   1.832 |
| hybrid            |     14.218 |  1.250 |   1.247 |

## Physical, Peak and Ramp Errors

| model             |   n_rows |   mae_mw |   rmse_mw |   rmse_mae_ratio |   n_peak_days |   peak_mae_mw |   baseline_peak_mae_mw |   peak_mape_pct |   n_ramps |   ramp_mae_mw |   baseline_ramp_mae_mw |   ramp_mase |
|:------------------|---------:|---------:|----------:|-----------------:|--------------:|--------------:|-----------------------:|----------------:|----------:|--------------:|-----------------------:|------------:|
| seasonal_naive    |    35033 | 3803.617 |  5533.862 |            1.455 |          1459 |      4038.623 |               4038.623 |          10.171 |      7295 |       684.872 |                684.872 |       1.000 |
| hour_weekday_mean |    35033 | 8055.409 | 11618.341 |            1.442 |          1459 |      8241.351 |               4038.623 |          16.396 |      7295 |      1537.296 |                684.872 |       2.245 |
| ridge_all         |    35033 | 6963.239 |  9431.054 |            1.354 |          1459 |      5809.649 |               4038.623 |          14.697 |      7295 |      1907.665 |                684.872 |       2.785 |
| per_zone_ridge    |    35033 | 6882.997 |  9604.137 |            1.395 |          1459 |      7030.537 |               4038.623 |          24.915 |      7295 |      1651.534 |                684.872 |       2.411 |
| hybrid            |    35033 | 4800.875 |  7306.612 |            1.522 |          1459 |      6026.019 |               4038.623 |          14.016 |      7295 |      1570.892 |                684.872 |       2.294 |

Peak errors use each complete measured zone/day's actual maximum. Incomplete days are excluded from peak metrics. Ramps compare consecutive hourly deltas within the same fold/zone/day during the configured IST evening window; they never bridge missing hours or folds. Pooled MW errors reflect zone magnitude; use per-zone scores below for comparison.

## Fold Coverage

|   fold | test_start                | test_end                  | train_end                 | training_zones                                |   n_train |   n_excluded_training |   n_expected |   n_forecast |   cache_gap_fraction | fold_status             |   n_measured |   n_common |   n_measured_without_comparison |   n_available_seasonal_naive |   n_available_hour_weekday_mean |   n_available_ridge_all |   n_available_per_zone_ridge |   n_available_hybrid |
|-------:|:--------------------------|:--------------------------|:--------------------------|:----------------------------------------------|----------:|----------------------:|-------------:|-------------:|---------------------:|:------------------------|-------------:|-----------:|--------------------------------:|-----------------------------:|--------------------------------:|------------------------:|-----------------------------:|---------------------:|
|      1 | 2024-08-31T18:30:00+00:00 | 2024-09-30T18:30:00+00:00 | 2024-08-21T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    127556 |                 75774 |         3600 |         3600 |                0.000 | cache coverage reliable |          720 |        720 |                               0 |                          720 |                             720 |                     720 |                          720 |                  720 |
|      2 | 2024-09-30T18:30:00+00:00 | 2024-10-31T18:30:00+00:00 | 2024-09-20T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    130436 |                 76494 |         3720 |         3720 |                0.000 | cache coverage reliable |          744 |        744 |                               0 |                          744 |                             744 |                     744 |                          744 |                  744 |
|      3 | 2024-10-31T18:30:00+00:00 | 2024-11-30T18:30:00+00:00 | 2024-10-21T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    133412 |                 77238 |         3600 |         3600 |                0.000 | cache coverage reliable |         2984 |       1402 |                            1582 |                         1640 |                            2410 |                    2410 |                         2410 |                 2410 |
|      4 | 2024-11-30T18:30:00+00:00 | 2024-12-31T18:30:00+00:00 | 2024-11-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    136511 |                 77739 |         3720 |         3720 |                0.000 | cache coverage reliable |         3483 |       3483 |                               0 |                         3483 |                            3483 |                    3483 |                         3483 |                 3483 |
|      5 | 2024-12-31T18:30:00+00:00 | 2025-01-31T18:30:00+00:00 | 2024-12-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    140165 |                 77805 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |                 3720 |
|      6 | 2025-01-31T18:30:00+00:00 | 2025-02-28T18:30:00+00:00 | 2025-01-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    143648 |                 78042 |         3360 |         3360 |                0.000 | cache coverage reliable |         3360 |       3360 |                               0 |                         3360 |                            3360 |                    3360 |                         3360 |                 3360 |
|      7 | 2025-02-28T18:30:00+00:00 | 2025-03-31T18:30:00+00:00 | 2025-02-18T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    147008 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |                 3720 |
|      8 | 2025-03-31T18:30:00+00:00 | 2025-04-30T18:30:00+00:00 | 2025-03-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    150728 |                 78042 |         3600 |         3600 |                0.000 | cache coverage reliable |         3600 |       3600 |                               0 |                         3600 |                            3600 |                    3600 |                         3600 |                 3600 |
|      9 | 2025-04-30T18:30:00+00:00 | 2025-05-31T18:30:00+00:00 | 2025-04-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    154328 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |                 3720 |
|     10 | 2025-05-31T18:30:00+00:00 | 2025-06-30T18:30:00+00:00 | 2025-05-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    158048 |                 78042 |         3600 |         3600 |                0.000 | cache coverage reliable |         3482 |       3482 |                               0 |                         3482 |                            3482 |                    3482 |                         3482 |                 3482 |
|     11 | 2025-06-30T18:30:00+00:00 | 2025-07-31T18:30:00+00:00 | 2025-06-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    161648 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3480 |       3480 |                               0 |                         3480 |                            3480 |                    3480 |                         3480 |                 3480 |
|     12 | 2025-07-31T18:30:00+00:00 | 2025-08-31T18:30:00+00:00 | 2025-07-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    165130 |                 78280 |         3720 |         3720 |                0.000 | cache coverage reliable |         3602 |       3602 |                               0 |                         3602 |                            3602 |                    3602 |                         3602 |                 3602 |

## Every Fold

|   fold | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|-------:|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|      1 | seasonal_naive    |      720 |     17.588 |              17.588 |  1.000 |   1.000 |            -6.403 |               55.972 |        30.921 |
|      1 | hour_weekday_mean |      720 |     14.087 |              17.588 |  0.777 |   0.702 |            -1.121 |               53.472 |        19.849 |
|      1 | ridge_all         |      720 |     18.864 |              17.588 |  0.991 |   1.038 |             7.669 |               33.194 |        53.116 |
|      1 | per_zone_ridge    |      720 |     14.013 |              17.588 |  0.748 |   0.685 |             1.900 |               52.361 |        26.613 |
|      1 | hybrid            |      720 |     14.494 |              17.588 |  0.781 |   0.719 |             1.065 |               52.778 |        25.733 |
|      2 | seasonal_naive    |      744 |     14.750 |              14.750 |  1.000 |   1.000 |             4.377 |               42.876 |        35.136 |
|      2 | hour_weekday_mean |      744 |     16.049 |              14.750 |  1.208 |   1.118 |           -11.821 |               78.495 |        23.777 |
|      2 | ridge_all         |      744 |     16.406 |              14.750 |  1.185 |   1.210 |            -4.539 |               53.360 |        37.539 |
|      2 | per_zone_ridge    |      744 |     15.914 |              14.750 |  1.197 |   1.111 |           -11.723 |               78.495 |        23.351 |
|      2 | hybrid            |      744 |     13.903 |              14.750 |  1.018 |   0.943 |            -7.132 |               76.747 |        22.049 |
|      3 | seasonal_naive    |     1402 |     16.178 |              16.178 |  1.000 |   1.000 |             7.583 |               29.886 |        47.941 |
|      3 | hour_weekday_mean |     1402 |     13.670 |              16.178 |  0.867 |   0.839 |             4.404 |               34.593 |        31.593 |
|      3 | ridge_all         |     1402 |     22.516 |              16.178 |  1.516 |   1.601 |            17.037 |               20.899 |        65.835 |
|      3 | per_zone_ridge    |     1402 |     20.587 |              16.178 |  1.416 |   1.455 |            18.438 |               11.484 |        45.750 |
|      3 | hybrid            |     1402 |     15.977 |              16.178 |  0.992 |   1.006 |            11.685 |               19.258 |        44.792 |
|      4 | seasonal_naive    |     3483 |     19.135 |              19.135 |  1.000 |   1.000 |            -2.834 |               45.765 |        73.057 |
|      4 | hour_weekday_mean |     3483 |     21.954 |              19.135 |  1.288 |   1.343 |             0.048 |               50.962 |        58.446 |
|      4 | ridge_all         |     3483 |     25.768 |              19.135 |  1.421 |   1.259 |             7.319 |               40.798 |        66.138 |
|      4 | per_zone_ridge    |     3483 |     69.726 |              19.135 |  1.784 |   1.617 |            63.966 |               20.729 |       345.099 |
|      4 | hybrid            |     3483 |     27.422 |              19.135 |  1.947 |   1.995 |           -15.462 |               73.155 |        54.268 |
|      5 | seasonal_naive    |     3720 |     11.999 |              11.999 |  1.000 |   1.000 |             1.464 |               40.269 |        34.800 |
|      5 | hour_weekday_mean |     3720 |     18.095 |              11.999 |  1.851 |   2.064 |            -3.518 |               58.898 |        47.452 |
|      5 | ridge_all         |     3720 |     17.569 |              11.999 |  1.478 |   1.419 |             0.563 |               50.081 |        46.589 |
|      5 | per_zone_ridge    |     3720 |     57.459 |              11.999 |  1.798 |   1.720 |            49.994 |               26.183 |       343.825 |
|      5 | hybrid            |     3720 |     13.727 |              11.999 |  1.282 |   1.284 |            -0.633 |               44.543 |        35.937 |
|      6 | seasonal_naive    |     3360 |      9.710 |               9.710 |  1.000 |   1.000 |            -1.995 |               48.125 |        33.868 |
|      6 | hour_weekday_mean |     3360 |     14.038 |               9.710 |  2.528 |   3.044 |            -7.951 |               69.940 |        34.184 |
|      6 | ridge_all         |     3360 |     14.453 |               9.710 |  1.972 |   1.970 |            -0.027 |               49.345 |        33.381 |
|      6 | per_zone_ridge    |     3360 |     24.907 |               9.710 |  2.024 |   2.174 |            15.541 |               37.054 |        93.263 |
|      6 | hybrid            |     3360 |     14.748 |               9.710 |  2.396 |   2.631 |            -6.443 |               60.655 |        35.446 |
|      7 | seasonal_naive    |     3720 |     10.487 |              10.487 |  1.000 |   1.000 |            -0.142 |               41.344 |        27.569 |
|      7 | hour_weekday_mean |     3720 |     14.275 |              10.487 |  2.125 |   2.383 |            -8.043 |               63.763 |        34.607 |
|      7 | ridge_all         |     3720 |     14.818 |              10.487 |  1.623 |   1.619 |             3.451 |               43.495 |        40.154 |
|      7 | per_zone_ridge    |     3720 |     17.684 |              10.487 |  1.707 |   1.711 |             7.224 |               36.022 |        48.476 |
|      7 | hybrid            |     3720 |     14.685 |              10.487 |  1.240 |   1.195 |             8.334 |               27.742 |        43.620 |
|      8 | seasonal_naive    |     3600 |     12.799 |              12.799 |  1.000 |   1.000 |            -0.092 |               46.111 |        42.137 |
|      8 | hour_weekday_mean |     3600 |     20.028 |              12.799 |  2.400 |   2.581 |            -6.368 |               60.972 |        43.387 |
|      8 | ridge_all         |     3600 |     20.270 |              12.799 |  1.854 |   1.953 |             7.454 |               40.556 |        68.123 |
|      8 | per_zone_ridge    |     3600 |     17.700 |              12.799 |  1.611 |   1.666 |             5.968 |               37.222 |        46.339 |
|      8 | hybrid            |     3600 |     14.088 |              12.799 |  1.129 |   1.144 |             5.800 |               36.667 |        42.510 |
|      9 | seasonal_naive    |     3720 |     16.489 |              16.489 |  1.000 |   1.000 |             4.767 |               33.414 |        44.368 |
|      9 | hour_weekday_mean |     3720 |     22.921 |              16.489 |  1.639 |   1.609 |            -2.725 |               55.161 |        54.274 |
|      9 | ridge_all         |     3720 |     23.727 |              16.489 |  1.335 |   1.304 |            10.896 |               41.263 |        85.769 |
|      9 | per_zone_ridge    |     3720 |     21.230 |              16.489 |  1.282 |   1.241 |             9.447 |               32.634 |        57.777 |
|      9 | hybrid            |     3720 |     18.071 |              16.489 |  0.993 |   0.958 |             8.244 |               33.199 |        50.123 |
|     10 | seasonal_naive    |     3482 |     10.623 |              10.623 |  1.000 |   1.000 |            -1.511 |               50.172 |        24.632 |
|     10 | hour_weekday_mean |     3482 |     23.065 |              10.623 |  2.299 |   2.143 |           -11.071 |               65.882 |        49.142 |
|     10 | ridge_all         |     3482 |     21.483 |              10.623 |  1.850 |   1.708 |             1.403 |               53.705 |        62.882 |
|     10 | per_zone_ridge    |     3482 |     18.364 |              10.623 |  1.802 |   1.766 |            -1.081 |               48.047 |        40.849 |
|     10 | hybrid            |     3482 |      9.798 |              10.623 |  0.829 |   0.810 |            -5.900 |               61.459 |        22.583 |
|     11 | seasonal_naive    |     3480 |      4.875 |               4.875 |  1.000 |   1.000 |            -0.572 |               32.960 |        12.577 |
|     11 | hour_weekday_mean |     3480 |     22.900 |               4.875 |  5.461 |   4.933 |           -11.185 |               65.431 |        46.743 |
|     11 | ridge_all         |     3480 |     21.422 |               4.875 |  4.708 |   4.144 |             1.941 |               50.000 |        58.546 |
|     11 | per_zone_ridge    |     3480 |     17.081 |               4.875 |  4.356 |   4.298 |             0.571 |               42.069 |        36.955 |
|     11 | hybrid            |     3480 |      7.466 |               4.875 |  1.389 |   1.273 |            -5.334 |               63.736 |        17.705 |
|     12 | seasonal_naive    |     3602 |      6.217 |               6.217 |  1.000 |   1.000 |             1.502 |               28.484 |        16.300 |
|     12 | hour_weekday_mean |     3602 |     21.424 |               6.217 |  3.724 |   3.218 |           -10.852 |               67.018 |        44.365 |
|     12 | ridge_all         |     3602 |     19.179 |               6.217 |  3.182 |   2.764 |             2.995 |               49.278 |        55.824 |
|     12 | per_zone_ridge    |     3602 |     14.441 |               6.217 |  2.617 |   2.536 |             3.061 |               33.592 |        33.163 |
|     12 | hybrid            |     3602 |      6.236 |               6.217 |  1.002 |   1.001 |             0.004 |               36.646 |        15.963 |

## Stratification: temperature_band

| segment      | status     | model             |   n_rows | mape_pct           | baseline_mape_pct   | mase               | rmsse              | signed_bias_pct      | shortfall_freq_pct   | p95_abs_pct        |
|:-------------|:-----------|:------------------|---------:|:-------------------|:--------------------|:-------------------|:-------------------|:---------------------|:---------------------|:-------------------|
| < 20 C       | reportable | seasonal_naive    |     5584 | 17.286687129949293 | 17.286687129949293  | 1.0                | 1.0                | -0.03388385689934982 | 45.075214899713465   | 58.714709686641626 |
| < 20 C       | reportable | hour_weekday_mean |     5584 | 21.561223063373408 | 17.286687129949293  | 1.4792004334245958 | 1.5611630195038826 | 2.735161206220565    | 45.45128939828081    | 59.70094984959919  |
| < 20 C       | reportable | ridge_all         |     5584 | 24.2695054413247   | 17.286687129949293  | 1.5227960054711762 | 1.4334420092248947 | 1.775653808459477    | 50.931232091690546   | 60.428745307817714 |
| < 20 C       | reportable | per_zone_ridge    |     5584 | 65.01285550908706  | 17.286687129949293  | 1.7274232430571295 | 1.601507598797754  | 59.61333617890533    | 19.37679083094556    | 332.158114556473   |
| < 20 C       | reportable | hybrid            |     5584 | 20.24861000675105  | 17.286687129949293  | 1.4176474141843867 | 1.5253526392746892 | -5.601560841245579   | 57.09169054441261    | 50.3172165357424   |
| 20 to < 30 C | reportable | seasonal_naive    |    22857 | 10.60085611944327  | 10.60085611944327   | 1.0                | 1.0                | 0.25238652857753835  | 39.725248282801765   | 31.157617497918725 |
| 20 to < 30 C | reportable | hour_weekday_mean |    22857 | 18.409988286576127 | 10.60085611944327   | 2.2931804965859457 | 2.265441033615093  | -9.254183298340957   | 65.42415890099313    | 42.027890790125376 |
| 20 to < 30 C | reportable | ridge_all         |    22857 | 17.209278357784306 | 10.60085611944327   | 1.8743324743447205 | 1.755416598968984  | 2.3097767888878606   | 47.110294439340244   | 42.68780645885095  |
| 20 to < 30 C | reportable | per_zone_ridge    |    22857 | 21.918385577826594 | 10.60085611944327   | 1.9274022651694414 | 1.8721159261939126 | 8.863422235683105    | 39.63337270857943    | 50.62118300777546  |
| 20 to < 30 C | reportable | hybrid            |    22857 | 13.1749561163515   | 10.60085611944327   | 1.3518646864521708 | 1.4365496526070456 | -0.3919251013689536  | 46.764667279170496   | 36.95434859599195  |
| 30 to < 45 C | reportable | seasonal_naive    |     6592 | 11.251155679283237 | 11.251155679283237  | 1.0                | 1.0                | 1.1537115660976562   | 39.654126213592235   | 31.232535175786484 |
| 30 to < 45 C | reportable | hour_weekday_mean |     6592 | 21.031628707814942 | 11.251155679283237  | 2.012243593163853  | 1.905063731065051  | -3.9986487877004793  | 58.88956310679612    | 51.05479071039606  |
| 30 to < 45 C | reportable | ridge_all         |     6592 | 25.32584238952942  | 11.251155679283237  | 1.8885568949980578 | 1.6931276118741894 | 14.175745451268478   | 34.23847087378641    | 81.02583197156393  |
| 30 to < 45 C | reportable | per_zone_ridge    |     6592 | 16.829751234514518 | 11.251155679283237  | 1.5426767883885575 | 1.4532571618121763 | 5.576655888270436    | 32.8125              | 41.1553135369805   |
| 30 to < 45 C | reportable | hybrid            |     6592 | 12.171059605827383 | 11.251155679283237  | 0.9358423791036707 | 0.8921038462902462 | 2.682665034052093    | 43.26456310679612    | 33.825090619097026 |
| >= 45 C      | absent     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |

## Stratification: hour_of_day

|   segment | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|----------:|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|         0 | reportable | seasonal_naive    |     1460 |     12.694 |              12.694 |  1.000 |   1.000 |             0.175 |               41.438 |        37.107 |
|         0 | reportable | hour_weekday_mean |     1460 |     23.024 |              12.694 |  2.514 |   2.436 |           -10.030 |               66.712 |        46.033 |
|         0 | reportable | ridge_all         |     1460 |     17.950 |              12.694 |  1.649 |   1.541 |            -1.536 |               55.959 |        43.090 |
|         0 | reportable | per_zone_ridge    |     1460 |     26.394 |              12.694 |  1.704 |   1.597 |            11.025 |               44.521 |        72.544 |
|         0 | reportable | hybrid            |     1460 |     14.246 |              12.694 |  1.225 |   1.211 |             0.302 |               44.726 |        38.470 |
|         1 | reportable | seasonal_naive    |     1460 |     12.870 |              12.870 |  1.000 |   1.000 |             0.257 |               41.438 |        38.212 |
|         1 | reportable | hour_weekday_mean |     1460 |     22.789 |              12.870 |  2.447 |   2.376 |            -9.719 |               65.342 |        45.644 |
|         1 | reportable | ridge_all         |     1460 |     17.993 |              12.870 |  1.632 |   1.526 |            -1.948 |               56.301 |        42.915 |
|         1 | reportable | per_zone_ridge    |     1460 |     25.914 |              12.870 |  1.676 |   1.568 |            10.505 |               43.836 |        68.489 |
|         1 | reportable | hybrid            |     1460 |     14.276 |              12.870 |  1.196 |   1.180 |             0.154 |               46.027 |        38.504 |
|         2 | reportable | seasonal_naive    |     1460 |     13.023 |              13.023 |  1.000 |   1.000 |             0.302 |               41.301 |        39.088 |
|         2 | reportable | hour_weekday_mean |     1460 |     22.462 |              13.023 |  2.365 |   2.299 |            -8.779 |               63.562 |        44.651 |
|         2 | reportable | ridge_all         |     1460 |     17.849 |              13.023 |  1.589 |   1.482 |            -1.888 |               55.479 |        42.056 |
|         2 | reportable | per_zone_ridge    |     1460 |     26.295 |              13.023 |  1.650 |   1.538 |            11.238 |               43.288 |        69.299 |
|         2 | reportable | hybrid            |     1460 |     14.435 |              13.023 |  1.182 |   1.174 |            -0.205 |               46.918 |        39.731 |
|         3 | reportable | seasonal_naive    |     1460 |     13.120 |              13.120 |  1.000 |   1.000 |             0.385 |               41.849 |        39.514 |
|         3 | reportable | hour_weekday_mean |     1460 |     22.480 |              13.120 |  2.343 |   2.269 |            -7.690 |               62.466 |        45.263 |
|         3 | reportable | ridge_all         |     1460 |     17.930 |              13.120 |  1.580 |   1.450 |            -1.298 |               55.137 |        42.561 |
|         3 | reportable | per_zone_ridge    |     1460 |     26.616 |              13.120 |  1.664 |   1.546 |            12.016 |               42.397 |        73.028 |
|         3 | reportable | hybrid            |     1460 |     14.865 |              13.120 |  1.216 |   1.220 |            -0.561 |               48.014 |        40.439 |
|         4 | reportable | seasonal_naive    |     1460 |     13.039 |              13.039 |  1.000 |   1.000 |             0.524 |               41.849 |        37.937 |
|         4 | reportable | hour_weekday_mean |     1460 |     22.283 |              13.039 |  2.380 |   2.332 |            -6.822 |               62.603 |        46.943 |
|         4 | reportable | ridge_all         |     1460 |     17.692 |              13.039 |  1.572 |   1.407 |            -0.384 |               53.904 |        42.583 |
|         4 | reportable | per_zone_ridge    |     1460 |     27.362 |              13.039 |  1.690 |   1.606 |            13.612 |               39.863 |        75.878 |
|         4 | reportable | hybrid            |     1460 |     15.001 |              13.039 |  1.237 |   1.261 |            -0.794 |               49.384 |        42.258 |
|         5 | reportable | seasonal_naive    |     1459 |     12.551 |              12.551 |  1.000 |   1.000 |             0.678 |               39.822 |        36.932 |
|         5 | reportable | hour_weekday_mean |     1459 |     20.831 |              12.551 |  2.421 |   2.422 |            -6.198 |               62.783 |        42.636 |
|         5 | reportable | ridge_all         |     1459 |     16.715 |              12.551 |  1.567 |   1.361 |             0.140 |               51.953 |        41.625 |
|         5 | reportable | per_zone_ridge    |     1459 |     28.509 |              12.551 |  1.716 |   1.714 |            16.249 |               36.463 |        80.068 |
|         5 | reportable | hybrid            |     1459 |     15.006 |              12.551 |  1.297 |   1.399 |            -1.541 |               50.720 |        45.473 |
|         6 | reportable | seasonal_naive    |     1459 |     11.914 |              11.914 |  1.000 |   1.000 |             0.836 |               38.588 |        33.468 |
|         6 | reportable | hour_weekday_mean |     1459 |     19.285 |              11.914 |  2.415 |   2.460 |            -5.906 |               61.823 |        40.962 |
|         6 | reportable | ridge_all         |     1459 |     16.485 |              11.914 |  1.580 |   1.381 |             1.169 |               48.115 |        42.717 |
|         6 | reportable | per_zone_ridge    |     1459 |     28.651 |              11.914 |  1.743 |   1.801 |            17.812 |               33.310 |        79.376 |
|         6 | reportable | hybrid            |     1459 |     15.599 |              11.914 |  1.436 |   1.587 |            -2.766 |               53.873 |        45.072 |
|         7 | reportable | seasonal_naive    |     1459 |     11.515 |              11.515 |  1.000 |   1.000 |             0.845 |               38.314 |        33.339 |
|         7 | reportable | hour_weekday_mean |     1459 |     19.087 |              11.515 |  2.205 |   2.210 |            -1.770 |               57.711 |        41.853 |
|         7 | reportable | ridge_all         |     1459 |     19.175 |              11.515 |  1.740 |   1.626 |             8.855 |               36.052 |        51.968 |
|         7 | reportable | per_zone_ridge    |     1459 |     28.757 |              11.515 |  1.893 |   1.814 |            20.944 |               26.662 |        81.116 |
|         7 | reportable | hybrid            |     1459 |     16.400 |              11.515 |  1.540 |   1.726 |            -1.695 |               51.337 |        46.552 |
|         8 | reportable | seasonal_naive    |     1459 |     11.421 |              11.421 |  1.000 |   1.000 |             0.740 |               38.862 |        34.846 |
|         8 | reportable | hour_weekday_mean |     1459 |     18.412 |              11.421 |  2.015 |   2.007 |            -0.545 |               55.929 |        45.171 |
|         8 | reportable | ridge_all         |     1459 |     21.815 |              11.421 |  1.913 |   1.841 |            13.837 |               30.158 |        65.972 |
|         8 | reportable | per_zone_ridge    |     1459 |     27.238 |              11.421 |  1.845 |   1.731 |            21.171 |               22.550 |        78.739 |
|         8 | reportable | hybrid            |     1459 |     15.802 |              11.421 |  1.512 |   1.679 |            -0.367 |               45.922 |        44.908 |
|         9 | reportable | seasonal_naive    |     1459 |     11.484 |              11.484 |  1.000 |   1.000 |             0.763 |               40.576 |        35.578 |
|         9 | reportable | hour_weekday_mean |     1459 |     17.625 |              11.484 |  1.858 |   1.847 |            -0.821 |               56.340 |        44.159 |
|         9 | reportable | ridge_all         |     1459 |     23.993 |              11.484 |  2.029 |   1.940 |            16.491 |               27.416 |        77.813 |
|         9 | reportable | per_zone_ridge    |     1459 |     25.969 |              11.484 |  1.668 |   1.563 |            20.934 |               21.453 |        74.156 |
|         9 | reportable | hybrid            |     1459 |     14.639 |              11.484 |  1.361 |   1.504 |            -0.344 |               45.579 |        39.620 |
|        10 | reportable | seasonal_naive    |     1459 |     11.588 |              11.588 |  1.000 |   1.000 |             0.757 |               39.685 |        35.493 |
|        10 | reportable | hour_weekday_mean |     1459 |     17.146 |              11.588 |  1.714 |   1.683 |            -0.390 |               55.860 |        45.822 |
|        10 | reportable | ridge_all         |     1459 |     26.182 |              11.588 |  2.145 |   2.002 |            19.170 |               26.456 |        84.093 |
|        10 | reportable | per_zone_ridge    |     1459 |     25.937 |              11.588 |  1.554 |   1.445 |            22.004 |               18.232 |        77.319 |
|        10 | reportable | hybrid            |     1459 |     14.833 |              11.588 |  1.308 |   1.391 |             0.493 |               45.031 |        40.646 |
|        11 | reportable | seasonal_naive    |     1459 |     11.559 |              11.559 |  1.000 |   1.000 |             0.703 |               40.918 |        35.120 |
|        11 | reportable | hour_weekday_mean |     1459 |     16.893 |              11.559 |  1.622 |   1.501 |            -0.193 |               53.873 |        44.777 |
|        11 | reportable | ridge_all         |     1459 |     26.718 |              11.559 |  2.213 |   2.033 |            19.371 |               26.388 |        84.255 |
|        11 | reportable | per_zone_ridge    |     1459 |     26.225 |              11.559 |  1.646 |   1.633 |            21.906 |               21.110 |        72.988 |
|        11 | reportable | hybrid            |     1459 |     14.388 |              11.559 |  1.233 |   1.284 |             0.008 |               46.813 |        41.447 |
|        12 | reportable | seasonal_naive    |     1459 |     11.675 |              11.675 |  1.000 |   1.000 |             0.666 |               40.439 |        34.833 |
|        12 | reportable | hour_weekday_mean |     1459 |     17.460 |              11.675 |  1.669 |   1.564 |            -0.510 |               53.598 |        45.429 |
|        12 | reportable | ridge_all         |     1459 |     26.326 |              11.675 |  2.193 |   1.978 |            18.464 |               26.594 |        81.047 |
|        12 | reportable | per_zone_ridge    |     1459 |     27.375 |              11.675 |  1.825 |   1.742 |            21.784 |               24.469 |        70.296 |
|        12 | reportable | hybrid            |     1459 |     14.525 |              11.675 |  1.217 |   1.204 |             0.562 |               47.019 |        40.977 |
|        13 | reportable | seasonal_naive    |     1459 |     11.906 |              11.906 |  1.000 |   1.000 |             0.672 |               40.576 |        35.358 |
|        13 | reportable | hour_weekday_mean |     1459 |     17.153 |              11.906 |  1.566 |   1.451 |             0.342 |               50.720 |        43.625 |
|        13 | reportable | ridge_all         |     1459 |     26.295 |              11.906 |  2.186 |   1.953 |            18.805 |               24.812 |        79.244 |
|        13 | reportable | per_zone_ridge    |     1459 |     27.766 |              11.906 |  1.831 |   1.750 |            22.571 |               23.235 |        68.755 |
|        13 | reportable | hybrid            |     1459 |     14.494 |              11.906 |  1.174 |   1.157 |             1.657 |               44.277 |        39.984 |
|        14 | reportable | seasonal_naive    |     1459 |     11.688 |              11.688 |  1.000 |   1.000 |             0.532 |               41.330 |        34.552 |
|        14 | reportable | hour_weekday_mean |     1459 |     17.174 |              11.688 |  1.691 |   1.608 |            -2.229 |               54.284 |        40.252 |
|        14 | reportable | ridge_all         |     1459 |     23.233 |              11.688 |  2.007 |   1.799 |            15.217 |               26.114 |        69.184 |
|        14 | reportable | per_zone_ridge    |     1459 |     28.063 |              11.688 |  1.835 |   1.738 |            21.515 |               26.731 |        72.833 |
|        14 | reportable | hybrid            |     1459 |     13.983 |              11.688 |  1.175 |   1.156 |             0.183 |               47.430 |        39.409 |
|        15 | reportable | seasonal_naive    |     1459 |     11.645 |              11.645 |  1.000 |   1.000 |             0.503 |               42.152 |        34.654 |
|        15 | reportable | hour_weekday_mean |     1459 |     16.876 |              11.645 |  1.735 |   1.656 |            -2.974 |               55.175 |        37.396 |
|        15 | reportable | ridge_all         |     1459 |     20.239 |              11.645 |  1.807 |   1.640 |            11.876 |               28.033 |        56.915 |
|        15 | reportable | per_zone_ridge    |     1459 |     29.272 |              11.645 |  1.846 |   1.754 |            21.656 |               28.307 |        74.967 |
|        15 | reportable | hybrid            |     1459 |     13.583 |              11.645 |  1.165 |   1.178 |             0.078 |               47.156 |        37.466 |
|        16 | reportable | seasonal_naive    |     1459 |     11.140 |              11.140 |  1.000 |   1.000 |             0.569 |               40.096 |        32.292 |
|        16 | reportable | hour_weekday_mean |     1459 |     16.259 |              11.140 |  1.813 |   1.732 |            -3.441 |               55.997 |        36.763 |
|        16 | reportable | ridge_all         |     1459 |     17.272 |              11.140 |  1.652 |   1.514 |             7.736 |               34.750 |        46.800 |
|        16 | reportable | per_zone_ridge    |     1459 |     31.130 |              11.140 |  1.907 |   1.819 |            22.558 |               30.912 |        87.749 |
|        16 | reportable | hybrid            |     1459 |     13.196 |              11.140 |  1.177 |   1.208 |             0.269 |               47.293 |        37.000 |
|        17 | reportable | seasonal_naive    |     1459 |     10.634 |              10.634 |  1.000 |   1.000 |             0.671 |               38.040 |        30.366 |
|        17 | reportable | hour_weekday_mean |     1459 |     16.854 |              10.634 |  1.976 |   1.847 |            -5.071 |               58.465 |        37.497 |
|        17 | reportable | ridge_all         |     1459 |     15.558 |              10.634 |  1.588 |   1.409 |             1.880 |               47.361 |        42.347 |
|        17 | reportable | per_zone_ridge    |     1459 |     32.222 |              10.634 |  1.957 |   1.877 |            21.615 |               37.697 |       100.739 |
|        17 | reportable | hybrid            |     1459 |     12.669 |              10.634 |  1.175 |   1.188 |             0.514 |               42.769 |        36.468 |
|        18 | reportable | seasonal_naive    |     1459 |     10.444 |              10.444 |  1.000 |   1.000 |             0.230 |               38.657 |        30.050 |
|        18 | reportable | hour_weekday_mean |     1459 |     18.905 |              10.444 |  2.386 |   2.240 |           -11.206 |               67.101 |        43.164 |
|        18 | reportable | ridge_all         |     1459 |     16.124 |              10.444 |  1.767 |   1.592 |            -5.909 |               61.618 |        36.780 |
|        18 | reportable | per_zone_ridge    |     1459 |     31.018 |              10.444 |  2.083 |   1.966 |            14.840 |               45.922 |        87.019 |
|        18 | reportable | hybrid            |     1459 |     12.831 |              10.444 |  1.299 |   1.364 |            -2.655 |               51.062 |        38.078 |
|        19 | reportable | seasonal_naive    |     1459 |     10.669 |              10.669 |  1.000 |   1.000 |            -0.252 |               40.850 |        30.912 |
|        19 | reportable | hour_weekday_mean |     1459 |     19.565 |              10.669 |  2.463 |   2.432 |           -14.450 |               69.705 |        48.454 |
|        19 | reportable | ridge_all         |     1459 |     17.621 |              10.669 |  1.955 |   1.833 |            -8.431 |               65.661 |        40.618 |
|        19 | reportable | per_zone_ridge    |     1459 |     28.704 |              10.669 |  2.085 |   2.014 |            10.256 |               47.293 |        67.660 |
|        19 | reportable | hybrid            |     1459 |     12.627 |              10.669 |  1.285 |   1.357 |            -3.474 |               53.873 |        36.202 |
|        20 | reportable | seasonal_naive    |     1459 |     11.120 |              11.120 |  1.000 |   1.000 |            -0.399 |               41.193 |        31.536 |
|        20 | reportable | hour_weekday_mean |     1459 |     19.884 |              11.120 |  2.371 |   2.417 |           -14.694 |               69.020 |        51.286 |
|        20 | reportable | ridge_all         |     1459 |     18.315 |              11.120 |  1.983 |   1.905 |            -7.897 |               64.496 |        42.851 |
|        20 | reportable | per_zone_ridge    |     1459 |     27.663 |              11.120 |  2.033 |   2.007 |             8.901 |               46.813 |        60.358 |
|        20 | reportable | hybrid            |     1459 |     12.733 |              11.120 |  1.243 |   1.290 |            -2.039 |               49.417 |        34.714 |
|        21 | reportable | seasonal_naive    |     1459 |     11.470 |              11.470 |  1.000 |   1.000 |            -0.460 |               41.672 |        32.500 |
|        21 | reportable | hour_weekday_mean |     1459 |     20.107 |              11.470 |  2.275 |   2.366 |           -14.304 |               67.992 |        51.384 |
|        21 | reportable | ridge_all         |     1459 |     18.545 |              11.470 |  1.912 |   1.850 |            -7.175 |               63.263 |        43.679 |
|        21 | reportable | per_zone_ridge    |     1459 |     27.245 |              11.470 |  1.995 |   1.970 |             8.350 |               45.648 |        59.980 |
|        21 | reportable | hybrid            |     1459 |     12.706 |              11.470 |  1.218 |   1.232 |            -1.757 |               48.732 |        34.838 |
|        22 | reportable | seasonal_naive    |     1459 |     11.679 |              11.679 |  1.000 |   1.000 |            -0.451 |               42.358 |        33.162 |
|        22 | reportable | hour_weekday_mean |     1459 |     20.358 |              11.679 |  2.218 |   2.321 |           -13.756 |               67.443 |        49.824 |
|        22 | reportable | ridge_all         |     1459 |     18.432 |              11.679 |  1.844 |   1.802 |            -7.008 |               63.674 |        44.281 |
|        22 | reportable | per_zone_ridge    |     1459 |     27.224 |              11.679 |  1.982 |   1.943 |             7.999 |               45.785 |        59.043 |
|        22 | reportable | hybrid            |     1459 |     12.644 |              11.679 |  1.201 |   1.223 |            -1.783 |               48.047 |        35.141 |
|        23 | reportable | seasonal_naive    |     1471 |     12.079 |              12.079 |  1.000 |   1.000 |            -0.209 |               41.536 |        36.787 |
|        23 | reportable | hour_weekday_mean |     1471 |     22.782 |              12.079 |  2.624 |   2.530 |           -11.300 |               69.680 |        46.183 |
|        23 | reportable | ridge_all         |     1471 |     18.247 |              12.079 |  1.734 |   1.635 |            -2.482 |               57.308 |        46.183 |
|        23 | reportable | per_zone_ridge    |     1471 |     26.385 |              12.079 |  1.710 |   1.577 |            10.624 |               46.295 |        73.379 |
|        23 | reportable | hybrid            |     1471 |     13.250 |              12.079 |  1.231 |   1.281 |             0.303 |               44.663 |        36.115 |

## Stratification: zone

| segment   | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| IN-NO     | reportable | seasonal_naive    |     6675 |     12.824 |              12.824 |  1.000 |   1.000 |            -0.086 |               45.438 |        32.936 |
| IN-NO     | reportable | hour_weekday_mean |     6675 |     25.970 |              12.824 |  2.192 |   2.066 |            -9.371 |               67.176 |        55.590 |
| IN-NO     | reportable | ridge_all         |     6675 |     19.324 |              12.824 |  1.448 |   1.349 |             2.500 |               54.202 |        54.130 |
| IN-NO     | reportable | per_zone_ridge    |     6675 |     17.007 |              12.824 |  1.359 |   1.342 |            -2.103 |               55.326 |        41.526 |
| IN-NO     | reportable | hybrid            |     6675 |     12.418 |              12.824 |  0.970 |   0.977 |            -2.767 |               52.869 |        33.761 |
| IN-WE     | reportable | seasonal_naive    |     6674 |      6.782 |               6.782 |  1.000 |   1.000 |             0.447 |               34.282 |        19.384 |
| IN-WE     | reportable | hour_weekday_mean |     6674 |     16.538 |               6.782 |  2.536 |   2.389 |           -12.608 |               73.914 |        37.199 |
| IN-WE     | reportable | ridge_all         |     6674 |     13.940 |               6.782 |  2.034 |   1.859 |             1.744 |               42.343 |        32.808 |
| IN-WE     | reportable | per_zone_ridge    |     6674 |     16.069 |               6.782 |  2.349 |   2.112 |             4.822 |               31.540 |        35.218 |
| IN-WE     | reportable | hybrid            |     6674 |      9.644 |               6.782 |  1.453 |   1.612 |            -2.077 |               38.178 |        31.696 |
| IN-SO     | reportable | seasonal_naive    |     6674 |      9.661 |               9.661 |  1.000 |   1.000 |            -0.240 |               42.254 |        27.005 |
| IN-SO     | reportable | hour_weekday_mean |     6674 |     19.751 |               9.661 |  2.304 |   2.249 |           -12.784 |               68.115 |        43.805 |
| IN-SO     | reportable | ridge_all         |     6674 |     16.390 |               9.661 |  1.776 |   1.631 |            -0.074 |               48.771 |        34.692 |
| IN-SO     | reportable | per_zone_ridge    |     6674 |     19.429 |               9.661 |  2.072 |   1.944 |             2.280 |               44.396 |        45.631 |
| IN-SO     | reportable | hybrid            |     6674 |     13.241 |               9.661 |  1.398 |   1.342 |            -3.279 |               56.683 |        32.563 |
| IN-EA     | reportable | seasonal_naive    |     8577 |     10.282 |              10.282 |  1.000 |   1.000 |             1.646 |               35.549 |        29.409 |
| IN-EA     | reportable | hour_weekday_mean |     8577 |     16.076 |              10.282 |  1.447 |   1.260 |             8.033 |               33.601 |        42.775 |
| IN-EA     | reportable | ridge_all         |     8577 |     24.853 |              10.282 |  2.170 |   2.017 |            15.960 |               30.698 |        77.745 |
| IN-EA     | reportable | per_zone_ridge    |     8577 |     13.580 |              10.282 |  1.226 |   1.119 |             7.358 |               28.950 |        39.044 |
| IN-EA     | reportable | hybrid            |     8577 |     13.308 |              10.282 |  1.289 |   1.214 |             0.885 |               43.092 |        35.173 |
| IN-NE     | reportable | seasonal_naive    |     6433 |     20.126 |              20.126 |  1.000 |   1.000 |            -0.271 |               46.961 |        69.860 |
| IN-NE     | reportable | hour_weekday_mean |     6433 |     19.650 |              20.126 |  1.041 |   0.932 |            -9.247 |               70.403 |        48.198 |
| IN-NE     | reportable | ridge_all         |     6433 |     23.512 |              20.126 |  1.209 |   1.075 |            -1.331 |               54.982 |        53.852 |
| IN-NE     | reportable | per_zone_ridge    |     6433 |     78.975 |              20.126 |  4.041 |   5.655 |            73.957 |               16.478 |       356.272 |
| IN-NE     | reportable | hybrid            |     6433 |     22.490 |              20.126 |  1.109 |   1.010 |             3.743 |               49.324 |        60.128 |

## Stratification: day_type

| segment   | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| holiday   | reportable | seasonal_naive    |     1968 |     12.302 |              12.302 |  1.000 |   1.000 |             3.104 |               42.530 |        38.188 |
| holiday   | reportable | hour_weekday_mean |     1968 |     20.496 |              12.302 |  2.371 |   2.463 |            -5.511 |               61.331 |        44.546 |
| holiday   | reportable | ridge_all         |     1968 |     20.865 |              12.302 |  2.057 |   2.030 |             3.780 |               47.561 |        57.192 |
| holiday   | reportable | per_zone_ridge    |     1968 |     52.785 |              12.302 |  2.130 |   2.154 |            39.582 |               38.059 |       244.202 |
| holiday   | reportable | hybrid            |     1968 |     15.976 |              12.302 |  1.474 |   1.602 |             1.690 |               48.577 |        46.897 |
| weekday   | reportable | seasonal_naive    |    23297 |     11.894 |              11.894 |  1.000 |   1.000 |             0.197 |               40.619 |        34.911 |
| weekday   | reportable | hour_weekday_mean |    23297 |     19.484 |              11.894 |  2.099 |   2.064 |            -6.694 |               61.313 |        45.726 |
| weekday   | reportable | ridge_all         |    23297 |     19.693 |              11.894 |  1.790 |   1.654 |             4.351 |               45.418 |        56.411 |
| weekday   | reportable | per_zone_ridge    |    23297 |     25.713 |              11.894 |  1.761 |   1.679 |            14.226 |               35.009 |        73.699 |
| weekday   | reportable | hybrid            |    23297 |     13.942 |              11.894 |  1.236 |   1.285 |            -1.001 |               48.573 |        38.952 |
| weekend   | reportable | seasonal_naive    |     9768 |     11.435 |              11.435 |  1.000 |   1.000 |             0.255 |               40.039 |        33.298 |
| weekend   | reportable | hour_weekday_mean |     9768 |     18.999 |              11.435 |  2.114 |   2.127 |            -5.714 |               60.227 |        44.705 |
| weekend   | reportable | ridge_all         |     9768 |     20.064 |              11.435 |  1.888 |   1.777 |             4.847 |               44.554 |        58.255 |
| weekend   | reportable | per_zone_ridge    |     9768 |     27.851 |              11.435 |  1.869 |   1.804 |            16.679 |               34.797 |        72.656 |
| weekend   | reportable | hybrid            |     9768 |     14.148 |              11.435 |  1.286 |   1.361 |            -0.262 |               45.629 |        40.296 |

## Stratification: lead_time_hours

|   segment | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|----------:|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|    14.500 | reportable | seasonal_naive    |     1460 |     12.694 |              12.694 |  1.000 |   1.000 |             0.175 |               41.438 |        37.107 |
|    14.500 | reportable | hour_weekday_mean |     1460 |     23.024 |              12.694 |  2.514 |   2.436 |           -10.030 |               66.712 |        46.033 |
|    14.500 | reportable | ridge_all         |     1460 |     17.950 |              12.694 |  1.649 |   1.541 |            -1.536 |               55.959 |        43.090 |
|    14.500 | reportable | per_zone_ridge    |     1460 |     26.394 |              12.694 |  1.704 |   1.597 |            11.025 |               44.521 |        72.544 |
|    14.500 | reportable | hybrid            |     1460 |     14.246 |              12.694 |  1.225 |   1.211 |             0.302 |               44.726 |        38.470 |
|    15.500 | reportable | seasonal_naive    |     1460 |     12.870 |              12.870 |  1.000 |   1.000 |             0.257 |               41.438 |        38.212 |
|    15.500 | reportable | hour_weekday_mean |     1460 |     22.789 |              12.870 |  2.447 |   2.376 |            -9.719 |               65.342 |        45.644 |
|    15.500 | reportable | ridge_all         |     1460 |     17.993 |              12.870 |  1.632 |   1.526 |            -1.948 |               56.301 |        42.915 |
|    15.500 | reportable | per_zone_ridge    |     1460 |     25.914 |              12.870 |  1.676 |   1.568 |            10.505 |               43.836 |        68.489 |
|    15.500 | reportable | hybrid            |     1460 |     14.276 |              12.870 |  1.196 |   1.180 |             0.154 |               46.027 |        38.504 |
|    16.500 | reportable | seasonal_naive    |     1460 |     13.023 |              13.023 |  1.000 |   1.000 |             0.302 |               41.301 |        39.088 |
|    16.500 | reportable | hour_weekday_mean |     1460 |     22.462 |              13.023 |  2.365 |   2.299 |            -8.779 |               63.562 |        44.651 |
|    16.500 | reportable | ridge_all         |     1460 |     17.849 |              13.023 |  1.589 |   1.482 |            -1.888 |               55.479 |        42.056 |
|    16.500 | reportable | per_zone_ridge    |     1460 |     26.295 |              13.023 |  1.650 |   1.538 |            11.238 |               43.288 |        69.299 |
|    16.500 | reportable | hybrid            |     1460 |     14.435 |              13.023 |  1.182 |   1.174 |            -0.205 |               46.918 |        39.731 |
|    17.500 | reportable | seasonal_naive    |     1460 |     13.120 |              13.120 |  1.000 |   1.000 |             0.385 |               41.849 |        39.514 |
|    17.500 | reportable | hour_weekday_mean |     1460 |     22.480 |              13.120 |  2.343 |   2.269 |            -7.690 |               62.466 |        45.263 |
|    17.500 | reportable | ridge_all         |     1460 |     17.930 |              13.120 |  1.580 |   1.450 |            -1.298 |               55.137 |        42.561 |
|    17.500 | reportable | per_zone_ridge    |     1460 |     26.616 |              13.120 |  1.664 |   1.546 |            12.016 |               42.397 |        73.028 |
|    17.500 | reportable | hybrid            |     1460 |     14.865 |              13.120 |  1.216 |   1.220 |            -0.561 |               48.014 |        40.439 |
|    18.500 | reportable | seasonal_naive    |     1460 |     13.039 |              13.039 |  1.000 |   1.000 |             0.524 |               41.849 |        37.937 |
|    18.500 | reportable | hour_weekday_mean |     1460 |     22.283 |              13.039 |  2.380 |   2.332 |            -6.822 |               62.603 |        46.943 |
|    18.500 | reportable | ridge_all         |     1460 |     17.692 |              13.039 |  1.572 |   1.407 |            -0.384 |               53.904 |        42.583 |
|    18.500 | reportable | per_zone_ridge    |     1460 |     27.362 |              13.039 |  1.690 |   1.606 |            13.612 |               39.863 |        75.878 |
|    18.500 | reportable | hybrid            |     1460 |     15.001 |              13.039 |  1.237 |   1.261 |            -0.794 |               49.384 |        42.258 |
|    19.500 | reportable | seasonal_naive    |     1459 |     12.551 |              12.551 |  1.000 |   1.000 |             0.678 |               39.822 |        36.932 |
|    19.500 | reportable | hour_weekday_mean |     1459 |     20.831 |              12.551 |  2.421 |   2.422 |            -6.198 |               62.783 |        42.636 |
|    19.500 | reportable | ridge_all         |     1459 |     16.715 |              12.551 |  1.567 |   1.361 |             0.140 |               51.953 |        41.625 |
|    19.500 | reportable | per_zone_ridge    |     1459 |     28.509 |              12.551 |  1.716 |   1.714 |            16.249 |               36.463 |        80.068 |
|    19.500 | reportable | hybrid            |     1459 |     15.006 |              12.551 |  1.297 |   1.399 |            -1.541 |               50.720 |        45.473 |
|    20.500 | reportable | seasonal_naive    |     1459 |     11.914 |              11.914 |  1.000 |   1.000 |             0.836 |               38.588 |        33.468 |
|    20.500 | reportable | hour_weekday_mean |     1459 |     19.285 |              11.914 |  2.415 |   2.460 |            -5.906 |               61.823 |        40.962 |
|    20.500 | reportable | ridge_all         |     1459 |     16.485 |              11.914 |  1.580 |   1.381 |             1.169 |               48.115 |        42.717 |
|    20.500 | reportable | per_zone_ridge    |     1459 |     28.651 |              11.914 |  1.743 |   1.801 |            17.812 |               33.310 |        79.376 |
|    20.500 | reportable | hybrid            |     1459 |     15.599 |              11.914 |  1.436 |   1.587 |            -2.766 |               53.873 |        45.072 |
|    21.500 | reportable | seasonal_naive    |     1459 |     11.515 |              11.515 |  1.000 |   1.000 |             0.845 |               38.314 |        33.339 |
|    21.500 | reportable | hour_weekday_mean |     1459 |     19.087 |              11.515 |  2.205 |   2.210 |            -1.770 |               57.711 |        41.853 |
|    21.500 | reportable | ridge_all         |     1459 |     19.175 |              11.515 |  1.740 |   1.626 |             8.855 |               36.052 |        51.968 |
|    21.500 | reportable | per_zone_ridge    |     1459 |     28.757 |              11.515 |  1.893 |   1.814 |            20.944 |               26.662 |        81.116 |
|    21.500 | reportable | hybrid            |     1459 |     16.400 |              11.515 |  1.540 |   1.726 |            -1.695 |               51.337 |        46.552 |
|    22.500 | reportable | seasonal_naive    |     1459 |     11.421 |              11.421 |  1.000 |   1.000 |             0.740 |               38.862 |        34.846 |
|    22.500 | reportable | hour_weekday_mean |     1459 |     18.412 |              11.421 |  2.015 |   2.007 |            -0.545 |               55.929 |        45.171 |
|    22.500 | reportable | ridge_all         |     1459 |     21.815 |              11.421 |  1.913 |   1.841 |            13.837 |               30.158 |        65.972 |
|    22.500 | reportable | per_zone_ridge    |     1459 |     27.238 |              11.421 |  1.845 |   1.731 |            21.171 |               22.550 |        78.739 |
|    22.500 | reportable | hybrid            |     1459 |     15.802 |              11.421 |  1.512 |   1.679 |            -0.367 |               45.922 |        44.908 |
|    23.500 | reportable | seasonal_naive    |     1459 |     11.484 |              11.484 |  1.000 |   1.000 |             0.763 |               40.576 |        35.578 |
|    23.500 | reportable | hour_weekday_mean |     1459 |     17.625 |              11.484 |  1.858 |   1.847 |            -0.821 |               56.340 |        44.159 |
|    23.500 | reportable | ridge_all         |     1459 |     23.993 |              11.484 |  2.029 |   1.940 |            16.491 |               27.416 |        77.813 |
|    23.500 | reportable | per_zone_ridge    |     1459 |     25.969 |              11.484 |  1.668 |   1.563 |            20.934 |               21.453 |        74.156 |
|    23.500 | reportable | hybrid            |     1459 |     14.639 |              11.484 |  1.361 |   1.504 |            -0.344 |               45.579 |        39.620 |
|    24.500 | reportable | seasonal_naive    |     1459 |     11.588 |              11.588 |  1.000 |   1.000 |             0.757 |               39.685 |        35.493 |
|    24.500 | reportable | hour_weekday_mean |     1459 |     17.146 |              11.588 |  1.714 |   1.683 |            -0.390 |               55.860 |        45.822 |
|    24.500 | reportable | ridge_all         |     1459 |     26.182 |              11.588 |  2.145 |   2.002 |            19.170 |               26.456 |        84.093 |
|    24.500 | reportable | per_zone_ridge    |     1459 |     25.937 |              11.588 |  1.554 |   1.445 |            22.004 |               18.232 |        77.319 |
|    24.500 | reportable | hybrid            |     1459 |     14.833 |              11.588 |  1.308 |   1.391 |             0.493 |               45.031 |        40.646 |
|    25.500 | reportable | seasonal_naive    |     1459 |     11.559 |              11.559 |  1.000 |   1.000 |             0.703 |               40.918 |        35.120 |
|    25.500 | reportable | hour_weekday_mean |     1459 |     16.893 |              11.559 |  1.622 |   1.501 |            -0.193 |               53.873 |        44.777 |
|    25.500 | reportable | ridge_all         |     1459 |     26.718 |              11.559 |  2.213 |   2.033 |            19.371 |               26.388 |        84.255 |
|    25.500 | reportable | per_zone_ridge    |     1459 |     26.225 |              11.559 |  1.646 |   1.633 |            21.906 |               21.110 |        72.988 |
|    25.500 | reportable | hybrid            |     1459 |     14.388 |              11.559 |  1.233 |   1.284 |             0.008 |               46.813 |        41.447 |
|    26.500 | reportable | seasonal_naive    |     1459 |     11.675 |              11.675 |  1.000 |   1.000 |             0.666 |               40.439 |        34.833 |
|    26.500 | reportable | hour_weekday_mean |     1459 |     17.460 |              11.675 |  1.669 |   1.564 |            -0.510 |               53.598 |        45.429 |
|    26.500 | reportable | ridge_all         |     1459 |     26.326 |              11.675 |  2.193 |   1.978 |            18.464 |               26.594 |        81.047 |
|    26.500 | reportable | per_zone_ridge    |     1459 |     27.375 |              11.675 |  1.825 |   1.742 |            21.784 |               24.469 |        70.296 |
|    26.500 | reportable | hybrid            |     1459 |     14.525 |              11.675 |  1.217 |   1.204 |             0.562 |               47.019 |        40.977 |
|    27.500 | reportable | seasonal_naive    |     1459 |     11.906 |              11.906 |  1.000 |   1.000 |             0.672 |               40.576 |        35.358 |
|    27.500 | reportable | hour_weekday_mean |     1459 |     17.153 |              11.906 |  1.566 |   1.451 |             0.342 |               50.720 |        43.625 |
|    27.500 | reportable | ridge_all         |     1459 |     26.295 |              11.906 |  2.186 |   1.953 |            18.805 |               24.812 |        79.244 |
|    27.500 | reportable | per_zone_ridge    |     1459 |     27.766 |              11.906 |  1.831 |   1.750 |            22.571 |               23.235 |        68.755 |
|    27.500 | reportable | hybrid            |     1459 |     14.494 |              11.906 |  1.174 |   1.157 |             1.657 |               44.277 |        39.984 |
|    28.500 | reportable | seasonal_naive    |     1459 |     11.688 |              11.688 |  1.000 |   1.000 |             0.532 |               41.330 |        34.552 |
|    28.500 | reportable | hour_weekday_mean |     1459 |     17.174 |              11.688 |  1.691 |   1.608 |            -2.229 |               54.284 |        40.252 |
|    28.500 | reportable | ridge_all         |     1459 |     23.233 |              11.688 |  2.007 |   1.799 |            15.217 |               26.114 |        69.184 |
|    28.500 | reportable | per_zone_ridge    |     1459 |     28.063 |              11.688 |  1.835 |   1.738 |            21.515 |               26.731 |        72.833 |
|    28.500 | reportable | hybrid            |     1459 |     13.983 |              11.688 |  1.175 |   1.156 |             0.183 |               47.430 |        39.409 |
|    29.500 | reportable | seasonal_naive    |     1459 |     11.645 |              11.645 |  1.000 |   1.000 |             0.503 |               42.152 |        34.654 |
|    29.500 | reportable | hour_weekday_mean |     1459 |     16.876 |              11.645 |  1.735 |   1.656 |            -2.974 |               55.175 |        37.396 |
|    29.500 | reportable | ridge_all         |     1459 |     20.239 |              11.645 |  1.807 |   1.640 |            11.876 |               28.033 |        56.915 |
|    29.500 | reportable | per_zone_ridge    |     1459 |     29.272 |              11.645 |  1.846 |   1.754 |            21.656 |               28.307 |        74.967 |
|    29.500 | reportable | hybrid            |     1459 |     13.583 |              11.645 |  1.165 |   1.178 |             0.078 |               47.156 |        37.466 |
|    30.500 | reportable | seasonal_naive    |     1459 |     11.140 |              11.140 |  1.000 |   1.000 |             0.569 |               40.096 |        32.292 |
|    30.500 | reportable | hour_weekday_mean |     1459 |     16.259 |              11.140 |  1.813 |   1.732 |            -3.441 |               55.997 |        36.763 |
|    30.500 | reportable | ridge_all         |     1459 |     17.272 |              11.140 |  1.652 |   1.514 |             7.736 |               34.750 |        46.800 |
|    30.500 | reportable | per_zone_ridge    |     1459 |     31.130 |              11.140 |  1.907 |   1.819 |            22.558 |               30.912 |        87.749 |
|    30.500 | reportable | hybrid            |     1459 |     13.196 |              11.140 |  1.177 |   1.208 |             0.269 |               47.293 |        37.000 |
|    31.500 | reportable | seasonal_naive    |     1459 |     10.634 |              10.634 |  1.000 |   1.000 |             0.671 |               38.040 |        30.366 |
|    31.500 | reportable | hour_weekday_mean |     1459 |     16.854 |              10.634 |  1.976 |   1.847 |            -5.071 |               58.465 |        37.497 |
|    31.500 | reportable | ridge_all         |     1459 |     15.558 |              10.634 |  1.588 |   1.409 |             1.880 |               47.361 |        42.347 |
|    31.500 | reportable | per_zone_ridge    |     1459 |     32.222 |              10.634 |  1.957 |   1.877 |            21.615 |               37.697 |       100.739 |
|    31.500 | reportable | hybrid            |     1459 |     12.669 |              10.634 |  1.175 |   1.188 |             0.514 |               42.769 |        36.468 |
|    32.500 | reportable | seasonal_naive    |     1459 |     10.444 |              10.444 |  1.000 |   1.000 |             0.230 |               38.657 |        30.050 |
|    32.500 | reportable | hour_weekday_mean |     1459 |     18.905 |              10.444 |  2.386 |   2.240 |           -11.206 |               67.101 |        43.164 |
|    32.500 | reportable | ridge_all         |     1459 |     16.124 |              10.444 |  1.767 |   1.592 |            -5.909 |               61.618 |        36.780 |
|    32.500 | reportable | per_zone_ridge    |     1459 |     31.018 |              10.444 |  2.083 |   1.966 |            14.840 |               45.922 |        87.019 |
|    32.500 | reportable | hybrid            |     1459 |     12.831 |              10.444 |  1.299 |   1.364 |            -2.655 |               51.062 |        38.078 |
|    33.500 | reportable | seasonal_naive    |     1459 |     10.669 |              10.669 |  1.000 |   1.000 |            -0.252 |               40.850 |        30.912 |
|    33.500 | reportable | hour_weekday_mean |     1459 |     19.565 |              10.669 |  2.463 |   2.432 |           -14.450 |               69.705 |        48.454 |
|    33.500 | reportable | ridge_all         |     1459 |     17.621 |              10.669 |  1.955 |   1.833 |            -8.431 |               65.661 |        40.618 |
|    33.500 | reportable | per_zone_ridge    |     1459 |     28.704 |              10.669 |  2.085 |   2.014 |            10.256 |               47.293 |        67.660 |
|    33.500 | reportable | hybrid            |     1459 |     12.627 |              10.669 |  1.285 |   1.357 |            -3.474 |               53.873 |        36.202 |
|    34.500 | reportable | seasonal_naive    |     1459 |     11.120 |              11.120 |  1.000 |   1.000 |            -0.399 |               41.193 |        31.536 |
|    34.500 | reportable | hour_weekday_mean |     1459 |     19.884 |              11.120 |  2.371 |   2.417 |           -14.694 |               69.020 |        51.286 |
|    34.500 | reportable | ridge_all         |     1459 |     18.315 |              11.120 |  1.983 |   1.905 |            -7.897 |               64.496 |        42.851 |
|    34.500 | reportable | per_zone_ridge    |     1459 |     27.663 |              11.120 |  2.033 |   2.007 |             8.901 |               46.813 |        60.358 |
|    34.500 | reportable | hybrid            |     1459 |     12.733 |              11.120 |  1.243 |   1.290 |            -2.039 |               49.417 |        34.714 |
|    35.500 | reportable | seasonal_naive    |     1459 |     11.470 |              11.470 |  1.000 |   1.000 |            -0.460 |               41.672 |        32.500 |
|    35.500 | reportable | hour_weekday_mean |     1459 |     20.107 |              11.470 |  2.275 |   2.366 |           -14.304 |               67.992 |        51.384 |
|    35.500 | reportable | ridge_all         |     1459 |     18.545 |              11.470 |  1.912 |   1.850 |            -7.175 |               63.263 |        43.679 |
|    35.500 | reportable | per_zone_ridge    |     1459 |     27.245 |              11.470 |  1.995 |   1.970 |             8.350 |               45.648 |        59.980 |
|    35.500 | reportable | hybrid            |     1459 |     12.706 |              11.470 |  1.218 |   1.232 |            -1.757 |               48.732 |        34.838 |
|    36.500 | reportable | seasonal_naive    |     1459 |     11.679 |              11.679 |  1.000 |   1.000 |            -0.451 |               42.358 |        33.162 |
|    36.500 | reportable | hour_weekday_mean |     1459 |     20.358 |              11.679 |  2.218 |   2.321 |           -13.756 |               67.443 |        49.824 |
|    36.500 | reportable | ridge_all         |     1459 |     18.432 |              11.679 |  1.844 |   1.802 |            -7.008 |               63.674 |        44.281 |
|    36.500 | reportable | per_zone_ridge    |     1459 |     27.224 |              11.679 |  1.982 |   1.943 |             7.999 |               45.785 |        59.043 |
|    36.500 | reportable | hybrid            |     1459 |     12.644 |              11.679 |  1.201 |   1.223 |            -1.783 |               48.047 |        35.141 |
|    37.500 | reportable | seasonal_naive    |     1471 |     12.079 |              12.079 |  1.000 |   1.000 |            -0.209 |               41.536 |        36.787 |
|    37.500 | reportable | hour_weekday_mean |     1471 |     22.782 |              12.079 |  2.624 |   2.530 |           -11.300 |               69.680 |        46.183 |
|    37.500 | reportable | ridge_all         |     1471 |     18.247 |              12.079 |  1.734 |   1.635 |            -2.482 |               57.308 |        46.183 |
|    37.500 | reportable | per_zone_ridge    |     1471 |     26.385 |              12.079 |  1.710 |   1.577 |            10.624 |               46.295 |        73.379 |
|    37.500 | reportable | hybrid            |     1471 |     13.250 |              12.079 |  1.231 |   1.281 |             0.303 |               44.663 |        36.115 |

## Stratification: zone_temperature_band

| segment             | status                     | model             |   n_rows | mape_pct           | baseline_mape_pct   | mase               | rmsse              | signed_bias_pct      | shortfall_freq_pct   | p95_abs_pct        |
|:--------------------|:---------------------------|:------------------|---------:|:-------------------|:--------------------|:-------------------|:-------------------|:---------------------|:---------------------|:-------------------|
| IN-NO: < 20 C       | reportable                 | seasonal_naive    |     1927 | 17.345920260690395 | 17.345920260690395  | 1.0                | 1.0                | 1.9632208534287672   | 48.46912298910223    | 43.6730821761413   |
| IN-NO: < 20 C       | reportable                 | hour_weekday_mean |     1927 | 27.787541842509    | 17.345920260690395  | 1.4629280285828505 | 1.448781712789025  | 25.226058795802203   | 13.7519460300986     | 80.70710082565249  |
| IN-NO: < 20 C       | reportable                 | ridge_all         |     1927 | 29.101805978278918 | 17.345920260690395  | 1.4734447210631507 | 1.4267304438199346 | 27.02067608407689    | 11.41670991177997    | 79.98679718581224  |
| IN-NO: < 20 C       | reportable                 | per_zone_ridge    |     1927 | 20.940201304563743 | 17.345920260690395  | 1.1122502527561247 | 1.151718111867653  | 14.744401828821205   | 28.12662169174883    | 67.39422138124428  |
| IN-NO: < 20 C       | reportable                 | hybrid            |     1927 | 17.43116802912328  | 17.345920260690395  | 1.0844897554960284 | 1.1279042668524002 | -2.937052487210131   | 52.67254800207577    | 38.88771621507095  |
| IN-NO: 20 to < 30 C | reportable                 | seasonal_naive    |     2817 | 10.319233187587864 | 10.319233187587864  | 1.0                | 1.0                | 0.8838900467931186   | 38.516151934682284   | 27.234494403603993 |
| IN-NO: 20 to < 30 C | reportable                 | hour_weekday_mean |     2817 | 21.965618592421237 | 10.319233187587864  | 2.3817574441094362 | 2.2480173991954002 | -18.95705522499036   | 82.0376286829961     | 49.542263945995906 |
| IN-NO: 20 to < 30 C | reportable                 | ridge_all         |     2817 | 14.515501469202135 | 10.319233187587864  | 1.4277062194903722 | 1.3256151977421955 | -1.7116518933077824  | 58.57294994675186    | 36.672163012870335 |
| IN-NO: 20 to < 30 C | reportable                 | per_zone_ridge    |     2817 | 14.544446747457425 | 10.319233187587864  | 1.511719726509065  | 1.4766933986303932 | -5.646203152757625   | 58.60844870429535    | 36.03405230484697  |
| IN-NO: 20 to < 30 C | reportable                 | hybrid            |     2817 | 11.697412489863934 | 10.319233187587864  | 1.1557470551713183 | 1.1820547603413638 | -1.1207083151452448  | 45.97089101881434    | 32.61798010557536  |
| IN-NO: 30 to < 45 C | reportable                 | seasonal_naive    |     1931 | 11.964818068856585 | 11.964818068856585  | 1.0                | 1.0                | -3.5468724807246823  | 52.511651993785605   | 28.772443837858166 |
| IN-NO: 30 to < 45 C | reportable                 | hour_weekday_mean |     1931 | 29.996564283828334 | 11.964818068856585  | 2.520211418503177  | 2.18009051334655   | -29.91279964362475   | 98.80890730191611    | 52.712715984612    |
| IN-NO: 30 to < 45 C | reportable                 | ridge_all         |     1931 | 16.580793376614277 | 11.964818068856585  | 1.4493190337564448 | 1.3275645185977087 | -15.826624408221505  | 90.52304505437597    | 31.9993904086145   |
| IN-NO: 30 to < 45 C | reportable                 | per_zone_ridge    |     1931 | 16.67421926821841  | 11.964818068856585  | 1.3858597114218882 | 1.3295310644352    | -13.747857275415331  | 77.67995857068877    | 38.79888181399771  |
| IN-NO: 30 to < 45 C | reportable                 | hybrid            |     1931 | 8.465374672401213  | 11.964818068856585  | 0.7112131999098191 | 0.7136654596240521 | -5.000332442365211   | 63.1279129984464     | 21.531994393339424 |
| IN-NO: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | seasonal_naive    |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | hour_weekday_mean |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | ridge_all         |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | per_zone_ridge    |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | hybrid            |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: 20 to < 30 C | reportable                 | seasonal_naive    |     5269 | 6.792567240418472  | 6.792567240418472   | 1.0                | 1.0                | 0.45788456927566323  | 33.953311823875495   | 19.955428234321673 |
| IN-WE: 20 to < 30 C | reportable                 | hour_weekday_mean |     5269 | 18.185142997740847 | 6.792567240418472   | 2.806829728557908  | 2.560272380853345  | -13.661043013645582  | 73.69519832985387    | 37.81315799759783  |
| IN-WE: 20 to < 30 C | reportable                 | ridge_all         |     5269 | 15.021416389234398 | 6.792567240418472   | 2.206398959301051  | 1.9612268320644346 | 1.2225547190642345   | 46.32757639020687    | 33.85474458963812  |
| IN-WE: 20 to < 30 C | reportable                 | per_zone_ridge    |     5269 | 16.690230269343864 | 6.792567240418472   | 2.454340317369329  | 2.176070679926535  | 3.278992448510935    | 37.483393433289045   | 35.9124558246071   |
| IN-WE: 20 to < 30 C | reportable                 | hybrid            |     5269 | 10.089391761515438 | 6.792567240418472   | 1.5323616000111857 | 1.6701518128482484 | -2.724574289643514   | 39.6280129056747     | 32.82040301574454  |
| IN-WE: 30 to < 45 C | reportable                 | seasonal_naive    |     1361 | 6.568622730388593  | 6.568622730388593   | 1.0                | 1.0                | 0.7803128469210793   | 33.87215282880235    | 17.07349150402441  |
| IN-WE: 30 to < 45 C | reportable                 | hour_weekday_mean |     1361 | 9.611959306716306  | 6.568622730388593   | 1.5259582099324036 | 1.5140530690252891 | -7.855315989138715   | 73.91623806024981    | 23.099097929270577 |
| IN-WE: 30 to < 45 C | reportable                 | ridge_all         |     1361 | 9.700803068051416  | 6.568622730388593   | 1.445477498012013  | 1.446300296850736  | 4.2525117490718785   | 25.42248346803821    | 24.774803503823552 |
| IN-WE: 30 to < 45 C | reportable                 | per_zone_ridge    |     1361 | 13.14358364925513  | 6.568622730388593   | 1.941119325495058  | 1.8035661692332359 | 11.993816457501282   | 6.318883174136664    | 29.64886365578915  |
| IN-WE: 30 to < 45 C | reportable                 | hybrid            |     1361 | 6.885747692194982  | 6.568622730388593   | 1.040255250071576  | 1.036126741778954  | 1.708389277165861    | 30.639235855988247   | 17.004564626702944 |
| IN-WE: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: < 20 C       | reportable                 | seasonal_naive    |     1080 | 13.018098268644868 | 13.018098268644868  | 1.0                | 1.0                | 2.2926583081539755   | 37.77777777777778    | 35.25534679801804  |
| IN-SO: < 20 C       | reportable                 | hour_weekday_mean |     1080 | 17.42563934315582  | 13.018098268644868  | 1.5977905607588243 | 1.672422953575116  | -4.183057266914459   | 51.57407407407407    | 41.705152711334    |
| IN-SO: < 20 C       | reportable                 | ridge_all         |     1080 | 19.860065327372165 | 13.018098268644868  | 1.5836288524679991 | 1.4519632812243504 | 7.712682567938504    | 35.74074074074074    | 54.45487861249051  |
| IN-SO: < 20 C       | reportable                 | per_zone_ridge    |     1080 | 24.589382181066263 | 13.018098268644868  | 1.9359217109228481 | 1.734933545844078  | 14.175597744749563   | 24.444444444444443   | 65.9464215823938   |
| IN-SO: < 20 C       | reportable                 | hybrid            |     1080 | 18.060988165959383 | 13.018098268644868  | 1.4177459311650393 | 1.325663903412149  | -2.4508396395056207  | 56.2037037037037     | 45.72125268875669  |
| IN-SO: 20 to < 30 C | reportable                 | seasonal_naive    |     4919 | 8.997057226046609  | 8.997057226046609   | 1.0                | 1.0                | -0.9402019402367378  | 43.26082537101037    | 24.485193933523252 |
| IN-SO: 20 to < 30 C | reportable                 | hour_weekday_mean |     4919 | 21.510531372770444 | 8.997057226046609   | 2.62572549506833   | 2.486954976098462  | -16.688371853959218  | 76.80422850172799    | 44.34514967273591  |
| IN-SO: 20 to < 30 C | reportable                 | ridge_all         |     4919 | 15.954499885976654 | 8.997057226046609   | 1.8631660072724407 | 1.7147358410001323 | -3.386316804899062   | 56.71884529375889    | 32.50315156024174  |
| IN-SO: 20 to < 30 C | reportable                 | per_zone_ridge    |     4919 | 19.06169118170691  | 8.997057226046609   | 2.183039729915665  | 2.0638767654358574 | -1.343135890824543   | 52.6529782476113     | 42.305867916399485 |
| IN-SO: 20 to < 30 C | reportable                 | hybrid            |     4919 | 12.616961420511068 | 8.997057226046609   | 1.4346404362549245 | 1.381539947126906  | -4.321389317625367   | 60.01219760113844    | 31.276090371339233 |
| IN-SO: 30 to < 45 C | reportable                 | seasonal_naive    |      675 | 9.12548397066801   | 9.12548397066801    | 1.0                | 1.0                | 0.8116293396040325   | 42.074074074074076   | 26.044358811792822 |
| IN-SO: 30 to < 45 C | reportable                 | hour_weekday_mean |      675 | 10.647683446364857 | 9.12548397066801    | 1.164665702007041  | 1.1088240125949773 | 1.902869344346352    | 31.25925925925926    | 26.61041660049059  |
| IN-SO: 30 to < 45 C | reportable                 | ridge_all         |      675 | 14.010027802380709 | 9.12548397066801    | 1.4692041790163635 | 1.2953002960723827 | 11.608029623791985   | 11.703703703703704   | 30.903312120299656 |
| IN-SO: 30 to < 45 C | reportable                 | per_zone_ridge    |      675 | 13.851498962201116 | 9.12548397066801    | 1.4966411640121122 | 1.3401480638090315 | 9.653155164782358    | 16.14814814814815    | 30.240833421537072 |
| IN-SO: 30 to < 45 C | reportable                 | hybrid            |      675 | 10.07449042280493  | 9.12548397066801    | 1.100189960176079  | 1.0622278549148876 | 2.987725743937039    | 33.18518518518518    | 25.975812337293675 |
| IN-SO: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: < 20 C       | reportable                 | seasonal_naive    |      837 | 7.101245994653031  | 7.101245994653031   | 1.0                | 1.0                | -0.1944892246278178  | 35.00597371565114    | 18.369391826378827 |
| IN-EA: < 20 C       | reportable                 | hour_weekday_mean |      837 | 8.975429776885811  | 7.101245994653031   | 1.2529797521159332 | 1.1682710013727826 | 1.5330838237356412   | 37.27598566308244    | 19.125339504821707 |
| IN-EA: < 20 C       | reportable                 | ridge_all         |      837 | 12.450305215848102 | 7.101245994653031   | 1.8185078577640545 | 1.625856825835197  | -11.468734684940966  | 86.85782556750299    | 22.935971259642084 |
| IN-EA: < 20 C       | reportable                 | per_zone_ridge    |      837 | 9.863920495493696  | 7.101245994653031   | 1.3268540916265934 | 1.2631528076823269 | 5.597865354860649    | 25.686977299880525   | 23.64147435628349  |
| IN-EA: < 20 C       | reportable                 | hybrid            |      837 | 18.660653251681317 | 7.101245994653031   | 2.693337892856422  | 2.6329870375845132 | -15.184126608230404  | 74.55197132616487    | 42.8543940002257   |
| IN-EA: 20 to < 30 C | reportable                 | seasonal_naive    |     5921 | 10.024945005779133 | 10.024945005779133  | 1.0                | 1.0                | 0.8939525212677693   | 37.15588583009627    | 29.16025272831706  |
| IN-EA: 20 to < 30 C | reportable                 | hour_weekday_mean |     5921 | 14.0273160479246   | 10.024945005779133  | 1.3247844806363631 | 1.138997932273714  | 4.524020316920003    | 39.18257051173788    | 34.53560753488254  |
| IN-EA: 20 to < 30 C | reportable                 | ridge_all         |     5921 | 19.274943854483865 | 10.024945005779133  | 1.775646869187847  | 1.6273952810192083 | 9.882753619021752    | 31.599391994595504   | 60.75616905410999  |
| IN-EA: 20 to < 30 C | reportable                 | per_zone_ridge    |     5921 | 12.303082204302028 | 10.024945005779133  | 1.1514651390457722 | 1.0570711983767633 | 5.09599359248678     | 33.32207397399088    | 35.247164171025766 |
| IN-EA: 20 to < 30 C | reportable                 | hybrid            |     5921 | 11.922759222144682 | 10.024945005779133  | 1.175938280481011  | 1.0877336007837906 | 0.5065083072324809   | 43.89461239655464    | 30.53422193097629  |
| IN-EA: 30 to < 45 C | reportable                 | seasonal_naive    |     1819 | 12.582008661993044 | 12.582008661993044  | 1.0                | 1.0                | 4.943018375721486    | 30.566245189664652   | 34.744630146381866 |
| IN-EA: 30 to < 45 C | reportable                 | hour_weekday_mean |     1819 | 26.01265705823572  | 12.582008661993044  | 1.8847641280062326 | 1.5950305677940335 | 22.447348132940203   | 13.743815283122595   | 56.67343136644728  |
| IN-EA: 30 to < 45 C | reportable                 | ridge_all         |     1819 | 48.715666315719496 | 12.582008661993044  | 3.4981952323861916 | 2.9651387128597397 | 48.36364587842718    | 1.9241341396371632   | 98.91931564336272  |
| IN-EA: 30 to < 45 C | reportable                 | per_zone_ridge    |     1819 | 19.446744516614288 | 12.582008661993044  | 1.4257843230295135 | 1.2674422884868544 | 15.529972292543993   | 16.21770203408466    | 49.26084762105896  |
| IN-EA: 30 to < 45 C | reportable                 | hybrid            |     1819 | 15.354324290247362 | 12.582008661993044  | 1.1959924241227458 | 1.1322772392745408 | 9.509321852962595    | 26.00329851566795    | 40.98630725613797  |
| IN-EA: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: < 20 C       | reportable                 | seasonal_naive    |     1696 | 25.097495600175268 | 25.097495600175268  | 1.0                | 1.0                | -3.417991952848458   | 49.764150943396224   | 77.04701388725155  |
| IN-NE: < 20 C       | reportable                 | hour_weekday_mean |     1696 | 23.020131872406367 | 25.097495600175268  | 0.9861702246256729 | 0.8803516095533449 | -16.878512293794195  | 80.18867924528303    | 49.48176271022928  |
| IN-NE: < 20 C       | reportable                 | ridge_all         |     1696 | 27.645236646648378 | 25.097495600175268  | 1.240997106117492  | 1.0766999384137796 | -23.75695585489654   | 86.79245283018868    | 48.886775483993745 |
| IN-NE: < 20 C       | reportable                 | per_zone_ridge    |     1696 | 168.8978881004107  | 25.097495600175268  | 6.998718497192337  | 7.541598548443584  | 168.56716559716534   | 1.0023584905660377   | 519.363695276025   |
| IN-NE: < 20 C       | reportable                 | hybrid            |     1696 | 25.07388505262475  | 25.097495600175268  | 1.0498201407459613 | 0.9786902380736562 | -4.973561537425785   | 53.007075471698116   | 57.34534581193019  |
| IN-NE: 20 to < 30 C | reportable                 | seasonal_naive    |     3931 | 18.781538480990427 | 18.781538480990427  | 1.0                | 1.0                | 0.0503808934024838   | 47.77410328160773    | 60.084181250598206 |
| IN-NE: 20 to < 30 C | reportable                 | hour_weekday_mean |     3931 | 18.884862399873825 | 18.781538480990427  | 1.0694616645258122 | 0.9694512952301858 | -7.844678348852912   | 67.71813787840244    | 45.86641785205206  |
| IN-NE: 20 to < 30 C | reportable                 | ridge_all         |     3931 | 20.530993978310683 | 18.781538480990427  | 1.1070637226235693 | 1.009064582415978  | 2.36992083881432     | 51.28466039175782    | 53.30845801038064  |
| IN-NE: 20 to < 30 C | reportable                 | per_zone_ridge    |     3931 | 52.267870954244096 | 18.781538480990427  | 2.7763779623864777 | 4.160349869670027  | 45.19284978300038    | 22.131773085728824   | 240.33523107667088 |
| IN-NE: 20 to < 30 C | reportable                 | hybrid            |     3931 | 20.9539214434653   | 18.781538480990427  | 1.0806518184361937 | 0.9923005941571466 | 6.820774250872887    | 44.645128466039175   | 59.46649730656428  |
| IN-NE: 30 to < 45 C | reportable                 | seasonal_naive    |      806 | 16.224917586163656 | 16.224917586163656  | 1.0                | 1.0                | 4.780485595118385    | 37.096774193548384   | 58.095961401945985 |
| IN-NE: 30 to < 45 C | reportable                 | hour_weekday_mean |      806 | 16.291618707413917 | 16.224917586163656  | 1.0523584081459574 | 0.915275435129705  | -0.02798349468534517 | 62.903225806451616   | 52.540027152617114 |
| IN-NE: 30 to < 45 C | reportable                 | ridge_all         |      806 | 29.351218673718403 | 16.224917586163656  | 1.7833820193461245 | 1.540433200722803  | 27.805416138501354   | 6.079404466501241    | 97.86385951496806  |
| IN-NE: 30 to < 45 C | reportable                 | per_zone_ridge    |      806 | 20.014882517551573 | 16.224917586163656  | 1.2511500432881852 | 1.1279021978375663 | 15.16122143831373    | 21.464019851116625   | 71.12681108570276  |
| IN-NE: 30 to < 45 C | reportable                 | hybrid            |      806 | 24.545517246621227 | 16.224917586163656  | 1.5367882653091247 | 1.3275097997567837 | 7.0725567205451805   | 64.39205955334988    | 78.29687618396018  |
| IN-NE: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | hybrid            |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |

## Stratification: time_rolling

| segment    | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:-----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| 2024-09-30 | reportable | seasonal_naive    |      720 |     17.588 |              17.588 |  1.000 |   1.000 |            -6.403 |               55.972 |        30.921 |
| 2024-09-30 | reportable | hour_weekday_mean |      720 |     14.087 |              17.588 |  0.777 |   0.702 |            -1.121 |               53.472 |        19.849 |
| 2024-09-30 | reportable | ridge_all         |      720 |     18.864 |              17.588 |  0.991 |   1.038 |             7.669 |               33.194 |        53.116 |
| 2024-09-30 | reportable | per_zone_ridge    |      720 |     14.013 |              17.588 |  0.748 |   0.685 |             1.900 |               52.361 |        26.613 |
| 2024-09-30 | reportable | hybrid            |      720 |     14.494 |              17.588 |  0.781 |   0.719 |             1.065 |               52.778 |        25.733 |
| 2024-10-31 | reportable | seasonal_naive    |      720 |     15.093 |              15.093 |  1.000 |   1.000 |             4.663 |               42.083 |        35.171 |
| 2024-10-31 | reportable | hour_weekday_mean |      720 |     16.058 |              15.093 |  1.182 |   1.105 |           -11.689 |               77.778 |        23.783 |
| 2024-10-31 | reportable | ridge_all         |      720 |     16.489 |              15.093 |  1.164 |   1.198 |            -4.384 |               52.917 |        37.586 |
| 2024-10-31 | reportable | per_zone_ridge    |      720 |     15.862 |              15.093 |  1.167 |   1.094 |           -11.532 |               77.778 |        23.360 |
| 2024-10-31 | reportable | hybrid            |      720 |     13.921 |              15.093 |  0.996 |   0.931 |            -6.924 |               75.972 |        22.115 |
| 2024-11-30 | reportable | seasonal_naive    |     1402 |     16.178 |              16.178 |  1.000 |   1.000 |             7.583 |               29.886 |        47.941 |
| 2024-11-30 | reportable | hour_weekday_mean |     1402 |     13.670 |              16.178 |  0.867 |   0.839 |             4.404 |               34.593 |        31.593 |
| 2024-11-30 | reportable | ridge_all         |     1402 |     22.516 |              16.178 |  1.516 |   1.601 |            17.037 |               20.899 |        65.835 |
| 2024-11-30 | reportable | per_zone_ridge    |     1402 |     20.587 |              16.178 |  1.416 |   1.455 |            18.438 |               11.484 |        45.750 |
| 2024-11-30 | reportable | hybrid            |     1402 |     15.977 |              16.178 |  0.992 |   1.006 |            11.685 |               19.258 |        44.792 |
| 2024-12-31 | reportable | seasonal_naive    |     3363 |     18.545 |              18.545 |  1.000 |   1.000 |            -3.899 |               46.476 |        71.588 |
| 2024-12-31 | reportable | hour_weekday_mean |     3363 |     21.437 |              18.545 |  1.303 |   1.353 |            -1.022 |               51.710 |        56.342 |
| 2024-12-31 | reportable | ridge_all         |     3363 |     25.320 |              18.545 |  1.416 |   1.248 |             6.330 |               41.748 |        63.692 |
| 2024-12-31 | reportable | per_zone_ridge    |     3363 |     68.598 |              18.545 |  1.794 |   1.619 |            62.696 |               21.023 |       330.856 |
| 2024-12-31 | reportable | hybrid            |     3363 |     27.331 |              18.545 |  1.977 |   2.012 |           -16.518 |               74.219 |        53.295 |
| 2025-01-31 | reportable | seasonal_naive    |     3600 |     12.006 |              12.006 |  1.000 |   1.000 |             1.430 |               40.444 |        35.122 |
| 2025-01-31 | reportable | hour_weekday_mean |     3600 |     18.000 |              12.006 |  1.868 |   2.075 |            -3.613 |               59.361 |        46.896 |
| 2025-01-31 | reportable | ridge_all         |     3600 |     17.504 |              12.006 |  1.491 |   1.428 |             0.484 |               50.444 |        46.446 |
| 2025-01-31 | reportable | per_zone_ridge    |     3600 |     58.550 |              12.006 |  1.813 |   1.729 |            50.975 |               26.417 |       346.217 |
| 2025-01-31 | reportable | hybrid            |     3600 |     13.816 |              12.006 |  1.291 |   1.285 |            -0.669 |               44.639 |        36.217 |
| 2025-02-28 | reportable | seasonal_naive    |     3600 |     10.009 |              10.009 |  1.000 |   1.000 |            -1.979 |               48.500 |        34.845 |
| 2025-02-28 | reportable | hour_weekday_mean |     3600 |     14.116 |              10.009 |  2.461 |   2.946 |            -8.085 |               70.750 |        34.346 |
| 2025-02-28 | reportable | ridge_all         |     3600 |     14.393 |              10.009 |  1.905 |   1.900 |            -0.090 |               49.250 |        33.331 |
| 2025-02-28 | reportable | per_zone_ridge    |     3600 |     28.435 |              10.009 |  1.997 |   2.123 |            19.058 |               37.139 |       104.452 |
| 2025-02-28 | reportable | hybrid            |     3600 |     14.668 |              10.009 |  2.285 |   2.513 |            -5.977 |               59.500 |        35.441 |
| 2025-03-31 | reportable | seasonal_naive    |     3600 |     10.407 |              10.407 |  1.000 |   1.000 |            -0.316 |               41.778 |        27.475 |
| 2025-03-31 | reportable | hour_weekday_mean |     3600 |     14.392 |              10.407 |  2.136 |   2.377 |            -8.134 |               64.306 |        34.713 |
| 2025-03-31 | reportable | ridge_all         |     3600 |     14.870 |              10.407 |  1.627 |   1.615 |             3.416 |               43.722 |        40.154 |
| 2025-03-31 | reportable | per_zone_ridge    |     3600 |     17.693 |              10.407 |  1.715 |   1.708 |             7.186 |               36.194 |        48.232 |
| 2025-03-31 | reportable | hybrid            |     3600 |     14.769 |              10.407 |  1.247 |   1.197 |             8.380 |               27.806 |        43.643 |
| 2025-04-30 | reportable | seasonal_naive    |     3600 |     12.799 |              12.799 |  1.000 |   1.000 |            -0.092 |               46.111 |        42.137 |
| 2025-04-30 | reportable | hour_weekday_mean |     3600 |     20.028 |              12.799 |  2.400 |   2.581 |            -6.368 |               60.972 |        43.387 |
| 2025-04-30 | reportable | ridge_all         |     3600 |     20.270 |              12.799 |  1.854 |   1.953 |             7.454 |               40.556 |        68.123 |
| 2025-04-30 | reportable | per_zone_ridge    |     3600 |     17.700 |              12.799 |  1.611 |   1.666 |             5.968 |               37.222 |        46.339 |
| 2025-04-30 | reportable | hybrid            |     3600 |     14.088 |              12.799 |  1.129 |   1.144 |             5.800 |               36.667 |        42.510 |
| 2025-05-31 | reportable | seasonal_naive    |     3600 |     16.752 |              16.752 |  1.000 |   1.000 |             4.796 |               33.444 |        44.957 |
| 2025-05-31 | reportable | hour_weekday_mean |     3600 |     23.115 |              16.752 |  1.624 |   1.590 |            -2.502 |               54.722 |        54.825 |
| 2025-05-31 | reportable | ridge_all         |     3600 |     23.945 |              16.752 |  1.321 |   1.288 |            11.142 |               41.389 |        86.676 |
| 2025-05-31 | reportable | per_zone_ridge    |     3600 |     21.482 |              16.752 |  1.276 |   1.231 |             9.689 |               32.583 |        58.297 |
| 2025-05-31 | reportable | hybrid            |     3600 |     18.399 |              16.752 |  0.993 |   0.957 |             8.366 |               33.361 |        51.951 |
| 2025-06-30 | reportable | seasonal_naive    |     3482 |     10.623 |              10.623 |  1.000 |   1.000 |            -1.511 |               50.172 |        24.632 |
| 2025-06-30 | reportable | hour_weekday_mean |     3482 |     23.065 |              10.623 |  2.299 |   2.143 |           -11.071 |               65.882 |        49.142 |
| 2025-06-30 | reportable | ridge_all         |     3482 |     21.483 |              10.623 |  1.850 |   1.708 |             1.403 |               53.705 |        62.882 |
| 2025-06-30 | reportable | per_zone_ridge    |     3482 |     18.364 |              10.623 |  1.802 |   1.766 |            -1.081 |               48.047 |        40.849 |
| 2025-06-30 | reportable | hybrid            |     3482 |      9.798 |              10.623 |  0.829 |   0.810 |            -5.900 |               61.459 |        22.583 |
| 2025-08-31 | reportable | seasonal_naive    |     3482 |      6.262 |               6.262 |  1.000 |   1.000 |             1.501 |               28.690 |        16.353 |
| 2025-08-31 | reportable | hour_weekday_mean |     3482 |     21.527 |               6.262 |  3.710 |   3.202 |           -10.829 |               67.088 |        44.338 |
| 2025-08-31 | reportable | ridge_all         |     3482 |     19.308 |               6.262 |  3.181 |   2.761 |             3.002 |               49.512 |        56.761 |
| 2025-08-31 | reportable | per_zone_ridge    |     3482 |     14.489 |               6.262 |  2.601 |   2.521 |             3.086 |               33.601 |        33.214 |
| 2025-08-31 | reportable | hybrid            |     3482 |      6.274 |               6.262 |  0.997 |   0.998 |            -0.020 |               36.818 |        15.990 |

## Lead-Time Investigation

| model             |   first_lead_mape_pct |   last_lead_mape_pct |   nondecreasing_steps |   total_steps |
|:------------------|----------------------:|---------------------:|----------------------:|--------------:|
| seasonal_naive    |                12.694 |               12.079 |                    12 |            23 |
| hour_weekday_mean |                23.024 |               22.782 |                    10 |            23 |
| ridge_all         |                17.950 |               18.247 |                    11 |            23 |
| per_zone_ridge    |                26.394 |               26.385 |                    13 |            23 |
| hybrid            |                14.246 |               13.250 |                    12 |            23 |

Error is not guaranteed to rise monotonically across these leads. This was treated as a suspected leak and checked: (1) the saved seasonal source timestamps satisfy the issue-minus-purge cutoff; (2) fold training ends before the first issue's cutoff; (3) serving features are built without demand, and the target is attached only for scoring; (4) no holdout rows are scored. Tests exercise these boundaries, including future-target perturbations. No future-demand input was found in those paths.

Two confounders remain: lead time maps one-to-one to hour of day in a fixed daily forecast, and the deliberately simple weather-noise bridge has constant sigma, so it cannot reproduce lead-dependent weather forecast degradation. Calendar-only baselines do not consume weather at all. This investigation permits the Stage 2 benchmark to be recorded, but does not establish production forecast skill or validate the assumed sigmas. Recheck with exact captured vintages when coverage permits; do not force a rising curve by selecting noise or parameters from these test results.

## Reproducibility

Machine-readable fold, coverage, summary and stratified tables are in `reports/model/`. All metrics, including the full peak/ramp diagnostics for each stratum, are in stratified.csv. Predictions and issue/source timestamps are in the DVC-tracked `data/interim/model_predictions.parquet`. manifest.json records actual input-file and pointer hashes, source/config hashes, runtime versions, seed and split boundaries. Temperature bands use observed temperatures for analysis only; sparse interior bands are merged, the hottest band stays separate, and segments below the sufficiency threshold are marked insufficient rather than quoted as performance. Absent zone/band cells remain absent.

## Hybrid

Ridge uses the configured linear features; LightGBM learns log residuals. Chronological early stopping is followed by a full-history refit with scaled iteration count. Recency weighting and per-zone Duan smearing apply. No speculative cause-based exclusions.
