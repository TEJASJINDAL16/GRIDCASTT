"""Configuration loader.

One place reads config.yaml and .env; every other module imports from here.
"""

import os
import pathlib

import yaml

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent


def load_config() -> dict:
    """Parse config/config.yaml and return it as a dict."""
    with open(PROJECT_ROOT / "config" / "config.yaml") as f:
        return yaml.safe_load(f)


def get_api_key(name: str = "EM_API_KEY") -> str:
    """Read a secret from the environment, falling back to a local .env file.

    The .env file is gitignored, so keys never reach the repository.
    """
    value = os.environ.get(name, "").strip()
    if value:
        return value

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            if key.strip() == name:
                return val.strip().strip('"').strip("'")

    raise RuntimeError(
        f"{name} not found. Copy .env.example to .env and add your key."
    )
