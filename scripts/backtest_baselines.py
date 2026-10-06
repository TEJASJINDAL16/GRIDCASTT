"""Run Stage 2's four frozen baselines against the local real-data cache."""

import logging
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.backtest.run import evaluate, load_cached, write_report
from src.config import PROJECT_ROOT, load_config


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = load_config()
    demand, weather = load_cached(PROJECT_ROOT, cfg)
    result = evaluate(demand, weather, cfg)
    path = write_report(result, cfg, PROJECT_ROOT)
    print(f"Baseline report: {path}")


if __name__ == "__main__":
    main()
