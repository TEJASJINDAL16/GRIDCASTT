"""All report and dashboard charts use these static SVG renderers."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np


def lines(path, x, series, ylabel, *, thresholds=(), pending=None, timezone=None):
    fig, ax = plt.subplots(figsize=(11, 3.1), layout="constrained")
    palette = ["#087f5b", "#9c4a26", "#52616b"]
    for (name, values), color in zip(series.items(), palette, strict=False):
        ax.plot(x, values, label=name, color=color, linewidth=1.7)
    for label, value in thresholds:
        if value is not None and np.isfinite(value):
            ax.axhline(value, color="#c92a2a", linestyle="--", label=label)
    if pending is not None and len(x):
        ax.axvspan(
            pending, max(x), facecolor="#f1f3f5", hatch="///", alpha=0.6, label="Pending actuals"
        )
    ax.axhline(0, color="#adb5bd", linewidth=0.6)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="best", fontsize=8)
    if timezone:
        locator = mdates.AutoDateLocator(tz=timezone)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator, tz=timezone))
        ax.set_xlabel(timezone)
    fig.autofmt_xdate()
    fig.savefig(path, format="svg")
    plt.close(fig)


def bars(path, labels, model, baseline, counts, ylabel):
    fig, ax = plt.subplots(figsize=(11, 3.1), layout="constrained")
    x = np.arange(len(labels))
    ax.bar(x - 0.2, model, width=0.4, label="Model", color="#087f5b")
    ax.bar(x + 0.2, baseline, width=0.4, label="Seasonal naive", color="#9c4a26")
    ax.set_xticks(
        x,
        [f"{label}\nn={count:,}" for label, count in zip(labels, counts, strict=True)],
        fontsize=8,
    )
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.18)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.savefig(path, format="svg")
    plt.close(fig)
