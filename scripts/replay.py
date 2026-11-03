"""Exercise the live state machine on real backtest rows and injected drift.

Monthly backtest refits supply precomputed challengers. This is a counterfactual
control-flow replay, not a live promotion, a new skill estimate or proof of
historical settlement timing. It never writes the production registry.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT, load_config
from src.monitor.drift import changed_within_bands, daily_metrics, evaluate_triggers, finish_attempt
from src.monitor.registry import compare
from src.records import pins, write_json


def main():
    root, cfg = PROJECT_ROOT, load_config()
    original = pd.read_parquet(root / "data/interim/model_predictions.parquet")
    original = original.loc[original.model == "hybrid"].copy()
    start = (
        original.datetime_utc.min()
        + (original.datetime_utc.max() - original.datetime_utc.min()) / 2
    )
    rows = original.copy()
    # A separately disclosed stress case exercises recovery; the prescribed
    # 2/5/10-percent sensitivity measurements are in the calibration report.
    shift = cfg["runtime"]["replay_stress_pct"]
    rows.loc[rows.datetime_utc >= start, "prediction_mw"] *= 1 + shift / 100
    rows["date"] = rows.datetime_utc.dt.tz_convert(cfg["project"]["timezone"]).dt.normalize()
    state, records, promoted_at = {}, [], None
    for day in sorted(rows.date.unique()):
        past = rows.loc[rows.date <= day].copy()
        recent = past.loc[
            past.date >= day - pd.Timedelta(days=cfg["drift"]["rolling_window_days"] - 1)
        ]
        watch = None
        if promoted_at is not None:
            watch = daily_metrics(
                past.loc[past.date > promoted_at],
                cfg,
                window=cfg["drift"]["post_promotion_watch_days"],
            )
        state, event = evaluate_triggers(
            daily_metrics(past, cfg),
            cfg,
            state,
            model_sha=cfg["drift"]["thresholds_backtest_sha"],
            issue_date=str(day.date()),
            settled_fraction=1.0,
            concept_drift=changed_within_bands(recent, original, cfg),
            watch_metrics=watch,
        )
        if event["action"] == "retrain":
            keys = ["fold", "zone", "datetime_utc"]
            challenger = original.merge(recent[keys], on=keys, validate="one_to_one")
            champion = recent.assign(model="champion")
            decision = compare(
                pd.concat([challenger, champion], ignore_index=True), cfg, champion="champion"
            )
            outcome = "promotion" if decision["promote"] else "rejection"
            state = finish_attempt(state, outcome, str(day.date()), cfg)
            event.update(outcome=outcome, decision=decision)
            if decision["promote"]:
                promoted_at = day
                future = rows.date > day
                rows.loc[future, "prediction_mw"] = original.loc[future, "prediction_mw"]
        records.append(event)
    out = root / "reports/replay"
    write_json(out / "events.json", records)
    summary = {
        "pins": pins(root, cfg),
        "counterfactual": True,
        "injected_shift_pct": shift,
        "retrain_attempts": sum(r["action"] == "retrain" for r in records),
        "promotions": sum(r.get("outcome") == "promotion" for r in records),
        "cooldown_days": sum(r["action"] == "cooldown" for r in records),
        "challengers": "precomputed chronological monthly refits from the frozen backtest",
        "historical_settlement_replayed": False,
    }
    write_json(out / "summary.json", summary)
    (root / "reports/replay.md").write_text(
        "# Control-flow Replay\n\nReal measured development rows; deliberately shifted incumbent predictions. "
        "This is a counterfactual functional exercise, not a deployment or an accuracy estimate. "
        "Challengers are the saved monthly refits; this replay does not claim to have rerun live training. "
        "First-settlement history is unavailable. The calibrated false-alarm and 2/5/10-percent delay "
        "tables remain in threshold_derivation.md.\n\n" + str(summary) + "\n",
        encoding="utf-8",
    )
    print(summary)


if __name__ == "__main__":
    main()
