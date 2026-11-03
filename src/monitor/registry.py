"""Evidence-based champion decisions; a failed comparison cannot promote."""

import numpy as np
import pandas as pd

from src.backtest.metrics import score, temperature_bands


def compare(rows, cfg, challenger="hybrid", champion="seasonal_naive"):
    left = rows.loc[rows.model == challenger].copy()
    right = rows.loc[rows.model == champion].copy()
    keys = ["fold", "zone", "datetime_utc"]
    if left.duplicated(keys).any() or right.duplicated(keys).any():
        return {"promote": False, "reasons": ["duplicate comparison rows"]}
    if (
        set(map(tuple, left[keys].to_numpy())) != set(map(tuple, right[keys].to_numpy()))
        or left.empty
    ):
        return {"promote": False, "reasons": ["different or empty comparison cohorts"]}
    a, b = score(left, cfg), score(right, cfg)
    folds = {}
    for name, frame in [(challenger, left), (champion, right)]:
        folds[name] = pd.DataFrame([score(g, cfg) for _, g in frame.groupby("fold")])
    reasons = []
    for metric in ["mase", "rmsse"]:
        av, bv = folds[challenger][metric].mean(), folds[champion][metric].mean()
        if not np.isfinite([av, bv]).all() or (av >= bv if metric == "mase" else av > bv):
            reasons.append(f"mean fold {metric} did not improve/hold")
    tolerance = cfg["evaluate"]["veto_tolerance"]
    for name, metric in [
        ("signed_bias_pct", "signed_bias_pct"),
        ("shortfall_freq_pct", "shortfall_freq_pct"),
        ("p95_pct", "p95_abs_pct"),
    ]:
        av, bv = a[metric], b[metric]
        if name == "signed_bias_pct":
            av, bv = abs(av), abs(bv)
        if tolerance[name] is None or av - bv > tolerance[name]:
            reasons.append(f"{name} veto or missing tolerance")
    bands, labels = temperature_bands(left.observed_temperature, cfg)
    highest = next(
        (
            label
            for label in reversed(labels)
            if (bands == label).sum() >= cfg["evaluate"]["insufficient_band_rows"]
        ),
        None,
    )
    if highest is None or tolerance["top_band_pct"] is None:
        reasons.append("no reportable temperature band or tolerance")
    else:
        selected = left.loc[bands == highest, keys]
        ac = score(left.merge(selected, on=keys), cfg)["mape_pct"]
        bc = score(right.merge(selected, on=keys), cfg)["mape_pct"]
        if ac - bc > tolerance["top_band_pct"]:
            reasons.append("top reportable temperature band veto")
    return {
        "promote": not reasons,
        "reasons": reasons,
        "challenger": a,
        "champion": b,
        "fold_means": {
            name: frame[["mase", "rmsse"]].mean().to_dict() for name, frame in folds.items()
        },
        "fold_win_rate": float((folds[challenger].mase < folds[champion].mase).mean()),
        "top_reportable_band": highest,
    }


def derive_tolerances(rows, cfg):
    """One sample standard deviation across frozen-model test folds."""
    stats, hot = [], []
    bands, labels = temperature_bands(rows.observed_temperature, cfg)
    highest = next(
        (
            x
            for x in reversed(labels)
            if (bands == x).sum() >= cfg["evaluate"]["insufficient_band_rows"]
        ),
        None,
    )
    for _, frame in rows.groupby("fold"):
        stats.append(score(frame, cfg))
        subset = frame.loc[bands.loc[frame.index] == highest]
        if len(subset) >= cfg["evaluate"]["insufficient_band_rows"]:
            hot.append(score(subset, cfg)["mape_pct"])
    data = pd.DataFrame(stats)
    return {
        "signed_bias_pct": float(data.signed_bias_pct.abs().std()),
        "shortfall_freq_pct": float(data.shortfall_freq_pct.std()),
        "p95_pct": float(data.p95_abs_pct.std()),
        "top_band_pct": float(np.std(hot, ddof=1)) if len(hot) > 1 else None,
    }
