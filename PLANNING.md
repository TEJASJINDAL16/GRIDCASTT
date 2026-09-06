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
at issue time, but the ~9 day revision lag means that anchor is still
estimated. It would bake a dependency on unsettled data into the target
definition itself. Note this does not affect the Phase 2 regional correction
layer, whose residual is taken from the base model's prediction, not from a
lagged actual.

**RULE** One daily job at issue time performs, in order: score settled
forecasts, update drift metrics, evaluate triggers, retrain if triggered,
issue the forecast, publish.

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
prediction = Ridge( cooling_degrees, heating_degrees, trend )
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
| `cooling_degrees` | yes — record heat | **yes** |
| `heating_degrees` | yes — record cold | **yes** |
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
as long as the model runs. With demand growing around 5% a year, a model
trained on four years and predicting the fifth lands roughly 11% low — on
every hour, always in the same direction.

A line keeps rising. That is the entire reason the linear stage exists.

#### Why the linear stage cannot distort normal conditions

```
cooling_degrees = max(0, T - 24)     zero for all T <= 24
heating_degrees = max(0, 15 - T)     zero for all T >= 15
```

Between 15 C and 24 C **both are zero**, so the temperature part of Stage 1
contributes nothing but its intercept. All variation in the comfortable band
comes from LightGBM.

The linear component is dormant in the common case and only speaks when
temperature genuinely matters. That is why the `max(0, ...)` form is used
rather than raw temperature.

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

**RULE** Apply monotone increasing constraints on `cooling_degrees` and
`heating_degrees` in the LightGBM stage.

*More heat cannot mean less cooling load. With few examples above 45 C an
unconstrained model fits noise and can produce a physically impossible dip.
This is only possible because temperature is split into two one-sided terms —
demand is U-shaped in raw temperature, so monotonicity cannot be declared on
it.*

**RULE** Correct the retransformation bias when inverting the log.
`exp(mean(log x))` understates `mean(x)`.

#### Two different Ridge models — do not confuse them

| | Features | Purpose |
|---|---|---|
| **Hybrid Stage 1** | 3: cooling, heating, trend | carry what must extrapolate |
| **Ridge baseline** | all engineered features | answer "could a simple model have done this?" |

Same algorithm, different feature sets, different jobs.

*Note on the hybrid Stage 1: with three uncorrelated features on ~175,000
rows the L2 penalty barely binds, so it is close to plain least squares. Ridge
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

**RULE** Search with Optuna, of the order of 100 trials. Log every trial to
MLflow — parameters, score, duration.

*Optuna learns which regions of the space are promising and samples there,
converging faster than random search, which in turn beats grid search per unit
of compute. All three are affordable because training takes seconds.*

**RULE** Tune the project parameters, not only the model ones. These are
likely to matter more:

| Parameter | What it controls |
|---|---|
| `recency_half_life_days` | how fast old data loses influence |
| `cooling_threshold_c` | where the elbow actually sits — measure it, do not assume 24 |
| number of piecewise cooling breakpoints | one straight ramp vs a bending curve |
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

**RULE** Within a test fold, train once at the fold boundary and issue daily
forecasts across the month without retraining.

*Rationale:* this is what the deployed system does — retraining is triggered
and rare. Retraining daily inside a fold would measure a system nobody is
going to run.

**RULE** Purge gap: training data within each fold ends **10 days before** the
fold's test period begins.

*Rationale:* rows settle from estimated to measured after roughly nine days,
and INV-3 forbids training on estimated rows. So at any real issue time the
newest usable training row is about ten days old. A backtest without this gap
trains on data that would not have existed at decision time — the error is
invisible and it inflates every result. This is the single easiest way to
produce a backtest number that cannot be reproduced in production.

**RULE** Early stopping: hold out the last 8 weeks of each fold's training
window as a validation set to select the iteration count, then refit on the
full training window using that count.

*The validation slice is the most recent part of training, never a random
sample.*

**RULE** Filter to measured rows before splitting, not after.

**RULE** The seasonal-naive baseline is defined as: *the most recent measured
value for the same hour and same weekday, at least `purge_gap_days` before the
issue time.*

*Rationale:* "same hour last week" is ambiguous under a settlement lag — last
week's value may still be estimated at issue time, and INV-4 forbids using it.
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
| `temperature` | tree | Open-Meteo | the dominant driver |
| `cooling_degrees` | **linear** + tree | `max(0, T - cooling_threshold_c)` | see below — kept for three reasons, none of which is helping the tree |
| `heating_degrees` | **linear** + tree | `max(0, heating_threshold_c - T)` | the other half of the temperature decomposition — see below |
| `trend` | **linear** + tree | days since start | year-on-year growth; without it the model targets the multi-year average and runs 5-7% low |
| `zone` | tree | data column, native categorical | five pooled series; without it the model predicts an average of five and matches none |

**RULE** Features marked `linear + tree` are passed to **both** stages. The
Ridge stage sees only those three; LightGBM sees everything.

**RULE** `heating_degrees` is not optional, even though heating load is small
across most of India.

*Rationale:* it is not an independent driver — it is the other half of the
temperature decomposition. Demand is U-shaped in raw temperature, so
temperature must be split into two one-sided terms before either the monotone
constraint or the linear extrapolation stage is possible at all. Omitting it
leaves cold extremes with no extrapolation path and the constraint only half
applied. It is a structural requirement of the architecture, not a judgement
about Indian winters.

**RULE** Everything else is a measured candidate, added one at a time and kept
only if the ablation shows it earning its place. Candidates: humidity, dew
point, apparent temperature, rolling temperatures (24h/72h/168h), consecutive
hot days, cloud cover, shortwave radiation, wind at 100m, precipitation,
festival proximity, cricket match days, explicit interactions.

**RULE** No demand lag features in Phase 1.

*Rationale:* lead time is 14-38h, so `t-24h` does not exist for later target
hours, and anything under about ten days old is still estimated. A model that
uses no recent demand and still beats seasonal naive has proved its weather
relationship is real, rather than being a persistence model in disguise.

A consequence worth stating rather than leaving implicit: the forecast path
therefore has no dependency on the demand API at issue time. See the settlement
lag rules in 5g.

### Why `cooling_degrees` stays despite being redundant for trees

It is a deterministic function of a column already present, so a tree can
reconstruct it by splitting. It carries no new information. It is kept for
three reasons:

1. **The Ridge baseline needs it.** Ridge on raw temperature fits one straight
   line through an elbow and is wrong at both ends. Comparing against a
   crippled baseline proves nothing.
2. **It enables the monotone constraint.** Demand is U-shaped in raw
   temperature — rising in heat and in cold — so monotonicity cannot be
   declared on it. Split into cooling and heating degrees and each is
   individually monotone.
3. **The extrapolation component is built on it.** The linear term that keeps
   rising past the training range has to be a term in something, and raw
   temperature will not serve.

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

**RULE** Compute `cooling_degrees` per city, then aggregate to the zone. Never
average temperature first and transform after.

*Rationale:* the transform is nonlinear, so the transform of the average is not
the average of the transforms. Delhi at 40 C and Shimla at 20 C average to
30 C giving 6 cooling degrees, where the correct weighted answer is nearer 13.
The error is largest on the hottest days, which is exactly where it matters
most.

**RULE** `gen_solar_mw` is not a feature. It is analysis material only — the
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
figure is 2.6% and the failure is invisible. An average cannot show you a
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
continues rising. Flag them, and exclude or downweight them in training.

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
are not repeated here: the Ridge stage carries what must extrapolate, and
monotone constraints let physics overrule sparse evidence where data is thin
rather than absent.

The point to carry forward is the reasoning, not the mechanism: **when a new
situation arises outside the data, the answer is to supply structure the model
cannot learn — never to trust it to generalise on its own.**

---

### Principle 4 — When you do not know, say so, and lean the safe way

Two separate obligations.

**RULE** When an input exceeds the training range, flag the forecast as
extrapolating, widen its uncertainty band, and surface both on the dashboard.

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
1  FEATURE        cooling_degrees = 48 - 24 = 24
                  training maximum was 22          <- outside the data

2  RIDGE          45,000 + 800 x 24 = 64,200 MW
                  the line does not care that 24 is unprecedented

3  TREE           seeks a split above cooling_degrees 22, finds none,
                  falls back to its top bin
                  contributes +1,100 MW (evening, weekday, June)

4  PREDICTION     65,300 MW

                  for comparison: a tree alone would say ~62,000 MW,
                  flat above its top split - 3,300 MW low, silently

5  RANGE CHECK    24 > 22  ->  flag EXTRAPOLATING

6  UNCERTAINTY    band widened from +/-2% to +/-6%

7  DASHBOARD      shown with a warning marker, not as a normal number

8  MONOTONICITY   constraint guaranteed the tree contribution could not
                  be negative here

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

VETO if:     worse in the top temperature band
             signed bias outside threshold
             shortfall frequency increased
             P95 absolute percentage error regressed

TIEBREAK     fold win rate, then simplicity

DIAGNOSTIC   RMSE/MAE ratio, reported alongside
```

*Rationale for the co-primary:* MASE is built on mean **absolute** error,
which is linear and therefore treats errors as interchangeable regardless of
size. Ten 200 MW misses and one 1,100 MW miss give the same MAE and the same
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
| Signed bias | mean(p-a) | direction, not accuracy | says nothing about magnitude |
| Shortfall frequency | % hours p < a by more than `shortfall_threshold_pct` | operational risk in the dangerous direction | ignores over-forecast |
| P95 abs % error | 95th percentile of \|a-p\|/a | how bad it gets, not how bad on average | tail only |
| Peak error | error on the day's maximum | capacity is booked against peak | one hour per day |
| Ramp error | \|delta_a - delta_p\| per hour | shape rather than level | noisier by construction |
| Ramp MASE | ramp error / baseline ramp error | makes ramp error interpretable | — |

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
today. It is a fixed-width window that lags the present.

*Rationale:* a window ending at today holds roughly 28 days of scorable rows, not
30, and on a slow settlement day holds 25. Sample size would then move with
pipeline health rather than with model quality, and a rolling metric whose
denominator wobbles is not measuring what its name says.

**RULE** Score every settled row. Do not wait for a day to complete. Report
**settled fraction** alongside every monitoring figure, exactly as row counts are
reported alongside every evaluation figure.

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
often than designed, and section 6 already names the consequence: a trigger that
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
it cannot see the two most recent days because those measurements do not exist yet.
There is no fix. "Detects shocks" and "detects shocks about three days after they
begin, because that is when meter data settles" are different claims, and only the
second survives a follow-up question.

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
| **Fewer than 24 hourly values produced** | Skip publication entirely. Never publish a partial day. |
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
flags: [climatology_fallback]    heavily degraded
flags: [extrapolating]           input outside training range (5f)
flags: [placeholder_in_use]      a config assumption is unreplaced (13)
```

**RULE** Flags propagate to the dashboard and into the stored forecast record.
A flagged forecast is visually distinct from a clean one.

**RULE** Flagged rows are excluded from headline accuracy figures and reported
separately. A model should not be blamed for a climatology fallback, nor
credited for one.

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

**RULE** The nightly job is a **monitoring** job. Retraining is one action it
may choose to take. It is not a retraining schedule.

Every night, unconditionally:
1. Fetch the previous day's actuals
2. Score forecasts whose rows have settled to measured
3. Update rolling error and signed bias
4. Publish the dashboard
5. Evaluate trigger conditions

**RULE** Retrain only when a trigger fires:

| Trigger | Condition | Catches |
|---|---|---|
| Rolling error | 30-day MAPE leaves the backtest-established band | Obvious degradation |
| Signed bias | Error consistently one-directional beyond threshold | Concept drift, earlier than raw error |
| Structural break | Sharp single-day deviation | Shocks — heatwave, lockdown, grid event |

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

**RULE** Log every trigger event with which condition fired.

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
| `data/raw/` | cached API pulls (gitignored) |
| `data/interim/` | derived datasets (gitignored) |
| `reports/` | backtest output, logs, charts |
| `state/` | committed append-only records: scores, drift history, promotion log |
| `models/` | champion pointer (`.dvc`), promotion records |
| `mlruns/` | MLflow file store (DVC-tracked) |
| `tests/` | one test per invariant, plus the feature contract test |
| `.github/workflows/` | `daily.yml`, `retry.yml`, `ci.yml` (see 14) |
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

**INV-3 — Never train on estimated rows.** Rows with `is_estimated == True`
carry a `TIME_SLICER_AVERAGE` fill-in, not a measurement. Training on them
teaches the model to reproduce an average.

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

- Milestones and timeline

---

## 11. Verified facts

Established by direct probe. Do not re-derive or guess.

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
| History depth | at least 4 years; probe did not reach the limit |
| Zones | `IN-NO`, `IN-WE`, `IN-SO`, `IN-EA`, `IN-NE`, plus `IN` |
| Estimation flags | `isEstimated` (bool), `estimationMethod` (string) |
| Revision behaviour | rows published as estimates are overwritten with measured values days later; visible as `updatedAt` > `createdAt` |
| Licence | academic, non-commercial. **Attribution to Electricity Maps required in published work.** Expires 2027-03-04 |

*Because the licence expires, historical data is cached to disk early. Every
downstream step reads the cache, so training, backtests and charts survive the
key lapsing. Only the live nightly update depends on the API.*

### Open-Meteo

Free, no API key. Archive API for observed history, forecast API for
predictions. **Not yet verified** — history depth unconfirmed.

### Environment

- Development machine: macOS, Homebrew Python. System-wide `pip install` is
  refused (PEP 668). Use the project venv via `make setup`.
- Both sandboxes available to the assistant block `api.electricitymap.org` and
  `open-meteo.com` at an egress proxy. Any command hitting those APIs must be
  run by the repository owner. All other work can be done by the assistant
  directly.

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
  jobs/
    daily.py                the single daily job (see 5b)
scripts/
  backfill.py               one-off history pull                  [exists]
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

 1  ingest/calendar_in.py        holidays, festivals, IST conversion
 2  features/quality.py          suppressed-demand detection
 3  features/build.py            the core feature set from 5e
 4  backtest/metrics.py          MAPE, stratified, signed bias
 5  models/baselines.py          seasonal naive first
 6  backtest/splits.py           boundaries and purge gap
 7  backtest/run.py              walk-forward, BASELINES ONLY
        --> first milestone: the number the project must beat
 8  models/hybrid.py             Ridge stage, then LightGBM on the residual
 9  backtest/run.py              same folds, now with the model
        --> second milestone: the first honest comparison
10  scripts/tune.py              Optuna on the tuning window, freeze to config
11  monitor/drift.py             thresholds derived from step 9 backtest
12  monitor/registry.py          champion/challenger
13  jobs/daily.py                wire it together
14  scripts/report.py            dashboard + backtest report
15  deploy                       daily.yml + retry.yml + Pages (see 14)
```

**RULE** Do not skip ahead to step 8. A model with no baseline to beat is a
number with no meaning, and the temptation to skip step 7 is exactly why so
many projects have no baseline.

**RULE** Drift thresholds (step 11) are derived from the step 9 backtest error
distribution. They are not chosen by hand.

**RULE** Both step-0 commands must be run by the repository owner, not by an
assistant. Both API hosts are blocked at the egress proxy in the assistant
sandboxes (see section 11, Environment). Everything after step 0 operates on
cached files and needs no network.

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

**RULE** When a placeholder is replaced, record the measured value, the date,
and how it was obtained — in the commit message and in the model card. An
assumption that silently became a number is indistinguishable from a number
that was always guessed.

| Config key | Placeholder | How to measure | Measurable after |
|---|---|---|---|
| `features.cooling_threshold_c` | 24.0 | plot demand against temperature, find where the slope changes | step 0 |
| `features.heating_threshold_c` | 15.0 | same plot, the cold-side inflection | step 0 |
| `evaluate.temperature_bands_c` | 20/30/40/45 | choose so each band holds enough rows to report on | step 0 |
| `splits.purge_gap_days` | 10 | `data/raw/demand_revisions/` — how long until `is_estimated` flips | ~4 weeks of daily runs |
| `drift.settlement_lag_days` | not set | distribution of measured-minus-created age in `data/raw/demand_revisions/`; report median and P95 | ~4 weeks of daily runs |
| `quality.suppression_*` | provisional | inspect flat-topped hot hours against known shedding events | step 0 |
| `train.recency_half_life_days` | 365 | Optuna sweep | step 10 |
| `train.per_zone_sample_weighting` | false | per-zone loss contribution after the log transform | step 9 |
| `drift.*` thresholds | not set | the step 9 backtest error distribution | step 9 |
| `forecast_error_sigma` | not set | archived forecast vintages vs observed | ~6 weeks of daily runs |
| `failure.max_forecast_vintage_age_hours` | 72 | score each vintage age against actuals; find where it stops beating the no-weather baseline | ~8 weeks of daily runs |
| linear stage feature list | 3 features | experiment: does adding more help? | step 9 |

### The two that matter most

**`cooling_threshold_c`** — every cooling-degree feature, the monotone
constraint and the linear extrapolation stage are all built on it. If the real
elbow is at 27 C and the config says 24, every one of those is subtly wrong
from the first commit onward. **Measure it before writing `features/build.py`.**

**`splits.purge_gap_days`** — currently inferred from a single observed row
(created 24 Aug, updated 26 Aug). If rows settle in four days the gap discards
six days of usable training data in every fold; if they take fourteen, every
backtest number is optimistic and cannot be reproduced in production. Neither
error announces itself.

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

### Kind B — the four pins

A model is explained by code **plus** the data it was fit on, the settings it was
given and the environment it ran in. Change one and the model changes.

| Pin | Mechanism |
|---|---|
| code | git commit sha |
| data | DVC hash of the training matrix |
| settings | `config/config.yaml`, in git — so the git sha covers it |
| environment | Docker image digest |
| randomness | seed, in config like everything else |

*The settings pin is free only because section 8 already requires every tunable
to live in one file. Scattered defaults would need a fifth pin, and it would be
the one people forget.*

**RULE** Every promotion writes a JSON promotion record to `state/promotions/`
carrying all four pins, the trigger that fired, and the metrics **as computed at
decision time**. It is committed in the same commit that moves the champion
pointer.

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
challengers — not only development experiments. Tag each run with the four pins.

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

*Rationale:* the page shows ten days of forecasts and roughly eight days of
error, because meter data settles late (5g). A dashboard that drew the
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
