"""CLI entry point for ``python -m bra.prepare``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .runner import (
    DEFAULT_AUDIT_DOC,
    DEFAULT_AUDIT_JSON,
    DEFAULT_OUTPUT_DIR,
    prepare_all,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m bra.prepare",
        description=(
            "Build normalized, derived datasets and the data audit. "
            "Raw source files are only read, never modified."
        ),
    )
    parser.add_argument("--data-root", default="data", help="Root of the data tree.")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Derived CSV output directory (default: {DEFAULT_OUTPUT_DIR}).",
    )
    parser.add_argument(
        "--audit-json",
        default=DEFAULT_AUDIT_JSON,
        help=f"Machine-readable audit path (default: {DEFAULT_AUDIT_JSON}).",
    )
    parser.add_argument(
        "--audit-doc",
        default=DEFAULT_AUDIT_DOC,
        help=f"Markdown audit path (default: {DEFAULT_AUDIT_DOC}).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run = prepare_all(
            args.data_root,
            output_dir=args.output_dir,
            audit_json=args.audit_json,
            audit_doc=args.audit_doc,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Preparation failed: {exc}", file=sys.stderr)
        return 1

    summary = run.summary()
    print("Prepared derived datasets")
    print(f"  datasets:       {summary['datasets']}")
    print(f"  input records:  {summary['input_records']}")
    print(f"  output records: {summary['output_records']}")
    print(f"  output dir:     {args.output_dir}")
    print(f"  audit JSON:     {run.audit_json}")
    print(f"  audit document: {run.audit_doc}")
    print(f"  unresolved:     {len(run.audit['unresolved_issues'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
