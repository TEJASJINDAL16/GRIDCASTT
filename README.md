# gridcast

Day-ahead electricity demand forecasting for the Indian grid — hourly, for every
day, with a model that keeps itself current.

> **Status:** early setup. Data sources being verified.

---

## What this is

Electricity cannot be stored at grid scale. Whatever the country consumes at
3 PM must be generated at 3 PM, so grid operators schedule generation a day
ahead against a forecast. When that forecast is wrong they either buy power on
the spot market at spike prices, or shed load.

`gridcast` forecasts the next 24 hours of demand, hour by hour, from weather and
calendar signals — and, more importantly, **keeps working after deployment**:
retraining nightly, watching itself for drift, and refusing an update that would
make it worse.

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| Target | hourly demand, next 24h, day-ahead | matches how dispatch actually works |
| Weather inputs | **forecast** weather, never actuals | training on actuals you would not have had at prediction time is leakage |
| Validation | walk-forward backtest | a random train/test split trains on the future to predict the past |
| Baseline | seasonal naive — same hour, same weekday, last week | strong for electricity; the claim of this project is the gap above it |
| Metrics | MAPE, peak-hour MAPE, signed bias | peak drives capacity; signed bias is the drift early-warning |
| Granularity | regional aggregate | the operator schedules against the aggregate, and aggregation smooths noise |

## Architecture

Two stages:

1. **Base model** — trained across regions, learns the universal demand response
   (the AC elbow above ~24 °C, the evening peak, weekday vs Sunday, thermal inertia).
2. **Regional correction** — per-region model trained on the base model's
   *residuals*. Learns only what is special about that region, which is a much
   smaller thing to learn from limited data.

Final forecast = base + correction.

## Data sources

| What | Source | Notes |
|---|---|---|
| Demand | [Electricity Maps](https://www.electricitymaps.com/) | zones `IN-NO`, `IN-WE`, `IN-SO`, `IN-EA`, `IN-NE` |
| Weather | [Open-Meteo](https://open-meteo.com/) | archive for history, forecast API for live operation |

Electricity data provided by **Electricity Maps**, used under an academic
licence for non-commercial research.

## Setup

```bash
make setup                    # creates .venv and installs dependencies
cp .env.example .env          # then paste your Electricity Maps key into .env
```

`.env` is gitignored. The key never enters the repository.

macOS ships a Homebrew-managed Python that refuses system-wide installs
(PEP 668). `make setup` builds a project-local virtual environment instead,
so nothing touches the system Python.

## Verify the data sources

```bash
make weather    # Open-Meteo — no key needed
make em         # Electricity Maps — needs .env
```

To run scripts directly, activate the environment first:

```bash
source .venv/bin/activate
python scripts/check_weather.py
```

## Layout

```
config/     config.yaml — every tunable lives here, no magic numbers in code
src/        ingest, features, models
scripts/    one-off checks and backfills
data/       raw and interim (gitignored)
reports/    backtest output, charts
```

## Note on cached history

The Electricity Maps academic licence has an expiry date. Historical data is
pulled once and cached to disk early, so training data, backtests and every
chart survive the key lapsing. Only the live nightly update depends on the API
staying available.
