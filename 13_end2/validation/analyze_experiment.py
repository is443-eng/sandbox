#!/usr/bin/env python3
"""
Statistical analysis for Homework 3: prompt conditions (typically A–C baseline + experiments).

Primary outcome (default): quality_composite — mean of
  factual_accuracy, completeness, structure, (6 - spurs_bias), each on 1–5.

Recommended for B vs C manipulation checks (run separately):
  --primary completeness
  --primary spurs_bias

Also runs one-way ANOVA on spurs_bias when present (lower is better for neutral tone).

Welch t-tests: baseline vs each other prompt_id present in the CSV.
Optional planned contrast: --contrast B C on --primary (e.g. B vs C on completeness).

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


def cohens_d_pooled(x: np.ndarray, y: np.ndarray) -> float:
    """Pooled-SD Cohen's d: (mean(x) - mean(y)) / s_pooled. NaN if degenerate."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 2 or len(y) < 2:
        return float("nan")
    nx, ny = len(x), len(y)
    vx = float(np.var(x, ddof=1))
    vy = float(np.var(y, ddof=1))
    denom = nx + ny - 2
    if denom <= 0:
        return float("nan")
    sp = np.sqrt(((nx - 1) * vx + (ny - 1) * vy) / denom)
    if sp == 0.0:
        return 0.0 if float(np.mean(x)) == float(np.mean(y)) else float("nan")
    return (float(np.mean(x)) - float(np.mean(y))) / sp


def _print_pairwise_descriptive(
    df: pd.DataFrame,
    col: str,
    prompts: list[str],
    *,
    higher_is_better: bool,
) -> None:
    """Means, mean differences, and Cohen's d for every unordered pair (for write-ups)."""
    print("=== Pairwise descriptive differences (same outcome as primary) ===")
    dir_note = (
        "Positive Δmean: first prompt higher on this metric (better if higher is better)."
        if higher_is_better
        else "Positive Δmean: first prompt higher spurs_bias (more homer tone; lower mean is better)."
    )
    print(
        f"Δmean = mean(first) − mean(second). {dir_note} "
        "Cohen's d uses pooled SD. "
        "Use for **effect size / magnitude**; inferential tests are in the Welch rows above."
    )
    for i, p1 in enumerate(prompts):
        for p2 in prompts[i + 1 :]:
            v1 = _series(df, col, p1)
            v2 = _series(df, col, p2)
            if len(v1) == 0 or len(v2) == 0:
                continue
            m1, m2 = float(np.mean(v1)), float(np.mean(v2))
            diff = m1 - m2
            d = cohens_d_pooled(v1, v2)
            direction = ""
            if higher_is_better:
                if diff > 0.01:
                    direction = f" ({p1} higher on average)"
                elif diff < -0.01:
                    direction = f" ({p2} higher on average)"
            else:
                if diff > 0.01:
                    direction = f" ({p1} more Spurs-biased on average)"
                elif diff < -0.01:
                    direction = f" ({p2} more Spurs-biased on average)"
            print(
                f"  {p1} vs {p2}: mean({p1})={m1:.3f}, mean({p2})={m2:.3f}, "
                f"Δmean={diff:+.3f}{direction}, Cohen's d={d:.3f} (n={len(v1)},{len(v2)})"
            )
    print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True, help="CSV from batch_validate.py")
    ap.add_argument(
        "--primary",
        default="quality_composite",
        metavar="COL",
        help=(
            "Outcome column: quality_composite | factual_accuracy | completeness | "
            "structure | spurs_bias (default: quality_composite). "
            "For B vs C effects try completeness or spurs_bias separately."
        ),
    )
    ap.add_argument(
        "--baseline",
        default="A",
        help="Baseline prompt id for contrasts (default: A)",
    )
    ap.add_argument(
        "--contrast",
        nargs=2,
        metavar=("P1", "P2"),
        default=None,
        help=(
            "Planned pairwise Welch t-test on --primary between two prompt ids "
            "(e.g. B C for B vs C). Uses Bonferroni alpha with baseline contrasts count."
        ),
    )
    ap.add_argument(
        "--all-likerts",
        action="store_true",
        help=(
            "After primary analysis, print mean±std by prompt for each rubric Likert "
            "(factual_accuracy, completeness, structure, spurs_bias) when columns exist."
        ),
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
    n_planned = 1 if args.contrast is not None else 0
    n_baseline = len(others)
    n_tests = max(1, n_baseline + n_planned)
    bonf = 0.05 / n_tests
    print(
        f"Welch t-tests vs baseline {base} "
        f"(Bonferroni α ≈ {bonf:.4f} for {n_tests} test(s): "
        f"{n_baseline} vs baseline"
        + (f", plus planned contrast" if n_planned else "")
        + "):"
    )
    higher_is_better = args.primary != "spurs_bias"

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
            dm = float(np.mean(a_vals)) - float(np.mean(o_vals))
            d = cohens_d_pooled(a_vals, o_vals)
            print(
                f"  {base} vs {other}: t = {t:.4f}, p = {p:.6g}{sig} "
                f"(Δmean={dm:+.3f}, Cohen's d={d:.3f})"
            )

    if args.contrast is not None:
        p1, p2 = args.contrast[0].strip().upper(), args.contrast[1].strip().upper()
        v1 = _series(df, args.primary, p1)
        v2 = _series(df, args.primary, p2)
        print()
        print(f"Planned contrast Welch t-test ({p1} vs {p2}) on {args.primary}:")
        if len(v1) < 2 or len(v2) < 2:
            print("  Skipped: need at least 2 scores per group.")
        else:
            t_c, p_c = stats.ttest_ind(v1, v2, equal_var=False)
            sig_c = " *" if p_c < bonf else ""
            dm_c = float(np.mean(v1)) - float(np.mean(v2))
            d_c = cohens_d_pooled(v1, v2)
            print(
                f"  t = {t_c:.4f}, p = {p_c:.6g}{sig_c} "
                f"(Δmean={p1}−{p2}={dm_c:+.3f}, Cohen's d={d_c:.3f})"
            )

    print()
    _print_pairwise_descriptive(
        df, args.primary, prompts_present, higher_is_better=higher_is_better
    )

    if args.all_likerts:
        likert_cols = [
            c
            for c in (
                "factual_accuracy",
                "completeness",
                "structure",
                "spurs_bias",
            )
            if c in df.columns
        ]
        if likert_cols:
            print("=== Mean (SD) by prompt_id — all rubric Likerts ===")
            sub2 = df.copy()
            sub2["prompt_id"] = sub2["prompt_id"].astype(str).str.upper()
            for col in likert_cols:
                print(f"\n{col}:")
                for pid in prompts_present:
                    s = sub2.loc[sub2["prompt_id"] == pid, col].dropna().astype(float)
                    if len(s) == 0:
                        continue
                    print(
                        f"  {pid}: M={float(s.mean()):.3f}, SD={float(s.std(ddof=1)):.3f}, n={len(s)}"
                    )
            print()

    print("=== One sentence for your write-up (edit as needed) ===")
    m_parts = []
    for p in prompts_present:
        v = _series(df, args.primary, p)
        if len(v):
            m_parts.append(f"{p} M={float(np.mean(v)):.2f} (SD={float(np.std(v, ddof=1)):.2f}, n={len(v)})")
    metric_note = (
        "higher is better on this metric"
        if higher_is_better
        else "lower is better (less Spurs bias)"
    )
    print(
        "Prompts differed in **average** "
        + f"{args.primary} ({metric_note}) "
        + "; ".join(m_parts)
        + ". "
        "Welch tests and ANOVA above address whether those **average** differences are "
        "large relative to within-prompt variability (statistical significance). "
        "You can still report **descriptive** differences and Cohen's d from the pairwise block."
    )
    print()

    if args.primary == "spurs_bias":
        print("Interpretation: for spurs_bias, lower is better (less homer tone).")
    elif args.primary == "quality_composite":
        print("Interpretation: for quality_composite, higher is better.")
    else:
        print(
            f"Interpretation: for {args.primary}, higher is better unless your rubric "
            "states otherwise (spurs_bias: lower is better)."
        )


if __name__ == "__main__":
    main()
