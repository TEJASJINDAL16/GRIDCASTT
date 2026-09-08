# Step-0 measurements

Generated 2026-09-08 14:47 UTC by `scripts/measure_step0.py`.

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

## The relationship test — the gate on option B

Variance differing across the switch says the same quantity is recorded with
different **precision**, not that a different quantity is recorded. That is
survivable: extra noise in the target inflates irreducible error without
biasing the conditional mean, and it shows up honestly as worse scores rather
than hiding as a wrong relationship.

It is survivable **only if the noise is roughly independent of the features**.
If reconstruction error is larger at peak hours or at high temperatures, it
distorts the response rather than blurring it. So the question that decides the
tier choice is not whether variance changed, but whether the
temperature-to-demand *slope* changed.

Method: the `sloped_below` specification — the only one of the three that is
identified on a proper grid — fitted separately either side of each zone's own
switch, on 12-month windows so both cover a full annual cycle. The breakpoint
is held **fixed** across the comparison so slope and breakpoint cannot trade
off. Calibrated against placebo boundaries in the pre-switch era.

| zone   | switch     |   breakpoint_c |   slope_before_pct_per_c |   slope_after_pct_per_c |   gap_pct_per_c |   placebo_p90_pct_per_c |   n_placebo | exceeds_placebo   |
|:-------|:-----------|---------------:|-------------------------:|------------------------:|----------------:|------------------------:|------------:|:------------------|
| IN-NO  | 2024-11-05 |           28   |                   -0.384 |                   0.362 |           0.749 |                   2.698 |          71 | False             |
| IN-WE  | 2024-11-05 |           26   |                    0.337 |                   1.59  |           1.249 |                   1.996 |          71 | False             |
| IN-SO  | 2024-11-05 |           21.5 |                   -1.194 |                  -1.576 |           0.388 |                   5.095 |          71 | False             |
| IN-NE  | 2024-11-05 |           25   |                   -3.45  |                   0.014 |           3.588 |                   3.12  |          71 | True              |
| IN-EA  | 2024-01-01 |           24.5 |                   -0.299 |                  -1.125 |           0.835 |                   0.935 |          61 | False             |

### Robustness — does the exceedance survive a different window?

| zone   | 9     | 12    | 15    | 18    |
|:-------|:------|:------|:------|:------|
| IN-EA  | False | False | True  | True  |
| IN-NE  | False | True  | True  | True  |
| IN-NO  | False | False | False | False |
| IN-SO  | False | False | False | False |
| IN-WE  | False | False | False | False |

IN-NE's gap is stable at roughly 3.5 %/C at every window length; what changes
is the placebo band, which tightens as the window grows. IN-EA exceeds only at
the two longest windows. The other three zones never exceed at any length.

**Consequence, per the ruling's one-or-two-zone branch:** `quality.trainable_from`
now excludes pre-switch rows for IN-NE and IN-EA and keeps the rest. The model
pools rows and does not require equal spans.

Worth stating plainly, because it is the opposite of what the variance result
suggested: **IN-EA had the largest variance change and among the most stable
relationships. Noise that blurs is not noise that distorts.** That distinction
was the whole basis for keeping tier 2, and it survived a test that could have
killed it.

## Which shape actually fits

5e asserts demand is U-shaped in temperature. That is a premise stated from
physics rather than measured — the same class of statement as INV-3's second
sentence, which turned out to be false. Three specifications, fitted on the
earlier rows and scored on the later ones (chronological, per INV-2):

```
v_shape       y ~ 1 + max(0, T - cooling) + max(0, heating - T)
flat_below    y ~ 1 + max(0, T - cooling)
sloped_below  y ~ 1 + T + max(0, T - cooling)
```

| tier          | spec         |   cooling_c |   heating_c |   params |   holdout_rmse_log | identified   | note         |   vs_best_pct |
|:--------------|:-------------|------------:|------------:|---------:|-------------------:|:-------------|:-------------|--------------:|
| measured      | v_shape      |        32   |          23 |        3 |            0.22553 | False        | on grid edge |          0    |
| measured      | flat_below   |        15   |         nan |        2 |            0.22752 | False        | on grid edge |          0.88 |
| measured      | sloped_below |        21.5 |         nan |        3 |            0.22563 | True         |              |          0.04 |
| measured+MODE | v_shape      |        32   |          25 |        3 |            0.31935 | False        | on grid edge |          0    |
| measured+MODE | flat_below   |        15   |         nan |        2 |            0.32127 | False        | on grid edge |          0.6  |
| measured+MODE | sloped_below |        25   |         nan |        3 |            0.3201  | True         |              |          0.23 |

**The V shape is not identified even on the widened grid.** In every tier it
runs to a grid edge, and it buys 0.04% on holdout RMSE for doing so. The single
specification that is identified — an interior breakpoint — is `sloped_below`:
demand rises with temperature across the whole observed range, more steeply
above the breakpoint.

That is a finding, not a failure. The negative heating coefficient reported
earlier was the V-shape's heating ramp acting as a general downward-sloping
term in temperature rather than as a heating load, which is why it wanted the
breakpoint at the top of the grid. `sloped_below` says the same thing
explicitly, and identifiably.

**Raised, not resolved:** 5c requires a monotone **increasing** constraint on
`heating_degrees`. There is no cold-side heating load in this data to
constrain, so the constraint would be applied to a term that is absorbing the
shallower lower segment of a monotone relationship.

## What was decided about `heating_degrees`

Added to the identified `sloped_below` specification and scored on the same
holdout, it improves RMSE by 0.263% on the measured tier — but the improvement
is a degenerate fit, not a heating load. Decomposed into net slopes:

```
T < 18.5     +0.86 %/C      8,340 rows
18.5 - 20.0  +6.35 %/C      3,341 rows      <- the whole gain lives here
T > 20.0     +0.21 %/C     48,430 rows      <- the cooling slope, flattened
```

Demand rises with temperature in all three segments. The gain is bought by a
+6.35 %/C sliver 1.5 C wide on 5.6% of rows, paid for by flattening the cooling
segment to +0.21 %/C — a fit that has stopped modelling the thing this project
exists to model. The three raw coefficients (+0.0615, -0.0594, +0.0530) are
large and offsetting; over a 1.5 C window the terms are near-collinear.

`heating_degrees` is **deleted from the feature set entirely**, linear stage and
tree. Its 5e justification was the U-shape, which is gone; and 5e's own three
reasons for keeping `cooling_degrees` despite being a deterministic transform of
a present column — the Ridge baseline needs it, it carries the constraint, the
extrapolation is built on it — none survive for `heating_degrees` now that it is
out of the linear stage, unconstrained, and not carrying extrapolation. The one
real cold response measured, IN-NE, the tree reaches through temperature x zone.

### Is IN-NE's cold response temperature, or December?

| zone   |   rows |   hour_wday_only_pct_per_c |   plus_month_fe_pct_per_c |   within_month_pct_per_c |
|:-------|-------:|---------------------------:|--------------------------:|-------------------------:|
| IN-EA  |   1854 |                       0.03 |                     -0.12 |                    -0.35 |
| IN-NE  |   2905 |                      -2.26 |                     -1.62 |                    -0.71 |
| IN-NO  |  13998 |                       0.41 |                      0.48 |                     0.38 |
| IN-SO  |   4739 |                       0.52 |                      0.57 |                     0.61 |
| IN-WE  |    536 |                       5.42 |                      4.75 |                     2.23 |

Two thirds of IN-NE's apparent cold-side response is position in the year, not
cold: -2.26 %/C controlling for hour and weekday, -1.62 %/C with month fixed
effects, **-0.71 %/C on within-month variation alone**. A real thermal component
survives, and it is a third of what the naive estimate said.

This is direct evidence of a feature-set gap. Nothing in the core set represents
position in the year, so the only feature able to absorb the seasonal signal was
temperature — and it did, as a distorted coefficient. Day-of-year, cyclically
encoded, joins the stage 2 ablation candidate list. It is not added to the core
set; it earns its place or it does not.

### The monotone constraint

LightGBM monotone constraints are per-feature and **global**, never
zone-conditional. Constraining raw `temperature` increasing — which the new
linear stage would otherwise invite — would make IN-NE's measured cold-side rise
structurally unrepresentable, forbidding the model from learning an effect
measured on 2,905 rows.

`features.monotone_increasing` is therefore `[cooling_degrees]` only.
`cooling_degrees` is zero below the breakpoint, so constraining it constrains the
hot tail — where the constraint is wanted — and leaves the cold side free.

## The temperature breakpoint — `features.temp_breakpoint_c`

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

Config now holds **21.5 C**, measured. `heating_threshold_c` is
deleted: there is no U-shape, so there is no cold inflection to hold a
threshold, and `heating_degrees` is removed from the feature set entirely.

| tier           |   rows |   naive_cool_c |   naive_heat_c |   adj_cool_c |   adj_heat_c |   adj_cool_pct_per_c |   adj_heat_pct_per_c | note                                       |
|:---------------|-------:|---------------:|---------------:|-------------:|-------------:|---------------------:|---------------------:|:-------------------------------------------|
| measured       |  85874 |             15 |           13   |         22.5 |         22.5 |                0.516 |               -2.2   | NOT IDENTIFIED — solution on the grid edge |
| measured+MODE  | 273275 |             15 |           12.5 |         32   |         25   |                1.267 |               -1.462 | NOT IDENTIFIED — solution on the grid edge |
| all except TSA | 422214 |             15 |           13   |         25   |         25   |                0.843 |               -1.309 | NOT IDENTIFIED — solution on the grid edge |

### Per-zone — tier `measured+MODE`

| zone   |   rows |   cooling_c |   heating_c |   cooling_pct_per_c |   heating_pct_per_c | note                                       |
|:-------|-------:|------------:|------------:|--------------------:|--------------------:|:-------------------------------------------|
| IN-EA  |  49372 |          25 |        25   |              -0.463 |              -0.724 | NOT IDENTIFIED — solution on the grid edge |
| IN-NE  |  49372 |          31 |        25   |              -3.907 |              -1.182 | NOT IDENTIFIED — solution on the grid edge |
| IN-NO  |  58177 |          25 |        25   |               1.239 |              -1.964 | NOT IDENTIFIED — solution on the grid edge |
| IN-SO  |  58177 |          29 |        22   |              -2.15  |              -1.351 |                                            |
| IN-WE  |  58177 |          21 |        20.5 |               0.992 |              -3.598 |                                            |

Cooling-threshold spread across zones: **10.00 C**.

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

### The band the project most wants to be good at is the one it knows least

The `> 45 C` band holds **25 rows, every one of them IN-NO**. The `40 - 45 C`
band holds 1,102, of which 1,043 are IN-NO. The hot tail is, in this dataset,
Delhi.

Two consequences, both stated rather than worked around.

**The top-band veto reads the top REPORTABLE band.** 5g lists "worse in the top
temperature band" as a veto on promotion. Evaluated on 25 rows that is not a
quality check, it is a coin toss that would reject challengers at random. The
veto now reads the highest band holding at least `insufficient_band_rows` rows —
in practice `40 - 45 C`. The `> 45 C` band is still computed, still reported,
still flagged insufficient, and never gates a promotion. 13's rule already says
a band that thin is reported as "insufficient rows to judge" rather than as a
number; a figure too weak to quote is too weak to veto on.

**Zone-by-band stratification has empty cells by construction.** Three zones have
no rows at all above 40 C. 5g's stratified table must render that as absent
rather than as zero error.

*This is the honest loss, and it belongs in the model card rather than buried
here: nine years of history and one weather point per zone buys 25 hours above
45 C. 5f's whole argument is that the model is least reliable exactly where it
matters most — this is the measurement of how little evidence there is to be
reliable on. A second weather point per zone, already a Phase 2 candidate in 5e,
is the direct remedy.*

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
