# Ablation

Frozen parameters and converged fits. One feature group is removed at a time; the cyclic seasonal candidate is a separately labelled addition. No feature or hyperparameter is selected from these test figures.

The measured-only and mixed-policy comparison covers the identical final three development folds. Compare those two rows with one another, not with twelve-fold headlines. This reduced comparison does not establish a full-year policy effect. Every score uses measured targets and the common baseline-availability cohort. MASE/RMSSE use seasonal-naive denominators; below 1 is required.

| variant                 |   folds |   n_rows |    mase |   rmsse |   mape_pct |
|:------------------------|--------:|---------:|--------:|--------:|-----------:|
| add_cyclic_day_of_year  |      12 |    35033 | 1.4811  | 1.47016 |   15.6581  |
| include_earlier_east    |      12 |    35033 | 1.23234 | 1.22891 |   14.0124  |
| measured_only           |       3 |    10564 | 1.09329 | 1.03062 |    7.84302 |
| mixed_same_three_folds  |       3 |    10564 | 1.07341 | 1.02812 |    7.83361 |
| without_cooling_degrees |      12 |    35033 | 1.25632 | 1.25429 |   14.2118  |
| without_day_of_week     |      12 |    35033 | 1.23204 | 1.22615 |   13.9661  |
| without_hour_of_day     |      12 |    35033 | 1.37797 | 1.36967 |   15.1371  |
| without_is_holiday      |      12 |    35033 | 1.25538 | 1.24754 |   14.2522  |
| without_temperature     |      12 |    35033 | 1.86508 | 1.88282 |   19.1424  |
| without_trend           |      12 |    35033 | 1.91269 | 1.93411 |   16.847   |
| without_zone            |      12 |    35033 | 3.85081 | 3.5459  |   37.547   |

No tested alternative clears mean-fold MASE below 1. The existing feature and estimation policy remain unchanged. The final holdout is unscored.
