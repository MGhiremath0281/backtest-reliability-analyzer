"""Command-line interface for the data-validation engine."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from .parsing import parse_date
from .reporting import DEFAULT_REPORT_PATH, has_failures, print_console, write_json
from .runner import run_validation
from .validators.survivorship import BacktestConfig


def _backtest_date(value: str) -> date:
    """argparse type: parse a backtest date or fail with a clear message."""

    parsed = parse_date(value)
    if parsed is None:
        raise argparse.ArgumentTypeError(
            f"could not parse date {value!r} "
            "(expected YYYY-MM-DD, DD-Mon-YYYY, or DD/MM/YYYY)"
        )
    return parsed


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
    backtest = parser.add_argument_group(
        "backtest assessment",
        (
            "Optionally assess one backtest against the collected data. "
            "Without these flags only the general survivorship data-coverage "
            "audit runs; backtest-specific results are reported as "
            "unavailable."
        ),
    )
    backtest.add_argument(
        "--backtest-index",
        default=None,
        help=(
            "Target index or universe name whose dated membership snapshots "
            "define the universe (for example: 'NIFTY 50')."
        ),
    )
    backtest.add_argument(
        "--backtest-start",
        type=_backtest_date,
        default=None,
        help="Backtest interval start date (inclusive).",
    )
    backtest.add_argument(
        "--backtest-end",
        type=_backtest_date,
        default=None,
        help="Backtest interval end date (inclusive).",
    )
    backtest.add_argument(
        "--backtest-symbol",
        action="append",
        default=[],
        metavar="SYMBOL",
        help=(
            "Explicit universe symbol; repeat for multiple symbols. Used "
            "instead of, or together with, --backtest-index."
        ),
    )
    backtest.add_argument(
        "--backtest-min-price-coverage",
        type=float,
        default=None,
        metavar="RATIO",
        help=(
            "Required per-symbol price coverage ratio in [0, 1] inside the "
            "backtest interval. Symbols below it are reported; no rows are "
            "dropped."
        ),
    )
    return parser


def _backtest_config(args: argparse.Namespace) -> BacktestConfig | None:
    """Build a BacktestConfig when any backtest flag was supplied."""

    if not (
        args.backtest_index
        or args.backtest_start
        or args.backtest_end
        or args.backtest_symbol
        or args.backtest_min_price_coverage is not None
    ):
        return None
    return BacktestConfig(
        target_index=args.backtest_index,
        universe_symbols=tuple(
            symbol.strip().upper() for symbol in args.backtest_symbol if symbol.strip()
        ),
        start_date=args.backtest_start,
        end_date=args.backtest_end,
        min_price_coverage=args.backtest_min_price_coverage,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run validation and return a process exit code.

    Exit codes: 0 when there are no failures (warnings are allowed), 1 when at
    least one dataset fails, and 2 when the report cannot be written. Invalid
    backtest inputs that argparse can detect (unparseable dates) exit with 2
    as a command-line usage error; logically inconsistent backtest windows are
    reported as warnings inside the report instead.
    """

    args = build_parser().parse_args(argv)
    data_root = Path(args.data_root)
    report = run_validation(data_root, backtest=_backtest_config(args))

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
