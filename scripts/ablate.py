"""Frozen-parameter feature and estimation-policy comparisons."""

import copy
import pathlib
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.backtest.run import evaluate, load_cached
from src.backtest.splits import research_plan
from src.config import PROJECT_ROOT, load_config
from src.features.build import FEATURE_COLUMNS, build_features
from src.records import pins, write_json


def evaluate_variant(variant):
    name, excluded, local, split = variant
    demand, weather = load_cached(PROJECT_ROOT, local)
    result = evaluate(demand, weather, local, hybrid=True, excluded=excluded, plan=split)
    path = PROJECT_ROOT / "reports/ablation" / f"{name}.csv"
    result["fold_scores"].to_csv(path, index=False)
    stats = result["fold_scores"].loc[lambda f: f.model == "hybrid"]
    return {
        "variant": name,
        "folds": len(split.folds),
        "n_rows": int(stats.n_rows.sum()),
        **stats[["mase", "rmsse", "mape_pct"]].mean().to_dict(),
    }


def main():
    root, cfg = PROJECT_ROOT, load_config()
    demand, weather = load_cached(root, cfg)
    plan = research_plan(root, build_features(weather, cfg, demand=demand), cfg)
    out = root / "reports/ablation"
    out.mkdir(parents=True, exist_ok=True)
    variants = [(f"without_{feature}", (feature,), cfg, plan) for feature in FEATURE_COLUMNS]
    cyclic = copy.deepcopy(cfg)
    cyclic["features"]["candidate_day_of_year"] = True
    variants.append(("add_cyclic_day_of_year", (), cyclic, plan))
    older = copy.deepcopy(cfg)
    older["quality"]["trainable_from"].pop("IN-EA", None)
    variants.append(("include_earlier_east", (), older, plan))
    reduced = replace(plan, folds=plan.folds[-3:])
    measured = copy.deepcopy(cfg)
    measured["quality"]["trainable_estimation_methods"] = ["MEASURED"]
    variants += [
        ("measured_only", (), measured, reduced),
        ("mixed_same_three_folds", (), cfg, reduced),
    ]
    records = []
    write_json(
        out / "manifest.json", {"pins": pins(root, cfg), "variants": [v[0] for v in variants]}
    )
    with ProcessPoolExecutor(max_workers=cfg["runtime"]["ablation_workers"]) as pool:
        futures = [pool.submit(evaluate_variant, variant) for variant in variants]
        for future in as_completed(futures):
            record = future.result()
            records.append(record)
            pd.DataFrame(records).sort_values("variant").to_csv(out / "summary.csv", index=False)
            print(record, flush=True)
    (root / "reports/ablation.md").write_text(
        "# Ablation\n\nFrozen parameters; no feature is selected using these test results. "
        "The measured-only comparison uses only the final three development folds and must be compared "
        "with mixed_same_three_folds, not the twelve-fold headline. All scores use measured targets "
        "and identical baseline availability. Out-of-sample MASE/RMSSE denominators are seasonal naive.\n\n"
        + pd.DataFrame(records).to_markdown(index=False)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
