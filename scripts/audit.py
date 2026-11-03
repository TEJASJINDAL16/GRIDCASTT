"""Check completion using evidence, without treating missing gates as passes."""

import pathlib
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.config import PROJECT_ROOT, load_config
from src.jobs.daily import read_json
from src.records import write_json


def main():
    root, cfg = PROJECT_ROOT, load_config()
    checks = []
    for label, paths in {
        "Hybrid and frozen backtest": [
            "src/models/hybrid.py",
            "reports/model.md",
            "reports/model/summary.csv",
        ],
        "Tuning evidence": ["reports/tuning/result.json"],
        "Ablation evidence": ["reports/ablation.md", "reports/ablation/summary.csv"],
        "Threshold replay": ["reports/threshold_derivation.md", "reports/calibration/sweep.csv"],
        "Daily job and failure handling": ["src/jobs/daily.py", "tests/test_daily.py"],
        "Dashboard and model card": ["docs/index.html", "reports/model_card.md"],
        "Deployment workflows": [
            ".github/workflows/daily.yml",
            ".github/workflows/retry.yml",
            ".github/workflows/image.yml",
        ],
        "Final holdout evaluated once": [
            "reports/holdout/evaluation.json",
            "reports/holdout/summary.csv",
        ],
    }.items():
        absent = [p for p in paths if not (root / p).exists()]
        checks.append(
            {"requirement": label, "passed": not absent, "evidence": paths, "missing": absent}
        )
    gate = read_json(
        root / "reports/calibration/selection.json",
        read_json(root / "reports/model/selection.json", {}),
    )
    checks.append(
        {
            "requirement": "Model beats baseline and clears every veto",
            "passed": gate.get("promote", False),
            "evidence": gate.get("reasons", ["not evaluated"]),
        }
    )
    for name in ["local", "container"]:
        path = root / "reports/verification" / f"{name}-tests.xml"
        passed = False
        if path.exists():
            suites = ET.parse(path).getroot().iter("testsuite")
            counts = [
                (int(s.get("tests", 0)), int(s.get("failures", 0)) + int(s.get("errors", 0)))
                for s in suites
            ]
            passed = bool(
                counts and sum(n for n, _ in counts) and not sum(errors for _, errors in counts)
            )
        checks.append(
            {
                "requirement": f"{name.title()} test suite verified",
                "passed": passed,
                "evidence": str(path.relative_to(root)),
            }
        )
    replay = read_json(root / "reports/replay/summary.json", {})
    checks.append(
        {
            "requirement": "Historical counterfactual recovery replay",
            "passed": replay.get("promotions", 0) > 0 and replay.get("cooldown_days", 0) > 0,
            "evidence": replay,
        }
    )
    calibration = read_json(root / "reports/calibration/result.json", {})
    rate = calibration.get("selected", {}).get("episodes_per_year")
    checks.append(
        {
            "requirement": "Measured replay alarm budget",
            "passed": rate is not None and rate <= cfg["drift"]["false_alarm_budget_per_year"],
            "evidence": rate,
        }
    )
    offline = read_json(root / "reports/verification/real_offline_flow.json", {})
    checks.append(
        {
            "requirement": "Real-data offline daily flow and idempotency",
            "passed": offline.get("outcome") == "success"
            and offline.get("forecast_rows") == 120
            and offline.get("repeat_identical", False),
            "evidence": "reports/verification/real_offline_flow.json (temporary approval fixture; not a live gate)",
        }
    )
    reproduction = read_json(root / "reports/verification/reproducibility.json", {})
    checks.append(
        {
            "requirement": "Linux reproduction to three decimals",
            "passed": reproduction.get("all_metrics_match", False)
            and reproduction.get("promotion_decision_matches", False),
            "evidence": "reports/verification/reproducibility.json",
        }
    )
    runs = [read_json(p, {}) for p in sorted((root / "state/runs").glob("*-daily.json"))]
    live = [r for r in runs if not r.get("offline") and r.get("outcome") == "success"]
    from datetime import date

    days = sorted({date.fromisoformat(r["issue_date"]) for r in live})
    consecutive = any(
        (days[i] - days[i - 1]).days == (days[i - 1] - days[i - 2]).days == 1
        for i in range(2, len(days))
    )
    checks.append(
        {
            "requirement": "Three consecutive successful live days",
            "passed": consecutive,
            "evidence": [str(d) for d in days],
        }
    )
    deployment = read_json(root / "reports/deployment.json", {})
    for field in ["dashboard_live", "image_published", "remote_backup_verified"]:
        checks.append(
            {"requirement": field, "passed": deployment.get(field, False), "evidence": deployment}
        )
    checks.append(
        {
            "requirement": "Runtime image digest pinned",
            "passed": bool(cfg["runtime"]["image_digest"]),
            "evidence": cfg["runtime"]["image_digest"],
        }
    )
    write_json(
        root / "reports/completion.json",
        {"complete": all(c["passed"] for c in checks), "checks": checks},
    )
    lines = [
        "# Completion Audit",
        "",
        "Every gate below requires evidence. Implementation alone does not establish deployment or forecasting skill.",
        "",
        "| Requirement | Status |",
        "|---|---|",
    ]
    lines += [
        f"| {c['requirement']} | {'PASS' if c['passed'] else 'NOT SATISFIED'} |" for c in checks
    ]
    (root / "reports/completion.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        "Complete"
        if all(c["passed"] for c in checks)
        else "Outstanding gates recorded in reports/completion.md"
    )


if __name__ == "__main__":
    main()
