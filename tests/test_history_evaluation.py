"""The final-year evaluator must refuse repeat scoring and ineligible candidates."""

import importlib.util
from pathlib import Path

import pytest


def evaluator():
    path = Path(__file__).resolve().parents[1] / "scripts/evaluate_history.py"
    spec = importlib.util.spec_from_file_location("evaluate_history_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_holdout_marker_prevents_any_data_access(tmp_path, monkeypatch):
    module = evaluator()
    marker = tmp_path / "reports/holdout/evaluation.json"
    marker.parent.mkdir(parents=True)
    marker.write_text("{}", encoding="utf-8")

    def forbidden(*args):
        raise AssertionError("Existing holdout must never be accessed again")

    monkeypatch.setattr(module, "load_cached", forbidden)
    module.final_holdout(tmp_path, {})


def test_failed_development_gate_cannot_claim_holdout(tmp_path):
    module = evaluator()
    with pytest.raises(ValueError, match="must pass"):
        module.final_holdout(tmp_path, {})
    assert not (tmp_path / "reports/holdout/evaluation.json").exists()
