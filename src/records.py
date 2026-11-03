"""Small atomic records and reproducibility metadata shared by batch jobs."""

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, delete=False, encoding="utf-8"
    ) as f:
        json.dump(value, f, default=str, indent=2, allow_nan=False)
        f.write("\n")
    pathlib.Path(f.name).replace(path)


def pins(root, cfg, data_path=None):
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    sources = sorted((root / "src").rglob("*.py")) + sorted((root / "scripts").glob("*.py"))
    code = hashlib.sha256("".join(digest(p) for p in sources).encode()).hexdigest()
    pointers = {str(p.relative_to(root)): digest(p) for p in sorted((root / "data").rglob("*.dvc"))}
    return {
        "git_sha": sha,
        "source_sha256": code,
        "data_sha256": digest(data_path) if data_path else None,
        "data_dvc_md5": hashlib.md5(pathlib.Path(data_path).read_bytes()).hexdigest()
        if data_path
        else None,
        "dvc_pointer_sha256": pointers,
        "config_sha256": digest(root / "config/config.yaml"),
        "image_digest": cfg["runtime"]["image_digest"],
        "seed": cfg["train"]["seed"],
    }


def track(root, *paths):
    """Create local DVC pointers; this neither stages Git nor uploads data."""
    subprocess.run(
        [sys.executable, "-m", "dvc", "add", *[str(p) for p in paths]],
        cwd=root,
        check=True,
        stdout=subprocess.DEVNULL,
    )
