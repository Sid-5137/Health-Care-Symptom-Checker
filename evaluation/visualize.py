"""Visualize summary scores and status.

Requires pandas + matplotlib when run.
Usage:
  python evaluation/visualize.py --summary evaluation/results/summary_scores_<ts>.csv --details evaluation/results/scored_cases_<ts>.csv
Outputs PNG charts into evaluation/charts/
"""
from __future__ import annotations
import argparse
from pathlib import Path

CHARTS_DIR_NAME = "charts"


def load_df(path):  # lazy pandas import
    try:
        import pandas as pd  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("pandas required: pip install pandas") from e
    return pd.read_csv(path)


def save_bar(ax, title: str, ylabel: str = "score"):
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("model")
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_horizontalalignment("right")
    ax.grid(axis="y", linestyle=":", alpha=0.4)


def visualize(summary_csv: Path, details_csv: Path | None):
    try:
        import matplotlib.pyplot as plt  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("matplotlib required: pip install matplotlib") from e
    import math

    summary_df = load_df(summary_csv)
    outdir = summary_csv.parent.parent / CHARTS_DIR_NAME
    outdir.mkdir(parents=True, exist_ok=True)

    # Pillar bars
    for col in ["correctness_score", "reasoning_score", "safety_score", "overall_score"]:
        ax = summary_df.sort_values(col, ascending=False).plot(
            kind="bar", x="model", y=col, figsize=(8,4), color="#4C78A8"
        )
        save_bar(ax, f"{col} by model")
        plt.tight_layout()
        plt.savefig(outdir / f"{col}.png", dpi=150)
        plt.close()

    # Optional radar chart (skip if <2 models)
    if len(summary_df) >= 2:
        import numpy as np  # type: ignore
        cols = ["correctness_score", "reasoning_score", "safety_score"]
        angles = np.linspace(0, 2 * np.pi, len(cols), endpoint=False)
        angles = np.concatenate((angles, [angles[0]]))
        fig, ax = plt.subplots(subplot_kw=dict(polar=True), figsize=(6,6))
        for _, row in summary_df.iterrows():
            values = row[cols].tolist()
            values.append(values[0])
            ax.plot(angles, values, label=row['model'])
            ax.fill(angles, values, alpha=0.1)
        ax.set_thetagrids(angles[:-1] * 180/np.pi, cols)
        ax.set_title('Pillar Radar')
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        plt.tight_layout()
        plt.savefig(outdir / 'pillar_radar.png', dpi=150)
        plt.close()

    print(f"Charts saved to {outdir}")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--summary", type=Path, required=True, help="summary_scores CSV path")
    p.add_argument("--details", type=Path, required=False, help="scored_cases CSV path (optional)")
    return p.parse_args()


def main():
    args = parse_args()
    visualize(args.summary, args.details)


if __name__ == "__main__":
    main()
