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
| 1 | Foundation and Measurement | IN PROGRESS |
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
- Network access to `api.electricitymap.org` and `open-meteo.com` **from the
  machine the pulls run on**. Probe before assuming — see `PLANNING.md` 11 and 12
- Docker installed and running
- **Python 3.12** available. `make setup` builds the venv from 3.12 explicitly,
  never from bare `python3`, and the Dockerfile pins the same version
- The GitHub repo created, **public**, with push access working
- **GitHub Actions enabled** on the repo
- **Workflow permissions set to "Read and write"** (Settings -> Actions ->
  General). Moved here from stage 5, where it was originally listed, because
  the archive workflow below runs from stage 1 and commits its status record to
  `state/`. `PLANNING.md` 5h makes writing that record a RULE, and a record
  destroyed with the runner has not been written. The same setting later lets
  the daily job commit `state/` back, which is both the git audit trail of
  section 14 and the repository activity that keeps a scheduled workflow from
  being disabled after 60 days. This is not scope creep: without it the stage-1
  archive workflow cannot satisfy a rule it is subject to
- **GitHub Secrets set now, not at stage 5** — `EM_API_KEY`,
  `GDRIVE_CREDENTIALS_DATA`, `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`. The
  archive workflow below runs from stage 1 and needs all four. See that
  deliverable for why it cannot wait
- **DVC remote: Google Drive, OAuth route.** The folder is already created and
  its ID is **`1Mrc2dxh8Ds5Q-GsyaSb-7ctaP6maH6be`**. Configure with
  `dvc remote add -d gdrive gdrive://1Mrc2dxh8Ds5Q-GsyaSb-7ctaP6maH6be`;
  the first `dvc push` that actually has bytes to upload opens a browser once
  and caches a token. **That token is not at `.dvc/tmp/gdrive-user-credentials.json`** —
  that path applied to earlier DVC versions and does not exist here. This
  version caches it under the pydrive2fs application cache directory, keyed by
  OAuth client id: on macOS,
  `~/Library/Caches/pydrive2fs/<client-id>/default.json`. Note also that
  `dvc push` with nothing tracked is a no-op that never authenticates, so the
  token appears only after the first real push. Do **not** use a service
  account — service accounts have no Drive storage quota of their own and the
  upload fails. A **personal OAuth client** is configured in `.dvc/config.local`,
  which avoids the global throttling of DVC's shared OAuth app. That file is
  gitignored, so CI needs the client id and secret as GitHub Secrets

### Build

| Path | Purpose | PLANNING ref |
|---|---|---|
| `Dockerfile` | pinned environment, published to GHCR | 14, step 0a |
| `.github/workflows/ci.yml` | invariant tests on every push | 14 |
| `tests/` | one test per invariant that is testable without a model | 9, 14 |
| `src/validate.py` | schema, range, gap, timezone checks on every ingest | 14 |
| `scripts/archive_daily.py` | weather vintages + demand revisions | 5d, step 0c |
| `scripts/backfill_weather.py` | cache Open-Meteo **archive** history for every zone point | 5a |
| `scripts/measure_step0.py` | produces the measurements report | 13 |
| `.github/workflows/archive.yml` | archive-only scheduler, from stage 1 | 5d, 14 |
| `.dvc/`, DVC remote | artifact versioning | 14, step 0b |

`backfill_weather.py` is a **sibling** of `backfill.py`, not an extension of it.
INV-1 is enforced structurally by keeping the archive and forecast paths apart,
and that separation is kept visible at the script level too.

*Why `backfill_weather.py` exists at all:* `PLANNING.md` 5a requires all three
sources cached to disk and treated as the source of truth, but `make weather`
only probes Open-Meteo and writes nothing, and `make backfill` covers demand
alone. Nothing built the weather cache. Every step-0 measurement needs demand
joined to temperature, so the stage cannot complete without it.

Then run the data pulls (`make weather`, `make backfill`, `make backfill-weather`)
and the measurement script.

### Deliverables

- [ ] `make setup` works from a clean clone, building the venv from Python 3.12
- [ ] Docker image builds; CI runs green on the stage-1 PR
- [ ] `dvc init` done, remote configured, `dvc push` succeeds
- [ ] Electricity Maps history depth **probed**, `demand.backfill_start` set to
      the true earliest available data rather than a guessed date. If the origin
      moves, say so in the report — `trend` is defined from that date
- [ ] EM rate-limit headers read on the first response and reported: what the
      academic licence actually allows
- [ ] `data/raw/` populated for all five zones over the full available history
- [ ] `data/raw/` weather archive cached for every zone point over the same span
- [ ] `src/validate.py` passes on the pulled data, and **fails** on a
      deliberately corrupted copy (prove the check works)
- [ ] `scripts/archive_daily.py` runs and writes a first weather vintage and a
      first demand-revision snapshot
- [ ] **`.github/workflows/archive.yml` live and green** — archive and
      `dvc push`, nothing else
- [ ] `reports/step0_measurements.md` exists, with plots, covering:
      demand vs temperature (the elbow), the cold-side inflection, band
      occupancy, candidate suppressed-demand hours, year-on-year growth,
      holiday vs matched non-holiday demand
- [ ] The elbow fitted by the method below, **both ways**, both numbers reported
- [ ] Per-zone elbows reported as evidence. If they spread by more than about
      2 C, say so plainly — that is phase 2 evidence for a per-zone map, not a
      phase 1 change
- [ ] `config/config.yaml` updated with the **measured** values for
      `features.cooling_threshold_c`, `features.heating_threshold_c`,
      `evaluate.temperature_bands_c`, `quality.suppression_*`, plus
      `evaluate.min_band_rows: 500`
- [ ] `PLANNING.md` section 13 table cells updated to the measured value followed
      by `(measured YYYY-MM-DD)`; value, date and method in the commit message
- [ ] `README.md` rewritten to match the shipped design — see below

### How the elbow is measured

**RULE** A raw scatter of demand against temperature conflates the temperature
response with the daily cycle. Demand is high at 20:00 and low at 04:00 for
reasons unrelated to temperature, and temperature is itself strongly correlated
with hour, so a naive fit recovers an elbow that is partly an artefact of when
hot hours happen.

```
two-segment fit on log(demand), breakpoint by RSS-minimising grid search,
pooled across zones, WITH hour-of-day and day-of-week fixed effects
   — equivalently: remove the hour x weekday means first, fit on the residual

run it BOTH ways once — naive and adjusted — and report both numbers.
if they differ materially, that difference is itself the finding.
```

Pooled scalar is confirmed for phase 1; the config schema does not change. Same
method for `heating_threshold_c`.

### Why the archive workflow cannot wait for stage 5

`PLANNING.md` 5d: weather forecast vintages and demand revisions are
**unrecoverable if delayed**. Three section 13 placeholders — `purge_gap_days`
(~4 weeks), `forecast_noise.*` (~6 weeks), `max_forecast_vintage_age_hours`
(~8 weeks) — become measurable only by accumulating daily runs, and stages 2
through 4 take longer than that. A laptop scheduler silently misses every day the
machine is asleep, and a missed day is a vintage that cannot be reconstructed.

The workflow does the archive and `dvc push` and **nothing else**. It is not
`daily.yml`, which still arrives at stage 5 with scoring, triggers, retraining
and publication. This is the one sanctioned piece of working ahead in stage 1.

### The README rewrite

The committed `README.md` contradicts `PLANNING.md` in three places, on a public
repo: it describes the phase 2 base-plus-regional-correction architecture as
though it were shipping, it says the model retrains **nightly** where section 6
forbids any calendar schedule, and it defines the baseline as "last week" where
5c requires the most recent **measured** matching hour. A public repo describing
an architecture we rejected is worse than no README.

Replace it now with something short and accurate: what the project forecasts, the
actual Ridge + LightGBM hybrid, trigger-based retraining stated explicitly as not
nightly, the 5c baseline definition, and a line saying the project is under
construction pointing at this document. The full README with the rejected-tools
list still lands at stage 5.

### Exit gate

No step-0 placeholder remains anywhere in config. CI is green. `dvc push`
succeeds. At least one archive file exists on disk. The measurements report
shows the elbow and states where it is.

### Do not do in this stage

No feature engineering, no baseline, no model, no metrics module. If the elbow
turns out to sit somewhere surprising, report it — do not adjust anything else
to accommodate it.

**RULE** Nothing may ever import from `scripts/measure_step0.py`. It does holiday
lookup and suppression detection ad hoc, using the `holidays` package directly,
because `src/ingest/calendar_in.py` and `src/features/quality.py` are stage 2
deliverables. It is throwaway analysis. If a function in it proves worth keeping,
it is **rewritten** into the proper module in stage 2, never imported across.

*Rationale:* an import edge from a module to a throwaway script is how the
throwaway script becomes load-bearing without anyone deciding that it should.

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

**RULE** The tuning run has a wall-clock budget of **2 hours**. Time one trial
first, project the total, and if the projection exceeds the budget reduce
`tuning.n_trials` and report what it was reduced to and why. Do not run it
overnight and do not silently exceed the budget.

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
- [ ] **Estimation-tier ablation** — train on the option-B span (measured plus
      `MODE_BREAKDOWN`) and on the measured-only span, score both on the **same
      measured folds**, and report the difference. The measured-only span
      cannot support the full twelve-fold protocol, so run a reduced comparison
      — fewer folds, shorter initial train — and say so explicitly in the
      report

*Why this deliverable exists:* it converts "training on `MODE_BREAKDOWN` data
did not hurt" from an assumption into a measurement. `PLANNING.md` 13 records
that decision as a judgement with evidence; this is the number that settles it.
It is also the first question a sceptical reader asks, and having the answer
ready is worth one extra backtest run.

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

- GitHub Secrets set — all four are already required from stage 1 for the
  archive workflow, and are listed again here because stage 5 is where the full
  daily job depends on them:

  | Secret | Contents | If missing |
  |---|---|---|
  | `EM_API_KEY` | the Electricity Maps key | no scoring, no revision archive |
  | `GDRIVE_CREDENTIALS_DATA` | contents of `~/Library/Caches/pydrive2fs/<client-id>/default.json` — **not** the `.dvc/tmp/` path documented for older DVC, which does not exist here | `dvc push` fails; every archive a runner produces dies with the runner |
  | `GDRIVE_CLIENT_ID` | the personal OAuth client id from `.dvc/config.local` | CI **silently** falls back to DVC's shared OAuth app, which is throttled globally |
  | `GDRIVE_CLIENT_SECRET` | the matching secret | as above |

  The client id and secret are needed because `.dvc/config.local` is gitignored
  under INV-6, so the runner has no copy of the personal client and no error
  announces the fallback.

- **Workflow permissions set to "Read and write"** — already required from
  stage 1 for the archive workflow's status record; restated here because this
  is where the daily job depends on it to commit `state/` back
- **GitHub Pages enabled**, source = branch `main`, folder `/docs`
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
- [ ] Pages serving the dashboard from `main` `/docs`
- [ ] **Electricity Maps attribution in the dashboard footer** — the academic
      licence requires attribution in published work (`PLANNING.md` 11)
- [ ] Docker image built **and pushed** to GHCR, per section 14
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
