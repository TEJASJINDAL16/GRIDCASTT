# Ablation

Frozen parameters; no feature is selected using these test results. The measured-only comparison uses only the final three development folds and must be compared with mixed_same_three_folds, not the twelve-fold headline. All scores use measured targets and identical baseline availability. Out-of-sample MASE/RMSSE denominators are seasonal naive.

| variant                 |   folds |    mase |   rmsse |   mape_pct |
|:------------------------|--------:|--------:|--------:|-----------:|
| without_hour_of_day     |      12 | 1.37835 | 1.37002 |   15.1407  |
| without_day_of_week     |      12 | 1.24863 | 1.24231 |   14.0959  |
| without_is_holiday      |      12 | 1.26295 | 1.25498 |   14.2952  |
| without_temperature     |      12 | 1.86563 | 1.8855  |   19.1251  |
| without_trend           |      12 | 1.91106 | 1.93406 |   16.7928  |
| without_cooling_degrees |      12 | 1.26252 | 1.26007 |   14.2577  |
| without_zone            |      12 | 3.85081 | 3.5459  |   37.547   |
| add_cyclic_day_of_year  |      12 | 1.48141 | 1.46973 |   15.6515  |
| measured_only           |       3 | 1.11404 | 1.05306 |    8.00206 |
| include_earlier_east    |      12 | 1.2357  | 1.23134 |   14.0432  |
| mixed_same_three_folds  |       3 | 1.11276 | 1.07224 |    7.89872 |
