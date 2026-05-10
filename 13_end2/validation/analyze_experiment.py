#!/usr/bin/env python3
"""
Statistical analysis for Homework 3: prompt conditions (typically A–C baseline + experiments).

Primary outcome (default): quality_composite — mean of
  factual_accuracy, completeness, structure, (6 - spurs_bias), each on 1–5.

Also runs one-way ANOVA on spurs_bias (lower is better for neutral tone).

Welch t-tests: baseline vs each other prompt_id present in the CSV.
Bonferroni alpha = 0.05 / k where k = number of contrasts (non-baseline groups).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _series(df: pd.DataFrame, col: str, prompt: str) -> np.ndarray:
    s = df.loc[df["prompt_id"].astype(str).str.upper() == prompt, col].dropna()
    return s.astype(float).values


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, help="CSV from batch_validate.py")
    ap.add_argument(
        "--primary",
        default="quality_composite",
        help="Primary outcome column (default: quality_composite)",
    )
    ap.add_argument(
        "--baseline",
        default="A",
        help="Baseline prompt id for contrasts (default: A)",
    )
    args = ap.parse_args()

    def resolve_scores_csv(arg: str) -> Path:
        p = Path(arg).expanduser()
        if p.is_file():
            return p.resolve()
        rel = Path.cwd() / p
        if rel.is_file():
            return rel.resolve()
        end2 = Path(__file__).resolve().parent.parent
        under_end2 = end2 / arg
        if under_end2.is_file():
            return under_end2.resolve()
        return rel.resolve()

    scores_path = resolve_scores_csv(args.scores)
    if not scores_path.is_file():
        end2 = Path(__file__).resolve().parent.parent
        hint = (
            f"File not found: {args.scores!r} (resolved from cwd {Path.cwd()})\n\n"
            "Produce scores with batch validation, e.g.:\n"
            f"  cd {end2}\n"
            "  python3 validation/batch_validate.py "
            "-i validation/data/reports_batch.csv -o validation/data/scores.csv\n\n"
            "Or run analysis on the bundled example:\n"
            "  python3 validation/analyze_experiment.py "
            "--scores validation/data/scores_example.csv\n"
        )
        print(hint, file=sys.stderr)
        sys.exit(1)

    df = pd.read_csv(scores_path)
    if "error" in df.columns:
        df = df[df["error"].isna() | (df["error"].astype(str) == "")]
    if args.primary not in df.columns:
        raise SystemExit(f"Column {args.primary!r} not in CSV")

    sub_ids = df["prompt_id"].astype(str).str.upper()
    prompts_present = sorted(sub_ids.unique().tolist())

    groups = [_series(df, args.primary, p) for p in prompts_present]
    if any(len(g) == 0 for g in groups):
        missing = [p for p, g in zip(prompts_present, groups) if len(g) == 0]
        print(
            "Warning: no scores for prompt(s):",
            missing,
            "(ANOVA may be invalid).",
            file=sys.stderr,
        )

    print("=== Summary by prompt_id ===")
    sub = df.copy()
    sub["prompt_id"] = sub["prompt_id"].astype(str).str.upper()
    gstat = sub.groupby("prompt_id")[args.primary].agg(["count", "mean", "std", "min", "max"])
    print(gstat.to_string())
    print()

    valid_groups = [g for g in groups if len(g) > 0]
    if len(valid_groups) >= 2:
        f_stat, p_anova = stats.f_oneway(*valid_groups)
        print(f"One-way ANOVA on {args.primary} (non-empty groups only):")
        print(f"  F = {f_stat:.4f}, p = {p_anova:.6g}")
        print()

    # spurs_bias ANOVA (same groups)
    if "spurs_bias" in df.columns:
        sg = [_series(df, "spurs_bias", p) for p in prompts_present]
        sg = [g for g in sg if len(g) > 0]
        if len(sg) >= 2:
            f2, p2 = stats.f_oneway(*sg)
            print("One-way ANOVA on spurs_bias (5 = max Spurs bias):")
            print(f"  F = {f2:.4f}, p = {p2:.6g}")
            print()

    base = args.baseline.upper()
    others = [p for p in prompts_present if p != base]
    k_contrasts = max(1, len(others))
    bonf = 0.05 / k_contrasts
    print(
        f"Welch t-tests vs baseline {base} "
        f"(Bonferroni alpha for {len(others)} contrast(s) ≈ {bonf:.4f}):"
    )
    a_vals = _series(df, args.primary, base)
    if len(a_vals) == 0:
        print(f"  No rows for baseline {base}; skipping contrasts.")
    else:
        for other in others:
            o_vals = _series(df, args.primary, other)
            if len(o_vals) == 0:
                continue
            t, p = stats.ttest_ind(a_vals, o_vals, equal_var=False)
            sig = " *" if p < bonf else ""
            print(f"  {base} vs {other}: t = {t:.4f}, p = {p:.6g}{sig}")
    print()
    print("Interpretation: for quality_composite, higher is better.")
    print("For spurs_bias alone, lower is better (less homer tone).")


if __name__ == "__main__":
    main()
