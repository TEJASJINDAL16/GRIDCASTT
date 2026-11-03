# Development Gate: Failed

The corrected model has mean-fold MASE 1.250 and RMSSE 1.247, against seasonal-naive values of 1.000. On 35,033 common measured rows, hybrid MAPE is 14.114%, against seasonal-naive MAPE 11.789%. These are development measurements.

The numerical convergence defect is fixed: fits at their iteration ceiling are refused. Reserved validation supported widening the ceiling from 1000 to 5000; frozen search parameters are unchanged. The twelve corrected folds stopped at 69 to 2602 iterations, all inside the new ceiling. Detailed fitted ranges and counts are in model/fits.json.

The model is unapproved. The final holdout remains reserved. Initial capped comparisons are retained under *_initial_capped; current feature and training-policy comparisons are in ablation.md when complete.

Gate reasons: ['mean fold mase did not improve/hold', 'mean fold rmsse did not improve/hold']

|   fold |   hybrid |   seasonal_naive |
|-------:|---------:|-----------------:|
|      1 | 0.780828 |                1 |
|      2 | 1.01765  |                1 |
|      3 | 0.992443 |                1 |
|      4 | 1.94691  |                1 |
|      5 | 1.28227  |                1 |
|      6 | 2.3957   |                1 |
|      7 | 1.2398   |                1 |
|      8 | 1.12908  |                1 |
|      9 | 0.992742 |                1 |
|     10 | 0.828972 |                1 |
|     11 | 1.38903  |                1 |
|     12 | 1.00224  |                1 |
