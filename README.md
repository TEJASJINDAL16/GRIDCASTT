# gridcast

Day-ahead electricity demand forecasting for the Indian grid — hourly, for all
five regional zones, with a model that keeps itself current and refuses an
update that would make it worse.

> **Status: under construction.** Stage 1 of 5. The build order, what "done"
> means at each stage, and what is deliberately not built yet are in
> [BUILD_STAGES.md](BUILD_STAGES.md). The specification is
> [PLANNING.md](PLANNING.md).
>
> No performance numbers are published yet. There will be none until there is a
> baseline to compare them against.

---

## The problem

Electricity cannot be stored at grid scale. Whatever a region consumes at 15:00
must be generated at 15:00, so operators schedule generation a day ahead
against a forecast. Error costs money in both directions: under-forecast and
power is bought on the spot market at spike prices, or load is shed;
over-forecast and plants are paid to burn fuel for power nobody used. In India
the Deviation Settlement Mechanism prices the gap daily.

Underneath that sits a slower problem. Demand **drifts** — air-conditioning
spreads, rooftop solar reshapes the daytime curve, EV charging adds night load.
A forecaster trained once and left alone never crashes and never errors. It
just stops being right.

The forecast is the product. The system that keeps the forecast honest is the
point.

## What it forecasts

| | |
|---|---|
| Target | hourly demand in MW, absolute level |
| Zones | IN-NO, IN-WE, IN-SO, IN-EA, IN-NE |
| Horizon | 24 hours covering the next IST calendar day |
| Issue time | 10:00 IST, so lead time is 14–38 hours |
| Method | direct multi-step — every target hour predicted independently, never recursively |

## Architecture

One pooled model across all five zones, with `zone` as a native categorical
feature. Trained on `log(demand)`, which makes a 10% swing the same size in
IN-NO at 55 GW and IN-NE at a fraction of that — so one fitted coefficient is
correct for every zone, and the optimiser stops trading away small-zone
accuracy for negligible large-zone gains.

It is a two-stage hybrid, everywhere and in all conditions:

```
prediction = Ridge( cooling_degrees, heating_degrees, trend )
           + LightGBM( all features, fitted on the residual )
           then exp() back to megawatts, with a Duan smearing correction
```

**Stage 1, Ridge** carries only what must extrapolate. A feature belongs here
only if it can take values outside the training range. `trend` always can, by
definition — every forecast is outside the training range in the time
dimension, and the gap widens for as long as the model runs. A tree asked to
predict beyond its last split falls into its top bin and predicts the final
training period's level permanently. A line keeps rising.

**Stage 2, LightGBM** carries everything else — daily shape, weekday effects,
holidays, zone differences, interactions — fitted on what the linear stage left
over. Between 15 °C and 24 °C both degree-day terms are zero, so the linear
component is dormant in the common case and only speaks when temperature
genuinely matters.

## Retraining

**Not on a schedule.** The daily job is a monitoring job; retraining is one
action it may choose to take. The drivers of drift here — AC penetration, solar
buildout, EV load, economic growth — move over years, so a nightly or monthly
cadence would be out of proportion to the physics, and every retrain is a
chance to ship something worse.

Three triggers, all with thresholds derived from a replay sweep against a
false-alarm budget rather than chosen by hand: 30-day rolling MAPE, 30-day
rolling signed bias, and a single-day structural break. A trigger authorises an
*attempt*, not a deployment — promotion stays gated on a champion/challenger
comparison, and a challenger that loses is the gate working.

## Baseline

**Seasonal naive**, defined as *the most recent measured value for the same
hour and the same weekday, at least `purge_gap_days` before the issue time*.

Not simply "last week". Demand rows are published as estimates and revised to
measured some days later, so last week's value may still be an estimate at
issue time — and a baseline built on a row the model is not allowed to see is
not under the same information constraint as the model. A baseline allowed to
see data the model cannot is not a fair comparison, and it is exactly the sort
of detail that quietly makes a model look better than it is.

Three more baselines ship alongside it: hour × weekday historical mean, Ridge
on all engineered features, and a per-zone model — which settles whether
pooling helps at all, at no extra cost, since the backtest is running anyway.

## Data sources

| What | Source | Key |
|---|---|---|
| Demand | [Electricity Maps](https://www.electricitymaps.com/), `powerConsumptionTotal` | yes, academic licence |
| Weather | [Open-Meteo](https://open-meteo.com/) — archive for history, forecast for prediction time | no |
| Holidays | `holidays` package, Indian state subdivisions, plus a hand-maintained festival list | no |

Weather forecast vintages are archived daily from the first day of the project.
Open-Meteo serves observed history and the current forecast, but never what the
forecast said on a past date — so without an archive the model trains on
perfect temperature and is deployed on approximate temperature, and learns to
trust it more than it should. That gap cannot be closed retroactively.

Electricity data provided by **Electricity Maps**, used under an academic
licence for non-commercial research.

## Setup

```bash
make setup
```

Builds a Python 3.12 virtual environment from pinned dependencies. On macOS
LightGBM also needs `brew install libomp`; `make setup` checks and tells you.

```bash
cp .env.example .env
```

Then add your Electricity Maps key. `.env` is gitignored and the key never
enters the repository.

```bash
make help          # every entry point
make test          # the invariant tests
```

## Layout

```
config/config.yaml   every tunable — no magic numbers in code
src/ingest/          one module per external source
src/                 features, models, backtest, monitor, viz
scripts/             entry points, all exposed as Makefile targets
data/raw/            cached API pulls and archives (DVC-tracked)
state/               committed append-only records — the audit trail
reports/             backtest output, measurements, model card
tests/               one test per invariant, plus the feature contract test
```

## Note on cached history

The Electricity Maps academic licence expires 2027-03-04. History is pulled
once and cached to disk early, and every downstream step reads the cache — so
training data, backtests and every published figure survive the key lapsing.
Only the live daily update depends on the API remaining available.
