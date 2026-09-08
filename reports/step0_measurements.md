# Step-0 measurements

Generated 2026-09-08 09:33 UTC by `scripts/measure_step0.py`.

PLANNING 12: the specification was written against data nobody had looked at.
This report replaces the section 13 step-0 assumptions with numbers, and says
where a number is still provisional.

## Data

| | |
|---|---|
| Joined rows | 423,672 |
| Span | 2017-01-01 to 2026-09-01 (UTC) |
| Zones | IN-EA, IN-NE, IN-NO, IN-SO, IN-WE |
| Headline tier | `measured+MODE` — measured, plus MODE_BREAKDOWN |

### `trend`'s origin moved

`demand.backfill_start` was `2021-01-01`, a guess. Electricity Maps actually
serves all five zones from 2017-01 (measured 2026-09-08), and the config is now
`2017-01-01`.

**This redefines `trend`.** 5e defines it as days since `demand.backfill_start`
with a fixed origin, so every `trend` value is now about four years larger than
it would have been. The feature is unchanged in meaning — days elapsed — but
any number computed against the old origin is not comparable to one computed
against the new one.

### Rows by estimation tier

Which of these are trainable is an **open decision** (PLANNING 10). Every
measurement below is reported per tier rather than collapsed into one number.

| tier                       |   IN-EA |   IN-NE |   IN-NO |   IN-SO |   IN-WE |
|:---------------------------|--------:|--------:|--------:|--------:|--------:|
| GENERAL_PURPOSE_ZONE_MODEL |   35035 |   35064 |   26280 |   26280 |   26280 |
| MODE_BREAKDOWN             |   26281 |   33680 |   42480 |   42480 |   42480 |
| TIME_SLICER_AVERAGE        |     308 |     289 |     287 |     287 |     287 |
| measured                   |   23091 |   15692 |   15697 |   15697 |   15697 |

## The estimation-method discontinuity test

**This is the gate on the option-B tier decision (PLANNING 13).** The case for
training on `MODE_BREAKDOWN` rows rests on that method naming the fuel-mix
breakdown rather than `powerConsumptionTotal`. Consumption is normally derived
from production plus net imports — which come from the breakdown — so if the
total is reconstructed rather than metered, option B trains on ~45 months of
derived numbers.

The switch has a date and the meter does not change on it, so a step model at
the boundary with temperature and calendar controls isolates the pipeline
change. Significance is calibrated against **placebo boundaries** — the same
model fitted at dates where nothing happened — because a regression standard
error assumes independent residuals and hourly demand is nothing of the sort.

| zone   | switch     |   rows |   level_step_pct |   placebo_p90_pct |   n_placebo |   vol_ratio |   shape_gap |   placebo_shape_p90 | exceeds_placebo   |
|:-------|:-----------|-------:|-----------------:|------------------:|------------:|------------:|------------:|--------------------:|:------------------|
| IN-EA  | 2024-01-01 |   2880 |             2.41 |             20.68 |          22 |        0.16 |       0.112 |               0.11  | True              |
| IN-NE  | 2024-11-05 |   2865 |           -52.65 |             33.47 |          22 |        0.78 |       0.385 |               0.319 | True              |
| IN-NO  | 2024-11-05 |   2880 |            -2.29 |             11.12 |          22 |        0.85 |       0.269 |               0.341 | False             |
| IN-SO  | 2024-11-05 |   2880 |             1.4  |             13.63 |          22 |        1    |       0.223 |               0.205 | True              |
| IN-WE  | 2024-11-05 |   2880 |             4.27 |             10.34 |          22 |        0.65 |       0.265 |               0.129 | True              |

**Zones do not switch on the same date.** IN-EA switches 2024-01-01, the other
four on 2024-11-05. That matters: nothing about Indian electricity demand
changes on two different dates for different regions, so anything that tracks
each zone's own switch date is a property of the pipeline, not of the world.

### Hour-to-hour variability, 90 days either side

| zone   | switch     |   before_mean_abs_dlog |   after_mean_abs_dlog |   ratio |   before_p95_hourly_pct |   after_p95_hourly_pct |
|:-------|:-----------|-----------------------:|----------------------:|--------:|------------------------:|-----------------------:|
| IN-NO  | 2024-11-05 |                0.0738  |               0.0672  |    0.91 |                    25.2 |                   18.3 |
| IN-WE  | 2024-11-05 |                0.04797 |               0.03226 |    0.67 |                    17.9 |                    7.7 |
| IN-SO  | 2024-11-05 |                0.05482 |               0.05608 |    1.02 |                    16.9 |                   13.6 |
| IN-NE  | 2024-11-05 |                0.11049 |               0.08695 |    0.79 |                    34.3 |                   27.6 |
| IN-EA  | 2024-01-01 |                0.04129 |               0.00635 |    0.15 |                    14.8 |                    1.7 |

## The thresholds — `features.cooling_threshold_c` and `heating_threshold_c`

Method, per ruling: RSS-minimising grid search on `log(demand)`, pooled, run
both naively and with zone, hour-of-day and weekday means removed first.

**Corrected from the first attempt.** Fitting one ramp alone is misspecified:
demand is not monotone in temperature, so a lone cooling ramp tries to span the
whole range and the search runs to whatever grid edge it is given. The first
run returned the grid boundary for every tier in both directions. A boundary
solution is not a measurement, and it is now reported as **NOT IDENTIFIED**
rather than as a number. The model fitted is the one the features actually use:

```
y ~ 1 + max(0, T - cooling) + max(0, heating - T),    heating < cooling
```

Config currently holds cooling **24.0 C**, heating **15.0 C**.

| tier           |   rows |   naive_cool_c |   naive_heat_c |   adj_cool_c |   adj_heat_c |   adj_cool_pct_per_c |   adj_heat_pct_per_c | note                                       |
|:---------------|-------:|---------------:|---------------:|-------------:|-------------:|---------------------:|---------------------:|:-------------------------------------------|
| measured       |  85874 |             14 |           13   |         23   |         22.5 |                0.529 |               -2.224 | NOT IDENTIFIED — solution on the grid edge |
| measured+MODE  | 273275 |             14 |           12.5 |         34.5 |         26   |                2.251 |               -1.354 | NOT IDENTIFIED — solution on the grid edge |
| all except TSA | 422214 |             14 |           13   |         31   |         28   |                1.209 |               -1.277 | NOT IDENTIFIED — solution on the grid edge |

### Per-zone — tier `measured+MODE`

| zone   |   rows |   cooling_c |   heating_c |   cooling_pct_per_c |   heating_pct_per_c | note                                       |
|:-------|-------:|------------:|------------:|--------------------:|--------------------:|:-------------------------------------------|
| IN-EA  |  49372 |        25   |        24.5 |              -0.446 |              -0.761 |                                            |
| IN-NE  |  49372 |        30.5 |        25.5 |              -3.36  |              -1.148 |                                            |
| IN-NO  |  58177 |        28.5 |        28   |               0.795 |              -2.005 | NOT IDENTIFIED — solution on the grid edge |
| IN-SO  |  58177 |        29   |        22   |              -2.15  |              -1.351 |                                            |
| IN-WE  |  58177 |        21   |        20.5 |               0.992 |              -3.598 |                                            |

Cooling-threshold spread across zones: **9.50 C**.

### The cold side does not behave like a heating load

The heating coefficient comes out **negative in every tier** — colder means
*less* demand, not more, across the observed range. That is physically
plausible for most of India, where electric heating is rare, and 5e already
says `heating_degrees` is kept as a structural requirement of the architecture
rather than because heating load is large.

It has a consequence worth raising before stage 2: 5c requires a **monotone
increasing** constraint on `heating_degrees` in the LightGBM stage. If the
relationship runs the other way in this data, that constraint would force the
model against the measured direction. Flagging rather than acting on it.

## Band occupancy — `evaluate.temperature_bands_c`

Under the sufficiency rule of PLANNING 13: interior bands at or above
`min_band_rows`, the top band kept separate regardless of count, and any band
below `insufficient_band_rows` reported as insufficient rather than as a number.

| band    |   rows | is_top_band   | verdict                    |
|:--------|-------:|:--------------|:---------------------------|
| < 20    |  46558 | False         | ok                         |
| 20 - 30 | 179417 | False         | ok                         |
| 30 - 40 |  46131 | False         | ok                         |
| 40 - 45 |   1144 | False         | ok                         |
| > 45    |     25 | True          | insufficient rows to judge |

### By zone

| zone   |   < 20 |   20 - 30 |   30 - 40 |   40 - 45 |   > 45 |
|:-------|-------:|----------:|----------:|----------:|-------:|
| IN-EA  |   6402 |     32304 |     10570 |        96 |      0 |
| IN-NE  |  11301 |     32604 |      5467 |         0 |      0 |
| IN-NO  |  16298 |     25710 |     15101 |      1043 |     25 |
| IN-SO  |  11022 |     42487 |      4668 |         0 |      0 |
| IN-WE  |   1535 |     46312 |     10325 |         5 |      0 |

## Suppressed-demand candidates — `quality.suppression_*`

Hours where temperature rose by at least
`1.0 C` on the hour while demand
changed by no more than `0.0%`.
5f principle 2: the source reports power consumed, not power wanted, so a
load-shedding hour records a supply ceiling and a model fitted to it learns
that demand stops rising in a heatwave.

| zone   |   flagged_hours |   median_temp_c |   max_temp_c |   eligible_hours |   flagged_pct |
|:-------|----------------:|----------------:|-------------:|-----------------:|--------------:|
| IN-EA  |            5612 |           28.5  |         41.9 |            49359 |         11.37 |
| IN-NE  |            5013 |           25.2  |         39.1 |            49347 |         10.16 |
| IN-NO  |            4723 |           27.9  |         44.8 |            58165 |          8.12 |
| IN-SO  |            4104 |           26.8  |         38.7 |            58165 |          7.06 |
| IN-WE  |            1830 |           29.25 |         39.8 |            58165 |          3.15 |

## Demand growth — assumed ~5%/year in 5c

Log-linear trend on annual mean demand, near-complete years only.

| zone   |   years |   from |   to |   pct_per_year |
|:-------|--------:|-------:|-----:|---------------:|
| IN-EA  |       5 |   2021 | 2025 |          -1.48 |
| IN-NE  |       5 |   2021 | 2025 |           2.82 |
| IN-NO  |       6 |   2020 | 2025 |           8.63 |
| IN-SO  |       6 |   2020 | 2025 |          11.86 |
| IN-WE  |       6 |   2020 | 2025 |           4.52 |

## Holiday effect — assumed 10-20% in 5e

Holiday hours against matched non-holiday hours, paired on (zone, hour, month,
year) so season, daily shape and growth do not confound it. Weekends are
excluded from both sides: a holiday resembles a Sunday, so comparing the two
would measure nothing.

| zone   |   holiday_hours |   matched_cells |   effect_pct |    p10 |   p90 |
|:-------|----------------:|----------------:|-------------:|-------:|------:|
| IN-EA  |            1912 |            1224 |         0.4  | -11.39 |  9.11 |
| IN-NE  |            1910 |            1222 |        -3.61 | -30.64 | 11.64 |
| IN-NO  |            2200 |            1392 |        -2.03 | -13.35 |  8.37 |
| IN-SO  |            2200 |            1392 |        -1.72 | -12.45 |  8.85 |
| IN-WE  |            2200 |            1392 |        -2.61 | -11.44 |  5.14 |

## Figures

- `figures/elbow.png`
- `figures/elbow_by_zone.png`
- `figures/band_occupancy.png`
- `figures/growth.png`
- `figures/suppression.png`
