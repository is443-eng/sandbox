#!/usr/bin/env python3
"""
Batch-validate reports from a CSV. Expected columns (minimum):
  prompt_id, report_id, report_text
Optional:
  source_context — retrieval/source block passed to the validator for factual checks

Writes a CSV with Likert columns, booleans, quality_composite, details, optional error.

Progress: prints `[n/total]` lines and per-row results to stderr unless `--quiet`.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

# Allow running as script from 13_end2
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validation.validator import validate_report_safe  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser(description="Batch AI validation (Homework 3 rubric)")
    p.add_argument("--input", "-i", required=True, help="Input CSV path")
    p.add_argument("--output", "-o", required=True, help="Output CSV path")
    p.add_argument("--text-col", default="report_text", help="Column with report body")
    p.add_argument(
        "--source-col",
        default="source_context",
        help="Optional column with source/retrieval text (skip if missing in row)",
    )
    p.add_argument(
        "--provider",
        default=None,
        help="ollama or openai (default: env VALIDATION_AI_PROVIDER or ollama)",
    )
    p.add_argument("--sleep", type=float, default=0.5, help="Seconds between API calls")
    p.add_argument("--keep-raw", action="store_true", help="Include raw validator JSON text")
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress status lines (final summary still prints)",
    )
    args = p.parse_args()

    df = pd.read_csv(args.input)
    if args.text_col not in df.columns:
        raise SystemExit(f"Missing column {args.text_col!r}")

    total = len(df)
    rows_out = []
    prov = args.provider or "(env default)"
    if not args.quiet:
        print(
            f"validation: {total} row(s), provider={prov}",
            file=sys.stderr,
            flush=True,
        )

    for n, (idx, row) in enumerate(df.iterrows(), start=1):
        text = str(row[args.text_col])
        src = None
        if args.source_col in df.columns and pd.notna(row.get(args.source_col)):
            src = str(row[args.source_col])

        rid = row.get("report_id", idx)
        pid = row.get("prompt_id", "")
        if not args.quiet:
            print(
                f"validation [{n}/{total}] report_id={rid!r} prompt_id={pid!r} …",
                file=sys.stderr,
                flush=True,
            )

        r = validate_report_safe(text, source_context=src, provider=args.provider)
        out = {
            "prompt_id": row.get("prompt_id", ""),
            "report_id": row.get("report_id", idx),
            "factual_accuracy": r.get("factual_accuracy"),
            "completeness": r.get("completeness"),
            "structure": r.get("structure"),
            "spurs_bias": r.get("spurs_bias"),
            "uses_we_our_for_spurs": r.get("uses_we_our_for_spurs"),
            "opponent_named_fairly": r.get("opponent_named_fairly"),
            "quality_composite": r.get("quality_composite"),
            "details": r.get("details", ""),
            "error": r.get("error") or "",
        }
        if args.keep_raw:
            out["raw_validator_response"] = r.get("raw_validator_response", "")
        rows_out.append(out)

        if not args.quiet:
            err = (r.get("error") or "").strip()
            if err:
                msg = err.replace("\n", " ")
                if len(msg) > 160:
                    msg = msg[:157] + "..."
                print(f"  → error: {msg}", file=sys.stderr, flush=True)
            else:
                qc = r.get("quality_composite")
                fa = r.get("factual_accuracy")
                print(
                    f"  → quality_composite={qc} (factual_accuracy={fa})",
                    file=sys.stderr,
                    flush=True,
                )

        time.sleep(max(0.0, args.sleep))

    out_df = pd.DataFrame(rows_out)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.output, index=False)
    print(f"Wrote {len(out_df)} rows to {args.output}")


if __name__ == "__main__":
    main()
