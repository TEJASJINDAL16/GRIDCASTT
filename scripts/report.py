"""Render the static dashboard."""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src.config import PROJECT_ROOT, load_config
from src.viz.dashboard import publish

if __name__ == "__main__":
    print(publish(PROJECT_ROOT, load_config()))
