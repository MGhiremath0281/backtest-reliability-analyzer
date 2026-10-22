"""Command-line interface for the data-validation engine."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from .reporting import DEFAULT_REPORT_PATH, has_failures, print_console, write_json
from .runner import run_validation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bra",
        description=(
            "Validate collected NSE datasets and write a JSON report. "
            "Source files are only read, never modified."
        ),
    )
    parser.add_argument(
        "--data-root",
        default="data",
        help="Root of the collected data tree (default: data).",
    )
    parser.add_argument(
        "--json-report",
        default=DEFAULT_REPORT_PATH,
        help=(
            "Path for the machine-readable JSON report "
            f"(default: {DEFAULT_REPORT_PATH})."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show every finding instead of grouping repeated findings.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run validation and return a process exit code.

    Exit codes: 0 when there are no failures (warnings are allowed), 1 when at
    least one dataset fails, and 2 when the report cannot be written.
    """

    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report = run_validation(data_root)

    try:
        report_path = write_json(report, args.json_report)
    except OSError as exc:
        print(
            f"Could not write JSON report to {args.json_report}: {exc}",
            file=sys.stderr,
        )
        print_console(report, verbose=args.verbose)
        return 2

    print_console(
        report,
        report_path=report_path,
        verbose=args.verbose,
    )
    return 1 if has_failures(report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
