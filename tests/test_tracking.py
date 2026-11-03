"""Restoring DVC experiment history must not write artifacts outside the repo."""

import yaml

from src.tracking import relocate_store


def test_file_store_paths_follow_restored_checkout(tmp_path):
    experiment = tmp_path / "mlruns/123"
    run = experiment / "abc"
    run.mkdir(parents=True)
    (experiment / "meta.yaml").write_text(
        "artifact_location: file:///old/mlruns/123\nname: gridcast\n", encoding="utf-8"
    )
    (run / "meta.yaml").write_text(
        "artifact_uri: file:///old/mlruns/123/abc/artifacts\nstatus: 3\n", encoding="utf-8"
    )
    relocate_store(tmp_path)
    assert (
        yaml.safe_load((experiment / "meta.yaml").read_text(encoding="utf-8"))["artifact_location"]
        == experiment.as_uri()
    )
    assert (
        yaml.safe_load((run / "meta.yaml").read_text(encoding="utf-8"))["artifact_uri"]
        == (run / "artifacts").as_uri()
    )
