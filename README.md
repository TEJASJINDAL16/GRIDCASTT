# gridcast

Day-ahead electricity demand forecasting for the Indian grid — hourly, for all
five regional zones, with a model that keeps itself current and refuses an
update that would make it worse.

> **Status: implementation and verification in progress.** The hybrid model,
> monitoring, guarded retraining, batch job and dashboard are implemented locally.
> [The completion audit](reports/completion.md) records which evidence and
> deployment gates have actually passed. The build order, what "done"
> means at each stage, and what is deliberately not built yet are in
> [BUILD_STAGES.md](BUILD_STAGES.md). The specification is
> [PLANNING.md](PLANNING.md).
>
> The twelve-fold baseline comparison, coverage limits and remaining assumptions
> are in [reports/baseline.md](reports/baseline.md). Reproduce it with `make baseline`.
> Eligible observations are retained without speculative cause-based filtering.
>
> **Current measured blocker:** the corrected hybrid fails the development gate
> (mean-fold MASE 1.250, seasonal baseline 1.000). It remains unapproved for deployment.
> See [the gate report](reports/model_gate_status.md). The final holdout remains
> reserved while the required ablations establish the next development decision.

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
prediction = Ridge( temperature, cooling_degrees, trend )
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
over. Raw temperature carries the slope throughout the range; cooling degrees
add the steeper response above the measured breakpoint. Heating degrees were
removed after the pooled U-shaped response failed measurement. These two model
stages belong to Build Stage 3; they are distinct from Build Stage 2's baseline work.

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

The daily archive script captures forecasts with exact issue times. A separate
recovery script retrieves historical forecasts at leads of one to seven days,
with their provenance and uncertain intra-day issue time kept explicit.
Stage 2 uses the configured constant-sigma weather-noise bridge; it does not
present recovered forecasts as exact historical 10:00 IST captures.

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

## Run the pipeline

After restoring the DVC data and running `make setup`, the research sequence is:

```bash
make tune        # reserved pre-test measured validation; two-hour budget
make model       # frozen twelve-fold comparison
make ablate      # feature removals and estimation-tier comparisons
make calibrate   # alarm-budget sweep, injected-drift delay, promotion gate
make report      # dashboard; pending values remain pending
make holdout     # final evaluation once; refuses a second run
make train       # saves a champion only if the selection gate passed
make model-card
make audit
```

`make daily` captures weather and demand, freezes newly settled scores, monitors,
attempts a gated retrain when warranted, forecasts the next day and publishes
the dashboard. `make retry` performs one eligible weather retry. Neither loops
or sleeps. `make daily ARGS="--offline --at 2026-11-04T04:30:00Z"` uses cached
vintages; it cannot invent a forecast for a date absent from that archive.

Keep the frozen research input snapshots when reproducing the reports. The
initial data-derived boundaries are saved in `reports/research_protocol.json`;
later cache refreshes cannot silently move the holdout. `make catch-up ARGS="--start YYYY-MM-DD"`
repairs a missing range by merging it, preserving old
history and recording the actual retrieval time.

## Deployment and recovery

The archive retains its 04:30 UTC schedule until an approved champion records a
published GHCR image reference in `pins.image_digest`. The image workflow tests
the image before publishing it and emits the immutable reference as an artifact.
Set `runtime.image_digest` to that full `ghcr.io/...@sha256:...` reference before
fitting the release artifact. The daily workflow then uses that exact image;
the archive becomes a manual repair path. GitHub Pages must serve `main:/docs`.

Both workflows require the four secrets documented in BUILD_STAGES: the
Electricity Maps key and the three Google Drive OAuth values. Authentication is
consumed through the normal configuration/DVC paths, never printed. A Drive
`invalid_grant` requires renewed owner authentication; retrying expired
credentials does not repair it. A failed remote upload must not publish new DVC
pointers. Retry and failure records remain separate from successful forecasts.

The live acceptance gate is three actual consecutive successful daily runs,
durable DVC backups, a published container and a working public dashboard.
Offline tests and replay do not substitute for those checks. Later quantile and
regional-model experiments remain gated on a working Phase 1 service.

## Tools deliberately omitted

| Tool | Reason |
|---|---|
| Airflow / Prefect | One linear daily batch does not need a scheduler database. |
| Kubernetes | There is no continuously running service to orchestrate. |
| Feast | One shared feature builder supplies the training/serving contract. |
| Prometheus / Grafana | Daily records and charts cover this monitoring cadence. |
| FastAPI model server | Forecasts are generated in a batch; there is no request API. |
| Hosted MLflow / Postgres | The local file store is sufficient for single-writer jobs. |
| Great Expectations | Direct validators enforce the small, explicit data contract. |
| Paid cloud | GitHub Actions, Pages and the configured Drive remote cover Phase 1. |
