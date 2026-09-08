# gridcast — Project Context

**Audience:** any agent or person working on this repository.
Read this file completely before writing code.

---

## 0. How to use this document

- **RULE** lines are binding. Do not violate them, do not "improve" on them.
- *Rationale* notes explain why a rule exists. They are context, not licence
  to reinterpret the rule.
- **§10 Open decisions** lists what has NOT been decided. If your task depends
  on something in §10, **stop and ask**. Do not invent a decision to keep
  moving. An invented decision that looks reasonable is worse than a blocked
  task, because nobody notices it was invented.
- **§9 Invariants** are the rules that silently destroy the project's validity
  if broken. Violating one does not produce an error — it produces a good
  number that is a lie.

Nothing enters the committed sections of this document except by explicit
instruction from the repository owner.

---

## 1. What this project is

**gridcast** is a day-ahead electricity demand forecasting service for the
Indian grid. It predicts demand hour by hour for the next 24 hours from
weather, calendar and time signals, and keeps itself correct after deployment
— monitoring for drift, retraining when the data says to, and refusing an
update that would make it worse.

The forecast is the product. The system that keeps the forecast honest is the
point.

---

## 2. Problem statement

Electricity cannot be stored at grid scale. Whatever a region consumes at
15:00 must be generated at 15:00, so grid operators schedule generation a day
ahead against a forecast.

Forecast error costs money in both directions:

- **Under-forecast** — insufficient generation scheduled. Power must be bought
  on the spot market at spike prices, or load is shed.
- **Over-forecast** — plants paid to run and burn fuel for power nobody used.

In India the Deviation Settlement Mechanism additionally penalises a state
financially for drawing more or less than scheduled. Forecast error appears
as a rupee figure on a settlement statement daily.

A second problem sits underneath. Demand **drifts**: air-conditioning
penetration rises, rooftop solar reshapes the daytime curve, EV charging adds
night-time load, economies grow. A forecaster trained once and left alone
decays silently — it never crashes, never errors, it just stops being right.

---

## 3. What this project must demonstrate

1. **Understanding of data** — real, public, messy data. Never generated.
2. **Designing a model from the data** — target, validation, baseline and
   metric chosen because the problem demands them, each justifiable.
3. **Feature engineering as domain understanding** — features that encode how
   electricity is actually used.
4. **MLOps** — versioned data, tracked experiments, a model registry,
   triggered retraining, drift monitoring, and a promotion gate.

---

## 4. Standards

**RULE** Production-grade practices, implemented at the smallest scale that
genuinely does the job. Where a team would use managed infrastructure, use the
file-backed equivalent.

**RULE** Do not give a narrow sub-problem its own pipeline. If a small change
achieves the same outcome as a large one, take the small change. Where
complexity is genuinely required, do not avoid it.

**RULE** Before adding any component, answer: *what problem does this solve in
this project?* If the problem cannot be named, do not add it.

**RULE** Every number claimed anywhere — README, dashboard, commit message —
must be readable out of a committed file.

**RULE** All tunable values live in `config/config.yaml`. No magic numbers in
code.

---

## 5. Build strategy

Phase 1, then 1b, then 2. Each gated on the one before it. Do not begin a
phase before the previous phase's exit criteria are met.

### Phase 1 — Complete loop, all zones

Build the entire machine: ingest, features, model, backtest, monitoring,
promotion gate, deployed dashboard. All five zones from the start, with region
as a native categorical feature (see 5c).

*Purpose:* prove the machinery works, and produce the benchmark that any later
architecture has to beat.

**Exit criteria — all must hold:**
- Beats the seasonal-naive baseline on a 12-month walk-forward backtest
- Per-zone error reported by temperature band, hour, zone and day type
- Daily evaluation job runs unattended
- Drift monitoring live
- Promotion gate demonstrably blocks a bad promotion
- Dashboard deployed and self-updating

*The pooling question — does one model across five zones beat five separate
models — is answered inside this phase, because a per-zone model is one of the
shipped baselines and the backtest is running regardless. It does not need a
phase of its own.*

### Phase 1b — Quantile forecasts

Gated on Phase 1 exit. Detailed in 5b.

### Phase 2 — Architecture experiments

All the open architectural questions, each measured against the Phase 1 model
on identical splits. One phase, not several, because they are all the same
shape of question: *can anything beat what Phase 1 shipped?*

- **A demand model plus a regional correction layer** — a base model carrying
  the shared physics, plus a thin per-region layer for local factors. This is
  the preferred direction and is to be tested, not assumed.
- **TFT and a time-series foundation model** (Chronos or similar) benchmarked
  on the same walk-forward folds
- **Leave-one-zone-out**, giving cold-start evidence for a region absent from
  training

**Exit criteria:** each experiment run on identical splits, with the verdict
recorded **either way**. "The simpler model won, here is the evidence" is a
valid and acceptable result.

### Why this order

**Debuggability.** Building base and correction together leaves no way to
isolate which is wrong. Phase 1 provides a trusted reference.

**Risk.** Phase 1 is a complete, defensible project on its own. If work stops
after it, the result is a deployed, self-updating forecaster with real measured
numbers. Everything after is a measured improvement on a working system.

## 5a. Data sources

Three sources. Only one needs an API key.

| Source | Provides | Key needed |
|---|---|---|
| **Electricity Maps** | demand — the target variable | yes (academic licence, in `.env`) |
| **Open-Meteo** | weather — most of the features | no |
| **`holidays`** (Python package) | Indian holiday calendar, state-aware | no |

**RULE** Demand comes from Electricity Maps, field `powerConsumptionTotal`,
for zones IN-NO, IN-WE, IN-SO, IN-EA and IN-NE. See section 11 for the
verified endpoint and response shape.

**RULE** Weather comes from Open-Meteo — the archive API for observed history,
the forecast API for prediction time. These are separate functions and must
stay separate (INV-1).

*Rationale:* Electricity Maps supplies demand and generation mix only. It has
no weather data. Weather is the dominant driver of demand, so Open-Meteo is
not an optional extra — without it the model has calendar features and almost
nothing else.

**RULE** Holidays come from the `holidays` package with Indian state
subdivisions, extended with a hand-maintained list of major festivals whose
dates move on the lunar calendar.

**RULE** Cache all three to disk under `data/raw/` early, and treat the cache
as the source of truth for training, backtesting and reporting.

*Rationale:* the Electricity Maps licence expires 2027-03-04. Once history is
cached, training data, backtests and every figure survive the key lapsing.
Only the live daily update depends on the API remaining available.

## 5b. Target definition

**RULE** Target: hourly electricity demand in megawatts, absolute level.

*The model is **trained** on `log(demand)` and predictions are converted back
to megawatts (see 5c). That is a training transform, not a change of target —
the quantity predicted, reported and scored is always MW.*

**RULE** Horizon: 24 values covering the next IST calendar day — the UTC
hourly marks 19:00 (D-1) through 18:00 (D), which map to IST 00:30 - 23:30.

*Rationale:* India is UTC+5:30 and the source publishes on UTC hour marks, so
no UTC hour lands on an IST hour boundary. These 24 marks cover the IST day
with no interpolation.

**RULE** Never interpolate the target onto IST hour boundaries. Smoothing a
target variable is not a formatting choice.

**RULE** Issue time: 10:00 IST daily. Lead time is therefore 14-38 hours,
varying by target hour.

**RULE** Method: direct multi-step. Every target hour is predicted
independently from features known at issue time. Never recursive.

*Rationale:* the weather forecast covers all 24 target hours at issue time, so
no predicted value is ever needed as an input. Recursive prediction would
compound error across 24 steps for no benefit.

**RULE** Never define the target as a delta from a lagged actual.

*Rationale:* delta-from-seasonal-naive requires last week's same-hour actual
at issue time, but that anchor may still be estimated — the settlement lag is
unmeasured (13) and `purge_gap_days` is deliberately conservative. It would bake a dependency on unsettled data into the target
definition itself. Note this does not affect the Phase 2 regional correction
layer, whose residual is taken from the base model's prediction, not from a
lagged actual.

**RULE** One daily job at issue time performs, **in this order and no other**.
This sequence is canonical; sections 6 and 14 refer to it and must not restate
it differently.

```
1  archive the weather forecast vintage, observed weather, demand revisions (5d)
2  score forecasts whose rows have reached the settlement frontier (5g)
3  update rolling error and signed bias (6)
4  evaluate trigger conditions, apply routing and cooldown (6)
5  retrain and run the promotion gate, if and only if step 4 authorised it (6)
6  build features and issue the 24-hour forecast (5b)
7  publish the dashboard (15)
```

*Rationale:* publication is last because the dashboard must show today's
forecast and today's trigger outcome. Retraining precedes issuing so that a
promoted challenger is the model that issues today.

### Phase 1b — quantile forecasts

Gated on Phase 1 exit criteria. Predict the 10th, 50th and 90th percentiles
instead of a point, so reserve margin can be sized from the forecast. Scored
with pinball loss plus a coverage check. Deferred rather than dropped: cheap
in LightGBM, but it adds training and scoring surface area before the core
loop is proven.

## 5c. Zones, model and data splits

### Zones

**RULE** Phase 1 trains on all five Indian zones together. Region is passed as
a native categorical feature (LightGBM `categorical_feature`), not one-hot
encoded.

**RULE** Train on `log(demand)`, not raw megawatts.

*Rationale:* every zone contributes the same number of rows — same date range,
same hourly granularity — so there is no count imbalance and nothing to fix by
subsampling. The imbalance is in magnitude: IN-NO runs tens of gigawatts, IN-NE
a fraction of that. A loss summed in megawatts treats a 500 MW miss identically
in both, though it is 1% in one zone and 25% in the other, so the optimiser
trades away small-zone accuracy for negligible large-zone gains. Log transform
makes variation comparable across zones — a 10% swing is +/-0.095 in log space
regardless of size — and as a side effect makes errors relative, aligning the
training objective with MAPE.

**RULE** Do not use MAPE as the training objective, despite it being the
evaluation metric.

*Rationale:* MAPE penalises over-prediction more than under-prediction for the
same absolute error, so it biases forecasts downward. Under-forecasting is the
expensive direction for a grid operator — shortfall, spot purchases, load
shedding. Log transform with L2 is symmetric in relative terms and carries no
such bias.

**RULE** Correct the retransformation bias when converting predictions back
from log space. `exp(mean(log x))` understates `mean(x)`.

**RULE** Do not apply per-zone sample weighting by default. Measure the
per-zone loss contribution after the log transform, and add weights only if a
zone still dominates.

*Rationale:* the transform is expected to be sufficient on its own. Applying
both is unmeasured redundancy. A zone with unusually high volatility is the
one case that might still need weighting — decide that from a number, not in
advance.

**RULE** Do not force tree splits on region.

*Rationale:* forcing a region split at the root means every branch below it
sees only one region's rows, so nothing is learned across regions. That is
per-zone models implemented in a more complicated way, and it discards the
reason for pooling. If region importance comes out low after the log
transform, that is a finding — the zones have similar demand *shape* once
scale is removed — not a defect to engineer around.

**RULE** Prefer features that encode mechanism over features that encode
identity.

*Rationale:* temperature to demand is physics; it holds in an unseen region,
in a hotter summer, in three years' time. "IN-NO runs around 55 GW" is
bookkeeping about this dataset. A model leaning on mechanism survives drift,
extrapolation and cold start; one leaning on identity does not. Identity
features are the small correction on top, never the thing carrying the
prediction.

**Development practice (not a rule):** build against a single zone for
iteration speed. The zone list is configuration, not code.

### Model architecture

Phase 1 is a **two-stage hybrid**. This is the architecture everywhere, in all
conditions — not a special case bolted on for heatwaves.

```
prediction = Ridge( temperature, cooling_degrees, trend )
           + LightGBM( all features, fitted on the residual )
           then exp() back to megawatts
```

**Stage 1 — Ridge.** Carries the relationships that must extrapolate.
**Stage 2 — LightGBM.** Carries everything else, fitted on what Stage 1 left
over: hour shape, weekday effects, holidays, zone differences, interactions,
and any curvature the linear term missed.

**RULE** A feature belongs in the linear stage only if it satisfies **both**:

1. it has a roughly linear relationship with log demand, and
2. **it can take values outside the training range**

| Feature | Can leave training range? | Linear stage |
|---|---|---|
| `temperature` | yes — record heat, record cold | **yes** |
| `cooling_degrees` | yes — record heat | **yes** |
| `trend` | **yes — always, by definition** | **yes** |
| `hour_of_day` | no, always 0-23 | no |
| `day_of_week` | no, always 0-6 | no |
| `is_holiday` | no, always 0 or 1 | no |
| `zone` | no, fixed set | no |
| humidity, cloud, wind | no, physically bounded | no |

A feature that cannot leave its training range gains nothing from the linear
stage. LightGBM models it better, because it can bend.

#### Why `trend` is in the linear stage

A tree can only split on values it has seen. Trained to `trend = 1460` and
asked to predict `trend = 1500`, it has no split above 1460, falls into its
top bin, and predicts the final training period's level **permanently**.

Unlike a heatwave this is not an edge case. **Every forecast is outside the
training range in the time dimension, by definition**, and the gap widens for
as long as the model runs. The tree pins to the level of its final training
period, so with demand growing around 5% a year — itself an unmeasured
assumption (13) — a forecast a year past the training boundary lands about 5%
low, and the shortfall compounds for as long as the model is not retrained. On
every hour, always in the same direction.

A line keeps rising. That is the entire reason the linear stage exists.

#### What the linear stage does across the range

```
temperature                                  everywhere
cooling_degrees = max(0, T - 21.5)           zero for all T <= 21.5
```

Together these reproduce the identified two-slope shape exactly: a shallow
slope below the breakpoint, carried by `temperature`, and a steeper one above
it, carried by `temperature + cooling_degrees`.

*This section previously claimed the linear stage was dormant between 15 C and
24 C, where `cooling_degrees` and `heating_degrees` were both zero and only the
intercept remained. That rested on demand being U-shaped in temperature, which
measurement has disproved — demand rises with temperature across the whole
observed range (13). There is no dormant band, and a linear stage that was
silent through the commonest 60% of hours would have been carrying no
extrapolable signal there at all.*

**RULE** The linear stage extrapolates **freely above** the training range and
is **clamped at the training minimum below** it. Record the training minimum
per fold. Governed by `features.clamp_linear_below`.

*Rationale:* with a positive slope on raw temperature, an unprecedented cold
snap extrapolates downward — the under-forecast direction that 5f Principle 4
exists to avoid. The asymmetry is principled, not a hedge. Above the range
there is a physical prior: hotter means more cooling load, and it is the
direction both climate and AC penetration are moving. Below it there is no
prior, no pooled heating load in the data, and the error leans the dangerous
way. Cold beyond anything seen flattens rather than continuing down.

#### Why the log scale makes one coefficient serve five zones

Because the target is `log(demand)`, a coefficient of 0.015 means **1.5% per
cooling degree**, not a fixed megawatt figure:

```
IN-NO at 55,000 MW  ->  1.5%  =  825 MW per degree
IN-NE at  2,000 MW  ->  1.5%  =   30 MW per degree
```

A percentage is scale-free where megawatts are not, so a single fitted
coefficient is correct for every zone. The log transform chosen for the zone
imbalance problem pays off a second time here.

**RULE** Apply a monotone increasing constraint on **`cooling_degrees` only**
in the LightGBM stage. Raw `temperature` is in the tree **unconstrained**.

*More heat cannot mean less cooling load. With few examples above 45 C an
unconstrained model fits noise and can produce a physically impossible dip.*

*Why not constrain raw temperature instead, now that it carries the linear
slope: LightGBM monotone constraints are **per-feature and global**, never
zone-conditional. Constraining temperature would make IN-NE's measured
cold-side rise — demand rising as it cools, -0.71 %/C within-month on 2,905
rows (13) — structurally unrepresentable, forbidding the model from learning a
real effect. The constraint exists to stop something absurd in the **hot tail**;
applying it across the whole range to achieve that costs a real effect at the
other end.*

*`cooling_degrees` is zero below the breakpoint, so constraining it constrains
the hot side and nothing else. The cold side stays free. This is also what
gives `cooling_degrees` a job in the tree despite being a deterministic
transform of a column already present: it is the feature that carries the
constraint.*

**RULE** Correct the retransformation bias when inverting the log, using
**Duan's smearing estimator**: multiply `exp(prediction)` by
`mean(exp(residual))` computed on that fold's training residuals, per zone.
Applied once, to the summed two-stage prediction, never to a stage separately.
`exp(mean(log x))` understates `mean(x)`.

#### Two different Ridge models — do not confuse them

| | Features | Purpose |
|---|---|---|
| **Hybrid Stage 1** | 3: cooling, heating, trend | carry what must extrapolate |
| **Ridge baseline** | all engineered features | answer "could a simple model have done this?" |

Same algorithm, different feature sets, different jobs.

*Note on the hybrid Stage 1: with three uncorrelated features on a matrix of
order 10^5 rows the L2 penalty barely binds, so it is close to plain least squares. Ridge
is used because the linear feature list is configurable and under test — if it
grows, those features will be correlated and the penalty starts doing real
work.*

**RULE** Ship these baselines in every backtest:
seasonal naive · hour x weekday historical mean · Ridge on all engineered
features · a per-zone model.

*The per-zone baseline settles whether pooling helps, inside Phase 1, at no
extra cost — the backtest is running anyway.*

**RULE** The linear-stage feature list is configurable, and whether adding
further features to it helps is an experiment to run, not a decision to
assume.

### Hyperparameter tuning

**RULE** Tune on a reserved early window. Freeze the chosen values into
`config/config.yaml` before the walk-forward backtest runs.

```
|<-- TUNING WINDOW -->|<---- WALK-FORWARD FOLDS ---->|<-- HOLDOUT -->|
   search here             hyperparameters FROZEN         untouched
```

**RULE** Never select hyperparameters by looking at walk-forward test fold
performance.

*Rationale:* this is where leakage hides second, and it is subtler than
feature leakage. The model never saw the test rows, so it feels clean — but
the **experimenter** saw them and chose based on what they showed. The test
folds then stop being an honest estimate. Nested cross-validation is the
rigorous alternative and costs 12x the compute for little gain here; tuning
once on a reserved window and freezing is sufficient, provided it is stated.

**RULE** Search with Optuna, of the order of 100 trials. Optuna keeps its own
trial storage; MLflow receives one summary run for the study (14) — parameters, score, duration.

*Optuna learns which regions of the space are promising and samples there,
converging faster than random search, which in turn beats grid search per unit
of compute. All three are affordable because training takes seconds.*

**RULE** Tune the project parameters, not only the model ones. These are
likely to matter more:

| Parameter | What it controls |
|---|---|
| `recency_half_life_days` | how fast old data loses influence |
| `temp_breakpoint_c` | where the slope actually steepens — measured at 21.5 (13), retunable |
| number of piecewise cooling breakpoints | Phase 2 only. Phase 1 uses the single ramp max(0, T - temp_breakpoint_c); a multi-breakpoint form would add cooling_degrees_1..n and is not specified here |
| Ridge `alpha` | regularisation of the linear stage |

LightGBM side: `num_leaves`, `learning_rate`, `min_data_in_leaf`,
`feature_fraction`, `bagging_fraction`, `lambda_l1`, `lambda_l2`.
`n_estimators` is not tuned — early stopping selects it per fold.

**RULE** Retraining is not retuning. A drift trigger retrains on fresh data
with **frozen** hyperparameters.

*Rationale:* an automated search with nobody in the loop can produce a worse
model, and it would make every retrain slow and non-deterministic. Retuning is
a deliberate act, performed when features change, the architecture changes, or
the data has shifted enough to justify it.

### Data splits

All splits are chronological. Never split randomly, never split by zone.
All five zones appear in both sides of every split; the boundary is time.

*The single sanctioned exception is the Phase 2 leave-one-zone-out experiment
(section 5), which is a diagnostic and never trains a production model.*

Defined relative to available history, not as fixed dates:

```
|<--------------------- DEVELOPMENT ---------------------->|<-- HOLDOUT -->|
|                                                          |               |
| tuning window | ---- expanding train ---- | 12 monthly   |   12 months   |
|  (earliest    |                           | test folds   |   untouched   |
|   12 months)  |                           |              |               |
       |
       +--> hyperparameter search happens HERE ONLY.
            Frozen into config before any fold runs.
            Fold results are never used to select them.
```

The tuning window is not excluded from later training — the walk-forward
trains on everything before each fold boundary, tuning window included. The
constraint is only that the **search** never sees a test fold.

**RULE** Final holdout: the most recent 12 months. Not looked at, not scored
against, not tuned on, until the project is otherwise finished.

*Rationale:* a backtest tuned against repeatedly becomes a training set. The
holdout is the only number that has not been contaminated by iteration. Twelve
months rather than six so it covers a full seasonal cycle and the final figure
is not a summer or winter artefact.

**RULE** Walk-forward: expanding window, monthly steps, twelve folds. Each
fold trains on all data before the fold boundary and tests on the following
month.

*Expanding rather than sliding, consistent with the training-window rule in
section 7.*

**RULE** The walk-forward folds straddle the `MODE_BREAKDOWN`-to-measured
transition (11). This is a known change in the **data-generating process inside
the test period**, and it must be stated as a caveat wherever fold results are
reported — the backtest report, the model card and the dashboard.

*Rationale:* the training span begins in the `MODE_BREAKDOWN` era and the most
recent folds and the whole holdout are measured rows, so a fold-to-fold change
in error can be a change in the data rather than a change in the model. Not
stating it would leave the single most likely alternative explanation for any
trend in the fold results unmentioned.

**RULE** Within a test fold, train once at the fold boundary and issue daily
forecasts across the month without retraining.

*Rationale:* this is what the deployed system does — retraining is triggered
and rare. Retraining daily inside a fold would measure a system nobody is
going to run.

**RULE** Purge gap: training data within each fold ends **10 days before** the
fold's test period begins.

*Rationale:* rows settle from estimated to measured after some lag, and INV-3
forbids training on estimated rows, so the newest usable training row at any
real issue time is `purge_gap_days` old. **The lag itself is unmeasured** — one
observed row took two days (5d, 13) — and 10 is a deliberately conservative
placeholder, not a finding. Never quote it as a measured settlement lag. A backtest without this gap
trains on data that would not have existed at decision time — the error is
invisible and it inflates every result. This is the single easiest way to
produce a backtest number that cannot be reproduced in production.

**RULE** Early stopping: hold out the last `splits.early_stopping_weeks` of each
fold's training window as a validation set to select the iteration count, then
refit on the full training window using that count **scaled by the row ratio**
`n_full / n_train_minus_validation`, rounded up.

*The validation slice sits at the end of the training window, before the purge
gap, and recency weights apply inside it exactly as in training.*

*The validation slice is the most recent part of training, never a random
sample.*

**RULE** The first fold boundary sits no earlier than
`splits.min_initial_train_months` after the end of the tuning window. Folds that
would train on less than that are not run.

**RULE** Filter to measured rows before splitting, not after.

**RULE** The seasonal-naive baseline is defined as: *the most recent measured
value for the same hour and same weekday, at least `purge_gap_days` before the
issue time.*

*Rationale:* "same hour last week" is ambiguous under a settlement lag — last
week's value may still be estimated at issue time, and a baseline built on an
estimated row is not under the same information constraint as the model.
Reaching back to the most recent **measured** matching hour puts the baseline
under exactly the same information constraint as the model. A baseline allowed
to see data the model cannot is not a fair comparison, and it is precisely the
sort of detail that quietly makes a model look better than it is.

## 5d. Vintage archiving

Three things are archived daily. All three are cheap; the first is
unrecoverable if not started immediately.

### Weather forecast vintages

**RULE** Every daily run archives the full weather forecast it fetched,
recorded against the time it was issued. Store the whole forecast horizon the
API returns, not only the 24 hours used, since the extra hours cost nothing and
give a wider range of lead times.

One row per (issued_at, location, target_datetime), with the weather variables
and derived `lead_time_hours`.
Written to `data/raw/forecast_vintages/`.

**RULE** Rows in the vintage archive with `lead_time_hours <= 0` are **analysis
material, not forecasts**. They are archived for completeness and must never be
used as features, nor scored as forecasts. Every consumer of the archive filters
on lead time before use.

*Rationale:* the forecast endpoint returns the current day from 00:00, so the
earliest rows of every vintage describe hours that had **already elapsed** when
the forecast was issued — about 2% of a 16-day horizon. They are the provider's
account of what just happened, not a prediction of it. Using one as a feature is
leakage under INV-1 wearing the right column name: the column says
`temperature_2m` and the row says the hour is in the archive, and nothing about
the shape of the data reveals that the value was not knowable at issue time.
`lead_time_hours` exists so the filter is trivial and so including a row is
always an explicit decision rather than an accidental one.

*Rationale:* Open-Meteo serves observed history and the current forecast, but
not what the forecast said on a past date. So training uses observed weather
while production is served a forecast — the model trains on perfect
temperature and is deployed on approximate temperature, and learns to trust it
more than it should. This gap cannot be closed retroactively. Every day
without archiving is a vintage that can never be recovered.

The archive unlocks three stages, in order:

| Stage | What becomes possible |
|---|---|
| now | nothing yet — assume `forecast_error_sigma` in config, marked as an assumption |
| ~6 weeks of pairs | measure the real error and replace the assumption with a number |
| ~6 months of vintages | stop simulating: train on the forecasts that actually existed at each past issue time |

**RULE** The noise-injection approach is a bridge, not a destination. Do not
build a season-aware, lead-time-varying noise model. Once vintages are
sufficient, training on real vintages removes the train/serve gap outright,
carrying the true lead-time dependence, seasonality and autocorrelation for
free.

*If the vintages accumulate more slowly than expected, modelling sigma as a
curve in lead time is the sanctioned intermediate step — error grows with lead
time, so a constant understates it at the far end of the horizon. Do that only
after the constant has been shown insufficient.*

### Observed weather

**RULE** The daily run also fetches observed weather for recent past days as
the archive API releases them, extending the observed history and completing
forecast/actual pairs.

### Demand revisions

**RULE** The daily run re-fetches recent demand and logs any change to
`is_estimated`, `updated_at` or the value itself, to
`data/raw/demand_revisions/`.

*Rationale:* the 10-day purge gap in section 5c is currently an assumption
derived from a single observation — one row created 24 Aug and updated 26 Aug.
Logging revisions turns that assumption into a measurement. If rows actually
settle in four days the gap is needlessly conservative; if they take fourteen,
every backtest so far has been optimistic. Either way it should be a number,
not a guess.

## 5e. Feature set

### Phase 1 — the core set

Chosen by one test: **remove it, and nothing else in the set can compensate.**

The **Stage** column says which half of the hybrid consumes each feature —
`linear` for the Ridge stage, `tree` for LightGBM. See 5c for why.

| Feature | Stage | Source | Why it cannot be dropped |
|---|---|---|---|
| `hour_of_day` | tree | timestamp (IST) | without it there is no daily shape at all |
| `day_of_week` | tree | timestamp (IST) | weekday vs Sunday is a large systematic gap; weather cannot infer it |
| `is_holiday` | tree | `holidays` + manual list | shifts demand 10-20% and is invisible in every other feature |
| `temperature` | **linear** + tree | Open-Meteo | the dominant driver; carries the slope below the breakpoint and can leave the training range in both directions |
| `cooling_degrees` | **linear** + tree | `max(0, T - temp_breakpoint_c)` | see below — kept for two reasons, neither of which is helping the tree |
| `trend` | **linear** + tree | days since `demand.backfill_start`, fixed origin | year-on-year growth; without it the tree pins to the final training period's level and runs low, by roughly the growth rate per year of staleness (5c) |

**RULE** Once training has begun, `demand.backfill_start` **never moves**.
Changing it invalidates every derived threshold and the champion itself, and
both must be rebuilt from scratch.

*Rationale:* `trend` is days since that date, so moving the origin shifts every
value by a constant. A constant shift is harmless to the Ridge stage, which
absorbs it in the intercept — but every LightGBM split on `trend` is an
**absolute number**. A tree that learned to split at `trend > 1460` keeps
splitting there while the data underneath it has moved four years, and nothing
errors. The drift thresholds have the same problem: they were derived from a
backtest whose feature matrix used the old origin. This is a silent-failure
mode of exactly the kind section 9 exists for, and the only safe response is to
treat an origin change as a full rebuild.
| `zone` | tree | data column, native categorical | five pooled series; without it the model predicts an average of five and matches none |

**RULE** Features marked `linear + tree` are passed to **both** stages. The
Ridge stage sees only those three; LightGBM sees everything.

*`heating_degrees` was here, and is deleted. Its entire justification was that
demand is U-shaped in raw temperature, so temperature had to be split into two
one-sided terms before either the monotone constraint or the linear
extrapolation stage was possible. Measurement disproved the premise (13): the
V shape is not identified on any grid, and demand rises with temperature across
the whole observed range. Raw `temperature` now carries the below-breakpoint
slope and the extrapolation directly, `cooling_degrees` carries the constraint,
and a deterministic transform of a column the tree already has, offered to a
model that gains nothing from transforms, has no remaining job. The one real
cold-side response measured — IN-NE — the tree reaches through
temperature x zone, with `zone` a native categorical.*

**RULE** Everything else is a measured candidate, added one at a time and kept
only if the ablation shows it earning its place. Candidates: **day-of-year,
cyclically encoded**, humidity, dew point, apparent temperature, rolling
temperatures (24h/72h/168h), consecutive hot days, cloud cover, shortwave
radiation, wind speed, precipitation, festival proximity, cricket match days,
explicit interactions.

*On day-of-year specifically: nothing in the core set represents position in the
year. `hour_of_day`, `day_of_week`, `is_holiday`, `temperature`,
`cooling_degrees`, `trend` and `zone` between them carry the daily cycle, the
weekly cycle, single flagged days, the weather and the multi-year drift — but
not the annual cycle except through temperature. Temperature carries most of it
and not all: not daylight length, not the agricultural pumping season, not the
festival period beyond individually flagged days.*

*There is direct evidence of the gap. IN-NE's apparent cold-side response
measures -2.26 %/C controlling only for hour and weekday, -1.62 %/C with month
fixed effects, and **-0.71 %/C using within-month variation alone** (13). Two
thirds of what looked like a thermal effect was position in the year, being
absorbed by the only feature available to absorb it. That is a feature-set gap
showing up as a distorted temperature coefficient.*

*It stays a candidate rather than joining the core set: it earns its place in
the ablation or it does not.*

**RULE** No demand lag features in Phase 1.

*Rationale:* lead time is 14-38h, so `t-24h` does not exist for later target
hours, and anything newer than `purge_gap_days` is treated as possibly still
estimated. A model that
uses no recent demand and still beats seasonal naive has proved its weather
relationship is real, rather than being a persistence model in disguise.

A consequence worth stating rather than leaving implicit: the forecast path
therefore has no dependency on the demand API at issue time. See the settlement
lag rules in 5g.

### Why `cooling_degrees` stays despite being redundant for trees

It is a deterministic function of a column already present, so a tree can
reconstruct it by splitting. It carries no new information. It is kept for
two reasons:

1. **The Ridge baseline needs it.** Ridge on raw temperature alone fits one
   straight line through a slope that steepens, and is wrong at both ends.
   Comparing against a crippled baseline proves nothing.
2. **It carries the monotone constraint, and nothing else can.** LightGBM
   monotone constraints are per-feature and global. Declaring one on raw
   temperature would forbid the measured cold-side rise in IN-NE. Because
   `cooling_degrees` is zero below the breakpoint, constraining it constrains
   the hot tail — where the constraint is wanted — and leaves the cold side
   free.

*A third reason stood here: that the extrapolation term had to be built on it,
because raw temperature would not serve. That was true only while the linear
stage excluded raw temperature, which it did because of the U-shape. Raw
temperature is now in the linear stage and carries the extrapolation itself,
so the reason has gone.*

**RULE** Include `cooling_degrees` in the ablation and report the result
honestly. The expected finding — that it adds little to the tree while
mattering to the baseline, the constraint and the extrapolation term — is
worth publishing either way.

### Extraction rules

**RULE** Convert timestamps to IST before extracting weekday or calendar date.

*Rationale:* the target window begins at 19:00 UTC, which is 00:30 IST the
following day. Taking `dayofweek` from the UTC timestamp mislabels the first
hour of every forecast, and the same error silently shifts every holiday
lookup by a day.

**RULE** Compute `cooling_degrees` per city, then aggregate to the zone,
load-weighted. Never average temperature first and transform after.

*Phase 1 configures exactly one point per zone (`weather.points`), so the rule is
inert as configured and no weights exist yet. It is written now because it is an
invariant that must hold the moment a second city is added — a Phase 2 candidate
— and because retrofitting it later silently changes every temperature feature.*

*Rationale:* the transform is nonlinear, so the transform of the average is not
the average of the transforms. Delhi at 40 C and Shimla at 20 C average to
30 C giving 6 cooling degrees, where the correct load-weighted answer is 8 with
equal weights and higher still once Delhi's far larger load is weighted in.
The error is largest on the hottest days, which is exactly where it matters
most.

**RULE** `gen_solar_mw` — the solar entry of the Electricity Maps power
breakdown, in MW — is not a feature. It is analysis material only — the
duck curve and solar-penetration trend.

*Rationale:* tomorrow's solar generation is not known at issue time. Using it
would be leakage under INV-1. Forecast shortwave radiation is the legitimate
route to the same signal.

## 5f. Extreme conditions — the governing ideology

This section is principles, not just instructions. When a case arises that is
not covered here, reason from the principles rather than guessing.

### The inversion that defines the problem

In most machine learning problems, accuracy and importance are unrelated.
Here they are inversely related:

```
Common conditions            Extreme conditions
-----------------            ------------------
abundant data                almost no data
model is accurate            model is weakest
errors are cheap             errors shed load
```

**The model is least reliable exactly where it matters most.** Everything
below follows from that sentence.

It is also why a single headline error figure is close to meaningless: it is
an average dominated by the easy 95%.

The five principles are ordered. Each is a precondition for the next.

---

### Principle 1 — You cannot fix what you cannot see

**RULE** Report error stratified into segments. Never publish a single
headline figure alone.

*Rationale:* if 5% of hours carry 15% error and 95% carry 2%, the overall
figure is 2.65% and the failure is invisible. An average cannot show you a
failure confined to a minority of cases, and the minority is the entire point.

**RULE** Temperature band is the primary stratification and is mandatory in
every report:

```
< 20 C          n=4,200     MAPE 2.1%
20 - 30 C       n=18,400    MAPE 1.8%
30 - 40 C       n=11,100    MAPE 2.4%
40 - 45 C       n=1,600     MAPE 4.1%
> 45 C          n=210       MAPE 9.8%    <- the number that matters
```

**RULE** Also stratify by hour of day, zone, and day type (weekday, weekend,
holiday). Each answers a question an average cannot:

| Stratification | Question it answers |
|---|---|
| temperature band | does it fail in heatwaves? |
| hour of day | does it fail at the evening peak, where capacity is booked? |
| zone | is one region far worse than the headline suggests? |
| day type | does it fail on holidays, which it has seen few of? |

*Always report the row count alongside the error. An error figure computed
over 210 hours is not the same kind of statement as one over 18,400, and the
reader needs to see which they are looking at.*

This principle is first because every later decision needs a number to justify
it. Fix before measuring and you cannot tell whether you helped.

---

### Principle 2 — Corrupt data at extremes is worse than no data

A model that faithfully fits biased data is confidently wrong, and nothing
downstream can detect it.

**RULE** Detect hours where demand plateaus or falls while temperature
continues rising. Flag them and **exclude** them from training. Not downweight —
INV-8 admits no partial weight.

*Rationale:* the source reports power **consumed**, not power **wanted**. When
the grid sheds load, consumption is capped by supply and the recorded value
becomes a ceiling rather than an observation:

```
47 C evening
  demand wanted     62,000 MW
  grid delivered    58,000 MW     <- load shedding
  data records      58,000 MW     <- what training sees
```

A model trained on this learns that demand stops rising above about 46 C, and
will then under-forecast every future heatwave while fitting its training data
beautifully. This is why Indian grid reporting separates peak demand, peak
demand met and deficit — the gap is real and the industry has a name for it.

This principle is second because modelling on a corrupt target is wasted
effort. No architecture repairs a biased label.

---

### Principle 3 — Where data ends, physics takes over

A model has two regimes and should behave differently in each: inside the
training range, trust the learned patterns; outside it, fall back to physical
structure. Trees are pure interpolation — they have no concept of "beyond",
and they flatten.

**This principle is why the architecture is a hybrid rather than a single
model.** The mechanisms are specified in section 5c (Model architecture) and
are not repeated here: the Ridge stage carries what must extrapolate, and the
monotone constraint on `cooling_degrees` lets physics overrule sparse evidence
in the hot tail, where data is thin rather than absent. Note the asymmetry —
there is no equivalent physical prior on the cold side, which is why the linear
stage is clamped there rather than constrained (5c).

The point to carry forward is the reasoning, not the mechanism: **when a new
situation arises outside the data, the answer is to supply structure the model
cannot learn — never to trust it to generalise on its own.**

---

### Principle 4 — When you do not know, say so, and lean the safe way

Two separate obligations.

**RULE** When a **weather** input exceeds the training range — `temperature`
or `cooling_degrees`, listed in `features.extrapolation_check` — flag the
forecast as extrapolating and surface it on the dashboard. Below the training
range the linear stage is additionally **clamped** (5c), so the flag says the
forecast is outside what the model knows *and* that the cold extrapolation has
been held flat rather than continued down. In Phase 1b, also
widen its uncertainty band.

*Rationale for the narrow scope:* `trend` is outside the training range on every
forecast by construction (5c), so a check across all features would flag every
row, forever. Band widening is Phase 1b because Phase 1 emits a point forecast
and there is no band to widen.

*Rationale:* a forecast the model cannot support must be labelled. Presented
identically to a confident one, it removes the operator's ability to apply
judgement — and that is the real failure, worse than the inaccuracy itself.

**RULE** Do not aim for the middle when uncertain. Bias toward over-forecast.

*Over-forecasting burns fuel; under-forecasting sheds load. These are not
equally bad, so the forecast should not be symmetric about them. Implemented
in Phase 1b, where the quantile machinery exists to choose the operating point
from evidence rather than by feel.*

---

### Principle 5 — The limit, and the honest response to it

**Some of this is unfixable, and the correct response is disclosure rather
than heroics.**

No amount of engineering makes a model good at 50 C when it has seen 50 C
twice. That is a data problem, and data problems do not yield to cleverness.

**RULE** The goal at extremes is not accuracy. It is:

- not being **confidently** wrong
- failing in the **safe** direction
- **saying** when the model is outside what it knows
- having **measured** exactly how bad it gets

**RULE** Record the training temperature range and the measured per-band
degradation in the model card.

*This reframing is what stops extreme handling becoming an unbounded
engineering project. The target is honesty and safety at 50 C, not accuracy.*

---

### Worked pass — a 48 C hour, every mechanism firing

Training data topped out at 46 C. Tomorrow's forecast says 48 C at 20:00.

```
1  FEATURES       temperature     = 48.0
                  cooling_degrees = 48 - 21.5 = 26.5
                  the training maximum of temperature is 48.6 in IN-NO and
                  below 44 in every other zone, so this is at or past the
                  edge of the data for any zone but IN-NO

2  RIDGE          both terms are live: the shallow slope on temperature
                  everywhere, the steeper one on cooling_degrees above 21.5.
                  the line does not care that the value is unprecedented

3  TREE           seeks a split above its top observed cooling_degrees,
                  finds none, falls back to its top bin
                  contributes a small residual (evening, weekday, June)

4  PREDICTION     exp(ridge + tree) x smearing

                  for comparison: a tree alone would flatten above its top
                  split and run low, silently. that gap is the reason the
                  linear stage exists

5  RANGE CHECK    temperature and cooling_degrees both past their training
                  maxima  ->  flag EXTRAPOLATING

6  UNCERTAINTY    Phase 1b only - band widened. Phase 1 emits the flag
                  and the marker, no band.

7  DASHBOARD      shown with a warning marker, not as a normal number

8  MONOTONICITY   the constraint on cooling_degrees guaranteed the tree
                  contribution could not be negative here. raw temperature
                  is unconstrained, which costs nothing in the hot tail
                  because cooling_degrees is what moves there

9  EVALUATION     once settled, scored in the ">45 C" band, never folded
                  into the headline average
```

The prediction is probably still somewhat wrong. It is wrong by less, wrong in
the safer direction, and labelled as uncertain rather than presented as fact.
That is the whole objective.

## 5g. Metrics

Metrics serve three different jobs with conflicting requirements. Using one
metric for all three is the common failure.

| Job | Question | Needs |
|---|---|---|
| Selection | which model do we ship? | one comparable number |
| Reporting | how good is it, honestly? | breakdown and context |
| Monitoring | has it started failing? | early warning, low noise |

### Selection

**RULE** Model selection follows this procedure exactly:

```
PRIMARY      MASE, mean across folds
CO-PRIMARY   RMSSE - must improve or hold

VETO if:     top REPORTABLE temperature band worse by more than
                 evaluate.veto_tolerance.top_band_pct
                 (the highest band holding at least
                  evaluate.insufficient_band_rows rows - see below)
             |signed bias| worse by more than
                 evaluate.veto_tolerance.signed_bias_pct
             shortfall frequency up by more than
                 evaluate.veto_tolerance.shortfall_freq_pct
             P95 abs % error up by more than
                 evaluate.veto_tolerance.p95_pct

TIEBREAK     fold win rate, then fewer features, then fewer
             tuned parameters at their bound

DIAGNOSTIC   RMSE/MAE ratio, reported alongside
```

**RULE** Every veto is a **tolerance**, never a bare inequality. Each tolerance
is derived from that metric's own fold-to-fold spread in the step 9 backtest and
recorded in section 13.

*Rationale:* "worse in the top temperature band" with no tolerance vetoes on a
0.001% move, and the top band has the fewest rows in the table, so its
fold-to-fold variation is the largest. An untoleranced veto rejects every
challenger on noise from the smallest sample in the report.

**RULE** The band this veto reads is the **highest band holding at least
`evaluate.insufficient_band_rows` rows**, not the highest band that exists. As
measured, that is 40-45 C at 1,102 rows; the `> 45 C` band holds **25**. The
`> 45 C` band is still computed, still reported, and still flagged insufficient
— it simply never gates a promotion.

*Rationale:* a veto evaluated on 25 rows is not a quality check, it is a coin
toss that rejects challengers at random, and 13's band-sufficiency rule already
says a band that thin is reported as "insufficient rows to judge" rather than as
a number. A figure too weak to quote is too weak to veto on.

*The loss is real and belongs in the model card rather than buried here: the
band this project most wants to be good at is the one it has least evidence
about. Twenty-five hours above 45 C, all of them in IN-NO, is what one weather
point per zone over nine years buys. A second point per zone — a Phase 2
candidate in 5e — is the direct remedy.*

*Rationale for the co-primary:* MASE is built on mean **absolute** error,
which is linear and therefore treats errors as interchangeable regardless of
size. Ten 200 MW misses and one 2,000 MW miss give the same MAE and the same
MASE — but a grid absorbs the first and has an incident on the second.
Requiring RMSSE to improve as well means a model cannot win by trading many
small errors for a few large ones. Both must move, so it has to be genuinely
better rather than differently distributed.

*Rationale for not switching to RMSSE alone:* squared-error metrics are
fragile to bad data — a single corrupt row can dominate the score. We exclude
estimated and suppressed rows, but "we believe we excluded them all" is not
the same as a metric that cannot be hijacked by one row we missed.

**RULE** Compare fold-by-fold win rate, not only the mean. A model whose good
mean comes from one unusually favourable fold while losing the other eleven is
worse, not better.

**RULE** The selection number is never quoted as the final result. It is
optimistically biased by having been selected on. The holdout is the reported
figure.

### Reporting

**RULE** Never quote a single headline number alone.

| Metric | Formula | Role | Blind spot |
|---|---|---|---|
| MAPE | mean(\|a-p\|/a) | headline, comparable across zones | asymmetric; an average |
| MAE | mean(\|a-p\|) MW | physical magnitude an engineer can act on | not comparable across zones |
| RMSE | sqrt(mean((a-p)^2)) MW | large misses count more, matching real cost | outlier-sensitive |
| MASE | see formulas below | is it beating the baseline at all | an average |
| RMSSE | see formulas below | penalises large misses, baseline included | outlier-sensitive |
| Signed bias | mean((p-a)/a), percent | direction, not accuracy | says nothing about magnitude |
| Shortfall frequency | % hours p < a by more than `shortfall_threshold_pct` | operational risk in the dangerous direction | ignores over-forecast |
| P95 abs % error | 95th percentile of \|a-p\|/a | how bad it gets, not how bad on average | tail only |
| Peak error | error at the hour of the day's **actual** maximum | capacity is booked against peak | one hour per day |
| Ramp error | \|delta_a - delta_p\| per hour, over `ramp_window_hours_ist` | shape rather than level | noisier by construction |
| Ramp MASE | ramp error / the seasonal-naive baseline's ramp error, same rows | makes ramp error interpretable | — |

*Two of these carry more weight than their position suggests.*

*Signed bias is the only entry that is not an accuracy metric. A model can have
excellent MAPE and be wrong in the same direction every day — a systematic,
correctable fault that no accuracy metric reveals. It also moves before total
error does, which is why it is the primary drift signal.*

*Ramp error is the only entry measuring shape. Two forecasts with identical
MAPE can differ completely in whether they tell the operator to ramp 3 GW or
5 GW. As solar penetration deepens the evening ramp each year, this is also the
metric that tracks whether the model is keeping pace with a physical
phenomenon that is actively changing.*

### Monitoring

**RULE** The monitoring set is exactly two metrics: 30-day rolling MAPE and
30-day rolling signed bias.

*Rationale:* more metrics watching for drift means more false alarms, and a
trigger that fires spuriously gets ignored. Thresholds are absolute, set from
the Phase 1 backtest, never recomputed from recent performance (see section 6).

**RULE** Track pipeline health separately from accuracy: forecast completeness
(all 24 values produced), data freshness (age of newest measured row), job
success, training duration.

*Rationale:* a silently failed job is indistinguishable from a healthy model
when viewed only through accuracy metrics — the numbers simply stop moving.

### Settlement lag

Demand rows are published estimated and revised to measured some days later —
one observed case took two days; the distribution is not yet known (see 13).
INV-4 already forbids scoring an estimated row. These rules say what that costs.

**RULE** The forecast path has no dependency on the demand source. Features are
calendar, temperature and zone only (5e), so at issue time the model needs the
weather API and nothing else. Settlement lag affects scoring and monitoring. It
never affects forecasting.

*Rationale:* worth stating because it is currently true by accident. Demand lags
were dropped for an unrelated reason — a 14-38h lead time makes them unavailable
— and this independence came free. Adding a lag feature would reintroduce the
dependency: at issue time the value would still be estimated, so the model would
be served a `TIME_SLICER_AVERAGE` fill-in having been trained on measured values.
That is train/serve skew, and it would bite hardest exactly when the data pipeline
is already under stress.

*Exception:* the seasonal-naive baseline is demand-based. At scoring time this is
harmless — everything has settled. If the dashboard shows the baseline beside a
forecast not yet scored, that comparison reaches back one week and must be flagged
when those rows are still estimated.

**RULE** The 30-day monitoring window ends at the **settlement frontier** — the
newest timestamp for which all expected rows have settled to measured — not at
today. It is a fixed-width window that lags the present. The frontier is computed
**per zone** for per-zone triggers, and as the earliest of the five for the
pooled figure.

*Rationale:* a window ending at today holds `30 - settlement_lag` days of
scorable rows rather than 30, and fewer still on a slow settlement day. Sample size would then move with
pipeline health rather than with model quality, and a rolling metric whose
denominator wobbles is not measuring what its name says.

**RULE** Score every settled row as it settles. Do not wait for a day to
complete. This governs the **score archive** — the audit trail, and the
dashboard's pending tail — not the trigger window, which is frontier-terminated
and therefore always fully settled.

**RULE** Report **settled fraction** alongside every monitoring figure, measured
against the rows expected **up to today**, not against the window.

*Rationale:* unsettled rows are not a random sample. If estimation clusters at
particular hours or zones — plausible, since it fills reporting gaps and reporting
gaps are not uniform — then partial-day scoring silently over-weights whichever
hours settle fastest. Peak-hour error could be measured on a biased subsample for
weeks with nothing to indicate it.

**RULE** Monitoring and trigger scores are **frozen**: the score computed when a
row first settles is the one that stands, even if that row is later revised again.
Backtest scores are **live**: recomputed from the current archive on every run.

*Rationale:* the two serve different purposes and the conflict between them is
unavoidable. Monitoring history is a record of decisions taken with the information
then available; recomputing it means a trigger that fired last week might not fire
today, and the audit trail contradicts itself. A backtest is an experiment and
should use best-known truth. Stating which is which is what stops the two paths
diverging silently, each believing itself authoritative.

**RULE** Drift thresholds are calibrated against a backtest that **replays the
settlement frontier**: evaluating the monitor at simulated date D scores only rows
that were settled as of D, reconstructed from `data/raw/demand_revisions/`.

*Rationale:* in a backtest run today everything has settled, so a 30-day window
holds its full complement of rows. The live monitor never sees that — it always
works at the frontier, with fewer rows and therefore more variance. A threshold
calibrated on backtest variance and applied to a noisier live metric fires more
often than designed, and the Monitoring rationale above names the consequence: a
trigger that
fires spuriously gets ignored. This is point-in-time correctness applied to
monitoring rather than to features, and it is possible only because 5d archives
revisions. Until enough revision history exists, calibrate on the fully settled
backtest and record that the thresholds are provisionally optimistic.

**RULE** State the detection delay wherever detection is claimed.

```
detection delay  =  settlement lag  +  window for the signal to emerge
```

*Rationale:* for the rolling-error and signed-bias triggers this is immaterial —
they watch for drift that moves over months. For the structural-break trigger it is
a real limit: that trigger exists to catch shocks, speed is its entire purpose, and
it cannot see the most recent `settlement_lag_days` because those measurements do
not exist yet. There is no fix. "Detects shocks" and "detects shocks roughly
`settlement_lag_days + 1` after they begin, because that is when meter data
settles" are different claims, and only the second survives a follow-up question.

### Phase 1b — quantiles

Pinball loss as the scoring rule, plus interval coverage: does the 90% band
contain 90% of actuals? A band covering 99% is uselessly wide; one covering
70% is a lie.

### Stratification

**RULE** Every reporting metric is computed across these dimensions, always
with row counts.

| Dimension | Question it answers |
|---|---|
| temperature band | does it fail in heatwaves? |
| hour of day | does it fail at the peak? |
| zone | is one region much worse than the headline? |
| day type | does it fail on holidays? |
| lead time | does error grow with distance — and if not, why not? |
| time, rolling | is it degrading? |

**RULE** Report row counts alongside every figure. "9.8% over n=210" and
"1.8% over n=18,400" are different kinds of claim, and a reader who cannot
distinguish them cannot calibrate either.

**RULE** Error must increase with lead time. If it does not, treat it as a
suspected leak and investigate before proceeding.

*Lead-time stratification is a diagnostic as well as a report: a 38-hour
forecast that is no worse than a 14-hour one usually means information from
after the issue time has reached the features.*

### Formulas

Both scaled metrics use the **out-of-sample** variant: the denominator is our
seasonal-naive baseline scored on the same test rows as the model.

```
MASE  =  sum |y - yhat|  /  sum |y - b|

RMSSE =  sqrt(  sum (y - yhat)^2  /  sum (y - b)^2  )

   y     = actual
   yhat  = model forecast
   b     = seasonal-naive baseline (defined in 5c)
```

**RULE** State the variant wherever these are reported. The original MASE
definition uses the in-sample naive error as denominator and yields different
numbers. The out-of-sample form is used here because it is a like-for-like
comparison and puts the baseline under the same information constraint as the
model — same rows, same settlement lag, same purge gap.

## 5h. Failure policy

### The governing rule

**RULE** Never publish an output that looks normal when it is not.

*Everything below follows from this. A forecast produced from stale inputs is
often still useful — but only if whoever reads it knows. An unmarked degraded
forecast is worse than no forecast, because it removes the reader's ability to
apply judgement, which is the same failure identified in 5f principle 4.*

### The three responses

| Response | When | What happens |
|---|---|---|
| **Degrade** | a worse but honest output is possible | produce it, flag it, publish the flag |
| **Skip** | no honest output is possible | produce nothing, record why, alert |
| **Fail fast** | continuing would corrupt stored state | stop before writing anything |

**RULE** Prefer degrade over skip, and skip over fail — but only when the
degraded output can be labelled. Silent degradation is not an option at any
level.

### Specific failures

| Failure | Response |
|---|---|
| **Weather forecast API down at issue time** | Degrade and retry — see below. Issue from the most recent archived vintage, flagged with its age. Retry every `retry_interval_minutes` and re-issue when the API returns. |
| **No archived vintage at all** | Skip. No forecast issued. Alert. Only possible in the first days of operation or after an outage longer than the archive covers. |
| **Demand API down** | Issue the forecast normally; it does not depend on demand at issue time. Skip scoring only, carry drift metrics forward unchanged, flag `scoring_skipped`. |
| **One zone returns nothing** | Degrade. Publish the zones that succeeded. Mark the missing zone unavailable — never display its previous forecast as though current. Never fail the run for one zone. |
| **Fewer than `min_zones_to_publish` succeed** | Skip. Alert. |
| **Gaps in cached history** | Log the gap, exclude those rows. If a fold's gap fraction exceeds `max_gap_fraction`, mark that fold's result unreliable in the report rather than dropping it silently. |
| **Retrain triggered, training errors** | Keep the champion. Promote nothing. Alert. Retry on the next trigger, not immediately. |
| **Challenger trains but loses** | Not a failure — the gate working. Log the comparison and keep the champion. |
| **Fewer than 24 hourly values produced for a zone** | Skip that zone. Never publish a partial day for it. Other zones publish normally, per the row above. |
| **Config placeholder unreplaced** (see 13) | Run, but propagate a `placeholder_in_use` flag into the output metadata and onto the dashboard. |
| **Missing required config key** | Fail fast at startup. Do not substitute a default. |

*On partial days:* a dashboard showing 19 of 24 hours invites the reader to
assume the rest are coming. They are not. Publish 24 or publish nothing.

*On stale weather:* this is where the daily forecast archive (5d) pays off
operationally as well as scientifically.

Because 5d archives the **full forecast horizon** the API returns rather than
only the 24 hours used, every target date already has a chain of vintages by
the time it arrives:

```
Target = tomorrow (D+1)

  issued yesterday     age 24h    <- freshest fallback
  issued 2 days ago    age 48h
  issued 3 days ago    age 72h    <- current cutoff
  issued 4 days ago    age 96h
  ...up to the horizon the API returns
```

**RULE** On an outage, select the vintage covering the target period with the
**smallest age**, subject to `max_forecast_vintage_age_hours`.

*The consequence is that a multi-day outage degrades gracefully rather than
falling off a cliff. A three-day outage still produces forecasts, from
progressively staler weather, each flagged with its age. It costs nothing
extra — the vintages are already on disk, because storing the whole horizon
was the same API response either way.*

**RULE** `max_forecast_vintage_age_hours` is not a judgement call. Set it
where a stale forecast stops beating the no-weather baseline.

*Rationale:* score each vintage age against actuals from the archive and find
the age at which a forecast becomes worse than seasonal naive with no weather
input at all. Past that point the stale weather is actively misleading the
model rather than helping it, and using it is worse than not having it. The
measurement uses data already being collected. Tracked in section 13.*

**RULE** Do not build a climatology fallback.

*Rationale:* it is a separate code path — computing, storing and serving
historical means — for a case that essentially cannot occur once the archive
exists. The previous vintage is always better than a climatological average
and needs no new mechanism. If there is genuinely no vintage, skip and alert.

### Degrade, retry, supersede

The weather forecast is the model's dominant input, so an outage is the
failure most worth handling well. It is also the one where a slightly later
answer is far better than a permanently degraded one.

**RULE** On weather API failure at issue time:

```
1  issue immediately from the most recent archived vintage,
   flagged  stale_weather_<age>h

2  retry every `retry_interval_minutes` for up to
   `retry_window_hours`

3  on success, RE-ISSUE a fresh forecast that supersedes the
   degraded one

4  if the window expires, keep the degraded forecast and stop
   retrying
```

*Rationale:* a day-ahead forecast issued at 10:00 and refreshed at 11:30 has
lost ninety minutes of lead time and gained a current weather forecast. That
is a good trade. Publishing the degraded version immediately means there is
always something to act on; superseding it means nobody is stuck with the
stale one longer than necessary.

**RULE** A re-issue is a new version, not a rewrite. Retain every version with
its actual issue time.

**RULE** Compute lead time from the **actual** issue time, never the nominal
10:00.

*Rationale:* a forecast re-issued at 11:30 has a shorter horizon than one
issued at 10:00, so it is a slightly easier problem. Recording the real issue
time means the lead-time stratification in 5g accounts for this automatically,
with no special-casing in the metrics.

**RULE** Accuracy is scored against the last version issued within the retry
window. All versions are retained for audit.

*The degraded version, being flagged, is excluded from headline accuracy under
the flag rule above. If it was superseded by a clean forecast, the clean one
counts — the system genuinely did produce an unflagged forecast that day, just
later than usual, and the lead-time record shows exactly how much later.*

### Status propagation

**RULE** Every forecast record carries a `flags` list. It is one mechanism,
shared by degradation and by the extrapolation warnings in 5f.

```
flags: []                        normal
flags: [stale_weather_24h]       degraded input
flags: [extrapolating]           input outside training range (5f)
flags: [placeholder_in_use]      a config assumption is unreplaced (13)
```

**RULE** Flags propagate to the dashboard and into the stored forecast record.
A flagged forecast is visually distinct from a clean one.

**RULE** Rows carrying an **input-degradation** flag — `stale_weather_*` — are
excluded from headline accuracy figures and reported separately. A model should
not be blamed for a stale input, nor credited for one.

**RULE** `extrapolating` and `placeholder_in_use` do **not** exclude a row.
`extrapolating` rows are reported in their temperature band (5f); a
`placeholder_in_use` row is labelled, per section 13.

*Rationale:* several placeholders are only measurable after weeks of live
running, so every early forecast carries `placeholder_in_use`. Excluding those
rows would leave the headline metric and both drift metrics with no rows at all,
disabling the monitor the flags exist to protect.

### Operational

**RULE** The daily job is idempotent. Re-running it for the same issue date
must not double-write, double-score, or double-count a trigger.

**RULE** After `max_consecutive_failures` consecutive failed runs, stop
retrying and escalate. Do not hammer a dead API.

**RULE** Every run writes a status record — success, degraded with reasons, or
failed with reason — whether or not it produced a forecast.

*Rationale:* a job that fails silently is indistinguishable from a job that is
not scheduled. The status record is what makes the monitor-alarm in section 6
checkable at all.

## 6. Retraining policy

**RULE** The daily job is a **monitoring** job. Retraining is one action it
may choose to take. It is not a retraining schedule.

It runs once a day at issue time — 10:00 IST, not overnight — in the canonical
order given in 5b. Steps 1 to 4 and step 7 of that sequence are unconditional;
only step 5 depends on a trigger.

**RULE** Retrain only when a trigger fires. The three triggers are defined
exactly as follows.

| | Rolling error | Signed bias | Structural break |
|---|---|---|---|
| **statistic** | 30-day rolling MAPE on settled rows | 30-day rolling mean of *signed* percentage error | single-day MAPE |
| **compared to** | upper bound from the replay | symmetric ± bound from the replay | much higher bound from the replay |
| **debounce** | 3 consecutive days | 3 consecutive days | none — already a single-day statistic |
| **scope** | pooled **and** per zone | pooled **and** per zone | per zone |
| **catches** | obvious degradation | concept drift, earlier than raw error | shocks — heatwave, lockdown, grid event |
| **on firing** | retrain attempt | retrain attempt | **alert and watch** — see below |

**RULE** Signed bias is reported broken out by lead time as well as pooled.

*Rationale:* random error cancels when summed with sign; systematic error
accumulates. So the signed mean has a far lower noise floor than MAPE and moves
first for the same underlying problem. For this model the first suspect behind a
persistent bias is `trend` — the only feature guaranteed to sit outside its
training range on every forecast, and therefore the term that goes stale first. A
trend problem grows with lead time; a temperature problem does not.

**RULE** Every trigger is evaluated per zone against that zone's own threshold,
as well as pooled.

*Rationale:* the five zones differ enormously in size. IN-NE degrading badly
would barely move a pooled figure dominated by IN-NO. A pooled-only monitor is
blind to precisely the failure that is easiest to miss. Detection is per zone;
the retrain remains global, since it is one pooled model with `zone` as a
feature.

**RULE** Never retrain on a calendar schedule.

*Rationale:* the drivers of drift here — AC penetration, solar buildout, EV
load, economic growth — move over years. A monthly cadence is out of
proportion to the physics.

**RULE** Trigger thresholds are absolute, derived from the original backtest,
stored in `config/config.yaml`. Never recompute a threshold from recent
performance.

*Rationale:* an adaptive band drifts along with the degradation and never
fires. The model gets worse, the band gets looser, everything looks fine
permanently. This is the one way the design fails silently, and it fails
exactly like the problem it exists to catch.

**RULE** Those thresholds are derived from a backtest that replays the settlement
frontier, not from a fully settled one. See 5g — a threshold calibrated on more
data than the live monitor will ever hold fires spuriously.

**RULE** A long gap with no trigger raises an alarm to verify the monitoring
is alive. It does not trigger a retrain.

*Rationale:* a silently failed scoring job is indistinguishable from a healthy
model when viewed from outside.

**RULE** A trigger authorises an attempt, not a deployment. Promotion remains
gated by champion/challenger comparison.

**RULE** Log every trigger event with which condition fired, whether it was
suppressed, and why.

**RULE** Simultaneous triggers need no precedence. The two error triggers
authorise the same single action, so a day on which both fire runs **one**
attempt, not two. A structural break firing alongside them additionally opens a
watch; it never adds a second attempt. Log every condition that fired.

### Deriving the thresholds

**RULE** Thresholds are not chosen as a percentile. Choose the tolerable
false-alarm rate and let the threshold fall out of it.

```
false_alarm_budget_per_year          (the tunable)
        |
replay the monitor across the whole backtest test period,
where by construction nothing has drifted, so every firing is false
        |
sweep threshold x debounce, count EPISODES per simulated year
        |
keep the tightest combination that stays inside the budget
```

**RULE** The unit counted is the **episode**, not the breach-day. A maximal run
of consecutive firing days is one episode, and a new episode cannot begin until
the cooldown has expired.

*Rationale:* consecutive 30-day windows share 29 of their 30 days, so breaches
arrive in clumps rather than scattered — one problem produces a run, not a
sprinkle. Each episode costs exactly one retrain attempt; breach-days cost
nothing. Counting days would make an 18-day clump look like eighteen alarms and
would drive the threshold far looser than it needs to be. This is also the
reason a percentile cannot be used: a percentile measures the fraction of days,
which is not the quantity anyone cares about, and cannot be converted into
episodes without knowing the correlation structure.

*Rationale:* a 95th-percentile band breaches on roughly 5% of windows with
nothing wrong — about one false trigger every twenty days — and 5g already names
the consequence: a trigger that fires spuriously gets ignored,
leaving a monitor that is trusted and dead (5g, Monitoring). The false-alarm rate must be a
measured number, not a hope. Overlapping 30-day windows are heavily
autocorrelated, so the firing rate of "3 consecutive days above threshold"
cannot be computed on paper; it can be measured in one replay pass. It is also
the defensible answer: "set so the monitor produces at most two false retrains
a year, measured over 12 months of replay" survives a follow-up question that
"the 99th percentile" does not.

**RULE** Thresholds are stored together with the git sha of the backtest that
produced them. A mismatch between that sha and the current model **disarms** the
monitor rather than firing on stale numbers.

*Rationale:* change the features and the error distribution moves, so the old
thresholds no longer mean what they meant.

**RULE** The replay uses the walk-forward model **as refit at every fold**, not a
single model frozen for the whole test period.

*Rationale:* the two give different thresholds and this document must not leave
the choice open. A refreshed model is always current, so every wobble in its
rolling error is forecasting difficulty — some months are simply harder — which
is exactly the noise floor a false alarm must sit above. A frozen model also
accumulates genuine ageing degradation, and calibrating against that would fold
the signal into the noise, producing a threshold loose enough never to fire on
the ageing it exists to catch. The frozen replay is a separate and useful
experiment — it measures how fast a champion decays, which is what justifies the
cooldown lengths — but it does not set the threshold.

**RULE** Where several threshold-and-debounce combinations sit inside the budget,
choose between them by measured detection delay on **injected drift**, never by
preference.

```
replay again, shifting predictions by d from a chosen day,
for d in {2%, 5%, 10%}; count days until each surviving
combination fires
```

*Rationale:* the budget says how much sensitivity may be spent; it does not say
what to spend it on. A tight threshold with a long debounce catches small
persistent drift and reacts slowly to shocks; a loose threshold with a short
debounce does the reverse, at identical false-alarm cost. Injected drift turns
that into a measurement. Where two combinations are close, prefer the one that
catches small drift, since a large shock will also reach the structural-break
trigger.

**RULE** Three kinds of firing are counted separately. Only the first spends the
budget.

| | what it is | spends |
|---|---|---|
| false alarm | fires while the model is healthy and unchanged | the budget |
| true positive | fires because something genuinely changed | nothing |
| echo | fires after a fix, because the rolling window is still stale | nothing — suppressed by cooldown |

*Rationale:* the budget is measured on a replay containing no promotions, so an
echo cannot appear in it and cannot consume it. Conflating the three makes the
budget look overspent when it is not, and invites loosening a threshold that was
correct.

**RULE** The post-promotion watch threshold is derived by the same procedure,
swept over 7-day windows rather than 30.

*Rationale:* fewer rows means a noisier statistic, so its threshold comes out
looser. That looseness must be measured, not assumed.

**RULE** While `drift.thresholds_derived` is false, the daily job computes,
records and publishes every metric and **cannot fire any trigger**. The
dashboard shows *monitor not armed*.

*Rationale:* a half-configured system that makes an arbitrary decision on day
one is the silent failure of section 9 in its purest form.

### Routing — is it the model, or is it the data?

**RULE** A met trigger condition is not yet a retrain. Every trigger passes
through this check first.

```
trigger condition met
  |
  |-- within-band error unchanged, only the mix of conditions moved?
  |        -> DATA DRIFT. Log, annotate the dashboard, do NOT retrain.
  |-- suppression flags present on those rows (INV-8)?
  |        -> data exclusion, not a trigger
  |-- ingest validation failed, or settled fraction too low?
  |        -> pipeline alert, or too early to judge. Not a trigger.
  |-- bands degraded across the board and bias leaning one way?
           -> CONCEPT DRIFT. Authorise a retrain attempt.
```

*Rationale:* the same headline number has two opposite meanings. A three-week
heat patch raises overall MAPE from 3.2% to 5.1% while every temperature band
stays flat and only the row counts move — the model is unchanged and is simply
being asked more of the hard questions. Genuine drift raises overall MAPE to the
same 5.1% with every band degraded and bias leaning. The stratified error table
of 5g is what separates them, and it is already computed for the dashboard, so
this is a comparison rather than new machinery.

**RULE** Retraining during an anomalous weather patch is forbidden even if the
error trigger fires.

*Rationale:* the relationship has not changed, so there is nothing to learn, and
recency weighting would overweight an unrepresentative few weeks. Where the
patch exceeds the training range — 48 C against a training maximum of 46 — the
linear stage is extrapolating and some under-forecast bias is expected and is a
real limitation. The response is still to flag those forecasts as extrapolating
and keep the data. It becomes genuinely valuable at the *next* legitimate
retrain, when the model gains extreme examples it never had. An anomalous patch
is a poor reason to retrain and an excellent thing to have retrained on later.

### Structural break — alert, not action

**RULE** A structural break raises an alert, flags the published forecast
low-confidence, and opens a **watch**. It does not itself authorise a retrain.

```
day 0     alert, flag forecasts low-confidence, open watch
day 1-6   |-- deviation gone            -> close the watch, log it, no retrain
          |-- 3 of 7 days breach        -> escalate to a retrain trigger
```

*Rationale:* a shock is one or two days of data buried under years of history —
there is nothing to retrain on yet, and the settlement lag of 5g means it cannot
even be seen until it is already days old. Escalation waits until there is
something to learn from, and stops one strange day discarding a working
champion.

### Cooldown

**RULE** After a promotion, the **30-day trigger metrics** authorise no new
retrain attempt for 30 days. After a rejection, 14 days. After an attempt that
failed with an error, 14 days. Measurement and publication continue throughout;
only the *action* is suppressed, and every suppressed firing is logged and shown.

*The cooldown scopes the 30-day metrics only. The 7-day post-promotion watch
stays live inside it — see below.*

*Rationale for the failure case:* a training error promotes nothing and rejects
nothing, so without its own cooldown the still-breached trigger fires again the
next day and keeps firing, which is both the daily-retrain loop this section
forbids and an unbudgeted overspend, since the budget is counted in episodes and
an episode is defined as ending at a cooldown.

*Rationale:* the rolling window still contains the old model's errors after a
promotion. Worked through with a 4.5% band, healthy error 3.2% and drifted error
6.4%: the trigger fires on day 15, the fix is promoted, and the 30-day figure
then sits **frozen at 4.80% from day 15 to day 30** — not slowly improving, flat,
because healthy days are entering the front while healthy days leave the back and
the bad block in the middle is untouched. It first drops below the band on day
33. Without a cooldown that is eighteen consecutive daily retrains after the
problem was already solved, each challenger differing from the champion by one
day of data — the exact calendar retrain schedule this section forbids. A
rejection gets 14 days for the same reason inverted: if the challenger lost
today, one more day of data will not change that.

**RULE** Do not reset the window on promotion, and do not evaluate the trigger
on days-since-promotion only.

*Rationale:* resetting leaves no monitoring metric for 30 days beginning at the
riskiest moment in the system's life. A growing window of 1, 2, 3 days is far
noisier than the 30-day sample the threshold was calibrated for, so the threshold
does not apply to it.

**RULE** During a cooldown the 30-day trigger metric is suppressed, but the
7-day **post-promotion watch** — computed over the current champion's forecasts
only — stays **live and may escalate to a retrain trigger**.

```
during cooldown:
  30-day trigger metric   suppressed (stale, echoing the old model)
  7-day champion watch    LIVE, can escalate
```

*Rationale:* the trigger metric answers "should we act" and gives no signal at
all for roughly fifteen days after a fix. The watch answers "did the fix work"
within the week. More importantly, a cooldown that suppressed everything would
leave the system blind for thirty days beginning at the moment it had just
changed the model — when a new problem is most likely and least expected. The
watch is the only metric in that period uncontaminated by the old model's
errors, by construction: it is computed solely from forecasts the new champion
issued. Suppressing the echo and covering the blind spot are therefore the same
mechanism used twice, not two mechanisms.

**RULE** An escalation from the watch resets the cooldown. It does not stack.

### What the retrain attempt is

**RULE** A triggered retrain uses the same architecture and the same
hyperparameters as the champion. It never retunes.

*Rationale:* re-searching hyperparameters against recent performance makes
choices using the test period. That is how a test set becomes training data —
through the experimenter rather than the code (INV-7). Hyperparameter search is a
separate deliberate act on the reserved tuning window.

**RULE** The attempt trains on full history with recency weighting (section 7),
through the settlement frontier rather than through today, and is scored against
the champion on the standard folds using the selection procedure of 5g. Either
outcome writes a promotion decision record with the five pins (section 14).

### Liveness

**RULE** The daily job must write a scoring record with n > 0 every day. A day
without one is a pipeline alert the next morning.

*Rationale:* the 90-day no-trigger alarm is a real check but a slow one. A dead
monitor should be caught in a day, not a quarter. Keep both — the daily record as
the fast net, the 90-day alarm as the slow one.

---

## 7. Training data rules

**RULE** Every retrain uses the full available history, with recency
weighting. Never use a short rolling window.

*Rationale:* electricity demand has a strong annual cycle. A model trained on
a few recent months has never seen a summer; asked to forecast 45 °C it is
extrapolating into conditions absent from its training data entirely.

**RULE** Apply recency weighting: `weight = 0.5 ** (days_ago / half_life)`.
Half-life is tuned by backtest. Starting value: 365 days.

*Rationale:* resolves the tension between wanting more data and wanting
current data. Old data is retained for seasonal coverage; stale relationships
lose influence rather than being discarded.

**Note for implementers:** training window, recency weighting and retrain
trigger are three independent knobs solving three different problems —
seasonal coverage, staleness, and whether rebuilding is worth it. Do not
conflate them.

---

## 8. Repository conventions

| Path | Contains |
|---|---|
| `config/config.yaml` | every tunable value |
| `src/config.py` | the only module that reads config or secrets |
| `src/ingest/` | API clients — one module per external source |
| `scripts/` | entry points, invoked via the Makefile |
| `data/raw/` | cached API pulls and archives; DVC-tracked, ignored via DVC generated entry |
| `data/interim/` | derived datasets; DVC-tracked, ignored via DVC generated entry |
| `reports/` | backtest output, logs, charts |
| `state/` | committed append-only records: `scores/`, `drift/`, `promotions/` (the promotion decision records of 14) |
| `models/` | champion pointer (`.dvc`) only |
| `mlruns/` | MLflow file store (DVC-tracked) |
| `tests/` | one test per invariant, plus the feature contract test |
| `.github/workflows/` | `daily.yml`, `retry.yml`, `ci.yml` (see 14) |
| `reports/model_card.md` | training ranges, per-band degradation, replaced placeholders |
| `docs/` | the published dashboard — static HTML + SVG, served by Pages (see 15) |
| `Dockerfile` | the pinned environment, published to GHCR |
| `.env` | secrets. **Gitignored. Never commit, never print, never echo.** |

**RULE** All entry points are exposed as Makefile targets. `make setup` must
work on a fresh clone.

**RULE** Commit messages state what changed and why, in prose. Reference
measured evidence where a claim is made.

---

## 9. Invariants

Breaking any of these produces a plausible number that is wrong. There will be
no error message.

**INV-1 — No leakage.** Only information available at prediction time may be
used as a feature. For weather this means the **forecast**, never the actual.
Enforced structurally: `fetch_archive()` and `fetch_forecast()` are separate
functions in `src/ingest/weather.py` and must remain so.

**INV-2 — No random train/test split.** Time series validation is
walk-forward only: train on the past, test on what came next. A shuffled split
trains on the future to predict the past.

**INV-3 — Never train on rows whose `estimation_method` is not in
`quality.trainable_estimation_methods`.** Rows with no estimation — measured —
are always trainable. **The `is_estimated` flag alone is not sufficient**: the
source uses three estimation methods and they are not equivalent (11). One,
`TIME_SLICER_AVERAGE`, is the fill-in this invariant was written for, and
training on it teaches the model to reproduce an average. Another,
`GENERAL_PURPOSE_ZONE_MODEL`, is a modelled series measured to be roughly four
times too smooth at the evening peak — training on it teaches under-dispersion,
which is invisible in a MAPE headline and fatal to 5f's extremes and to INV-8.

*This invariant originally asserted that `is_estimated == True` meant a
`TIME_SLICER_AVERAGE` fill-in. That was written from a single observation and
stated as fact; it is false for two of the three methods. Keeping the allowlist
in config rather than in code means the decision is versioned and reviewable
rather than buried.*

**INV-4 — Score only against measured rows.** Rows are revised after
publication. A row scored while still estimated produces error that is not
real error.

**INV-5 — Baseline before claim.** No performance claim is made without the
baseline number stated alongside it.

**INV-6 — Secrets never leave `.env`.** Not in code, not in logs, not in
committed files, not in terminal output.

**INV-7 — Never select hyperparameters using walk-forward test folds.** Tune
on the reserved window only. The model never saw those rows, so it feels
clean — but the experimenter did, and a test set used to make a choice has
become training data.

**INV-8 — Never train on suppressed-demand hours.** Where the grid shed load
the recorded value is a supply ceiling, not a demand observation. Training on
it teaches the model that demand stops rising in a heatwave.

**INV-9 — One feature definition.** Training and serving both call
`features/build.py` and nothing else. A second implementation drifts from the
first, and the model is then served inputs subtly unlike the ones it learned
from, with nothing erroring. Enforced by a contract test in CI (see 14).

---

## 10. Open decisions — NOT DECIDED

**Do not implement anything below without asking first.** These are open by
intent, not by oversight.

- Timeline and dates (the milestone *content* is fixed in 12 and 14)
- **Confirmation of the estimation-tier decision.** DECIDED provisionally
  (13): trainable methods are measured plus `MODE_BREAKDOWN`. It is provisional
  on one test — the 2024-11-05 discontinuity check in 13. If that test finds a
  material discontinuity, the decision is void, the trainable span becomes
  measured-only, and **5c's split budget has to be redesigned around it. That
  redesign is the repository owner's decision, not an implementer's.**

---

## 11. Verified facts

Established by direct probe. Do not re-derive or guess.

**RULE** API responses arrive in camelCase (`isEstimated`, `updatedAt`,
`createdAt`). `src/ingest/` converts every field to snake_case on write, and
every downstream reference — features, validation, invariants — uses the
snake_case form. There is exactly one conversion point.

### Electricity Maps — probed 2026-09-03

| | |
|---|---|
| Base URL | `https://api.electricitymap.org/v3` |
| Auth | header `auth-token: <key>` |
| Range endpoint | `GET /power-breakdown/past-range?zone=&start=&end=` |
| Latest endpoint | `GET /power-breakdown/latest?zone=` |
| **Demand field** | **`powerConsumptionTotal`**, megawatts |
| Timestamps | **UTC**. India is UTC+5:30 — a half-hour offset |
| Granularity | hourly confirmed (168 rows for a 7-day window) |
| **History depth** | **all five zones from 2017-01 (measured 2026-09-08, binary search against the floor 2015-01-01)** |
| **Range limit** | **10 days per `past-range` call at hourly granularity (measured 2026-09-08). A longer window returns 4xx with `Date range exceeded 10 days limit for hourly data`, which `fetch_range` treats as unrecoverable — so an oversized chunk yields an empty pull that looks like a completed one** |
| **Rate limit** | **2400 requests per 60 seconds (measured 2026-09-08, from `x-ratelimit-limit` / `ratelimit-policy`). A full five-zone backfill is roughly 340 requests, so the request budget is not a constraint** |
| Zones | `IN-NO`, `IN-WE`, `IN-SO`, `IN-EA`, `IN-NE`, plus `IN` |
| Estimation flags | `isEstimated` (bool), `estimationMethod` (string). **Three methods observed, and they are not equivalent — see below** |
| Revision behaviour | rows published as estimates are overwritten with measured values days later; visible as `updatedAt` > `createdAt` |
| Licence | academic, non-commercial. **Attribution to Electricity Maps required in published work.** Expires 2027-03-04 |

*Because the licence expires, historical data is cached to disk early. Every
downstream step reads the cache, so training, backtests and charts survive the
key lapsing. Only the live daily update depends on the API.*

#### Estimation methods — three, not one (measured 2026-09-08)

Recorded here as observation. **What follows for INV-3 is not yet decided** —
see 10.

| `estimationMethod` | Period | What it appears to be | Trainable |
|---|---|---|---|
| `GENERAL_PURPOSE_ZONE_MODEL` | 2017-01 to ~2020, all five zones | a modelled series, ~4x too smooth at the evening peak | no |
| `MODE_BREAKDOWN` | ~2021 to the measured switch | the fuel-mix breakdown is estimated; the consumption total is not a fill-in | yes |
| `TIME_SLICER_AVERAGE` | the switch boundary, and current unsettled rows | the fill-in INV-3 was written for | no |
| *(none)* — `isEstimated == False` | from the switch | measured | yes |

Row counts by method and zone, over 2017-01-01 to 2026-09-01 (measured
2026-09-08):

| Method | IN-EA | IN-NE | IN-NO | IN-SO | IN-WE |
|---|---|---|---|---|---|
| `GENERAL_PURPOSE_ZONE_MODEL` | 35,035 | 35,064 | 26,280 | 26,280 | 26,280 |
| `MODE_BREAKDOWN` | 26,281 | 33,680 | 42,480 | 42,480 | 42,480 |
| `TIME_SLICER_AVERAGE` | 308 | 289 | 287 | 287 | 287 |
| measured | 23,091 | 15,692 | 15,697 | 15,697 | 15,697 |

**The switch to measured is not simultaneous across zones.** IN-EA goes
measured from around 2024-06; the other four switch on **2024-11-05**, with a
short `TIME_SLICER_AVERAGE` band either side. Anything that assumes one
project-wide settlement date is wrong for IN-EA.

A `TIME_SLICER_AVERAGE` fill-in repeats: the same (hour, weekday) takes an
identical value. Tested on 18-day samples of IN-NO, none of the tiers do.

| Tier | n | distinct | exact repeats | zero hour-to-hour delta | mean abs delta |
|---|---|---|---|---|---|
| 2017-06 `GENERAL_PURPOSE_ZONE_MODEL` | 432 | 420 | 2.8% | 0 | 638 MW |
| 2022-06 `MODE_BREAKDOWN` | 432 | 429 | 0.7% | 1 | 3,798 MW |
| 2025-06 measured | 432 | 427 | 1.2% | 0 | 1,772 MW |

`MODE_BREAKDOWN` is at least as variable as measured data, so its
`powerConsumptionTotal` is not a time-slice average.
`GENERAL_PURPOSE_ZONE_MODEL` is real-looking but **measurably smoother than
reality** — the standard deviation across days at 18:00 IST is 1,610 MW in
2017 against 6,780 MW in 2025 — which is the signature of a model output, and
training on it would teach the forecaster to under-predict variance.

### Open-Meteo

Free, no API key. Archive API for observed history, forecast API for
predictions. **Not yet verified** — history depth unconfirmed.

### Environment

- Development machine: macOS, Homebrew Python. System-wide `pip install` is
  refused (PEP 668). Use the project venv via `make setup`.
- Assistant sandboxes **without network access** block `api.electricitymap.org`
  and `open-meteo.com` at an egress proxy. This is a property of the sandbox, not
  of assistants in general: an assistant running directly on the development
  machine reaches both hosts normally. Verify with a probe rather than assuming
  either way — see the step-0 RULE in section 12. All other work needs no network.

---

## 12. Phase 1 build order

The document says what to build and why. This says in what order, so the
sequence is not inferred.

### Module layout

```
src/
  config.py                 config + secrets                      [exists]
  ingest/
    electricity_maps.py     demand                                [exists]
    weather.py              archive + forecast, kept separate     [exists]
    calendar_in.py          holidays, festivals, IST conversion
  features/
    build.py                THE feature builder. Both training and serving
                            call this and nothing else.
    weather_feats.py        cooling/heating degrees, per-city then aggregate
    quality.py              suppressed-demand detection (INV-8)
  models/
    hybrid.py               Ridge stage + LightGBM stage
    baselines.py            seasonal naive, hour x weekday, ridge-all, per-zone
  backtest/
    splits.py               tuning / walk-forward / holdout boundaries, purge gap
    run.py                  the walk-forward loop
    metrics.py              MAPE, stratified reporting, signed bias
  monitor/
    drift.py                rolling error, bias, trigger evaluation
    registry.py             model versions, champion/challenger gate
  viz/
    plots.py                shared chart code. The backtest report and the
                            dashboard both call this. Never two chart paths.
  validate.py               schema, range, gap and timezone checks on every
                            ingest. Fails loudly and refuses to write (14)
  features/
    forecast_noise.py       the 5d training-time weather noise injection.
                            Applied to raw temperature BEFORE the degree
                            transforms, since max(0, .) is nonlinear
  jobs/
    daily.py                the single daily job, in the canonical order of 5b
scripts/
  backfill.py               one-off history pull                  [exists]
  archive_daily.py          vintage + revision archiving, from step 0c
  ablate.py                 feature-group ablation (5e)
  model_card.py             writes reports/model_card.md - training ranges,
                            per-band degradation, replaced placeholders
  tune.py                   Optuna search on the tuning window
  report.py                 dashboard + backtest report
```

**RULE** `features/build.py` is the only path from raw data to a feature
matrix. Training and serving both call it. Do not write a second feature path
for inference.

*Rationale:* two feature paths is how train/serve skew gets into a system.
When they drift apart the model is served inputs subtly unlike the ones it
learned from, and nothing errors.

### Order

**RULE** Step 0 comes before any code is written. Everything in this document
was specified against data nobody had looked at, and several values in
`config/config.yaml` are placeholders. Build on the real distribution, not on
the assumed one.

```
 0  make weather                 verify Open-Meteo, confirm archive depth
    make backfill                pull and cache all zones, all history
        --> then run the section 13 measurements and replace the
            placeholders BEFORE building features on top of them

0a  Dockerfile + ci.yml          pin the environment and start the invariant
                                 tests BEFORE any result is produced in it
0b  dvc init + remote            artifacts versioned from the first run
0c  scripts/archive_daily.py     START THE ARCHIVE NOW. Weather vintages and
                                 demand revisions are unrecoverable if delayed
                                 (5d), and nothing later can reconstruct them

 1  ingest/calendar_in.py        holidays, festivals, IST conversion
 2  features/quality.py          suppressed-demand detection
 3  features/build.py            the core feature set from 5e
 4  backtest/splits.py           boundaries and purge gap
 5  models/baselines.py          seasonal naive (needs the purge gap from 4)
 6  backtest/metrics.py          MAPE, stratified, signed bias
                                 (MASE/RMSSE denominators need 5)
 7  backtest/run.py              walk-forward, BASELINES ONLY
        --> first milestone: the number the project must beat
 8  models/hybrid.py             Ridge stage, then LightGBM on the residual
 9  backtest/run.py              same folds, now with the model
        --> second milestone: the first honest comparison
10  scripts/tune.py              Optuna on the tuning window, freeze to config
10a RE-RUN step 9                with the frozen parameters. This re-run is the
                                 BACKTEST OF RECORD - every threshold, tolerance
                                 and reported figure derives from it, not from
                                 the untuned step 9
11  monitor/drift.py             thresholds derived from step 9 backtest
12  monitor/registry.py          champion/challenger
13  jobs/daily.py                wire it together
14  scripts/report.py            dashboard + backtest report
15  deploy                       daily.yml + retry.yml + Pages (see 14)
```

**RULE** Do not skip ahead to step 8. A model with no baseline to beat is a
number with no meaning, and the temptation to skip step 7 is exactly why so
many projects have no baseline.

**RULE** Drift thresholds (step 11) are derived from the **step 10a** backtest —
step 9 re-run with frozen hyperparameters — never from the untuned step 9 and
never by hand.

*Rationale:* 5c requires hyperparameters frozen before the walk-forward that
counts, and section 6 disarms the monitor when the threshold's backtest sha does
not match the current model. Deriving thresholds from step 9 and then tuning at
step 10 would change the sha and permanently disarm the monitor on first run.

**RULE** Until `data/raw/demand_revisions/` holds enough history to replay the
settlement frontier, thresholds are calibrated on the fully settled backtest and
recorded as **provisionally optimistic**, per 5g. `settlement_frontier_replay`
stays false until then.

**RULE** Both step-0 commands must be run on a machine with network access to
both API hosts. Verify that access with a probe before assuming it — some
assistant sandboxes are behind an egress proxy that blocks both (see section 11,
Environment) and some are not. Everything after step 0 operates on cached files
and needs no network.

### Milestones

| After step | You have |
|---|---|
| 7 | the baseline number the project exists to beat |
| 9 | the first honest model-versus-baseline comparison |
| 13 | a system that runs itself |
| 15 | a deployed, self-updating forecaster — Phase 1 complete |

---

## 13. Assumptions to replace with measurements

Every value below is a **placeholder standing in for something measurable**.
They exist because the specification was written before the data was pulled.

**RULE** Replace each one with a measured value at the point in the build
where it becomes measurable. Do not carry a placeholder past that point.

**RULE** When a placeholder is replaced, record it on three surfaces, each with
a different job. An assumption that silently became a number is indistinguishable
from a number that was always guessed.

| Surface | Carries |
|---|---|
| this table | the measured value in place of the placeholder, followed by `(measured YYYY-MM-DD)`. Nothing more |
| the commit message | the value, the date and the method, in prose |
| the model card (15, step 15) | every replaced placeholder, and every one still outstanding |

| Config key | Placeholder | How to measure | Measurable after |
|---|---|---|---|
| `features.temp_breakpoint_c` | **21.5 (measured 2026-09-08)** — renamed from `cooling_threshold_c` | RSS-minimising breakpoint of the identified `sloped_below` fit, held-out scored | step 0 |
| `features.heating_threshold_c` | **deleted (2026-09-08)** — no U-shape, so no cold inflection to hold a threshold | — | step 0 |
| `evaluate.temperature_bands_c` | 20/30/40/45 | band occupancy, under the sufficiency rule below | step 0 |
| `splits.purge_gap_days` | 10 | `data/raw/demand_revisions/` — how long until `is_estimated` flips | ~4 weeks of daily runs |
| `drift.settlement_lag_days` | not set | distribution of measured-minus-created age in `data/raw/demand_revisions/`; report median and P95 | ~4 weeks of daily runs |
| `quality.suppression_*` | provisional | inspect flat-topped hot hours against known shedding events | step 0 |
| `train.recency_half_life_days` | 365 | Optuna sweep | step 10 |
| `train.per_zone_sample_weighting` | false | per-zone loss contribution after the log transform | step 9 |
| `drift.thresholds.*` | null | replay sweep against `false_alarm_budget_per_year` — see 6 | step 10a |
| `drift.debounce_days` | 3 | same sweep; threshold and debounce are chosen together | step 10a |
| `drift.cooldown_after_*_days` | 30 / 14 / 14 | window length and observed recovery time in a frozen-model replay | step 10a |
| `drift.watch_threshold` | null | same replay sweep, 7-day windows | step 10a |
| `forecast_noise.day_bias_sigma_c` | 1.2 | archived forecast vintages vs observed: sd of the per-day mean error | ~6 weeks of daily runs |
| `forecast_noise.hour_wobble_sigma_c` | 0.5 | same archive: sd of the within-day residual after removing the day bias | ~6 weeks of daily runs |
| `evaluate.veto_tolerance.*` | not set | fold-to-fold spread of each veto metric in the step 10a backtest | step 10a |
| `train.ridge.alpha`, `train.lightgbm.*` | null | Optuna search on the tuning window | step 10 |
| `failure.max_forecast_vintage_age_hours` | 72 | score each vintage age against actuals; find where it stops beating the no-weather baseline | ~8 weeks of daily runs |
| linear stage feature list | 3 features | experiment: does adding more help? | step 9 |

### Band sufficiency

**RULE** Temperature bands are not chosen against a flat row floor. The top band
is inherently the sparsest and is exactly the band that must stay separate, so a
uniform minimum would merge away the only number that matters.

```
interior bands    >= evaluate.min_band_rows          (default 500)
top band          kept separate regardless of count
any band < 200    reported as "insufficient rows to judge", never as a number
```

*Rationale:* a band reported as 9.8% over n=140 invites a reader to treat it as a
measurement. Saying the rows are insufficient is the honest form of the same
information, and it is the 5f principle-5 position applied to the report itself.

### Measured facts, recorded but not configured

Neither of these is a tunable and neither becomes a config key. The model learns
growth through `trend` and the holiday effect through `is_holiday`; putting a
number for either in config would create a second, unused definition of something
the model already estimates. They are measured because the document quotes them,
and a quoted figure has to come from somewhere.

| Fact | Assumed | How to measure | Measurable after | Recorded in |
|---|---|---|---|---|
| demand growth, % per year | ~5, in 5c | fit a trend on zone totals once history is loaded | step 0 | `reports/step0_measurements.md`, model card |
| `is_holiday` demand effect | 10-20%, in 5e | holiday vs matched non-holiday hours | step 0 | `reports/step0_measurements.md`, model card |

### The two that matter most

**`temp_breakpoint_c`** — every cooling-degree feature, the monotone
constraint and the linear extrapolation stage are all built on it. If the real
elbow is at 27 C and the config says 24, every one of those is subtly wrong
from the first commit onward. **Measure it before writing `features/build.py`.**

**`splits.purge_gap_days`** — currently inferred from a single observed row
(created 24 Aug, updated 26 Aug). If rows settle in four days the gap discards
six days of usable training data in every fold; if they take fourteen, every
backtest number is optimistic and cannot be reproduced in production. Neither
error announces itself.

### Recorded judgement — which estimation tiers are trainable

Decided 2026-09-08. Recorded here because the reasoning is more valuable than
the conclusion, and because the conclusion looks arbitrary without it.

**The problem.** INV-3 as originally written forbade training on
`is_estimated == True`, on the stated ground that such rows carry a
`TIME_SLICER_AVERAGE` fill-in. That premise came from a single observation and
was asserted as fact. Section 11 records that the source uses three estimation
methods; only one is that fill-in. Applying the invariant literally leaves 22
months of trainable history against the 60-month split budget of 5c — 12 tuning
+ 24 minimum initial train + 12 fold months + 12 holdout — so the specified
walk-forward cannot run at all.

**The options, and why B.**

| | Trainable from | Span | Verdict |
|---|---|---|---|
| A — measured only | 2024-11 | 22 mo | Not available. Cannot run the 5c protocol |
| **B — measured + `MODE_BREAKDOWN`** | ~2021-01 | ~68 mo | **Chosen** |
| C — everything but `TIME_SLICER_AVERAGE` | 2017-01 | ~116 mo | Rejected |

C is not a close call. Recency weighting at a 365-day half-life gives 2017 data
roughly 0.2% of today's weight, so C buys almost no effective training signal
while importing data measured to be about four times too smooth at the evening
peak — standard deviation across days at 18:00 IST of 1,610 MW in 2017 against
6,780 MW in 2025. Under-dispersed data is worst exactly where this project
claims to be careful: 5f's extremes and INV-8's suppression detection both
depend on seeing real variance. C trades the project's best argument for
nothing.

**The caveat on that reasoning.** `train.recency_half_life_days` is tuned by
Optuna at step 10. If it comes out much longer than 365 days the
`MODE_BREAKDOWN` era gains weight and this decision becomes more load-bearing.
Flag it if that happens.

**Why provisional.** The case for B rests on `MODE_BREAKDOWN` naming the
fuel-mix breakdown rather than `powerConsumptionTotal`. That is an inference
about someone else's pipeline, and consumption is normally derived from
production plus net imports — which come from the breakdown. If the total is
reconstructed rather than metered, B trains on 45 months of derived numbers.

It is testable, because the switch has a date: at 2024-11-05 the method changes
and the meter does not. Compare 60 days either side for a discontinuity in
level, in hour-to-hour variance and in average daily shape, controlling for
temperature and calendar since November is not October. No material
discontinuity confirms B. A material discontinuity voids it — and then 5c must
be redesigned around the measured-only span, which is the repository owner's
decision.

The test and its result are recorded in `reports/step0_measurements.md` either
way. It is the evidence for the largest judgement call in the project.

**RULE** Any figure quoted in the README, dashboard or model card that depends
on an unreplaced placeholder must say so.

---

## 14. Automation and MLOps

### Two kinds of automation

They need different tools and conflating them is how tool lists get long.

**Kind A — it must happen without me.** The forecast goes out at 10:00 IST
whether or not a laptop is open. This needs a *scheduler*.

**Kind B — it must be repeatable by anyone, later.** Six months on, "why is this
the live model?" has to be answerable, and provable. Nothing is waiting on it.
This needs *versioning and tracking*.

Kind B has no latency requirement, which is why nothing here runs as a service.

### What is automated

**Clock-driven** — archive the weather forecast vintage; archive observed
weather; archive demand revisions; build features and issue the 24-hour
forecast; score forecasts that have reached the settlement frontier; update
rolling error and signed bias; evaluate the three triggers; retrain and run the
promotion gate when one fires; publish the dashboard; the weather-outage retry
loop; the monitor heartbeat alarm. Sources: 5b, 5d, 5g, 5h, 6.

**On demand** — walk-forward backtest; ablation; Optuna search; the section 13
measurements; environment build.

**Continuous** — one test per invariant; ingest validation; the feature contract
test.

### The scheduler

**RULE** The repository is public. GitHub Actions minutes are unlimited and
Pages is free on public repositories; on a private one both are metered.

**RULE** Three workflows, not one.

| File | Schedule | Does |
|---|---|---|
| `daily.yml` | `30 4 * * *` (UTC) = 10:00 IST | the whole daily job |
| `retry.yml` | `*/15 * * * *` | the weather-outage retry of 5h |
| `ci.yml` | on push | invariant tests, contract test, lint |

**RULE** Every scheduled job is idempotent. `retry.yml` reads current state,
exits immediately when the forecast is already fulfilled or the 4-hour window
has closed, and otherwise makes one attempt.

*Rationale:* the naive design is one job that sleeps and polls for four hours.
That occupies a runner, and if the runner dies the retry dies with it. Schedulers
also fire twice occasionally, so a job that is not safe to run twice is a job
that will corrupt state eventually.

**RULE** Cron is UTC. Convert once, in the workflow file, with the IST time in a
comment beside it.

**Known behaviour, not bugs:** scheduled runs can start ten to twenty minutes
late under load — 5h already computes lead time from the actual issue time, so
lateness is measured rather than hidden. Scheduled workflows are disabled after
about 60 days of repository inactivity; the daily job commits state back to the
repository, which counts as activity, so the schedule sustains itself.

**RULE** Secrets live in GitHub Secrets and are referenced by name. INV-6 extends
to CI: never echo a secret, never print a URL containing one, never let a failing
step dump the environment.

### Where state lives

Runners are destroyed after every run, so anything that must survive has to be
written somewhere outside them. Two destinations, split by size and purpose.

**RULE** Small append-only records — daily scores, drift history, the promotion
log, replaced placeholder values — are **committed to `state/` by the daily
job**.

*Rationale:* free, and the git history becomes a day-by-day audit trail of the
system's behaviour, readable with `git log` and available even if every other
tool is broken.

**RULE** Bulk archives — raw API pulls, forecast vintages, training matrices,
model binaries, `mlruns/` — are **DVC-tracked and pushed to the DVC remote**.

**RULE** The daily job runs `dvc push` before it exits. A vintage that exists
only on a destroyed runner is not an archive.

**RULE** A directory under DVC control is ignored by DVC's own generated entry,
never by a hand-written `.gitignore` line as well. A path both hand-ignored and
DVC-tracked fails in confusing ways.

### Kind B — the five pins

A model is explained by code **plus** the data it was fit on, the settings it was
given and the environment it ran in. Change one and the model changes.

| Pin | Mechanism |
|---|---|
| code | git commit sha |
| data | DVC hash of the training matrix |
| settings | `config/config.yaml`, in git — so the git sha covers it |
| environment | Docker image digest |
| randomness | seed, in config like everything else |

*The settings pin costs nothing only because section 8 already requires every
tunable to live in one file. Scattered defaults would need a sixth pin, and it
would be the one people forget.*

**RULE** Every promotion **decision** writes a JSON record to
`state/promotions/` carrying all five pins, the trigger that fired, the outcome,
and the metrics **as computed at decision time**. A promotion commits it together
with the champion pointer move; a rejection or a failed attempt commits it on its
own.

*Rationale:* metrics recomputed later are computed on revised data (5g), so a
recomputed number is a different quantity wearing the same name. Record the
decision's numbers at the decision.

**RULE** State the reproducibility level claimed: a re-run reproduces the
**decision**, and reproduces metrics to three decimal places. Not bit-identical.

*Rationale:* multi-threaded floating-point summation does not always add in the
same order. Claiming bit-identical reproducibility invites an easy refutation. If
a promotion decision can flip on that much noise, the gate is tighter than the
noise floor of the data, which is itself worth discovering.

### Tools

**DVC — data and artifact versioning.** DVC hashes a file, writes a small
pointer file that git tracks, and keeps the bytes in a remote. Git stays small
and a git commit pins data as precisely as it pins code.

**RULE** Use `dvc add` for artifacts. Do not use `dvc repro` or `dvc.yaml`.

*Rationale:* the DVC pipeline DAG is good, but section 8 already makes the
Makefile the entry point and `daily.yml` already fixes the order. Two
orchestrators describing one pipeline drift apart, and then one of them is a lie.

**RULE** The DVC remote is Google Drive. A local-only remote is acceptable
through Phase 1 development; a real remote is required before step 15, because
without one every archive a runner produces is destroyed with the runner.

**MLflow — experiment tracking.** File-backed at `./mlruns`, no server, no
database. Local UI via `mlflow ui` when needed.

**RULE** Log every **production retrain attempt**, including rejected
challengers — not only development experiments. Tag each run with the five pins.

*Rationale:* logging rejections is what makes the store an audit trail of a live
system rather than a notebook by-product. "Why was the March challenger rejected"
is the question that gets asked.

**RULE** Optuna owns the search and its own trial storage. MLflow receives one
run holding the study summary — best params, best value, trial count. Do not log
all trials to both.

**Docker — environment reproducibility.** One Dockerfile, versions pinned,
image published to GHCR, used identically by CI and locally.

**RULE** The Dockerfile is written at step 0a, before results exist.

*Rationale:* retrofitting a pinned environment after nine steps of results means
none of those nine results are reproducible, and nobody goes back to redo them.

**Feature store — the guarantee, not the infrastructure.**

**RULE** Do not adopt Feast or any feature-store service. The property a feature
store exists to provide is delivered by three things already in this design:
INV-9's single feature module; a CI contract test asserting the training and
serving paths produce identical column names, order and dtypes; and the 5d
vintage archive, which is point-in-time correct by construction.

*Rationale:* a feature store buys no train/serve skew, cross-team feature sharing
and low-latency online serving. We have one team and one batch job a day, so two
thirds of it is a registry, an online store and a materialisation service to keep
alive for no gain. The defensible position is that the guarantee was implemented
at the right scale, not that the tool was installed.

**Validation.**

**RULE** `src/validate.py` checks every ingest with plain assertions: expected
columns present, MW within a physically plausible range, no duplicate
timestamps, no unexpected gaps, timezone UTC, `is_estimated` present. Fail loudly
and refuse to write. Do not adopt Great Expectations.

*Rationale:* both APIs can change shape silently, and a renamed column produces a
plausible wrong forecast rather than an error. That is section 9's philosophy
applied to ingest. Great Expectations solves it with a config system, a data
context and a docs site, for checks that are twenty lines here.

**Alerting.**

**RULE** Two layers only: GitHub's workflow-failure notification, and the status
field the dashboard already carries from 5h. No monitoring stack.

**RULE** Anything 5h calls an *alert* exits the workflow **non-zero**, after
writing its status record and publishing. A skip that exits zero notifies nobody.
A degrade exits zero — it produced an honest forecast and said so.

*Rationale:* silent degradation is the enemy, and 5h already makes degradation
visible on the page. Prometheus and Grafana exist for high-frequency service
metrics; one data point a day belongs in a table.

### Rejected

| Tool | Why not |
|---|---|
| Airflow / Prefect | one linear daily job; a scheduler with a database is more machinery than the work |
| Kubernetes | nothing long-running to orchestrate |
| Feast | see above — the guarantee without the service |
| Prometheus / Grafana | daily cadence, not service telemetry |
| FastAPI model server | batch workload; nothing calls it |
| Hosted MLflow / Postgres backend | concurrency and speed we do not need |
| Great Expectations | heavy for twenty lines of assertions |
| Paid cloud | see the cost table |

**RULE** Each rejection above is stated in the README with its reason. A
rejection with a reason is a design decision; a silent omission is a gap.

### Cost

Every component is free and none requires a payment method.

| Component | Terms |
|---|---|
| GitHub Actions | unlimited minutes on public repositories |
| GitHub Pages | free on public repositories |
| GHCR (container registry) | free for public images |
| GitHub Secrets | included |
| DVC | open source; remote on the Google Drive free tier |
| MLflow, Optuna, LightGBM, pytest | open source, run locally |

*GitHub Pro's private-repository Actions allowance is not needed, because the
repository is public.*

### When each piece arrives

| Step (see 12) | Piece |
|---|---|
| 0a | Dockerfile, `ci.yml`, first invariant tests |
| 0b | `dvc init`, remote configured |
| 3 | feature contract test joins CI |
| 9 | MLflow logging on the backtest |
| 10 | Optuna study, summary to MLflow |
| 12 | promotion records, git as registry |
| 13 | `state/` commits from the daily job, `dvc push` |
| 15 | `daily.yml`, `retry.yml`, Pages |

---

## 15. Dashboard

Static HTML plus pre-rendered SVG, generated by `scripts/report.py`, written to
`docs/`, served by GitHub Pages. One page. No server, no framework, no build
step, no live updating, no login.

### The constraint that shapes it

**RULE** The error panels cover only rows that have reached the settlement
frontier. The most recent days carry a forecast but no error, and are drawn as
**pending**, never as zero error or as a perfect fit.

*Rationale:* the page shows `dashboard.history_days` of forecasts and fewer days
of error — the difference is the settlement lag (5g). A dashboard that drew the
unsettled tail as error would state its most visible falsehood in its most
prominent panel, and would look better for it — which is exactly the failure
mode this project exists to argue against. Rendering it as pending is the
visible proof that the settlement rules are implemented rather than merely
written down.

### Layout

Top to bottom, one column.

| Block | Contains | Enforces |
|---|---|---|
| Status strip | zone selector, issue time, weather vintage age, degraded flag, model version | 5h status propagation |
| Headline tiles | MASE, MAPE, signed bias, shortfall count, settled fraction — each with its baseline value beside it | INV-5 |
| Today | 24h forecast curve, seasonal naive as a second line, peak hour and peak MW | 5b |
| Last 10 days | forecast and actual overlaid; beneath it **signed error**, over above the axis and under below; unsettled tail hatched | 5g, settlement lag |
| Where it goes wrong | error by hour of day, by temperature band, by lead time — row counts beside each | 5g stratification |
| Is it drifting | 30-day rolling MAPE and signed bias with **trigger thresholds drawn as lines**; last trigger and last promotion dates | 6 |
| Footer | placeholders still in use, model version, settlement frontier date, generated-at | 13 |

**RULE** Every error figure on the page is displayed with its baseline figure
adjacent. No error number appears alone.

*Rationale:* INV-5 in pixels. The page must not be screenshottable into a claim
that omits what it beat.

**RULE** Every stratified figure is displayed with its row count.

**RULE** Signed error is plotted as a signed quantity around a zero axis, not as
absolute error.

*Rationale:* direction is the operationally meaningful part. Over-forecast means
over-procurement; under-forecast means the grid came up short. Config already
defines `shortfall_threshold_pct`; the header tile reports shortfall hours as a
count out of total, because "6 of 192 hours under by more than 3%" is a more
useful sentence than any average.

**RULE** Drift thresholds are drawn on the rolling charts as reference lines.

*Rationale:* a threshold that is only visible after it fires gives no warning. A
threshold drawn on the chart shows how close the system is to firing.

**RULE** The lead-time error chart is published, not kept internal.

*Rationale:* 5g makes rising error with lead time a leak diagnostic. Publishing
it runs that check every day rather than whenever someone remembers to look.

### Implementation

**RULE** `src/viz/plots.py` is the only chart implementation. `scripts/report.py`
and `backtest/run.py` both call it.

*Rationale:* the charts published must be the charts decisions were made from. A
separate prettier implementation for the public page is one that can disagree
with the evidence and never be caught.

**RULE** Charts are pre-rendered to SVG at build time, one set per zone, toggled
client-side by visibility. No charting library, no data fetching in the browser.

*Rationale:* five zones times a handful of charts is a few hundred kilobytes of
static files. The page then works offline, has no runtime dependency that can
break silently, and needs no build toolchain.

**RULE** Leave vertical room in the Today panel for quantile bands. Phase 1b
adds them; they must not require a redesign.

### Not doing

No map — five zones is a bar chart and a map is decoration. No live updating, no
websockets, no authentication, no interactivity beyond the zone toggle and
hover.
