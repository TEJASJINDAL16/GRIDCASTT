# gridcast — Build Stages

> **This document is the work order. `PLANNING.md` is the law.**
> `PLANNING.md` says what is true and what is forbidden. This document says what
> to build now, what "done" means, and when you may move on.

---

## 0. How to use this document

**RULE** Read `PLANNING.md` in full before touching this file. Nothing here
overrides anything there. Where they appear to disagree, `PLANNING.md` wins and
the disagreement is a bug in this document — report it, do not resolve it
yourself.

**RULE** Work on exactly one stage at a time. Do not begin work belonging to a
later stage, even when it looks trivial or convenient.

**RULE** A stage is complete only when **every** box in its Deliverables list is
ticked and its Exit Gate is satisfied and evidenced. Tick a box only when the
thing exists and has been run — not when it has been written.

**RULE** When a stage completes, append an entry to the Stage Log at the bottom:
date, commit sha, and one line per deliverable saying how it was verified. Then
stop and report. Do not start the next stage without being told to.

**RULE** Before starting any stage, read its **Requires from the human** section
and confirm every item is in place. If one is missing, stop and ask. Do not work
around a missing credential, and never invent, hardcode or commit one.

**RULE** Every stage ends with the invariant tests green. A stage that leaves a
test red is not complete.

### Naming — do not confuse these

| Term | Means |
|---|---|
| **Build Stage 1-5** (this doc) | the order of construction |
| **Phase 1 / 1b / 2** (`PLANNING.md`) | product scope: the complete loop, then quantiles, then architecture experiments |

All five build stages below deliver `PLANNING.md`'s **Phase 1**.

---

## Status

| Stage | Name | State |
|---|---|---|
| 1 | Foundation and Measurement | NOT STARTED |
| 2 | Features and the Baseline | BLOCKED — needs stage 1 |
| 3 | Model and Tuning | BLOCKED — needs stage 2 |
| 4 | Monitoring, Registry, Daily Job | BLOCKED — needs stage 3 |
| 5 | Dashboard, Deploy, Evidence | BLOCKED — needs stage 4 |

Update the State column as you go: `NOT STARTED` -> `IN PROGRESS` -> `COMPLETE (sha)`.

---

# Stage 1 — Foundation and Measurement

**Goal.** A reproducible environment, the real data on disk, the archive
running, and every step-0 assumption in `PLANNING.md` section 13 replaced by a
measured number.

**Why first.** Section 12 is explicit: the entire document was specified against
data nobody had looked at. `cooling_threshold_c` alone underpins every
cooling-degree feature, the monotone constraint and the linear extrapolation
stage. Building features on a guessed elbow makes every later number wrong in a
way nothing downstream can detect.

### Requires from the human

- `EM_API_KEY` present in `.env` (gitignored, chmod 600)
- Network access to `api.electricitymap.org` and `open-meteo.com`
- Docker installed and running
- The GitHub repo created, **public**, with push access working
- **DVC remote: Google Drive, OAuth route.** The folder is already created and
  its ID is **`1Mrc2dxh8Ds5Q-GsyaSb-7ctaP6maH6be`**. Configure with
  `dvc remote add -d gdrive gdrive://1Mrc2dxh8Ds5Q-GsyaSb-7ctaP6maH6be`;
  the first `dvc push` opens a browser once and caches a token in
  `.dvc/tmp/gdrive-user-credentials.json` (gitignored). Do **not** use a service
  account — service accounts have no Drive storage quota of their own and the
  upload fails. If `dvc push` returns a rate-limit error, that is DVC's shared
  OAuth app being throttled globally, not a problem with this repo; the fix is a
  personal OAuth client ID, and you should ask before setting one up.

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `Dockerfile` | pinned environment, published to GHCR | 14, step 0a |
| `.github/workflows/ci.yml` | invariant tests on every push | 14 |
| `tests/` | one test per invariant that is testable without a model | 9, 14 |
| `src/validate.py` | schema, range, gap, timezone checks on every ingest | 14 |
| `scripts/archive_daily.py` | weather vintages + demand revisions | 5d, step 0c |
| `scripts/measure_step0.py` | produces the measurements report | 13 |
| `.dvc/`, DVC remote | artifact versioning | 14, step 0b |

Then run the two data pulls (`make weather`, `make backfill`) and the
measurement script.

### Deliverables

- [ ] `make setup` works from a clean clone
- [ ] Docker image builds; CI runs green on push
- [ ] `dvc init` done, remote configured, `dvc push` succeeds
- [ ] `data/raw/` populated for all five zones over the full available history
- [ ] `src/validate.py` passes on the pulled data, and **fails** on a
      deliberately corrupted copy (prove the check works)
- [ ] `scripts/archive_daily.py` runs and writes a first weather vintage and a
      first demand-revision snapshot
- [ ] `reports/step0_measurements.md` exists, with plots, covering:
      demand vs temperature (the elbow), the cold-side inflection, band
      occupancy, candidate suppressed-demand hours, year-on-year growth,
      holiday vs matched non-holiday demand
- [ ] `config/config.yaml` updated with the **measured** values for
      `features.cooling_threshold_c`, `features.heating_threshold_c`,
      `evaluate.temperature_bands_c`, `quality.suppression_*`
- [ ] `PLANNING.md` section 13 rows for those keys marked replaced, each with
      the measured value, the date and the method — in the commit message

### Exit gate

No step-0 placeholder remains anywhere in config. CI is green. `dvc push`
succeeds. At least one archive file exists on disk. The measurements report
shows the elbow and states where it is.

### Do not do in this stage

No feature engineering, no baseline, no model, no metrics module. If the elbow
turns out to sit somewhere surprising, report it — do not adjust anything else
to accommodate it.

---

# Stage 2 — Features and the Baseline

**Goal.** The feature pipeline, and the number the project exists to beat.

**Why before any model.** Section 12: *"A model with no baseline to beat is a
number with no meaning."*

### Requires from the human

Nothing new. Stage 1 complete.

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `src/ingest/calendar_in.py` | holidays, festivals, IST conversion | 5e |
| `src/features/quality.py` | suppressed-demand detection (INV-8) | 5f P2 |
| `src/features/weather_feats.py` | cooling/heating degrees, per city then aggregate | 5e |
| `src/features/forecast_noise.py` | training-time weather noise, applied to raw temperature **before** the degree transforms | 5d |
| `src/features/build.py` | THE feature builder. Training and serving both call this | INV-9 |
| `src/backtest/splits.py` | tuning window, folds, purge gap, holdout | 5c |
| `src/models/baselines.py` | seasonal naive, hour x weekday, ridge-all, per-zone | 5c |
| `src/backtest/metrics.py` | MAPE, MASE, RMSSE, stratified reporting, signed bias | 5g |
| `src/backtest/run.py` | the walk-forward loop — **baselines only** | 5c |
| `tests/` | INV-1..9 plus the train/serve feature contract test | 9, 14 |

Build in that order: splits before baselines (the baseline needs the purge gap),
baselines before metrics (MASE and RMSSE denominators are the baseline).

### Deliverables

- [ ] `features/build.py` is the only path from raw data to a feature matrix
- [ ] Contract test green: training and serving paths emit identical column
      names, order and dtypes
- [ ] Every invariant INV-1..INV-9 has a test, and all are green
- [ ] `reports/baseline.md`: all four baselines scored across the twelve
      walk-forward folds
- [ ] Every figure in it stratified by temperature band, hour, zone, day type
      and lead time, **with row counts**
- [ ] The headline baseline number recorded explicitly as the number to beat
- [ ] Error rises with lead time — or, if it does not, a written investigation
      of the suspected leak (5g makes this mandatory)

### Exit gate

`reports/baseline.md` exists and states the number to beat. All invariant tests
green. The lead-time check passed or was investigated in writing.

### Do not do in this stage

No hybrid model. No tuning. No drift code.

---

# Stage 3 — Model and Tuning

**Goal.** The Ridge + LightGBM hybrid, tuned, with a backtest of record.

### Requires from the human

Nothing new.

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `src/models/hybrid.py` | Ridge stage, then LightGBM on the residual | 5c |
| `src/backtest/run.py` | same folds, now with the model | 5c |
| `scripts/ablate.py` | feature-group ablation | 5e |
| `scripts/tune.py` | Optuna on the reserved tuning window (INV-7) | 5c |
| — | **then re-run the backtest** with frozen parameters (step 10a) | 12 |

MLflow logging arrives here: file-backed, no server.

### Deliverables

- [ ] Hybrid implemented as specified: Ridge on the three linear-stage features,
      LightGBM on the residual, log target, Duan smearing on inversion
- [ ] Backtest across twelve folds, model vs every baseline
- [ ] `reports/ablation.md`: one feature group removed at a time, including
      `cooling_degrees`, reported honestly either way
- [ ] Optuna search run on the tuning window **only**, parameters frozen into
      `config/config.yaml`
- [ ] **Backtest of record**: the re-run with frozen parameters. Its git sha
      written to `drift.thresholds_backtest_sha`
- [ ] MLflow runs logged with all five pins
- [ ] `reports/model.md`: MASE and RMSSE per fold, with the baseline alongside

### Exit gate

MASE below 1 across folds. No regression against the baseline on any veto
metric. Ablation run and reported. The backtest of record exists and its sha is
in config.

### Do not do in this stage

Do not touch the holdout. Do not derive drift thresholds yet — they come from
the backtest of record, in stage 4.

---

# Stage 4 — Monitoring, Registry, Daily Job

**Goal.** The self-updating loop, proven by replay before it ever runs live.

### Requires from the human

Nothing new.

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `src/monitor/drift.py` | rolling metrics, threshold derivation, routing, triggers, cooldowns | 6 |
| `src/monitor/registry.py` | champion/challenger gate, promotion decision records | 6, 14 |
| `src/jobs/daily.py` | the daily job, in the canonical seven-step order | 5b |

Threshold derivation is the substantial piece: replay the monitor across the
backtest of record, sweep threshold against debounce, count **episodes**, keep
what fits `false_alarm_budget_per_year`, then break ties by injected-drift
detection delay.

### Deliverables

- [ ] Thresholds derived by the sweep, not chosen — with the sweep table saved
- [ ] `reports/threshold_derivation.md`: the episode counts per combination and
      the injected-drift detection table
- [ ] `settlement_frontier_replay` handled honestly: if the revision archive is
      too young, calibrate on the settled backtest and record the thresholds as
      provisionally optimistic
- [ ] Routing implemented: data drift vs concept drift, suppression, failed
      validation, low settled fraction
- [ ] Cooldowns implemented for all three outcomes: promotion, rejection, failure
- [ ] Post-promotion watch implemented and able to escalate inside a cooldown
- [ ] Champion/challenger gate with tolerances, not bare inequalities
- [ ] Promotion decision records written for **every** outcome
- [ ] `jobs/daily.py` runs end to end offline for a chosen historical date
- [ ] Idempotency proven: run it twice for the same date, show no double-write,
      no double-score, no double-counted trigger
- [ ] A historical replay exercising the full path: trigger -> routing ->
      cooldown -> retrain -> gate -> promotion

### Exit gate

The replay produces no more false alarms than the budget allows. The idempotency
proof exists. All invariant tests green.

### Do not do in this stage

No deployment. No dashboard beyond what the replay needs.

---

# Stage 5 — Dashboard, Deploy, Evidence

**Goal.** It runs itself, in public, and the claims are provable.

### Requires from the human

- GitHub Secrets set: `EM_API_KEY`, and `GDRIVE_CREDENTIALS_DATA` — the contents
  of `.dvc/tmp/gdrive-user-credentials.json`, which DVC reads from that
  environment variable in CI
- GitHub Pages enabled on the repo
- Confirmation that the repo is public

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `src/viz/plots.py` | the only chart implementation, shared with the backtest | 15 |
| `scripts/report.py` | builds `docs/` | 15 |
| `.github/workflows/daily.yml` | the daily job, 04:30 UTC | 14 |
| `.github/workflows/retry.yml` | the weather-outage retry, idempotent | 5h, 14 |
| `scripts/model_card.py` | `reports/model_card.md` | 5f, 13 |
| `README.md` | including the rejected-tools list with reasons | 14 |

### Deliverables

- [ ] Dashboard built to `docs/`, all seven blocks of section 15
- [ ] Unsettled tail rendered as pending — never as zero error
- [ ] No error figure anywhere on the page without its baseline beside it
- [ ] Trigger thresholds drawn on the rolling charts
- [ ] Lead-time chart published
- [ ] Pages serving the dashboard
- [ ] `daily.yml` and `retry.yml` live; three consecutive successful daily runs
- [ ] `state/` commits appearing from the daily job; `dvc push` running in it
- [ ] **Holdout evaluated once**, and reported alongside the baseline
- [ ] `reports/model_card.md`: training ranges, per-band degradation, every
      placeholder still unreplaced
- [ ] README states each rejected tool and why

### Exit gate

Three consecutive green daily runs. Dashboard live and correct. Holdout number
reported. Model card lists remaining placeholders honestly.

---

## Stage Log

*Append one entry per completed stage. Do not edit earlier entries.*

```
(empty)
```
