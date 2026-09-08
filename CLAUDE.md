# gridcast — instructions for any agent working here

## What this is

**gridcast** is a day-ahead electricity demand forecasting service for the Indian
grid. It predicts demand hour by hour for the next 24 hours across five zones
(IN-NO, IN-WE, IN-SO, IN-EA, IN-NE) from weather, calendar and time signals, and
keeps itself correct after deployment — monitoring for drift, retraining only
when the data says to, and refusing an update that would make it worse. The
forecast is the product; the system that keeps the forecast honest is the point.
It is **mid-build**: Stage 1 of 5 is complete, Stage 2 is next.

## Read order and authority

1. **`PLANNING.md`** — read it **in full** before touching anything. ~2,400 lines.
2. **`BUILD_STAGES.md`** — what to build now, what "done" means.

`PLANNING.md` is **the law**. `BUILD_STAGES.md` is **the work order**. Where they
disagree, PLANNING wins and the disagreement is a bug in BUILD_STAGES — **report
it, do not resolve it yourself.**

Lines beginning **RULE** are binding. Do not violate them and do not improve on
them. Section 9's **INV-1 … INV-9** are the invariants whose breach produces a
plausible number that is wrong, with no error message.

Work on **exactly one stage at a time**. Do not start work belonging to a later
stage, even when it looks trivial or convenient.

## Stop and ask — do not decide these alone

- Anything listed in **PLANNING section 10** (open decisions).
- Any value **section 13** lists as a measurement, while it is still unmeasured.
- Any **conflict between two RULEs**.
- Any case where **a stated premise turns out to be false** — see below.
- Anything requiring a **credential, an account, or a repository setting**.
- Anything that would change **committed architecture** in PLANNING.

An invented decision that looks reasonable is worse than a blocked task, because
nobody notices it was invented.

## When a premise turns out to be false

**This has happened four times in Stage 1 and it is the single most valuable
behaviour in this project.**

| Premise | Asserted | Measured |
|---|---|---|
| INV-3's rationale | `is_estimated` means a `TIME_SLICER_AVERAGE` fill-in | three estimation methods, not equivalent |
| The U-shape | demand is U-shaped in temperature | not identified on any grid; monotone increasing |
| Settlement lag | 10 days, from one observed row | still unmeasured; the archive is accruing it |
| Heating load | a structural requirement of the architecture | no pooled cold-side rise; real in IN-NE only |

Each was asserted from plausible physics. Each was wrong. Each would have
produced a confident wrong number rather than an error.

**When measurement contradicts the specification: stop. Report the measurement
and what it invalidates. Propose a fix. Wait.** Do not patch around it, do not
weaken the claim so it survives, and do not proceed on the assumption that the
spec must have meant something else.

## Secrets — INV-6

The Electricity Maps key is in `.env`. The DVC OAuth client is in
`.dvc/config.local`. The Google Drive token is in
`~/Library/Caches/pydrive2fs/<client-id>/default.json`.

**Never read any of them, never print any of them, never copy a value into
another file, never echo an environment in a workflow step.** Pass them through
`src/config.py`, which is the only module that reads secrets. Verifying a key
works means checking a response status, not looking at the key.

## Git

- **A branch per build stage.** Commits per logical unit.
- **Messages in prose**, saying what changed and *why*, with the evidence where
  a claim is made. A one-line message loses the reasoning, and the reasoning is
  the thing worth keeping.
- **PR into `main` at the end of each stage. Never merge — the owner merges.**
- **Never squash.** The commit history is the audit trail and section 14 depends
  on it.
- `gh` is **not installed**. Use `git` plus the GitHub API; a token can be
  obtained via `git credential fill` without ever printing it.

## Environment

- **Python 3.12 explicitly**, never bare `python3` (which is 3.14 here and lacks
  wheels). `make setup` from a clean clone builds the venv and checks
  prerequisites.
- **macOS: LightGBM needs `brew install libomp`.** Without it `import lightgbm`
  fails at `dlopen`, not at install — invisible until something trains. On Linux
  the equivalent is `libgomp1`, installed in the image.
- **The DVC remote is Google Drive**, already configured and verified. Bulk data
  is DVC-tracked; `state/` is committed to git.
- **The archive workflow runs daily at 04:30 UTC = 10:00 IST from `main`.**
- Every entry point is a Makefile target. `make help` lists them.
- There is **no `timeout` command** on this macOS. Run long jobs in the
  background instead.

## Where things are remembered

| Surface | Holds |
|---|---|
| `PLANNING.md` | the rules and the reasoning |
| `config/config.yaml` | the numbers, each annotated with the date it was measured |
| git history | the decision as it was taken |
| `reports/` | the evidence a decision was taken on |
| chat | **nothing that matters** |

**If a decision is not in one of the first four, it did not happen.** Chat is
compacted and lost.

---

# Things learned the hard way in Stage 1

Not in either document. Written down because each one cost real time or nearly
produced a wrong number.

## The archive is the one thing with a deadline

Weather forecast vintages and demand revisions are **unrecoverable if delayed**.
Open-Meteo serves observed history and the current forecast, never what the
forecast said on a past date. If the archive workflow is broken, fixing it is
more urgent than whatever else is in progress.

Vintage rows with `lead_time_hours <= 0` describe hours that had already elapsed
at issue time. They are archived for completeness and are **not forecasts** —
using one as a feature is leakage under INV-1. Always filter on lead time.

## Statistical honesty rules that earned their place

- **A grid search that returns a grid boundary has not measured anything.**
  Report `NOT IDENTIFIED` and widen the grid. Two estimators returned boundaries
  in Stage 1 and both looked like findings.
- **Calibrate step tests against placebo boundaries, not t-statistics.** Hourly
  demand residuals are nothing like independent. A naive test gave IN-NE a −52%
  step at t = −19.4; against its own placebo band it was ordinary wandering.
- **Report row counts beside every figure.** A band with 25 rows is reported as
  "insufficient rows to judge", never as a number, and never gates a promotion.
- **Validate before writing.** A frame that reaches disk is one every later step
  trusts. `src/validate.py` refuses the write; that is the point of it.
- **Test the premise, not just the estimator.** When a fit misbehaves, ask
  whether the shape you assumed exists.

## API facts (measured — do not re-derive)

- **Electricity Maps**: 10 days maximum per `past-range` call at hourly
  granularity; a longer window returns 4xx, `fetch_range` swallows it, and the
  backfill completes having written nothing. Rate limit 2400 requests / 60s —
  not a constraint. History starts 2017-01.
- **Open-Meteo**: prices a request by the *volume* returned, not the count. One
  multi-year request over eight variables gets 429'd on its own. Chunk by
  calendar year and back off on 429.
- Both store timestamps **UTC**. Convert to IST once, downstream, where calendar
  features are extracted. India is UTC+5:30, so a naive timestamp read as UTC
  mislabels the weekday on the first hour of every forecast day.

## Tooling traps

- `dvc push` **with nothing tracked is a no-op that never authenticates**, so the
  OAuth token does not appear until the first push that has bytes to upload.
- The `dvc[gdrive]` dependency chain does **not** resolve to a working set on its
  own; the pins in `requirements.txt` are load-bearing and `pip check` is clean
  only at those versions.
- A directory under DVC control is ignored by **DVC's own generated entry**,
  never by a hand-written `.gitignore` line as well (PLANNING 14). Both together
  fail confusingly.
- **pandas 3.0**: assigning `None` into a bool column raises `LossySetitemError`;
  and a `Series` with a `RangeIndex` combined against a `DatetimeIndex` frame
  silently produces all-NaN. The second one made a test pass for the wrong
  reason.
- Output piped through `tail` is block-buffered, so a long background job looks
  hung when it is fine.

## Project-specific rules easy to miss

- **Nothing may import from `scripts/measure_step0.py`.** It is throwaway
  analysis. Anything worth keeping is rewritten into the proper module.
- **`quality.trainable_estimation_methods`** is the allowlist INV-3 keys on, and
  **`quality.trainable_from`** carries per-zone start dates. The trainable span
  is the effect of those two — it is *not* `demand.backfill_start`, which is a
  **cache** boundary.
- **`demand.backfill_start` (2017-01-01) never moves.** It is `trend`'s origin,
  and every LightGBM split on `trend` is an absolute number. Changing it
  invalidates every derived threshold and the champion itself.
- The hot temperature bands are **essentially Delhi-only**. Three zones have no
  rows at all above 40 C, so zone-by-band tables have empty cells by
  construction — render them as absent, not as zero error.
