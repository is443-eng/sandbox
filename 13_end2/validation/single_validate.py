#!/usr/bin/env python3
"""Validate one report from stdin or a text file (quick check)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from validation.validator import validate_report  # noqa: E402


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", "-f", help="Path to report .txt")
    g.add_argument("--stdin", action="store_true", help="Read report body from stdin")
    p.add_argument("--source", help="Optional path to source/retrieval text file")
    p.add_argument("--provider", default=None)
    p.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress status line on stderr before validating",
    )
    args = p.parse_args()

    if args.stdin:
        report_text = sys.stdin.read()
    else:
        report_text = Path(args.file).read_text(encoding="utf-8")

    src = Path(args.source).read_text(encoding="utf-8") if args.source else None
    if not args.quiet:
        prov = args.provider or "(env VALIDATION_AI_PROVIDER)"
        print(f"validation: calling provider={prov} …", file=sys.stderr, flush=True)
    out = validate_report(report_text, source_context=src, provider=args.provider)
    # Drop bulky raw for console
    raw = out.pop("raw_validator_response", None)
    print(json.dumps(out, indent=2))
    if raw:
        print("\n--- raw ---\n", raw[:2000], file=sys.stderr)


if __name__ == "__main__":
    main()
