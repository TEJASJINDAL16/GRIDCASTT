# Model refinement: learning from the baseline

Research checkpoint: 2026-11-04. The original hybrid remains unapproved. These
are development comparisons, not final holdout results or a live deployment.

## What changed in the approach

The old model tried to reconstruct demand level from weather, time and region.
The seasonal baseline already knew a region's recent demand level. We asked:
can we keep that useful anchor and improve its reliability before building a
more complicated model?

The new research scope permits demand-history features and alternative
architectures. The implementation uses measured observations at or before issue
time minus the existing ten-day availability gap. It does not use yesterday's
final demand: we cannot demonstrate that this would have been available.
Matching hours have the same zone, IST hour and weekday as the target.

## Experiment 1: average two or four comparable observations

Intuition: one old reading can be unusually high or low. Averaging several
comparable readings may reduce that noise. The trade-off is slower response to
changes in demand level. This is a hypothesis, not an established causal account.

Tools: pandas/NumPy history lookups, the existing chronological split plan and
metric implementation. We replayed the exact 35,033 measured rows used by the
original model comparison. Every reproduced seasonal prediction was checked
against the stored baseline. Nothing was dropped to give a candidate easier rows.

The two-observation average reduced mean-fold MASE from 1.000 to 0.965187 and
RMSSE from 1.000 to 0.966340. Pooled MAPE fell from 11.788892% to 11.304090%.
It won 7 of 12 months and cleared the existing diagnostic promotion checks,
including the highest reportable temperature band. Shortfall frequency did
increase from 40.56% to 41.12%, inside the existing tolerance; this is not a win
on every metric. Peak and ramp errors improved on the common evaluation rows.

The four-observation average had mean-fold MASE 1.003436, so it failed the
primary criterion even though pooled MAPE improved. This is why the project
keeps a fixed selection metric instead of choosing whichever headline looks best.

## Experiment 2: let a tree correct the seasonal anchor

We fitted LightGBM to log(actual demand / seasonal prediction), using calendar,
weather, temperature change from the source hour, source age, and relative
historical demand levels. Fixed settings: 200 trees, 15 leaves, learning rate
0.03, minimum leaf size 100 and L2 penalty 10. These are explicit experimental
settings, not a new optimal-parameter claim. Only earlier measured targets train
the correction. With insufficient training rows it uses the seasonal baseline.

This gave mean-fold MASE 1.076901 and RMSSE 1.072411, both worse than the
baseline. Its pooled MAPE was 12.771664%. We rejected it. The experiment does
not prove why it lost; limited measured history, changing regional coverage and
transfer between weather/demand regimes remain plausible explanations to test.
It does establish that this particular learned correction did not earn its cost.

## An uncomfortable validation finding

Before looking at the new fold results, the existing reserved early validation
window selected the four-observation average: MASE 0.974024 versus 0.981568 for
two observations and 1.368417 for the learned correction. That validation has
only 2,184 measured rows, all from the Eastern zone. Its winner did not win the
later multi-zone comparison. Early validation was too narrow to establish a
universal choice. We have preserved that selection in protocol.json rather than
rewriting it to claim the two-observation choice was selected beforehand.

## Experiment 3: choose the window from recent earlier data

After observing the first experiment, we added a chronological adaptive
alternative. At each monthly boundary it selects one, two or four matching
observations separately per zone using eight weeks of earlier measured targets.
The validation slice ends at the purged training boundary. Scarce history falls
back to one observation. The selected windows are recorded for every fold.

Mean-fold MASE was 0.987779 and RMSSE 0.988930. It cleared the diagnostic gate,
but won only 5 of 12 months and was weaker overall than the simple two-reading
average. The added adaptation did not justify preferring it in this comparison.
This was a follow-up development experiment, not a new untouched test.

## What we can responsibly say now

We have implemented a simple time-series candidate that beats the seasonal
baseline on the existing development comparison. SeasonalAverage is reusable;
DemandHistory is shared by the candidates and enforces the source cutoff.
Missing history remains explicitly missing. Distinct future observations cannot
change earlier lookups, and estimated observations cannot supply their values.

The two-reading candidate is now a promising development choice, not a production
champion. Choosing it after comparing development results introduces selection
optimism. At that checkpoint the final holdout was still unscored; its frozen one-time evaluation is recorded below. Historical demand still uses revised
values with an assumed availability gap; it is not a complete first-publication
replay. Weather inputs retain the original simulated-forecast limitation.

A demand-history model also changes the serving dependency: live prediction now
requires a usable demand cache. The original weather-only failure policy and its
monitoring thresholds cannot simply be inherited without new verification.
Production integration, fresh monitoring calibration and guarded final evaluation
must precede activation. No production pointer or dashboard accuracy claim changed.

## Verification and reproduction

Run `make refine-model` for the research comparison. Inputs are the existing
cache, frozen research protocol and original prediction cohort. Configuration is
under `refinement` in config/config.yaml. Fold scores, summary, stratification,
selection results and adaptive choices are under reports/refinement. The first
experiment's reports are retained under reports/refinement_initial. Prediction
rows are DVC-tracked at data/interim/refinement_predictions.parquet.

New regression checks verify estimated/future observations cannot affect history,
missing-history handling and the adaptive fallback. The full suite exposed an
older real-cache test that sampled the last 2,000 demand and weather rows
independently. Their cache endpoints differ, so only 808 timestamps overlapped.
The test now samples 2,000 common hours and checks the exact joined count; the
feature implementation did not need to change.

Final verification: 195 tests passed; Ruff passed. The prediction artifact is
tracked in local DVC. Upload initially failed with Google Drive OAuth `invalid_client`. After importing
the Desktop OAuth client JSON through src/config.py and completing fresh browser
authorization, the DVC upload succeeded. The refinement prediction artifact is
backed up remotely. The downloaded credential JSON is ignored by Git.

## Frozen final-year evaluation - 2026-11-04

The two-observation rule was frozen before the one-time reserved-year evaluation
requested after development. No alternatives were compared on this year and no
model settings were changed using its result. The evaluator claims the shared
holdout marker before scoring and refuses subsequent reruns.

September 2025-August 2026 covers 43,800 expected zone-hours. All had feature
coverage; 512 unmeasured targets were excluded from both sides, leaving 43,288
matched measured rows. Candidate MAPE was 7.688134% versus 7.985172%; MAE was
2,946.924506 MW versus 3,120.156810 MW; RMSE was 4,467.592545 MW versus
4,757.146796 MW. Mean-month MASE was 0.957086 and RMSSE 0.955590, versus one
for the baseline. The candidate won 9 of 12 months.

The result is not uniform. Northeast MAPE rose from 11.483082% to 11.496437%.
Overall shortfall frequency rose from 40.230549% to 40.549344%. Signed bias was
-0.141649% versus -0.116788%. Peak, ramp and P95 absolute percentage errors
improved. Existing diagnostic checks passed, but production approval remains
false: demand-dependent serving and fresh monitoring calibration still need to
be verified before activation. The year is now consumed and must not be reused
as an untouched test during further model refinement.

Full metrics and coverage are in reports/holdout_history; the prediction
artifact is DVC-tracked and uploaded to Drive. Linux reproduced 38 saved
metric values to three decimals, without reissuing or selecting forecasts.
