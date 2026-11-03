"""Build a model card from measured artifacts and explicit remaining limits."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from src.config import PROJECT_ROOT
from src.jobs.daily import read_json


def main():
    root = PROJECT_ROOT
    metadata = read_json(
        root / "models/champion.json", read_json(root / "models/candidate.json", {})
    )
    selection = read_json(
        root / "reports/calibration/selection.json",
        read_json(root / "reports/model/selection.json", {}),
    )
    fits = read_json(root / "reports/model/fits.json", [])
    ranges = metadata.get("ranges", fits[-1]["training_ranges"] if fits else {})
    range_rows = [
        {"zone": zone, "feature": feature, **limits}
        for zone, features in ranges.items()
        for feature, limits in features.items()
    ]
    parts = [
        "# Gridcast Model Card",
        "",
        "Day-ahead hourly consumption in MW for five Indian zones. Academic, non-commercial use; demand data from Electricity Maps.",
        "",
        "## Model and Evidence",
        "",
        "Ridge on temperature, cooling degrees and trend, plus LightGBM residuals; log target and per-zone Duan smearing. No demand lags or inferred-cause filtering.",
        "",
        f"Deployment approved by development selection gate: {selection.get('promote', False)}. Reasons: {selection.get('reasons', ['No completed gate'])}.",
        "",
        "Tuning uses measured Eastern-zone targets before the first test fold. The originally reserved early year contained no measured targets. This limits cross-zone tuning evidence.",
        "",
        "Development folds cross the MODE_BREAKDOWN-to-measured transition. Forecast weather is a constant-sigma simulation bridge; results do not establish exact historical forecast-vintage skill.",
    ]
    for name in ["model", "holdout"]:
        path = root / f"reports/{name}/summary.csv"
        if path.exists():
            frame = pd.read_csv(path)
            parts += [
                "",
                f"## {name.title()} Results",
                "",
                "Out-of-sample MASE/RMSSE on identical measured rows; seasonal-naive denominator.",
                "",
                frame[
                    ["model", "n_rows", "mape_pct", "mase", "rmsse", "signed_bias_pct"]
                ].to_markdown(index=False),
            ]
            strata = pd.read_csv(root / f"reports/{name}/stratified.csv")
            bands = strata.loc[
                (strata.dimension == "temperature_band")
                & strata.model.isin(["hybrid", "seasonal_naive"]),
                ["segment", "model", "n_rows", "status", "mape_pct", "signed_bias_pct"],
            ].copy()
            for column in ["mape_pct", "signed_bias_pct"]:
                bands[column] = bands[column].astype(object)
                bands.loc[bands.status != "reportable", column] = "insufficient / absent"
            parts += ["", "### Temperature-band limits", "", bands.to_markdown(index=False)]
    parts += [
        "",
        "## Training Ranges",
        "",
        "Production-artifact ranges."
        if metadata.get("ranges")
        else "Final development fold ranges; no approved production artifact exists.",
        pd.DataFrame(range_rows).to_markdown(index=False)
        if range_rows
        else "No fitted ranges available.",
        "",
        "## Remaining Assumptions",
        "",
        "Ten-day settlement purge; weather-noise sigmas 1.2 C daily and 0.5 C hourly; maximum vintage age 72 hours. Exact captured-vintage and first-settlement history is too short to replace these honestly. Thresholds use fully settled replay and remain provisionally optimistic. Cooldown lengths are policy defaults; a frozen-champion decay study remains required to validate them.",
        "",
        "Manual festival coverage remains limited to the configured external calendar; no dates are invented. Sparse hottest bands are shown as insufficient, never as established performance.",
        "",
        "Earlier exploratory analysis inspected the eventual holdout history. The final scoring run is reserved, but the project cannot claim the entire dataset was unseen throughout development.",
        "",
        "## Reproducibility",
        "",
        str(metadata.get("pins", {})),
        "",
        "Decision and metrics to three decimal places are the target; not bit-identical floating-point artifacts. A null image digest means the container pin is not yet verified.",
        "",
    ]
    (root / "reports/model_card.md").write_text("\n".join(parts), encoding="utf-8")


if __name__ == "__main__":
    main()
