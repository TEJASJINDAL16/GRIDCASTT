# Stage 2: Features and Baseline

Generated 2026-10-06T14:30:39.726266+00:00. Reproduce: `make baseline` (cached data only).

**Number to beat: seasonal-naive MAPE 11.789% over 35,033 common measured rows.** Its out-of-sample MASE and RMSSE are 1.000. The Stage 3 selection criterion is mean fold MASE, with RMSSE co-primary; the pooled MAPE above is descriptive, not a final holdout result.

## Protocol and Limits

12 monthly expanding folds: 2024-09-01 up to 2025-09-01 (exclusive), IST calendar boundaries. The final holdout is 2025-09-01 through 2026-09-01 (exclusive), and was not scored. A partial newest month is excluded from the split anchor. Reserved tuning window: 2020-01-01 through 2021-01-01 (exclusive), IST. No tuning was run and production hyperparameters remain null.

Earlier exploratory analyses examined the full cached history. The holdout is reserved from this baseline loop; a later final accuracy claim must disclose that earlier exploration rather than describing the dataset as completely unseen throughout the project.

Each learned baseline is fitted once per fold. Training ends at least ten days before the first issue, slightly earlier than a ten-day gap from the test boundary. The ten-day settlement gap is an unmeasured assumption. Daily issue time is 10:00 IST on the preceding date. UTC hourly targets map to IST 00:30-23:30, with exact leads 14.5-37.5 hours. No target interpolation or recursive prediction is used.

The seasonal baseline uses the latest measured same-zone/hour/weekday value at least ten days before each daily issue; it can use eligible history accumulated within a fold. Historical means are per zone/hour/weekday. Ridge-all and per-zone Ridge use identical engineered features, categorical hour/weekday/zone encodings, log targets, fixed alpha=1.0, configured recency weights, and per-zone Duan smearing estimated on training residuals. These parameters were not selected using test-fold performance.

Weather inputs use the configured constant-sigma simulation bridge: per-city/IST-day Gaussian bias sigma=1.2 C plus hourly wobble sigma=0.5 C. Noise is applied to raw temperature before cooling-degree transforms in both training and simulated serving. These are assumptions, not measured forecast errors. This benchmark does not claim historical point-in-time weather accuracy. Recovered forecasts have uncertain intra-day issue times and are not silently treated as exact 10:00 IST vintages.

**Data-generating-process caveat:** folds straddle the MODE_BREAKDOWN-to-measured transition. Only measured targets are scored, while training allows measured plus MODE_BREAKDOWN. Early folds consequently score fewer zones. IN-NE has no eligible training history at its first measured fold; learned models abstain there. All four reported baseline scores use the same measured rows with finite predictions from every baseline. Expected, measured and excluded rows are reported below. Incomplete weather days are skipped for that zone; missing actuals are not scored. A fold above failure.max_gap_fraction is marked unreliable rather than silently removed. The demand archive contains current revised values; the assumed purge is not a complete historical revision replay.

All otherwise eligible observations are retained, including hot hours with sustained demand drops. No heuristic infers a cause or removes records based on temperature and demand residuals. Manual festival extensions remain incomplete, and cyclic day-of-year remains an ablation candidate.

## Overall Comparison

| model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| seasonal_naive    |    35033 |     11.789 |              11.789 |  1.000 |   1.000 |             0.376 |               40.565 |        34.849 |
| hour_weekday_mean |    35033 |     19.406 |              11.789 |  2.118 |   2.099 |            -6.354 |               61.011 |        45.461 |
| ridge_all         |    35033 |     20.024 |              11.789 |  1.837 |   1.715 |             5.011 |               44.615 |        58.279 |
| per_zone_ridge    |    35033 |     28.064 |              11.789 |  1.806 |   1.727 |            17.006 |               33.974 |        75.382 |

Percentage metrics are expressed in percent. MASE=sum(abs(error))/sum(abs(seasonal error)); RMSSE=sqrt(sum(error^2)/sum(seasonal error^2)), the out-of-sample variants on identical rows. Zero denominators are undefined, never coerced to zero. Lower is better except signed bias, whose sign states over/under forecast. Shortfall counts misses below the configured -3% threshold.

## Mean Across Folds

| model             |   mape_pct |   mase |   rmsse |
|:------------------|-----------:|-------:|--------:|
| seasonal_naive    |     12.571 |  1.000 |   1.000 |
| hour_weekday_mean |     18.542 |  2.181 |   2.165 |
| ridge_all         |     19.875 |  1.932 |   1.845 |
| per_zone_ridge    |     25.978 |  1.854 |   1.825 |

## Physical, Peak and Ramp Errors

| model             |   n_rows |   mae_mw |   rmse_mw |   rmse_mae_ratio |   n_peak_days |   peak_mae_mw |   baseline_peak_mae_mw |   peak_mape_pct |   n_ramps |   ramp_mae_mw |   baseline_ramp_mae_mw |   ramp_mase |
|:------------------|---------:|---------:|----------:|-----------------:|--------------:|--------------:|-----------------------:|----------------:|----------:|--------------:|-----------------------:|------------:|
| seasonal_naive    |    35033 | 3803.617 |  5533.862 |            1.455 |          1459 |      4038.623 |               4038.623 |          10.171 |      7295 |       684.872 |                684.872 |       1.000 |
| hour_weekday_mean |    35033 | 8055.409 | 11618.341 |            1.442 |          1459 |      8241.351 |               4038.623 |          16.396 |      7295 |      1537.296 |                684.872 |       2.245 |
| ridge_all         |    35033 | 6986.671 |  9491.552 |            1.359 |          1459 |      5626.407 |               4038.623 |          14.503 |      7295 |      1969.549 |                684.872 |       2.876 |
| per_zone_ridge    |    35033 | 6867.848 |  9555.387 |            1.391 |          1459 |      7010.025 |               4038.623 |          25.259 |      7295 |      1690.905 |                684.872 |       2.469 |

Peak errors use each complete measured zone/day's actual maximum. Incomplete days are excluded from peak metrics. Ramps compare consecutive hourly deltas within the same fold/zone/day during the configured IST evening window; they never bridge missing hours or folds. Pooled MW errors reflect zone magnitude; use per-zone scores below for comparison.

## Fold Coverage

|   fold | test_start                | test_end                  | train_end                 | training_zones                                |   n_train |   n_excluded_training |   n_expected |   n_forecast |   cache_gap_fraction | fold_status             |   n_measured |   n_common |   n_measured_without_comparison |   n_available_seasonal_naive |   n_available_hour_weekday_mean |   n_available_ridge_all |   n_available_per_zone_ridge |
|-------:|:--------------------------|:--------------------------|:--------------------------|:----------------------------------------------|----------:|----------------------:|-------------:|-------------:|---------------------:|:------------------------|-------------:|-----------:|--------------------------------:|-----------------------------:|--------------------------------:|------------------------:|-----------------------------:|
|      1 | 2024-08-31T18:30:00+00:00 | 2024-09-30T18:30:00+00:00 | 2024-08-21T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    127556 |                 75774 |         3600 |         3600 |                0.000 | cache coverage reliable |          720 |        720 |                               0 |                          720 |                             720 |                     720 |                          720 |
|      2 | 2024-09-30T18:30:00+00:00 | 2024-10-31T18:30:00+00:00 | 2024-09-20T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    130436 |                 76494 |         3720 |         3720 |                0.000 | cache coverage reliable |          744 |        744 |                               0 |                          744 |                             744 |                     744 |                          744 |
|      3 | 2024-10-31T18:30:00+00:00 | 2024-11-30T18:30:00+00:00 | 2024-10-21T04:30:00+00:00 | ['IN-EA', 'IN-NO', 'IN-SO', 'IN-WE']          |    133412 |                 77238 |         3600 |         3600 |                0.000 | cache coverage reliable |         2984 |       1402 |                            1582 |                         1640 |                            2410 |                    2410 |                         2410 |
|      4 | 2024-11-30T18:30:00+00:00 | 2024-12-31T18:30:00+00:00 | 2024-11-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    136511 |                 77739 |         3720 |         3720 |                0.000 | cache coverage reliable |         3483 |       3483 |                               0 |                         3483 |                            3483 |                    3483 |                         3483 |
|      5 | 2024-12-31T18:30:00+00:00 | 2025-01-31T18:30:00+00:00 | 2024-12-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    140165 |                 77805 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |
|      6 | 2025-01-31T18:30:00+00:00 | 2025-02-28T18:30:00+00:00 | 2025-01-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    143648 |                 78042 |         3360 |         3360 |                0.000 | cache coverage reliable |         3360 |       3360 |                               0 |                         3360 |                            3360 |                    3360 |                         3360 |
|      7 | 2025-02-28T18:30:00+00:00 | 2025-03-31T18:30:00+00:00 | 2025-02-18T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    147008 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |
|      8 | 2025-03-31T18:30:00+00:00 | 2025-04-30T18:30:00+00:00 | 2025-03-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    150728 |                 78042 |         3600 |         3600 |                0.000 | cache coverage reliable |         3600 |       3600 |                               0 |                         3600 |                            3600 |                    3600 |                         3600 |
|      9 | 2025-04-30T18:30:00+00:00 | 2025-05-31T18:30:00+00:00 | 2025-04-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    154328 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3720 |       3720 |                               0 |                         3720 |                            3720 |                    3720 |                         3720 |
|     10 | 2025-05-31T18:30:00+00:00 | 2025-06-30T18:30:00+00:00 | 2025-05-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    158048 |                 78042 |         3600 |         3600 |                0.000 | cache coverage reliable |         3482 |       3482 |                               0 |                         3482 |                            3482 |                    3482 |                         3482 |
|     11 | 2025-06-30T18:30:00+00:00 | 2025-07-31T18:30:00+00:00 | 2025-06-20T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    161648 |                 78042 |         3720 |         3720 |                0.000 | cache coverage reliable |         3480 |       3480 |                               0 |                         3480 |                            3480 |                    3480 |                         3480 |
|     12 | 2025-07-31T18:30:00+00:00 | 2025-08-31T18:30:00+00:00 | 2025-07-21T04:30:00+00:00 | ['IN-EA', 'IN-NE', 'IN-NO', 'IN-SO', 'IN-WE'] |    165130 |                 78280 |         3720 |         3720 |                0.000 | cache coverage reliable |         3602 |       3602 |                               0 |                         3602 |                            3602 |                    3602 |                         3602 |

## Every Fold

|   fold | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|-------:|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|      1 | seasonal_naive    |      720 |     17.588 |              17.588 |  1.000 |   1.000 |            -6.403 |               55.972 |        30.921 |
|      1 | hour_weekday_mean |      720 |     14.087 |              17.588 |  0.777 |   0.702 |            -1.121 |               53.472 |        19.849 |
|      1 | ridge_all         |      720 |     18.878 |              17.588 |  1.000 |   1.055 |             6.611 |               34.861 |        54.556 |
|      1 | per_zone_ridge    |      720 |     13.918 |              17.588 |  0.740 |   0.679 |             2.221 |               52.361 |        26.710 |
|      2 | seasonal_naive    |      744 |     14.750 |              14.750 |  1.000 |   1.000 |             4.377 |               42.876 |        35.136 |
|      2 | hour_weekday_mean |      744 |     16.049 |              14.750 |  1.208 |   1.118 |           -11.821 |               78.495 |        23.777 |
|      2 | ridge_all         |      744 |     16.781 |              14.750 |  1.216 |   1.244 |            -5.192 |               54.839 |        38.415 |
|      2 | per_zone_ridge    |      744 |     15.868 |              14.750 |  1.193 |   1.112 |           -11.523 |               78.495 |        23.888 |
|      3 | seasonal_naive    |     1402 |     16.178 |              16.178 |  1.000 |   1.000 |             7.583 |               29.886 |        47.941 |
|      3 | hour_weekday_mean |     1402 |     13.670 |              16.178 |  0.867 |   0.839 |             4.404 |               34.593 |        31.593 |
|      3 | ridge_all         |     1402 |     22.750 |              16.178 |  1.543 |   1.643 |            17.599 |               19.900 |        66.167 |
|      3 | per_zone_ridge    |     1402 |     21.277 |              16.178 |  1.447 |   1.471 |            19.437 |                9.986 |        47.385 |
|      4 | seasonal_naive    |     3483 |     19.135 |              19.135 |  1.000 |   1.000 |            -2.834 |               45.765 |        73.057 |
|      4 | hour_weekday_mean |     3483 |     21.954 |              19.135 |  1.288 |   1.343 |             0.048 |               50.962 |        58.446 |
|      4 | ridge_all         |     3483 |     26.197 |              19.135 |  1.446 |   1.291 |             8.693 |               39.564 |        69.067 |
|      4 | per_zone_ridge    |     3483 |     72.027 |              19.135 |  1.827 |   1.642 |            66.833 |               18.691 |       352.702 |
|      5 | seasonal_naive    |     3720 |     11.999 |              11.999 |  1.000 |   1.000 |             1.464 |               40.269 |        34.800 |
|      5 | hour_weekday_mean |     3720 |     18.095 |              11.999 |  1.851 |   2.064 |            -3.518 |               58.898 |        47.452 |
|      5 | ridge_all         |     3720 |     17.819 |              11.999 |  1.490 |   1.431 |             1.845 |               47.688 |        48.617 |
|      5 | per_zone_ridge    |     3720 |     57.857 |              11.999 |  1.842 |   1.745 |            50.972 |               24.113 |       343.147 |
|      6 | seasonal_naive    |     3360 |      9.710 |               9.710 |  1.000 |   1.000 |            -1.995 |               48.125 |        33.868 |
|      6 | hour_weekday_mean |     3360 |     14.038 |               9.710 |  2.528 |   3.044 |            -7.951 |               69.940 |        34.184 |
|      6 | ridge_all         |     3360 |     14.618 |               9.710 |  1.985 |   1.949 |             0.835 |               47.024 |        34.379 |
|      6 | per_zone_ridge    |     3360 |     25.317 |               9.710 |  2.081 |   2.231 |            16.441 |               33.839 |        93.640 |
|      7 | seasonal_naive    |     3720 |     10.487 |              10.487 |  1.000 |   1.000 |            -0.142 |               41.344 |        27.569 |
|      7 | hour_weekday_mean |     3720 |     14.275 |              10.487 |  2.125 |   2.383 |            -8.043 |               63.763 |        34.607 |
|      7 | ridge_all         |     3720 |     15.198 |              10.487 |  1.673 |   1.655 |             4.211 |               42.473 |        41.222 |
|      7 | per_zone_ridge    |     3720 |     17.980 |              10.487 |  1.716 |   1.721 |             7.954 |               34.973 |        49.202 |
|      8 | seasonal_naive    |     3600 |     12.799 |              12.799 |  1.000 |   1.000 |            -0.092 |               46.111 |        42.137 |
|      8 | hour_weekday_mean |     3600 |     20.028 |              12.799 |  2.400 |   2.581 |            -6.368 |               60.972 |        43.387 |
|      8 | ridge_all         |     3600 |     20.533 |              12.799 |  1.868 |   1.967 |             8.287 |               39.472 |        71.009 |
|      8 | per_zone_ridge    |     3600 |     17.722 |              12.799 |  1.631 |   1.695 |             6.433 |               36.611 |        46.249 |
|      9 | seasonal_naive    |     3720 |     16.489 |              16.489 |  1.000 |   1.000 |             4.767 |               33.414 |        44.368 |
|      9 | hour_weekday_mean |     3720 |     22.921 |              16.489 |  1.639 |   1.609 |            -2.725 |               55.161 |        54.274 |
|      9 | ridge_all         |     3720 |     23.754 |              16.489 |  1.331 |   1.314 |            11.535 |               41.022 |        88.717 |
|      9 | per_zone_ridge    |     3720 |     21.110 |              16.489 |  1.267 |   1.220 |             9.928 |               31.989 |        57.775 |
|     10 | seasonal_naive    |     3482 |     10.623 |              10.623 |  1.000 |   1.000 |            -1.511 |               50.172 |        24.632 |
|     10 | hour_weekday_mean |     3482 |     23.065 |              10.623 |  2.299 |   2.143 |           -11.071 |               65.882 |        49.142 |
|     10 | ridge_all         |     3482 |     21.460 |              10.623 |  1.829 |   1.694 |             1.637 |               54.078 |        64.770 |
|     10 | per_zone_ridge    |     3482 |     17.744 |              10.623 |  1.720 |   1.690 |            -1.101 |               46.783 |        39.704 |
|     11 | seasonal_naive    |     3480 |      4.875 |               4.875 |  1.000 |   1.000 |            -0.572 |               32.960 |        12.577 |
|     11 | hour_weekday_mean |     3480 |     22.900 |               4.875 |  5.461 |   4.933 |           -11.185 |               65.431 |        46.743 |
|     11 | ridge_all         |     3480 |     21.358 |               4.875 |  4.652 |   4.135 |             1.739 |               50.489 |        58.453 |
|     11 | per_zone_ridge    |     3480 |     16.469 |               4.875 |  4.172 |   4.157 |             0.319 |               41.897 |        36.270 |
|     12 | seasonal_naive    |     3602 |      6.217 |               6.217 |  1.000 |   1.000 |             1.502 |               28.484 |        16.300 |
|     12 | hour_weekday_mean |     3602 |     21.424 |               6.217 |  3.724 |   3.218 |           -10.852 |               67.018 |        44.365 |
|     12 | ridge_all         |     3602 |     19.154 |               6.217 |  3.149 |   2.764 |             2.745 |               49.778 |        56.750 |
|     12 | per_zone_ridge    |     3602 |     14.447 |               6.217 |  2.611 |   2.537 |             3.025 |               33.870 |        33.515 |

## Stratification: temperature_band

| segment      | status     | model             |   n_rows | mape_pct           | baseline_mape_pct   | mase               | rmsse              | signed_bias_pct      | shortfall_freq_pct   | p95_abs_pct        |
|:-------------|:-----------|:------------------|---------:|:-------------------|:--------------------|:-------------------|:-------------------|:---------------------|:---------------------|:-------------------|
| < 20 C       | reportable | seasonal_naive    |     5584 | 17.286687129949293 | 17.286687129949293  | 1.0                | 1.0                | -0.03388385689934982 | 45.075214899713465   | 58.714709686641626 |
| < 20 C       | reportable | hour_weekday_mean |     5584 | 21.561223063373408 | 17.286687129949293  | 1.4792004334245958 | 1.5611630195038826 | 2.735161206220565    | 45.45128939828081    | 59.70094984959919  |
| < 20 C       | reportable | ridge_all         |     5584 | 24.851566036942017 | 17.286687129949293  | 1.5670584007570638 | 1.4787361934337049 | 3.5387493842279265   | 48.78223495702006    | 63.580344590625295 |
| < 20 C       | reportable | per_zone_ridge    |     5584 | 67.46267962895344  | 17.286687129949293  | 1.8104003646615996 | 1.665405524185626  | 63.01019961583138    | 16.189111747851005   | 341.807659178085   |
| 20 to < 30 C | reportable | seasonal_naive    |    22857 | 10.60085611944327  | 10.60085611944327   | 1.0                | 1.0                | 0.25238652857753835  | 39.725248282801765   | 31.157617497918725 |
| 20 to < 30 C | reportable | hour_weekday_mean |    22857 | 18.409988286576127 | 10.60085611944327   | 2.2931804965859457 | 2.265441033615093  | -9.254183298340957   | 65.42415890099313    | 42.027890790125376 |
| 20 to < 30 C | reportable | ridge_all         |    22857 | 17.083464096251337 | 10.60085611944327   | 1.8566013415622566 | 1.7483466810411732 | 2.1071094068818668   | 47.29842061512885    | 42.24230953301455  |
| 20 to < 30 C | reportable | per_zone_ridge    |    22857 | 21.680539345967    | 10.60085611944327   | 1.9084825307577793 | 1.8555083071421643 | 8.787851038145156    | 39.13024456402853    | 51.1425450193388   |
| 30 to < 45 C | reportable | seasonal_naive    |     6592 | 11.251155679283237 | 11.251155679283237  | 1.0                | 1.0                | 1.1537115660976562   | 39.654126213592235   | 31.232535175786484 |
| 30 to < 45 C | reportable | hour_weekday_mean |     6592 | 21.031628707814942 | 11.251155679283237  | 2.012243593163853  | 1.905063731065051  | -3.9986487877004793  | 58.88956310679612    | 51.05479071039606  |
| 30 to < 45 C | reportable | ridge_all         |     6592 | 26.127946361533628 | 11.251155679283237  | 1.9367351482371662 | 1.7325673375234159 | 16.329621196071674   | 31.780946601941746   | 84.16322861873874  |
| 30 to < 45 C | reportable | per_zone_ridge    |     6592 | 16.824631476416293 | 11.251155679283237  | 1.5292934659634512 | 1.4322948572726555 | 6.5313032791410555   | 31.158980582524272   | 40.85419266313502  |
| >= 45 C      | absent     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| >= 45 C      | absent     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |

## Stratification: hour_of_day

|   segment | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|----------:|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|         0 | reportable | seasonal_naive    |     1460 |     12.694 |              12.694 |  1.000 |   1.000 |             0.175 |               41.438 |        37.107 |
|         0 | reportable | hour_weekday_mean |     1460 |     23.024 |              12.694 |  2.514 |   2.436 |           -10.030 |               66.712 |        46.033 |
|         0 | reportable | ridge_all         |     1460 |     18.083 |              12.694 |  1.636 |   1.533 |            -1.227 |               55.068 |        45.375 |
|         0 | reportable | per_zone_ridge    |     1460 |     27.117 |              12.694 |  1.725 |   1.615 |            11.936 |               44.726 |        74.114 |
|         1 | reportable | seasonal_naive    |     1460 |     12.870 |              12.870 |  1.000 |   1.000 |             0.257 |               41.438 |        38.212 |
|         1 | reportable | hour_weekday_mean |     1460 |     22.789 |              12.870 |  2.447 |   2.376 |            -9.719 |               65.342 |        45.644 |
|         1 | reportable | ridge_all         |     1460 |     18.164 |              12.870 |  1.625 |   1.524 |            -1.697 |               55.959 |        44.015 |
|         1 | reportable | per_zone_ridge    |     1460 |     26.608 |              12.870 |  1.695 |   1.583 |            11.400 |               44.247 |        70.817 |
|         2 | reportable | seasonal_naive    |     1460 |     13.023 |              13.023 |  1.000 |   1.000 |             0.302 |               41.301 |        39.088 |
|         2 | reportable | hour_weekday_mean |     1460 |     22.462 |              13.023 |  2.365 |   2.299 |            -8.779 |               63.562 |        44.651 |
|         2 | reportable | ridge_all         |     1460 |     18.032 |              13.023 |  1.584 |   1.482 |            -1.673 |               55.822 |        43.640 |
|         2 | reportable | per_zone_ridge    |     1460 |     26.961 |              13.023 |  1.666 |   1.550 |            12.136 |               42.671 |        71.515 |
|         3 | reportable | seasonal_naive    |     1460 |     13.120 |              13.120 |  1.000 |   1.000 |             0.385 |               41.849 |        39.514 |
|         3 | reportable | hour_weekday_mean |     1460 |     22.480 |              13.120 |  2.343 |   2.269 |            -7.690 |               62.466 |        45.263 |
|         3 | reportable | ridge_all         |     1460 |     18.092 |              13.120 |  1.573 |   1.450 |            -1.028 |               55.068 |        43.282 |
|         3 | reportable | per_zone_ridge    |     1460 |     27.238 |              13.120 |  1.677 |   1.558 |            12.952 |               41.233 |        75.687 |
|         4 | reportable | seasonal_naive    |     1460 |     13.039 |              13.039 |  1.000 |   1.000 |             0.524 |               41.849 |        37.937 |
|         4 | reportable | hour_weekday_mean |     1460 |     22.283 |              13.039 |  2.380 |   2.332 |            -6.822 |               62.603 |        46.943 |
|         4 | reportable | ridge_all         |     1460 |     17.798 |              13.039 |  1.558 |   1.401 |            -0.037 |               53.630 |        43.758 |
|         4 | reportable | per_zone_ridge    |     1460 |     28.078 |              13.039 |  1.704 |   1.620 |            14.705 |               39.178 |        78.043 |
|         5 | reportable | seasonal_naive    |     1459 |     12.551 |              12.551 |  1.000 |   1.000 |             0.678 |               39.822 |        36.932 |
|         5 | reportable | hour_weekday_mean |     1459 |     20.831 |              12.551 |  2.421 |   2.422 |            -6.198 |               62.783 |        42.636 |
|         5 | reportable | ridge_all         |     1459 |     16.732 |              12.551 |  1.549 |   1.342 |             0.516 |               51.953 |        41.348 |
|         5 | reportable | per_zone_ridge    |     1459 |     29.286 |              12.551 |  1.729 |   1.730 |            17.449 |               36.189 |        83.590 |
|         6 | reportable | seasonal_naive    |     1459 |     11.914 |              11.914 |  1.000 |   1.000 |             0.836 |               38.588 |        33.468 |
|         6 | reportable | hour_weekday_mean |     1459 |     19.285 |              11.914 |  2.415 |   2.460 |            -5.906 |               61.823 |        40.962 |
|         6 | reportable | ridge_all         |     1459 |     16.285 |              11.914 |  1.549 |   1.343 |             1.428 |               48.184 |        42.724 |
|         6 | reportable | per_zone_ridge    |     1459 |     29.361 |              11.914 |  1.742 |   1.809 |            19.064 |               31.460 |        81.272 |
|         7 | reportable | seasonal_naive    |     1459 |     11.515 |              11.515 |  1.000 |   1.000 |             0.845 |               38.314 |        33.339 |
|         7 | reportable | hour_weekday_mean |     1459 |     19.087 |              11.515 |  2.205 |   2.210 |            -1.770 |               57.711 |        41.853 |
|         7 | reportable | ridge_all         |     1459 |     18.849 |              11.515 |  1.706 |   1.608 |             9.341 |               35.024 |        51.348 |
|         7 | reportable | per_zone_ridge    |     1459 |     29.424 |              11.515 |  1.897 |   1.814 |            22.139 |               24.400 |        81.162 |
|         8 | reportable | seasonal_naive    |     1459 |     11.421 |              11.421 |  1.000 |   1.000 |             0.740 |               38.862 |        34.846 |
|         8 | reportable | hour_weekday_mean |     1459 |     18.412 |              11.421 |  2.015 |   2.007 |            -0.545 |               55.929 |        45.171 |
|         8 | reportable | ridge_all         |     1459 |     21.768 |              11.421 |  1.915 |   1.865 |            14.689 |               27.622 |        67.856 |
|         8 | reportable | per_zone_ridge    |     1459 |     27.842 |              11.421 |  1.873 |   1.741 |            22.167 |               20.836 |        77.782 |
|         9 | reportable | seasonal_naive    |     1459 |     11.484 |              11.484 |  1.000 |   1.000 |             0.763 |               40.576 |        35.578 |
|         9 | reportable | hour_weekday_mean |     1459 |     17.625 |              11.484 |  1.858 |   1.847 |            -0.821 |               56.340 |        44.159 |
|         9 | reportable | ridge_all         |     1459 |     24.353 |              11.484 |  2.074 |   1.996 |            17.648 |               25.771 |        79.205 |
|         9 | reportable | per_zone_ridge    |     1459 |     26.441 |              11.484 |  1.722 |   1.596 |            21.657 |               19.123 |        73.293 |
|        10 | reportable | seasonal_naive    |     1459 |     11.588 |              11.588 |  1.000 |   1.000 |             0.757 |               39.685 |        35.493 |
|        10 | reportable | hour_weekday_mean |     1459 |     17.146 |              11.588 |  1.714 |   1.683 |            -0.390 |               55.860 |        45.822 |
|        10 | reportable | ridge_all         |     1459 |     26.852 |              11.588 |  2.229 |   2.081 |            20.487 |               25.154 |        86.558 |
|        10 | reportable | per_zone_ridge    |     1459 |     26.197 |              11.588 |  1.621 |   1.489 |            22.396 |               16.450 |        73.687 |
|        11 | reportable | seasonal_naive    |     1459 |     11.559 |              11.559 |  1.000 |   1.000 |             0.703 |               40.918 |        35.120 |
|        11 | reportable | hour_weekday_mean |     1459 |     16.893 |              11.559 |  1.622 |   1.501 |            -0.193 |               53.873 |        44.777 |
|        11 | reportable | ridge_all         |     1459 |     27.433 |              11.559 |  2.304 |   2.112 |            20.683 |               25.291 |        87.931 |
|        11 | reportable | per_zone_ridge    |     1459 |     25.884 |              11.559 |  1.647 |   1.625 |            22.047 |               19.260 |        70.644 |
|        12 | reportable | seasonal_naive    |     1459 |     11.675 |              11.675 |  1.000 |   1.000 |             0.666 |               40.439 |        34.833 |
|        12 | reportable | hour_weekday_mean |     1459 |     17.460 |              11.675 |  1.669 |   1.564 |            -0.510 |               53.598 |        45.429 |
|        12 | reportable | ridge_all         |     1459 |     26.988 |              11.675 |  2.278 |   2.043 |            19.683 |               25.565 |        83.997 |
|        12 | reportable | per_zone_ridge    |     1459 |     26.732 |              11.675 |  1.801 |   1.715 |            21.742 |               22.755 |        69.262 |
|        13 | reportable | seasonal_naive    |     1459 |     11.906 |              11.906 |  1.000 |   1.000 |             0.672 |               40.576 |        35.358 |
|        13 | reportable | hour_weekday_mean |     1459 |     17.153 |              11.906 |  1.566 |   1.451 |             0.342 |               50.720 |        43.625 |
|        13 | reportable | ridge_all         |     1459 |     26.927 |              11.906 |  2.266 |   2.018 |            20.052 |               23.715 |        80.875 |
|        13 | reportable | per_zone_ridge    |     1459 |     27.130 |              11.906 |  1.802 |   1.722 |            22.631 |               21.727 |        69.228 |
|        14 | reportable | seasonal_naive    |     1459 |     11.688 |              11.688 |  1.000 |   1.000 |             0.532 |               41.330 |        34.552 |
|        14 | reportable | hour_weekday_mean |     1459 |     17.174 |              11.688 |  1.691 |   1.608 |            -2.229 |               54.284 |        40.252 |
|        14 | reportable | ridge_all         |     1459 |     23.576 |              11.688 |  2.051 |   1.828 |            16.129 |               25.086 |        71.001 |
|        14 | reportable | per_zone_ridge    |     1459 |     27.450 |              11.688 |  1.810 |   1.704 |            21.459 |               25.977 |        70.055 |
|        15 | reportable | seasonal_naive    |     1459 |     11.645 |              11.645 |  1.000 |   1.000 |             0.503 |               42.152 |        34.654 |
|        15 | reportable | hour_weekday_mean |     1459 |     16.876 |              11.645 |  1.735 |   1.656 |            -2.974 |               55.175 |        37.396 |
|        15 | reportable | ridge_all         |     1459 |     20.333 |              11.645 |  1.811 |   1.644 |            12.644 |               26.525 |        57.862 |
|        15 | reportable | per_zone_ridge    |     1459 |     28.876 |              11.645 |  1.817 |   1.716 |            21.853 |               27.553 |        75.176 |
|        16 | reportable | seasonal_naive    |     1459 |     11.140 |              11.140 |  1.000 |   1.000 |             0.569 |               40.096 |        32.292 |
|        16 | reportable | hour_weekday_mean |     1459 |     16.259 |              11.140 |  1.813 |   1.732 |            -3.441 |               55.997 |        36.763 |
|        16 | reportable | ridge_all         |     1459 |     17.205 |              11.140 |  1.627 |   1.499 |             8.324 |               32.968 |        48.009 |
|        16 | reportable | per_zone_ridge    |     1459 |     31.049 |              11.140 |  1.869 |   1.775 |            23.132 |               29.815 |        90.001 |
|        17 | reportable | seasonal_naive    |     1459 |     10.634 |              10.634 |  1.000 |   1.000 |             0.671 |               38.040 |        30.366 |
|        17 | reportable | hour_weekday_mean |     1459 |     16.854 |              10.634 |  1.976 |   1.847 |            -5.071 |               58.465 |        37.497 |
|        17 | reportable | ridge_all         |     1459 |     15.543 |              10.634 |  1.563 |   1.384 |             2.281 |               46.470 |        42.572 |
|        17 | reportable | per_zone_ridge    |     1459 |     32.133 |              10.634 |  1.895 |   1.832 |            22.410 |               35.778 |       101.522 |
|        18 | reportable | seasonal_naive    |     1459 |     10.444 |              10.444 |  1.000 |   1.000 |             0.230 |               38.657 |        30.050 |
|        18 | reportable | hour_weekday_mean |     1459 |     18.905 |              10.444 |  2.386 |   2.240 |           -11.206 |               67.101 |        43.164 |
|        18 | reportable | ridge_all         |     1459 |     16.111 |              10.444 |  1.737 |   1.555 |            -5.764 |               61.206 |        37.036 |
|        18 | reportable | per_zone_ridge    |     1459 |     30.838 |              10.444 |  2.024 |   1.924 |            15.421 |               44.688 |        86.277 |
|        19 | reportable | seasonal_naive    |     1459 |     10.669 |              10.669 |  1.000 |   1.000 |            -0.252 |               40.850 |        30.912 |
|        19 | reportable | hour_weekday_mean |     1459 |     19.565 |              10.669 |  2.463 |   2.432 |           -14.450 |               69.705 |        48.454 |
|        19 | reportable | ridge_all         |     1459 |     17.629 |              10.669 |  1.925 |   1.801 |            -8.341 |               65.730 |        41.315 |
|        19 | reportable | per_zone_ridge    |     1459 |     28.760 |              10.669 |  2.042 |   1.978 |            10.831 |               46.059 |        67.652 |
|        20 | reportable | seasonal_naive    |     1459 |     11.120 |              11.120 |  1.000 |   1.000 |            -0.399 |               41.193 |        31.536 |
|        20 | reportable | hour_weekday_mean |     1459 |     19.884 |              11.120 |  2.371 |   2.417 |           -14.694 |               69.020 |        51.286 |
|        20 | reportable | ridge_all         |     1459 |     18.349 |              11.120 |  1.957 |   1.880 |            -7.796 |               65.250 |        43.901 |
|        20 | reportable | per_zone_ridge    |     1459 |     27.914 |              11.120 |  2.007 |   1.978 |             9.487 |               45.853 |        59.325 |
|        21 | reportable | seasonal_naive    |     1459 |     11.470 |              11.470 |  1.000 |   1.000 |            -0.460 |               41.672 |        32.500 |
|        21 | reportable | hour_weekday_mean |     1459 |     20.107 |              11.470 |  2.275 |   2.366 |           -14.304 |               67.992 |        51.384 |
|        21 | reportable | ridge_all         |     1459 |     18.613 |              11.470 |  1.889 |   1.828 |            -7.010 |               63.194 |        44.504 |
|        21 | reportable | per_zone_ridge    |     1459 |     27.580 |              11.470 |  1.975 |   1.941 |             8.990 |               45.031 |        60.455 |
|        22 | reportable | seasonal_naive    |     1459 |     11.679 |              11.679 |  1.000 |   1.000 |            -0.451 |               42.358 |        33.162 |
|        22 | reportable | hour_weekday_mean |     1459 |     20.358 |              11.679 |  2.218 |   2.321 |           -13.756 |               67.443 |        49.824 |
|        22 | reportable | ridge_all         |     1459 |     18.509 |              11.679 |  1.822 |   1.781 |            -6.746 |               63.742 |        44.551 |
|        22 | reportable | per_zone_ridge    |     1459 |     27.569 |              11.679 |  1.961 |   1.913 |             8.744 |               44.414 |        64.391 |
|        23 | reportable | seasonal_naive    |     1471 |     12.079 |              12.079 |  1.000 |   1.000 |            -0.209 |               41.536 |        36.787 |
|        23 | reportable | hour_weekday_mean |     1471 |     22.782 |              12.079 |  2.624 |   2.530 |           -11.300 |               69.680 |        46.183 |
|        23 | reportable | ridge_all         |     1471 |     18.362 |              12.079 |  1.717 |   1.623 |            -2.230 |               56.628 |        48.105 |
|        23 | reportable | per_zone_ridge    |     1471 |     27.082 |              12.079 |  1.729 |   1.589 |            11.453 |               45.819 |        78.349 |

## Stratification: zone

| segment   | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| IN-NO     | reportable | seasonal_naive    |     6675 |     12.824 |              12.824 |  1.000 |   1.000 |            -0.086 |               45.438 |        32.936 |
| IN-NO     | reportable | hour_weekday_mean |     6675 |     25.970 |              12.824 |  2.192 |   2.066 |            -9.371 |               67.176 |        55.590 |
| IN-NO     | reportable | ridge_all         |     6675 |     19.572 |              12.824 |  1.434 |   1.328 |             3.672 |               52.584 |        56.656 |
| IN-NO     | reportable | per_zone_ridge    |     6675 |     17.405 |              12.824 |  1.361 |   1.341 |            -0.384 |               51.775 |        43.555 |
| IN-WE     | reportable | seasonal_naive    |     6674 |      6.782 |               6.782 |  1.000 |   1.000 |             0.447 |               34.282 |        19.384 |
| IN-WE     | reportable | hour_weekday_mean |     6674 |     16.538 |               6.782 |  2.536 |   2.389 |           -12.608 |               73.914 |        37.199 |
| IN-WE     | reportable | ridge_all         |     6674 |     14.158 |               6.782 |  2.064 |   1.885 |             2.744 |               40.351 |        33.880 |
| IN-WE     | reportable | per_zone_ridge    |     6674 |     15.715 |               6.782 |  2.304 |   2.081 |             4.209 |               32.484 |        34.293 |
| IN-SO     | reportable | seasonal_naive    |     6674 |      9.661 |               9.661 |  1.000 |   1.000 |            -0.240 |               42.254 |        27.005 |
| IN-SO     | reportable | hour_weekday_mean |     6674 |     19.751 |               9.661 |  2.304 |   2.249 |           -12.784 |               68.115 |        43.805 |
| IN-SO     | reportable | ridge_all         |     6674 |     16.650 |               9.661 |  1.785 |   1.626 |             0.891 |               47.693 |        35.158 |
| IN-SO     | reportable | per_zone_ridge    |     6674 |     19.991 |               9.661 |  2.117 |   1.962 |             3.810 |               42.433 |        47.227 |
| IN-EA     | reportable | seasonal_naive    |     8577 |     10.282 |              10.282 |  1.000 |   1.000 |             1.646 |               35.549 |        29.409 |
| IN-EA     | reportable | hour_weekday_mean |     8577 |     16.076 |              10.282 |  1.447 |   1.260 |             8.033 |               33.601 |        42.775 |
| IN-EA     | reportable | ridge_all         |     8577 |     24.908 |              10.282 |  2.169 |   2.052 |            16.097 |               30.780 |        80.136 |
| IN-EA     | reportable | per_zone_ridge    |     8577 |     13.560 |              10.282 |  1.221 |   1.120 |             7.577 |               27.772 |        39.030 |
| IN-NE     | reportable | seasonal_naive    |     6433 |     20.126 |              20.126 |  1.000 |   1.000 |            -0.271 |               46.961 |        69.860 |
| IN-NE     | reportable | hour_weekday_mean |     6433 |     19.650 |              20.126 |  1.041 |   0.932 |            -9.247 |               70.403 |        48.198 |
| IN-NE     | reportable | ridge_all         |     6433 |     23.564 |              20.126 |  1.215 |   1.075 |            -1.752 |               56.024 |        53.196 |
| IN-NE     | reportable | per_zone_ridge    |     6433 |     79.650 |              20.126 |  4.085 |   5.804 |            74.588 |               16.540 |       360.397 |

## Stratification: day_type

| segment   | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| holiday   | reportable | seasonal_naive    |     1896 |     12.523 |              12.523 |  1.000 |   1.000 |             3.468 |               40.665 |        39.385 |
| holiday   | reportable | hour_weekday_mean |     1896 |     20.394 |              12.523 |  2.333 |   2.446 |            -4.839 |               59.863 |        44.789 |
| holiday   | reportable | ridge_all         |     1896 |     21.047 |              12.523 |  2.035 |   2.014 |             4.652 |               45.886 |        59.113 |
| holiday   | reportable | per_zone_ridge    |     1896 |     54.528 |              12.523 |  2.070 |   2.132 |            42.593 |               36.814 |       260.776 |
| weekday   | reportable | seasonal_naive    |    23369 |     11.877 |              11.877 |  1.000 |   1.000 |             0.176 |               40.776 |        34.869 |
| weekday   | reportable | hour_weekday_mean |    23369 |     19.496 |              11.877 |  2.103 |   2.066 |            -6.745 |               61.432 |        45.695 |
| weekday   | reportable | ridge_all         |    23369 |     19.845 |              11.877 |  1.798 |   1.664 |             4.861 |               44.786 |        57.567 |
| weekday   | reportable | per_zone_ridge    |    23369 |     25.902 |              11.877 |  1.760 |   1.670 |            14.769 |               33.891 |        74.065 |
| weekend   | reportable | seasonal_naive    |     9768 |     11.435 |              11.435 |  1.000 |   1.000 |             0.255 |               40.039 |        33.298 |
| weekend   | reportable | hour_weekday_mean |     9768 |     18.999 |              11.435 |  2.114 |   2.127 |            -5.714 |               60.227 |        44.705 |
| weekend   | reportable | ridge_all         |     9768 |     20.252 |              11.435 |  1.898 |   1.795 |             5.442 |               43.960 |        59.571 |
| weekend   | reportable | per_zone_ridge    |     9768 |     28.100 |              11.435 |  1.870 |   1.799 |            17.392 |               33.620 |        72.846 |

## Stratification: lead_time_hours

|   segment | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|----------:|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
|    14.500 | reportable | seasonal_naive    |     1460 |     12.694 |              12.694 |  1.000 |   1.000 |             0.175 |               41.438 |        37.107 |
|    14.500 | reportable | hour_weekday_mean |     1460 |     23.024 |              12.694 |  2.514 |   2.436 |           -10.030 |               66.712 |        46.033 |
|    14.500 | reportable | ridge_all         |     1460 |     18.083 |              12.694 |  1.636 |   1.533 |            -1.227 |               55.068 |        45.375 |
|    14.500 | reportable | per_zone_ridge    |     1460 |     27.117 |              12.694 |  1.725 |   1.615 |            11.936 |               44.726 |        74.114 |
|    15.500 | reportable | seasonal_naive    |     1460 |     12.870 |              12.870 |  1.000 |   1.000 |             0.257 |               41.438 |        38.212 |
|    15.500 | reportable | hour_weekday_mean |     1460 |     22.789 |              12.870 |  2.447 |   2.376 |            -9.719 |               65.342 |        45.644 |
|    15.500 | reportable | ridge_all         |     1460 |     18.164 |              12.870 |  1.625 |   1.524 |            -1.697 |               55.959 |        44.015 |
|    15.500 | reportable | per_zone_ridge    |     1460 |     26.608 |              12.870 |  1.695 |   1.583 |            11.400 |               44.247 |        70.817 |
|    16.500 | reportable | seasonal_naive    |     1460 |     13.023 |              13.023 |  1.000 |   1.000 |             0.302 |               41.301 |        39.088 |
|    16.500 | reportable | hour_weekday_mean |     1460 |     22.462 |              13.023 |  2.365 |   2.299 |            -8.779 |               63.562 |        44.651 |
|    16.500 | reportable | ridge_all         |     1460 |     18.032 |              13.023 |  1.584 |   1.482 |            -1.673 |               55.822 |        43.640 |
|    16.500 | reportable | per_zone_ridge    |     1460 |     26.961 |              13.023 |  1.666 |   1.550 |            12.136 |               42.671 |        71.515 |
|    17.500 | reportable | seasonal_naive    |     1460 |     13.120 |              13.120 |  1.000 |   1.000 |             0.385 |               41.849 |        39.514 |
|    17.500 | reportable | hour_weekday_mean |     1460 |     22.480 |              13.120 |  2.343 |   2.269 |            -7.690 |               62.466 |        45.263 |
|    17.500 | reportable | ridge_all         |     1460 |     18.092 |              13.120 |  1.573 |   1.450 |            -1.028 |               55.068 |        43.282 |
|    17.500 | reportable | per_zone_ridge    |     1460 |     27.238 |              13.120 |  1.677 |   1.558 |            12.952 |               41.233 |        75.687 |
|    18.500 | reportable | seasonal_naive    |     1460 |     13.039 |              13.039 |  1.000 |   1.000 |             0.524 |               41.849 |        37.937 |
|    18.500 | reportable | hour_weekday_mean |     1460 |     22.283 |              13.039 |  2.380 |   2.332 |            -6.822 |               62.603 |        46.943 |
|    18.500 | reportable | ridge_all         |     1460 |     17.798 |              13.039 |  1.558 |   1.401 |            -0.037 |               53.630 |        43.758 |
|    18.500 | reportable | per_zone_ridge    |     1460 |     28.078 |              13.039 |  1.704 |   1.620 |            14.705 |               39.178 |        78.043 |
|    19.500 | reportable | seasonal_naive    |     1459 |     12.551 |              12.551 |  1.000 |   1.000 |             0.678 |               39.822 |        36.932 |
|    19.500 | reportable | hour_weekday_mean |     1459 |     20.831 |              12.551 |  2.421 |   2.422 |            -6.198 |               62.783 |        42.636 |
|    19.500 | reportable | ridge_all         |     1459 |     16.732 |              12.551 |  1.549 |   1.342 |             0.516 |               51.953 |        41.348 |
|    19.500 | reportable | per_zone_ridge    |     1459 |     29.286 |              12.551 |  1.729 |   1.730 |            17.449 |               36.189 |        83.590 |
|    20.500 | reportable | seasonal_naive    |     1459 |     11.914 |              11.914 |  1.000 |   1.000 |             0.836 |               38.588 |        33.468 |
|    20.500 | reportable | hour_weekday_mean |     1459 |     19.285 |              11.914 |  2.415 |   2.460 |            -5.906 |               61.823 |        40.962 |
|    20.500 | reportable | ridge_all         |     1459 |     16.285 |              11.914 |  1.549 |   1.343 |             1.428 |               48.184 |        42.724 |
|    20.500 | reportable | per_zone_ridge    |     1459 |     29.361 |              11.914 |  1.742 |   1.809 |            19.064 |               31.460 |        81.272 |
|    21.500 | reportable | seasonal_naive    |     1459 |     11.515 |              11.515 |  1.000 |   1.000 |             0.845 |               38.314 |        33.339 |
|    21.500 | reportable | hour_weekday_mean |     1459 |     19.087 |              11.515 |  2.205 |   2.210 |            -1.770 |               57.711 |        41.853 |
|    21.500 | reportable | ridge_all         |     1459 |     18.849 |              11.515 |  1.706 |   1.608 |             9.341 |               35.024 |        51.348 |
|    21.500 | reportable | per_zone_ridge    |     1459 |     29.424 |              11.515 |  1.897 |   1.814 |            22.139 |               24.400 |        81.162 |
|    22.500 | reportable | seasonal_naive    |     1459 |     11.421 |              11.421 |  1.000 |   1.000 |             0.740 |               38.862 |        34.846 |
|    22.500 | reportable | hour_weekday_mean |     1459 |     18.412 |              11.421 |  2.015 |   2.007 |            -0.545 |               55.929 |        45.171 |
|    22.500 | reportable | ridge_all         |     1459 |     21.768 |              11.421 |  1.915 |   1.865 |            14.689 |               27.622 |        67.856 |
|    22.500 | reportable | per_zone_ridge    |     1459 |     27.842 |              11.421 |  1.873 |   1.741 |            22.167 |               20.836 |        77.782 |
|    23.500 | reportable | seasonal_naive    |     1459 |     11.484 |              11.484 |  1.000 |   1.000 |             0.763 |               40.576 |        35.578 |
|    23.500 | reportable | hour_weekday_mean |     1459 |     17.625 |              11.484 |  1.858 |   1.847 |            -0.821 |               56.340 |        44.159 |
|    23.500 | reportable | ridge_all         |     1459 |     24.353 |              11.484 |  2.074 |   1.996 |            17.648 |               25.771 |        79.205 |
|    23.500 | reportable | per_zone_ridge    |     1459 |     26.441 |              11.484 |  1.722 |   1.596 |            21.657 |               19.123 |        73.293 |
|    24.500 | reportable | seasonal_naive    |     1459 |     11.588 |              11.588 |  1.000 |   1.000 |             0.757 |               39.685 |        35.493 |
|    24.500 | reportable | hour_weekday_mean |     1459 |     17.146 |              11.588 |  1.714 |   1.683 |            -0.390 |               55.860 |        45.822 |
|    24.500 | reportable | ridge_all         |     1459 |     26.852 |              11.588 |  2.229 |   2.081 |            20.487 |               25.154 |        86.558 |
|    24.500 | reportable | per_zone_ridge    |     1459 |     26.197 |              11.588 |  1.621 |   1.489 |            22.396 |               16.450 |        73.687 |
|    25.500 | reportable | seasonal_naive    |     1459 |     11.559 |              11.559 |  1.000 |   1.000 |             0.703 |               40.918 |        35.120 |
|    25.500 | reportable | hour_weekday_mean |     1459 |     16.893 |              11.559 |  1.622 |   1.501 |            -0.193 |               53.873 |        44.777 |
|    25.500 | reportable | ridge_all         |     1459 |     27.433 |              11.559 |  2.304 |   2.112 |            20.683 |               25.291 |        87.931 |
|    25.500 | reportable | per_zone_ridge    |     1459 |     25.884 |              11.559 |  1.647 |   1.625 |            22.047 |               19.260 |        70.644 |
|    26.500 | reportable | seasonal_naive    |     1459 |     11.675 |              11.675 |  1.000 |   1.000 |             0.666 |               40.439 |        34.833 |
|    26.500 | reportable | hour_weekday_mean |     1459 |     17.460 |              11.675 |  1.669 |   1.564 |            -0.510 |               53.598 |        45.429 |
|    26.500 | reportable | ridge_all         |     1459 |     26.988 |              11.675 |  2.278 |   2.043 |            19.683 |               25.565 |        83.997 |
|    26.500 | reportable | per_zone_ridge    |     1459 |     26.732 |              11.675 |  1.801 |   1.715 |            21.742 |               22.755 |        69.262 |
|    27.500 | reportable | seasonal_naive    |     1459 |     11.906 |              11.906 |  1.000 |   1.000 |             0.672 |               40.576 |        35.358 |
|    27.500 | reportable | hour_weekday_mean |     1459 |     17.153 |              11.906 |  1.566 |   1.451 |             0.342 |               50.720 |        43.625 |
|    27.500 | reportable | ridge_all         |     1459 |     26.927 |              11.906 |  2.266 |   2.018 |            20.052 |               23.715 |        80.875 |
|    27.500 | reportable | per_zone_ridge    |     1459 |     27.130 |              11.906 |  1.802 |   1.722 |            22.631 |               21.727 |        69.228 |
|    28.500 | reportable | seasonal_naive    |     1459 |     11.688 |              11.688 |  1.000 |   1.000 |             0.532 |               41.330 |        34.552 |
|    28.500 | reportable | hour_weekday_mean |     1459 |     17.174 |              11.688 |  1.691 |   1.608 |            -2.229 |               54.284 |        40.252 |
|    28.500 | reportable | ridge_all         |     1459 |     23.576 |              11.688 |  2.051 |   1.828 |            16.129 |               25.086 |        71.001 |
|    28.500 | reportable | per_zone_ridge    |     1459 |     27.450 |              11.688 |  1.810 |   1.704 |            21.459 |               25.977 |        70.055 |
|    29.500 | reportable | seasonal_naive    |     1459 |     11.645 |              11.645 |  1.000 |   1.000 |             0.503 |               42.152 |        34.654 |
|    29.500 | reportable | hour_weekday_mean |     1459 |     16.876 |              11.645 |  1.735 |   1.656 |            -2.974 |               55.175 |        37.396 |
|    29.500 | reportable | ridge_all         |     1459 |     20.333 |              11.645 |  1.811 |   1.644 |            12.644 |               26.525 |        57.862 |
|    29.500 | reportable | per_zone_ridge    |     1459 |     28.876 |              11.645 |  1.817 |   1.716 |            21.853 |               27.553 |        75.176 |
|    30.500 | reportable | seasonal_naive    |     1459 |     11.140 |              11.140 |  1.000 |   1.000 |             0.569 |               40.096 |        32.292 |
|    30.500 | reportable | hour_weekday_mean |     1459 |     16.259 |              11.140 |  1.813 |   1.732 |            -3.441 |               55.997 |        36.763 |
|    30.500 | reportable | ridge_all         |     1459 |     17.205 |              11.140 |  1.627 |   1.499 |             8.324 |               32.968 |        48.009 |
|    30.500 | reportable | per_zone_ridge    |     1459 |     31.049 |              11.140 |  1.869 |   1.775 |            23.132 |               29.815 |        90.001 |
|    31.500 | reportable | seasonal_naive    |     1459 |     10.634 |              10.634 |  1.000 |   1.000 |             0.671 |               38.040 |        30.366 |
|    31.500 | reportable | hour_weekday_mean |     1459 |     16.854 |              10.634 |  1.976 |   1.847 |            -5.071 |               58.465 |        37.497 |
|    31.500 | reportable | ridge_all         |     1459 |     15.543 |              10.634 |  1.563 |   1.384 |             2.281 |               46.470 |        42.572 |
|    31.500 | reportable | per_zone_ridge    |     1459 |     32.133 |              10.634 |  1.895 |   1.832 |            22.410 |               35.778 |       101.522 |
|    32.500 | reportable | seasonal_naive    |     1459 |     10.444 |              10.444 |  1.000 |   1.000 |             0.230 |               38.657 |        30.050 |
|    32.500 | reportable | hour_weekday_mean |     1459 |     18.905 |              10.444 |  2.386 |   2.240 |           -11.206 |               67.101 |        43.164 |
|    32.500 | reportable | ridge_all         |     1459 |     16.111 |              10.444 |  1.737 |   1.555 |            -5.764 |               61.206 |        37.036 |
|    32.500 | reportable | per_zone_ridge    |     1459 |     30.838 |              10.444 |  2.024 |   1.924 |            15.421 |               44.688 |        86.277 |
|    33.500 | reportable | seasonal_naive    |     1459 |     10.669 |              10.669 |  1.000 |   1.000 |            -0.252 |               40.850 |        30.912 |
|    33.500 | reportable | hour_weekday_mean |     1459 |     19.565 |              10.669 |  2.463 |   2.432 |           -14.450 |               69.705 |        48.454 |
|    33.500 | reportable | ridge_all         |     1459 |     17.629 |              10.669 |  1.925 |   1.801 |            -8.341 |               65.730 |        41.315 |
|    33.500 | reportable | per_zone_ridge    |     1459 |     28.760 |              10.669 |  2.042 |   1.978 |            10.831 |               46.059 |        67.652 |
|    34.500 | reportable | seasonal_naive    |     1459 |     11.120 |              11.120 |  1.000 |   1.000 |            -0.399 |               41.193 |        31.536 |
|    34.500 | reportable | hour_weekday_mean |     1459 |     19.884 |              11.120 |  2.371 |   2.417 |           -14.694 |               69.020 |        51.286 |
|    34.500 | reportable | ridge_all         |     1459 |     18.349 |              11.120 |  1.957 |   1.880 |            -7.796 |               65.250 |        43.901 |
|    34.500 | reportable | per_zone_ridge    |     1459 |     27.914 |              11.120 |  2.007 |   1.978 |             9.487 |               45.853 |        59.325 |
|    35.500 | reportable | seasonal_naive    |     1459 |     11.470 |              11.470 |  1.000 |   1.000 |            -0.460 |               41.672 |        32.500 |
|    35.500 | reportable | hour_weekday_mean |     1459 |     20.107 |              11.470 |  2.275 |   2.366 |           -14.304 |               67.992 |        51.384 |
|    35.500 | reportable | ridge_all         |     1459 |     18.613 |              11.470 |  1.889 |   1.828 |            -7.010 |               63.194 |        44.504 |
|    35.500 | reportable | per_zone_ridge    |     1459 |     27.580 |              11.470 |  1.975 |   1.941 |             8.990 |               45.031 |        60.455 |
|    36.500 | reportable | seasonal_naive    |     1459 |     11.679 |              11.679 |  1.000 |   1.000 |            -0.451 |               42.358 |        33.162 |
|    36.500 | reportable | hour_weekday_mean |     1459 |     20.358 |              11.679 |  2.218 |   2.321 |           -13.756 |               67.443 |        49.824 |
|    36.500 | reportable | ridge_all         |     1459 |     18.509 |              11.679 |  1.822 |   1.781 |            -6.746 |               63.742 |        44.551 |
|    36.500 | reportable | per_zone_ridge    |     1459 |     27.569 |              11.679 |  1.961 |   1.913 |             8.744 |               44.414 |        64.391 |
|    37.500 | reportable | seasonal_naive    |     1471 |     12.079 |              12.079 |  1.000 |   1.000 |            -0.209 |               41.536 |        36.787 |
|    37.500 | reportable | hour_weekday_mean |     1471 |     22.782 |              12.079 |  2.624 |   2.530 |           -11.300 |               69.680 |        46.183 |
|    37.500 | reportable | ridge_all         |     1471 |     18.362 |              12.079 |  1.717 |   1.623 |            -2.230 |               56.628 |        48.105 |
|    37.500 | reportable | per_zone_ridge    |     1471 |     27.082 |              12.079 |  1.729 |   1.589 |            11.453 |               45.819 |        78.349 |

## Stratification: zone_temperature_band

| segment             | status                     | model             |   n_rows | mape_pct           | baseline_mape_pct   | mase               | rmsse              | signed_bias_pct      | shortfall_freq_pct   | p95_abs_pct        |
|:--------------------|:---------------------------|:------------------|---------:|:-------------------|:--------------------|:-------------------|:-------------------|:---------------------|:---------------------|:-------------------|
| IN-NO: < 20 C       | reportable                 | seasonal_naive    |     1927 | 17.345920260690395 | 17.345920260690395  | 1.0                | 1.0                | 1.9632208534287672   | 48.46912298910223    | 43.6730821761413   |
| IN-NO: < 20 C       | reportable                 | hour_weekday_mean |     1927 | 27.787541842509    | 17.345920260690395  | 1.4629280285828505 | 1.448781712789025  | 25.226058795802203   | 13.7519460300986     | 80.70710082565249  |
| IN-NO: < 20 C       | reportable                 | ridge_all         |     1927 | 31.140466664278616 | 17.345920260690395  | 1.5809863079066648 | 1.5178598150238136 | 29.571367059130672   | 9.49662688116243     | 83.54783009741404  |
| IN-NO: < 20 C       | reportable                 | per_zone_ridge    |     1927 | 22.957309386326855 | 17.345920260690395  | 1.208535972976509  | 1.251706093669972  | 18.66090376383492    | 20.86144265697976    | 73.17684022328132  |
| IN-NO: 20 to < 30 C | reportable                 | seasonal_naive    |     2817 | 10.319233187587864 | 10.319233187587864  | 1.0                | 1.0                | 0.8838900467931186   | 38.516151934682284   | 27.234494403603993 |
| IN-NO: 20 to < 30 C | reportable                 | hour_weekday_mean |     2817 | 21.965618592421237 | 10.319233187587864  | 2.3817574441094362 | 2.2480173991954002 | -18.95705522499036   | 82.0376286829961     | 49.542263945995906 |
| IN-NO: 20 to < 30 C | reportable                 | ridge_all         |     2817 | 14.827391134898356 | 10.319233187587864  | 1.4601212242855135 | 1.3494572533997218 | -1.9982747445112317  | 58.324458643947466   | 36.89540326238609  |
| IN-NO: 20 to < 30 C | reportable                 | per_zone_ridge    |     2817 | 14.814122102857567 | 10.319233187587864  | 1.5383476274552526 | 1.5008528334916629 | -5.501199683871917   | 57.969471068512604   | 36.454895377433445 |
| IN-NO: 30 to < 45 C | reportable                 | seasonal_naive    |     1931 | 11.964818068856585 | 11.964818068856585  | 1.0                | 1.0                | -3.5468724807246823  | 52.511651993785605   | 28.772443837858166 |
| IN-NO: 30 to < 45 C | reportable                 | hour_weekday_mean |     1931 | 29.996564283828334 | 11.964818068856585  | 2.520211418503177  | 2.18009051334655   | -29.91279964362475   | 98.80890730191611    | 52.712715984612    |
| IN-NO: 30 to < 45 C | reportable                 | ridge_all         |     1931 | 14.94910791953625  | 11.964818068856585  | 1.3041843980501622 | 1.2132267350264725 | -13.901837900708019  | 87.20870015535992    | 30.183998110230483 |
| IN-NO: 30 to < 45 C | reportable                 | per_zone_ridge    |     1931 | 15.642180523740516 | 11.964818068856585  | 1.2979766788144682 | 1.2657429659783408 | -11.923781423146385  | 73.58881408596582    | 38.127181097615164 |
| IN-NO: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NO: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | seasonal_naive    |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | hour_weekday_mean |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | ridge_all         |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: < 20 C       | insufficient rows to judge | per_zone_ridge    |       44 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: 20 to < 30 C | reportable                 | seasonal_naive    |     5269 | 6.792567240418472  | 6.792567240418472   | 1.0                | 1.0                | 0.45788456927566323  | 33.953311823875495   | 19.955428234321673 |
| IN-WE: 20 to < 30 C | reportable                 | hour_weekday_mean |     5269 | 18.185142997740847 | 6.792567240418472   | 2.806829728557908  | 2.560272380853345  | -13.661043013645582  | 73.69519832985387    | 37.81315799759783  |
| IN-WE: 20 to < 30 C | reportable                 | ridge_all         |     5269 | 14.887107414781294 | 6.792567240418472   | 2.1823913396544117 | 1.9572662101565548 | 1.7020130346881355   | 45.4735243879294     | 34.90908050491757  |
| IN-WE: 20 to < 30 C | reportable                 | per_zone_ridge    |     5269 | 16.305182956810008 | 6.792567240418472   | 2.405734921636693  | 2.1446988072074706 | 2.5602145613405103   | 38.64110836970962    | 34.70208426425717  |
| IN-WE: 30 to < 45 C | reportable                 | seasonal_naive    |     1361 | 6.568622730388593  | 6.568622730388593   | 1.0                | 1.0                | 0.7803128469210793   | 33.87215282880235    | 17.07349150402441  |
| IN-WE: 30 to < 45 C | reportable                 | hour_weekday_mean |     1361 | 9.611959306716306  | 6.568622730388593   | 1.5259582099324036 | 1.5140530690252891 | -7.855315989138715   | 73.91623806024981    | 23.099097929270577 |
| IN-WE: 30 to < 45 C | reportable                 | ridge_all         |     1361 | 11.357071821542414 | 6.568622730388593   | 1.6847845349554782 | 1.6372060674786446 | 7.210708641166505    | 19.250551065393093   | 27.62924096583466  |
| IN-WE: 30 to < 45 C | reportable                 | per_zone_ridge    |     1361 | 12.950818436667992 | 6.568622730388593   | 1.9120277482135282 | 1.7840182087512937 | 11.71865129366211    | 6.465833945628215    | 29.80277608905726  |
| IN-WE: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-WE: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: < 20 C       | reportable                 | seasonal_naive    |     1080 | 13.018098268644868 | 13.018098268644868  | 1.0                | 1.0                | 2.2926583081539755   | 37.77777777777778    | 35.25534679801804  |
| IN-SO: < 20 C       | reportable                 | hour_weekday_mean |     1080 | 17.42563934315582  | 13.018098268644868  | 1.5977905607588243 | 1.672422953575116  | -4.183057266914459   | 51.57407407407407    | 41.705152711334    |
| IN-SO: < 20 C       | reportable                 | ridge_all         |     1080 | 20.86583286253972  | 13.018098268644868  | 1.6283359604183187 | 1.4743881458554429 | 10.040470819716694   | 32.77777777777778    | 57.927562251135875 |
| IN-SO: < 20 C       | reportable                 | per_zone_ridge    |     1080 | 25.45807857454521  | 13.018098268644868  | 1.9924547685906744 | 1.7657837561609202 | 15.771918960135627   | 23.425925925925924   | 67.15276891549308  |
| IN-SO: 20 to < 30 C | reportable                 | seasonal_naive    |     4919 | 8.997057226046609  | 8.997057226046609   | 1.0                | 1.0                | -0.9402019402367378  | 43.26082537101037    | 24.485193933523252 |
| IN-SO: 20 to < 30 C | reportable                 | hour_weekday_mean |     4919 | 21.510531372770444 | 8.997057226046609   | 2.62572549506833   | 2.486954976098462  | -16.688371853959218  | 76.80422850172799    | 44.34514967273591  |
| IN-SO: 20 to < 30 C | reportable                 | ridge_all         |     4919 | 15.85223267194851  | 8.997057226046609   | 1.8410819465596746 | 1.6873385806411392 | -2.865280838949689   | 56.08863590160602    | 32.19570944703992  |
| IN-SO: 20 to < 30 C | reportable                 | per_zone_ridge    |     4919 | 19.228009522496638 | 8.997057226046609   | 2.1878893754165896 | 2.0569092551395514 | -0.13114307314545923 | 50.62004472453751    | 43.41534021361416  |
| IN-SO: 30 to < 45 C | reportable                 | seasonal_naive    |      675 | 9.12548397066801   | 9.12548397066801    | 1.0                | 1.0                | 0.8116293396040325   | 42.074074074074076   | 26.044358811792822 |
| IN-SO: 30 to < 45 C | reportable                 | hour_weekday_mean |      675 | 10.647683446364857 | 9.12548397066801    | 1.164665702007041  | 1.1088240125949773 | 1.902869344346352    | 31.25925925925926    | 26.61041660049059  |
| IN-SO: 30 to < 45 C | reportable                 | ridge_all         |      675 | 15.719748864381804 | 9.12548397066801    | 1.6485117189125698 | 1.436263427916359  | 13.623285284881613   | 10.37037037037037    | 33.457025307126514 |
| IN-SO: 30 to < 45 C | reportable                 | per_zone_ridge    |      675 | 16.80066284860513  | 9.12548397066801    | 1.809882721597875  | 1.5803001035611837 | 13.39384958853069    | 13.185185185185185   | 34.46749694026433  |
| IN-SO: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-SO: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: < 20 C       | reportable                 | seasonal_naive    |      837 | 7.101245994653031  | 7.101245994653031   | 1.0                | 1.0                | -0.1944892246278178  | 35.00597371565114    | 18.369391826378827 |
| IN-EA: < 20 C       | reportable                 | hour_weekday_mean |      837 | 8.975429776885811  | 7.101245994653031   | 1.2529797521159332 | 1.1682710013727826 | 1.5330838237356412   | 37.27598566308244    | 19.125339504821707 |
| IN-EA: < 20 C       | reportable                 | ridge_all         |      837 | 11.267904957822235 | 7.101245994653031   | 1.6468498074434166 | 1.4931387749070084 | -9.863052411480782   | 81.83990442054959    | 21.672633147833988 |
| IN-EA: < 20 C       | reportable                 | per_zone_ridge    |      837 | 10.311788367025411 | 7.101245994653031   | 1.3763667255676493 | 1.317647243893604  | 6.797068912738879    | 22.58064516129032    | 25.610551206880135 |
| IN-EA: 20 to < 30 C | reportable                 | seasonal_naive    |     5921 | 10.024945005779133 | 10.024945005779133  | 1.0                | 1.0                | 0.8939525212677693   | 37.15588583009627    | 29.16025272831706  |
| IN-EA: 20 to < 30 C | reportable                 | hour_weekday_mean |     5921 | 14.0273160479246   | 10.024945005779133  | 1.3247844806363631 | 1.138997932273714  | 4.524020316920003    | 39.18257051173788    | 34.53560753488254  |
| IN-EA: 20 to < 30 C | reportable                 | ridge_all         |     5921 | 18.789098946192205 | 10.024945005779133  | 1.7350800841459417 | 1.609159128352777  | 9.106330479884313    | 32.47762202330687    | 60.38716236971076  |
| IN-EA: 20 to < 30 C | reportable                 | per_zone_ridge    |     5921 | 12.025231793769596 | 10.024945005779133  | 1.126091220939539  | 1.0434207050560795 | 4.999880863000508    | 32.34250971119743    | 34.904679977554984 |
| IN-EA: 30 to < 45 C | reportable                 | seasonal_naive    |     1819 | 12.582008661993044 | 12.582008661993044  | 1.0                | 1.0                | 4.943018375721486    | 30.566245189664652   | 34.744630146381866 |
| IN-EA: 30 to < 45 C | reportable                 | hour_weekday_mean |     1819 | 26.01265705823572  | 12.582008661993044  | 1.8847641280062326 | 1.5950305677940335 | 22.447348132940203   | 13.743815283122595   | 56.67343136644728  |
| IN-EA: 30 to < 45 C | reportable                 | ridge_all         |     1819 | 51.10264128968872  | 12.582008661993044  | 3.6740418778513266 | 3.1107351716430687 | 50.79753506017988    | 1.7592083562396923   | 104.25102093192346 |
| IN-EA: 30 to < 45 C | reportable                 | per_zone_ridge    |     1819 | 20.052676959745902 | 12.582008661993044  | 1.4661684115242961 | 1.2949521623958198 | 16.322427288755215   | 15.283122594832326   | 50.783766563759904 |
| IN-EA: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-EA: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: < 20 C       | reportable                 | seasonal_naive    |     1696 | 25.097495600175268 | 25.097495600175268  | 1.0                | 1.0                | -3.417991952848458   | 49.764150943396224   | 77.04701388725155  |
| IN-NE: < 20 C       | reportable                 | hour_weekday_mean |     1696 | 23.020131872406367 | 25.097495600175268  | 0.9861702246256729 | 0.8803516095533449 | -16.878512293794195  | 80.18867924528303    | 49.48176271022928  |
| IN-NE: < 20 C       | reportable                 | ridge_all         |     1696 | 27.241608720681228 | 25.097495600175268  | 1.2214618657415557 | 1.0602703099801714 | -23.19977675105351   | 86.49764150943396    | 48.070896424928094 |
| IN-NE: < 20 C       | reportable                 | per_zone_ridge    |     1696 | 173.93990190174821 | 25.097495600175268  | 7.2305357782237385 | 7.9073092222918335 | 173.65075262767314   | 0.9433962264150944   | 525.7619709738639  |
| IN-NE: 20 to < 30 C | reportable                 | seasonal_naive    |     3931 | 18.781538480990427 | 18.781538480990427  | 1.0                | 1.0                | 0.0503808934024838   | 47.77410328160773    | 60.084181250598206 |
| IN-NE: 20 to < 30 C | reportable                 | hour_weekday_mean |     3931 | 18.884862399873825 | 18.781538480990427  | 1.0694616645258122 | 0.9694512952301858 | -7.844678348852912   | 67.71813787840244    | 45.86641785205206  |
| IN-NE: 20 to < 30 C | reportable                 | ridge_all         |     3931 | 20.615726705369323 | 18.781538480990427  | 1.120513625375335  | 1.015256031192351  | 1.2717289910998986   | 53.167133045026716   | 51.72085186964797  |
| IN-NE: 20 to < 30 C | reportable                 | per_zone_ridge    |     3931 | 51.418143112570654 | 18.781538480990427  | 2.730744774492043  | 4.047712244182434  | 44.24111380097287    | 22.131773085728824   | 225.39994119710542 |
| IN-NE: 30 to < 45 C | reportable                 | seasonal_naive    |      806 | 16.224917586163656 | 16.224917586163656  | 1.0                | 1.0                | 4.780485595118385    | 37.096774193548384   | 58.095961401945985 |
| IN-NE: 30 to < 45 C | reportable                 | hour_weekday_mean |      806 | 16.291618707413917 | 16.224917586163656  | 1.0523584081459574 | 0.915275435129705  | -0.02798349468534517 | 62.903225806451616   | 52.540027152617114 |
| IN-NE: 30 to < 45 C | reportable                 | ridge_all         |      806 | 30.204944521196598 | 16.224917586163656  | 1.840298117327789  | 1.580321889200205  | 28.6341235836002     | 5.831265508684864    | 99.75140341715584  |
| IN-NE: 30 to < 45 C | reportable                 | per_zone_ridge    |      806 | 18.933733742309997 | 16.224917586163656  | 1.19151014640722   | 1.0700547016548616 | 14.142363552128323   | 22.084367245657567   | 66.95329959380038  |
| IN-NE: >= 45 C      | absent                     | seasonal_naive    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | hour_weekday_mean |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | ridge_all         |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |
| IN-NE: >= 45 C      | absent                     | per_zone_ridge    |        0 | not reportable     | not reportable      | not reportable     | not reportable     | not reportable       | not reportable       | not reportable     |

## Stratification: time_rolling

| segment    | status     | model             |   n_rows |   mape_pct |   baseline_mape_pct |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |
|:-----------|:-----------|:------------------|---------:|-----------:|--------------------:|-------:|--------:|------------------:|---------------------:|--------------:|
| 2024-09-30 | reportable | seasonal_naive    |      720 |     17.588 |              17.588 |  1.000 |   1.000 |            -6.403 |               55.972 |        30.921 |
| 2024-09-30 | reportable | hour_weekday_mean |      720 |     14.087 |              17.588 |  0.777 |   0.702 |            -1.121 |               53.472 |        19.849 |
| 2024-09-30 | reportable | ridge_all         |      720 |     18.878 |              17.588 |  1.000 |   1.055 |             6.611 |               34.861 |        54.556 |
| 2024-09-30 | reportable | per_zone_ridge    |      720 |     13.918 |              17.588 |  0.740 |   0.679 |             2.221 |               52.361 |        26.710 |
| 2024-10-31 | reportable | seasonal_naive    |      720 |     15.093 |              15.093 |  1.000 |   1.000 |             4.663 |               42.083 |        35.171 |
| 2024-10-31 | reportable | hour_weekday_mean |      720 |     16.058 |              15.093 |  1.182 |   1.105 |           -11.689 |               77.778 |        23.783 |
| 2024-10-31 | reportable | ridge_all         |      720 |     16.839 |              15.093 |  1.192 |   1.231 |            -5.057 |               54.444 |        38.695 |
| 2024-10-31 | reportable | per_zone_ridge    |      720 |     15.822 |              15.093 |  1.164 |   1.095 |           -11.332 |               77.778 |        23.976 |
| 2024-11-30 | reportable | seasonal_naive    |     1402 |     16.178 |              16.178 |  1.000 |   1.000 |             7.583 |               29.886 |        47.941 |
| 2024-11-30 | reportable | hour_weekday_mean |     1402 |     13.670 |              16.178 |  0.867 |   0.839 |             4.404 |               34.593 |        31.593 |
| 2024-11-30 | reportable | ridge_all         |     1402 |     22.750 |              16.178 |  1.543 |   1.643 |            17.599 |               19.900 |        66.167 |
| 2024-11-30 | reportable | per_zone_ridge    |     1402 |     21.277 |              16.178 |  1.447 |   1.471 |            19.437 |                9.986 |        47.385 |
| 2024-12-31 | reportable | seasonal_naive    |     3363 |     18.545 |              18.545 |  1.000 |   1.000 |            -3.899 |               46.476 |        71.588 |
| 2024-12-31 | reportable | hour_weekday_mean |     3363 |     21.437 |              18.545 |  1.303 |   1.353 |            -1.022 |               51.710 |        56.342 |
| 2024-12-31 | reportable | ridge_all         |     3363 |     25.740 |              18.545 |  1.440 |   1.278 |             7.720 |               40.440 |        66.199 |
| 2024-12-31 | reportable | per_zone_ridge    |     3363 |     70.940 |              18.545 |  1.837 |   1.644 |            65.614 |               18.941 |       342.935 |
| 2025-01-31 | reportable | seasonal_naive    |     3600 |     12.006 |              12.006 |  1.000 |   1.000 |             1.430 |               40.444 |        35.122 |
| 2025-01-31 | reportable | hour_weekday_mean |     3600 |     18.000 |              12.006 |  1.868 |   2.075 |            -3.613 |               59.361 |        46.896 |
| 2025-01-31 | reportable | ridge_all         |     3600 |     17.733 |              12.006 |  1.500 |   1.437 |             1.767 |               48.028 |        48.470 |
| 2025-01-31 | reportable | per_zone_ridge    |     3600 |     58.929 |              12.006 |  1.856 |   1.752 |            51.940 |               24.333 |       346.361 |
| 2025-02-28 | reportable | seasonal_naive    |     3600 |     10.009 |              10.009 |  1.000 |   1.000 |            -1.979 |               48.500 |        34.845 |
| 2025-02-28 | reportable | hour_weekday_mean |     3600 |     14.116 |              10.009 |  2.461 |   2.946 |            -8.085 |               70.750 |        34.346 |
| 2025-02-28 | reportable | ridge_all         |     3600 |     14.563 |              10.009 |  1.918 |   1.882 |             0.786 |               46.917 |        34.185 |
| 2025-02-28 | reportable | per_zone_ridge    |     3600 |     28.810 |              10.009 |  2.052 |   2.176 |            19.931 |               34.000 |       103.543 |
| 2025-03-31 | reportable | seasonal_naive    |     3600 |     10.407 |              10.407 |  1.000 |   1.000 |            -0.316 |               41.778 |        27.475 |
| 2025-03-31 | reportable | hour_weekday_mean |     3600 |     14.392 |              10.407 |  2.136 |   2.377 |            -8.134 |               64.306 |        34.713 |
| 2025-03-31 | reportable | ridge_all         |     3600 |     15.249 |              10.407 |  1.678 |   1.653 |             4.173 |               42.694 |        41.360 |
| 2025-03-31 | reportable | per_zone_ridge    |     3600 |     17.979 |              10.407 |  1.722 |   1.716 |             7.915 |               35.222 |        48.847 |
| 2025-04-30 | reportable | seasonal_naive    |     3600 |     12.799 |              12.799 |  1.000 |   1.000 |            -0.092 |               46.111 |        42.137 |
| 2025-04-30 | reportable | hour_weekday_mean |     3600 |     20.028 |              12.799 |  2.400 |   2.581 |            -6.368 |               60.972 |        43.387 |
| 2025-04-30 | reportable | ridge_all         |     3600 |     20.533 |              12.799 |  1.868 |   1.967 |             8.287 |               39.472 |        71.009 |
| 2025-04-30 | reportable | per_zone_ridge    |     3600 |     17.722 |              12.799 |  1.631 |   1.695 |             6.433 |               36.611 |        46.249 |
| 2025-05-31 | reportable | seasonal_naive    |     3600 |     16.752 |              16.752 |  1.000 |   1.000 |             4.796 |               33.444 |        44.957 |
| 2025-05-31 | reportable | hour_weekday_mean |     3600 |     23.115 |              16.752 |  1.624 |   1.590 |            -2.502 |               54.722 |        54.825 |
| 2025-05-31 | reportable | ridge_all         |     3600 |     23.972 |              16.752 |  1.317 |   1.298 |            11.786 |               41.194 |        89.335 |
| 2025-05-31 | reportable | per_zone_ridge    |     3600 |     21.336 |              16.752 |  1.258 |   1.208 |            10.165 |               32.000 |        58.291 |
| 2025-06-30 | reportable | seasonal_naive    |     3482 |     10.623 |              10.623 |  1.000 |   1.000 |            -1.511 |               50.172 |        24.632 |
| 2025-06-30 | reportable | hour_weekday_mean |     3482 |     23.065 |              10.623 |  2.299 |   2.143 |           -11.071 |               65.882 |        49.142 |
| 2025-06-30 | reportable | ridge_all         |     3482 |     21.460 |              10.623 |  1.829 |   1.694 |             1.637 |               54.078 |        64.770 |
| 2025-06-30 | reportable | per_zone_ridge    |     3482 |     17.744 |              10.623 |  1.720 |   1.690 |            -1.101 |               46.783 |        39.704 |
| 2025-08-31 | reportable | seasonal_naive    |     3482 |      6.262 |               6.262 |  1.000 |   1.000 |             1.501 |               28.690 |        16.353 |
| 2025-08-31 | reportable | hour_weekday_mean |     3482 |     21.527 |               6.262 |  3.710 |   3.202 |           -10.829 |               67.088 |        44.338 |
| 2025-08-31 | reportable | ridge_all         |     3482 |     19.270 |               6.262 |  3.145 |   2.758 |             2.748 |               50.029 |        57.497 |
| 2025-08-31 | reportable | per_zone_ridge    |     3482 |     14.495 |               6.262 |  2.594 |   2.522 |             3.056 |               33.831 |        33.643 |

## Lead-Time Investigation

| model             |   first_lead_mape_pct |   last_lead_mape_pct |   nondecreasing_steps |   total_steps |
|:------------------|----------------------:|---------------------:|----------------------:|--------------:|
| seasonal_naive    |                12.694 |               12.079 |                    12 |            23 |
| hour_weekday_mean |                23.024 |               22.782 |                    10 |            23 |
| ridge_all         |                18.083 |               18.362 |                    11 |            23 |
| per_zone_ridge    |                27.117 |               27.082 |                    12 |            23 |

Error is not guaranteed to rise monotonically across these leads. This was treated as a suspected leak and checked: (1) the saved seasonal source timestamps satisfy the issue-minus-purge cutoff; (2) fold training ends before the first issue's cutoff; (3) serving features are built without demand, and the target is attached only for scoring; (4) no holdout rows are scored. Tests exercise these boundaries, including future-target perturbations. No future-demand input was found in those paths.

Two confounders remain: lead time maps one-to-one to hour of day in a fixed daily forecast, and the deliberately simple weather-noise bridge has constant sigma, so it cannot reproduce lead-dependent weather forecast degradation. Calendar-only baselines do not consume weather at all. This investigation permits the Stage 2 benchmark to be recorded, but does not establish production forecast skill or validate the assumed sigmas. Recheck with exact captured vintages when coverage permits; do not force a rising curve by selecting noise or parameters from these test results.

## Reproducibility

Machine-readable fold, coverage, summary and stratified tables are in `reports/baseline/`. All metrics, including the full peak/ramp diagnostics for each stratum, are in stratified.csv. Predictions and issue/source timestamps are in the DVC-tracked `data/interim/baseline_predictions.parquet`. manifest.json records actual input-file and pointer hashes, source/config hashes, runtime versions, seed and split boundaries. Temperature bands use observed temperatures for analysis only; sparse interior bands are merged, the hottest band stays separate, and segments below the sufficiency threshold are marked insufficient rather than quoted as performance. Absent zone/band cells remain absent.
