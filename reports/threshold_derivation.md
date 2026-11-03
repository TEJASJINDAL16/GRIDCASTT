# Threshold Replay

Fully settled, refreshed-fold replay. Thresholds are provisionally optimistic: historical first-settlement coverage is insufficient. Delay figures omit settlement lag.

Measured target rows: 35,033. Replay span: 365 days. Complete daily windows (overlapping, not independent): {'IN-EA': 197, 'IN-NE': 151, 'IN-NO': 161, 'IN-SO': 161, 'IN-WE': 161, 'pooled': 151}.

|                   |   selected |
|:------------------|-----------:|
| scale             |    1.01724 |
| debounce          |    1       |
| episodes          |    0       |
| episodes_per_year |    0       |
| delay_2_days      |   30       |
| delay_5_days      |   23       |
| delay_10_days     |   18       |
| mean_delay        |   23.6667  |

All candidates: calibration/sweep.csv. Seven-day watch candidates: calibration/watch_sweep.csv. Veto tolerances use one sample standard deviation across folds; a missing top-band tolerance prevents promotion.

Model passes selection gate: False. Reasons: ['mean fold mase did not improve/hold', 'mean fold rmsse did not improve/hold'].
