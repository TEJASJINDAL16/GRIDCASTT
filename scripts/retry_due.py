"""Dependency-free workflow preflight using policy recorded by the daily job."""

import json
import pathlib
from datetime import UTC, datetime


def due(root, now):
    records = sorted((root / "state/runs").glob("*-daily.json"))
    if not records:
        return False
    status = json.loads(records[-1].read_text(encoding="utf-8"))
    return bool(
        status.get("retry_needed")
        and status.get("retry_deadline")
        and now <= datetime.fromisoformat(status["retry_deadline"])
        and status.get("consecutive_failures", 0) < status["max_failures"]
    )


if __name__ == "__main__":
    print(str(due(pathlib.Path(__file__).resolve().parent.parent, datetime.now(UTC))).lower())
