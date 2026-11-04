# Implementation Decisions

Technical decisions and validation findings recorded on 2026-11-04.
The earlier suspected-demand-suppression rule remains removed.

## Tuning Window

The original 2020 tuning interval has no measured demand targets. Scoring it
would violate INV-4. The implementation reserves the three months ending at
the first development fold's training cutoff for measured validation, with
an additional purge before its training boundary. Only IN-EA has measured
targets there. This is a limitation of the available data, and it is disclosed
in the study, model report and model card. The existing twelve test folds and
final holdout boundaries are preserved. No test-fold result selects parameters.

## Contradictory Legacy Text

The hybrid table once named cooling/heating/trend although the governing
feature definition removed heating. The implemented linear inputs are
temperature, cooling degrees and trend. Monotonicity applies to the tree's
cooling-degree input alone; it does not prove monotonicity of the combined model
when raw temperature also changes. Extrapolation is explicitly flagged.

## Runtime Retrain Evidence

A fitted champion cannot be scored retrospectively on dates included in its
training data. Runtime comparisons therefore use complete monthly folds after
the incumbent's training cutoff plus the purge, through the pooled settlement
frontier, capped at twelve folds. They do not reserve another twelve-month
research holdout on every live run. The number of prospective folds is recorded;
an attempt without such
prospective evidence is rejected and recorded. No training error or absent
comparison can move the champion pointer.

The production artifact can only be fitted after the guarded final research
evaluation exists. This keeps the bootstrap fit from training on the reserved
period before that evaluation. Calendar additions verified from West Bengal's
2024 and 2025 notices fall after the tuning validation interval, so they did not
change the inputs during the running search. Older years remain incomplete.

## Recovery Corrections

Partial-zone weather output schedules a retry. Every retry has a separate
immutable attempt record. Published lead times use actual issuance after API
calls and training. Cache writes and forecast files use atomic replacement.
Observed weather resumes from its previous cache boundary after an outage.
The archive schedule stays active until the daily job has an approved champion
and a published container pin; an unfinished deployment cannot disable capture.

The original data-derived research split is persisted in
`reports/research_protocol.json`. Research entry points reuse it after cache
refreshes; they refuse an unrecorded change in split settings. Runtime
prospective evaluation remains separate. This preserves the reserved final
year when the live archive advances, without replacing relative split rules
with manually chosen dates.

## Deployment Evidence

Local Google Drive authentication was checked and failed with invalid_grant.
This prevents verification of durable production backups. A fresh local archive
capture did succeed for all five zones. Captured data remains on the machine.
Three consecutive live daily runs require three actual dates; simulated runs
are never substituted for that exit gate. The completion audit remains false
until the published dashboard, container, remote backups and live runs have
been verified.

## Dependency References

The implementation follows the installed LightGBM and Optuna APIs, checked
against their official references:

- https://lightgbm.readthedocs.io/en/latest/pythonapi/lightgbm.LGBMRegressor.html
- https://optuna.readthedocs.io/en/stable/reference/generated/optuna.study.Study.html

## Iteration Convergence Correction

The first selected fit hit the 1000-round ceiling. A reserved-window check with a 5000-round ceiling stopped at 1456 (refit 1526); validation MASE was 0.902437 versus the capped 0.899704. The ceiling was therefore not an identified early-stopping count. The implementation now rejects a fit at its ceiling. Frozen Optuna hyperparameters are retained; no test result selects the new ceiling. Initial backtest and ablation reports remain in *_initial_capped. Corrected comparisons are rerun before any gate decision. A within-zone linear-centering diagnostic did not improve reserved validation (0.918477), so it was not adopted.

## Final Local Disposition, 2026-11-04

Corrected mean-fold MASE is 1.249804 and RMSSE 1.246597; the seasonal comparator is 1.000 for both. Hybrid MAPE is 14.113545%, versus 11.788892% for seasonal naive on 35,033 common measured targets. No tested feature or training-policy alternative passes mean MASE below one. The mixed-policy and measured-only comparison uses the same 10,564 targets in three folds; mixed-policy MASE is 1.073411 versus measured-only 1.093294. No full-year policy claim is made.

Late observed weather enriches analysis context in memory without rewriting frozen actuals or predictions. Routing uses the evidence for the zone whose condition fired, and insufficient band evidence is explicitly inconclusive. Stale-input error is separately labelled; it does not enter headline figures. The final holdout command refuses a failed development gate. No production champion was approved, no final holdout was consumed, and no live-day exit gate is claimed.

The calibrated replay has zero healthy alarm episodes in 365 days, against a two-per-year budget; injected 2/5/10-percent shifts were detected after 30/23/18 days, excluding settlement lag. Exact first-settlement replay is unavailable, so thresholds remain provisionally optimistic. Counterfactual recovery uses precomputed chronological refits and does not substitute for live training or deployment. Local and Linux metrics agree to three decimals.

Local DVC pointers and the consistent 100-trial study snapshot were written. Remote upload remains unverified because existing Drive authentication returns invalid_grant. Public GitHub HTML independently confirms archive run 58 failed in remote configuration and upload.
