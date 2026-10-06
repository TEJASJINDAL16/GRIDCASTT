"""Hand-calculated metrics and time-context checks, not implementation mirrors."""

import numpy as np
import pandas as pd
import pytest

from src.backtest.metrics import score, temperature_bands, with_error_context


def test_out_of_sample_scaled_metrics_and_bias(cfg):
    frame = pd.DataFrame({"demand_mw": [100., 200.], "prediction_mw": [110., 180.],
                          "baseline_mw": [120., 160.]})
    result = score(frame, cfg)
    assert result["mape_pct"] == 10
    assert result["mae_mw"] == 15
    assert result["mase"] == .5
    assert result["rmsse"] == .5
    assert result["signed_bias_pct"] == 0
    assert result["shortfall_freq_pct"] == 50


def test_zero_denominator_is_undefined_not_a_false_win(cfg):
    frame = pd.DataFrame({"demand_mw": [100.], "prediction_mw": [110.], "baseline_mw": [100.]})
    result = score(frame, cfg)
    assert result["mase"] is None and result["rmsse"] is None


@pytest.mark.parametrize("actual,estimated", [(0., False), (100., True), (100., None)])
def test_invalid_or_unmeasured_targets_are_refused(cfg, actual, estimated):
    frame = pd.DataFrame({"demand_mw": [actual], "prediction_mw": [110.],
                          "baseline_mw": [100.], "is_estimated": [estimated]})
    with pytest.raises(ValueError):
        score(frame, cfg)


def test_ramps_and_peaks_keep_full_day_context_after_hour_stratification(cfg):
    times = pd.date_range("2025-05-01 19:00", periods=24, freq="h", tz="UTC")
    frame = pd.DataFrame({"datetime_utc": times, "zone": "IN-NO", "fold": 1,
                          "date_ist": times.tz_convert("Asia/Kolkata").date,
                          "hour_of_day": times.tz_convert("Asia/Kolkata").hour,
                          "demand_mw": np.arange(24) * 10 + 100,
                          "prediction_mw": np.arange(24) * 5 + 100,
                          "baseline_mw": 100.})
    context = with_error_context(frame, cfg)
    at_eighteen = score(context.loc[context.hour_of_day == 18], cfg)
    assert at_eighteen["n_ramps"] == 1
    assert at_eighteen["ramp_mae_mw"] == 5
    assert at_eighteen["ramp_mase"] == .5
    assert at_eighteen["n_peak_days"] == 0
    peak = score(context.loc[context.hour_of_day == 23], cfg)
    assert peak["n_peak_days"] == 1
    assert peak["peak_mae_mw"] == 115


def test_ramp_cannot_bridge_a_missing_hour_or_zone(cfg):
    stamps = pd.to_datetime(["2025-05-01 11:00Z", "2025-05-01 13:00Z", "2025-05-01 14:00Z"])
    frame = pd.DataFrame({"datetime_utc": stamps, "zone": ["IN-NO", "IN-NO", "IN-NE"],
                          "fold": 1, "date_ist": stamps.tz_convert("Asia/Kolkata").date,
                          "hour_of_day": stamps.tz_convert("Asia/Kolkata").hour,
                          "demand_mw": [100, 200, 300], "prediction_mw": [100, 100, 100],
                          "baseline_mw": [100, 100, 100]})
    assert score(frame, cfg)["n_ramps"] == 0
    assert score(frame, cfg)["n_peak_days"] == 0


def test_hottest_temperature_band_stays_separate_when_absent(cfg):
    temp = pd.Series([15.] * 600 + [25.] * 600 + [35.] * 600 + [42.] * 600)
    labels, categories = temperature_bands(temp, cfg)
    assert categories[-1] == ">= 45 C"
    assert labels.eq(categories[-1]).sum() == 0


def test_sparse_interior_band_merges_without_losing_hottest_band(cfg):
    temp = pd.Series([15.] * 600 + [25.] * 20 + [35.] * 600 + [42.] * 600 + [46.] * 5)
    labels, categories = temperature_bands(temp, cfg)
    assert "20 to < 40 C" in categories
    assert labels.eq(">= 45 C").sum() == 5
