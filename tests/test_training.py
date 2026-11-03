"""A failed fit and the bootstrap command cannot damage release state."""

import numpy as np
import pandas as pd
import pytest

from src.jobs.train import fit_artifact
from src.records import write_json
from tests.test_backtest import small_inputs


def test_invalid_training_matrix_is_refused_before_writing(tmp_path, cfg):
    cfg, demand, weather = small_inputs(cfg)
    weather["temperature_2m"] = np.inf
    with pytest.raises(ValueError, match="refusing to write"):
        fit_artifact(
            tmp_path, cfg, demand, weather, pd.Timestamp("2024-04-01", tz="UTC"), approved=False
        )
    assert not list(tmp_path.rglob("*_training.parquet"))
    assert not list(tmp_path.rglob("*.joblib"))


def test_bootstrap_cannot_overwrite_an_existing_champion(tmp_path, cfg, monkeypatch):
    from scripts import train

    write_json(tmp_path / cfg["runtime"]["model_metadata"], {"version": "existing"})
    monkeypatch.setattr(train, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(train, "load_config", lambda: cfg)
    with pytest.raises(SystemExit, match="Champion already initialized"):
        train.main()


def test_failed_development_gate_cannot_consume_the_final_holdout(tmp_path, cfg, monkeypatch):
    from scripts import holdout

    write_json(tmp_path / "reports/model/selection.json", {"promote": False})
    monkeypatch.setattr(holdout, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(holdout, "load_config", lambda: cfg)
    with pytest.raises(SystemExit, match="final holdout stays reserved"):
        holdout.main()
    assert not (tmp_path / "reports/holdout/evaluation.json").exists()
