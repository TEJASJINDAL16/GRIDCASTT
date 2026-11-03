"""One local MLflow run per experiment or production attempt."""

from src.config import configure_tracking
from src.records import pins


def relocate_store(root):
    """Keep DVC-restored file-store artifacts inside this checkout."""
    import yaml

    store = root / "mlruns"
    for path in store.glob("**/meta.yaml"):
        metadata = yaml.safe_load(path.read_text(encoding="utf-8"))
        key = "artifact_uri" if "artifact_uri" in metadata else "artifact_location"
        if key not in metadata:
            continue
        target = path.parent / "artifacts" if key == "artifact_uri" else path.parent
        if metadata[key] != target.as_uri():
            metadata[key] = target.as_uri()
            temporary = path.with_suffix(".tmp")
            temporary.write_text(yaml.safe_dump(metadata), encoding="utf-8")
            temporary.replace(path)


def log_run(root, cfg, name, metrics, artifacts=(), data_path=None):
    configure_tracking()
    import mlflow

    relocate_store(root)
    mlflow.set_tracking_uri((root / "mlruns").as_uri())
    mlflow.set_experiment("gridcast")
    with mlflow.start_run(run_name=name):
        mlflow.set_tags({k: str(v) for k, v in pins(root, cfg, data_path).items()})
        mlflow.log_params(
            {
                "half_life": cfg["train"]["recency_half_life_days"],
                "breakpoint": cfg["features"]["temp_breakpoint_c"],
                "ridge_alpha": cfg["train"]["ridge"]["alpha"],
                **{f"lightgbm_{k}": v for k, v in cfg["train"]["lightgbm"].items()},
            }
        )
        mlflow.log_metrics({k: float(v) for k, v in metrics.items() if v is not None})
        for path in artifacts:
            mlflow.log_artifact(str(path))
