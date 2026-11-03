"""Build the seven dashboard sections from recorded forecasts and scores."""

import html
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from src.backtest.metrics import score, temperature_bands
from src.monitor.drift import clean_scores, daily_metrics, threshold_for
from src.viz.plots import bars, lines


def publish(root, cfg):
    from src.jobs.daily import forecast_history, read_json, score_history, select_versions

    out = root / cfg["dashboard"]["output_dir"]
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    history = select_versions(forecast_history(root, cfg), cfg)
    recorded_scores = score_history(root, cfg)
    scores = clean_scores(recorded_scores)
    degraded = recorded_scores.iloc[0:0]
    if len(recorded_scores):
        degraded = recorded_scores.loc[
            recorded_scores["flags"].map(
                lambda flags: any(str(flag).startswith("stale_weather_") for flag in flags)
            )
        ]
    status_files = sorted((root / "state/runs").glob("*-daily.json"))
    status = read_json(status_files[-1], {}) if status_files else {}
    metadata = read_json(root / cfg["runtime"]["model_metadata"], {})
    development_link = ""
    development_path = root / "reports/model/stratified.csv"
    if development_path.exists():
        strata = pd.read_csv(development_path)
        lead = strata.loc[strata.dimension == "lead_time_hours"]
        model = lead.loc[lead.model == "hybrid"].set_index("segment")
        baseline = lead.loc[lead.model == "seasonal_naive"].set_index("segment")
        if len(model):
            model = model.sort_index(key=lambda labels: labels.astype(float))
            baseline = baseline.reindex(model.index)
            bars(
                assets / "development-lead.svg",
                model.index.tolist(),
                model.mape_pct,
                baseline.mape_pct,
                model.n_rows.astype(int),
                "Development MAPE (%)",
            )
            development_link = '<p><a href="assets/development-lead.svg">Development lead-time comparison: hybrid, seasonal baseline and row counts</a>. Simulated forecast weather; development results do not establish live accuracy.</p>'
    rows = []
    for zone in cfg["demand"]["all_zones"]:
        f = history.loc[history.zone == zone].copy() if len(history) else pd.DataFrame()
        s = scores.loc[scores.zone == zone].copy() if len(scores) else pd.DataFrame()
        observed_scores = (
            recorded_scores.loc[recorded_scores.zone == zone]
            if len(recorded_scores)
            else pd.DataFrame()
        )
        if len(s):
            s = s.loc[np.isfinite(s.baseline_mw) & np.isfinite(s.prediction_mw)].copy()
        cards = "<p>Pending measured actuals. No live accuracy estimate is available.</p>"
        if len(observed_scores) and not len(s):
            cards = "<p>Measured actuals are recorded; no comparable headline accuracy is available yet.</p>"
        if len(s):
            stats = score(s, cfg)
            baseline = s.copy()
            baseline["prediction_mw"] = baseline.baseline_mw
            bs = score(baseline, cfg)
            cards = (
                '<dl class="metrics">'
                + "".join(
                    f"<div><dt>{label}</dt><dd>{stats[key]:.3f}<small>Baseline {bs[key]:.3f} | n={len(s):,}</small></dd></div>"
                    for label, key in [
                        ("MAPE %", "mape_pct"),
                        ("MASE", "mase"),
                        ("Signed bias %", "signed_bias_pct"),
                        ("Shortfall %", "shortfall_freq_pct"),
                    ]
                    if stats[key] is not None and bs[key] is not None
                )
                + "</dl>"
            )
            shortfalls = (
                (s.prediction_mw - s.demand_mw) / s.demand_mw * 100
                < -cfg["evaluate"]["shortfall_threshold_pct"]
            ).sum()
            baseline_shortfalls = (
                (s.baseline_mw - s.demand_mw) / s.demand_mw * 100
                < -cfg["evaluate"]["shortfall_threshold_pct"]
            ).sum()
            cards += f"<p>Shortfall hours: {shortfalls:,}; baseline: {baseline_shortfalls:,} (n={len(s):,}).</p>"
        today = "<p>No forecast has been issued for this zone.</p>"
        if len(degraded):
            affected = degraded.loc[degraded.zone == zone].copy()
            if len(affected):
                comparable = affected.loc[
                    np.isfinite(affected.baseline_mw) & np.isfinite(affected.prediction_mw)
                ]
                cards += f"<p>Input-degraded hours excluded from headline accuracy: {len(affected):,}.</p>"
                if len(comparable):
                    errors = score(comparable, cfg)
                    cards += f"<p>Separate degraded-input MAPE: model {errors['mape_pct']:.3f}%; baseline {errors['baseline_mape_pct']:.3f}% (n={len(comparable):,}).</p>"
        recent = "<p>Forecast history has not started.</p>"
        if len(f):
            latest = f.loc[f.issue_date == history.issue_date.max()]
            if latest.empty:
                today = f"<p>Unavailable for the latest issue ({history.issue_date.max()}).</p>"
            else:
                today_path = assets / f"{zone}-today.svg"
                lines(
                    today_path,
                    latest.datetime_utc,
                    {"Forecast": latest.prediction_mw, "Seasonal naive": latest.baseline_mw},
                    "Demand (MW)",
                    timezone=cfg["project"]["timezone"],
                )
                peak = latest.loc[latest.prediction_mw.idxmax()]
                target = peak.datetime_utc.tz_convert(cfg["project"]["timezone"])
                today = f'<p>Forecast for {target:%d %b %Y}. Peak {peak.prediction_mw:,.0f} MW at {target:%H:%M IST}</p><img src="assets/{today_path.name}" alt="Hourly forecast and seasonal baseline">'
            recent_frame = f.loc[
                f.datetime_utc
                >= f.datetime_utc.max() - pd.Timedelta(days=cfg["dashboard"]["history_days"])
            ]
            if len(observed_scores):
                recent_frame = recent_frame.merge(
                    observed_scores[["zone", "datetime_utc", "demand_mw"]],
                    on=["zone", "datetime_utc"],
                    how="left",
                )
            else:
                recent_frame = recent_frame.assign(demand_mw=np.nan)
            pending = recent_frame.loc[recent_frame.demand_mw.isna(), "datetime_utc"]
            hist_path = assets / f"{zone}-history.svg"
            lines(
                hist_path,
                recent_frame.datetime_utc,
                {
                    "Forecast": recent_frame.prediction_mw,
                    "Actual": recent_frame.demand_mw,
                    "Seasonal naive": recent_frame.baseline_mw,
                },
                "Demand (MW)",
                pending=pending.min() if len(pending) else None,
                timezone=cfg["project"]["timezone"],
            )
            err_path = assets / f"{zone}-error.svg"
            recent = f'<img src="assets/{hist_path.name}" alt="Forecast history, actuals and pending hours">'
            headline_keys = pd.MultiIndex.from_frame(s[["zone", "datetime_utc"]]) if len(s) else []
            comparable = pd.MultiIndex.from_frame(recent_frame[["zone", "datetime_utc"]]).isin(
                headline_keys
            )
            if comparable.any():
                lines(
                    err_path,
                    recent_frame.datetime_utc,
                    {
                        "Model": (recent_frame.prediction_mw - recent_frame.demand_mw).where(
                            comparable
                        ),
                        "Seasonal naive": (recent_frame.baseline_mw - recent_frame.demand_mw).where(
                            comparable
                        ),
                    },
                    "Signed error (MW)",
                    pending=pending.min() if len(pending) else None,
                    timezone=cfg["project"]["timezone"],
                )
                recent += f'<img src="assets/{err_path.name}" alt="Signed forecast error and baseline error">'
            else:
                recent += "<p>No comparable errors yet. Hatched hours await measured actuals; stale weather errors are reported separately.</p>"
        breakdown = "<p>Waiting for settled forecasts.</p>"
        drift = (
            "<p>Monitor not armed.</p>"
            if not cfg["drift"]["thresholds_derived"]
            else "<p>Waiting for complete settled windows.</p>"
        )
        if len(s):
            breakdown = ""
            s["temperature_band"], _ = temperature_bands(s.observed_temperature, cfg)
            s["lead_hour"] = np.floor(s.lead_time_hours).astype("int64")
            for column in ["hour_of_day", "temperature_band", "lead_hour"]:
                stats = []
                for label, group in s.groupby(column, observed=True):
                    if (
                        column == "temperature_band"
                        and len(group) < cfg["evaluate"]["insufficient_band_rows"]
                    ):
                        breakdown += f"<p>{html.escape(str(label))}: insufficient rows to judge (n={len(group)}).</p>"
                        continue
                    value = score(group, cfg)
                    label = f"{label}-{label + 1}h" if column == "lead_hour" else str(label)
                    stats.append((label, value["mape_pct"], value["baseline_mape_pct"], len(group)))
                if stats:
                    path = assets / f"{zone}-{column}.svg"
                    labels, model, base, counts = zip(*stats, strict=True)
                    bars(path, labels, model, base, counts, "MAPE (%)")
                    breakdown += f'<img src="assets/{path.name}" alt="Errors by {column}, with baseline and row counts">'
            rolling = daily_metrics(s, cfg)
            rolling = rolling.loc[rolling.zone == zone]
            if len(rolling) and rolling.error.notna().any():
                drift = ""
                for metric, column, label in [
                    ("rolling_error", "error", "MAPE (%)"),
                    ("signed_bias", "bias", "Signed bias (%)"),
                ]:
                    path = assets / f"{zone}-{metric}.svg"
                    bound = threshold_for(cfg, metric, zone)
                    thresholds = [("Trigger", bound)] + (
                        [("Negative trigger", -bound)]
                        if metric == "signed_bias" and bound is not None
                        else []
                    )
                    base_col = (
                        rolling.baseline_error if column == "error" else rolling.baseline_bias
                    )
                    lines(
                        path,
                        rolling.date,
                        {"Model": rolling[column], "Seasonal naive": base_col},
                        label,
                        thresholds=thresholds,
                        timezone=cfg["project"]["timezone"],
                    )
                    drift += f'<img src="assets/{path.name}" alt="Rolling {label} and trigger thresholds">'
        flags = sorted({flag for values in latest["flags"] for flag in values}) if len(f) else []
        age = status.get("weather_age_hours", {}).get(zone)
        if age is not None:
            cards += f"<p>Weather vintage age at issue: {age:.1f} hours.</p>"
        rows.append(
            f'<article data-zone="{zone}"><section><h2>{zone}</h2><p>{html.escape(", ".join(flags) or "No forecast flags")}</p>{cards}<p>Settled fraction: {status.get("settled_fraction", 0):.1%}</p></section><section><h2>Today</h2>{today}</section><section><h2>Last 10 days</h2>{recent}</section><section><h2>Where it goes wrong</h2>{breakdown}</section><section><h2>Is it drifting?</h2>{drift}<p>Latest action: {html.escape(str(status.get("trigger", {}).get("action", "Not evaluated")))}</p></section></article>'
        )
    footer = "Weather-noise sigmas, settlement lag and maximum vintage age remain assumptions. Development folds span the transition from estimated to measured targets. Threshold replay is provisionally optimistic."
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Gridcast | Indian electricity demand</title><style>body{margin:0;color:#202824;background:#fff;font:15px system-ui;letter-spacing:0}header,main,footer{max-width:1100px;margin:auto;padding:24px}header{border-bottom:2px solid #087f5b}h1{font-size:32px;margin:0 0 8px}h2{font-size:20px}section{padding:18px 0;border-bottom:1px solid #ddd}img{display:block;width:100%;height:auto}select{padding:8px;font:inherit;border:1px solid #aeb9b2;background:white}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:18px}.metrics div{border-left:3px solid #087f5b;padding-left:12px}dd{margin:8px 0;font-size:23px}small{display:block;font-size:12px;color:#5d665f;margin-top:6px}footer{font-size:13px;color:#536057;overflow-wrap:anywhere}article[hidden]{display:none}.status{color:#9c4a26}@media(max-width:600px){header,main,footer{padding:16px}h1{font-size:28px}}</style>'
    content += (
        '<header><h1>Gridcast</h1><p>Day-ahead electricity demand across India</p><label for="zone">Region </label><select id="zone">'
        + "".join(f"<option>{z}</option>" for z in cfg["demand"]["all_zones"])
        + f'</select><p class="status">{html.escape(status.get("outcome", "Awaiting first daily run"))} | Issued {html.escape(status.get("run_at", "Not issued"))}</p><p>Model {html.escape(metadata.get("version", "No approved champion"))}</p></header><main>'
    )
    alerts = " ".join(status.get("alerts", []))
    content += f'<p role="status">{html.escape(alerts)}</p>'
    content += (
        "".join(rows)
        + f'</main><footer><p>{footer}</p>{development_link}<p>Training cutoff: {html.escape(str(metadata.get("train_end", "Pending")))} | Last promotion: {html.escape(str(metadata.get("trained_at", "None")))}</p><p>Settlement frontier: {html.escape(str(status.get("frontiers", {}).get("pooled", "Pending")))}</p><p>Generated {datetime.now(UTC).isoformat()} | Demand data: <a href="https://www.electricitymaps.com/">Electricity Maps</a> | Weather: Open-Meteo</p></footer><script>const select=document.getElementById("zone");function show(){{document.querySelectorAll("article").forEach(a=>a.hidden=a.dataset.zone!==select.value)}}select.addEventListener("change",show);show();</script></html>'
    )
    temporary = out / ".index.tmp"
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(out / "index.html")
    return out / "index.html"
