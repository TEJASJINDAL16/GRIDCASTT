"""Dependency-free handover: archive keeps running until a champion is ready."""

import json
import pathlib
import re


def image_reference(root):
    path = root / "models/champion.json"
    if not path.exists():
        return ""
    metadata = json.loads(path.read_text(encoding="utf-8"))
    reference = metadata.get("pins", {}).get("image_digest") or ""
    if metadata.get("approved") and re.fullmatch(
        r"ghcr\.io/[a-z0-9_./-]+@sha256:[a-f0-9]{64}", reference
    ):
        return reference
    return ""


if __name__ == "__main__":
    print(image_reference(pathlib.Path(__file__).resolve().parent.parent))
