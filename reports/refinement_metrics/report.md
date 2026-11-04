# Frozen demand-history model evaluation

Development metrics; model selection has examined this period.

The candidate averages the latest two eligible same-zone, IST-hour and weekday measured values at least ten days before issue. It falls back to one when only one exists. No demand from after the issue cutoff enters the predictor.

## Overall metrics

| model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
| history_mean_2 |    35033 |    11.3041 | 3618.0442 | 5244.1776 | 0.9512 |  0.9477 |            0.2978 |              41.1241 |       34.0311 |          1459 |     3825.9620 |      7295 |      654.1098 |      0.9551 |
| seasonal_naive |    35033 |    11.7889 | 3803.6166 | 5533.8623 | 1.0000 |  1.0000 |            0.3764 |              40.5646 |       34.8493 |          1459 |     4038.6230 |      7295 |      684.8724 |      1.0000 |

## Mean of monthly scores

| model          |   mase |   rmsse |   mape_pct |
|:---------------|-------:|--------:|-----------:|
| history_mean_2 | 0.9652 |  0.9663 |    12.1589 |
| seasonal_naive | 1.0000 |  1.0000 |    12.5707 |

## Regional metrics

| segment   | model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|:----------|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
| IN-NO     | seasonal_naive |     6675 |    12.8238 | 5615.8896 | 7233.6409 | 1.0000 |  1.0000 |           -0.0863 |              45.4382 |       32.9361 |           278 |     6013.6331 |      1390 |      960.0122 |      1.0000 |
| IN-NO     | history_mean_2 |     6675 |    11.7080 | 5018.8425 | 6367.0258 | 0.8937 |  0.8802 |           -0.5754 |              47.0262 |       30.0132 |           278 |     5274.9766 |      1390 |      945.3205 |      0.9847 |
| IN-WE     | seasonal_naive |     6674 |     6.7822 | 5663.4705 | 7474.0626 | 1.0000 |  1.0000 |            0.4474 |              34.2823 |       19.3841 |           278 |     6262.3453 |      1390 |     1111.8345 |      1.0000 |
| IN-WE     | history_mean_2 |     6674 |     6.6698 | 5552.9670 | 7419.8928 | 0.9805 |  0.9928 |            0.5153 |              32.8888 |       19.3996 |           278 |     6292.4946 |      1390 |     1036.5428 |      0.9323 |
| IN-SO     | seasonal_naive |     6674 |     9.6607 | 3777.8768 | 4895.4724 | 1.0000 |  1.0000 |           -0.2399 |              42.2535 |       27.0053 |           278 |     4150.4388 |      1390 |      803.8626 |      1.0000 |
| IN-SO     | history_mean_2 |     6674 |     9.6781 | 3762.6334 | 4819.3199 | 0.9960 |  0.9844 |           -0.3923 |              44.6509 |       26.2894 |           278 |     4218.7500 |      1390 |      763.0054 |      0.9492 |
| IN-EA     | seasonal_naive |     8577 |    10.2819 | 3447.1534 | 4678.1518 | 1.0000 |  1.0000 |            1.6465 |              35.5486 |       29.4091 |           357 |     3263.4370 |      1785 |      476.6134 |      1.0000 |
| IN-EA     | history_mean_2 |     8577 |     9.7433 | 3265.4549 | 4421.9645 | 0.9473 |  0.9452 |            2.0094 |              34.4992 |       28.7746 |           357 |     2903.1008 |      1785 |      460.4392 |      0.9661 |
| IN-NE     | seasonal_naive |     6433 |    20.1264 |  495.6086 |  692.9397 | 1.0000 |  1.0000 |           -0.2714 |              46.9610 |       69.8601 |           268 |      599.8507 |      1340 |      110.5619 |      1.0000 |
| IN-NE     | history_mean_2 |     6433 |    19.4608 |  477.2336 |  647.9465 | 0.9629 |  0.9351 |           -0.5879 |              48.7176 |       61.3063 |           268 |      586.2015 |      1340 |      100.3578 |      0.9077 |

## Monthly metrics

|   fold | model          |   n_rows |   mape_pct |    mae_mw |   rmse_mw |   mase |   rmsse |   signed_bias_pct |   shortfall_freq_pct |   p95_abs_pct |   n_peak_days |   peak_mae_mw |   n_ramps |   ramp_mae_mw |   ramp_mase |
|-------:|:---------------|---------:|-----------:|----------:|----------:|-------:|--------:|------------------:|---------------------:|--------------:|--------------:|--------------:|----------:|--------------:|------------:|
|      1 | history_mean_2 |      720 |    18.1159 | 6810.2549 | 7559.4566 | 1.0286 |  0.9784 |           -5.0309 |              53.4722 |       29.7445 |            30 |     6896.6167 |       150 |      250.0433 |      0.9076 |
|      2 | history_mean_2 |      744 |    14.7185 | 5558.4832 | 6627.1491 | 1.0021 |  1.0254 |            3.4553 |              44.8925 |       35.0358 |            31 |     4662.5161 |       155 |      187.7290 |      0.8813 |
|      3 | history_mean_2 |     1402 |    15.1090 | 5351.5210 | 6507.2825 | 0.9305 |  0.9278 |            8.7667 |              23.4665 |       41.0562 |            58 |     4289.0862 |       290 |      862.1483 |      1.0713 |
|      4 | history_mean_2 |     3483 |    20.5275 | 5074.5620 | 7307.9039 | 1.0620 |  1.0519 |           -2.1796 |              50.1005 |       63.5804 |           145 |     5476.0345 |       725 |      587.7745 |      0.9565 |
|      5 | history_mean_2 |     3720 |    10.9639 | 3142.4840 | 4367.1609 | 0.9048 |  0.8919 |            0.9108 |              38.8172 |       31.2923 |           155 |     3466.2677 |       775 |      704.0987 |      0.9417 |
|      6 | history_mean_2 |     3360 |     9.4105 | 2636.1963 | 3682.0543 | 1.0295 |  1.0459 |           -3.1443 |              52.2321 |       28.6657 |           140 |     2833.0464 |       700 |      721.2771 |      0.9757 |
|      7 | history_mean_2 |     3720 |    10.2941 | 3319.7526 | 4524.3004 | 0.9813 |  0.9466 |            0.3087 |              39.9462 |       25.8231 |           155 |     3729.6548 |       775 |      737.9619 |      0.9673 |
|      8 | history_mean_2 |     3600 |    11.5888 | 3327.6278 | 4677.1237 | 0.8742 |  0.8822 |            0.2991 |              46.1389 |       37.2349 |           150 |     3899.8700 |       750 |      764.3500 |      1.0320 |
|      9 | history_mean_2 |     3720 |    15.6910 | 5154.4387 | 7305.4155 | 0.9446 |  0.9443 |            4.6381 |              36.0753 |       41.6845 |           155 |     4882.9581 |       775 |      772.3342 |      0.9307 |
|     10 | history_mean_2 |     3482 |     8.7411 | 3672.7674 | 5236.8751 | 0.8074 |  0.8099 |           -2.9523 |              51.3211 |       21.1341 |           145 |     3863.9690 |       725 |      630.9848 |      0.8492 |
|     11 | history_mean_2 |     3480 |     4.8737 | 2059.5372 | 3127.1150 | 1.0702 |  1.1540 |           -0.2338 |              33.5920 |       12.1697 |           145 |     2377.0586 |       725 |      495.4690 |      0.9442 |
|     12 | history_mean_2 |     3602 |     5.8736 | 2367.4729 | 3526.7559 | 0.9471 |  0.9377 |            1.5479 |              26.9295 |       15.4351 |           150 |     2860.4500 |       750 |      557.3007 |      0.9566 |
|      1 | seasonal_naive |      720 |    17.5880 | 6620.8583 | 7726.3990 | 1.0000 |  1.0000 |           -6.4025 |              55.9722 |       30.9205 |            30 |     6720.2333 |       150 |      275.5000 |      1.0000 |
|      2 | seasonal_naive |      744 |    14.7499 | 5546.7554 | 6462.7876 | 1.0000 |  1.0000 |            4.3771 |              42.8763 |       35.1360 |            31 |     4589.0645 |       155 |      213.0129 |      1.0000 |
|      3 | seasonal_naive |     1402 |    16.1775 | 5751.4208 | 7013.3290 | 1.0000 |  1.0000 |            7.5830 |              29.8859 |       47.9410 |            58 |     5400.6552 |       290 |      804.7724 |      1.0000 |
|      4 | seasonal_naive |     3483 |    19.1354 | 4778.2205 | 6947.0714 | 1.0000 |  1.0000 |           -2.8338 |              45.7651 |       73.0568 |           145 |     5139.8552 |       725 |      614.4855 |      1.0000 |
|      5 | seasonal_naive |     3720 |    11.9990 | 3473.1847 | 4896.6346 | 1.0000 |  1.0000 |            1.4640 |              40.2688 |       34.8000 |           155 |     3691.6903 |       775 |      747.7200 |      1.0000 |
|      6 | seasonal_naive |     3360 |     9.7098 | 2560.5875 | 3520.5307 | 1.0000 |  1.0000 |           -1.9954 |              48.1250 |       33.8677 |           140 |     2771.3286 |       700 |      739.2371 |      1.0000 |
|      7 | seasonal_naive |     3720 |    10.4865 | 3383.0691 | 4779.4532 | 1.0000 |  1.0000 |           -0.1417 |              41.3441 |       27.5691 |           155 |     3761.4710 |       775 |      762.8916 |      1.0000 |
|      8 | seasonal_naive |     3600 |    12.7992 | 3806.6650 | 5301.6034 | 1.0000 |  1.0000 |           -0.0923 |              46.1111 |       42.1370 |           150 |     4418.7800 |       750 |      740.6707 |      1.0000 |
|      9 | seasonal_naive |     3720 |    16.4886 | 5456.5667 | 7736.2714 | 1.0000 |  1.0000 |            4.7674 |              33.4140 |       44.3679 |           155 |     5143.8581 |       775 |      829.8000 |      1.0000 |
|     10 | seasonal_naive |     3482 |    10.6231 | 4549.1212 | 6465.8819 | 1.0000 |  1.0000 |           -1.5109 |              50.1723 |       24.6320 |           145 |     4742.0069 |       725 |      743.0745 |      1.0000 |
|     11 | seasonal_naive |     3480 |     4.8748 | 1924.4865 | 2709.8981 | 1.0000 |  1.0000 |           -0.5718 |              32.9598 |       12.5770 |           145 |     2470.2000 |       725 |      524.7462 |      1.0000 |
|     12 | seasonal_naive |     3602 |     6.2170 | 2499.6527 | 3761.0797 | 1.0000 |  1.0000 |            1.5022 |              28.4842 |       16.3003 |           150 |     2939.0333 |       750 |      582.6107 |      1.0000 |

## Interpretation and limits

Lower is better for errors; signed bias is positive for overforecast and negative for underforecast. Shortfall frequency counts forecasts more than the configured 3% below actual demand. MASE and RMSSE use the out-of-sample seasonal baseline denominator on identical rows. Mean-month and pooled metrics use different weighting. Peak metrics require complete measured zone-days; ramps never bridge missing hours. CSV breakdowns include sample counts, and sparse temperature bands are explicitly marked insufficient.

The demand availability gap remains an assumption; revised historical values do not recreate the original publication state. Historical analyses have previously explored the cached dataset; this year was reserved from forecast selection, not completely unseen throughout the project. This candidate uses no forecast weather values; temperature is observed analysis context only. No production champion is approved by this report. Demand-dependent serving, monitor recalibration, deployment and live acceptance remain separate requirements.

Diagnostic comparison result: PASS. Reasons: [].
