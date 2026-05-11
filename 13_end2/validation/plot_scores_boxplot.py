#!/usr/bin/env python3
"""
Box plot of a numeric score column by prompt_id (e.g. quality_composite from scores.csv).

Example:
  cd 13_end2
  python3 validation/plot_scores_boxplot.py --scores validation/data/scores.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _prompt_order(ids: list[str]) -> list[str]:
    preferred = ["A", "B", "C", "D"]
    seen = set(ids)
    ordered = [p for p in preferred if p in seen]
    rest = sorted(p for p in ids if p not in ordered)
    return ordered + rest


def main() -> None:
    ap = argparse.ArgumentParser(description="Box plot of scores by prompt_id")
    ap.add_argument(
        "--scores",
        default=str(_ROOT / "validation" / "data" / "scores.csv"),
        help="CSV from batch_validate.py (default: validation/data/scores.csv)",
    )
    ap.add_argument(
        "--column",
        default="quality_composite",
        help="Numeric column to plot (default: quality_composite)",
    )
    ap.add_argument(
        "--out",
        "-o",
        default=str(_ROOT / "validation" / "data" / "quality_composite_boxplot.png"),
        help="Output PNG path",
    )
    ap.add_argument(
        "--title",
        default="",
        help="Figure title (default: auto from column name)",
    )
    args = ap.parse_args()

    path = Path(args.scores).expanduser().resolve()
    if not path.is_file():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(path)
    if "error" in df.columns:
        df = df[df["error"].isna() | (df["error"].astype(str) == "")]
    if args.column not in df.columns:
        print(f"Missing column {args.column!r}", file=sys.stderr)
        sys.exit(1)
    if "prompt_id" not in df.columns:
        print("Missing column 'prompt_id'", file=sys.stderr)
        sys.exit(1)

    df = df.copy()
    df["prompt_id"] = df["prompt_id"].astype(str).str.upper()
    df[args.column] = pd.to_numeric(df[args.column], errors="coerce")
    df = df.dropna(subset=[args.column])
    if df.empty:
        print("No numeric rows to plot.", file=sys.stderr)
        sys.exit(1)

    order = _prompt_order(df["prompt_id"].unique().tolist())
    plot_df = df[df["prompt_id"].isin(order)]

    fig, ax = plt.subplots(figsize=(6, 4.5), dpi=120)
    groups = [plot_df.loc[plot_df["prompt_id"] == p, args.column].values for p in order]
    labels = [f"{p}\n(n={len(g)})" for p, g in zip(order, groups)]

    bp = ax.boxplot(
        groups,
        tick_labels=labels,
        patch_artist=True,
        medianprops=dict(color="black", linewidth=1.5),
    )
    colors = ["#c6dbef", "#9ecae1", "#6baed6", "#4292c6"]
    for i, box in enumerate(bp["boxes"]):
        box.set_facecolor(colors[i % len(colors)])
        box.set_alpha(0.9)

    title = args.title.strip() or f"{args.column} by prompt condition"
    ax.set_title(title)
    ax.set_ylabel(args.column.replace("_", " ").title())
    ax.set_xlabel("Prompt ID")
    ax.grid(True, axis="y", alpha=0.35)
    ax.set_ylim(bottom=max(0.5, float(plot_df[args.column].min()) - 0.35))

    fig.tight_layout()
    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
