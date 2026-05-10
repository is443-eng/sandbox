#!/usr/bin/env python3
"""
Homework 3: run lab_spurs_multi_agent.py for each (--gen-prompt × replicate), parse stdout,
and write reports_batch.csv for batch_validate.py.

Total subprocess runs = len(prompts) × replicates (default prompts A,B,C → e.g. 3 × 10 = 30).
If --validate is set, batch_validate runs once per row (same count of validator API calls).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd

_HERE = Path(__file__).resolve().parent
_END2 = _HERE.parent

AGENT1_MARKER = "--- Agent 1 (retrieval via tool) ---"
AGENT2_MARKER = "--- Agent 2 (report, no tools) ---"


def parse_lab_stdout(stdout: str) -> tuple[str, str, str | None]:
    """
    Split Agent 1 retrieval block vs Agent 2 report.
    Returns (report_text, source_context, error_message_or_none).
    """
    if AGENT2_MARKER not in stdout:
        return "", "", "missing Agent 2 marker in stdout"
    before, after = stdout.split(AGENT2_MARKER, 1)
    report_text = after.strip()
    if not report_text:
        return "", "", "empty report after Agent 2 marker"
    if AGENT1_MARKER not in before:
        return report_text, "", "missing Agent 1 marker (report kept)"

    _, middle = before.split(AGENT1_MARKER, 1)
    source = middle.strip()
    # Optional single-line note from lab (deterministic routing)
    if source.startswith("(deterministic routing"):
        nl = source.find("\n")
        if nl != -1:
            source = source[nl + 1 :].strip()
    # Strip other leading parenthetical one-liners if model adds noise
    while source.startswith("(") and ")" in source[:200]:
        close = source.find(")")
        if close != -1 and close < 300:
            rest = source[close + 1 :].lstrip()
            if rest.startswith("\n"):
                source = rest[1:].strip()
            else:
                source = rest.strip()
        else:
            break

    return report_text, source, None


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Batch-generate Spurs reports for HW3 (prompts A–C) and optional validate/analyze."
    )
    ap.add_argument(
        "--query",
        default=(
            "Give me a recap of the Spurs' latest game in the database."
        ),
        help="User question passed to the lab (same for all runs unless you script externally).",
    )
    ap.add_argument(
        "-n",
        "--replicates",
        type=int,
        default=5,
        metavar="N",
        help="Reports per prompt (balanced design). Default: 5.",
    )
    ap.add_argument(
        "--prompts",
        default="A,B,C",
        help="Comma-separated gen prompts (default: A,B,C).",
    )
    ap.add_argument(
        "--lab",
        type=Path,
        default=_END2 / "spurs_reporter" / "lab_spurs_multi_agent.py",
        help="Path to lab_spurs_multi_agent.py",
    )
    ap.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter for subprocess (default: sys.executable)",
    )
    ap.add_argument("--model", default=None, help="Forwarded to lab --model")
    ap.add_argument("--db", default=None, help="Forwarded to lab --db")
    ap.add_argument("--season", default=None, metavar="YYYY-YY", help="Forwarded to lab --season")
    ap.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Forwarded to lab --limit",
    )
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=_END2 / "validation" / "data" / "reports_batch.csv",
        help="Output CSV path (default: 13_end2/validation/data/reports_batch.csv)",
    )
    ap.add_argument(
        "--scores-out",
        type=Path,
        default=_END2 / "validation" / "data" / "scores.csv",
        help="Scores CSV when using --validate (default: validation/data/scores.csv under 13_end2)",
    )
    ap.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="If set, save full stdout per run (e.g. A_01.txt)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds between lab subprocess calls",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned runs only; do not invoke the lab",
    )
    ap.add_argument(
        "--validate",
        action="store_true",
        help="After CSV is written, run batch_validate.py -> --scores-out",
    )
    ap.add_argument(
        "--analyze",
        action="store_true",
        help="Run analyze_experiment.py on --scores-out (after --validate if used)",
    )
    ap.add_argument(
        "--validation-provider",
        default=None,
        help="Forwarded to batch_validate --provider",
    )
    args = ap.parse_args()

    lab_path = args.lab.resolve()
    if not lab_path.is_file():
        print(f"Lab script not found: {lab_path}", file=sys.stderr)
        sys.exit(1)

    cwd = lab_path.parent
    prompts = [p.strip().upper() for p in args.prompts.split(",") if p.strip()]
    for p in prompts:
        if p not in ("A", "B", "C"):
            print(f"Invalid prompt id {p!r}; expected A, B, or C", file=sys.stderr)
            sys.exit(1)

    total_runs = len(prompts) * args.replicates
    print(
        f"Design: {len(prompts)} prompts × {args.replicates} replicates = {total_runs} lab runs.",
        file=sys.stderr,
    )

    if args.dry_run:
        rid = 0
        for prompt in prompts:
            for rep in range(1, args.replicates + 1):
                rid += 1
                print(f"  {rid:3d}  prompt={prompt}  replicate={rep}")
        sys.exit(0)

    rows: list[dict] = []
    failures: list[tuple[str, int, str]] = []

    for prompt in prompts:
        for rep in range(1, args.replicates + 1):
            cmd = [
                args.python,
                str(lab_path),
                args.query,
                "--gen-prompt",
                prompt,
            ]
            if args.model:
                cmd.extend(["--model", args.model])
            if args.db:
                cmd.extend(["--db", args.db])
            if args.season is not None:
                cmd.extend(["--season", args.season])
            if args.limit is not None:
                cmd.extend(["--limit", str(args.limit)])

            proc = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=600,
            )
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""

            if args.raw_dir:
                args.raw_dir.mkdir(parents=True, exist_ok=True)
                raw_file = args.raw_dir / f"{prompt}_{rep:02d}.txt"
                raw_file.write_text(
                    f"=== STDOUT ===\n{stdout}\n\n=== STDERR ===\n{stderr}\n",
                    encoding="utf-8",
                )

            if proc.returncode != 0:
                failures.append(
                    (prompt, rep, f"exit {proc.returncode}: {stderr[:500]}")
                )
                print(
                    f"FAIL {prompt} rep={rep} rc={proc.returncode}",
                    file=sys.stderr,
                )
                time.sleep(max(0.0, args.sleep))
                continue

            report_text, source_context, perr = parse_lab_stdout(stdout)
            if perr or not report_text:
                msg = perr or "empty report"
                failures.append((prompt, rep, msg))
                print(f"FAIL {prompt} rep={rep} parse: {msg}", file=sys.stderr)
                time.sleep(max(0.0, args.sleep))
                continue

            rows.append(
                {
                    "prompt_id": prompt,
                    "report_id": len(rows) + 1,
                    "replicate": rep,
                    "report_text": report_text,
                    "source_context": source_context,
                }
            )
            print(f"OK   {prompt} rep={rep} id={len(rows)}", file=sys.stderr)
            time.sleep(max(0.0, args.sleep))

    if not rows:
        print("No successful rows; not writing CSV.", file=sys.stderr)
        sys.exit(2)

    out_path = args.out_csv
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    print(f"Wrote {len(rows)} rows to {out_path}", file=sys.stderr)

    if failures:
        print(f"\n{len(failures)} run(s) failed:", file=sys.stderr)
        for prompt, rep, msg in failures:
            print(f"  {prompt} rep={rep}: {msg[:120]}", file=sys.stderr)

    rc = 0 if not failures else 1

    if args.validate:
        bv = _HERE / "batch_validate.py"
        vcmd = [
            args.python,
            str(bv),
            "-i",
            str(out_path),
            "-o",
            str(args.scores_out),
        ]
        if args.validation_provider:
            vcmd.extend(["--provider", args.validation_provider])
        print(f"\nRunning: {' '.join(vcmd)}", file=sys.stderr)
        vrc = subprocess.call(vcmd, cwd=str(_END2))
        if vrc != 0:
            rc = vrc
        elif args.analyze:
            av = _HERE / "analyze_experiment.py"
            acmd = [
                args.python,
                str(av),
                "--scores",
                str(args.scores_out),
            ]
            print(f"Running: {' '.join(acmd)}", file=sys.stderr)
            arc = subprocess.call(acmd, cwd=str(_END2))
            if arc != 0:
                rc = arc
    elif args.analyze:
        av = _HERE / "analyze_experiment.py"
        scores_path = args.scores_out
        if not scores_path.is_file():
            print(
                f"--analyze requires scores at {scores_path} "
                "(run with --validate first or generate scores separately).",
                file=sys.stderr,
            )
            sys.exit(1)
        acmd = [args.python, str(av), "--scores", str(scores_path)]
        print(f"Running: {' '.join(acmd)}", file=sys.stderr)
        arc = subprocess.call(acmd, cwd=str(_END2))
        rc = arc

    raise SystemExit(rc)


if __name__ == "__main__":
    main()
