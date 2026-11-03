"""Initialize the champion only after the recorded development gate passes."""

import json
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.backtest.run import load_cached
from src.config import PROJECT_ROOT, load_config
from src.jobs.train import fit_artifact
from src.records import write_json
from src.tracking import log_run


def main():
    cfg = load_config()
    if (PROJECT_ROOT / cfg["runtime"]["model_metadata"]).exists():
        raise SystemExit(
            "Champion already initialized; updates must pass the monitored retrain gate."
        )
    if not (PROJECT_ROOT / "reports/holdout/evaluation.json").exists():
        raise SystemExit(
            "Evaluate the final holdout once before fitting the production artifact on all available history."
        )
    decision = json.loads(
        (PROJECT_ROOT / "reports/calibration/selection.json").read_text(encoding="utf-8")
    )
    demand, weather = load_cached(PROJECT_ROOT, cfg)
    approved = decision["promote"]
    metadata = fit_artifact(
        PROJECT_ROOT,
        cfg,
        demand,
        weather,
        datetime.now(UTC),
        approved=approved,
        name="champion" if approved else "candidate",
    )
    path = PROJECT_ROOT / "state/promotions/bootstrap.json"
    write_json(
        path,
        {
            "outcome": "promotion" if approved else "rejection",
            "decision": decision,
            "pins": metadata["pins"],
            "model": metadata,
        },
    )
    log_run(PROJECT_ROOT, cfg, "bootstrap", {"approved": int(approved)}, [path])
    print(
        "Champion initialized"
        if approved
        else "Candidate saved; selection gate rejected deployment"
    )


if __name__ == "__main__":
    main()
