# Frozen demand-history model evaluation

Final reserved-year evaluation. The candidate was fixed before scoring.

The candidate averages the latest two eligible same-zone, IST-hour and weekday measured values at least ten days before issue. It falls back to one when only one exists. No demand from after the issue cutoff enters the predictor.

## Overall metrics

| model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
| history_mean_2 |    43288 |     7.6881 | 2946.9245 | 4467.5925 | 0.9445 |  0.9391 |           -0.1416 |              40.5493 |       21.4965 |          1800 |     3211.6269 |      9000 |      610.3604 |      0.9800 |
| seasonal_naive |    43288 |     7.9852 | 3120.1568 | 4757.1468 | 1.0000 |  1.0000 |           -0.1168 |              40.2305 |       21.8240 |          1800 |     3438.9656 |      9000 |      622.8422 |      1.0000 |

## Mean of monthly scores

| model          |   mase |   rmsse |   mape_pct |
|:---------------|-------:|--------:|-----------:|
| history_mean_2 | 0.9571 |  0.9556 |     7.6934 |
| seasonal_naive | 1.0000 |  1.0000 |     7.9764 |

## Regional metrics

| segment   | model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|:----------|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
| IN-NO     | seasonal_naive |     8657 |     9.1393 | 5083.0057 | 6835.3446 | 1.0000 |  1.0000 |            0.0502 |              41.2268 |       25.5078 |           360 |     6011.9639 |      1800 |      813.2217 |      1.0000 |
| IN-NO     | history_mean_2 |     8657 |     8.7590 | 4814.7608 | 6383.6678 | 0.9472 |  0.9339 |            0.0154 |              42.1971 |       23.8975 |           360 |     5513.2181 |      1800 |      809.1047 |      0.9949 |
| IN-WE     | seasonal_naive |     8658 |     6.1688 | 4905.7961 | 6428.5582 | 1.0000 |  1.0000 |           -0.2227 |              38.4384 |       15.7838 |           360 |     5380.3417 |      1800 |      953.0172 |      1.0000 |
| IN-WE     | history_mean_2 |     8658 |     5.8756 | 4654.5839 | 6051.3967 | 0.9488 |  0.9413 |           -0.2169 |              37.3181 |       14.9331 |           360 |     5055.7653 |      1800 |      931.5681 |      0.9775 |
| IN-SO     | seasonal_naive |     8658 |     6.6165 | 3319.6163 | 4304.0364 | 1.0000 |  1.0000 |           -0.2067 |              41.0949 |       16.4651 |           360 |     3645.0917 |      1800 |      656.8339 |      1.0000 |
| IN-SO     | history_mean_2 |     8658 |     6.2407 | 3114.1994 | 4089.4330 | 0.9381 |  0.9501 |           -0.2386 |              41.3490 |       15.6958 |           360 |     3439.3097 |      1800 |      633.2408 |      0.9641 |
| IN-EA     | seasonal_naive |     8659 |     6.5194 | 1994.4935 | 2533.1589 | 1.0000 |  1.0000 |           -0.2876 |              37.5794 |       15.6783 |           360 |     1677.5611 |      1800 |      538.3672 |      1.0000 |
| IN-EA     | history_mean_2 |     8659 |     6.0701 | 1855.7924 | 2356.5496 | 0.9305 |  0.9303 |           -0.3397 |              37.7295 |       15.0588 |           360 |     1594.9528 |      1800 |      531.6069 |      0.9874 |
| IN-NE     | seasonal_naive |     8656 |    11.4831 |  297.5772 |  402.2087 | 1.0000 |  1.0000 |            0.0829 |              42.8142 |       28.3489 |           360 |      479.8694 |      1800 |      152.7711 |      1.0000 |
| IN-NE     | history_mean_2 |     8656 |    11.4964 |  295.0153 |  386.0059 | 0.9914 |  0.9597 |            0.0717 |              44.1543 |       28.0917 |           360 |      454.8889 |      1800 |      146.2817 |      0.9575 |

## Monthly metrics

|   fold | model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|-------:|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
|      1 | history_mean_2 |     3600 |     7.4790 | 3099.7397 | 4547.6874 | 0.9235 |  0.9077 |           -0.7955 |              47.2778 |       19.9509 |           150 |     3385.1700 |       750 |      591.3613 |      0.9772 |
|      2 | history_mean_2 |     3562 |    14.0788 | 5115.5521 | 7250.3171 | 1.0599 |  1.0112 |           11.3962 |               9.5171 |       34.6406 |           145 |     4164.4621 |       725 |      845.5428 |      1.0536 |
|      3 | history_mean_2 |     3484 |     8.5842 | 2701.7127 | 3969.9589 | 0.9882 |  1.0006 |            2.6629 |              30.9989 |       21.0676 |           145 |     3693.1621 |       725 |      786.0421 |      1.0495 |
|      4 | history_mean_2 |     3720 |     6.2898 | 2134.3171 | 2971.6684 | 1.0894 |  1.1049 |           -2.3346 |              54.3280 |       15.4034 |           155 |     3215.4258 |       775 |      420.7729 |      1.0022 |
|      5 | history_mean_2 |     3720 |     4.9135 | 1708.0301 | 2421.6202 | 0.9469 |  0.9369 |           -1.1340 |              38.6022 |       12.4909 |           155 |     2054.0000 |       775 |      482.6658 |      1.0098 |
|      6 | history_mean_2 |     3122 |     6.0026 | 1775.3839 | 2332.9250 | 1.0615 |  1.0404 |           -0.7750 |              46.1883 |       17.6139 |           130 |     1683.3038 |       650 |      475.4015 |      0.9584 |
|      7 | history_mean_2 |     3720 |     8.2306 | 2659.4086 | 3909.4737 | 0.9141 |  0.9289 |           -2.5150 |              42.9032 |       24.7652 |           155 |     2644.8419 |       775 |      661.2168 |      1.0194 |
|      8 | history_mean_2 |     3600 |     9.0602 | 3901.9256 | 5902.8959 | 0.9455 |  0.9726 |           -4.2725 |              56.9722 |       23.3012 |           150 |     4479.2100 |       750 |      764.1913 |      1.0062 |
|      9 | history_mean_2 |     3720 |     8.3892 | 3795.7804 | 5388.8077 | 0.8220 |  0.8375 |           -1.9860 |              46.6667 |       20.8842 |           155 |     4010.7032 |       775 |      609.8381 |      0.9518 |
|     10 | history_mean_2 |     3600 |     6.7213 | 2637.6868 | 3879.3567 | 0.9041 |  0.9072 |           -1.6263 |              37.5833 |       18.7353 |           150 |     2740.5967 |       750 |      502.3633 |      0.8977 |
|     11 | history_mean_2 |     3720 |     7.1092 | 3209.8105 | 4742.6102 | 0.8494 |  0.8559 |           -0.0733 |              41.4247 |       17.2447 |           155 |     3242.0774 |       775 |      640.8774 |      0.8784 |
|     12 | history_mean_2 |     3720 |     5.4629 | 2537.7309 | 3575.8510 | 0.9804 |  0.9634 |            0.1172 |              33.7634 |       13.1212 |           155 |     3103.9000 |       775 |      549.6574 |      0.9371 |
|      1 | seasonal_naive |     3600 |     8.0169 | 3356.4775 | 5010.3530 | 1.0000 |  1.0000 |           -0.7508 |              44.1389 |       22.1444 |           150 |     3574.2067 |       750 |      605.1440 |      1.0000 |
|      2 | seasonal_naive |     3562 |    13.2863 | 4826.3026 | 7170.2706 | 1.0000 |  1.0000 |            9.9017 |              12.1842 |       33.9262 |           145 |     4258.9379 |       725 |      802.5545 |      1.0000 |
|      3 | seasonal_naive |     3484 |     8.3333 | 2733.8519 | 3967.7110 | 1.0000 |  1.0000 |            1.0363 |              37.3995 |       20.1653 |           145 |     3739.9448 |       725 |      748.9959 |      1.0000 |
|      4 | seasonal_naive |     3720 |     6.1168 | 1959.1704 | 2689.5702 | 1.0000 |  1.0000 |           -1.9536 |              49.7312 |       15.9386 |           155 |     2771.5935 |       775 |      419.8400 |      1.0000 |
|      5 | seasonal_naive |     3720 |     5.2443 | 1803.7468 | 2584.6951 | 1.0000 |  1.0000 |           -0.5991 |              35.3763 |       13.9120 |           155 |     2207.6968 |       775 |      477.9871 |      1.0000 |
|      6 | seasonal_naive |     3122 |     5.6962 | 1672.5429 | 2242.2759 | 1.0000 |  1.0000 |           -0.9960 |              44.7149 |       17.3858 |           130 |     1676.2385 |       650 |      496.0338 |      1.0000 |
|      7 | seasonal_naive |     3720 |     8.5905 | 2909.3188 | 4208.7214 | 1.0000 |  1.0000 |           -1.7296 |              41.7742 |       24.4952 |           155 |     2951.6710 |       775 |      648.6581 |      1.0000 |
|      8 | seasonal_naive |     3600 |     9.4200 | 4126.8833 | 6068.9700 | 1.0000 |  1.0000 |           -3.7037 |              55.4167 |       23.3794 |           150 |     4597.1600 |       750 |      759.5133 |      1.0000 |
|      9 | seasonal_naive |     3720 |    10.1152 | 4617.6524 | 6434.6661 | 1.0000 |  1.0000 |           -1.2752 |              47.0430 |       24.5905 |           155 |     4872.7677 |       775 |      640.7006 |      1.0000 |
|     10 | seasonal_naive |     3600 |     7.0161 | 2917.5008 | 4276.3829 | 1.0000 |  1.0000 |           -1.5990 |              41.0000 |       18.3746 |           150 |     3159.4533 |       750 |      559.6187 |      1.0000 |
|     11 | seasonal_naive |     3720 |     8.2952 | 3778.7621 | 5541.0006 | 1.0000 |  1.0000 |            0.6921 |              38.1452 |       20.7317 |           155 |     3914.9032 |       775 |      729.5690 |      1.0000 |
|     12 | seasonal_naive |     3720 |     5.5867 | 2588.4831 | 3711.7133 | 1.0000 |  1.0000 |           -0.2513 |              35.8333 |       13.9383 |           155 |     3363.7290 |       775 |      586.5703 |      1.0000 |

## Interpretation and limits

Lower is better for errors; signed bias is positive for overforecast and negative for underforecast. Shortfall frequency counts forecasts more than the configured 3% below actual demand. MASE and RMSSE use the out-of-sample seasonal baseline denominator on identical rows. Mean-month and pooled metrics use different weighting. Peak metrics require complete measured zone-days; ramps never bridge missing hours. CSV breakdowns include sample counts, and sparse temperature bands are explicitly marked insufficient.

The demand availability gap remains an assumption; revised historical values do not recreate the original publication state. Historical analyses have previously explored the cached dataset; this year was reserved from forecast selection, not completely unseen throughout the project. This candidate uses no forecast weather values; temperature is observed analysis context only. No production champion is approved by this report. Demand-dependent serving, monitor recalibration, deployment and live acceptance remain separate requirements.

Diagnostic comparison result: PASS. Reasons: [].
