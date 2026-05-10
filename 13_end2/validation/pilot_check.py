#!/usr/bin/env python3
"""
Pilot / variance check: summarize scores by prompt_id and warn on narrow spread (ceiling/floor effects).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, help="CSV from batch_validate.py")
    ap.add_argument(
        "--warn-range",
        type=float,
        default=0.75,
        help="Warn if per-prompt mean range on spurs_bias or composite is below this (default 0.75)",
    )
    args = ap.parse_args()

    df = pd.read_csv(args.scores)
    if "error" in df.columns:
        df = df[df["error"].isna() | (df["error"].astype(str) == "")]
    if df.empty:
        print("No valid rows.", file=sys.stderr)
        sys.exit(1)

    df["prompt_id"] = df["prompt_id"].astype(str).str.upper()

    cols = [c for c in ("quality_composite", "spurs_bias", "factual_accuracy") if c in df.columns]
    print("Per-prompt means:")
    print(df.groupby("prompt_id")[cols].mean().to_string())
    print()

    for col in cols:
        means = df.groupby("prompt_id")[col].mean()
        r = float(means.max() - means.min()) if len(means) > 1 else 0.0
        print(f"Mean range for {col}: {r:.3f}")
        if r < args.warn_range:
            print(
                f"  ** Warning: range < {args.warn_range} — scores may be too clustered for strong inference.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
